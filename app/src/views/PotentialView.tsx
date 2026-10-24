import { useMemo, useState } from 'react';
import { InstrumentRow } from '../components/rows';
import { ConsistencyStrip, InfoTip, LightTag, TotalBadge } from '../components/signals';
import { Disclosure, ErrorNote, Loading, Notice, Segmented, ViewIntro } from '../components/ui';
import * as f from '../lib/format';
import { useSignals } from '../lib/hooks';
import { consistencyCells, gradeOf, hasTotal, LIST_INFO, LIST_KINDS, parseListKind, rankSignals, reasonChips, sectorName, totalOf, type ListKind } from '../lib/signals';
import { buildHash, updateParams, type Route } from '../lib/router';
import { thresholdLabel } from '../lib/turnover';
import type { SignalsData } from '../lib/types';
import { useApp } from '../state/AppState';
import { capText } from '../lib/top';

const PAGE = 25;

/** Hauptzahl einer Zeile je Liste. */
function MainFigure({ data, k, kind }: { data: SignalsData; k: number; kind: ListKind }) {
  if (kind === 'gesamt') {
    const total = totalOf(data, k);
    return (
      <>
        <TotalBadge total={total} grade={gradeOf(total, data)} />
        <span className="row-fig-sub">{hasTotal(data) ? 'Gesamt' : 'Ø kurz/lang'}</span>
      </>
    );
  }
  if (kind === 'volumen') {
    const rvol = data.merkmale.rvol?.[k] ?? null;
    return (
      <>
        <span className="sig-points">{rvol === null ? '–' : `${new Intl.NumberFormat('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(rvol)}×`}</span>
        <span className="row-fig-sub">Volumen üblich</span>
      </>
    );
  }
  if (kind === 'potenzial' || (kind === 'lang' && data.potenzial[k] !== null)) {
    const upside = data.potenzial[k];
    return (
      <>
        <span className={`pct pct-strong ${upside !== null && upside >= 0 ? 'pct-plus' : 'pct-minus'}`}>{f.pct(upside, 0)}</span>
        <span className="row-fig-sub">bis Ø Kursziel</span>
      </>
    );
  }
  const points = kind === 'kurz' ? data.kurz[k] : kind === 'lang' ? data.lang[k] : null;
  return (
    <>
      <span className="sig-points">{points === null ? '–' : Math.round(points)}</span>
      <span className="row-fig-sub">von 100 Punkten</span>
    </>
  );
}

