/* Musterdepots (ab 1.9) – nach dem Bericht „Zwei Zehnerdepots · 1–30 Tage · Beiträge“.
 *
 * Zwei Depots entstehen aus den Häufigkeitslisten des Berichts 1–30 (Zeiträume 1–30 Kalendertage,
 * Gewichtungen 0/100, 40/60, 50/50, 60/40, Gruppe A und B): die zehn Aktien mit den meisten ersten
 * Plätzen und die zehn mit den meisten Top-10-Nennungen. Dazu eigene Depots (ISIN-Listen auf dem Gerät).
 *
 * Je Rückblickfenster h (1–30 Kalendertage, Ende = Kursstichtag) eine eigene Rechnung: gleiche
 * Startbeträge je Aktie, danach unveränderte Stückzahlen (Bruchstücke erlaubt, keine Umschichtung).
 * Start ist der letzte echte Schlusskurs am oder vor (Stichtag − h), höchstens 7 Kalendertage davor –
 * dieselbe Regel wie in den Ranglisten. Rendite einer Aktie in der gewählten Basis:
 *   r = (Endkurs × Wechselkurs Ende) / (Startkurs × Wechselkurs Start) − 1
 * mit Euro-Referenzkursen (Kurs des Tages oder der letzte davor, höchstens ``max_alter_tage`` alt).
 * Beitrag = Startgewicht × r (in Prozentpunkten); die Summe der Beiträge ist die Depotrendite.
 * Nichts wird aufgefüllt: Fehlt ein Kurs, bleibt die Aktie in diesem Fenster draußen (mit Grund).
 * Reine Funktionen – ohne Browser testbar. */

import { groupFrequency, total, type GroupSelection } from './groups';
import { WEIGHTS } from './scoring';
import type { FrequencyData, FxData, Instruments, SeriesData } from './types';

export const DEPOT_DAYS = 30;
/** Startkurs höchstens so viele Kalendertage vor dem gewünschten Start (wie in den Ranglisten). */
export const START_LOOKBACK = 7;
export const DEPOT_SIZE = 10;
export const MAX_OWN_DEPOTS = 8;
export const MAX_DEPOT_MEMBERS = 20;

export type DepotBasis = 'usd' | 'eur' | 'lokal';

export const BASIS_LABEL: Record<DepotBasis, string> = { usd: 'USD', eur: 'EUR', lokal: 'Originalwährung' };

/* ------------------------------------------------------------------ Häufigkeit: zwei Top-10-Listen */

export type FrequencyPreset = 'bericht' | 'gesamt' | 'rendite';

export interface FrequencySelection {
  label: string;
  from: number;
  to: number;
  weights: number[];
  text: string;
}

export const FREQUENCY_PRESETS: Record<FrequencyPreset, FrequencySelection> = {
  bericht: { label: 'Bericht 1–30', from: 1, to: 30, weights: [0, 40, 50, 60], text: '1–30 Kalendertage · 0/100, 40/60, 50/50, 60/40' },
  gesamt: { label: 'Gesamt 1–90', from: 1, to: 90, weights: [...WEIGHTS], text: '1–90 Kalendertage · alle elf Gewichtungen' },
  rendite: { label: 'Höchste Rendite', from: 1, to: 30, weights: [0], text: '1–30 Kalendertage · nur 0/100 (Kursrendite)' },
};

/* Gewichtungen der Häufigkeit (ab 1.10): Standard „kurz“ = 40/60, 50/50, 60/40 (Wunsch vom 14.10.: kürzere
 * Auswertung, Gleichmäßigkeit und Rendite gemischt); als Optionen ausführlich alle elf (0/100 bis 100/0, wie in der
 * Datei „Zwei Zehnerdepots“ v3), die vier des Berichts und jede einzelne Gewichtung. */
export type WeightChoice = 'alle' | 'kurz' | 'bericht' | number;

export const STANDARD_CHOICE: WeightChoice = 'kurz';

export const WEIGHT_CHOICE_LABEL: Record<'alle' | 'kurz' | 'bericht', string> = {
  kurz: 'Standard: 40/60, 50/50, 60/40',
  alle: 'Ausführlich: alle 11 Gewichtungen (0/100 bis 100/0)',
  bericht: 'Bericht: 0/100, 40/60, 50/50, 60/40',
};

