/* Gruppenvergleich A/B über 1–30 Tage (ab 1.4, `gruppen-v1`).
 *
 * Gruppe A: alle Aktien mit ausreichender Datenqualität (0/100 auf V, übrige Gewichtungen auf U).
 * Gruppe B: dieselben Aktien, zusätzlich Ø Tagesumsatz ≥ 10 Mio. USD über 20 Sitzungen
 *           (0/100 auf V ∩ L, übrige auf U ∩ L, Perzentile innerhalb der Gruppe).
 * Beide Gruppen werden auf dem Server berechnet; die App liest Spitzenreiter (overview.bin) und
 * Top-10-Fundstellen (frequency.bin) und zählt hier nur. Identität immer über den Instrumentindex
 * (= ISIN), nie über Namen oder Ticker – Aktiengattungen und ADRs haben eigene ISINs.
 */

import { decodeBits, WEIGHTS } from './scoring';
import type { FrequencyData, Group, Instruments, Occurrences, Overview, OverviewRow } from './types';

export const GROUP_LABEL: Record<Group, string> = { a: 'Gruppe A', b: 'Gruppe B' };
export const GROUP_TEXT: Record<Group, string> = {
  a: 'alle vergleichbaren Aktien',
  b: 'nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD',
};
export const MARKER_SLOTS = 8;

/** Enthält der Datenstand die Ranglisten der Gruppe B? (ältere Stände nicht) */
export function hasGroups(overview: Overview | null | undefined): boolean {
  return Boolean(overview?.v0l && overview.v0l.length && overview.ul && Object.keys(overview.ul).length === WEIGHTS.length);
}

export function overviewRow(overview: Overview, group: Group, weight: number, h: number): OverviewRow | undefined {
  if (group === 'a') return weight === 0 ? overview.v0[h - 1] : overview.u[String(weight)]?.[h - 1];
  return weight === 0 ? overview.v0l?.[h - 1] : overview.ul?.[String(weight)]?.[h - 1];
}

export interface MatrixCell {
  h: number;
  weight: number;
  row: OverviewRow;
  /** Andere Zeiträume derselben Spalte mit derselben Spitzenaktie und demselben tatsächlichen Start- und Endkurs */
  same: number[];
}

export interface MatrixRow {
  h: number;
  cells: MatrixCell[];
}

/** Matrix Zeiträume × elf Gewichtungen einer Gruppe; markiert identische Kursfenster je Spalte. */
export function matrixRows(overview: Overview, group: Group, from: number, to: number): MatrixRow[] {
  const rows: MatrixRow[] = [];
  for (let h = from; h <= to; h += 1) {
    rows.push({
      h,
      cells: WEIGHTS.map((weight) => ({ h, weight, row: overviewRow(overview, group, weight, h) ?? { h, M: 0, empty: 'keine_vergleichbare_aktie' }, same: [] })),
    });
  }
  for (let k = 0; k < WEIGHTS.length; k += 1) {
    const byWindow = new Map<string, MatrixCell[]>();
    for (const row of rows) {
      const cell = row.cells[k];
      if (cell.row.idx === undefined || cell.row.start === undefined) continue;
      const key = `${cell.row.idx}:${cell.row.start}`;
      const list = byWindow.get(key) ?? [];
      list.push(cell);
      byWindow.set(key, list);
    }
    for (const list of byWindow.values()) {
      if (list.length < 2) continue;
      for (const cell of list) cell.same = list.filter((other) => other !== cell).map((other) => other.h);
    }
  }
  return rows;
}

export interface CoverageCount {
  theoretical: number;
  computed: number;
  /** leere Ranglisten je Grund (Schlüssel wie overview.empty) */
  empty: Record<string, number>;
}

export function matrixCoverage(rows: MatrixRow[]): CoverageCount {
  const out: CoverageCount = { theoretical: 0, computed: 0, empty: {} };
  for (const row of rows) {
    for (const cell of row.cells) {
      out.theoretical += 1;
      if (cell.row.M > 0) out.computed += 1;
      else {
        const key = cell.row.empty ?? 'keine_vergleichbare_aktie';
        out.empty[key] = (out.empty[key] ?? 0) + 1;
      }
    }
  }
  return out;
}

export interface Marker {
  idx: number;
  /** Farbplatz 0–7 für die häufigsten wiederkehrenden Aktien, null = neutrale Kennzeichnung */
  slot: number | null;
  /** Platz-1-Vorkommen in der Matrix (beide Gruppen, gewählte Zeiträume, alle Gewichtungen) */
  count: number;
  countA: number;
  countB: number;
}

/** Kennzeichnung wiederkehrender Spitzenaktien – gleich in beiden Gruppen und allen Ansichten.
 * Grundlage sind die Platz-1-Zellen beider Gruppen im gewählten Zeitraumbereich; die häufigsten
 * bekommen feste Farbplätze (bei Gleichstand nach ISIN), alle mit Anzahl. */
