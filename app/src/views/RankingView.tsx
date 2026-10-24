import { useEffect, useMemo } from 'react';
import { CompareBlock } from '../components/compare';
import { NoiseBadges, NoiseToggle, WeightControl, WindowRuler } from '../components/controls';
import { IconDownload, IconGrid } from '../components/icons';
import { InstrumentRow } from '../components/rows';
import { Disclosure, ErrorNote, Loading, Notice, Pager, Pct, Segmented } from '../components/ui';
import { Explain } from '../components/explain';
import { GlossaryTip, Term } from '../components/help';
import { EMPTY_REASONS, INSTRUMENT_HINT_SHORT, WINDOW_HINT_SHORT, hintLabels } from '../lib/codes';
import { downloadText, safeFilename, toCsv, type CsvValue } from '../lib/csv';
import * as f from '../lib/format';
import { useOverview, useWindowFull, useWindowHead } from '../lib/hooks';
import { endDayOf, exchangeOf, instName, unitOf } from '../lib/instruments';
import { canHideNoisy, isVeryLow, noiseFlags, quietRanked, turnoverOf, turnoverShort } from '../lib/turnover';
import { buildHash, navigate, updateParams, type Route } from '../lib/router';
import { overviewRow } from '../lib/groups';
import { cohortFor, cohortSize, hasGroupB, orderFor, parseGroup, parsePolicy, parseWeight, parseWindow, rankedEntries } from '../lib/scoring';
import type { Group, Instruments, Manifest, Policy, WindowData } from '../lib/types';
import type { RankedEntry } from '../lib/scoring';
import { useApp } from '../state/AppState';
import { PREVIEW } from '../lib/env';

const PAGE = 50;

/** Beschreibt die Vergleichsmenge der gewählten Rangliste in Alltagssprache. */
export function CohortNote({ win, policy, weight, universe, group = 'a' }: { win: WindowData; policy: Policy; weight: number; universe: number; group?: Group }) {
  const cohort = cohortFor(policy, weight);
  const v = win.counts.V;
  const u = win.counts.U;
  if (group === 'b') {
    const vl = win.counts.L ?? 0;
    const ul = win.counts.UL ?? 0;
    return (
      <div className="section-note">
        <p>
          Gruppe B: nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD (20 Sitzungen) – {f.integer(vl)} von {f.integer(v)} vergleichbaren Aktien für {f.windowLabel(win.h)}.
        </p>
        {cohort === 'v0' ? (
          <p>Diese Liste ist nur nach Kursrendite sortiert; Reihenfolge und Renditen wie in Gruppe A, ohne die übrigen Aktien.</p>
        ) : (
          <p>
            Bewertet werden {f.plural(ul, 'gleichmäßig gestiegene Aktie', 'gleichmäßig gestiegene Aktien')} dieser Gruppe. Perzentile und Rangscore beziehen sich nur auf die Gruppe B; die Rangscores sind
            deshalb nicht mit Gruppe A vergleichbar.
          </p>
        )}
      </div>
    );
  }
  return (
    <div className="section-note">
      <p>
        Teiluniversum: {f.integer(v)} von {f.integer(universe)} gelisteten Instrumenten für {f.windowLabel(win.h)} vergleichbar (veröffentlichte Kursrendite).
      </p>
      {cohort === 'v0' ? (
        <p>Diese Liste umfasst alle {f.integer(v)} und ist nur nach Kursrendite sortiert.</p>
      ) : (
        <p>
          Bewertet werden {f.plural(u, 'gleichmäßig gestiegene Aktie', 'gleichmäßig gestiegene Aktien')} (mindestens 15 echte Tageskurse, positive Rendite und positive Trendsteigung).
          {policy === 'common_trend' ? ' Gleiches Vergleichsfeld: alle elf Gewichtungen nutzen dieselben Aktien.' : ''}
          {policy === 'common_trend' && weight === 0 ? ' Dadurch ist auch 0/100 hier eingeschränkt.' : ''}
        </p>
      )}
    </div>
  );
}

/** Kennzahlen einer Aktie in diesem Fenster (Position in WindowData.m). */
function memberFacts(win: WindowData, member: number) {
  const m = win.m;
  return {
    start: m.start[member],
    n: m.n[member],
    nExp: m.n_exp[member],
    p0: m.p0?.[member] ?? null,
    p1: m.p1?.[member] ?? null,
    slope: m.slope[member],
    noise: m.noise[member],
    mdd: m.mdd[member],
    up: m.up?.[member] ?? null,
    vol: m.vol[member],
    wf: m.wf[member],
  };
}

