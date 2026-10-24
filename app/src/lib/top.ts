/* „Top 3 nach Zahlen“ (ab 1.11) – eine feste Rechenregel über alle Aktien, ohne Meinung.
 *
 * Simons Wunsch vom 14.10.2026: „nach berechenbaren Fakten ausrechnen … nach Berechnungen handeln, emotionslos“ –
 * Aktien, die in vielen Ranglisten vorne stehen, deren Kurs steigt, bei denen die Analysten positiv sind und
 * das Volumen steigt; Börsenwert berücksichtigen.
 *
 * Punkte 0–100 je Aktie:
 *   40  Wiederholt vorne – Anteil der gültigen Standard-Ranglisten (40/60, 50/50, 60/40 · 1–30 Tage · Gruppe A
 *       und B), in denen die Aktie unter den ersten 10 steht
 *   25  Steigt stetig    – Steig-Konstanz 30/60/90 Tage (0–100, Teil der Gesamtwertung im Signal-Stand)
 *   20  Analysten        – Kursziel-Potenzial (0–100, Teil der Gesamtwertung; voll erst ab 5 Analysten)
 *   15  Volumen          – Umsatz der letzten Sitzung ÷ Ø 20 Sitzungen bei steigendem Kurs (5 Sitzungen):
 *                          1,0-fach = 0, ab 2,0-fach voll; ohne steigenden Kurs 0
 *   Abzug Börsenwert: unter 300 Mio. € −10, unter 50 Mio. € −20
 *
 * Gewertet werden nur Aktien mit mindestens einer Top-10-Nennung in der Standardauswahl. Fehlende Angaben zählen
 * 0 Punkte (nie geschätzt). Warnzeichen (sehr kleiner Börsenwert, Kurs in 20 Sitzungen verdoppelt, wenige
 * Analysten, überkauft, wenig Umsatz) werden angezeigt; nur der Börsenwert geht als Abzug in die Punkte ein.
 *
 * Ab 1.14 (Simons Wahl „aussagekräftiger“): Plätze und Top 3 nur für handelbare Aktien – Ø Tagesumsatz ab
 * 10 Mio. USD (Gruppe B). Weniger gehandelte Aktien behalten ihre Punkte (z. B. unter „Deine Aktien“), bekommen
 * aber keinen Platz: Ihre Kurse sind leichter zu bewegen, ein Kauf zum angezeigten Kurs ist oft nicht möglich.
 */

import * as f from './format';
import type { FreqRow } from './depots';
import type { SignalsData } from './types';

export const TOP_POINTS = { vorne: 40, steigt: 25, analysten: 20, volumen: 15 } as const;
export type TopPart = keyof typeof TOP_POINTS;
export const TOP_PARTS: TopPart[] = ['vorne', 'steigt', 'analysten', 'volumen'];
export const TOP_PART_LABEL: Record<TopPart, string> = {
  vorne: 'Oft vorne',
  steigt: 'Steigt stetig',
  analysten: 'Analysten',
  volumen: 'Volumen',
};

export const SMALL_CAP_EUR = 300e6;
export const MICRO_CAP_EUR = 50e6;
export const SMALL_CAP_PENALTY = 10;
export const MICRO_CAP_PENALTY = 20;
/** Relatives Volumen, ab dem der Volumen-Teil voll zählt */
export const VOLUME_FULL = 2;
/** Relatives Volumen, ab dem die App „Volumen gestiegen“ anzeigt */
export const VOLUME_BADGE = 1.5;
export const DOUBLED_20 = 1.0;
export const OVERBOUGHT_RSI = 75;
export const FEW_ANALYSTS = 3;
export const LOW_TURNOVER_EUR = 1e6;

export type TopWarningKey = 'kleinstwert' | 'klein' | 'verdoppelt' | 'wenige_analysten' | 'ueberkauft' | 'wenig_umsatz' | 'ohne_signale';

export interface TopWarning {
  key: TopWarningKey;
  text: string;
}

export interface TopEntry {
  isin: string;
  /** Index in den Instrumenten des Datenstands */
  idx: number;
  /** Index im Signal-Stand oder null */
  sig: number | null;
  /** Platz unter den handelbaren Aktien (1 = beste); 0 = nicht handelbar genug (ohne Platz). Bei gleichen Punkten
   * entscheidet die Reihenfolge der Regel */
  place: number;
  /** ab 1.14: Ø Tagesumsatz ab 10 Mio. USD (Gruppe B) – nur diese Aktien bekommen einen Platz */
  tradeable: boolean;
  /** Platz unter allen Aktien mit Top-10-Nennung (auch wenig gehandelte) */
  overall: number;
  points: number;
  parts: Record<TopPart, number>;
  penalty: number;
  /** Top-10-Nennungen und erste Plätze in der Standardauswahl, gültige Ranglisten (Nenner) */
  n10: number;
  n1: number;
  valid: number;
  konstanz: number | null;
  kursziel: number | null;
  rvol: number | null;
  r5: number | null;
  r20: number | null;
  upside: number | null;
  analysts: number | null;
  capEur: number | null;
  total: number | null;
  /** Anteil früherer Fälle mit ähnlicher Steig-Konstanz, die 20 bzw. 60 Handelstage später höher standen */
  hit20: number | null;
  hit60: number | null;
  warnings: TopWarning[];
}

