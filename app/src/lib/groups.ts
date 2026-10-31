/* Gruppenvergleich A/B über 1–90 Tage (ab 1.4, `gruppen-v1`; identische Kursfenster ab 1.5 `frequency-v2`).
 *
 * Gruppe A: alle Aktien mit ausreichender Datenqualität (0/100 auf V, übrige Gewichtungen auf U).
 * Gruppe B: dieselben Aktien, zusätzlich Ø Tagesumsatz ≥ 10 Mio. USD über 20 Sitzungen
 *           (0/100 auf V ∩ L, übrige auf U ∩ L, Perzentile innerhalb der Gruppe).
 * Beide Gruppen werden auf dem Server berechnet; die App liest Spitzenreiter (overview.bin) und
 * Top-10-Fundstellen (frequency.bin) und zählt hier nur. Identität immer über den Instrumentindex
 * (= ISIN), nie über Namen oder Ticker – Aktiengattungen und ADRs haben eigene ISINs.
 */

import { decodeBits, FIXED_WINDOWS, WEIGHTS } from './scoring';
import type { Cohort, FrequencyData, Group, Instruments, Occurrences, Overview, OverviewRow } from './types';

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

/** Vergleichsmenge einer Rangliste (natives Feld): 0/100 auf V bzw. V ∩ L, sonst U bzw. U ∩ L. */
export function cohortKey(group: Group, weight: number): Cohort {
  if (group === 'a') return weight === 0 ? 'v0' : 'u';
  return weight === 0 ? 'v0l' : 'ul';
}

/** Kleinster Zeitraum mit identischem Bestand aus ISIN und tatsächlichem Startdatum (frequency-v2),
 * sonst der Zeitraum selbst. Gleicher Wert = gleiche Rangliste. */
