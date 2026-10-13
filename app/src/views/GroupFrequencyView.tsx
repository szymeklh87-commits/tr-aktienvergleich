/* Häufigkeitsranking nach Auftrag vom 13.10.2026 (ab 1.5): Welche Aktie erscheint am häufigsten?
 *
 * Je Aktiengruppe (A, B oder beide zusammen mit getrennten Treffern), über die gewählten
 * Gewichtungen (alle elf, nur mit Gleichmäßigkeitsanteil oder eine) und Zeiträume (alle 1–90 oder
 * eine zusammenhängende Spanne). Standard: „gewinnt am häufigsten“ (Platz 1, Top 3, Top 10, ISIN);
 * Umschalter „Meiste Top-10-Nennungen“ (Top 10, Top 3, Platz 1, ISIN). Wahlweise zählen identische
 * Kursfenster (gleiche Gruppe, Gewichtung und ISIN-/Startdatumsbestand) nur einmal.
 */

import { useMemo, useState } from 'react';
import { IconDownload, IconGrid } from '../components/icons';
import { ErrorNote, Loading, Notice, Pager, Segmented, SectionTitle } from '../components/ui';
import { downloadText, safeFilename, toCsv, type CsvValue } from '../lib/csv';
import { PREVIEW } from '../lib/env';
import * as f from '../lib/format';
import { canDedupe, GROUP_LABEL, groupFrequency, hasGroups, markers, total, type FrequencyOrder, type GroupFrequencyEntry, type GroupFrequencyResult, type GroupSelection, type Marker } from '../lib/groups';
import { useFrequency, useOverview } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { buildHash, navigate, updateParams, type Route } from '../lib/router';
import { parseWeight, WEIGHTS } from '../lib/scoring';
import { thresholdLabel } from '../lib/turnover';
import type { FrequencyData, Instruments, Manifest, Overview } from '../lib/types';
import { useApp } from '../state/AppState';
import { MarkBadge } from '../components/marks';

const PAGE = 30;
const SPANS: [number, number][] = [
  [1, 90],
  [1, 30],
  [31, 60],
  [61, 90],
];

export type WeightPreset = 'alle' | 'trend' | number;

export function parseWeightPreset(route: Route): WeightPreset {
  const text = route.params.get('gw') ?? route.params.get('fw');
  if (text === null || text === 'alle') return 'alle';
  if (text === 'trend') return 'trend';
  return parseWeight(text, 0);
}

export function presetWeights(preset: WeightPreset): number[] {
  if (preset === 'alle') return [...WEIGHTS];
  if (preset === 'trend') return WEIGHTS.filter((w) => w !== 0);
  return [preset];
}

function presetText(preset: WeightPreset): string {
  if (preset === 'alle') return 'alle elf Gewichtungen';
  if (preset === 'trend') return 'nur Gewichtungen mit Gleichmäßigkeitsanteil (10/90 bis 100/0)';
  return `nur ${f.weightShort(preset)} (${f.weightLabel(preset)})`;
}

function parseDay(text: string | null, fallback: number): number {
  const n = Number(text);
  return Number.isInteger(n) && n >= 1 && n <= 90 ? n : fallback;
}

function groupsText(groups: GroupSelection, manifest: Manifest): string {
  if (groups === 'a') return 'Gruppe A (alle vergleichbaren Aktien)';
  if (groups === 'b') return `Gruppe B (Ø Tagesumsatz ≥ ${thresholdLabel(manifest)})`;
  return `Gruppe A und B zusammen (B ist eine Teilmenge von A; Treffer getrennt ausgewiesen)`;
}