export interface TopResult {
  /** alle Aktien mit Top-10-Nennung in der Reihenfolge der Regel (handelbare und wenig gehandelte gemischt) */
  entries: TopEntry[];
  /** nur handelbare Aktien (Platz 1, 2, …) – daraus die Top 3 */
  ranked: TopEntry[];
  valid: number;
  /** Signal-Stand vorhanden und mit Gesamtwertung (signale-v2) */
  withSignals: boolean;
  /** Börsenwert im Signal-Stand vorhanden (ab 1.11) */
  withCap: boolean;
}

const finite = (x: number | null | undefined): x is number => typeof x === 'number' && Number.isFinite(x);
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
/** Teilpunkte in ganzen Zehnteln (ab 1.18): angezeigt wird Zehntel / 10, summiert wird ganzzahlig. */
const tenths = (x: number) => Math.round(x * 10);

/** Volumen-Teil (0–1): relatives Volumen bei steigendem Kurs; ohne steigenden Kurs 0. */
export function volumeShare(rvol: number | null | undefined, r5: number | null | undefined): number | null {
  if (!finite(rvol)) return null;
  if (!finite(r5) || r5 <= 0) return 0;
  return clamp01((rvol - 1) / (VOLUME_FULL - 1));
}

/** Abzug für kleinen Börsenwert (in EUR); ohne Angabe kein Abzug. */
export function capPenalty(capEur: number | null | undefined): number {
  if (!finite(capEur)) return 0;
  if (capEur < MICRO_CAP_EUR) return MICRO_CAP_PENALTY;
  if (capEur < SMALL_CAP_EUR) return SMALL_CAP_PENALTY;
  return 0;
}

/** „99 Mio. €“, „1,25 Mrd. €“ */
export function capText(capEur: number | null | undefined): string {
  return finite(capEur) ? f.money(capEur, '€') : 'unbekannt';
}

/** Kurztext „Volumen 2,4-fach“ für Zeilen und Listen (nur bei deutlich gestiegenem Volumen), sonst null. */
export function volumeBadge(rvol: number | null | undefined): string | null {
  if (!finite(rvol) || rvol < VOLUME_BADGE) return null;
  return `Volumen ${new Intl.NumberFormat('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(rvol)}-fach`;
}

function warningsFor(e: Omit<TopEntry, 'warnings' | 'place' | 'overall'>, rsi: number | null, turnover: number | null): TopWarning[] {
  const out: TopWarning[] = [];
  if (e.sig === null) out.push({ key: 'ohne_signale', text: 'ohne Signal-Daten (Steigen, Analysten, Volumen zählen 0)' });
  if (finite(e.capEur) && e.capEur < MICRO_CAP_EUR) out.push({ key: 'kleinstwert', text: `sehr kleiner Börsenwert (${capText(e.capEur)})` });
  else if (finite(e.capEur) && e.capEur < SMALL_CAP_EUR) out.push({ key: 'klein', text: `kleiner Börsenwert (${capText(e.capEur)})` });
  if (finite(e.r20) && e.r20 >= DOUBLED_20) out.push({ key: 'verdoppelt', text: `in 20 Sitzungen ${f.pct(e.r20, 0)} – mehr als verdoppelt` });
  if (e.sig !== null && finite(e.analysts) && e.analysts < FEW_ANALYSTS) out.push({ key: 'wenige_analysten', text: e.analysts === 0 ? 'keine Analysten' : `nur ${f.plural(e.analysts, 'Analyst', 'Analysten')}` });
  if (finite(rsi) && rsi >= OVERBOUGHT_RSI) out.push({ key: 'ueberkauft', text: `RSI ${Math.round(rsi)} – überkauft` });
  if (finite(turnover) && turnover < LOW_TURNOVER_EUR) out.push({ key: 'wenig_umsatz', text: `wenig Umsatz (${f.money(turnover, '€')} am Tag)` });
  return out;
}

/** Reihenfolge bei gleichen Punkten: mehr Top-10-Nennungen, mehr erste Plätze, höhere Gesamtwertung, ISIN. */
function compare(a: TopEntry, b: TopEntry): number {
  return b.points - a.points || b.n10 - a.n10 || b.n1 - a.n1 || (b.total ?? -1) - (a.total ?? -1) || (a.isin < b.isin ? -1 : a.isin > b.isin ? 1 : 0);
}

/**
 * Rangfolge aller Aktien mit mindestens einer Top-10-Nennung in der Standardauswahl.
 * ``rows`` und ``valid`` aus ``topLists(…, selectionFor('kurz'), 'ab')``; ``signals`` darf fehlen. ``liquid`` (ab 1.14):
 * Gruppe B je Instrumentindex (Ø Tagesumsatz ab 10 Mio. USD) – nur diese Aktien bekommen einen Platz; ohne Angabe
 * (Stände ohne Umsatz) gelten alle als handelbar.
 */