/** Zeilen einer Signal-Liste (auch für die Startseite). */
export function SignalRows({ data, order, kind, limit, offset = 0 }: { data: SignalsData; order: number[]; kind: ListKind; limit: number; offset?: number }) {
  const { instruments, isinIndex } = useApp();
  if (!instruments) return null;
  const rows = order.slice(offset, offset + limit);
  return (
    <ol className="rows sig-rows" start={offset + 1}>
      {rows.map((k, i) => {
        const idx = isinIndex.get(data.isin[k]);
        if (idx === undefined) return null;
        const chips = reasonChips(data, k, kind);
        const cells = kind === 'gesamt' ? consistencyCells(data, k) : [];
        return (
          <InstrumentRow
            key={data.isin[k]}
            idx={idx}
            rank={offset + i + 1}
            href={buildHash(`/aktie/${data.isin[k]}`, { tab: 'signale' })}
            meta={
              <>
                <span className="sig-lights">
                  <LightTag light={data.kurz_ampel[k]} label="kurz" compact />
                  <LightTag light={data.lang_ampel[k]} label="lang" compact />
                </span>
                {data.boersenwert_eur?.[k] != null ? <span className="row-cap">Börsenwert {capText(data.boersenwert_eur[k])}</span> : null}
              </>
            }
            figs={<MainFigure data={data} k={k} kind={kind} />}
          >
            {cells.length ? <ConsistencyStrip cells={cells} /> : null}
            {chips.length ? (
              <ul className="reasons" aria-label="Gründe">
                {chips.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            ) : null}
          </InstrumentRow>
        );
      })}
    </ol>
  );
}

export function PotentialView({ route }: { route: Route }) {
  const { instruments, isinIndex, manifest, status } = useApp();
  const signals = useSignals();
  const kind: ListKind = parseListKind(route.params.get('liste'));
  const minAnalysts = Number(route.params.get('min') ?? (kind === 'potenzial' ? 3 : 0)) || 0;
  const onlyGreen = route.params.get('gruen') === '1';
  const liquidOnly = route.params.get('g') === 'b';
  const sectorParam = route.params.get('branche');
  const sector = sectorParam !== null && sectorParam !== '' ? Number(sectorParam) : null;
  const [shown, setShown] = useState(PAGE);
  const data = signals.data;
  const order = useMemo(() => {
    if (!data || !instruments) return [];
    const liquid = (isin: string) => {
      const idx = isinIndex.get(isin);
      return idx !== undefined && Boolean(instruments.turnover?.liquid?.[idx]);
    };
    return rankSignals(data, { kind, minAnalysts, onlyGreen, liquidOnly, sector }, liquid);
  }, [data, instruments, isinIndex, kind, minAnalysts, onlyGreen, liquidOnly, sector]);

  if (!instruments || !manifest) return null;
  const info = LIST_INFO[kind];
  const activeFilters = [minAnalysts > (kind === 'potenzial' ? 3 : 0), onlyGreen, liquidOnly, sector !== null].filter(Boolean).length;

  return (
    <div className="view">
      <header className="view-head">
        <h2 className="view-title">Kandidaten mit Potenzial</h2>
        <ViewIntro>
          <p className="view-intro">
            Alle Aktien der Trade-Republic-Liste, jeden Tag nach festen Regeln bewertet. Oben stehen Aktien, die in 30, 60 und 90 Tagen oft gestiegen sind und deren
            Kursziel deutlich über dem Kurs liegt – zusammengefasst in der <strong>Gesamtwertung</strong> (0 bis 100). Dazu zwei Ampeln: <strong>kurzfristig</strong> (Tage bis
            Wochen) und <strong>langfristig</strong> (etwa 12 Monate). Kursziele sind Meinungen von Analysten. Das Ganze ist eine geordnete Zusammenfassung, keine
            Kaufempfehlung.
            <InfoTip label="So entstehen Gesamtwertung und Ampeln">
              {data ? (
                <>
                  {data.regeln.gesamt_regel ? (
                    <>
                      <strong>Gesamtwertung:</strong> {data.regeln.gesamt_regel}{' '}
                    </>
                  ) : null}
                  <strong>Kurzfristig:</strong> {data.regeln.ampel_kurz} <strong>Langfristig:</strong> {data.regeln.ampel_lang} Jede Zahl ist in der Einzelansicht einer Aktie erklärt.
                </>
              ) : (
                'Die Regeln stehen in der Einzelansicht jeder Aktie.'
              )}
            </InfoTip>
          </p>
        </ViewIntro>
      </header>

      {!status?.signale ? (
        <Notice tone="info" title="Noch keine Signale berechnet">
          <p>
            Kennzahlen und Kursziele lädt der tägliche Lauf nach den Kursen. Sobald der erste Signal-Stand veröffentlicht ist, erscheinen hier die Kandidaten. Starten lässt sich das auch
            unter ☰ → Jetzt aktualisieren („Nur Kennzahlen und Signale“).
          </p>
        </Notice>
      ) : null}
      {signals.error ? <ErrorNote error={signals.error} /> : null}
      {status?.signale && !data && !signals.error ? <Loading height={320} label="Signale werden geladen" /> : null}

      {data ? (
        <>
          <section className="section filters" aria-label="Liste und Filter">
            <Segmented
              label="Liste"
              options={LIST_KINDS.map((value) => ({ value, label: LIST_INFO[value].label }))}
              value={kind}
              onChange={(value) => {
                setShown(PAGE);
                updateParams(route, { liste: value === 'gesamt' ? null : value, min: null });
              }}
            />
            <p className="section-note">{info.text}</p>
            <Disclosure summary={`Filter${activeFilters ? ` (${activeFilters} aktiv)` : ''}`}>
            <div className="filter-row">
                <label className="filter">
                  <span>Analysten mindestens</span>
                  <select value={String(minAnalysts)} onChange={(e: Event) => updateParams(route, { min: (e.target as HTMLSelectElement).value })}>
                    {[0, 1, 3, 5, 10].map((n) => (
                      <option key={n} value={n}>
                        {n === 0 ? 'egal' : n}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="filter">
                  <span>Branche</span>
                  <select value={sector === null ? '' : String(sector)} onChange={(e: Event) => updateParams(route, { branche: (e.target as HTMLSelectElement).value || null })}>
                    <option value="">alle</option>
                    {data.sektoren.map((name, k) => (
                      <option key={name} value={k}>
                        {sectorName(name)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="filter filter-check">
                  <input type="checkbox" checked={onlyGreen} onChange={() => updateParams(route, { gruen: onlyGreen ? null : '1' })} />
                  <span>{kind === 'gesamt' && hasTotal(data) ? `nur stark (ab ${data.regeln.gesamt_stark_ab ?? 65} Punkten)` : 'nur grün'}</span>
                </label>
                <label className="filter filter-check">
                  <input type="checkbox" checked={liquidOnly} onChange={() => updateParams(route, { g: liquidOnly ? null : 'b' })} />
                  <span>nur Gruppe B (Ø Umsatz ≥ {thresholdLabel(manifest)})</span>
                </label>
              </div>
            </Disclosure>
          </section>

          <section className="section" aria-labelledby="kandidaten">
            <h2 className="section-title" id="kandidaten">
              {info.title}
            </h2>
            <p className="section-note">
              {f.plural(order.length, 'Aktie', 'Aktien')} · Signale vom {f.berlinTime(data.erstellt_utc)}, Kurse bis {f.isoDate(data.kursstand)}. Antippen öffnet Urteil, Gründe und Prognose.
            </p>
            {order.length ? (
              <SignalRows data={data} order={order} kind={kind} limit={shown} />
            ) : (
              <p className="empty-body">Keine Aktie erfüllt diese Filter. Weniger Analysten verlangen oder „nur grün“ ausschalten.</p>
            )}
            {order.length > shown ? (
              <div className="toolbar">
                <button type="button" className="btn" onClick={() => setShown(shown + PAGE)}>
                  Weitere {Math.min(PAGE, order.length - shown)} anzeigen
                </button>
              </div>
            ) : null}
          </section>

          <section className="section" aria-labelledby="zahlen">
            <h2 className="section-title" id="zahlen">
              Überblick
            </h2>
            <p className="section-note">
              {f.integer(data.anzahl.aktien)} Aktien bewertet, {f.integer(data.anzahl.mit_kursziel)} mit Kursziel.
              {data.anzahl.gesamt ? ` Gesamtwertung stark: ${f.integer(data.anzahl.gesamt.stark)}, mittel: ${f.integer(data.anzahl.gesamt.mittel)}.` : ''} Kurzfristig grün:{' '}
              {f.integer(data.anzahl.kurz.gruen)}, langfristig grün: {f.integer(data.anzahl.lang.gruen)}, beides grün: {f.integer(data.anzahl.beide_gruen)}. {data.regeln.hinweis}
            </p>
          </section>
        </>
      ) : null}
    </div>
  );
}
