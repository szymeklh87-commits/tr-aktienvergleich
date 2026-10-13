/* Gruppenvergleich A/B über 1–30 Tage: Matrix, kompakte Liste und Häufigkeitsranking (ab 1.4).
 *
 * Zeilen = Zeiträume, Spalten = elf Gewichtungen, Zelle = erstplatzierte Aktie. Wiederkehrende
 * Aktien tragen in allen drei Ansichten und in beiden Gruppen dieselbe Kennzeichnung (Farbe und
 * „×Anzahl“). Antippen markiert alle Vorkommen und bietet Rangliste und Kursverlauf an.
 */

import { useEffect, useMemo, useRef } from 'react';
import { useDark } from '../components/charts';
import { ErrorNote, IsinCopy, Loading, Notice, Pager, Pct, Segmented, SectionTitle } from '../components/ui';
import { EMPTY_PHRASE, EMPTY_SHORT } from '../lib/codes';
import { seriesColor } from '../lib/colors';
import * as f from '../lib/format';
import {
  canDedupe,
  GROUP_LABEL,
  GROUP_TEXT,
  groupFrequency,
  hasGroups,
  markers,
  matrixCoverage,
  matrixRows,
  overviewRow,
  sameText,
  total,
  type GroupFrequencyEntry,
  type GroupSelection,
  type Marker,
  type MatrixCell,
} from '../lib/groups';
import { useFrequency, useOverview } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { buildHash, updateParams, type Route } from '../lib/router';
import { parseGroup, parseWeight, WEIGHTS } from '../lib/scoring';
import type { FrequencyData, Group, Instruments, Overview } from '../lib/types';
import { useApp } from '../state/AppState';

type Mode = 'matrix' | 'liste' | 'haeufigkeit';
const RANGES: [number, number][] = [
  [1, 30],
  [31, 60],
  [61, 90],
];
const PAGE = 30;

function parseRange(route: Route): [number, number] {
  const from = Number(route.params.get('von'));
  const found = RANGES.find(([a]) => a === from);
  return found ?? RANGES[0];
}

function parseMode(text: string | null): Mode {
  return text === 'liste' || text === 'haeufigkeit' ? text : 'matrix';
}

function weightHead(w: number): [string, string] {
  if (w === 0) return ['0/100', 'nur Rendite'];
  if (w === 100) return ['100/0', 'nur Gleichmäßigkeit'];
  return [`${w}/${100 - w}`, `${w} % gleichmäßig`];
}

export function MarkBadge({ marker }: { marker: Marker | undefined }) {
  const dark = useDark();
  if (!marker || marker.count < 2) return null;
  const color = marker.slot !== null ? seriesColor(marker.slot, dark) : undefined;
  return (
    <span className={`mark${marker.slot === null ? ' mark-neutral' : ''}`} title={`${marker.count}-mal Platz 1 in der Matrix (Gruppe A: ${marker.countA}, Gruppe B: ${marker.countB})`}>
      <i style={color ? { background: color } : undefined} aria-hidden="true" />
      <span className="visually-hidden">wiederkehrend, </span>×{marker.count}
    </span>
  );
}

