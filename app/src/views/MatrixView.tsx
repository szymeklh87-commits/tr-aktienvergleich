/* Gruppenvergleich A/B über 1–90 Tage: Matrix, kompakte Liste und Häufigkeitsranking (ab 1.4, 90 Zeilen ab 1.5).
 *
 * Zeilen = Zeiträume, Spalten = elf Gewichtungen, Zelle = erstplatzierte Aktie. Wiederkehrende
 * Aktien tragen in allen Ansichten und in beiden Gruppen dieselbe Kennzeichnung (Farbe und
 * „↻ Anzahl“). Antippen markiert alle Vorkommen und bietet Rangliste und Kursverlauf an.
 */

import { useEffect, useMemo, useRef } from 'react';
import { useDark } from '../components/charts';
import { MarkBadge } from '../components/marks';
import { WindowChips } from '../components/controls';
import { IconDownload } from '../components/icons';
import { ErrorNote, IsinCopy, Loading, Notice, Pct, SectionTitle, Segmented, ViewIntro } from '../components/ui';
import { EMPTY_PHRASE, EMPTY_SHORT } from '../lib/codes';
import { seriesColor } from '../lib/colors';
import { downloadText, safeFilename, toCsv, type CsvValue } from '../lib/csv';
import { PREVIEW } from '../lib/env';
import * as f from '../lib/format';
import { GROUP_LABEL, GROUP_TEXT, hasGroups, markers, matrixCoverage, matrixRows, overviewRow, sameText, type GroupSelection, type Marker, type MatrixCell } from '../lib/groups';
import { useFrequency, useOverview } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { buildHash, updateParams, type Route } from '../lib/router';
import { parseGroup, parseWeight, WEIGHTS } from '../lib/scoring';
import type { Group, Instruments, Manifest, Overview } from '../lib/types';
import { useApp } from '../state/AppState';
import { GroupFrequencyTable } from './GroupFrequencyView';

type Mode = 'matrix' | 'liste' | 'haeufigkeit';
const RANGES: [number, number][] = [
  [1, 90],
  [1, 30],
  [31, 60],
  [61, 90],
];

function parseRange(route: Route): [number, number] {
  const from = Number(route.params.get('von'));
  const to = Number(route.params.get('bis'));
  const found = RANGES.find(([a, b]) => a === from && (b === to || (!to && a !== 1)));
  return found ?? RANGES[0];
}

function rangeValue([a, b]: [number, number]): string {
  return `${a}-${b}`;
}

function parseMode(text: string | null): Mode {
  return text === 'liste' || text === 'haeufigkeit' ? text : 'matrix';
}

function weightHead(w: number): [string, string] {
  if (w === 0) return ['0/100', 'nur Rendite'];
  if (w === 100) return ['100/0', 'nur Gleichmäßigkeit'];
  return [`${w}/${100 - w}`, `${w} % gleichmäßig`];
}

export { MarkBadge };

