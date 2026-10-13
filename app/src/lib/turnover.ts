/* Ø Tagesumsatz je Aktie und die zwei Rendite-Ranglisten (Erweiterung 1.1).
 *
 * Ranking 1 „Höchste Kursrendite“: alle Aktien mit veröffentlichter Kursrendite (Menge V),
 * sortiert nur nach Kursrendite (0 % Gleichmäßigkeit / 100 % Kursrendite).
 * Ranking 2 „… – Ø Tagesumsatz mindestens 10 Mio. USD“: dieselbe Liste, nur Aktien, deren
 * Ø Tagesumsatz der letzten 20 Sitzungen bestimmt ist und die Schwelle erreicht. Der Umsatz ist
 * ein Aufnahmefilter, kein Sortierkriterium. Beide Listen kommen fertig vom Server (orders.v0 /
 * orders.v0l); die App sortiert nichts selbst.
 */

import * as f from './format';
import type { Instruments, Manifest, Overview, WindowData, WinnerRow } from './types';

export type ReturnList = 'alle' | 'umsatz';

export const DEFAULT_THRESHOLD_USD = 10_000_000;
export const DEFAULT_VERY_LOW_USD = 1_000_000;

export interface TurnoverInfo {
  status: string;
  usd: number | null;
  local: number | null;
  currency: string | null;
  sessions: number;
  withData: number;
  positive: number;
  first: number | null;
  last: number | null;
  fxFirst: number | null;
  fxLast: number | null;
  liquid: boolean;
}

export function parseReturnList(text: string | null | undefined): ReturnList {
  return text === 'umsatz' ? 'umsatz' : 'alle';
}

export function thresholdUsd(manifest: Manifest | null): number {
  return manifest?.turnover?.schwelle_usd ?? DEFAULT_THRESHOLD_USD;
}

export function veryLowUsd(manifest: Manifest | null): number {
  return manifest?.turnover?.sehr_niedrig_usd ?? DEFAULT_VERY_LOW_USD;
}

/** „10 Mio. USD“ aus der Schwelle des Datenstands. */
export function thresholdLabel(manifest: Manifest | null): string {
  return f.money(thresholdUsd(manifest), 'USD').replace(',0 Mio.', ' Mio.');
}

export function listTitle(list: ReturnList, manifest: Manifest | null): string {
  return list === 'alle' ? 'Höchste Kursrendite' : `Höchste Kursrendite – Ø Tagesumsatz mindestens ${thresholdLabel(manifest)}`;
}

export function hasTurnover(instruments: Instruments | null): boolean {
  return Boolean(instruments?.turnover && instruments.turnover.status.length === instruments.count);
}

export function turnoverOf(instruments: Instruments, idx: number): TurnoverInfo | null {
  const t = instruments.turnover;
  if (!t || idx < 0 || idx >= t.status.length) return null;
  return {
    status: t.status[idx],
    usd: t.usd[idx],
    local: t.local[idx],
    currency: t.currency[idx],
    sessions: t.sessions[idx],
    withData: t.with_data[idx],
    positive: t.positive[idx],
    first: t.first[idx],
    last: t.last[idx],
    fxFirst: t.fx_first[idx],
    fxLast: t.fx_last[idx],
    liquid: Boolean(t.liquid[idx]),
  };
}

export function isVeryLow(info: TurnoverInfo | null, manifest: Manifest | null): boolean {
  return Boolean(info && info.status === 'ok' && info.usd !== null && info.usd < veryLowUsd(manifest));
}

/** Kurzer Text für Listen: „Ø 12,4 Mio. USD je Sitzung“ bzw. der Grund, warum kein Wert vorliegt. */
export function turnoverShort(info: TurnoverInfo | null, manifest: Manifest | null): string {
  if (!info) return 'Ø Umsatz: keine Angabe in diesem Datenstand';
  if (info.status === 'ok' && info.usd !== null) return `Ø ${f.money(info.usd, 'USD')} je Sitzung`;
  const text = manifest?.codes.turnover_status?.[info.status]?.kurz ?? info.status;
  return `Ø Umsatz nicht bestimmbar: ${text}`;
}

/** Berechnungsbasis kompakt: „20 Sitzungen 15.09.–12.10.2026, alle mit Umsatz; Ø 8,4 Mio. AUD, EZB-Kurs bis 12.10.2026“. */
export function turnoverBasis(info: TurnoverInfo | null, manifest: Manifest | null): string {
  if (!info) return '';
  const parts: string[] = [];
  if (info.sessions > 0 && info.first !== null && info.last !== null) {
    let text = `${info.sessions} Sitzungen ${f.dayShort(info.first)}–${f.day(info.last)}`;
    if (info.withData > 0) {
      text += info.positive === info.sessions ? ', alle mit Umsatz' : `, ${info.positive} mit Umsatz`;
      if (info.withData < info.sessions) text += `, ${info.sessions - info.withData} ohne Daten`;
    }
    parts.push(text);
  }
  if (info.status === 'ok' && info.local !== null && info.currency && info.currency !== 'USD') {
    const source = manifest?.turnover?.wechselkurse.quelle?.startsWith('EZB') ? 'EZB-Kurs' : 'Referenzkurs';
    const when = info.fxLast !== null ? ` bis ${f.day(info.fxLast)}` : '';
    parts.push(`Ø ${f.money(info.local, info.currency)}, ${source}${when}`);
  }
  if (info.status !== 'ok') {
    const text = manifest?.codes.turnover_status?.[info.status]?.text;
    if (text) parts.push(text);
  }
  return parts.join('; ');
}

/** Rangfolge der gewählten Liste aus einer Fensterdatei (vom Server sortiert). */
export function listOrder(win: WindowData, list: ReturnList): number[] {
  return list === 'alle' ? win.orders.v0 : win.orders.v0l ?? [];
}

export function listTies(win: WindowData, list: ReturnList): Set<number> {
  return new Set(list === 'alle' ? win.ties.v0 : win.ties.v0l ?? []);
}

export function listSize(win: WindowData, list: ReturnList): number {
  return list === 'alle' ? win.counts.V : win.counts.L ?? (win.orders.v0l ?? []).length;
}

export function winnersOf(overview: Overview, list: ReturnList): WinnerRow[] {
  return list === 'alle' ? overview.winners : overview.winners_l ?? [];
}

export function countsOf(overview: Overview, list: ReturnList): number[] {
  return list === 'alle' ? overview.counts.V : overview.counts.L ?? [];
}

export interface ListEntry {
  rank: number;
  idx: number;
  r: number;
  start: number;
  end: number;
  p0: number | null;
  p1: number | null;
  wf: number;
  tie: boolean;
}

/** Plätze ``offset`` … ``offset + count − 1`` einer Rendite-Rangliste mit allen Anzeigewerten. */
export function listEntries(win: WindowData, list: ReturnList, offset: number, count: number): ListEntry[] {
  const order = listOrder(win, list);
  const ties = listTies(win, list);
  const position = new Map<number, number>();
  win.m.idx.forEach((idx, pos) => position.set(idx, pos));
  const out: ListEntry[] = [];
  for (let k = offset; k < Math.min(order.length, offset + count); k += 1) {
    const idx = order[k];
    const pos = position.get(idx);
    if (pos === undefined) continue;
    out.push({
      rank: k + 1,
      idx,
      r: win.m.r[pos],
      start: win.m.start[pos],
      end: win.cutoff_day,
      p0: win.m.p0?.[pos] ?? null,
      p1: win.m.p1?.[pos] ?? null,
      wf: win.m.wf[pos],
      tie: ties.has(k),
    });
  }
  return out;
}