export function rankTop(rows: FreqRow[], valid: number, signals: SignalsData | null | undefined, liquid?: (boolean | null)[] | null): TopResult {
  const sigIndex = new Map<string, number>();
  signals?.isin.forEach((isin, k) => sigIndex.set(isin, k));
  const parts = signals?.gesamt_teile;
  const feat = signals?.merkmale ?? {};
  const caps = signals?.boersenwert_eur;
  const entries: TopEntry[] = [];
  for (const row of rows) {
    if (row.n10 <= 0) continue;
    const k = sigIndex.get(row.isin);
    const sig = k === undefined ? null : k;
    const pick = (values: (number | null)[] | undefined) => (sig === null || !values ? null : values[sig] ?? null);
    const konstanz = pick(parts?.konstanz);
    const kursziel = pick(parts?.kursziel);
    const rvol = pick(feat.rvol);
    const r5 = pick(feat.r5);
    const capEur = pick(caps);
    const share = valid > 0 ? clamp01(row.n10 / valid) : 0;
    const vol = volumeShare(rvol, r5);
    const parts10: Record<TopPart, number> = {
      vorne: tenths(TOP_POINTS.vorne * share),
      steigt: tenths(TOP_POINTS.steigt * clamp01((konstanz ?? 0) / 100)),
      analysten: tenths(TOP_POINTS.analysten * clamp01((kursziel ?? 0) / 100)),
      volumen: tenths(TOP_POINTS.volumen * (vol ?? 0)),
    };
    const scored: Record<TopPart, number> = { vorne: parts10.vorne / 10, steigt: parts10.steigt / 10, analysten: parts10.analysten / 10, volumen: parts10.volumen / 10 };
    const penalty = capPenalty(capEur);
    // Summe exakt in Zehnteln: 0,1 + 5,6 + 0,3 + 0,5 ergäbe als Gleitkommasumme 6,4999… und damit 6 statt 7 Punkte
    const sum = (parts10.vorne + parts10.steigt + parts10.analysten + parts10.volumen - 10 * penalty) / 10;
    const base = {
      isin: row.isin,
      idx: row.idx,
      sig,
      tradeable: !liquid || Boolean(liquid[row.idx]),
      points: Math.max(0, Math.round(sum)),
      parts: scored,
      penalty,
      n10: row.n10,
      n1: row.n1,
      valid,
      konstanz,
      kursziel,
      rvol,
      r5,
      r20: pick(feat.r20),
      upside: pick(signals?.potenzial),
      analysts: sig === null || !signals ? null : signals.analysten[sig] ?? null,
      capEur,
      total: pick(signals?.gesamt),
      hit20: pick(signals?.gesamt_steigt_20),
      hit60: pick(signals?.gesamt_steigt_60),
    };
    entries.push({ ...base, place: 0, overall: 0, warnings: warningsFor(base, pick(feat.rsi), pick(feat.umsatz_eur)) });
  }
  entries.sort(compare);
  entries.forEach((e, k) => (e.overall = k + 1));
  const ranked = entries.filter((e) => e.tradeable);
  ranked.forEach((e, k) => (e.place = k + 1));
  return {
    entries,
    ranked,
    valid,
    withSignals: Boolean(signals && signals.gesamt_teile),
    withCap: Boolean(caps),
  };
}

/** Eine Zeile Begründung: „in 45 von 66 Ranglisten unter den ersten 10 · steigt an 61 % der Tage …“ */
export function topReason(e: TopEntry): string {
  const bits = [`in ${f.integer(e.n10)} von ${f.integer(e.valid)} Standard-Ranglisten unter den ersten 10`];
  if (e.n1 > 0) bits.push(`${f.integer(e.n1)}× Platz 1`);
  if (finite(e.upside) && finite(e.analysts) && e.analysts > 0) bits.push(`Kursziel ${f.pct(e.upside, 0)} (${f.plural(e.analysts, 'Analyst', 'Analysten')})`);
  const badge = volumeBadge(e.rvol);
  if (badge && finite(e.r5) && e.r5 > 0) bits.push(badge);
  return bits.join(' · ');
}

/** „Früher 20 Handelstage später höher: 58 % (alle Aktien 52 %)“ oder null. */
export function hitText(e: TopEntry, base20: number | null | undefined): string | null {
  if (!finite(e.hit20)) return null;
  const all = finite(base20) ? ` (alle Aktien ${f.plainPct(base20 * 100, 0)})` : '';
  const sixty = finite(e.hit60) ? `, nach 60: ${f.plainPct(e.hit60 * 100, 0)}` : '';
  return `Früher bei ähnlicher Steig-Konstanz 20 Handelstage später höher: ${f.plainPct(e.hit20 * 100, 0)}${all}${sixty}`;
}

/** Platz einer Aktie (ISIN) in der Rangfolge oder null, wenn sie keine Top-10-Nennung hat. */
export function placeOf(result: TopResult, isin: string): TopEntry | null {
  return result.entries.find((e) => e.isin === isin) ?? null;
}
