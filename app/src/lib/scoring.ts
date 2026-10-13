/* Perzentile und Scores aus veröffentlichten, exakten Rangdaten.
 *
 * Bitgleich zur Python-Berechnung: gleiche IEEE-754-Operationsfolge.
 *   P = 100 · (doppelterRang/2 − 1) / (M − 1); M = 1 → 100
 *   Score(w) = (w/100)·G + (1 − w/100)·R; w = 0 → R; w = 100 → G
 * Die Reihenfolge der Ranglisten wird nie hier berechnet, sondern aus den
 * veröffentlichten Ranglisten übernommen.
 */

import type { Cohort, Policy, WindowData } from './types';

export const WEIGHTS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100] as const;
export const QUICK_WINDOWS = [1, 3, 7, 14, 21, 30, 45, 60, 90] as const;
export const LEGACY_ALIASES: Record<string, number> = { return: 0, mix40: 40, mix50: 50, mix60: 60, consistency: 100 };

export function isValidWindow(h: unknown): h is number {
  return typeof h === 'number' && Number.isInteger(h) && h >= 1 && h <= 90;
}

export function parseWindow(text: string | null | undefined, fallback = 30): number {
  if (text === null || text === undefined) return fallback;
  if (!/^\d{1,2}$/.test(text.trim())) return fallback;
  const value = Number(text);
  return isValidWindow(value) ? value : fallback;
}

export function parseWeight(text: string | null | undefined, fallback = 60): number {
  if (text === null || text === undefined) return fallback;
  const lowered = text.trim().toLowerCase();
  if (lowered in LEGACY_ALIASES) return LEGACY_ALIASES[lowered];
  if (!/^\d{1,3}$/.test(lowered)) return fallback;
  const value = Number(lowered);
  return (WEIGHTS as readonly number[]).includes(value) ? value : fallback;
}

export function parsePolicy(text: string | null | undefined): Policy {
  return text === 'common_trend' ? 'common_trend' : 'native';
}

export function cohortFor(policy: Policy, weight: number): Cohort {
  return policy === 'native' && weight === 0 ? 'v0' : 'u';
}

export function pctFromDoubled(doubled: number, m: number): number {
  if (m === 1) return 100;
  return (100 * (doubled / 2 - 1)) / (m - 1);
}

export function weightedScore(weight: number, g: number, r: number): number {
  if (weight === 0) return r;
  if (weight === 100) return g;
  return (weight / 100) * g + (1 - weight / 100) * r;
}

export interface RankedEntry {
  rank: number;
  idx: number;
  member: number; // Position in WindowData.m
  r: number;
  r2: number | null;
  score: number;
  g: number | null;
  rPct: number;
  tie: boolean;
}

export function memberIndex(win: WindowData): Map<number, number> {
  const map = new Map<number, number>();
  win.m.idx.forEach((idx, pos) => map.set(idx, pos));
  return map;
}

export function orderFor(win: WindowData, policy: Policy, weight: number): number[] {
  return cohortFor(policy, weight) === 'v0' ? win.orders.v0 : win.orders.u[String(weight)] ?? [];
}

export function tiesFor(win: WindowData, policy: Policy, weight: number): Set<number> {
  const list = cohortFor(policy, weight) === 'v0' ? win.ties.v0 : win.ties.u[String(weight)] ?? [];
  return new Set(list);
}

export function cohortSize(win: WindowData, policy: Policy, weight: number): number {
  return cohortFor(policy, weight) === 'v0' ? win.counts.V : win.counts.U;
}

/** Einträge einer veröffentlichten Rangliste (Platz offset+1 … offset+limit). */
export function rankedEntries(win: WindowData, policy: Policy, weight: number, offset = 0, limit = 50): RankedEntry[] {
  const order = orderFor(win, policy, weight);
  const positions = memberIndex(win);
  const ties = tiesFor(win, policy, weight);
  const cohort = cohortFor(policy, weight);
  const out: RankedEntry[] = [];
  for (let k = offset; k < Math.min(order.length, offset + limit); k += 1) {
    const idx = order[k];
    const member = positions.get(idx);
    if (member === undefined) continue;
    const entry = entryScores(win, member, cohort, weight);
    out.push({ rank: k + 1, idx, member, tie: ties.has(k), ...entry });
  }
  return out;
}

export function entryScores(win: WindowData, member: number, cohort: Cohort, weight: number): { r: number; r2: number | null; score: number; g: number | null; rPct: number } {
  const m = win.m;
  const r = m.r[member];
  const r2 = m.r2[member];
  if (cohort === 'v0') {
    const rPct = pctFromDoubled(m.a_rv[member], win.counts.V);
    return { r, r2, score: rPct, g: null, rPct };
  }
  const aG = m.a_gu[member];
  const aR = m.a_ru[member];
  if (aG === null || aR === null) throw new Error('Instrument ist nicht in der Vergleichsmenge U');
  const g = pctFromDoubled(aG, win.counts.U);
  const rPct = pctFromDoubled(aR, win.counts.U);
  return { r, r2, score: weightedScore(weight, g, rPct), g, rPct };
}

/** Rang eines Instruments in einer veröffentlichten Rangliste (oder null). */
export function rankOf(win: WindowData, policy: Policy, weight: number, idx: number): number | null {
  const order = orderFor(win, policy, weight);
  const position = order.indexOf(idx);
  return position >= 0 ? position + 1 : null;
}

/** Spalten der Rangmatrix vor Version 1.1 (ohne Ranking 2). */
export const LEGACY_RANK_COLUMNS = ['v0', ...WEIGHTS.map((w) => `u${w}`)];

/** Rangmatrix aus der Kursreihendatei: 90 Fenster × Spalten laut ``rank_columns``
 * (v0, u0 … u100, ab 1.1 zusätzlich v0l = Ranking 2); 0 = kein Rang. */
export function decodeRanks(b64: string): Uint16Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  const out = new Uint16Array(bytes.length / 2);
  for (let i = 0; i < out.length; i += 1) out[i] = bytes[2 * i] | (bytes[2 * i + 1] << 8);
  return out;
}

export function rankFromMatrix(matrix: Uint16Array, h: number, policy: Policy, weight: number, columns: string[] = LEGACY_RANK_COLUMNS): number | null {
  return rankInColumn(matrix, h, cohortFor(policy, weight) === 'v0' ? 'v0' : `u${weight}`, columns);
}

/** Rang in einer benannten Spalte (z. B. „v0l“ für Ranking 2); null, wenn es die Spalte nicht gibt. */
export function rankInColumn(matrix: Uint16Array, h: number, column: string, columns: string[] = LEGACY_RANK_COLUMNS): number | null {
  const k = columns.indexOf(column);
  if (k < 0 || h < 1 || h > 90) return null;
  const value = matrix[(h - 1) * columns.length + k];
  return value > 0 ? value : null;
}

/** Bitmaske 90 Fenster (little-endian) → Zugehörigkeit je Fenster. */
export function decodeBits(b64: string): boolean[] {
  const binary = atob(b64);
  const out: boolean[] = [];
  for (let h = 0; h < 90; h += 1) {
    const byte = binary.charCodeAt(h >> 3) || 0;
    out.push(((byte >> (h & 7)) & 1) === 1);
  }
  return out;
}

export function decodeStatus(b64: string): Uint8Array {
  const binary = atob(b64);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
  return out;
}