export function parseWeightChoice(text: string | null | undefined): WeightChoice {
  if (text === 'alle' || text === 'kurz' || text === 'bericht') return text;
  const n = Number(text);
  if (text !== null && text !== undefined && text !== '' && Number.isInteger(n) && (WEIGHTS as readonly number[]).includes(n)) return n;
  return STANDARD_CHOICE;
}

export function weightChoiceLabel(choice: WeightChoice): string {
  if (typeof choice === 'number') return choice === 0 ? 'Nur 0/100 (Kursrendite)' : choice === 100 ? 'Nur 100/0 (Gleichmäßigkeit)' : `Nur ${choice}/${100 - choice}`;
  return WEIGHT_CHOICE_LABEL[choice];
}

/** Auswahl der Häufigkeit: Gewichtungen und Zeitraum 1–30 (Standard) oder 1–90 Kalendertage. */
export function selectionFor(choice: WeightChoice, to: 30 | 90 = 30): FrequencySelection {
  const weights = choice === 'alle' ? [...WEIGHTS] : choice === 'kurz' ? [40, 50, 60] : choice === 'bericht' ? [0, 40, 50, 60] : [choice];
  const text =
    choice === 'alle'
      ? 'alle 11 Gewichtungen von 0/100 bis 100/0'
      : choice === 'kurz'
        ? '40/60, 50/50, 60/40'
        : choice === 'bericht'
          ? '0/100, 40/60, 50/50, 60/40'
          : `nur ${choice}/${100 - choice}`;
  return { label: weightChoiceLabel(choice), from: 1, to, weights, text: `1–${to} Kalendertage · ${text}` };
}

/** Listenlänge der Häufigkeit (ab 1.10): Top 20 wie in der Datei, wahlweise Top 10. */
export const LIST_SIZES = [20, 10] as const;
export const DEFAULT_LIST_SIZE = 20;

export interface FreqRow {
  idx: number;
  isin: string;
  n1: number;
  n3: number;
  n10: number;
  /** Ranglisten der Auswahl, in denen die Aktie einen Rang hat */
  available: number;
  /** Platz in der Liste „häufigste erste Plätze“ (1–10) oder null */
  rank1: number | null;
  /** Platz in der Liste „häufigste Top-10-Nennungen“ (1–10) oder null */
  rank10: number | null;
  /** Platz in der vollständigen Reihenfolge nach ersten Plätzen (auch über 10); null ohne ersten Platz */
  place1: number | null;
  /** Platz in der vollständigen Reihenfolge nach Top-10-Nennungen (auch über 10); null ohne Nennung */
  place10: number | null;
  both: boolean;
  /** ab 1.14: in der Liste „erste Plätze“ ohne eigenen ersten Platz – aufgefüllt nach Top 3, dann Top 10 */
  filled?: boolean;
}

export interface TopLists {
  /** Listenlänge (10 oder 20) */
  size: number;
  /** alle Aktien mit mindestens einer Nennung (für Ränge außerhalb der Listen) */
  rows: FreqRow[];
  firsts: FreqRow[];
  tops: FreqRow[];
  /** beide Listen zusammen, jede ISIN einmal */
  union: FreqRow[];
  /** in beiden Listen */
  both: FreqRow[];
  /** gültige Ranglisten der Auswahl */
  valid: number;
  /** ausgewählte Kombinationen (Zeiträume × Gewichtungen × Gruppen) */
  possible: number;
  /** ab 1.14: Plätze der Liste „erste Plätze“, die mangels Siegern aufgefüllt sind (nach Top 3, dann Top 10) */
  filled: number;
}

/** Wie im Bericht: erste Plätze, dann Top 3, Top 10, ISIN. */
export function byWins(a: FreqRow, b: FreqRow): number {
  return b.n1 - a.n1 || b.n3 - a.n3 || b.n10 - a.n10 || (a.isin < b.isin ? -1 : a.isin > b.isin ? 1 : 0);
}

/** Wie im Bericht: Top-10-Nennungen, dann erste Plätze, Top 3, ISIN. */
export function byTops(a: FreqRow, b: FreqRow): number {
  return b.n10 - a.n10 || b.n1 - a.n1 || b.n3 - a.n3 || (a.isin < b.isin ? -1 : a.isin > b.isin ? 1 : 0);
}