/** Ausklappbare Details einer Ranglistenzeile (Auftrag: Ticker, Börse, Anfang, Schlusskurse, Steigung,
 * Rauschen, Rückgang, positive Schlusskursvergleiche, Datenquelle, Datenalter, Qualitätsstatus). */
function RankingDetails({ win, entry, instruments, manifest }: { win: WindowData; entry: RankedEntry; instruments: Instruments; manifest: Manifest }) {
  const x = memberFacts(win, entry.member);
  const idx = entry.idx;
  const unit = unitOf(instruments, idx);
  const turnover = turnoverOf(instruments, idx);
  const hints = [...hintLabels(WINDOW_HINT_SHORT, x.wf), ...hintLabels(INSTRUMENT_HINT_SHORT, instruments.warnings[idx] ?? 0)];
  if (isVeryLow(turnover, manifest)) hints.unshift('kaum Umsatz');
  const lastDay = instruments.last_close_day[idx];
  return (
    <Disclosure summary="Details">
      <dl className="kv">
        {(
          [
            ['Ticker / Symbol', [instruments.ticker[idx], instruments.symbol[idx]].filter(Boolean).join(' / ') || '–'],
            ['Referenzbörse', `${exchangeOf(instruments, idx) ?? '–'}${unit ? `, Kurse in ${unit}` : ''}`],
            ['Zeitraum (tatsächlich)', `${f.day(x.start)} bis ${f.day(endDayOf(instruments, idx, win.cutoff_day))} (Ziel-Start ${f.day(win.target_start_day)})`],
            ['Startkurs → Referenzschluss', `${f.price(x.p0, unit)} → ${f.price(x.p1, unit)}`],
            ['Schlusskurse im Fenster', `${f.integer(x.n)} von ${f.integer(x.nExp)} erwarteten Sitzungen`],
            ['Positive Schlusskursvergleiche', x.up !== null ? `${f.integer(x.up)} von ${f.integer(Math.max(0, x.n - 1))}` : 'nicht berechnet (Datenstand vor 1.5)'],
            ['Relative Steigung', x.slope !== null && x.slope !== undefined ? `${f.signedPctValue(x.slope, 3)} je Sitzung` : 'nicht berechenbar (unter 15 Schlusskursen)'],
            ['Residualrauschen', x.noise !== null && x.noise !== undefined ? f.plainPct(x.noise, 2) : 'nicht berechenbar'],
            ['Maximaler Rückgang', `−${f.plainPct(100 * x.mdd, 2)}`],
            ['Volumen belegt', f.plainPct(100 * x.vol, 0)],
            ['Ø Tagesumsatz (Referenzbörse)', turnoverShort(turnover, manifest)],
            ['Datenquelle', manifest.provider.prices],
            ['Datenalter', lastDay !== null && lastDay !== undefined ? `letzter Schlusskurs ${f.day(lastDay)}, berechnet ${f.berlinTime(manifest.computed_at_utc)}` : '–'],
            ['Qualitätsstatus', hints.length ? `geprüft; Hinweise: ${hints.join('; ')}` : 'alle Prüfungen bestanden, keine Hinweise'],
          ] as [string, string][]
        ).map(([k, v]) => (
          <div className="kv-row" key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </Disclosure>
  );
}

export function RankingView({ route }: { route: Route }) {
  const { manifest, instruments, prefs, setPrefs, isDemo } = useApp();
  const h = parseWindow(route.params.get('h'), prefs.h);
  const weight = parseWeight(route.params.get('w'), prefs.w);
  const policy = parsePolicy(route.params.get('p') ?? prefs.policy);
  const limitParam = route.params.get('n');
  const limit: '10' | '50' | 'alle' = limitParam === '50' || limitParam === 'alle' ? limitParam : '10';
  const page = Math.max(1, Number(route.params.get('seite') ?? 1) || 1);
  const showChart = route.params.get('chart') === '1';
  const requestedGroup = parseGroup(route.params.get('g'));

  const head = useWindowHead(h);
  const overview = useOverview();
  const groupsAvailable = head.data ? hasGroupB(head.data) : false;
  const group: Group = requestedGroup === 'b' && groupsAvailable ? 'b' : 'a';
  const size = head.data ? cohortSize(head.data, policy, weight, group) : 0;
  // Ab 1.14 „Auffällige ausblenden“: erst unter den ersten 50 Plätzen (Kopfdatei) suchen, die vollständige Datei nur laden,
  // wenn dort nicht genug unauffällige Aktien stehen
  const clean = prefs.ohneAuffaellige && canHideNoisy(instruments);
  const headQuiet = useMemo(
    () => (clean && head.data && instruments ? quietRanked(head.data, policy, weight, group, instruments, manifest) : null),
    [clean, head.data, policy, weight, group, instruments, manifest],
  );
  const headComplete = head.data ? orderFor(head.data, policy, weight, group).length >= size : false;
  const needFull = limit === 'alle' || Boolean(clean && headQuiet && !headComplete && headQuiet.length < Number(limit));
  const full = useWindowFull(h, needFull);
  const fullQuiet = useMemo(
    () => (clean && needFull && full.data && instruments ? quietRanked(full.data, policy, weight, group, instruments, manifest) : null),
    [clean, needFull, full.data, policy, weight, group, instruments, manifest],
  );

  useEffect(() => {
    if (prefs.h !== h || prefs.w !== weight || prefs.policy !== policy) setPrefs({ h, w: weight, policy });
  }, [h, weight, policy]);

  if (!manifest || !instruments) return null;
  const win = needFull ? full.data : head.data;
  const quiet = needFull ? fullQuiet : headQuiet;
  const shownSize = clean ? (quiet?.length ?? 0) : size;
  const pages = limit === 'alle' ? Math.max(1, Math.ceil(shownSize / PAGE)) : 1;
  const currentPage = Math.min(page, pages);
  const offset = limit === 'alle' ? (currentPage - 1) * PAGE : 0;
  const count = limit === 'alle' ? PAGE : Number(limit);
  const entries = win ? (clean ? (quiet ?? []).slice(offset, offset + count) : rankedEntries(win, policy, weight, offset, count, group)) : [];
  const hidden = clean && entries.length ? entries[entries.length - 1].rank - offset - entries.length : 0;
  const firstFive = clean ? (quiet ?? []).slice(0, 5) : head.data ? rankedEntries(head.data, policy, weight, 0, 5, group) : [];
  const cohort = cohortFor(policy, weight, group);
  const emptyRow = overview.data
    ? cohort === 'v0' || cohort === 'v0l'
      ? overviewRow(overview.data, group, 0, h)
      : (group === 'b' ? overview.data.ul?.[String(weight)] : overview.data.u[String(weight)])?.[h - 1]
    : undefined;
  const loadError = head.error ?? (needFull ? full.error : null);

  const setWindow = (next: number) => updateParams(route, { h: next, seite: null });

  const exportRanking = (format: 'csv' | 'json') => {
    const source = win;
    if (!source) return;
    const all = clean
      ? (quiet ?? []).slice(0, limit === 'alle' ? undefined : Number(limit))
      : rankedEntries(source, policy, weight, 0, limit === 'alle' ? size : Number(limit), group);
    const meta: [string, string][] = [
      ['Ansicht', 'Ranking nach Gewichtung'],
      ['Zeitraum', f.windowLabel(h)],
      ['Gewichtung', f.weightLabel(weight)],
      ['Aktiengruppe', group === 'b' ? 'B: Ø Tagesumsatz ≥ 10 Mio. USD (eigene Perzentile)' : 'A: alle vergleichbaren Aktien'],
      ['Vergleichsfeld', policy === 'native' ? 'nativ (0/100 auf V, sonst U)' : 'gleiches Feld (alle auf U)'],
      ['Vergleichsfeld M', String(size)],
      ...(clean ? ([['Auswahl', 'ohne Auffällige (Ø Tagesumsatz unter 1 Mio. USD oder nicht bestimmbar, Einzelsprung) – Rang wie in der vollständigen Rangliste']] as [string, string][]) : []),
      ['Rangscore', 'Perzentil-Score 0–100 innerhalb des Vergleichsfelds – keine Prognose, keine Wahrscheinlichkeit'],
      ['Snapshot', manifest.snapshot_id],
      ['Kursstichtag', manifest.cutoff_session_date],
      ['Berechnet', manifest.computed_at_utc],
      ['Datenmodus', manifest.data_mode === 'demo' ? 'DEMO – synthetische Testdaten' : manifest.data_mode],
      ['Kursquelle', manifest.provider.prices],
      ['Methode', manifest.versions.method ?? ''],
    ];
    const records = all.map((e) => {
      const x = memberFacts(source, e.member);
      const turnover = turnoverOf(instruments, e.idx);
      return {
        rang: e.rank,
        name: instName(instruments, e.idx),
        isin: instruments.isin[e.idx],
        ticker: instruments.ticker[e.idx] ?? instruments.symbol[e.idx] ?? null,
        referenzboerse: exchangeOf(instruments, e.idx),
        kurseinheit: unitOf(instruments, e.idx),
        rangscore: e.score,
        kursrendite_prozent: 100 * e.r,
        r2: e.r2,
        perzentil_gleichmaessigkeit: e.g,
        perzentil_rendite: e.rPct,
        beginn: f.day(x.start),
        ende: f.day(endDayOf(instruments, e.idx, source.cutoff_day)),
        startkurs: x.p0,
        referenzschluss: x.p1,
        schlusskurse: x.n,
        positive_schlusskursvergleiche: x.up,
        relative_steigung_prozent_je_sitzung: x.slope,
        residualrauschen_prozent: x.noise,
        max_rueckgang_prozent: 100 * x.mdd,
        umsatz_usd: turnover?.status === 'ok' ? turnover.usd : null,
        gleichstand: e.tie,
      };
    });
    const name = `ranking_${h}T_w${weight}_${policy}${group === 'b' ? '_gruppeB' : ''}_${manifest.snapshot_id}`;
    if (format === 'json') {
      downloadText(safeFilename(`${name}.json`), JSON.stringify({ format: 'tr-rangliste/1', meta: Object.fromEntries(meta), eintraege: records }, null, 2), 'application/json;charset=utf-8');
      return;
    }
    const rows: CsvValue[][] = records.map((r) => [
      r.rang,
      r.name,
      r.isin,
      r.rangscore,
      r.kursrendite_prozent,
      r.r2,
      r.referenzschluss,
      r.kurseinheit,
      r.umsatz_usd,
      r.ticker,
      r.referenzboerse,
      r.beginn,
      r.ende,
      r.schlusskurse,
      r.positive_schlusskursvergleiche,
      r.relative_steigung_prozent_je_sitzung,
      r.residualrauschen_prozent,
      r.max_rueckgang_prozent,
      r.perzentil_gleichmaessigkeit,
      r.perzentil_rendite,
      r.gleichstand ? 'Gleichstand' : '',
    ]);
    const csv = toCsv(
      meta,
      ['Rang', 'Unternehmen', 'ISIN', 'Rangscore', 'Kursrendite %', 'R²', 'Referenzschluss', 'Kurseinheit', 'Ø Tagesumsatz USD', 'Ticker', 'Referenzbörse', 'Beginn', 'Ende', 'Schlusskurse', 'Positive Schlusskursvergleiche', 'Relative Steigung % je Sitzung', 'Residualrauschen %', 'Max. Rückgang %', 'Gleichmäßigkeit-Perzentil', 'Rendite-Perzentil', 'Hinweis'],
      rows,
      [undefined, undefined, undefined, 4, 6, 6],
    );
    downloadText(safeFilename(`${name}.csv`), csv);
  };

  return (
    <div className="view">
      <header className="view-head">
        <Explain
          kinds={['rueckblick', 'rang']}
          term="rangscore"
          sees={
            <>
              Eine Rangliste der vergleichbaren Aktien für den gewählten Zeitraum. Oben stehen Aktien, die stark <em>und</em> gleichmäßig gestiegen sind – je nach
              Gewichtung zählt das eine oder das andere mehr.
            </>
          }
          todo={
            <>
              Zeitraum und <Term id="gewichtung">Gewichtung</Term> wählen, dann eine Aktie antippen: Sie zeigt alle Zahlen und den Kursverlauf.
            </>
          }
          numbers={[
            [<Term id="kursrendite">Kursrendite</Term>, 'Wie viel Prozent der Kurs vom Startkurs bis zum Kursstand gestiegen oder gefallen ist.'],
            [<Term id="gleichmaessigkeit">R² (Gleichmäßigkeit)</Term>, 'Von 0 bis 1: wie gerade der Kurs verlaufen ist. 1 heißt fast wie mit dem Lineal. R² sagt nichts über die Richtung – die zeigt die Kursrendite.'],
            [<Term id="rangscore">Rangscore</Term>, '0 bis 100, danach ist die Liste sortiert. Er verbindet die Plätze bei Gleichmäßigkeit und Kursrendite nach der Gewichtung.'],
          ]}
          how={
            <>
              <p>
                Für jede Aktie zählt, welchen Platz sie bei der Kursrendite und bei der Gleichmäßigkeit unter allen vergleichbaren Aktien hat – als{' '}
                <Term id="perzentil">Perzentil</Term> von 0 (schlechteste) bis 100 (beste). Der Rangscore gewichtet beide: Die erste Zahl der Gewichtung gilt für die
                Gleichmäßigkeit, die zweite für die Kursrendite.
              </p>
              <p>Sobald die Gleichmäßigkeit mitzählt, kommen nur Aktien in die Liste, die im Zeitraum gestiegen sind und mindestens 15 Tageskurse haben.</p>
            </>
          }
          example={<>Gewichtung 60/40, Gleichmäßigkeit-Perzentil 50, Rendite-Perzentil 90: 0,6 × 50 + 0,4 × 90 = 66.</>}
        />
      </header>
      <WindowRuler value={h} onChange={setWindow}>
        {head.data ? (
          <p>
            Rückblick ab <strong>{f.dayWithWeekday(head.data.target_start_day)}</strong> bis Kursstand <strong>{f.dayWithWeekday(head.data.cutoff_day)}</strong>. Startkurs ist der letzte Börsenschluss am oder vor dem Ziel-Startdatum.
          </p>
        ) : null}
      </WindowRuler>
      <WeightControl weight={weight} onWeight={(w) => updateParams(route, { w, seite: null })} policy={policy} onPolicy={(p) => updateParams(route, { p, seite: null })} />
      {groupsAvailable ? (
        <Segmented
          label="Aktiengruppe"
          options={[
            { value: 'a', label: 'A: alle Aktien' },
            { value: 'b', label: 'B: Ø Umsatz ≥ 10 Mio. USD' },
          ]}
          value={group}
          onChange={(g) => updateParams(route, { g: g === 'b' ? 'b' : null, seite: null })}
        />
      ) : null}

      {loadError ? <ErrorNote error={loadError} /> : null}
      {head.data ? <CohortNote win={head.data} policy={policy} weight={weight} universe={manifest.coverage.universe_total} group={group} /> : null}
      {canHideNoisy(instruments) && size > 0 ? <NoiseToggle /> : null}

      {head.data && size === 1 ? (
        <Notice tone="info" title="Einziger qualifizierter Titel – keine relative Konkurrenzbewertung">
          <p>Rangscore 100 bedeutet hier nur, dass keine andere Aktie die Bedingungen erfüllt.</p>
        </Notice>
      ) : null}
      {head.data && size > 1 && size < 10 ? (
        <Notice tone="info" title="Kleines Vergleichsfeld">
          <p>Nur {f.plural(size, 'Aktie erfüllt', 'Aktien erfüllen')} die Bedingungen. Ein Platz unter den ersten zehn ist hier keine Platzierung gegenüber dem gesamten TR-Angebot.</p>
        </Notice>
      ) : null}

      {head.data && size === 0 ? (
        <Notice tone="info" title="Keine Rangliste für diese Auswahl">
          <p>{EMPTY_REASONS[emptyRow?.empty ?? ''] ?? EMPTY_REASONS.keine_vergleichbare_aktie}</p>
          {cohortFor(policy, weight) === 'u' && head.data.counts.V > 0 ? (
            <div className="notice-actions">
              <a className="btn btn-primary" href={buildHash('/ranking', { h, w: 0, p: 'native', g: group === 'b' ? 'b' : null })}>
                Reine Renditeliste (0/100) zeigen
              </a>
            </div>
          ) : null}
        </Notice>
      ) : null}

      {size > 0 ? (
        <>
          <div className="toolbar no-print">
            <Segmented
              label="Umfang"
              hideLabel
              options={[
                { value: '10', label: 'Top 10' },
                { value: '50', label: 'Top 50' },
                { value: 'alle', label: clean && needFull && quiet ? `Alle ${f.integer(quiet.length)}` : clean ? 'Alle' : `Alle ${f.integer(size)}` },
              ]}
              value={limit}
              onChange={(value) => updateParams(route, { n: value === '10' ? null : value, seite: null })}
            />
          </div>
          <div className="row-legend">
            <p>Rechts in jeder Zeile:</p>
            <ul>
              <li>
                <strong>Prozentzahl</strong> – die Kursrendite im Zeitraum <GlossaryTip id="kursrendite" label="Kursrendite" />
              </li>
              <li>
                <strong>Rangscore</strong> – 0 bis 100, danach ist sortiert <GlossaryTip id="rangscore" label="Rangscore" />
              </li>
              <li>
                <strong>R²</strong> – Gleichmäßigkeit, 0 bis 1 <GlossaryTip id="gleichmaessigkeit" label="R² (Gleichmäßigkeit)" />
              </li>
            </ul>
          </div>
          {!win && !loadError ? <Loading height={limit === '10' ? 760 : 1400} label="Rangliste wird geladen" /> : null}
          {win && clean && !entries.length ? (
            <p className="empty-body">Auf diesen Plätzen stehen nur auffällige Aktien. Ohne Haken bei „Auffällige ausblenden“ erscheint die vollständige Rangliste.</p>
          ) : null}
          {win && entries.length ? (
            <ol className="rows" aria-label={`Rangliste ${f.windowLabel(h)}, ${f.weightLabel(weight)}${group === 'b' ? ', Gruppe B' : ''}`} start={clean ? undefined : offset + 1}>
              {entries.map((entry) => {
                const x = memberFacts(win, entry.member);
                const unit = unitOf(instruments, entry.idx);
                return (
                  <InstrumentRow
                    key={entry.idx}
                    idx={entry.idx}
                    rank={entry.rank}
                    tie={entry.tie}
                    href={buildHash(`/aktie/${instruments.isin[entry.idx]}`, { h, w: weight, p: policy })}
                    meta={
                      <>
                        {entry.tie ? <span className="badge">gleichauf</span> : null}
                        <NoiseBadges flags={noiseFlags(instruments, manifest, entry.idx, x.wf)} />
                        <span className="row-alt">
                          Schluss {f.day(endDayOf(instruments, entry.idx, win.cutoff_day))}: {f.price(x.p1, unit)} · {turnoverShort(turnoverOf(instruments, entry.idx), manifest)}
                        </span>
                      </>
                    }
                    figs={
                      <>
                        <Pct value={entry.r} strong />
                        <span className="row-fig-sub">Rangscore {f.score(entry.score)}</span>
                        <span className="row-fig-sub">R² {entry.r2 !== null ? f.r2(entry.r2) : '–'}</span>
                      </>
                    }
                  >
                    <RankingDetails win={win} entry={entry} instruments={instruments} manifest={manifest} />
                  </InstrumentRow>
                );
              })}
            </ol>
          ) : null}
          {limit === 'alle' ? <Pager page={currentPage} pages={pages} onChange={(p) => updateParams(route, { seite: p })} label="Seiten der Rangliste" /> : null}
          {clean && entries.length ? (
            <p className="section-note">
              Ohne Auffällige: Plätze wie in der vollständigen Rangliste ({f.integer(size)} Aktien)
              {hidden ? `; bis Platz ${f.integer(entries[entries.length - 1].rank)} ${hidden === 1 ? 'ist 1 Aktie' : `sind ${f.integer(hidden)} Aktien`} ausgeblendet` : ''}.
            </p>
          ) : null}
          {!clean && limit !== 'alle' && size > Number(limit) ? (
            <p className="section-note">
              Gezeigt: Platz 1 bis {f.integer(Math.min(size, Number(limit)))} von {f.integer(size)}.
            </p>
          ) : null}

          <div className="toolbar no-print">
            <button type="button" className="btn" onClick={() => navigate('/raster', { quelle: 'ranking', n: limit === '10' ? 10 : 50, h, w: weight, p: policy, g: group === 'b' ? 'b' : null })}>
              <IconGrid /> Im Chart-Raster öffnen
            </button>
            {!PREVIEW ? (
              <>
                <button type="button" className="btn btn-quiet" onClick={() => exportRanking('csv')} disabled={!win}>
                  <IconDownload /> CSV
                </button>
                <button type="button" className="btn btn-quiet" onClick={() => exportRanking('json')} disabled={!win}>
                  <IconDownload /> JSON
                </button>
              </>
            ) : null}
          </div>

          {head.data && (!clean || quiet?.length) ? (
            <Disclosure summary="Kursverlauf der ersten fünf, gemeinsam indexiert" defaultOpen={showChart}>
              <CompareBlock
                isins={firstFive.map((e) => instruments.isin[e.idx])}
                h={h}
                cutoffDay={head.data.cutoff_day}
                rankingReturns={new Map(firstFive.map((e) => [instruments.isin[e.idx], e.r]))}
              />
            </Disclosure>
          ) : null}
        </>
      ) : null}

      {isDemo ? <p className="section-note">DEMO: synthetische Testdaten, keine echten Unternehmen.</p> : null}
    </div>
  );
}