export function MatrixView({ route }: { route: Route }) {
  const { manifest, instruments, prefs } = useApp();
  const overview = useOverview();
  const mode = parseMode(route.params.get('ansicht'));
  const frequency = useFrequency(mode === 'haeufigkeit');
  const group = parseGroup(route.params.get('g') ?? prefs.group);
  const [from, to] = parseRange(route);
  const selected = route.params.get('isin');
  const jump = Number(route.params.get('zeile')) || null;
  const data = overview.data;

  const markerMap = useMemo(() => (data && instruments ? markers(data, instruments, from, to) : new Map<number, Marker>()), [data, instruments, from, to]);
  const rows = useMemo(() => (data ? matrixRows(data, group, from, to) : []), [data, group, from, to]);

  if (!manifest || !instruments) return null;
  const set = (changes: Record<string, string | number | null>) => updateParams(route, changes);
  const selectedIdx = selected ? instruments.isin.indexOf(selected) : -1;
  const toggle = (idx: number) => set({ isin: instruments.isin[idx] === selected ? null : instruments.isin[idx] });
  const groupsReady = hasGroups(data);
  const jumpTo = (h: number) => {
    const inRange = h >= from && h <= to;
    set({ zeile: h, ...(inRange ? {} : { von: null, bis: null }) });
  };
  const freqGroups = route.params.get('gruppen');

  return (
    <div className="view matrix-view">
      <header className="view-head">
        <ViewIntro>
          <p className="lede">
            Eine Tabelle mit Platz 1 für jeden Zeitraum (Zeilen, 1 bis 90 Tage) und jede Gewichtung (Spalten) – getrennt für Gruppe A (alle vergleichbaren Aktien) und Gruppe B
            (nur Ø Tagesumsatz ab 10 Mio. USD). Gleiche Aktien sind gleich gekennzeichnet; tippe eine an, um alle ihre Felder zu markieren.
          </p>
          <p className="section-note">
            Kursstand {f.dayLong(manifest.cutoff_day)}, berechnet {f.berlinTime(manifest.computed_at_utc)}. Historische Tagesschlusskurse, keine Livekurse.
          </p>
        </ViewIntro>
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
          options={RANGES.map((range) => ({ value: rangeValue(range), label: range[0] === 1 && range[1] === 90 ? 'Alle 1–90' : `${range[0]}–${range[1]}` }))}
          value={rangeValue([from, to])}
          onChange={(v) => {
            const [a, b] = v.split('-').map(Number);
            set({ von: a === 1 && b === 90 ? null : a, bis: a === 1 && b === 90 ? null : b, seite: null, zeile: null });
          }}
        />
        {mode !== 'haeufigkeit' ? <WindowChips value={jump} onPick={jumpTo} label="Zu Zeitraum springen" onPage /> : null}
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
              <p className="section-note">
                Gewichtungen seitlich wischen, die Zeiträume bleiben links stehen. Zelle: Spitzenaktie, ISIN, tatsächliche Kursrendite und Rangscore 0–100. ≡ = identisches Kursfenster wie in den
                genannten Zeiträumen (gleicher Bestand aus ISIN und tatsächlichem Startdatum, etwa durch Wochenende oder Feiertag).
              </p>
              <Matrix rows={rows} instruments={instruments} markers={markerMap} selectedIdx={selectedIdx} onPick={toggle} jump={jump} />
              {!PREVIEW ? <MatrixExport rows={rows} instruments={instruments} manifest={manifest} group={group} /> : null}
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
              jump={jump}
            />
          ) : null}
          {mode === 'haeufigkeit' ? (
            frequency.error ? (
              <ErrorNote error={frequency.error} />
            ) : frequency.data ? (
              <GroupFrequencyTable
                route={route}
                manifest={manifest}
                frequencyData={frequency.data}
                overview={data}
                instruments={instruments}
                groups={(freqGroups === 'ab' ? 'ab' : group) as GroupSelection}
                from={from}
                to={to}
                onGroups={(value) => set({ gruppen: value === 'ab' ? 'ab' : null, g: value === 'ab' ? route.params.get('g') : value === 'a' ? null : value, seite: null })}
              />
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
        <span className="muted">Rangscore {f.score(row.score ?? null)}</span>
      </span>
    </>
  );
}

function Matrix({
  rows,
  instruments,
  markers: markerMap,
  selectedIdx,
  onPick,
  jump,
}: {
  rows: ReturnType<typeof matrixRows>;
  instruments: Instruments;
  markers: Map<number, Marker>;
  selectedIdx: number;
  onPick: (idx: number) => void;
  jump: number | null;
}) {
  const dark = useDark();
  const wrapRef = useRef<HTMLDivElement | null>(null);
  // Schnellwahl 7 … 90 Tage: Zeile unter den fixierten Kopf holen
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap || !jump) return;
    const row = wrap.querySelector<HTMLElement>(`tr[data-h="${jump}"]`);
    if (!row) return;
    const head = (wrap.querySelector('thead') as HTMLElement | null)?.getBoundingClientRect().height ?? 0;
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    wrap.scrollTo({ top: wrap.scrollTop + row.getBoundingClientRect().top - wrap.getBoundingClientRect().top - head, behavior: reduced ? 'auto' : 'smooth' });
    wrap.closest('.matrix-view')?.querySelector('.gmatrix-wrap')?.scrollIntoView({ block: 'nearest' });
  }, [jump, rows]);
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
            <tr key={row.h} data-h={row.h} className={row.h === jump ? 'is-jump' : undefined} aria-current={row.h === jump ? 'true' : undefined}>
              <th scope="row" className="gday">
                {row.h}
                {row.h === jump ? <small className="jump-note">gewählt</small> : null}
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
                        aria-label={`${f.windowLabel(row.h)}, ${f.weightLabel(cell.weight)}: ${instName(instruments, idx)}, ${f.pct(cell.row.r ?? null, 1)}, Rangscore ${f.score(cell.row.score ?? null)}${recurring ? `, ${marker!.count} erste Plätze` : ''}`}
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
  jump,
}: {
  rows: ReturnType<typeof matrixRows>;
  instruments: Instruments;
  markers: Map<number, Marker>;
  selectedIdx: number;
  weight: number;
  onWeight: (w: number) => void;
  onPick: (idx: number) => void;
  jump: number | null;
}) {
  const k = WEIGHTS.indexOf(weight as (typeof WEIGHTS)[number]);
  const listRef = useRef<HTMLOListElement | null>(null);
  useEffect(() => {
    if (!jump) return;
    const item = listRef.current?.querySelector<HTMLElement>(`li[data-h="${jump}"]`);
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    item?.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' });
  }, [jump, rows]);
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
      <ol className="glist" ref={listRef}>
        {rows.map((row) => {
          const cell = row.cells[k];
          const idx = cell.row.idx;
          const marker = idx !== undefined ? markerMap.get(idx) : undefined;
          return (
            <li
              key={row.h}
              data-h={row.h}
              className={`glist-row${idx !== undefined && idx === selectedIdx ? ' is-selected' : ''}${row.h === jump ? ' is-jump' : ''}`}
              aria-current={row.h === jump ? 'true' : undefined}
            >
              <span className="glist-day" aria-label={f.windowLabel(row.h)}>
                {row.h === 1 ? '1 Tag' : `${row.h} Tage`}
                {row.h === jump ? <small className="jump-note">gewählt</small> : null}
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

/** Matrix einer Gruppe als CSV oder JSON (alle Zeilen des Ausschnitts, alle elf Gewichtungen). */
function MatrixExport({ rows, instruments, manifest, group }: { rows: ReturnType<typeof matrixRows>; instruments: Instruments; manifest: Manifest; group: Group }) {
  const meta: [string, string][] = [
    ['Ansicht', `Matrix ${GROUP_LABEL[group]} (${GROUP_TEXT[group]})`],
    ['Zeiträume', `${rows[0]?.h ?? 1}–${rows[rows.length - 1]?.h ?? 90} Kalendertage`],
    ['Zelle', 'erstplatzierte Aktie je Zeitraum und Gewichtung (Gleichmäßigkeit/Kursrendite)'],
    ['Snapshot', manifest.snapshot_id],
    ['Kursstichtag', manifest.cutoff_session_date],
    ['Berechnet', manifest.computed_at_utc],
    ['Methode', manifest.versions?.method ?? ''],
    ['Datenmodus', manifest.data_mode === 'demo' ? 'DEMO – synthetische Testdaten' : manifest.data_mode],
  ];
  const cells = rows.flatMap((row) =>
    row.cells.map((cell) => {
      const r = cell.row;
      return {
        tage: row.h,
        gewichtung: f.weightShort(cell.weight),
        name: r.idx !== undefined ? instName(instruments, r.idx) : null,
        isin: r.idx !== undefined ? instruments.isin[r.idx] : null,
        kursrendite_prozent: r.r !== undefined && r.r !== null ? 100 * r.r : null,
        rangscore: r.score ?? null,
        r2: r.r2 ?? null,
        beginn: r.start !== undefined ? f.day(r.start) : null,
        schlusskurse: r.n ?? null,
        vergleichsfeld: r.M,
        gleichstand: Boolean(r.tie),
        identisch_mit: cell.same,
        nicht_berechenbar: r.idx === undefined ? EMPTY_PHRASE[r.empty ?? ''] ?? r.empty ?? 'keine Rangliste' : null,
      };
    }),
  );
  const name = `matrix_gruppe${group.toUpperCase()}_${rows[0]?.h ?? 1}-${rows[rows.length - 1]?.h ?? 90}_${manifest.snapshot_id}`;
  const csv = () => {
    const header = ['Tage', 'Gewichtung', 'Unternehmen', 'ISIN', 'Kursrendite %', 'Rangscore', 'R²', 'Beginn', 'Schlusskurse', 'Vergleichsfeld', 'Gleichstand', 'Identisch mit', 'Nicht berechenbar'];
    const data: CsvValue[][] = cells.map((c) => [c.tage, c.gewichtung, c.name, c.isin, c.kursrendite_prozent, c.rangscore, c.r2, c.beginn, c.schlusskurse, c.vergleichsfeld, c.gleichstand, c.identisch_mit.join(' '), c.nicht_berechenbar]);
    downloadText(safeFilename(`${name}.csv`), toCsv(meta, header, data, [undefined, undefined, undefined, undefined, 6, 4, 6]));
  };
  const json = () => downloadText(safeFilename(`${name}.json`), JSON.stringify({ format: 'tr-matrix/1', meta: Object.fromEntries(meta), zellen: cells }, null, 2), 'application/json;charset=utf-8');
  return (
    <div className="toolbar no-print">
      <button type="button" className="btn btn-quiet" onClick={csv}>
        <IconDownload /> Matrix als CSV
      </button>
      <button type="button" className="btn btn-quiet" onClick={json}>
        <IconDownload /> Matrix als JSON
      </button>
    </div>
  );
}
