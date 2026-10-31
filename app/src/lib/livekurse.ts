/* Aktuelle Kurse aus „Jetzt aktualisieren“ (ab 1.21): Lieferungen lesen, zusammenführen, Zeitangaben.
 *
 * Jeder Kurs trägt drei getrennte Zeitangaben:
 *   Kurszeit      wann der Kurs an der Börse entstand (laut Kursanbieter)
 *   Abrufzeit     wann der Server ihn abgerufen hat
 *   Verzögerung   bekannte Verzögerung des Anbieters für diese Börse (laut Antwort, sonst laut Yahoo-Hilfe)
 * Ob ein Kurs „aktuell“ heißt, rechnet die App bei jeder Anzeige neu aus der jetzigen Uhrzeit – ein gespeicherter Kurs wird
 * nach dem erneuten Öffnen nie als aktuell gezeigt, wenn er es nicht mehr ist. */

import * as f from './format';

export interface LiveQuote {
  isin: string;
  symbol: string | null;
  price: number;
  /** Einheit des Kurses wie geliefert (z. B. EUR, USD, GBp) */
  unit: string | null;
  /** Kurszeit (ms seit 1970, UTC) */
  quoteTime: number;
  /** Handelstag des Kurses an der Börse (JJJJ-MM-TT) */
  session: string | null;
  marketState: string | null;
  delayMin: number | null;
  delaySource: 'yahoo_antwort' | 'yahoo_hilfe' | null;
  previousClose: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  /** Abrufzeit (ms seit 1970, UTC) */
  fetchedAt: number;
  kennung: string;
}

export interface DayCourse {
  isin: string;
  /** Zeitpunkte in Sekunden seit 1970 (UTC) */
  t: number[];
  c: number[];
  tz: string | null;
  interval: string;
  fetchedAt: number;
}

interface RawQuote {
  isin?: unknown;
  symbol?: unknown;
  kurs?: unknown;
  einheit?: unknown;
  kurszeit_utc?: unknown;
  sitzung?: unknown;
  marktstatus?: unknown;
  verzoegerung_min?: unknown;
  verzoegerung_quelle?: unknown;
  vortag?: unknown;
  eroeffnung?: unknown;
  hoch?: unknown;
  tief?: unknown;
  umsatz?: unknown;
  abrufzeit_utc?: unknown;
}

export interface Delivery {
  schema: string;
  kennung: string;
  teil: number;
  teile: number;
  umfang: string;
  angefragt_utc: string;
  erstellt_utc: string;
  quelle: { name: string; weg: string | null; hinweis: string };
  kurse: RawQuote[];
  fehlend: { isin: string; grund: string }[];
  kursverlauf: Record<string, { t: number[]; c: number[]; zeitzone: string | null; intervall: string; abrufzeit_utc?: string }>;
}

export const DELIVERY_SCHEMA = 'tr-kursaktualisierung/1';

const ISIN = /^[A-Z]{2}[A-Z0-9]{9}\d$/;

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function text(value: unknown, max = 40): string | null {
  return typeof value === 'string' && value.length <= max ? value : null;
}