export function MatrixView({ route }: { route: Route }) {
  const { manifest, instruments } = useApp();
  const overview = useOverview();
  const mode = parseMode(route.params.get('ansicht'));
  const frequency = useFrequency(mode === 'haeufigkeit');
  const group = parseGroup(route.params.get('g'));
  const [from, to] = parseRange(route);
  const selected = route.params.get('isin');
  const data = overview.data;

  const markerMap = useMemo(() => (data && instruments ? markers(data, instruments, from, to) : new Map<number, Marker>()), [data, instruments, from, to]);
  const rows = useMemo(() => (data ? matrixRows(data, group, from, to) : []), [data, group, from, to]);

  if (!manifest || !instruments) return null;
  const set = (changes: Record<string, string | number | null>) => updateParams(route, changes);
  const selectedIdx = selected ? instruments.isin.indexOf(selected) : -1;
  const toggle = (idx: number) => set({ isin: instruments.isin[idx] === selected ? null : instruments.isin[idx] });
  const groupsReady = hasGroups(data);

  return (
    <div className="view matrix-view">
      <header className="view-head">
        <p className="lede">
          Je Zeitraum und Gewichtung die erstplatzierte Aktie – getrennt für Gruppe A (alle vergleichbaren Aktien) und Gruppe B (nur Ø Tagesumsatz ab 10 Mio. USD). Wiederkehrende Aktien sind gleich
          gekennzeichnet; Antippen markiert alle Vorkommen.
        </p>
        <p className="section-note">
          Kursstand {f.dayLong(manifest.cutoff_day)}, berechnet {f.berlinTime(manifest.computed_at_utc)}. Historische Tagesschlusskurse, keine Livekurse.
        </p>
      </header>

      <Segmented
        label="Aktiengruppe"
        options={[
          { value: 'a', label: 'A: alle Aktien' },
          { value: 'b', label: 'B: Ø Umsatz ≥ 10 Mio. USD' },
        ]}
        value={group}
        onChange={(g) => set({ g: g === 'a' ? null : g })}
      />
      <div className="matrix-controls">
        <Segmented
          label="Ansicht"
          options={[
            { value: 'matrix', label: 'Matrix' },
            { value: 'liste', label: 'Liste' },
            { value: 'haeufigkeit', label: 'Häufigkeit' },
          ]}
          value={mode}
          onChange={(m) => set({ ansicht: m === 'matrix' ? null : m, seite: null })}
        />
        <Segmented
          label="Zeiträume"
          options={RANGES.map(([a, b]) => ({ value: `${a}`, label: `${a}–${b} Tage` }))}
          value={`${from}`}
          onChange={(v) => set({ von: v === '1' ? null : v, seite: null })}
        />
      </div>

      {overview.error ? <ErrorNote error={overview.error} /> : null}
      {!data && !overview.error ? <Loading height={480} label="Matrix wird geladen" /> : null}
      {data && group === 'b' && !groupsReady ? (
        <Notice tone="info" title="Gruppe B in diesem Datenstand noch nicht berechnet">
          <p>Die Ranglisten der Gruppe B mit allen elf Gewichtungen gibt es ab Version 1.4. Der nächste tägliche Lauf rechnet sie mit.</p>
        </Notice>
      ) : null}

      {data && (group === 'a' || groupsReady) ? (
        <>
          <CoverageLine overview={data} group={group} from={from} to={to} />
          {selectedIdx >= 0 ? (
            <Selection idx={selectedIdx} instruments={instruments} marker={markerMap.get(selectedIdx)} group={group} overview={data} from={from} to={to} onClear={() => set({ isin: null })} />
          ) : null}
          {mode === 'matrix' ? (
            <>
              <p className="section-note">Gewichtungen seitlich wischen, die Zeiträume bleiben links stehen. ≡ = gleiches Kursfenster wie in den genannten Zeiträumen (Wochenende oder Feiertag).</p>
              <Matrix rows={rows} instruments={instruments} markers={markerMap} selectedIdx={selectedIdx} onPick={toggle} />
            </>
          ) : null}
          {mode === 'liste' ? (
            <CompactList
              rows={rows}
              instruments={instruments}
              markers={markerMap}
              selectedIdx={selectedIdx}
              weight={parseWeight(route.params.get('w'), 0)}
              onWeight={(w) => set({ w })}
              onPick={toggle}
            />
          ) : null}
          {mode === 'haeufigkeit' ? (
            frequency.error ? (
              <ErrorNote error={frequency.error} />
            ) : frequency.data ? (
              <FrequencyTable route={route} frequencyData={frequency.data} instruments={instruments} markers={markerMap} selectedIdx={selectedIdx} onPick={toggle} from={from} to={to} group={group} />
            ) : (
              <Loading height={480} label="Fundstellen werden geladen" />
            )
          ) : null}
          <p className="section-note">
            Häufige Nennung bedeutet Übereinstimmung dieser rückblickenden Vergleiche – keine unabhängigen Kaufsignale und keine Gewinnwahrscheinlichkeit. Gleiche Namen oder Ticker werden nie
            zusammengefasst; maßgeblich ist die ISIN.
          </p>
        </>
      ) : null}
    </div>
  );
}