export function sameSetRep(source: { same_set?: FrequencyData['same_set'] } | null | undefined, group: Group, weight: number, h: number): number {
  const reps = source?.same_set?.[cohortKey(group, weight)];
  return reps?.[h - 1] ?? h;
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

/** Matrix Zeiträume × elf Gewichtungen einer Gruppe; markiert identische Kursfenster je Spalte.
 * Mit `overview.same_set` (ab 1.5) exakt: gleicher ISIN-/Startdatumsbestand; sonst Näherung über die
 * Spitzenaktie mit gleichem tatsächlichem Start. */
export function matrixRows(overview: Overview, group: Group, from: number, to: number): MatrixRow[] {
  const rows: MatrixRow[] = [];
  for (let h = from; h <= to; h += 1) {
    rows.push({
      h,
      cells: WEIGHTS.map((weight) => ({ h, weight, row: overviewRow(overview, group, weight, h) ?? { h, M: 0, empty: 'keine_vergleichbare_aktie' }, same: [] })),
    });
  }
  const exact = Boolean(overview.same_set);
  for (let k = 0; k < WEIGHTS.length; k += 1) {
    const byWindow = new Map<string, MatrixCell[]>();
    for (const row of rows) {
      const cell = row.cells[k];
      if (cell.row.idx === undefined || cell.row.start === undefined) continue;
      const key = exact ? `r${sameSetRep(overview, group, WEIGHTS[k], row.h)}` : `${cell.row.idx}:${cell.row.start}`;
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

function firstPlaceCounts(overview: Overview, from: number, to: number, weights: readonly number[] = WEIGHTS): Map<number, Marker> {
  const counts = new Map<number, Marker>();
  for (const group of ['a', 'b'] as Group[]) {
    if (group === 'b' && !hasGroups(overview)) continue;
    for (let h = from; h <= to; h += 1) {
      for (const weight of weights) {
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
  return counts;
}

const slotCache = new WeakMap<Overview, Map<number, number>>();

/** Feste Farbplätze für die acht häufigsten Spitzenaktien des ganzen Stands (1–90 Tage, alle
 * Gewichtungen, beide Gruppen; bei Gleichstand nach ISIN). Damit trägt dieselbe ISIN in jeder
 * Ansicht dieselbe Farbe – unabhängig vom dort gewählten Ausschnitt. */
export function markerSlots(overview: Overview, instruments: Instruments): Map<number, number> {
  const cached = slotCache.get(overview);
  if (cached) return cached;
  const recurring = [...firstPlaceCounts(overview, 1, 90).values()].filter((m) => m.count >= 2);
  recurring.sort((a, b) => b.count - a.count || (instruments.isin[a.idx] < instruments.isin[b.idx] ? -1 : 1));
  const slots = new Map<number, number>();
  recurring.slice(0, MARKER_SLOTS).forEach((m, k) => slots.set(m.idx, k));
  slotCache.set(overview, slots);
  return slots;
}

/** Kennzeichnung wiederkehrender Spitzenaktien – gleich in beiden Gruppen und allen Ansichten.
 * Die Anzahl zählt die Platz-1-Zellen beider Gruppen im gewählten Ausschnitt; die Farbe kommt aus
 * `markerSlots` (ganzer Stand), damit sie in jeder Ansicht gleich bleibt. */
export function markers(overview: Overview, instruments: Instruments, from: number, to: number, weights: readonly number[] = WEIGHTS): Map<number, Marker> {
  const counts = firstPlaceCounts(overview, from, to, weights);
  const slots = markerSlots(overview, instruments);
  for (const marker of counts.values()) marker.slot = slots.get(marker.idx) ?? null;
  return counts;
}

/* ------------------------------------------------------------------ Häufigkeitsranking */

export type GroupSelection = 'a' | 'b' | 'ab';

export type FrequencyOrder = 'n1' | 'n10';

export interface GroupFrequencyOptions {
  groups: GroupSelection;
  weights: number[];
  from: number;
  to: number;
  /** Identische Kursfenster (gleiche Gruppe und Gewichtung, gleicher ISIN-/Startdatumsbestand) nur einmal zählen */
  dedupe: boolean;
  /** n1 = „gewinnt am häufigsten“ (Platz 1, Top 3, Top 10, ISIN); n10 = „Meiste Top-10-Nennungen“ (Top 10, Top 3, Platz 1, ISIN) */
  order?: FrequencyOrder;
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

/** Kann „identische Kursfenster nur einmal zählen“ gerechnet werden? Ab 1.5 exakt über gleiche
 * ISIN-/Startdatumsbestände (`same_set`), in Ständen von 1.4 näherungsweise über Kalenderstarts. */
export function canDedupe(freq: FrequencyData | null | undefined, instruments: Instruments | null | undefined): boolean {
  return Boolean(freq?.same_set || (freq?.starts && instruments?.calendar));
}

/** Häufigkeitsranking nach Auftrag: Platz-1-Vorkommen, dann Top 3, Top 10, ISIN. Jede Aktie zählt
 * je Rangliste höchstens einmal; Platz 1 zählt zugleich zu Top 3 und Top 10 (die Spalten werden nie
 * addiert). „Auswertbare Kombinationen“ = Ranglisten der Auswahl, in denen die Aktie einen Rang hat. */
/** Reihenfolge des Häufigkeitsrankings: „gewinnt am häufigsten“ (Platz 1, Top 3, Top 10, ISIN) bzw. „meiste Top-10-Nennungen“
 * (Top 10, Top 3, Platz 1, ISIN). Eine Funktion für Tabelle und Standardlisten. */
export function sortiere(entries: GroupFrequencyEntry[], order: FrequencyOrder, groups: GroupSelection, isin: string[]): GroupFrequencyEntry[] {
  const keys: (keyof GroupCounts)[] = order === 'n10' ? ['n10', 'n3', 'n1'] : ['n1', 'n3', 'n10'];
  return [...entries].sort((x, y) => {
    for (const key of keys) {
      const diff = total(y, key, groups) - total(x, key, groups);
      if (diff) return diff;
    }
    return isin[x.idx] < isin[y.idx] ? -1 : isin[x.idx] > isin[y.idx] ? 1 : 0;
  });
}

/** Die beiden Standardlisten (Gesamtauftrag vom 31.10.2026, Abschnitt 5.3): die zehn Aktien mit den meisten Platz-1-Platzierungen
 * (nur Aktien mit mindestens einem ersten Platz) und die zehn mit den meisten Top-10-Nennungen – aus derselben Zählung. */
export function spitzenlisten(result: GroupFrequencyResult, isin: string[], n = 10): { platz1: GroupFrequencyEntry[]; top10: GroupFrequencyEntry[] } {
  const groups = result.options.groups;
  return {
    platz1: sortiere(result.entries.filter((e) => total(e, 'n1', groups) > 0), 'n1', groups, isin).slice(0, n),
    top10: sortiere(result.entries, 'n10', groups, isin).slice(0, n),
  };
}

export function groupFrequency(freq: FrequencyData, instruments: Instruments, options: GroupFrequencyOptions): GroupFrequencyResult {
  const weights = [...new Set(options.weights)].filter((w) => (WEIGHTS as readonly number[]).includes(w)).sort((a, b) => a - b);
  if (!weights.length) throw new Error('Keine Gewichtung gewählt');
  if (options.from < 1 || options.to > 90 || options.from > options.to) throw new Error('Ungültiger Zeitraum');
  const groups: Group[] = options.groups === 'ab' ? ['a', 'b'] : [options.groups];
  if (groups.includes('b') && !freq.occ.ul) throw new Error('Dieser Datenstand enthält Gruppe B noch nicht');
  const dedupe = options.dedupe && canDedupe(freq, instruments);
  const exact = Boolean(freq.same_set);
  const starts = freq.starts ?? {};
  const calendar = instruments.calendar ?? [];
  const liquid = instruments.turnover?.liquid ?? [];
  const startOf = (idx: number, h: number, fallback: number): number => {
    const code = calendar[idx];
    const value = code ? starts[code]?.[h - 1] : null;
    return value ?? fallback;
  };
  // Schlüssel eines Kursfensters für „nur einmal zählen“: exakt der Vertreter gleicher Bestände
  const windowKey = (group: Group, weight: number, h: number, idx: number, start: number): string =>
    exact ? `r${sameSetRep(freq, group, weight, h)}` : `s${start ?? startOf(idx, h, -h)}`;

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
      const computed = new Set<number>();
      for (let h = options.from; h <= options.to; h += 1) {
        if ((sizes[h - 1] ?? 0) <= 0) continue;
        if (dedupe && exact) computed.add(sameSetRep(freq, group, weight, h));
        else valid[group] += 1;
      }
      valid[group] += computed.size;
      const occ = occurrencesOf(freq, group, weight);
      if (!occ) continue;
      for (let k = 0; k < occ.h.length; k += 1) {
        const h = occ.h[k];
        if (h < options.from || h > options.to) continue;
        const idx = occ.idx[k];
        const rank = occ.rank[k];
        const key = dedupe ? `${idx}:${weight}:${windowKey(group, weight, h, idx, occ.start[k])}` : `${idx}:${weight}:${h}`;
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

  // Zugelassene Kombinationen aus der Zugehörigkeit zu V bzw. U je Zeitraum (Gruppe B: nur Aktien aus L)
  for (const entry of entries.values()) {
    const idx = entry.idx;
    const vBits = decodeBits(instruments.v_bits[idx]);
    const uBits = decodeBits(instruments.u_bits[idx]);
    for (const group of groups) {
      if (group === 'b' && !liquid[idx]) continue;
      let available = 0;
      for (const weight of weights) {
        const bits = weight === 0 ? vBits : uBits;
        const keys = new Set<string>();
        for (let h = options.from; h <= options.to; h += 1) {
          if (!bits[h - 1]) continue;
          if (dedupe) keys.add(windowKey(group, weight, h, idx, startOf(idx, h, -h)));
          else available += 1;
        }
        available += keys.size;
      }
      entry[group].available = available;
    }
  }

  const order: FrequencyOrder = options.order === 'n10' ? 'n10' : 'n1';
  const listed = sortiere(
    [...entries.values()].filter((e) => total(e, 'n10', options.groups) > 0),
    order,
    options.groups,
    instruments.isin,
  );
  return {
    options: { ...options, weights, dedupe, order },
    entries: listed,
    validA: valid.a,
    validB: valid.b,
    theoretical: weights.length * (options.to - options.from + 1),
    mergedA: merged.a,
    mergedB: merged.b,
  };
}

/* ------------------------------------------------------- Sieger nach Zeitraum (zehn Fenster) */

export interface TenWindowRow {
  h: number;
  a: OverviewRow;
  b: OverviewRow | null;
}

/** Spitzenreiter der zehn festen Zeiträume 7 … 90 Tage für eine Gewichtung, Gruppe A und B. */
export function tenWindowRows(overview: Overview, weight: number): TenWindowRow[] {
  const withB = hasGroups(overview);
  return FIXED_WINDOWS.map((h) => ({
    h,
    a: overviewRow(overview, 'a', weight, h) ?? { h, M: 0, empty: 'keine_vergleichbare_aktie' },
    b: withB ? overviewRow(overview, 'b', weight, h) ?? { h, M: 0, empty: 'keine_aktie_mit_umsatz' } : null,
  }));
}

export interface TenWindowCount {
  idx: number;
  a: number;
  b: number;
  windows: number[];
}

/** Zählung nur über diese zehn Zeiträume (Platz 1 je Gruppe) – getrennt von der Zählung über 1–90 Tage. */
export function tenWindowCounts(rows: TenWindowRow[], instruments: Instruments): TenWindowCount[] {
  const map = new Map<number, TenWindowCount>();
  for (const row of rows) {
    for (const [group, cell] of [['a', row.a], ['b', row.b]] as const) {
      if (!cell || cell.idx === undefined) continue;
      const entry = map.get(cell.idx) ?? { idx: cell.idx, a: 0, b: 0, windows: [] };
      entry[group] += 1;
      if (!entry.windows.includes(row.h)) entry.windows.push(row.h);
      map.set(cell.idx, entry);
    }
  }
  return [...map.values()]
    .filter((e) => e.a + e.b >= 2)
    .sort((x, y) => y.a + y.b - (x.a + x.b) || y.a - x.a || (instruments.isin[x.idx] < instruments.isin[y.idx] ? -1 : 1));
}

/** Kurzer Text zu identischen Kursfenstern einer Matrixzelle. */
export function sameText(cell: MatrixCell): string {
  if (!cell.same.length) return '';
  const all = [cell.h, ...cell.same].sort((a, b) => a - b);
  return `gleiches Kursfenster wie ${all.filter((h) => h !== cell.h).join(', ')} ${all.length === 2 && all.filter((h) => h !== cell.h)[0] === 1 ? 'Tag' : 'Tage'}`;
}
