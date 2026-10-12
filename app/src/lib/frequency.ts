/* Häufigste Aktien (Abschnitt 34) – Zählung aus veröffentlichten Fundstellen eines Snapshots.
 * Identische Regeln wie traktien/analytics/frequency.py (gegenseitig getestet). */

import { WEIGHTS, cohortFor, decodeBits } from './scoring';
import type { FrequencyData, Instruments, Policy } from './types';

export type TopK = 1 | 3 | 10;
export type SortMode = 'occurrences' | 'distinct_windows';

export interface Occurrence {
  h: number;
  weight: number;
  rank: number;
  score: number;
  r: number;
  start: number;
  end: number;
  cohortSize: number;
  smallField: boolean;
}

export interface FrequencyEntry {
  idx: number;
  n1: number;
  n3: number;
  n10: number;
  available: number;
  distinctWindows: number;
  distinctWeights: number;
  distinctEffective: number;
  hitsByWeight: Record<number, number>;
  occurrences: Occurrence[];
}

export interface FrequencyOptions {
  policy: Policy;
  weights: number[];
  from: number;
  to: number;
  topK: TopK;
  sort: SortMode;
}

export interface FrequencyResult {
  options: FrequencyOptions;
  mode: 'single' | 'all';
  theoreticalCells: number;
  validCells: number;
  emptyCells: number;
  entries: FrequencyEntry[];
}

export function nK(entry: FrequencyEntry, k: TopK): number {
  return k === 1 ? entry.n1 : k === 3 ? entry.n3 : entry.n10;
}

function sortKey(e: FrequencyEntry, k: TopK, mode: 'single' | 'all', sort: SortMode): number[] {
  if (sort === 'distinct_windows') return [-e.distinctWindows, -nK(e, k), -e.n1, e.idx];
  if (mode === 'single') {
    if (k === 10) return [-e.n10, -e.n3, -e.n1, e.idx];
    if (k === 3) return [-e.n3, -e.n1, -e.n10, e.idx];
    return [-e.n1, -e.n3, -e.n10, e.idx];
  }
  if (k === 10) return [-e.n10, -e.distinctWindows, -e.n3, -e.n1, e.idx];
  if (k === 3) return [-e.n3, -e.distinctWindows, -e.n1, -e.n10, e.idx];
  return [-e.n1, -e.distinctWindows, -e.n3, -e.n10, e.idx];
}

function compareKeys(a: number[], b: number[]): number {
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return 0;
}

/** Anzahl der Fenster h im Bereich, in denen das Instrument zu V bzw. U gehört. */
export function membershipCounts(instruments: Instruments, from: number, to: number): { v: Int32Array; u: Int32Array } {
  const v = new Int32Array(instruments.count);
  const u = new Int32Array(instruments.count);
  for (let i = 0; i < instruments.count; i += 1) {
    const vBits = decodeBits(instruments.v_bits[i]);
    const uBits = decodeBits(instruments.u_bits[i]);
    for (let h = from; h <= to; h += 1) {
      if (vBits[h - 1]) v[i] += 1;
      if (uBits[h - 1]) u[i] += 1;
    }
  }
  return { v, u };
}

export function aggregateFrequency(
  freq: FrequencyData,
  instruments: Instruments,
  options: FrequencyOptions,
  membership?: { v: Int32Array; u: Int32Array },
): FrequencyResult {
  const weights = [...new Set(options.weights)].sort((a, b) => a - b);
  if (!weights.length || weights.some((w) => !(WEIGHTS as readonly number[]).includes(w))) throw new Error('Ungültige Gewichtungen');
  if (options.from < 1 || options.to > 90 || options.from > options.to) throw new Error('Ungültiger Zeitraum');
  const mode = weights.length === 1 ? 'single' : 'all';
  const counts = membership ?? membershipCounts(instruments, options.from, options.to);
  const stats = new Map<number, FrequencyEntry>();
  const windowsHit = new Map<number, Set<number>>();
  const weightsHit = new Map<number, Set<number>>();
  const effective = new Map<number, Set<string>>();
  let validCells = 0;

  const ensure = (idx: number): FrequencyEntry => {
    let entry = stats.get(idx);
    if (!entry) {
      entry = { idx, n1: 0, n3: 0, n10: 0, available: 0, distinctWindows: 0, distinctWeights: 0, distinctEffective: 0, hitsByWeight: {}, occurrences: [] };
      stats.set(idx, entry);
    }
    return entry;
  };

  // Gültige Zellen E und Verfügbarkeit A_i
  let vCells = 0;
  let uCellsPerWeight = 0;
  for (const w of weights) {
    const cohort = cohortFor(options.policy, w);
    for (let h = options.from; h <= options.to; h += 1) {
      const m = cohort === 'v0' ? freq.M.v0[h - 1] : freq.M.u[h - 1];
      if (m > 0) validCells += 1;
    }
    if (cohort === 'v0') vCells += 1;
    else uCellsPerWeight += 1;
  }
  for (let i = 0; i < instruments.count; i += 1) {
    const available = vCells * counts.v[i] + uCellsPerWeight * counts.u[i];
    if (available > 0) ensure(i).available = available;
  }

  // Treffer aus Fundstellen
  for (const w of weights) {
    const cohort = cohortFor(options.policy, w);
    const occ = cohort === 'v0' ? freq.occ.v0 : freq.occ.u[String(w)];
    if (!occ) continue;
    for (let k = 0; k < occ.h.length; k += 1) {
      const h = occ.h[k];
      if (h < options.from || h > options.to) continue;
      const rank = occ.rank[k];
      const idx = occ.idx[k];
      const entry = ensure(idx);
      if (rank <= 1) entry.n1 += 1;
      if (rank <= 3) entry.n3 += 1;
      if (rank <= 10) entry.n10 += 1;
      if (rank <= options.topK) {
        const size = cohort === 'v0' ? freq.M.v0[h - 1] : freq.M.u[h - 1];
        if (!windowsHit.has(idx)) windowsHit.set(idx, new Set());
        if (!weightsHit.has(idx)) weightsHit.set(idx, new Set());
        if (!effective.has(idx)) effective.set(idx, new Set());
        windowsHit.get(idx)!.add(h);
        weightsHit.get(idx)!.add(w);
        effective.get(idx)!.add(`${occ.start[k]}:${freq.cutoff_day}`);
        entry.hitsByWeight[w] = (entry.hitsByWeight[w] ?? 0) + 1;
        entry.occurrences.push({
          h,
          weight: w,
          rank,
          score: occ.score[k],
          r: occ.r[k],
          start: occ.start[k],
          end: freq.cutoff_day,
          cohortSize: size,
          smallField: size < options.topK,
        });
      }
    }
  }

  const listed: FrequencyEntry[] = [];
  for (const entry of stats.values()) {
    entry.distinctWindows = windowsHit.get(entry.idx)?.size ?? 0;
    entry.distinctWeights = weightsHit.get(entry.idx)?.size ?? 0;
    entry.distinctEffective = effective.get(entry.idx)?.size ?? 0;
    if (nK(entry, options.topK) > 0) listed.push(entry);
  }
  listed.sort((a, b) => compareKeys(sortKey(a, options.topK, mode, options.sort), sortKey(b, options.topK, mode, options.sort)));
  const theoretical = weights.length * (options.to - options.from + 1);
  return {
    options: { ...options, weights },
    mode,
    theoreticalCells: theoretical,
    validCells,
    emptyCells: theoretical - validCells,
    entries: listed,
  };
}
