import { useState } from 'react';
import { PriceChart } from '../components/charts';
import { WindowRuler } from '../components/controls';
import { IconDownload } from '../components/icons';
import { Disclosure, ErrorNote, IsinCopy, KeyValues, Loading, Notice, Pct, Segmented, SectionTitle, WatchButton } from '../components/ui';
import { gapsWithin, transform, windowPoints, type ValueMode } from '../lib/chartmath';
import { IDENTITY_LABELS, READY_LEVEL, statusInfo, warningTexts } from '../lib/codes';
import { downloadBlob, safeFilename } from '../lib/csv';
import { PNG_COLORS, renderPng } from '../lib/exportpng';
import * as f from '../lib/format';
import { useSeries, useWindowFull, useWindowHead } from '../lib/hooks';
import { exchangeOf, instName, trNameIfDifferent, typeLabel, unitOf } from '../lib/instruments';
import { buildHash, updateParams, type Route } from '../lib/router';
import { cohortFor, decodeRanks, entryScores, memberIndex, parsePolicy, parseWeight, parseWindow, rankFromMatrix, WEIGHTS } from '../lib/scoring';
import type { Manifest, Policy, SeriesData, WindowData } from '../lib/types';
import { useApp } from '../state/AppState';
import { PREVIEW } from '../lib/env';

const RETURN_OK = [15, 16, 17, 18];
const TREND_OK = 18;

function reasonFor(manifest: Manifest, status: number | null, cohort: 'v0' | 'u'): string {
  if (status === null) return 'keine Daten';
  if (cohort === 'v0') return RETURN_OK.includes(status) ? '' : statusInfo(manifest, status).kurz ?? '';
  if (status === TREND_OK) return '';
  return statusInfo(manifest, status).kurz ?? '';
}

