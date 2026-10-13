/* Lokale Einstellungen und Watchlist (nur auf diesem Gerät, in diesem Browser).
 * Alle Zugriffe sind abgesichert; ohne Speicher funktioniert die App mit Standardwerten.
 * Hinweis für Nutzer: Beim Löschen der Browserdaten gehen Watchlist und Einstellungen
 * verloren – deshalb gibt es Export und Import. */

import type { Policy } from './types';

export type Theme = 'system' | 'hell' | 'dunkel';

export interface Prefs {
  h: number;
  w: number;
  policy: Policy;
  theme: Theme;
  gridColumns: number[];
  frequencyTopK: 1 | 3 | 10;
  frequencyWeights: 'all' | number;
  frequencyPolicy: Policy;
  frequencySort: 'occurrences' | 'distinct_windows';
  compareA: number;
  compareB: number;
  /** Eigener Depotwert für die Beträge der Umschichtungs-Regel (null = Wert des Regeldepots). */
  ruleDepot: number | null;
}

export const DEFAULT_PREFS: Prefs = {
  h: 30,
  w: 60,
  policy: 'native',
  theme: 'system',
  gridColumns: [1, 7, 14, 30, 60, 90],
  frequencyTopK: 10,
  frequencyWeights: 'all',
  frequencyPolicy: 'native',
  frequencySort: 'occurrences',
  compareA: 50,
  compareB: 60,
  ruleDepot: null,
};

const PREFS_KEY = 'tr-vergleich:einstellungen:v1';
const WATCH_KEY = 'tr-vergleich:watchlist:v1';
const SNAPSHOT_KEY = 'tr-vergleich:gewaehlter-stand:v1';

function read<T>(key: string): T | null {
  try {
    const text = window.localStorage.getItem(key);
    return text ? (JSON.parse(text) as T) : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown): boolean {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

const WEIGHT_SET = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

/** Prüft gespeicherte oder importierte Einstellungen; Unbekanntes fällt auf Standardwerte zurück. */
export function sanitizePrefs(input: Partial<Prefs> | null | undefined): Prefs {
  const merged: Prefs = { ...DEFAULT_PREFS, ...(input && typeof input === 'object' ? input : {}) };
  if (!Number.isInteger(merged.h) || merged.h < 1 || merged.h > 90) merged.h = DEFAULT_PREFS.h;
  if (!WEIGHT_SET.includes(merged.w)) merged.w = DEFAULT_PREFS.w;
  if (merged.policy !== 'native' && merged.policy !== 'common_trend') merged.policy = 'native';
  if (!['system', 'hell', 'dunkel'].includes(merged.theme)) merged.theme = 'system';
  if (!Array.isArray(merged.gridColumns) || !merged.gridColumns.length || merged.gridColumns.some((h) => !Number.isInteger(h) || h < 1 || h > 90)) {
    merged.gridColumns = DEFAULT_PREFS.gridColumns;
  }
  merged.gridColumns = [...new Set(merged.gridColumns)].slice(0, 8);
  if (![1, 3, 10].includes(merged.frequencyTopK)) merged.frequencyTopK = DEFAULT_PREFS.frequencyTopK;
  if (merged.frequencyWeights !== 'all' && !WEIGHT_SET.includes(merged.frequencyWeights as number)) merged.frequencyWeights = 'all';
  if (merged.frequencyPolicy !== 'native' && merged.frequencyPolicy !== 'common_trend') merged.frequencyPolicy = 'native';
  if (merged.frequencySort !== 'occurrences' && merged.frequencySort !== 'distinct_windows') merged.frequencySort = 'occurrences';
  if (!WEIGHT_SET.includes(merged.compareA)) merged.compareA = DEFAULT_PREFS.compareA;
  if (!WEIGHT_SET.includes(merged.compareB)) merged.compareB = DEFAULT_PREFS.compareB;
  if (merged.ruleDepot !== null && !(typeof merged.ruleDepot === 'number' && Number.isFinite(merged.ruleDepot) && merged.ruleDepot >= 100 && merged.ruleDepot <= 100_000_000)) {
    merged.ruleDepot = null;
  }
  const known = Object.keys(DEFAULT_PREFS);
  for (const key of Object.keys(merged)) if (!known.includes(key)) delete (merged as unknown as Record<string, unknown>)[key];
  return merged;
}

export function loadPrefs(): Prefs {
  return sanitizePrefs(read<Partial<Prefs>>(PREFS_KEY));
}

export function savePrefs(prefs: Prefs): boolean {
  return write(PREFS_KEY, prefs);
}

export function loadWatchlist(): string[] {
  const list = read<string[]>(WATCH_KEY);
  return Array.isArray(list) ? list.filter((x) => typeof x === 'string' && /^[A-Z]{2}[A-Z0-9]{9}\d$/.test(x)) : [];
}

export function saveWatchlist(list: string[]): boolean {
  return write(WATCH_KEY, list);
}

export function loadChosenSnapshot(): string | null {
  return read<string>(SNAPSHOT_KEY);
}

export function saveChosenSnapshot(id: string | null): void {
  if (id === null) {
    try {
      window.localStorage.removeItem(SNAPSHOT_KEY);
    } catch {
      /* ignorieren */
    }
    return;
  }
  write(SNAPSHOT_KEY, id);
}

export function exportPersonalData(prefs: Prefs, watchlist: string[]): string {
  return JSON.stringify({ format: 'tr-vergleich-persoenlich/1', exportiert: new Date().toISOString(), einstellungen: prefs, watchlist }, null, 2);
}

export function importPersonalData(text: string): { prefs?: Partial<Prefs>; watchlist?: string[] } {
  const data = JSON.parse(text);
  if (!data || data.format !== 'tr-vergleich-persoenlich/1') throw new Error('Unbekanntes Dateiformat');
  const watchlist = Array.isArray(data.watchlist) ? data.watchlist.filter((x: unknown) => typeof x === 'string' && /^[A-Z]{2}[A-Z0-9]{9}\d$/.test(x as string)) : undefined;
  return { prefs: data.einstellungen ?? undefined, watchlist };
}