export function markers(overview: Overview, instruments: Instruments, from: number, to: number): Map<number, Marker> {
  const counts = new Map<number, Marker>();
  for (const group of ['a', 'b'] as Group[]) {
    if (group === 'b' && !hasGroups(overview)) continue;
    for (let h = from; h <= to; h += 1) {
      for (const weight of WEIGHTS) {
        const row = overviewRow(overview, group, weight, h);
        if (!row || row.idx === undefined) continue;
        const entry = counts.get(row.idx) ?? { idx: row.idx, slot: null, count: 0, countA: 0, countB: 0 };
        entry.count += 1;
        if (group === 'a') entry.countA += 1;
        else entry.countB += 1;
        counts.set(row.idx, entry);
      }
    }
  }
  const recurring = [...counts.values()].filter((m) => m.count >= 2);
  recurring.sort((a, b) => b.count - a.count || (instruments.isin[a.idx] < instruments.isin[b.idx] ? -1 : 1));
  recurring.slice(0, MARKER_SLOTS).forEach((m, k) => (m.slot = k));
  return counts;
}

/* ------------------------------------------------------------------ Häufigkeitsranking */

export type GroupSelection = 'a' | 'b' | 'ab';

export interface GroupFrequencyOptions {
  groups: GroupSelection;
  weights: number[];
  from: number;
  to: number;
  /** Identische Kursfenster (gleiche Gewichtung, gleicher tatsächlicher Start und Endkurs) nur einmal zählen */
  dedupe: boolean;
}

export interface GroupCounts {
  n1: number;
  n3: number;
  n10: number;
  available: number;
}

export interface GroupFrequencyEntry {
  idx: number;
  a: GroupCounts;
  b: GroupCounts;
}

export interface GroupFrequencyResult {
  options: GroupFrequencyOptions;
  entries: GroupFrequencyEntry[];
  /** gültige Ranglisten je Gruppe (bei „einmal zählen“: verschiedene Kursfenster der Spitzen-Fundstellen nicht gezählt) */
  validA: number;
  validB: number;
  theoretical: number;
  /** Top-10-Fundstellen, die als identisches Kursfenster zusammengefasst wurden (nur bei „einmal zählen“) */
  mergedA: number;
  mergedB: number;
}

function emptyCounts(): GroupCounts {
  return { n1: 0, n3: 0, n10: 0, available: 0 };
}

export function total(entry: GroupFrequencyEntry, key: keyof GroupCounts, groups: GroupSelection): number {
  if (groups === 'a') return entry.a[key];
  if (groups === 'b') return entry.b[key];
  return entry.a[key] + entry.b[key];
}

function occurrencesOf(freq: FrequencyData, group: Group, weight: number): Occurrences | undefined {
  if (group === 'a') return weight === 0 ? freq.occ.v0 : freq.occ.u[String(weight)];
  return weight === 0 ? freq.occ.v0l : freq.occ.ul?.[String(weight)];
}

function cohortSizes(freq: FrequencyData, group: Group, weight: number): number[] {
  if (group === 'a') return weight === 0 ? freq.M.v0 : freq.M.u;
  return (weight === 0 ? freq.M.v0l : freq.M.ul) ?? [];
}

/** Kann „identische Kursfenster nur einmal zählen“ gerechnet werden (Kalenderstarts vorhanden)? */
export function canDedupe(freq: FrequencyData | null | undefined, instruments: Instruments | null | undefined): boolean {
  return Boolean(freq?.starts && instruments?.calendar);
}

/** Häufigkeitsranking nach Auftrag: Platz-1-Vorkommen, dann Top 3, Top 10, ISIN. Jede Aktie zählt
 * je Rangliste höchstens einmal; Platz 1 zählt zugleich zu Top 3 und Top 10 (die Spalten werden nie
 * addiert). „Auswertbare Kombinationen“ = Ranglisten der Auswahl, in denen die Aktie einen Rang hat. */