/** Hauptansicht „Häufigste Aktien“ (#/haeufig). */
export function GroupFrequencyView({ route }: { route: Route }) {
  const { manifest, instruments, prefs } = useApp();
  const frequency = useFrequency();
  const overview = useOverview();
  if (!manifest || !instruments) return null;
  let from = parseDay(route.params.get('von'), 1);
  let to = parseDay(route.params.get('bis'), 90);
  if (from > to) [from, to] = [to, from];
  const groupsParam = route.params.get('gruppen');
  const fallback: GroupSelection = prefs.group === 'b' ? 'b' : 'a';
  const groups: GroupSelection = groupsParam === 'a' || groupsParam === 'b' || groupsParam === 'ab' ? groupsParam : fallback;

  return (
    <div className="view">
      <header className="view-head">
        <p className="lede">Welche Aktie erscheint in diesem Datenstand am häufigsten vorne? Gezählt wird je Rangliste höchstens einmal je Aktie und Kennzahl.</p>
        <p className="section-note">
          Kursstand {f.dayLong(manifest.cutoff_day)}, berechnet {f.berlinTime(manifest.computed_at_utc)}. Häufige Nennung bedeutet Übereinstimmung rückblickender Vergleiche – keine unabhängigen
          Kaufsignale und keine Gewinnwahrscheinlichkeit.
        </p>
      </header>
      {frequency.error ? <ErrorNote error={frequency.error} /> : null}
      {overview.error ? <ErrorNote error={overview.error} /> : null}
      {!frequency.data && !frequency.error ? <Loading height={520} label="Häufigkeiten werden gezählt" /> : null}
      {frequency.data && overview.data ? (
        <GroupFrequencyTable route={route} manifest={manifest} frequencyData={frequency.data} overview={overview.data} instruments={instruments} groups={groups} from={from} to={to} rangeControl />
      ) : null}
      <p className="section-note">
        Die frühere, ausführlichere Zählung mit Top-K-Auswahl, Vergleichsfeld und „verschiedene Zeiträume“: <a href="#/haeufig/erweitert">Erweiterte Zählung</a>.
      </p>
    </div>
  );
}