function CoverageLine({ overview, group, from, to }: { overview: Overview; group: Group; from: number; to: number }) {
  const rows = matrixRows(overview, group, from, to);
  const coverage = matrixCoverage(rows);
  const empty = Object.entries(coverage.empty).sort((a, b) => b[1] - a[1]);
  const field = group === 'a' ? overview.counts.V : overview.counts.L ?? [];
  const trend = group === 'a' ? overview.counts.U : overview.counts.UL ?? [];
  return (
    <p className="section-note coverage-line">
      {GROUP_LABEL[group]} ({GROUP_TEXT[group]}): {f.integer(coverage.computed)} von {f.integer(coverage.theoretical)} Ranglisten berechnet.
      {empty.length ? ` Nicht berechenbar: ${empty.map(([key, n]) => `${f.integer(n)} (${EMPTY_PHRASE[key] ?? key})`).join(', ')}.` : ''} Vergleichbar bei {to} Tagen: {f.integer(field[to - 1] ?? 0)} Aktien mit
      Kursrendite, davon {f.integer(trend[to - 1] ?? 0)} gleichmäßig gestiegen.
    </p>
  );
}

function Selection({ idx, instruments, marker, group, overview, from, to, onClear }: { idx: number; instruments: Instruments; marker: Marker | undefined; group: Group; overview: Overview; from: number; to: number; onClear: () => void }) {
  // erste Zelle der Aktie in dieser Gruppe als Einstieg in Rangliste und Kursverlauf
  let first: { h: number; w: number } | null = null;
  for (let h = from; h <= to && !first; h += 1) {
    for (const w of WEIGHTS) {
      if (overviewRow(overview, group, w, h)?.idx === idx) {
        first = { h, w };
        break;
      }
    }
  }
  const isin = instruments.isin[idx];
  return (
    <section className="matrix-selection" aria-label="Markierte Aktie">
      <div className="matrix-selection-head">
        <MarkBadge marker={marker} />
        <strong>{instName(instruments, idx)}</strong>
      </div>
      <IsinCopy isin={isin} compact />
      <p className="section-note">
        {marker ? `${f.plural(marker.count, 'Mal', 'Mal')} Platz 1 in ${from}–${to} Tagen (Gruppe A: ${marker.countA}, Gruppe B: ${marker.countB}).` : 'In diesen Zeiträumen nie auf Platz 1.'} Alle Vorkommen sind
        markiert.
      </p>
      <div className="toolbar">
        {first ? (
          <a className="btn btn-primary" href={buildHash('/ranking', { h: first.h, w: first.w, p: 'native', g: group === 'b' ? 'b' : null })}>
            Rangliste {f.windowLabel(first.h)}, {weightHead(first.w)[0]}
          </a>
        ) : null}
        <a className="btn" href={buildHash(`/aktie/${isin}`, { h: first?.h ?? from, w: first?.w ?? 0, p: 'native' })}>
          Kursverlauf
        </a>
        <button type="button" className="btn btn-quiet" onClick={onClear}>
          Markierung aufheben
        </button>
      </div>
    </section>
  );
}

function CellBody({ cell, instruments, marker }: { cell: MatrixCell; instruments: Instruments; marker: Marker | undefined }) {
  const row = cell.row;
  if (row.idx === undefined) return <span className="gcell-empty">{EMPTY_SHORT[row.empty ?? ''] ?? 'nicht berechenbar'}</span>;
  return (
    <>
      <span className="gcell-top">
        <MarkBadge marker={marker} />
        {row.tie ? <span className="badge">gleichauf</span> : null}
        {row.sole ? <span className="badge">einziger Titel</span> : null}
        {cell.same.length ? (
          <span className="same-mark" title={sameText(cell)}>
            ≡ {cell.same.join(', ')}
          </span>
        ) : null}
      </span>
      <span className="gcell-name">{instName(instruments, row.idx)}</span>
      <span className="gcell-isin" translate="no">
        {instruments.isin[row.idx]}
      </span>
      <span className="gcell-figs">
        <Pct value={row.r ?? null} digits={1} strong />
        <span className="muted">Score {f.score(row.score ?? null)}</span>
      </span>
    </>
  );
}