function time(value: unknown): number | null {
  if (typeof value !== 'string') return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

/** Prüft eine entschlüsselte Lieferung und liefert die gültigen Kurse; Ungültiges wird übergangen. */
export function quotesFromDelivery(delivery: Delivery): LiveQuote[] {
  if (!delivery || delivery.schema !== DELIVERY_SCHEMA || !Array.isArray(delivery.kurse)) return [];
  const out: LiveQuote[] = [];
  for (const raw of delivery.kurse) {
    const isin = text(raw.isin, 12);
    const price = num(raw.kurs);
    const quoteTime = time(raw.kurszeit_utc);
    const fetchedAt = time(raw.abrufzeit_utc);
    if (!isin || !ISIN.test(isin) || price === null || price <= 0 || quoteTime === null || fetchedAt === null) continue;
    const delay = num(raw.verzoegerung_min);
    const source = raw.verzoegerung_quelle === 'yahoo_antwort' || raw.verzoegerung_quelle === 'yahoo_hilfe' ? raw.verzoegerung_quelle : null;
    out.push({
      isin,
      symbol: text(raw.symbol, 24),
      price,
      unit: text(raw.einheit, 8),
      quoteTime,
      session: text(raw.sitzung, 10),
      marketState: text(raw.marktstatus, 16),
      delayMin: delay !== null && delay >= 0 && delay <= 240 ? Math.round(delay) : null,
      delaySource: delay !== null ? source : null,
      previousClose: num(raw.vortag),
      open: num(raw.eroeffnung),
      high: num(raw.hoch),
      low: num(raw.tief),
      volume: num(raw.umsatz),
      fetchedAt,
      kennung: delivery.kennung,
    });
  }
  return out;
}

export function coursesFromDelivery(delivery: Delivery): DayCourse[] {
  if (!delivery || delivery.schema !== DELIVERY_SCHEMA || !delivery.kursverlauf || typeof delivery.kursverlauf !== 'object') return [];
  const out: DayCourse[] = [];
  for (const [isin, raw] of Object.entries(delivery.kursverlauf)) {
    if (!ISIN.test(isin) || !raw || !Array.isArray(raw.t) || !Array.isArray(raw.c) || raw.t.length !== raw.c.length || !raw.t.length) continue;
    if (!raw.t.every((x) => Number.isFinite(x)) || !raw.c.every((x) => Number.isFinite(x) && x > 0)) continue;
    out.push({ isin, t: raw.t, c: raw.c, tz: text(raw.zeitzone, 64), interval: text(raw.intervall, 8) ?? '5m', fetchedAt: time(raw.abrufzeit_utc) ?? time(delivery.erstellt_utc) ?? 0 });
  }
  return out;
}

/** Neuerer Kurs gewinnt (Kurszeit, bei Gleichstand die spätere Abrufzeit). */
export function newerQuote(a: LiveQuote | undefined, b: LiveQuote): LiveQuote {
  if (!a) return b;
  if (b.quoteTime !== a.quoteTime) return b.quoteTime > a.quoteTime ? b : a;
  return b.fetchedAt >= a.fetchedAt ? b : a;
}

export function mergeQuotes(map: ReadonlyMap<string, LiveQuote>, quotes: LiveQuote[]): Map<string, LiveQuote> {
  const next = new Map(map);
  for (const quote of quotes) next.set(quote.isin, newerQuote(next.get(quote.isin), quote));
  return next;
}

// ------------------------------------------------------------------ Verzögerungen und Zeitangaben

/** Verzögerung je Symbol-Endung laut Yahoo-Hilfe „Exchanges and data providers on Yahoo Finance“ (help.yahoo.com/kb/SLN2310.html,
 * abgerufen am 31.10.2026). Dieselbe Tabelle wie im Server (jobs/kursaktualisierung.py). USA ohne Endung: Nasdaq-Daten in
 * Echtzeit, OTC 15 Minuten – ohne Börsenangabe nicht unterscheidbar, deshalb keine Angabe. */
export const YAHOO_DELAY_MIN: Record<string, number> = {
  '.AS': 15, '.AT': 15, '.AX': 20, '.BA': 30, '.BD': 15, '.BE': 15, '.BK': 15, '.BM': 15, '.BO': 15, '.BR': 15,
  '.CN': 0, '.CO': 0, '.DE': 15, '.DU': 15, '.F': 15, '.HA': 15, '.HE': 0, '.HK': 15, '.HM': 15, '.IC': 0, '.IL': 20,
  '.IR': 15, '.IS': 15, '.JK': 10, '.JO': 15, '.KL': 15, '.KQ': 20, '.KS': 20, '.L': 20, '.LS': 15, '.MC': 15,
  '.MI': 20, '.MU': 15, '.MX': 20, '.NE': 0, '.NS': 0, '.NZ': 20, '.OL': 15, '.PA': 15, '.PR': 20, '.RG': 0,
  '.SA': 15, '.SG': 15, '.SI': 20, '.SN': 15, '.SS': 30, '.ST': 0, '.SW': 30, '.SZ': 30, '.T': 20, '.TA': 20,
  '.TL': 0, '.TO': 0, '.TW': 20, '.TWO': 20, '.V': 0, '.VI': 15, '.VS': 0, '.WA': 15,
};

export function knownDelay(symbol: string | null | undefined): number | null {
  if (!symbol || !symbol.includes('.')) return null;
  const suffix = `.${symbol.slice(symbol.lastIndexOf('.') + 1).toUpperCase()}`;
  return YAHOO_DELAY_MIN[suffix] ?? null;
}

export function delayText(minutes: number | null, source: 'yahoo_antwort' | 'yahoo_hilfe' | null): string {
  if (minutes === null) return 'Verzögerung unbekannt';
  const where = source === 'yahoo_antwort' ? 'laut Yahoo-Antwort' : 'laut Yahoo-Hilfe';
  return minutes === 0 ? `Echtzeit ${where}` : `${minutes} Min. verzögert ${where}`;
}

const clockFmt = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Berlin' });
const dayKeyFmt = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' });
const shortDayFmt = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', timeZone: 'Europe/Berlin' });
const hoursFmt = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 });