export function topLists(
  freq: FrequencyData,
  instruments: Instruments,
  selection: FrequencyPreset | FrequencySelection = 'bericht',
  groups: GroupSelection = 'ab',
  size = DEPOT_SIZE,
): TopLists {
  const p = typeof selection === 'string' ? FREQUENCY_PRESETS[selection] : selection;
  const result = groupFrequency(freq, instruments, { groups, weights: p.weights, from: p.from, to: p.to, dedupe: false, order: 'n1' });
  const rows: FreqRow[] = result.entries.map((e) => ({
    idx: e.idx,
    isin: instruments.isin[e.idx],
    n1: total(e, 'n1', groups),
    n3: total(e, 'n3', groups),
    n10: total(e, 'n10', groups),
    available: total(e, 'available', groups),
    rank1: null,
    rank10: null,
    place1: null,
    place10: null,
    both: false,
  }));
  const allFirsts = rows.filter((r) => r.n1 > 0).sort(byWins);
  const allTops = rows.filter((r) => r.n10 > 0).sort(byTops);
  allFirsts.forEach((r, k) => (r.place1 = k + 1));
  allTops.forEach((r, k) => (r.place10 = k + 1));
  // Ab 1.14 (Simons Wunsch „Musterdepots vollständig“): Haben weniger Aktien einen ersten Platz, als die Liste lang ist,
  // füllen die nächsten nach derselben Reihenfolge auf (Top 3, dann Top 10, dann ISIN) – ein Zehnerdepot hat immer zehn
  // Positionen, solange so viele Aktien genannt sind. Sie behalten „0 erste Plätze“ und sind gekennzeichnet.
  const fill = allFirsts.length < size ? rows.filter((r) => r.n1 === 0 && r.n10 > 0).sort(byWins).slice(0, size - allFirsts.length) : [];
  fill.forEach((r) => (r.filled = true));
  const firsts = [...allFirsts.slice(0, size), ...fill];
  const tops = allTops.slice(0, size);
  firsts.forEach((r, k) => (r.rank1 = k + 1));
  tops.forEach((r, k) => (r.rank10 = k + 1));
  for (const r of rows) r.both = r.rank1 !== null && r.rank10 !== null;
  const union = [...new Map([...firsts, ...tops].map((r) => [r.idx, r])).values()];
  const groupCount = groups === 'ab' ? 2 : 1;
  const valid = groups === 'a' ? result.validA : groups === 'b' ? result.validB : result.validA + result.validB;
  return {
    size,
    rows: rows.filter((r) => r.n10 > 0 || r.n1 > 0),
    firsts,
    tops,
    union,
    both: firsts.filter((r) => r.both),
    valid,
    possible: (p.to - p.from + 1) * p.weights.length * groupCount,
    filled: fill.length,
  };
}

export interface WeightWinner {
  weight: number;
  /** häufigster Sieger (meiste erste Plätze; Gleichstand: Top 3, Top 10, ISIN) oder null */
  row: FreqRow | null;
  /** gültige Ranglisten dieser Gewichtung (Nenner) */
  valid: number;
  possible: number;
}

/** „Welche Aktie gewinnt bei welcher Gewichtung am häufigsten?“ – je Gewichtung über 1–``to`` Tage, A und B. */
export function winnersByWeight(freq: FrequencyData, instruments: Instruments, to: 30 | 90 = 30, groups: GroupSelection = 'ab'): WeightWinner[] {
  return WEIGHTS.map((w) => {
    const lists = topLists(freq, instruments, { label: '', from: 1, to, weights: [w], text: '' }, groups, 1);
    return { weight: w, row: lists.firsts[0] ?? null, valid: lists.valid, possible: lists.possible };
  });
}

export interface PlaceShift {
  row: FreqRow;
  /** Platz in der Liste der Top-10-Nennungen: mit vier Gewichtungen (Bericht) und mit allen elf */
  before: number | null;
  after: number;
  /** Top-10-Nennungen vorher (vier Gewichtungen) */
  n10Before: number;
}

/** „Was ändert sich mit allen elf Gewichtungen?“ – Top-``size`` der Nennungen ausführlich (alle elf), daneben Platz
 * und Nennungen in der Standardauswahl 40/60, 50/50, 60/40 (1–30 Tage, A und B). */
