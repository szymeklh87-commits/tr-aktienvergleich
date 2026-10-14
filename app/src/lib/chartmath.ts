/* Aufbereitung echter Tageskurse für Diagramme. Keine Interpolation, keine erfundenen Werte. */

import type { SeriesData } from './types';

export interface Point {
  day: number;
  close: number;
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  closeRaw: number | null;
}

export type ValueMode = 'absolut' | 'index' | 'prozent';

export function points(series: SeriesData): Point[] {
  return series.d.map((day, i) => ({
    day,
    close: series.c[i],
    open: series.o?.[i] ?? null,
    high: series.h?.[i] ?? null,
    low: series.l?.[i] ?? null,
    volume: series.v[i] ?? null,
    closeRaw: series.c_raw?.[i] ?? null,
  }));
}

/** Startsitzung des Fensters h laut Rechenkern (null, wenn nicht auflösbar). */
export function windowStart(series: SeriesData, h: number): number | null {
  return series.window_start[h - 1] ?? null;
}

/** Punkte eines Kalenderfensters: ab der veröffentlichten Startsitzung bis zum Stichtag. */
export function windowPoints(series: SeriesData, h: number, cutoffDay: number): { pts: Point[]; start: number | null; fallback: boolean } {
  const all = points(series);
  const start = windowStart(series, h);
  if (start !== null) return { pts: all.filter((p) => p.day >= start && p.day <= cutoffDay), start, fallback: false };
  // Ohne auflösbare Startsitzung: verfügbare Historie ab Ziel-Startdatum (als solche gekennzeichnet)
  const target = cutoffDay - h;
  const pts = all.filter((p) => p.day >= target && p.day <= cutoffDay);
  return { pts, start: pts.length ? pts[0].day : null, fallback: true };
}

/** Volumen je Sitzung im Verhältnis zum Ø der ``n`` Sitzungen davor (ab 1.11): Tag → Faktor (2 = doppelt so hoch).
 * Nur Sitzungen mit genug Vorlauf und gemeldetem Volumen; fehlende Volumina zählen nicht zum Durchschnitt. */
export function relativeVolumes(pts: Point[], n = 20): Map<number, number> {
  const out = new Map<number, number>();
  const history: number[] = [];
  let sum = 0;
  for (const p of pts) {
    const v = p.volume;
    const known = v !== null && Number.isFinite(v) && v >= 0;
    if (known && history.length >= n && sum > 0) out.set(p.day, v / (sum / n));
    if (known) {
      history.push(v);
      sum += v;
      if (history.length > n) sum -= history[history.length - n - 1];
    }
  }
  return out;
}

/** Lücken = erwartete Sitzungen ohne gültigen Kurs innerhalb eines Bereichs. */
export function gapsWithin(series: SeriesData, from: number, to: number): number[] {
  return series.gaps.filter((d) => d >= from && d <= to);
}

/** Segmente für die Linie: an fehlenden erwarteten Sitzungen wird unterbrochen. */
export function segments(pts: Point[], gaps: number[]): Point[][] {
  if (!pts.length) return [];
  const gapSet = gaps.slice().sort((a, b) => a - b);
  const out: Point[][] = [[pts[0]]];
  let g = 0;
  for (let i = 1; i < pts.length; i += 1) {
    const prev = pts[i - 1].day;
    const cur = pts[i].day;
    while (g < gapSet.length && gapSet[g] <= prev) g += 1;
    const hasGap = g < gapSet.length && gapSet[g] > prev && gapSet[g] < cur;
    if (hasGap) out.push([pts[i]]);
    else out[out.length - 1].push(pts[i]);
  }
  return out;
}

export function transform(value: number, base: number, mode: ValueMode): number {
  if (mode === 'absolut') return value;
  if (mode === 'index') return (100 * value) / base;
  return 100 * (value / base - 1);
}

/** OLS auf dem Preis mit t = 0 … N−1 – nur zur Darstellung der Anpassungsgeraden.
 * Wird gegen die veröffentlichte relative Steigung geprüft; bei Abweichung wird keine Gerade gezeigt. */
export function fitLine(pts: Point[]): { m: number; b: number; slopePct: number } | null {
  const n = pts.length;
  if (n < 2) return null;
  const tMean = (n - 1) / 2;
  let pMean = 0;
  for (const p of pts) pMean += p.close;
  pMean /= n;
  let stt = 0;
  let stp = 0;
  pts.forEach((p, i) => {
    stt += (i - tMean) * (i - tMean);
    stp += (i - tMean) * (p.close - pMean);
  });
  const m = stp / stt;
  return { m, b: pMean - m * tMean, slopePct: (100 * m) / pMean };
}

export function fitMatches(fit: { slopePct: number } | null, published: number | null | undefined): boolean {
  if (!fit || published === null || published === undefined) return false;
  const tolerance = Math.max(1e-9, Math.abs(published) * 1e-5);
  return Math.abs(fit.slopePct - published) <= tolerance;
}

export interface CommonBase {
  day: number | null;
  shifted: boolean;
  reason: string | null;
}

/** Gemeinsamer Basis-Sitzungstag mehrerer Reihen ohne Auffüllen.
 * Bevorzugt die letzte gemeinsame Sitzung am oder vor dem Ziel-Startdatum (≤ 7 Tage),
 * sonst die erste gemeinsame Sitzung danach (verschobener Vergleichsbeginn). */
export function commonBase(seriesList: SeriesData[], h: number, cutoffDay: number): CommonBase {
  if (!seriesList.length) return { day: null, shifted: false, reason: 'Keine Aktie ausgewählt' };
  const target = cutoffDay - h;
  let common = null as Set<number> | null;
  for (const s of seriesList) {
    const days = new Set(s.d.filter((d) => d >= target - 7 && d <= cutoffDay));
    common = common === null ? days : new Set([...common].filter((d) => days.has(d)));
  }
  const sorted = [...(common ?? new Set<number>())].sort((a, b) => a - b);
  const before = sorted.filter((d) => d <= target);
  if (before.length) return { day: before[before.length - 1], shifted: false, reason: null };
  const after = sorted.filter((d) => d > target && d < cutoffDay);
  if (after.length) return { day: after[0], shifted: true, reason: 'gemeinsame Datenverfügbarkeit' };
  return { day: null, shifted: false, reason: 'Kein gemeinsamer Basiszeitpunkt mit echten Kursen aller ausgewählten Aktien' };
}

export function valueAt(series: SeriesData, day: number): number | null {
  const i = series.d.indexOf(day);
  return i >= 0 ? series.c[i] : null;
}

export function nearestIndex(days: number[], target: number): number {
  let lo = 0;
  let hi = days.length - 1;
  if (hi < 0) return -1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (days[mid] < target) lo = mid + 1;
    else hi = mid;
  }
  if (lo > 0 && Math.abs(days[lo - 1] - target) <= Math.abs(days[lo] - target)) return lo - 1;
  return lo;
}
