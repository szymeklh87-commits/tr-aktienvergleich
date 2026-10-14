/* Bericht „1–30 Tage · Rendite und Gleichmäßigkeit“ (ab 1.8.1) – eine Seite zum Durchscrollen wie der
 * Bericht 30D-4W-two-groups: je Zeitraum 1–30 Tage der Spitzenreiter für 0/100, 40/60, 50/50 und 60/40
 * (vier Tabellen untereinander, Gruppe A und B nebeneinander), alle vier Gewichtungen nebeneinander als
 * Matrix, „Welche Aktie erscheint am häufigsten?“ und die Wege zur vollständigen Rangliste, zu den
 * Kursverläufen, zur Abdeckung und zur Rechenvorschrift. Antippen in Matrix oder Häufigkeit hebt alle
 * Vorkommen einer ISIN auf der ganzen Seite hervor. */

import { useMemo } from 'react';
import { useDark } from '../components/charts';
import { TotalBadge } from '../components/signals';
import { IconClose, IconDownload } from '../components/icons';
import { ErrorNote, Loading, Notice, Pct, SectionTitle, Segmented, ViewIntro } from '../components/ui';
import { EMPTY_SHORT } from '../lib/codes';
import { seriesColor } from '../lib/colors';
import { downloadText, safeFilename, toCsv } from '../lib/csv';
import { PREVIEW } from '../lib/env';
import * as f from '../lib/format';
import { canDedupe, groupFrequency, hasGroups, overviewRow, total, type FrequencyOrder, type GroupSelection, type Marker, type MatrixRow } from '../lib/groups';
import { useFrequency, useOverview, useSignals } from '../lib/hooks';
import { berlinClock, isIntraday } from '../lib/intraday';
import { instName } from '../lib/instruments';
import {
  firstReportCell,
  parseReportPick,
  pickedWeights,
  REPORT_DAYS,
  REPORT_WEIGHTS,
  reportBlocks,
  reportCsvRows,
  reportLeaders,
  reportMarkers,
  reportMatrix,
  reportRows,
  reportStats,
  type ReportCell,
  type ReportRow,
} from '../lib/report';
import { buildHash, updateParams, type Route } from '../lib/router';
import { GRADE_WORD, totalsByIsin, type TotalEntry } from '../lib/signals';
import { thresholdLabel } from '../lib/turnover';
import type { Group, Instruments, Manifest, Overview } from '../lib/types';
import { useApp } from '../state/AppState';

const SECTIONS = [
  { id: 'bericht-tabellen', label: 'Tabellen' },
  { id: 'bericht-matrix', label: 'Nebeneinander' },
  { id: 'bericht-haeufig', label: 'Häufigkeit' },
];

function wl(w: number): string {
  return `${w}/${100 - w}`;
}

function emptyText(reason: string | undefined): string {
  const text = reason ? EMPTY_SHORT[reason] ?? reason : 'nicht berechenbar';
  return text[0].toUpperCase() + text.slice(1);
}

function scrollToSection(id: string) {
  const el = document.getElementById(id);
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  el?.scrollIntoView({ block: 'start', behavior: reduced ? 'auto' : 'smooth' });
}

type Totals = Map<string, TotalEntry> | null;

function Total({ isin, totals }: { isin: string; totals: Totals }) {
  const entry = totals?.get(isin);
  return entry ? <TotalBadge total={entry.total} grade={entry.grade} size="mini" /> : null;
}

function Cell({ c, instruments, manifest, marked, totals }: { c: ReportCell; instruments: Instruments; manifest: Manifest; marked: boolean; totals: Totals }) {
  if (c.idx === null) return <span className="rep-empty">{emptyText(c.row?.empty)}</span>;
  const row = c.row!;
  const isin = instruments.isin[c.idx];
  const unit = instruments.price_unit[c.idx] ?? instruments.currency[c.idx];
  return (
    <a
      className="rep-cell"
      href={buildHash(`/aktie/${isin}`, { tab: 'rendite', h: c.h, w: c.weight, p: 'native', g: c.group === 'b' ? 'b' : null })}
      aria-current={marked ? 'true' : undefined}
    >
      <span className="rep-name">
        {instName(instruments, c.idx)}
        {c.repeats > 1 ? (
          <span className="rep-rep" aria-label={`in ${c.repeats} von ${REPORT_DAYS} Zeiträumen vorne`}>
            ↻{c.repeats}
          </span>
        ) : null}
        <Total isin={isin} totals={totals} />
      </span>
      <span className="rep-isin" translate="no">
        {isin}
      </span>
      <Pct value={row.r} strong />
      <span className="rep-meta">
        {row.start !== undefined ? `${f.dayShort(row.start)}–${f.dayShort(manifest.cutoff_day)}` : ''}
        {unit ? ` · ${unit}` : ''}
        {c.weight > 0 && row.score !== undefined && row.score !== null ? ` · Score ${f.score(row.score)}` : ''}
      </span>
    </a>
  );
}