/** Tabelle mit Filtern – auch in der Matrix A/B verwendet (dort mit festem Zeitraumbereich). */
export function GroupFrequencyTable({
  route,
  manifest,
  frequencyData,
  overview,
  instruments,
  groups,
  from,
  to,
  rangeControl = false,
  onGroups,
}: {
  route: Route;
  manifest: Manifest;
  frequencyData: FrequencyData;
  overview: Overview;
  instruments: Instruments;
  groups: GroupSelection;
  from: number;
  to: number;
  rangeControl?: boolean;
  onGroups?: (groups: GroupSelection) => void;
}) {
  const { prefs, setPrefs } = useApp();
  const set = (changes: Record<string, string | number | null>) => updateParams(route, { seite: null, ...changes });
  const preset = parseWeightPreset(route);
  const weights = presetWeights(preset);
  const dedupeAvailable = canDedupe(frequencyData, instruments);
  const dedupe = route.params.get('einmal') === '1' && dedupeAvailable;
  const sortParam = route.params.get('sort');
  const order: FrequencyOrder = sortParam === 'n10' || sortParam === 'n1' ? sortParam : prefs.frequencyOrder;
  const page = Math.max(1, Number(route.params.get('seite') ?? 1) || 1);
  const selected = route.params.get('isin');
  const selectedIdx = selected ? instruments.isin.indexOf(selected) : -1;
  const withB = hasGroups(overview) && Boolean(frequencyData.occ.ul);
  const effectiveGroups: GroupSelection = withB ? groups : 'a';
  const [fromDraft, setFromDraft] = useState(String(from));
  const [toDraft, setToDraft] = useState(String(to));
  const [freeMode, setFreeMode] = useState(false);

  const result = useMemo(
    () => groupFrequency(frequencyData, instruments, { groups: effectiveGroups, weights, from, to, dedupe, order }),
    [frequencyData, instruments, effectiveGroups, weights.join(','), from, to, dedupe, order],
  );
  const markerMap = useMemo(() => markers(overview, instruments, from, to, weights), [overview, instruments, from, to, weights.join(',')]);
  const pages = Math.max(1, Math.ceil(result.entries.length / PAGE));
  const current = Math.min(page, pages);
  const visible = result.entries.slice((current - 1) * PAGE, current * PAGE);
  const both = effectiveGroups === 'ab';
  const presetSpan = SPANS.some(([a, b]) => a === from && b === to);
  const spanKey = freeMode || !presetSpan ? 'frei' : `${from}-${to}`;
  const setGroups = (value: GroupSelection) => (onGroups ? onGroups(value) : set({ gruppen: value }));

  const cell = (entry: GroupFrequencyEntry, key: 'n1' | 'n3' | 'n10' | 'available') =>
    both ? (
      <>
        <span className="gnum">{f.integer(entry.a[key] + entry.b[key])}</span>
        <small className="gsplit">A {f.integer(entry.a[key])}</small>
        <small className="gsplit">B {f.integer(entry.b[key])}</small>
      </>
    ) : (
      <span className="gnum">{f.integer(total(entry, key, effectiveGroups))}</span>
    );

  return (
    <section className="section gfreq-section" aria-labelledby="haeufigkeit">
      <SectionTitle id="haeufigkeit">Häufigkeitsranking</SectionTitle>
      <div className="matrix-controls">
        <Segmented
          label="Aktiengruppe"
          options={[
            { value: 'a', label: 'A: alle' },
            { value: 'b', label: 'B: Umsatz' },
            { value: 'ab', label: 'A und B' },
          ]}
          value={effectiveGroups}
          onChange={(value) => setGroups(value as GroupSelection)}
        />
        <Segmented
          label="Sortierung"
          options={[
            { value: 'n1', label: 'Gewinnt am häufigsten' },
            { value: 'n10', label: 'Meiste Top-10-Nennungen' },
          ]}
          value={order}
          onChange={(value) => {
            setPrefs({ frequencyOrder: value as FrequencyOrder });
            set({ sort: value });
          }}
        />
        <label className="field">
          <span className="field-label">Gewichtungen</span>
          <select
            className="select"
            value={preset === 'alle' || preset === 'trend' ? preset : String(preset)}
            onChange={(e: Event) => {
              const value = (e.target as HTMLSelectElement).value;
              set({ gw: value === 'alle' ? null : value, fw: null });
            }}
          >
            <option value="alle">Alle elf Gewichtungen</option>
            <option value="trend">Nur mit Gleichmäßigkeitsanteil (10/90–100/0)</option>
            {WEIGHTS.map((w) => (
              <option key={w} value={String(w)}>
                Nur {f.weightShort(w)} – {f.weightLabel(w)}
              </option>
            ))}
          </select>
        </label>
        {rangeControl ? (
          <div className="segmented-wrap">
            <Segmented
              label="Zeiträume"
              options={[...SPANS.map(([a, b]) => ({ value: `${a}-${b}`, label: a === 1 && b === 90 ? 'Alle 1–90' : `${a}–${b}` })), { value: 'frei', label: 'Frei' }]}
              value={spanKey}
              onChange={(value) => {
                if (value === 'frei') {
                  // Spanne bleibt zunächst wie gewählt; die Felder darunter übernehmen eine eigene
                  setFreeMode(true);
                  setFromDraft(String(from));
                  setToDraft(String(to));
                  return;
                }
                const [a, b] = value.split('-').map(Number);
                setFreeMode(false);
                setFromDraft(String(a));
                setToDraft(String(b));
                set({ von: a === 1 ? null : a, bis: b === 90 ? null : b });
              }}
            />
            {spanKey === 'frei' ? (
              <form
                className="range-pair"
                onSubmit={(e: Event) => {
                  e.preventDefault();
                  let a = parseDay(fromDraft, 1);
                  let b = parseDay(toDraft, 90);
                  if (a > b) [a, b] = [b, a];
                  set({ von: a, bis: b });
                }}
              >
                <label className="field">
                  <span className="field-label">von (Tage)</span>
                  <input className="input" type="number" inputMode="numeric" min={1} max={90} value={fromDraft} onChange={(e: Event) => setFromDraft((e.target as HTMLInputElement).value)} />
                </label>
                <label className="field">
                  <span className="field-label">bis (Tage)</span>
                  <input className="input" type="number" inputMode="numeric" min={1} max={90} value={toDraft} onChange={(e: Event) => setToDraft((e.target as HTMLInputElement).value)} />
                </label>
                <button type="submit" className="btn btn-primary">
                  Spanne übernehmen
                </button>
              </form>
            ) : null}
          </div>
        ) : null}
        <label className="gcheck">
          <input type="checkbox" checked={dedupe} disabled={!dedupeAvailable} onChange={(e: Event) => set({ einmal: (e.target as HTMLInputElement).checked ? '1' : null })} />
          <span>Identische Kursfenster nur einmal zählen</span>
        </label>
      </div>

      {!withB && groups !== 'a' ? (
        <Notice tone="info" title="Gruppe B in diesem Datenstand noch nicht berechnet">
          <p>Gezählt wird deshalb nur Gruppe A.</p>
        </Notice>
      ) : null}

      <ScopeNote result={result} manifest={manifest} preset={preset} order={order} exact={Boolean(frequencyData.same_set)} />

      {result.entries.length === 0 ? (
        <p className="empty-body">In dieser Auswahl hat keine Aktie einen Platz unter den ersten 10.</p>
      ) : (
        <div className="table-wrap">
          <table className={`table gfreq${both ? ' gfreq-both' : ''}`}>
            <caption className="visually-hidden">Häufigkeitsranking, {groupsText(effectiveGroups, manifest)}</caption>
            <thead>
              <tr>
                <th scope="col" className="n">
                  Rang
                </th>
                <th scope="col" className="sticky">
                  Unternehmen, ISIN
                </th>
                <th scope="col" className="n">
                  Platz 1
                </th>
                <th scope="col" className="n">
                  Top 3
                </th>
                <th scope="col" className="n">
                  Top 10
                </th>
                <th scope="col" className="n">
                  Zuge&shy;lassen
                  <small>Kombi&shy;nationen</small>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((entry, k) => {
                const rank = (current - 1) * PAGE + k + 1;
                const isin = instruments.isin[entry.idx];
                const n1 = total(entry, 'n1', effectiveGroups);
                const marker: Marker | undefined = markerMap.get(entry.idx);
                return (
                  <tr key={entry.idx} className={entry.idx === selectedIdx ? 'is-selected' : ''}>
                    <td className="n">{rank}</td>
                    <th scope="row" className="sticky">
                      <button type="button" className="table-pick" aria-pressed={entry.idx === selectedIdx} onClick={() => set({ isin: entry.idx === selectedIdx ? null : isin })}>
                        <span>{instName(instruments, entry.idx)}</span>
                      </button>
                      {n1 >= 2 ? <FirstPlaces count={n1} slot={marker?.slot ?? null} /> : null}
                      <span className="gcell-isin" translate="no">
                        {isin}
                      </span>
                      {entry.idx === selectedIdx ? (
                        <span className="gfreq-links">
                          <a href={buildHash(`/aktie/${isin}`, { h: to })}>Kursverlauf</a>
                          <a href={buildHash('/matrix', { isin, g: effectiveGroups === 'b' ? 'b' : null })}>In der Matrix markieren</a>
                        </span>
                      ) : null}
                    </th>
                    <td className="n">{cell(entry, 'n1')}</td>
                    <td className="n">{cell(entry, 'n3')}</td>
                    <td className="n">{cell(entry, 'n10')}</td>
                    <td className="n">{cell(entry, 'available')}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={current} pages={pages} onChange={(p) => updateParams(route, { seite: p })} label="Seiten des Häufigkeitsrankings" />
      <div className="toolbar no-print">
        <button
          type="button"
          className="btn"
          disabled={!result.entries.length}
          onClick={() => navigate('/raster', { quelle: 'isins', isins: result.entries.slice(0, 10).map((e) => instruments.isin[e.idx]).join(','), titel: 'Top 10 des Häufigkeitsrankings' })}
        >
          <IconGrid /> Erste 10 im Chart-Raster
        </button>
        {!PREVIEW ? (
          <>
            <button type="button" className="btn btn-quiet" onClick={() => exportFrequency(result, instruments, manifest, frequencyData, preset, 'csv')}>
              <IconDownload /> CSV
            </button>
            <button type="button" className="btn btn-quiet" onClick={() => exportFrequency(result, instruments, manifest, frequencyData, preset, 'json')}>
              <IconDownload /> JSON
            </button>
          </>
        ) : null}
      </div>
    </section>
  );
}

/** „↻ 14 erste Plätze“ – Zahl der Platz-1-Vorkommen in dieser Auswahl; Farbe wie in allen Ansichten. */
function FirstPlaces({ count, slot }: { count: number; slot: number | null }) {
  return <MarkBadge marker={{ idx: -1, slot, count, countA: count, countB: 0 }} split={false} context="in dieser Auswahl" />;
}

function ScopeNote({ result, manifest, preset, order, exact }: { result: GroupFrequencyResult; manifest: Manifest; preset: WeightPreset; order: FrequencyOrder; exact: boolean }) {
  const o = result.options;
  const groups = o.groups;
  const span = o.from === 1 && o.to === 90 ? 'alle Zeiträume 1–90 Tage' : `Zeiträume ${o.from}–${o.to} Tage`;
  const requested = result.theoretical;
  return (
    <p className="section-note scope-note">
      <strong>Auswahl:</strong> {groupsText(groups, manifest)}, {presetText(preset)}, {span}. <strong>Sortierung:</strong>{' '}
      {order === 'n1' ? 'gewinnt am häufigsten – Platz 1, dann Top 3, Top 10, ISIN' : 'erscheint am häufigsten in den Top 10 – Top 10, dann Top 3, Platz 1, ISIN'}. Platz 1 zählt zugleich zu Top 3 und
      Top 10; die Spalten werden nicht addiert. <strong>Berechenbare Kombinationen (Nenner):</strong> {groups !== 'b' ? `A ${f.integer(result.validA)}` : ''}
      {groups === 'ab' ? ', ' : ''}
      {groups !== 'a' ? `B ${f.integer(result.validB)}` : ''} von je {f.integer(requested)} angeforderten
      {o.dedupe
        ? ` – identische Kursfenster einmal gezählt (${exact ? 'gleicher Bestand aus ISIN und tatsächlichem Startdatum' : 'Näherung über gleiche Startsitzung, Datenstand vor 1.5'}; ${f.integer(result.mergedA + result.mergedB)} Top-10-Fundstellen zusammengefasst)`
        : ''}
      . Nicht berechenbare Kombinationen (z. B. Gleichmäßigkeit bei weniger als 15 Schlusskursen) zählen nicht. „Zugelassen“ = Ranglisten der Auswahl, in denen die Aktie überhaupt einen Rang hat. Überlappende
      Zeiträume und ähnliche Gewichtungen bleiben voneinander abhängig.
    </p>
  );
}

function exportFrequency(result: GroupFrequencyResult, instruments: Instruments, manifest: Manifest, data: FrequencyData, preset: WeightPreset, format: 'csv' | 'json') {
  const o = result.options;
  const meta: [string, string][] = [
    ['Ansicht', 'Häufigkeitsranking'],
    ['Gruppen', groupsText(o.groups, manifest)],
    ['Gewichtungen', presetText(preset)],
    ['Zeiträume', `${o.from}–${o.to} Kalendertage`],
    ['Zählweise', o.dedupe ? 'identische Kursfenster einmal' : 'alle Kalenderfenster'],
    ['Sortierung', o.order === 'n10' ? 'Top 10, Top 3, Platz 1, ISIN' : 'Platz 1, Top 3, Top 10, ISIN'],
    ['Berechenbare Kombinationen A / B', `${result.validA} / ${result.validB} (angefordert je Gruppe ${result.theoretical})`],
    ['Aggregationsversion', data.aggregation_version],
    ['Snapshot', manifest.snapshot_id],
    ['Kursstichtag', manifest.cutoff_session_date],
    ['Datenmodus', manifest.data_mode === 'demo' ? 'DEMO – synthetische Testdaten' : manifest.data_mode],
    ['Hinweis', 'Nennungen sind keine Gewinnwahrscheinlichkeiten und keine unabhängigen Bestätigungen.'],
  ];
  const name = `haeufigkeit_${o.groups}_${preset}_${o.from}-${o.to}${o.dedupe ? '_einmal' : ''}_${manifest.snapshot_id}`;
  if (format === 'json') {
    const payload = {
      format: 'tr-haeufigkeit/1',
      meta: Object.fromEntries(meta),
      eintraege: result.entries.map((e, k) => ({
        rang: k + 1,
        name: instName(instruments, e.idx),
        isin: instruments.isin[e.idx],
        gruppe_a: { platz1: e.a.n1, top3: e.a.n3, top10: e.a.n10, zugelassen: e.a.available },
        gruppe_b: { platz1: e.b.n1, top3: e.b.n3, top10: e.b.n10, zugelassen: e.b.available },
      })),
    };
    downloadText(safeFilename(`${name}.json`), JSON.stringify(payload, null, 2), 'application/json;charset=utf-8');
    return;
  }
  const rows: CsvValue[][] = result.entries.map((e, k) => [
    k + 1,
    instName(instruments, e.idx),
    instruments.isin[e.idx],
    total(e, 'n1', o.groups),
    total(e, 'n3', o.groups),
    total(e, 'n10', o.groups),
    total(e, 'available', o.groups),
    e.a.n1,
    e.b.n1,
    e.a.n10,
    e.b.n10,
  ]);
  const csv = toCsv(meta, ['Rang', 'Unternehmen', 'ISIN', 'Platz 1', 'Top 3', 'Top 10', 'Zugelassene Kombinationen', 'Platz 1 in A', 'Platz 1 in B', 'Top 10 in A', 'Top 10 in B'], rows);
  downloadText(safeFilename(`${name}.csv`), csv);
}

export { GROUP_LABEL };