function Matrix({ rows, instruments, markers: markerMap, selectedIdx, onPick }: { rows: ReturnType<typeof matrixRows>; instruments: Instruments; markers: Map<number, Marker>; selectedIdx: number; onPick: (idx: number) => void }) {
  const dark = useDark();
  const wrapRef = useRef<HTMLDivElement | null>(null);
  // Markierte Aktie außerhalb des sichtbaren Ausschnitts (z. B. nach Gruppenwechsel): erstes Vorkommen zeigen
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap || selectedIdx < 0) return;
    const cells = [...wrap.querySelectorAll<HTMLElement>('td.gcell.is-selected')];
    if (!cells.length) return;
    const view = wrap.getBoundingClientRect();
    const head = (wrap.querySelector('thead') as HTMLElement | null)?.getBoundingClientRect().height ?? 0;
    const side = (wrap.querySelector('th.gday') as HTMLElement | null)?.getBoundingClientRect().width ?? 0;
    const visible = (el: HTMLElement) => {
      const b = el.getBoundingClientRect();
      return b.bottom > view.top + head && b.top < view.bottom && b.right > view.left + side && b.left < view.right;
    };
    if (cells.some(visible)) return; // eine markierte Zelle ist schon zu sehen (z. B. gerade angetippt)
    const box = cells[0].getBoundingClientRect();
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    wrap.scrollTo({ top: wrap.scrollTop + box.top - view.top - head - 8, left: wrap.scrollLeft + box.left - view.left - side - 8, behavior: reduced ? 'auto' : 'smooth' });
  }, [selectedIdx, rows]);
  return (
    <div className="gmatrix-wrap" role="region" aria-label="Matrix: Zeiträume und Gewichtungen, horizontal verschiebbar" tabIndex={0} ref={wrapRef}>
      <table className={`gmatrix${selectedIdx >= 0 ? ' has-selection' : ''}`}>
        <thead>
          <tr>
            <th scope="col" className="gcorner">
              Tage
            </th>
            {WEIGHTS.map((w) => {
              const [main, sub] = weightHead(w);
              return (
                <th scope="col" key={w}>
                  {main}
                  <small>{sub}</small>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.h}>
              <th scope="row" className="gday">
                {row.h}
              </th>
              {row.cells.map((cell) => {
                const idx = cell.row.idx;
                const marker = idx !== undefined ? markerMap.get(idx) : undefined;
                const recurring = marker && marker.count >= 2;
                const color = recurring && marker!.slot !== null ? seriesColor(marker!.slot, dark) : undefined;
                const isSelected = idx !== undefined && idx === selectedIdx;
                return (
                  <td key={cell.weight} className={`gcell${isSelected ? ' is-selected' : ''}${idx === undefined ? ' is-empty' : ''}`} style={color ? { borderLeftColor: color } : undefined}>
                    {idx !== undefined ? (
                      <button
                        type="button"
                        className="gcell-btn"
                        aria-pressed={isSelected}
                        aria-label={`${f.windowLabel(row.h)}, ${f.weightLabel(cell.weight)}: ${instName(instruments, idx)}, ${f.pct(cell.row.r ?? null, 1)}, Score ${f.score(cell.row.score ?? null)}${recurring ? `, ${marker!.count}-mal Platz 1` : ''}`}
                        onClick={() => onPick(idx)}
                      >
                        <CellBody cell={cell} instruments={instruments} marker={marker} />
                      </button>
                    ) : (
                      <CellBody cell={cell} instruments={instruments} marker={marker} />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CompactList({
  rows,
  instruments,
  markers: markerMap,
  selectedIdx,
  weight,
  onWeight,
  onPick,
}: {
  rows: ReturnType<typeof matrixRows>;
  instruments: Instruments;
  markers: Map<number, Marker>;
  selectedIdx: number;
  weight: number;
  onWeight: (w: number) => void;
  onPick: (idx: number) => void;
}) {
  const k = WEIGHTS.indexOf(weight as (typeof WEIGHTS)[number]);
  return (
    <section className="section" aria-labelledby="kompakt">
      <SectionTitle id="kompakt">Spitzenreiter je Zeitraum, {f.weightLabel(weight)}</SectionTitle>
      <div className="chips" role="radiogroup" aria-label="Gewichtung">
        {WEIGHTS.map((w) => (
          <button key={w} type="button" role="radio" aria-checked={w === weight} className={`chip${w === weight ? ' is-active' : ''}`} onClick={() => onWeight(w)}>
            {weightHead(w)[0]}
          </button>
        ))}
      </div>
      <ol className="glist">
        {rows.map((row) => {
          const cell = row.cells[k];
          const idx = cell.row.idx;
          const marker = idx !== undefined ? markerMap.get(idx) : undefined;
          return (
            <li key={row.h} className={`glist-row${idx !== undefined && idx === selectedIdx ? ' is-selected' : ''}`}>
              <span className="glist-day" aria-label={f.windowLabel(row.h)}>
                {row.h === 1 ? '1 Tag' : `${row.h} Tage`}
              </span>
              {idx !== undefined ? (
                <button type="button" className="glist-btn" aria-pressed={idx === selectedIdx} onClick={() => onPick(idx)}>
                  <CellBody cell={cell} instruments={instruments} marker={marker} />
                </button>
              ) : (
                <CellBody cell={cell} instruments={instruments} marker={marker} />
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function FrequencyTable({
  route,
  frequencyData,
  instruments,
  markers: markerMap,
  selectedIdx,
  onPick,
  from,
  to,
  group,
}: {
  route: Route;
  frequencyData: FrequencyData;
  instruments: Instruments;
  markers: Map<number, Marker>;
  selectedIdx: number;
  onPick: (idx: number) => void;
  from: number;
  to: number;
  group: Group;
}) {
  const set = (changes: Record<string, string | number | null>) => updateParams(route, { seite: null, ...changes });
  const groupsParam = route.params.get('gruppen');
  const groups: GroupSelection = groupsParam === 'ab' ? 'ab' : group;
  const weightParam = route.params.get('fw');
  const single = weightParam !== null && weightParam !== 'alle' ? parseWeight(weightParam, 0) : null;
  const dedupeAvailable = canDedupe(frequencyData, instruments);
  const dedupe = route.params.get('einmal') === '1' && dedupeAvailable;
  const page = Math.max(1, Number(route.params.get('seite') ?? 1) || 1);
  const result = useMemo(
    () => groupFrequency(frequencyData, instruments, { groups, weights: single === null ? [...WEIGHTS] : [single], from, to, dedupe }),
    [frequencyData, instruments, groups, single, from, to, dedupe],
  );
  const pages = Math.max(1, Math.ceil(result.entries.length / PAGE));
  const current = Math.min(page, pages);
  const visible = result.entries.slice((current - 1) * PAGE, current * PAGE);
  const both = groups === 'ab';
  const counts = (entry: GroupFrequencyEntry, key: 'n1' | 'n3' | 'n10' | 'available') =>
    both ? (
      <>
        <span className="gnum">{f.integer(entry.a[key])}</span>
        <span className="gnum">{f.integer(entry.b[key])}</span>
      </>
    ) : (
      <span className="gnum">{f.integer(total(entry, key, groups))}</span>
    );

  return (
    <section className="section" aria-labelledby="haeufigkeit">
      <SectionTitle id="haeufigkeit">Häufigkeitsranking {groups === 'ab' ? 'Gruppe A und B' : GROUP_LABEL[groups]}</SectionTitle>
      <div className="matrix-controls">
        <Segmented
          label="Gruppen"
          options={[
            { value: group, label: `Nur ${GROUP_LABEL[group]}` },
            { value: 'ab', label: 'A und B getrennt' },
          ]}
          value={groups === 'ab' ? 'ab' : group}
          onChange={(v) => set({ gruppen: v === 'ab' ? 'ab' : null })}
        />
        <label className="field">
          <span className="field-label">Gewichtungen</span>
          <select className="select" value={single === null ? 'alle' : String(single)} onChange={(e: Event) => set({ fw: (e.target as HTMLSelectElement).value === 'alle' ? null : (e.target as HTMLSelectElement).value })}>
            <option value="alle">Alle elf zusammen</option>
            {WEIGHTS.map((w) => (
              <option key={w} value={String(w)}>
                Nur {f.weightLabel(w)}
              </option>
            ))}
          </select>
        </label>
        <label className="gcheck">
          <input type="checkbox" checked={dedupe} disabled={!dedupeAvailable} onChange={(e: Event) => set({ einmal: (e.target as HTMLInputElement).checked ? '1' : null })} />
          <span>Identische Kursfenster nur einmal zählen</span>
        </label>
      </div>
      <p className="section-note">
        Sortiert nach Platz-1-Vorkommen, dann Top 3, Top 10 und ISIN. Je Rangliste zählt eine Aktie höchstens einmal; Platz 1 zählt zugleich zu Top 3 und Top 10 – die Spalten werden nicht addiert.{' '}
        {dedupe
          ? `Gleiche Gewichtung mit demselben tatsächlichen Start- und Endkurs zählt einmal (${f.integer(result.mergedA + result.mergedB)} Top-10-Fundstellen zusammengefasst).`
          : `Gezählt werden alle ${f.integer(result.theoretical)} angeforderten Kombinationen aus Zeitraum und Gewichtung je Gruppe; berechnet: ${groups !== 'b' ? `A ${f.integer(result.validA)}` : ''}${groups === 'ab' ? ', ' : ''}${groups !== 'a' ? `B ${f.integer(result.validB)}` : ''}.`}
        {!dedupeAvailable ? ' „Nur einmal zählen“ gibt es ab Datenständen der Version 1.4.' : ''}
      </p>
      {result.entries.length === 0 ? (
        <p className="empty-body">In dieser Auswahl hat keine Aktie einen Top-10-Platz.</p>
      ) : (
        <div className="table-wrap">
          <table className={`table gfreq${both ? ' gfreq-both' : ''}`}>
            <thead>
              <tr>
                <th scope="col" className="n">
                  Rang
                </th>
                <th scope="col" className="sticky">
                  Unternehmen, ISIN
                </th>
                {(['Platz 1', 'Top 3', 'Top 10', 'Auswertbar'] as const).map((label) => (
                  <th scope="col" className="n" key={label}>
                    {label}
                    {both ? <small>A | B</small> : null}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((entry, k) => {
                const rank = (current - 1) * PAGE + k + 1;
                return (
                  <tr key={entry.idx} className={entry.idx === selectedIdx ? 'is-selected' : ''}>
                    <td className="n">{rank}</td>
                    <th scope="row" className="sticky">
                      <button type="button" className="table-pick" aria-pressed={entry.idx === selectedIdx} onClick={() => onPick(entry.idx)}>
                        <span>{instName(instruments, entry.idx)}</span>
                      </button>
                      <MarkBadge marker={markerMap.get(entry.idx)} />
                      <span className="gcell-isin" translate="no">
                        {instruments.isin[entry.idx]}
                      </span>
                    </th>
                    <td className="n">{counts(entry, 'n1')}</td>
                    <td className="n">{counts(entry, 'n3')}</td>
                    <td className="n">{counts(entry, 'n10')}</td>
                    <td className="n">{counts(entry, 'available')}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={current} pages={pages} onChange={(p) => set({ seite: p })} label="Seiten des Häufigkeitsrankings" />
    </section>
  );
}

