/* Lokale Einstellungen und Watchlist (nur auf diesem Gerät, in diesem Browser).
 * Alle Zugriffe sind abgesichert; ohne Speicher funktioniert die App mit Standardwerten.
 * Hinweis für Nutzer: Beim Löschen der Browserdaten gehen Watchlist und Einstellungen
 * verloren – deshalb gibt es Export und Import. */

import { sanitizeDepots, type DepotBasis, type OwnDepot } from './depots';
import type { Group, Policy } from './types';

export type Theme = 'system' | 'hell' | 'dunkel';

export interface Prefs {
  h: number;
  w: number;
  policy: Policy;
  /** Aktiengruppe A (alle) oder B (Ø Umsatz ≥ 10 Mio. USD) – bleibt beim Zeitraumwechsel erhalten */
  group: Group;
  /** Häufigkeitsranking: „gewinnt am häufigsten“ (Platz 1) oder „Meiste Top-10-Nennungen“ */
  frequencyOrder: 'n1' | 'n10';
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
  /** Musterdepots (ab 1.9): eigene Depots als ISIN-Listen, Rechenbasis und Startkapital */
  depots: OwnDepot[];
  depotBasis: DepotBasis;
  depotCapital: number;
  /** ab 1.14: Rendite-Ranglisten ohne Aktien mit kaum Umsatz (unter 1 Mio. USD am Tag) und ohne Einzelsprung */
  ohneAuffaellige: boolean;
}

/** Simons Dreier- und Viererdepot aus dem Bericht „Zwei Zehnerdepots · 1–30 Tage“ (14.10.2026) – auf dem Gerät änderbar. */
export const DEFAULT_DEPOTS: OwnDepot[] = [
  { name: 'Dreierdepot', isins: ['US74624M1027', 'US50015M1099', 'US70465T1079'] },
  { name: 'Viererdepot', isins: ['US74624M1027', 'US5352191093', 'CA82509L1076', 'US70465T1079'] },
];

export const DEFAULT_PREFS: Prefs = {
  h: 90,
  w: 60,
  policy: 'native',
  group: 'a',
  frequencyOrder: 'n1',
  theme: 'system',
  gridColumns: [1, 7, 14, 30, 60, 90],
  frequencyTopK: 10,
  frequencyWeights: 'all',
  frequencyPolicy: 'native',
  frequencySort: 'occurrences',
  compareA: 50,
  compareB: 60,
  ruleDepot: null,
  depots: DEFAULT_DEPOTS,
  depotBasis: 'usd',
  depotCapital: 1000,
  ohneAuffaellige: false,
};

const PREFS_KEY = 'tr-vergleich:einstellungen:v2';
// v1 (bis 1.4): Standardzeitraum 30 Tage. Beim Wechsel auf v2 gilt einmal der neue Standard 90 Tage / 60/40.
const PREFS_KEY_V1 = 'tr-vergleich:einstellungen:v1';
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
  if (merged.group !== 'a' && merged.group !== 'b') merged.group = 'a';
  if (merged.frequencyOrder !== 'n1' && merged.frequencyOrder !== 'n10') merged.frequencyOrder = 'n1';
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
  merged.depots = Array.isArray(merged.depots) ? sanitizeDepots(merged.depots) : DEFAULT_DEPOTS;
  if (!['usd', 'eur', 'lokal'].includes(merged.depotBasis)) merged.depotBasis = 'usd';
  if (!(typeof merged.depotCapital === 'number' && Number.isFinite(merged.depotCapital) && merged.depotCapital >= 1 && merged.depotCapital <= 100_000_000)) merged.depotCapital = DEFAULT_PREFS.depotCapital;
  merged.ohneAuffaellige = merged.ohneAuffaellige === true;
  const known = Object.keys(DEFAULT_PREFS);
  for (const key of Object.keys(merged)) if (!known.includes(key)) delete (merged as unknown as Record<string, unknown>)[key];
  return merged;
}

export function loadPrefs(): Prefs {
  const current = read<Partial<Prefs>>(PREFS_KEY);
  if (current) return sanitizePrefs(current);
  const old = read<Partial<Prefs>>(PREFS_KEY_V1);
  if (!old) return sanitizePrefs(null);
  // Übernahme aus v1: alles außer Zeitraum und Gewichtung (neuer Standard 90 Tage, 60/40)
  const { h: _h, w: _w, ...rest } = old;
  return sanitizePrefs(rest);
}

export function savePrefs(prefs: Prefs): boolean {
  return write(PREFS_KEY, prefs);
}

export function loadWatchlist(): string[] {
  const list = read<string[]>(WATCH_KEY);
  // mehrfach erfasste ISINs zusammenführen (Reihenfolge des ersten Vorkommens)
  return Array.isArray(list) ? [...new Set(list.filter((x) => typeof x === 'string' && /^[A-Z]{2}[A-Z0-9]{9}\d$/.test(x)))] : [];
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