/** „13:42 Uhr“ (heute) bzw. „30.10., 22:00 Uhr“ – Berliner Zeit. */
export function whenText(ms: number, now = Date.now()): string {
  const date = new Date(ms);
  const sameDay = dayKeyFmt.format(date) === dayKeyFmt.format(new Date(now));
  return sameDay ? `${clockFmt.format(date)} Uhr` : `${shortDayFmt.format(date)}, ${clockFmt.format(date)} Uhr`;
}

/** Alter als Menge: „5 Min.“, „2,3 Std.“, „18 Tage“. */
export function ageText(ms: number, now = Date.now()): string {
  const minutes = Math.max(0, Math.round((now - ms) / 60_000));
  if (minutes < 60) return `${Math.max(1, minutes)} Min.`;
  const hours = Math.round(minutes / 6) / 10;
  if (hours < 24) return `${hoursFmt.format(hours)} Std.`;
  const days = Math.round(hours / 24);
  return days === 1 ? '1 Tag' : `${days} Tage`;
}

/** Zeitabstand: „gerade eben“, „vor 5 Min.“, „vor 2,3 Std.“, „vor 18 Tagen“. */
export function agoText(ms: number, now = Date.now()): string {
  const minutes = Math.max(0, Math.round((now - ms) / 60_000));
  if (minutes < 1) return 'gerade eben';
  const age = ageText(ms, now);
  if (age.endsWith('Tage')) return `vor ${age}n`;
  if (age === '1 Tag') return 'vor 1 Tag';
  return `vor ${age}`;
}

export type QuoteState = 'aktuell' | 'nicht_aktuell' | 'boerse_zu';

/** Spielraum über der gemeldeten Verzögerung, bis ein Kurs während des Handels als „nicht aktuell“ gilt. */
export const FRESH_SLACK_MIN = 20;
/** Ein gespeicherter Abruf gilt höchstens so lange als aktuell. */
export const FETCH_MAX_MIN = 30;

export interface QuoteStatus {
  state: QuoteState;
  /** kurze Kennzeichnung, z. B. „aktuell“, „nicht aktuell (2 Std. alt)“, „Börse geschlossen“ */
  badge: string;
  quoteText: string;
  fetchText: string;
  delayText: string;
}

/** Zustand eines Kurses jetzt. „aktuell“ nur, wenn der Handel läuft, der Kurs höchstens Verzögerung + 20 Minuten alt ist
 * und der Abruf höchstens 30 Minuten zurückliegt. Sonst „nicht aktuell“ bzw. „Börse geschlossen“ – nie aus dem Speicher
 * übernommen, immer neu gerechnet. */
export function quoteStatus(quote: LiveQuote, now = Date.now()): QuoteStatus {
  const delay = quote.delayMin ?? 0;
  const ageMin = (now - quote.quoteTime) / 60_000;
  const fetchAgeMin = (now - quote.fetchedAt) / 60_000;
  const trading = quote.marketState === 'REGULAR';
  let state: QuoteState;
  let badge: string;
  if (!trading && quote.marketState !== null) {
    state = 'boerse_zu';
    badge = quote.marketState === 'PRE' || quote.marketState === 'PREPRE' ? 'vor Handelsbeginn – letzter Kurs' : 'Börse geschlossen – letzter Kurs';
  } else if (trading && ageMin <= delay + FRESH_SLACK_MIN && fetchAgeMin <= FETCH_MAX_MIN) {
    state = 'aktuell';
    badge = 'aktuell';
  } else {
    state = 'nicht_aktuell';
    badge = `nicht aktuell (Kurs ${ageText(quote.quoteTime, now)} alt)`;
  }
  return {
    state,
    badge,
    quoteText: `Kurszeit ${whenText(quote.quoteTime, now)}${quote.session ? ` (Handelstag ${f.isoDate(quote.session)})` : ''}`,
    fetchText: `abgerufen ${whenText(quote.fetchedAt, now)} (${agoText(quote.fetchedAt, now)})`,
    delayText: delayText(quote.delayMin, quote.delaySource),
  };
}

/** Veränderung zum Vortag in Prozent (als Anteil), wenn bekannt. */
export function dayChange(quote: LiveQuote): number | null {
  if (quote.previousClose === null || quote.previousClose <= 0) return null;
  return quote.price / quote.previousClose - 1;
}