export function weightShift(freq: FrequencyData, instruments: Instruments, size = DEFAULT_LIST_SIZE): { shifts: PlaceShift[]; validBefore: number; validAfter: number } {
  const after = topLists(freq, instruments, selectionFor('alle'), 'ab', size);
  const before = topLists(freq, instruments, selectionFor(STANDARD_CHOICE), 'ab', size);
  const old = new Map(before.rows.map((r) => [r.isin, r]));
  return {
    shifts: after.tops.map((row) => ({ row, after: row.rank10 ?? 0, before: old.get(row.isin)?.place10 ?? null, n10Before: old.get(row.isin)?.n10 ?? 0 })),
    validBefore: before.valid,
    validAfter: after.valid,
  };
}

/* ------------------------------------------------------------------ Depots */

export interface DepotDef {
  key: string;
  name: string;
  isins: string[];
  /** siege/top10: aus dem Bericht 1–30 gebildet; eigen: auf diesem Gerät gespeichert */
  kind: 'siege' | 'top10' | 'eigen';
}

export interface OwnDepot {
  name: string;
  isins: string[];
}

/** Die beiden Zehnerdepots – immer aus der Standardauswahl (40/60, 50/50, 60/40, 1–30 Tage, A und B; ab 1.10),
 * unabhängig von der Anzeige der Häufigkeit oben. */
export function reportDepots(lists: TopLists): DepotDef[] {
  return [
    { key: 'siege', name: '10 Sieger', isins: lists.firsts.map((r) => r.isin), kind: 'siege' },
    { key: 'top10', name: '10 Top-10', isins: lists.tops.map((r) => r.isin), kind: 'top10' },
  ];
}

export function ownDepotDefs(own: OwnDepot[]): DepotDef[] {
  return own.map((d, k) => ({ key: `eigen-${k + 1}`, name: d.name, isins: d.isins, kind: 'eigen' as const }));
}

/* ------------------------------------------------------------------ Kurse und Wechselkurse */