export function groupFrequency(freq: FrequencyData, instruments: Instruments, options: GroupFrequencyOptions): GroupFrequencyResult {
  const weights = [...new Set(options.weights)].filter((w) => (WEIGHTS as readonly number[]).includes(w)).sort((a, b) => a - b);
  if (!weights.length) throw new Error('Keine Gewichtung gewählt');
  if (options.from < 1 || options.to > 90 || options.from > options.to) throw new Error('Ungültiger Zeitraum');
  const groups: Group[] = options.groups === 'ab' ? ['a', 'b'] : [options.groups];
  if (groups.includes('b') && !freq.occ.ul) throw new Error('Dieser Datenstand enthält Gruppe B noch nicht');
  const dedupe = options.dedupe && canDedupe(freq, instruments);
  const starts = freq.starts ?? {};
  const calendar = instruments.calendar ?? [];
  const liquid = instruments.turnover?.liquid ?? [];
  const startOf = (idx: number, h: number, fallback: number): number => {
    const code = calendar[idx];
    const value = code ? starts[code]?.[h - 1] : null;
    return value ?? fallback;
  };

  const entries = new Map<number, GroupFrequencyEntry>();
  const ensure = (idx: number): GroupFrequencyEntry => {
    let entry = entries.get(idx);
    if (!entry) {
      entry = { idx, a: emptyCounts(), b: emptyCounts() };
      entries.set(idx, entry);
    }
    return entry;
  };
  const valid: Record<Group, number> = { a: 0, b: 0 };
  const merged: Record<Group, number> = { a: 0, b: 0 };

  for (const group of groups) {
    // Treffer: je Aktie und Schlüssel höchstens einmal (Schlüssel = Zelle bzw. Gewichtung + tatsächliches Fenster)
    const seen = { n1: new Set<string>(), n3: new Set<string>(), n10: new Set<string>() };
    for (const weight of weights) {
      const sizes = cohortSizes(freq, group, weight);
      for (let h = options.from; h <= options.to; h += 1) if ((sizes[h - 1] ?? 0) > 0) valid[group] += 1;
      const occ = occurrencesOf(freq, group, weight);
      if (!occ) continue;
      for (let k = 0; k < occ.h.length; k += 1) {
        const h = occ.h[k];
        if (h < options.from || h > options.to) continue;
        const idx = occ.idx[k];
        const rank = occ.rank[k];
        const key = dedupe ? `${idx}:${weight}:${occ.start[k]}` : `${idx}:${weight}:${h}`;
        const counts = ensure(idx)[group];
        if (rank <= 1 && !seen.n1.has(key)) {
          seen.n1.add(key);
          counts.n1 += 1;
        }
        if (rank <= 3 && !seen.n3.has(key)) {
          seen.n3.add(key);
          counts.n3 += 1;
        }
        if (rank <= 10) {
          if (seen.n10.has(key)) merged[group] += 1;
          else {
            seen.n10.add(key);
            counts.n10 += 1;
          }
        }
      }
    }
  }

  // Auswertbare Kombinationen aus der Zugehörigkeit zu V bzw. U je Zeitraum (Gruppe B: nur Aktien aus L)
  const pure = weights.includes(0) ? 1 : 0;
  const trendWeights = weights.filter((w) => w !== 0).length;
  for (const entry of entries.values()) {
    const idx = entry.idx;
    const vBits = decodeBits(instruments.v_bits[idx]);
    const uBits = decodeBits(instruments.u_bits[idx]);
    const vKeys = new Set<number>();
    const uKeys = new Set<number>();
    let vCount = 0;
    let uCount = 0;
    for (let h = options.from; h <= options.to; h += 1) {
      if (vBits[h - 1]) {
        vCount += 1;
        vKeys.add(startOf(idx, h, -h));
      }
      if (uBits[h - 1]) {
        uCount += 1;
        uKeys.add(startOf(idx, h, -h));
      }
    }
    const available = dedupe ? pure * vKeys.size + trendWeights * uKeys.size : pure * vCount + trendWeights * uCount;
    for (const group of groups) {
      if (group === 'b' && !liquid[idx]) continue;
      entry[group].available = available;
    }
  }

  const listed = [...entries.values()].filter((e) => total(e, 'n10', options.groups) > 0);
  const isin = instruments.isin;
  listed.sort(
    (x, y) =>
      total(y, 'n1', options.groups) - total(x, 'n1', options.groups) ||
      total(y, 'n3', options.groups) - total(x, 'n3', options.groups) ||
      total(y, 'n10', options.groups) - total(x, 'n10', options.groups) ||
      (isin[x.idx] < isin[y.idx] ? -1 : isin[x.idx] > isin[y.idx] ? 1 : 0),
  );
  return {
    options: { ...options, weights, dedupe },
    entries: listed,
    validA: valid.a,
    validB: valid.b,
    theoretical: weights.length * (options.to - options.from + 1),
    mergedA: merged.a,
    mergedB: merged.b,
  };
}

/** Kurzer Text zu identischen Kursfenstern einer Matrixzelle. */
export function sameText(cell: MatrixCell): string {
  if (!cell.same.length) return '';
  const all = [cell.h, ...cell.same].sort((a, b) => a - b);
  return `gleiches Kursfenster wie ${all.filter((h) => h !== cell.h).join(', ')} ${all.length === 2 && all.filter((h) => h !== cell.h)[0] === 1 ? 'Tag' : 'Tage'}`;
}
