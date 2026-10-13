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

/** Prüfziffer einer ISIN (Luhn über die Ziffernfolge mit A = 10 … Z = 35). */
export function isinCheckDigitOk(isin: string): boolean {
  if (!ISIN_RE.test(isin)) return false;
  const digits = isin
    .slice(0, 11)
    .split('')
    .map((ch) => (ch >= '0' && ch <= '9' ? ch : String(ch.charCodeAt(0) - 55)))
    .join('');
  let sum = 0;
  let double = true;
  for (let i = digits.length - 1; i >= 0; i -= 1) {
    let d = Number(digits[i]);
    if (double) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
    double = !double;
  }
  return (10 - (sum % 10)) % 10 === Number(isin[11]);
}

export interface IsinImport {
  /** gültige ISINs in Eingabereihenfolge, ohne Doppelte */
  valid: string[];
  /** Einträge mit ISIN-Form, aber falscher Prüfziffer, oder ohne ISIN-Form */
  invalid: string[];
  /** mehrfach eingegebene ISINs (zusammengeführt) */
  duplicates: number;
}

/** ISIN-Liste aus freiem Text (Zeilen, Kommas, Semikolons, Leerzeichen). Nur ISINs zählen – Namen
 * oder Ticker werden nie einer Aktie zugeordnet. */
export function parseIsinImport(text: string): IsinImport {
  const out: IsinImport = { valid: [], invalid: [], duplicates: 0 };
  for (const part of text.split(/[,\s;]+/)) {
    const token = part.trim().toUpperCase().replace(/^"|"$/g, '');
    if (!token) continue;
    if (!isinCheckDigitOk(token)) {
      if (!out.invalid.includes(token)) out.invalid.push(token);
      continue;
    }
    if (out.valid.includes(token)) out.duplicates += 1;
    else out.valid.push(token);
  }
  return out;
}