/** Index des letzten Werts ≤ ``day`` in aufsteigenden Tagen (−1 = keiner). */
export function lastAtOrBefore(days: number[], day: number): number {
  let lo = 0;
  let hi = days.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (days[mid] <= day) {
      found = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return found;
}

/** ISO-Währung für die Umrechnung (Untereinheiten wie Pence haben dieselbe Kursänderung). */
export function fxCurrency(currency: string | null | undefined): string | null {
  if (!currency) return null;
  const code = currency.toUpperCase();
  return ({ GBX: 'GBP', GBP: 'GBP', ZAC: 'ZAR', ILA: 'ILS' } as Record<string, string>)[code] ?? code;
}

export interface FxRate {
  value: number;
  day: number;
}

export interface FxLookup {
  /** Basiswährung je Einheit ``currency`` am Tag ``day`` (Kurs des Tages oder der letzte davor). */
  rate(currency: string, day: number, basis: Exclude<DepotBasis, 'lokal'>): FxRate | null;
}

export function fxLookup(fx: FxData): FxLookup {
  const days = fx.tage;
  const maxAge = Number.isFinite(fx.max_alter_tage) ? fx.max_alter_tage : 5;
  const perEur = (currency: string, day: number): FxRate | null => {
    if (currency === 'EUR') return { value: 1, day };
    const column = fx.je_eur[currency];
    if (!column) return null;
    for (let k = lastAtOrBefore(days, day); k >= 0 && day - days[k] <= maxAge; k -= 1) {
      const value = column[k];
      if (value !== null && value !== undefined && Number.isFinite(value) && value > 0) return { value, day: days[k] };
    }
    return null;
  };
  return {
    rate(currency, day, basis) {
      if (basis === 'usd') {
        if (currency === 'USD') return { value: 1, day };
        const usd = perEur('USD', day);
        const own = perEur(currency, day);
        return usd && own ? { value: usd.value / own.value, day: Math.min(usd.day, own.day) } : null;
      }
      if (currency === 'EUR') return { value: 1, day };
      const own = perEur(currency, day);
      return own ? { value: 1 / own.value, day: own.day } : null;
    },
  };
}

/* ------------------------------------------------------------------ Rechnung je Aktie und Depot */

export interface MemberOk {
  ok: true;
  isin: string;
  currency: string | null;
  startDay: number;
  startClose: number;
  endDay: number;
  endClose: number;
  /** Kursänderung in Notierungswährung (Anteil, 0,25 = +25 %) */
  localReturn: number;
  fxStart: FxRate | null;
  fxEnd: FxRate | null;
  /** Rendite in der gewählten Basis (Anteil) */
  ret: number;
  startVolume: number | null;
  endVolume: number | null;
  flags: string[];
}

export interface MemberMissing {
  ok: false;
  isin: string;
  reason: string;
}

export type MemberResult = MemberOk | MemberMissing;

export function memberReturn(isin: string, series: SeriesData | undefined, cutoffDay: number, h: number, basis: DepotBasis, fx: FxLookup | null): MemberResult {
  if (!series) return { ok: false, isin, reason: 'nicht im Datenstand oder ohne Kursreihe' };
  const d = series.d;
  const c = series.c;
  const end = lastAtOrBefore(d, cutoffDay);
  if (end < 0) return { ok: false, isin, reason: 'kein Kurs bis zum Stichtag' };
  if (cutoffDay - d[end] > START_LOOKBACK) return { ok: false, isin, reason: `letzter Kurs älter als ${START_LOOKBACK} Tage` };
  const target = cutoffDay - h;
  const start = lastAtOrBefore(d, target);
  if (start < 0 || target - d[start] > START_LOOKBACK) return { ok: false, isin, reason: 'kein Startkurs (Kursreihe beginnt später oder Lücke)' };
  const c0 = c[start];
  const c1 = c[end];
  if (!(Number.isFinite(c0) && c0 > 0 && Number.isFinite(c1) && c1 > 0)) return { ok: false, isin, reason: 'kein gültiger Schlusskurs' };
  const localReturn = c1 / c0 - 1;
  const currency = fxCurrency(series.listing.currency);
  let fxStart: FxRate | null = null;
  let fxEnd: FxRate | null = null;
  let ret = localReturn;
  if (basis !== 'lokal') {
    if (!fx || !currency) return { ok: false, isin, reason: 'kein Wechselkurs im Datenstand' };
    fxStart = fx.rate(currency, d[start], basis);
    fxEnd = fx.rate(currency, d[end], basis);
    if (!fxStart || !fxEnd) return { ok: false, isin, reason: `kein Wechselkurs für ${currency}` };
    ret = (c1 * fxEnd.value) / (c0 * fxStart.value) - 1;
  }
  const volume = (k: number): number | null => {
    const v = series.v[k];
    return v === null || v === undefined || !Number.isFinite(v) ? null : v;
  };
  const startVolume = volume(start);
  const endVolume = volume(end);
  const flags: string[] = [];
  if (startVolume === 0) flags.push('Startkurs ohne gemeldeten Umsatz');
  if (endVolume === 0) flags.push('Endkurs ohne gemeldeten Umsatz');
  if (series.provisional && series.provisional.day === d[end]) flags.push('Endkurs vorläufig (Zwischenstand)');
  return { ok: true, isin, currency, startDay: d[start], startClose: c0, endDay: d[end], endClose: c1, localReturn, fxStart, fxEnd, ret, startVolume, endVolume, flags };
}

export interface DepotPosition extends MemberOk {
  /** Startgewicht (Anteil) */
  w0: number;
  /** Beitrag zur Depotrendite (Anteil; × 100 = Prozentpunkte) */
  contribution: number;
  /** Endgewicht (Anteil) */
  w1: number;
  startValue: number;
  endValue: number;
  /** zusätzlich: sehr geringer Ø Tagesumsatz o. Ä. */
  warnings: string[];
}

export interface DepotResult {
  h: number;
  targetDay: number;
  endDay: number;
  positions: DepotPosition[];
  missing: MemberMissing[];
  /** Depotrendite (Anteil) oder null, wenn keine Aktie einen Kurs hat */
  ret: number | null;
  capital: number;
  endValue: number | null;
  /** † – mindestens eine Position mit Umsatz- oder Kurshinweis */
  flagged: boolean;
}

/** Ein Depot für ein Rückblickfenster. ``warningsFor`` liefert zusätzliche Hinweise je ISIN (z. B. dünn gehandelt). */
export function computeDepot(
  isins: string[],
  series: Map<string, SeriesData>,
  cutoffDay: number,
  h: number,
  basis: DepotBasis,
  fx: FxLookup | null,
  capital: number,
  warningsFor: (isin: string) => string[] = () => [],
): DepotResult {
  const results = [...new Set(isins)].map((isin) => memberReturn(isin, series.get(isin), cutoffDay, h, basis, fx));
  const ok = results.filter((r): r is MemberOk => r.ok);
  const missing = results.filter((r): r is MemberMissing => !r.ok);
  const n = ok.length;
  const w0 = n ? 1 / n : 0;
  const ret = n ? ok.reduce((sum, r) => sum + w0 * r.ret, 0) : null;
  const positions: DepotPosition[] = ok.map((r) => {
    const warnings = warningsFor(r.isin);
    return {
      ...r,
      w0,
      contribution: w0 * r.ret,
      w1: ret === null || 1 + ret <= 0 ? 0 : (w0 * (1 + r.ret)) / (1 + ret),
      startValue: capital * w0,
      endValue: capital * w0 * (1 + r.ret),
      warnings,
    };
  });
  const endDays = ok.map((r) => r.endDay);
  return {
    h,
    targetDay: cutoffDay - h,
    endDay: endDays.length ? Math.max(...endDays) : cutoffDay,
    positions,
    missing,
    ret,
    capital,
    endValue: ret === null ? null : capital * (1 + ret),
    flagged: positions.some((p) => p.flags.length > 0 || p.warnings.length > 0),
  };
}

export type ContributionSort = 'beitrag' | 'rendite' | 'name';

export function sortPositions(positions: DepotPosition[], sort: ContributionSort, nameOf: (isin: string) => string): DepotPosition[] {
  const list = [...positions];
  if (sort === 'name') return list.sort((a, b) => nameOf(a.isin).localeCompare(nameOf(b.isin), 'de') || (a.isin < b.isin ? -1 : 1));
  if (sort === 'rendite') return list.sort((a, b) => b.ret - a.ret || (a.isin < b.isin ? -1 : 1));
  return list.sort((a, b) => b.contribution - a.contribution || (a.isin < b.isin ? -1 : 1));
}

export interface DepotWindowRow {
  h: number;
  targetDay: number;
  /** Bewertungsstart: letzter Werktag am oder vor (Stichtag − h) */
  anchorDay: number;
  values: { key: string; ret: number | null; flagged: boolean; members: number; missing: number }[];
}

/** Letzter Werktag (Mo–Fr) am oder vor ``day`` (Epochentag; 1.1.1970 war ein Donnerstag). */
export function weekdayAtOrBefore(day: number): number {
  const weekday = (((day + 4) % 7) + 7) % 7; // 0 = Sonntag, 6 = Samstag
  return weekday === 0 ? day - 2 : weekday === 6 ? day - 1 : day;
}

/** Alle Depots für die Fenster 1 … ``days``: Depotrendite je Fenster (getrennte Rechnungen, kein Verlauf). */
export function depotWindows(
  depots: DepotDef[],
  series: Map<string, SeriesData>,
  cutoffDay: number,
  basis: DepotBasis,
  fx: FxLookup | null,
  days = DEPOT_DAYS,
  warningsFor: (isin: string) => string[] = () => [],
): DepotWindowRow[] {
  const rows: DepotWindowRow[] = [];
  for (let h = 1; h <= days; h += 1) {
    rows.push({
      h,
      targetDay: cutoffDay - h,
      anchorDay: weekdayAtOrBefore(cutoffDay - h),
      values: depots.map((depot) => {
        const result = computeDepot(depot.isins, series, cutoffDay, h, basis, fx, 1, warningsFor);
        return { key: depot.key, ret: result.ret, flagged: result.flagged, members: result.positions.length, missing: result.missing.length };
      }),
    });
  }
  return rows;
}

/* ------------------------------------------------------------------ Eigene Depots */

const ISIN_RE = /^[A-Z]{2}[A-Z0-9]{9}\d$/;

/** Prüft gespeicherte oder importierte eigene Depots: Name 1–40 Zeichen, 1–20 gültige ISINs, höchstens 8 Depots. */
export function sanitizeDepots(input: unknown): OwnDepot[] {
  if (!Array.isArray(input)) return [];
  const out: OwnDepot[] = [];
  for (const item of input) {
    if (!item || typeof item !== 'object') continue;
    const name = typeof (item as OwnDepot).name === 'string' ? (item as OwnDepot).name.trim().slice(0, 40) : '';
    const raw = Array.isArray((item as OwnDepot).isins) ? (item as OwnDepot).isins : [];
    const isins = [...new Set(raw.filter((x): x is string => typeof x === 'string').map((x) => x.trim().toUpperCase()).filter((x) => ISIN_RE.test(x)))].slice(0, MAX_DEPOT_MEMBERS);
    if (!name || !isins.length) continue;
    out.push({ name, isins });
    if (out.length >= MAX_OWN_DEPOTS) break;
  }
  return out;
}