function ReportTable({
  weight,
  rows,
  withB,
  instruments,
  manifest,
  markedIdx,
  totals,
}: {
  weight: number;
  rows: ReportRow[];
  withB: boolean;
  instruments: Instruments;
  manifest: Manifest;
  markedIdx: number;
  totals: Totals;
}) {
  const blocks = reportBlocks(rows, withB);
  const filled = rows.filter((row) => row.a.idx !== null || (withB && row.b.idx !== null)).length;
  return (
    <section className="rep-block" aria-labelledby={`bericht-w${weight}`}>
      <h3 className="rep-block-title" id={`bericht-w${weight}`}>
        {wl(weight)} <span>Gleichmäßigkeit/Kursrendite</span>
      </h3>
      <p className="section-note">
        {weight === 0 ? 'Nur Kursrendite.' : `${weight} % Gleichmäßigkeit (R²), ${100 - weight} % Kursrendite.`} {filled} von {REPORT_DAYS} Zeiträumen mit Spitzenreiter.
      </p>
      <table className={`rep-table${markedIdx >= 0 ? ' has-mark' : ''}`}>
        <thead>
          <tr>
            <th scope="col">Tage</th>
            <th scope="col">A · ohne Umsatzgrenze</th>
            <th scope="col">B · Ø ≥ {thresholdLabel(manifest)}</th>
          </tr>
        </thead>
        <tbody>
          {blocks.map((block) =>
            block.kind === 'leer' ? (
              <tr key={`leer-${block.from}`} className="rep-gap">
                <th scope="row">{block.from === block.to ? block.from : `${block.from}–${block.to}`}</th>
                <td colSpan={2}>
                  <span className="rep-empty">
                    {emptyText(block.reason)}
                    {withB ? ' (A und B)' : ''}
                  </span>
                </td>
              </tr>
            ) : (
              <tr key={block.row.h} data-h={block.row.h}>
                <th scope="row">{block.row.h}</th>
                <td className={block.row.a.idx !== null && block.row.a.idx === markedIdx ? 'is-marked' : undefined}>
                  <Cell c={block.row.a} instruments={instruments} manifest={manifest} marked={block.row.a.idx === markedIdx} totals={totals} />
                </td>
                <td className={withB && block.row.b.idx !== null && block.row.b.idx === markedIdx ? 'is-marked' : undefined}>
                  {withB ? <Cell c={block.row.b} instruments={instruments} manifest={manifest} marked={block.row.b.idx === markedIdx} totals={totals} /> : <span className="rep-empty">–</span>}
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
    </section>
  );
}

function ReportMatrix({
  rows,
  instruments,
  markerMap,
  markedIdx,
  onPick,
}: {
  rows: MatrixRow[];
  instruments: Instruments;
  markerMap: Map<number, Marker>;
  markedIdx: number;
  onPick: (idx: number) => void;
}) {
  const dark = useDark();
  return (
    <table className={`rep-matrix${markedIdx >= 0 ? ' has-mark' : ''}`}>
      <thead>
        <tr>
          <th scope="col">Tage</th>
          {REPORT_WEIGHTS.map((w) => (
            <th scope="col" key={w}>
              {wl(w)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.h} data-h={row.h}>
            <th scope="row">{row.h}</th>
            {row.cells.map((cell) => {
              const idx = cell.row.idx;
              if (idx === undefined) {
                const reason = emptyText(cell.row.empty);
                return (
                  <td key={cell.weight} className="rm-cell is-empty" title={reason}>
                    <span aria-hidden="true">–</span>
                    <span className="visually-hidden">{reason}</span>
                  </td>
                );
              }
              const marker = markerMap.get(idx);
              const recurring = marker !== undefined && marker.count >= 2;
              const color = recurring && marker.slot !== null ? seriesColor(marker.slot, dark) : undefined;
              const isMarked = idx === markedIdx;
              return (
                <td key={cell.weight} className={`rm-cell${isMarked ? ' is-marked' : ''}`} style={color ? { borderLeftColor: color } : undefined}>
                  <button
                    type="button"
                    className="rm-btn"
                    aria-pressed={isMarked}
                    aria-label={`${f.windowLabel(row.h)}, ${wl(cell.weight)}: ${instName(instruments, idx)}, ${f.pct(cell.row.r ?? null, 1)}${recurring ? `, ${marker.count} erste Plätze im Bericht` : ''}`}
                    onClick={() => onPick(idx)}
                  >
                    <span className="rm-name">{instName(instruments, idx)}</span>
                    <span className="rm-figs">
                      <Pct value={cell.row.r ?? null} digits={1} strong />
                      {recurring ? <span className="rm-rep">↻{marker.count}</span> : null}
                    </span>
                  </button>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Springt zur nächsten hervorgehobenen Zelle unterhalb des sichtbaren Ausschnitts (am Ende wieder zur ersten). */
function scrollToNextMarked() {
  const cells = [...document.querySelectorAll<HTMLElement>('.report-view td.is-marked')];
  if (!cells.length) return;
  const appbar = document.querySelector<HTMLElement>('.appbar')?.getBoundingClientRect().height ?? 56;
  const offset = appbar + 48; // fixierter Tabellenkopf
  // unten verdecken Leiste und Navigation einen Teil des Bildschirms
  const coveredBelow = (document.querySelector<HTMLElement>('.rep-markbar')?.getBoundingClientRect().height ?? 0) + (document.querySelector<HTMLElement>('.bottomnav')?.getBoundingClientRect().height ?? 0) + 16;
  const visibleEnd = window.scrollY + window.innerHeight - coveredBelow;
  const tops = cells.map((el) => el.getBoundingClientRect().top + window.scrollY);
  const below = tops.find((top) => top + 24 > visibleEnd);
  const next = below ?? tops[0];
  const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  window.scrollTo({ top: Math.max(0, next - offset), behavior: reduced ? 'auto' : 'smooth' });
}

function MarkBar({
  overview,
  instruments,
  idx,
  marker,
  withB,
  hits,
  total,
  onClear,
}: {
  overview: Overview;
  instruments: Instruments;
  idx: number;
  marker: Marker | undefined;
  withB: boolean;
  hits: number;
  total: TotalEntry | undefined;
  onClear: () => void;
}) {
  const isin = instruments.isin[idx];
  const first = firstReportCell(overview, idx);
  const counts = marker ? (withB ? `${marker.count}× Platz 1 in 1–30 Tagen (A: ${marker.countA}, B: ${marker.countB})` : `${marker.count}× Platz 1 in 1–30 Tagen`) : 'In 1–30 Tagen nie auf Platz 1';
  return (
    <section className="rep-markbar" aria-label="Hervorgehobene Aktie">
      <p className="rep-markbar-text">
        <strong>{instName(instruments, idx)}</strong>
        <span>
          {counts}
          {total && total.total !== null ? ` · Gesamtwertung ${Math.round(total.total)} (${GRADE_WORD[total.grade]})` : ''} · <span translate="no">{isin}</span>
        </span>
      </p>
      <button type="button" className="icon-btn" aria-label="Markierung entfernen" title="Markierung entfernen" onClick={onClear}>
        <IconClose />
      </button>
      <div className="rep-markbar-actions">
        {hits > 0 ? (
          <button type="button" className="btn btn-quiet" onClick={scrollToNextMarked}>
            Nächstes Vorkommen
          </button>
        ) : null}
        <a className="btn btn-primary" href={buildHash(`/aktie/${isin}`, { tab: 'rendite', h: first?.h ?? REPORT_DAYS, w: first?.weight ?? 0, p: 'native', g: first?.group === 'b' ? 'b' : null })}>
          Kursverlauf
        </a>
      </div>
    </section>
  );
}

/** Hervorgehobene Zellen auf der Seite: Tabellen der gewählten Gewichtungen (A und B) und Matrix (gewählte Gruppe). */
function markedHits(overview: Overview, idx: number, weights: number[], withB: boolean, matrixGroup: Group): number {
  let hits = 0;
  for (let h = 1; h <= REPORT_DAYS; h++) {
    for (const weight of weights) {
      if (overviewRow(overview, 'a', weight, h)?.idx === idx) hits++;
      if (withB && overviewRow(overview, 'b', weight, h)?.idx === idx) hits++;
    }
    for (const weight of REPORT_WEIGHTS) if (overviewRow(overview, matrixGroup, weight, h)?.idx === idx) hits++;
  }
  return hits;
}

export function ReportView({ route }: { route: Route }) {
  const { manifest, instruments } = useApp();
  const overview = useOverview();
  const frequency = useFrequency();
  const signals = useSignals();
  const totals = useMemo(() => totalsByIsin(signals.data), [signals.data]);
  const pick = parseReportPick(route.params.get('w'));
  const data = overview.data;
  const withB = data ? hasGroups(data) : false;
  const matrixGroup: Group = route.params.get('mg') === 'b' && withB ? 'b' : 'a';

  const tables = useMemo(() => (data ? REPORT_WEIGHTS.map((w) => ({ weight: w, rows: reportRows(data, w) })) : []), [data]);
  const matrix = useMemo(() => (data ? reportMatrix(data, matrixGroup) : []), [data, matrixGroup]);
  const markerMap = useMemo(() => (data && instruments ? reportMarkers(data, instruments) : new Map<number, Marker>()), [data, instruments]);
  const leaders = useMemo(() => (instruments ? reportLeaders(markerMap, instruments, 5) : []), [markerMap, instruments]);
  const stats = useMemo(
    () => (data && instruments && manifest ? reportStats(data, instruments, manifest.coverage.universe_total, manifest.coverage.histories_loaded) : null),
    [data, instruments, manifest],
  );

  const groupsParam = route.params.get('fg');
  const groups: GroupSelection = groupsParam === 'a' || groupsParam === 'b' ? groupsParam : 'ab';
  const onlyTrend = route.params.get('fw') === 'trend';
  const order: FrequencyOrder = route.params.get('sort') === 'n10' ? 'n10' : 'n1';
  const dedupeAvailable = canDedupe(frequency.data, instruments);
  const dedupe = route.params.get('einmal') === '1' && dedupeAvailable;
  const freq = useMemo(() => {
    if (!frequency.data || !instruments) return null;
    try {
      return groupFrequency(frequency.data, instruments, { groups, weights: onlyTrend ? [40, 50, 60] : [...REPORT_WEIGHTS], from: 1, to: REPORT_DAYS, dedupe, order });
    } catch (exc) {
      return exc instanceof Error ? exc : new Error(String(exc));
    }
  }, [frequency.data, instruments, groups, onlyTrend, dedupe, order]);

  if (!manifest || !instruments) return null;
  const set = (changes: Record<string, string | number | null>) => updateParams(route, changes);
  const intraday = isIntraday(manifest);
  const marked = route.params.get('m');
  const markedIdx = marked ? instruments.isin.indexOf(marked) : -1;
  const toggleMark = (idx: number) => set({ m: instruments.isin[idx] === marked ? null : instruments.isin[idx] });

  const download = () => {
    if (!data) return;
    const csv = toCsv(
      [
        ['Inhalt', 'Bericht 1–30 Tage: Spitzenreiter je Zeitraum, Gewichtungen 0/100, 40/60, 50/50, 60/40, Gruppe A und B'],
        ['Kursstichtag', manifest.cutoff_session_date],
        ['Art', intraday ? `Zwischenstand, Kurse bis ${berlinClock(manifest.zwischenstand?.kurse_bis_utc)} (vorläufig)` : 'Stand mit Schlusskursen (Tagesschluss)'],
        ['Snapshot', manifest.snapshot_id],
        ['Gruppe B', `Ø Tagesumsatz ≥ ${thresholdLabel(manifest)} über 20 Sitzungen`],
        ['Basis', manifest.currency_basis],
      ],
      ['Gewichtung', 'Tage', 'Gruppe', 'Unternehmen', 'ISIN', 'Kursrendite', 'Score', 'R²', 'Start', 'Ende', 'Einheit', 'Hinweis'],
      reportCsvRows(data, instruments, manifest.cutoff_day, (day) => f.day(day)),
      [undefined, undefined, undefined, undefined, undefined, 6, 2, 4],
    );
    downloadText(safeFilename(`bericht_1-30_${manifest.snapshot_id}.csv`), csv);
  };

  return (
    <div className="view report-view">
      <header className="view-head">
        <ViewIntro>
          <p className="lede">
            Je Zeitraum von 1 bis 30 Kalendertagen die Aktie auf Platz 1 – für vier Gewichtungen Gleichmäßigkeit/Kursrendite (0/100, 40/60, 50/50, 60/40), <strong>Gruppe A</strong> (alle
            Aktien) und <strong>Gruppe B</strong> (Ø Tagesumsatz ab {thresholdLabel(manifest)}) nebeneinander. Antippen öffnet Kursverlauf und Kennzahlen.
          </p>
          <p className="section-note">
            {intraday
              ? `Zwischenstand vom ${f.dayLong(manifest.cutoff_day)}, Kurse bis ${berlinClock(manifest.zwischenstand?.kurse_bis_utc)} (vorläufig).`
              : `Kursstichtag ${f.dayLong(manifest.cutoff_day)}, Tagesschlusskurse, berechnet ${f.berlinTime(manifest.computed_at_utc)}.`}{' '}
            Kursrendite in Originalwährung, ohne Dividenden, Wechselkurs, Steuern und Gebühren. Rückblick, keine Prognose.
          </p>
        </ViewIntro>
      </header>

      {stats ? (
        <dl className="rep-stats">
          <div>
            <dt>ISINs im TR-Verzeichnis</dt>
            <dd>{f.integer(stats.isins)}</dd>
          </div>
          <div>
            <dt>geladene Kursreihen</dt>
            <dd>{f.integer(stats.series)}</dd>
          </div>
          <div>
            <dt>Aktien in mindestens einem 1–30-Tage-Fenster</dt>
            <dd>{f.integer(stats.computed)}</dd>
          </div>
          <div>
            <dt>Ranglisten mit Spitzenreiter</dt>
            <dd>
              {f.integer(stats.combos)} <small>von {f.integer(stats.combosTotal)}</small>
            </dd>
          </div>
        </dl>
      ) : null}

      {leaders.length ? (
        <section className="section rep-leaders" aria-labelledby="bericht-vorne">
          <SectionTitle id="bericht-vorne">Am häufigsten auf Platz 1</SectionTitle>
          <p className="section-note">
            Gezählt über alle {f.integer(stats?.combos ?? 0)} Ranglisten des Berichts (1–30 Tage, vier Gewichtungen{withB ? ', Gruppe A und B' : ''}). Antippen hebt die Aktie auf der ganzen Seite hervor.
            {totals ? ' Das Kästchen hinter dem Namen ist die Gesamtwertung 0–100 (Steig-Konstanz, Kursziel, Aufmerksamkeit, Qualität; grün ab 65, gelb ab 50) – der Blick nach vorn neben dem Rückblick.' : ''}
          </p>
          <ol className="rep-freq">
            {leaders.map((m, k) => (
              <li key={m.idx} className={m.idx === markedIdx ? 'is-marked' : undefined}>
                <span className="rep-rank">{k + 1}</span>
                <button type="button" className="rep-freq-name" aria-pressed={m.idx === markedIdx} onClick={() => toggleMark(m.idx)}>
                  <span>
                    {instName(instruments, m.idx)}
                    <Total isin={instruments.isin[m.idx]} totals={totals} />
                  </span>
                  <small translate="no">{instruments.isin[m.idx]}</small>
                </button>
                <span className="rep-lead-count">
                  <b>{m.count}×</b>
                  {withB ? (
                    <small>
                      A {m.countA} · B {m.countB}
                    </small>
                  ) : null}
                </span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <nav className="rep-jump" aria-label="Im Bericht springen">
        {SECTIONS.map((s) => (
          <button key={s.id} type="button" className="chip" onClick={() => scrollToSection(s.id)}>
            {s.label}
          </button>
        ))}
      </nav>

      <section className="section rep-section" id="bericht-tabellen" aria-labelledby="bericht-tabellen-titel">
        <SectionTitle id="bericht-tabellen-titel">Spitzenreiter je Zeitraum</SectionTitle>
        <Segmented
          label="Gewichtung Gleichmäßigkeit/Kursrendite"
          options={[{ value: 'alle', label: 'Alle vier' }, ...REPORT_WEIGHTS.map((w) => ({ value: String(w), label: wl(w) }))]}
          value={String(pick)}
          onChange={(value) => set({ w: value === 'alle' ? null : value })}
        />
        <p className="section-note">
          0/100 = nur Kursrendite. Bei 40/60, 50/50 und 60/40 zählen Gleichmäßigkeit (R² der Trendgeraden) und Kursrendite als Rangperzentil innerhalb der Gruppe – berechenbar erst ab 15 echten
          Schlusskursen, mit positiver Steigung und positiver Rendite; kurze Zeiträume bleiben deshalb leer. ↻ = dieselbe Aktie liegt in mehreren Zeiträumen vorne; durch Wochenenden kann derselbe
          Kurszeitraum mehrfach erscheinen.{totals ? ' Kästchen = Gesamtwertung 0–100 der Aktie.' : ''}
        </p>
        {overview.error ? <ErrorNote error={overview.error} /> : null}
        {!data && !overview.error ? <Loading height={600} label="Bericht wird geladen" /> : null}
        {data && !withB ? (
          <Notice tone="info" title="Gruppe B in diesem Datenstand noch nicht berechnet">
            <p>Die Spalte B folgt mit dem nächsten täglichen Lauf.</p>
          </Notice>
        ) : null}
        {data
          ? tables
              .filter((t) => pickedWeights(pick).includes(t.weight))
              .map((t) => <ReportTable key={t.weight} weight={t.weight} rows={t.rows} withB={withB} instruments={instruments} manifest={manifest} markedIdx={markedIdx} totals={totals} />)
          : null}
      </section>

      <section className="section rep-section" id="bericht-matrix" aria-labelledby="bericht-matrix-titel">
        <SectionTitle id="bericht-matrix-titel">Alle vier Gewichtungen nebeneinander</SectionTitle>
        <p className="section-note">
          Je Zeitraum die Aktie auf Platz 1 für 0/100, 40/60, 50/50 und 60/40. Gleiche Farbe und ↻ = dieselbe Aktie mehrfach vorne (gezählt im ganzen Bericht). Antippen hebt alle Vorkommen hervor.
        </p>
        {withB ? (
          <Segmented
            label="Gruppe"
            options={[
              { value: 'a', label: 'A · alle Aktien' },
              { value: 'b', label: `B · Ø ≥ ${thresholdLabel(manifest)}` },
            ]}
            value={matrixGroup}
            onChange={(value) => set({ mg: value === 'a' ? null : value })}
          />
        ) : null}
        {data ? <ReportMatrix rows={matrix} instruments={instruments} markerMap={markerMap} markedIdx={markedIdx} onPick={toggleMark} /> : null}
      </section>

      <section className="section rep-section" id="bericht-haeufig" aria-labelledby="bericht-haeufig-titel">
        <SectionTitle id="bericht-haeufig-titel">Welche Aktie erscheint am häufigsten?</SectionTitle>
        <p className="section-note">
          Gezählt über die 30 Zeiträume und die gewählten Gewichtungen: wie oft eine Aktie auf Platz 1, unter den ersten 3 und unter den ersten 10 steht. Jede Rangliste zählt je Aktie höchstens
          einmal; Platz 1 zählt zugleich zu Top 3 und Top 10.
        </p>
        <div className="rep-filters">
          <Segmented
            label="Gruppen"
            options={[
              { value: 'ab', label: 'A und B' },
              { value: 'a', label: 'nur A' },
              { value: 'b', label: 'nur B' },
            ]}
            value={groups}
            onChange={(value) => set({ fg: value === 'ab' ? null : value })}
          />
          <Segmented
            label="Gewichtungen"
            options={[
              { value: 'alle', label: 'alle vier' },
              { value: 'trend', label: '40/60, 50/50, 60/40' },
            ]}
            value={onlyTrend ? 'trend' : 'alle'}
            onChange={(value) => set({ fw: value === 'alle' ? null : value })}
          />
          <Segmented
            label="Ranking nach"
            options={[
              { value: 'n1', label: 'ersten Plätzen' },
              { value: 'n10', label: 'Top-10-Nennungen' },
            ]}
            value={order}
            onChange={(value) => set({ sort: value === 'n1' ? null : value })}
          />
          {dedupeAvailable ? (
            <Segmented
              label="Zählweise"
              options={[
                { value: '0', label: 'jedes Fenster' },
                { value: '1', label: 'gleiche Kursfenster einmal' },
              ]}
              value={dedupe ? '1' : '0'}
              onChange={(value) => set({ einmal: value === '1' ? '1' : null })}
            />
          ) : null}
        </div>
        {frequency.error ? <ErrorNote error={frequency.error} /> : null}
        {!frequency.data && !frequency.error ? <Loading height={360} label="Häufigkeiten werden gezählt" /> : null}
        {freq instanceof Error ? <ErrorNote error={freq} /> : null}
        {freq && !(freq instanceof Error) ? (
          <>
            <p className="rep-freq-head" aria-hidden="true">
              <span>Platz 1</span>
              <span>Top 3</span>
              <span>Top 10</span>
            </p>
            <ol className="rep-freq">
              {freq.entries.slice(0, 30).map((entry, k) => (
                <li key={entry.idx} className={entry.idx === markedIdx ? 'is-marked' : undefined}>
                  <span className="rep-rank">{k + 1}</span>
                  <button type="button" className="rep-freq-name" aria-pressed={entry.idx === markedIdx} onClick={() => toggleMark(entry.idx)}>
                    <span>
                      {instName(instruments, entry.idx)}
                      <Total isin={instruments.isin[entry.idx]} totals={totals} />
                    </span>
                    <small translate="no">{instruments.isin[entry.idx]}</small>
                  </button>
                  <span className="rep-freq-nums" aria-label={`Platz 1: ${total(entry, 'n1', groups)}, Top 3: ${total(entry, 'n3', groups)}, Top 10: ${total(entry, 'n10', groups)}`}>
                    <b>{total(entry, 'n1', groups)}</b>
                    <span>{total(entry, 'n3', groups)}</span>
                    <span>{total(entry, 'n10', groups)}</span>
                  </span>
                </li>
              ))}
            </ol>
            <p className="section-note">
              Antippen hebt die Aktie in Tabellen und Matrix hervor. Mehr Filter, alle Zeiträume 1–90 und Download: <a href={buildHash('/haeufig', { von: 1, bis: 30, gruppen: groups })}>Häufigste Aktien</a>.
            </p>
          </>
        ) : null}
      </section>

      <nav className="entry-grid" aria-label="Weiter im Bericht">
        <a className="entry entry-main" href="#/depots">
          <strong>Musterdepots aus diesem Bericht</strong>
          <span>Die zehn häufigsten Sieger und die zehn häufigsten Top-10-Aktien als Depot: Rendite und Beitrag jeder Aktie für 1–30 Tage</span>
        </a>
        <a className="entry" href={buildHash('/ranking', { h: 30, w: pick === 'alle' ? 0 : pick, p: 'native' })}>
          <strong>Vollständige Rangliste</strong>
          <span>Alle auswertbaren Aktien mit Score, Rendite, R², Schlusskurs, Ø Umsatz</span>
        </a>
        <a className="entry" href={buildHash('/raster', { h: 30, w: pick === 'alle' ? 0 : pick })}>
          <strong>Kursverläufe im Raster</strong>
          <span>Die ersten Aktien als Charts, Start = 100</span>
        </a>
        <a className="entry" href="#/aktien">
          <strong>Abdeckung</strong>
          <span>Alle {f.integer(manifest.coverage.universe_total)} ISINs und Datenlücken</span>
        </a>
        <a className="entry" href="#/methodik">
          <strong>Berechnung und Grenzen</strong>
          <span>Zeitraum, Rendite, Gleichmäßigkeit, Score, Gruppe B</span>
        </a>
      </nav>

      {!PREVIEW && data ? (
        <div className="toolbar no-print">
          <button type="button" className="btn" onClick={download}>
            <IconDownload /> Bericht herunterladen (CSV)
          </button>
        </div>
      ) : null}

      {data && markedIdx >= 0 ? (
        <MarkBar
          overview={data}
          instruments={instruments}
          idx={markedIdx}
          marker={markerMap.get(markedIdx)}
          withB={withB}
          hits={markedHits(data, markedIdx, pickedWeights(pick), withB, matrixGroup)}
          total={totals?.get(instruments.isin[markedIdx])}
          onClear={() => set({ m: null })}
        />
      ) : null}
    </div>
  );
}
