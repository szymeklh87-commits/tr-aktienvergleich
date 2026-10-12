/* Anzeigehilfen für Instrumente eines Snapshots. */

import { TYPE_LABELS } from './codes';
import { normalize } from './search';
import type { Instruments } from './types';

/** Vollständiger Name (nie abgeschnitten); fällt auf den TR-Namen bzw. die ISIN zurück. */
export function instName(inst: Instruments, i: number): string {
  return inst.name[i] || inst.tr_name[i] || inst.isin[i];
}

/** TR-Listenname, falls er sichtbar vom Namen der Identitätsquelle abweicht. */
export function trNameIfDifferent(inst: Instruments, i: number): string | null {
  const tr = inst.tr_name[i];
  if (!tr) return null;
  return normalize(tr) === normalize(instName(inst, i)) ? null : tr;
}

/** Einheit der Notierung, z. B. „EUR“ oder „GBp“ (Pence). */
export function unitOf(inst: Instruments, i: number): string | null {
  return inst.price_unit[i] ?? inst.currency[i] ?? null;
}

export function exchangeOf(inst: Instruments, i: number): string | null {
  return inst.exchange[i] ?? inst.exchange_key[i] ?? null;
}

export function typeLabel(inst: Instruments, i: number): string {
  return TYPE_LABELS[inst.type[i]] ?? inst.type[i];
}

/** Für Listen: „Xetra, EUR“ */
export function listingShort(inst: Instruments, i: number): string {
  const parts = [exchangeOf(inst, i), unitOf(inst, i)].filter(Boolean);
  return parts.join(', ');
}

export function idxList(isinIndex: Map<string, number>, isins: string[]): number[] {
  const out: number[] = [];
  for (const isin of isins) {
    const idx = isinIndex.get(isin);
    if (idx !== undefined && !out.includes(idx)) out.push(idx);
  }
  return out;
}

const ISIN_RE = /^[A-Z]{2}[A-Z0-9]{9}\d$/;

export function parseIsinList(text: string | null | undefined): string[] {
  if (!text) return [];
  const out: string[] = [];
  for (const part of text.split(/[,\s;]+/)) {
    const isin = part.trim().toUpperCase();
    if (ISIN_RE.test(isin) && !out.includes(isin)) out.push(isin);
  }
  return out;
}
