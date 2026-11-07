/* Eigene Positionen (ab 1.24.0): Einstandskurs je Aktie, nur auf diesem Gerät gespeichert – keine Zugangsdaten, keine
 * Orders, keine Übertragung. Grundlage für „Halten“ oder „Verkaufen“ in der Einzelansicht. */

import type { Position } from './bewertung';

export const POSITIONS_KEY = 'tr-vergleich:positionen:v1';
const ISIN = /^[A-Z]{2}[A-Z0-9]{9}\d$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export type Positions = Record<string, Position>;

/** Nur gültige Einträge übernehmen (gespeichert oder importiert). */
export function sanitizePositions(input: unknown): Positions {
  const out: Positions = {};
  if (!input || typeof input !== 'object') return out;
  for (const [isin, raw] of Object.entries(input as Record<string, unknown>)) {
    if (!ISIN.test(isin) || !raw || typeof raw !== 'object') continue;
    const r = raw as Record<string, unknown>;
    const kurs = typeof r.kurs === 'number' && Number.isFinite(r.kurs) && r.kurs > 0 ? r.kurs : null;
    if (kurs === null) continue;
    out[isin] = {
      kurs,
      einheit: typeof r.einheit === 'string' && r.einheit.length <= 8 ? r.einheit : null,
      datum: typeof r.datum === 'string' && DATE.test(r.datum) ? r.datum : null,
    };
  }
  return out;
}

/** Deutsche Zahl („17,79“, „1.234,5“) oder null. */
export function parseAmount(text: string): number | null {
  const clean = text.trim().replace(/\s/g, '');
  if (!clean) return null;
  const normalized = clean.includes(',') ? clean.replace(/\./g, '').replace(',', '.') : clean;
  if (!/^\d+(\.\d+)?$/.test(normalized)) return null;
  const value = Number(normalized);
  return Number.isFinite(value) && value > 0 ? value : null;
}

const listeners = new Set<() => void>();
let cache: Positions | null = null;

export function loadPositions(): Positions {
  if (cache) return cache;
  try {
    const text = window.localStorage.getItem(POSITIONS_KEY);
    cache = sanitizePositions(text ? JSON.parse(text) : null);
  } catch {
    cache = {};
  }
  return cache;
}

/** Speichern (null entfernt die Position). Ohne Speicher (privates Fenster) bleibt es für diese Sitzung im Speicher. */
export function savePosition(isin: string, position: Position | null): boolean {
  const next = { ...loadPositions() };
  if (position) next[isin] = position;
  else delete next[isin];
  cache = next;
  let stored = true;
  try {
    window.localStorage.setItem(POSITIONS_KEY, JSON.stringify(next));
  } catch {
    stored = false;
  }
  listeners.forEach((fn) => fn());
  return stored;
}

export function subscribePositions(fn: () => void): () => void {
  listeners.add(fn);
  const onStorage = (event: StorageEvent) => {
    if (event.key === POSITIONS_KEY) {
      cache = null;
      fn();
    }
  };
  window.addEventListener('storage', onStorage);
  return () => {
    listeners.delete(fn);
    window.removeEventListener('storage', onStorage);
  };
}