function RankMatrix({ series, win, idx, h, policy }: { series: SeriesData; win: WindowData | null; idx: number; h: number; policy: Policy }) {
  const { manifest } = useApp();
  const ranks = decodeRanks(series.ranks_b64);
  const status = series.window_status[h - 1] ?? null;
  const member = win ? memberIndex(win).get(idx) : undefined;
  const cell = (p: Policy, w: number) => {
    const cohort = cohortFor(p, w);
    const rank = rankFromMatrix(ranks, h, p, w);
    if (rank === null) return <span className="muted">{reasonFor(manifest!, status, cohort) || 'kein Rang'}</span>;
    const size = win ? (cohort === 'v0' ? win.counts.V : win.counts.U) : null;
    const inCohort = win && member !== undefined && (cohort === 'v0' || win.m.a_gu[member] !== null);
    const score = inCohort ? entryScores(win!, member!, cohort, w).score : null;
    return (
      <>
        <span className="cell-rank">{rank}</span>
        {size !== null ? <span className="muted"> von {f.integer(size)}</span> : null}
        <br />
        <span className="muted">{score !== null ? `Score ${f.score(score)}` : 'Score wird geladen'}</span>
      </>
    );
  };
  return (
    <div className="table-wrap">
      <table className="table">
        <caption>
          {f.windowLabel(h)}: Rang und Score je Gewichtung. Hervorgehoben ist das gewählte Vergleichsfeld ({policy === 'native' ? 'nativ' : 'gleiches Feld'}).
        </caption>
        <thead>
          <tr>
            <th scope="col">Gewichtung</th>
            <th scope="col" className="n">
              Nativ
            </th>
            <th scope="col" className="n">
              Gleiches Feld
            </th>
          </tr>
        </thead>
        <tbody>
          {WEIGHTS.map((w) => (
            <tr key={w}>
              <th scope="row">
                {w} % Gleichmäßigkeit
                <br />
                <span className="muted">{100 - w} % Rendite</span>
              </th>
              <td className="n" style={policy === 'native' ? { fontWeight: 600 } : undefined}>
                {cell('native', w)}
              </td>
              <td className="n" style={policy === 'common_trend' ? { fontWeight: 600 } : undefined}>
                {cell('common_trend', w)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DetailView({ route, isin }: { route: Route; isin: string }) {
  const { manifest, instruments, isinIndex, prefs, isDemo } = useApp();
  const h = parseWindow(route.params.get('h'), prefs.h);
  const weight = parseWeight(route.params.get('w'), prefs.w);
  const policy = parsePolicy(route.params.get('p') ?? prefs.policy);
  const modeParam = route.params.get('ansicht');
  const mode: ValueMode = modeParam === 'index' || modeParam === 'prozent' ? modeParam : 'absolut';
  const candles = route.params.get('kerzen') === '1';
  const showFit = route.params.get('anpassung') !== '0';
  const idx = isinIndex.get(isin);
  const series = useSeries(idx !== undefined && instruments?.has_series[idx] ? isin : null);
  const head = useWindowHead(h);
  const status = series.data ? series.data.window_status[h - 1] : null;
  const inV = status !== null && RETURN_OK.includes(status);
  const inHead = head.data && idx !== undefined ? memberIndex(head.data).has(idx) : false;
  const full = useWindowFull(h, Boolean(head.data) && inV && !inHead);
  const [exporting, setExporting] = useState(false);

  if (!manifest || !instruments) return null;
  if (idx === undefined) {
    return (
      <Notice tone="warn" title="ISIN nicht in diesem Datenstand">
        <p>{isin} ist in der TR-Aktienliste des gewählten Stands nicht enthalten.</p>
      </Notice>
    );
  }

  const name = instName(instruments, idx);
  const trName = trNameIfDifferent(instruments, idx);
  const unit = unitOf(instruments, idx);
  const levelStatus = instruments.level_status[idx];
  const win = inHead ? head.data : full.data;
  const member = win ? memberIndex(win).get(idx) : undefined;
  const m = win && member !== undefined ? win.m : null;
  const pos = member ?? -1;
  const chart = series.data ? windowPoints(series.data, h, manifest.cutoff_day) : null;
  const gaps = series.data && chart && chart.pts.length ? gapsWithin(series.data, chart.pts[0].day, manifest.cutoff_day) : [];
  const warnings = warningTexts(manifest.codes.instrument_warnings, instruments.warnings[idx]);
  const windowWarnings = m ? warningTexts(manifest.codes.window_warnings, m.wf[pos]) : [];
  const lastDay = instruments.last_close_day[idx];

  const marketText = (() => {
    if (levelStatus === 7) return `Börse am Kursstichtag ${f.day(manifest.cutoff_day)} geschlossen – letzter Kurs vom ${f.day(lastDay)}.`;
    if (levelStatus === 8) return `Börse am Kursstichtag geöffnet, aber kein geprüfter Schlusskurs vorhanden. Letzter Kurs vom ${f.day(lastDay)}.`;
    if (levelStatus === READY_LEVEL) return `Letzter regulärer Schluss vom ${f.day(lastDay)}.`;
    return statusInfo(manifest, levelStatus).text;
  })();

  const exportPng = async () => {
    if (!series.data || !chart) return;
    setExporting(true);
    try {
      const base = chart.pts[0]?.close ?? 1;
      const blob = await renderPng({
        heading: `${name} (${isin})`,
        meta: [
          `${f.windowLabel(h)}: ${chart.pts.length ? f.dayRange(chart.pts[0].day, chart.pts[chart.pts.length - 1].day) : 'keine Kurse'}. ${mode === 'absolut' ? `Kurs in ${unit ?? '–'}` : mode === 'index' ? 'Index: Start = 100' : 'Veränderung in Prozent seit Start'}.`,
          `${exchangeOf(instruments, idx) ?? ''}, splitbereinigte Tagesschlusskurse. Quelle: ${series.data.source.provider ?? manifest.provider.prices}${isDemo ? ' (DEMO – synthetische Testdaten)' : ''}. Kursstand ${f.day(manifest.cutoff_day)}, Snapshot ${manifest.snapshot_id}.`,
        ],
        panels: [
          {
            title: name,
            subtitle: [m ? `Kursrendite ${f.pct(m.r[pos])}${m.r2[pos] !== null ? `, R² ${f.r2(m.r2[pos])}` : ''}` : 'Kursrendite für diesen Zeitraum nicht veröffentlicht'],
            lines: [{ color: PNG_COLORS[0], points: chart.pts.map((p) => ({ day: p.day, value: transform(p.close, base, mode) })), gaps }],
            xDomain: [chart.pts[0]?.day ?? manifest.cutoff_day - h, manifest.cutoff_day],
            yMode: mode,
          },
        ],
        columns: 1,
        panelWidth: 760,
        plotHeight: 300,
        footer: ['Momentaufnahme der historischen Tagesschlusskurse; keine Liveansicht, keine Prognose.'],
      });
      downloadBlob(safeFilename(`kurschart_${isin}_${h}T_${manifest.snapshot_id}.png`), blob);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="view">
      <header className="view-head">
        <h2 className="view-title">{name}</h2>
        {trName ? <p className="row-alt">In der TR-Liste: {trName}</p> : null}
        <div className="toolbar">
          <IsinCopy isin={isin} />
          <WatchButton isin={isin} name={name} />
        </div>
        <KeyValues
          items={[
            ['Ticker / Symbol', [instruments.ticker[idx], instruments.symbol[idx]].filter(Boolean).join(' / ') || '–'],
            ['Instrumenttyp', typeLabel(instruments, idx)],
            ['Referenzbörse', `${exchangeOf(instruments, idx) ?? '–'}${instruments.mic[idx] ? ` (${instruments.mic[idx]})` : ''}`],
            ['Währung und Einheit', unit ? `${unit}${unit !== instruments.currency[idx] && instruments.currency[idx] ? ` (Untereinheit von ${instruments.currency[idx]})` : ''}` : '–'],
            ['Letzter verwendeter Schlusskurs', instruments.last_close[idx] !== null ? `${f.price(instruments.last_close[idx], unit)} am ${f.day(lastDay)}` : 'keiner'],
            ['Marktstatus', marketText],
            ['TR-Listung', `In der offiziellen TR-Aktienliste (abgerufen ${f.berlinTime(manifest.universe.retrieved_at_utc)}). Keine Zusage, dass die Aktie im eigenen Konto sofort handelbar ist.`],
            ['Identität', `${IDENTITY_LABELS[instruments.identity[idx]] ?? instruments.identity[idx]}${instruments.identity_reason[idx] ? ` (${instruments.identity_reason[idx]})` : ''}`],
          ]}
        />
        {warnings.length ? (
          <Notice tone="warn" title="Hinweise zu diesem Instrument">
            <ul className="prose" style={{ gap: 2 }}>
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </Notice>
        ) : null}
      </header>

      <WindowRuler value={h} onChange={(next) => updateParams(route, { h: next })}>
        {chart && chart.pts.length ? (
          <p>
            Tatsächlich: <strong>{f.dayWithWeekday(chart.pts[0].day)}</strong> bis <strong>{f.dayWithWeekday(chart.pts[chart.pts.length - 1].day)}</strong>
          </p>
        ) : null}
      </WindowRuler>

      {!instruments.has_series[idx] ? (
        <Notice tone="info" title="Keine Kursdaten">
          <p>{statusInfo(manifest, levelStatus).text || 'Für dieses Instrument liegen keine verwertbaren Kurse vor.'} Es wird kein Ersatzverlauf gezeigt.</p>
        </Notice>
      ) : null}
      {series.error ? <ErrorNote error={series.error} /> : null}

      {series.data && chart ? (
        <>
          <section className="section" aria-labelledby="kennzahlen">
            <SectionTitle id="kennzahlen">Kennzahlen für {f.windowLabel(h)}</SectionTitle>
            {status !== null && !inV ? (
              <Notice tone="info" title={statusInfo(manifest, status).kurz ?? 'Nicht berechenbar'}>
                <p>{statusInfo(manifest, status).text} Für diesen Zeitraum wird keine Kursrendite veröffentlicht.</p>
              </Notice>
            ) : null}
            {inV && !m ? (full.error ? <ErrorNote error={full.error} /> : <Loading height={320} label="Kennzahlen werden geladen" />) : null}
            {m ? (
              <>
                <div className="fig">
                  <Pct value={m.r[pos]} strong />
                  <span className="fig-label">
                    Kursrendite vom {f.day(m.start[pos])} bis {f.day(win!.cutoff_day)}
                  </span>
                </div>
                <KeyValues
                  items={[
                    ['Börsensitzungen', `${f.integer(m.n[pos])} mit Kurs von ${f.integer(m.n_exp[pos])} erwarteten`],
                    [
                      'Gleichmäßigkeit R²',
                      m.r2[pos] !== null ? (
                        <>
                          <strong>{f.r2(m.r2[pos])}</strong>
                          <br />
                          <span className="muted">Nähe zu einer geraden Preislinie; 1 wäre exakt gerade. Kein Maß für Sicherheit oder künftige Kurse.</span>
                        </>
                      ) : (
                        `nicht berechenbar (${m.n[pos] < 15 ? `mindestens 15 echte Tageskurse nötig, vorhanden ${m.n[pos]}` : 'Kurs blieb konstant'})`
                      ),
                    ],
                    ['Relative Steigung', m.slope[pos] !== null ? `${f.signedPctValue(m.slope[pos], 3)} je Handelstag (bezogen auf den Durchschnittskurs)` : '–'],
                    ['Residualrauschen', m.noise[pos] !== null ? `${f.plainPct(m.noise[pos], 2)} typische Abweichung von der Geraden` : '–'],
                    ['Größter Rückgang im Zeitraum', f.pct(-m.mdd[pos])],
                    ['Volumenabdeckung', `${f.plainPct(100 * m.vol[pos], 0)} der Tage mit belegtem Umsatz`],
                    ['Aufwärtsbewertung', status === TREND_OK ? 'bewertbar: gleichmäßig gestiegen, in allen elf Gewichtungen enthalten' : statusInfo(manifest, status ?? 0).text],
                  ]}
                />
                {windowWarnings.length ? (
                  <Notice tone="warn" title="Hinweise zu diesem Zeitraum">
                    {windowWarnings.map((w) => (
                      <p key={w}>{w}</p>
                    ))}
                  </Notice>
                ) : null}
              </>
            ) : null}
          </section>

          <section className="section" aria-labelledby="kurs">
            <SectionTitle id="kurs">Kursverlauf</SectionTitle>
            <Segmented
              label="Darstellung"
              hideLabel
              options={[
                { value: 'absolut', label: 'Kurs' },
                { value: 'index', label: 'Index 100' },
                { value: 'prozent', label: 'Prozent' },
              ]}
              value={mode}
              onChange={(value) => updateParams(route, { ansicht: value === 'absolut' ? null : value })}
            />
            <div className="toolbar">
              {series.data.ohlc_complete ? (
                <label className="check">
                  <input type="checkbox" checked={candles} onChange={(e: Event) => updateParams(route, { kerzen: (e.target as HTMLInputElement).checked ? 1 : null })} />
                  <span>Kerzen (Eröffnung, Hoch, Tief, Schluss)</span>
                </label>
              ) : null}
              {m && m.r2[pos] !== null ? (
                <label className="check">
                  <input type="checkbox" checked={showFit} onChange={(e: Event) => updateParams(route, { anpassung: (e.target as HTMLInputElement).checked ? null : 0 })} />
                  <span>Anpassung an vergangene Kurse</span>
                </label>
              ) : null}
            </div>
            <PriceChart
              title={name}
              pts={chart.pts}
              gaps={gaps}
              start={chart.start}
              end={manifest.cutoff_day}
              unit={unit}
              mode={mode}
              candles={candles && series.data.ohlc_complete}
              showFit={showFit && Boolean(m && m.r2[pos] !== null)}
              publishedSlopePct={m ? m.slope[pos] : null}
              caption={
                <>
                  <span>
                    Splitbereinigter historischer Kursverlauf (Tagesschlusskurse), {exchangeOf(instruments, idx) ?? 'Börse unbekannt'}, {mode === 'absolut' ? `in ${unit ?? '–'}` : mode === 'index' ? 'Index mit Startwert 100 (kein Eurobetrag)' : 'Veränderung seit Start in Prozent'}. Quelle: {series.data.source.provider ?? manifest.provider.prices}, abgerufen {f.berlinTime(series.data.source.fetched_at)}.
                  </span>
                  {h === 1 ? <span>1 Kalendertag: gezeigt werden nur die belegten Tagesschlusskurse, kein Tagesverlauf. Intradaydaten sind nicht verfügbar.</span> : null}
                  {chart.fallback ? <span>Für dieses Fenster gibt es keine gültige Startsitzung; gezeigt wird die verfügbare Historie ab {f.day(chart.pts[0]?.day)}.</span> : null}
                </>
              }
            />
            {!PREVIEW ? (
              <div className="toolbar no-print">
                <button type="button" className="btn" disabled={exporting || !chart.pts.length} onClick={() => void exportPng()}>
                  <IconDownload /> {exporting ? 'PNG wird erstellt …' : 'Als PNG speichern'}
                </button>
                <button type="button" className="btn btn-quiet" onClick={() => window.print()}>
                  Drucken
                </button>
              </div>
            ) : null}
            <Disclosure summary="Kurse als Tabelle">
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">Datum</th>
                      <th scope="col" className="n">
                        Schluss ({unit ?? '–'})
                      </th>
                      <th scope="col" className="n">
                        Volumen
                      </th>
                      {series.data.c_raw ? (
                        <th scope="col" className="n">
                          Unbereinigt
                        </th>
                      ) : null}
                    </tr>
                  </thead>
                  <tbody>
                    {[...chart.pts].reverse().map((p) => (
                      <tr key={p.day}>
                        <td>{f.dayWithWeekday(p.day)}</td>
                        <td className="n">{f.price(p.close)}</td>
                        <td className="n">{f.volume(p.volume)}</td>
                        {series.data!.c_raw ? <td className="n">{p.closeRaw !== null && Math.abs(p.closeRaw - p.close) > 1e-9 * Math.abs(p.close) ? f.price(p.closeRaw) : 'gleich'}</td> : null}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {gaps.length ? <p className="section-note">Fehlende erwartete Sitzungen: {gaps.map((d) => f.day(d)).join(', ')}. Dafür werden keine Kurse erzeugt.</p> : null}
            </Disclosure>
            {series.data.events.length ? (
              <p className="section-note">
                Kapitalmaßnahmen in der geladenen Historie:{' '}
                {series.data.events.map((e) => `${e.type === 'split' ? 'Split' : e.type} am ${f.day(e.day)} (Faktor ${e.factor.toLocaleString('de-DE')})`).join('; ')}. Frühere Kurse sind entsprechend bereinigt und waren damals so nicht handelbar.
              </p>
            ) : null}
          </section>

          <section className="section" aria-labelledby="ränge">
            <SectionTitle id="ränge">Rang in allen elf Gewichtungen</SectionTitle>
            <RankMatrix series={series.data} win={win ?? null} idx={idx} h={h} policy={policy} />
            <div className="toolbar">
              <a className="btn" href={buildHash(`/haeufig/${isin}`, { p: policy })}>
                Alle 90 Zeiträume als Matrix
              </a>
              <a className="btn btn-quiet" href={buildHash('/ranking', { h, w: weight, p: policy })}>
                Zur Rangliste
              </a>
            </div>
          </section>
        </>
      ) : instruments.has_series[idx] && !series.error ? (
        <Loading height={520} label="Kursreihe wird geladen" />
      ) : null}

      <section className="section" aria-labelledby="heute">
        <SectionTitle id="heute">Heute / Kurs aktuell</SectionTitle>
        <p className="section-note">
          Für diese Installation ist keine Live- oder Intradayquelle eingerichtet. Angezeigt wird der letzte reguläre Schluss vom {f.day(lastDay)} an der Referenzbörse in {unit ?? 'Notierungswährung'}. Ein Börsenschluss ist kein ausführbarer Trade-Republic-Kurs.
        </p>
      </section>
    </div>
  );
}
