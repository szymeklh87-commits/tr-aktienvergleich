/* Umschichtungs-Regel (ab Version 1.3, `rotation-v1`).
 *
 * Der Server rechnet die Regel für alle Varianten (Anzahl Aktien, Rhythmus, Trendzeitraum,
 * Startkapital) im Rückblick durch und wendet sie auf den neuesten Kursstand an. Die App zeigt die
 * Ergebnisse nur an: Sie wählt die Variante, ordnet Orders nach Umschichtungstagen und rechnet
 * Beträge auf einen selbst gewählten Depotwert um. Sie erzeugt keine eigenen Signale.
 */

import type { Point } from './chartmath';
import * as f from './format';
import type { RotationAction, RotationIndex, RotationPreview, RotationReason, RotationRhythm, RotationVariant, RotationVariantInfo } from './types';

export interface VariantChoice {
  holdings: number;
  rhythm: RotationRhythm;
  lookback: number;
  capital: number;
}

export function variantKey(choice: VariantChoice): string {
  return `n${choice.holdings}-${choice.rhythm}-w${choice.lookback}-k${Math.round(choice.capital)}`;
}

/** Standardvariante des Servers (Fallback: erste gerechnete Variante). */
export function defaultChoice(index: RotationIndex): VariantChoice {
  const info = index.varianten.find((v) => v.key === index.standard) ?? index.varianten[0];
  if (!info) return { holdings: 5, rhythm: 'monatlich', lookback: 13, capital: 10000 };
  return { holdings: info.aktien, rhythm: info.rhythmus, lookback: info.trend_wochen, capital: info.kapital };
}

/** Variante aus den Adressparametern n, r, w, k; Unbekanntes fällt auf den Standard zurück. */
export function parseChoice(params: URLSearchParams, index: RotationIndex): VariantChoice {
  const base = defaultChoice(index);
  const rule = index.regel;
  const pickNumber = (raw: string | null, allowed: number[], fallback: number): number => {
    if (raw === null || !/^\d{1,9}$/.test(raw)) return fallback;
    const value = Number(raw);
    return allowed.includes(value) ? value : fallback;
  };
  const rhythmRaw = params.get('r');
  const rhythm = rhythmRaw === 'monatlich' || rhythmRaw === 'woechentlich' ? rhythmRaw : null;
  return {
    holdings: pickNumber(params.get('n'), rule.aktien, base.holdings),
    rhythm: rhythm && rule.rhythmus.includes(rhythm) ? rhythm : base.rhythm,
    lookback: pickNumber(params.get('w'), rule.trend_wochen, base.lookback),
    capital: pickNumber(params.get('k'), rule.kapital, base.capital),
  };
}

export function variantInfo(index: RotationIndex, key: string): RotationVariantInfo | null {
  return index.varianten.find((v) => v.key === key) ?? null;
}

export function rhythmLabel(rhythm: RotationRhythm): string {
  return rhythm === 'woechentlich' ? 'Wöchentlich' : 'Monatlich';
}

export function rhythmText(rhythm: RotationRhythm): string {
  return rhythm === 'woechentlich' ? 'jeden Freitag' : 'am ersten Freitag im Monat';
}

export function lookbackText(weeks: number): string {
  if (weeks === 13) return '13 Wochen (etwa 3 Monate)';
  if (weeks === 4) return '4 Wochen (etwa 1 Monat)';
  return f.plural(weeks, 'Woche', 'Wochen');
}

export function targetShare(holdings: number): number {
  return holdings > 0 ? 1 / holdings : 0;
}

export function actionLabel(action: RotationAction): string {
  switch (action) {
    case 'kauf':
      return 'Kaufen';
    case 'verkauf':
      return 'Verkaufen';
    case 'aufstocken':
      return 'Aufstocken';
    case 'reduzieren':
      return 'Teilweise verkaufen';
  }
}

export function actionPast(action: RotationAction): string {
  switch (action) {
    case 'kauf':
      return 'Kauf';
    case 'verkauf':
      return 'Verkauf';
    case 'aufstocken':
      return 'Aufgestockt';
    case 'reduzieren':
      return 'Teilverkauf';
  }
}

export function isSell(action: RotationAction): boolean {
  return action === 'verkauf' || action === 'reduzieren';
}

/** Begründung einer Änderung im Tagesvorschlag, in den Worten der Regel. */
export function reasonText(reason: RotationReason, ctx: { rank: number | null; holdings: number; keepFactor: number; band: number; before: number | null }): string {
  const buffer = ctx.holdings * ctx.keepFactor;
  switch (reason) {
    case 'nicht_mehr_kandidat':
      return 'erfüllt die Auswahl nicht mehr (Umsatz, Kursdaten oder Tagessprung)';
    case 'platz_ausserhalb_puffer':
      return `nur noch Platz ${ctx.rank ?? '–'} – gehalten wird bis Platz ${buffer}`;
    case 'anteil_angleichen':
      return `Anteil ${f.plainPct((ctx.before ?? 0) * 100, 1)} liegt mehr als ${f.integer(ctx.band * 100)} Prozentpunkte neben dem Ziel von ${f.plainPct(targetShare(ctx.holdings) * 100, 0)}`;
    case 'neu_unter_den_besten':
      return `Platz ${ctx.rank ?? '–'} der Rangliste, noch nicht im Regeldepot`;
  }
}

export interface Holding {
  idx: number;
  shares: number | null;
  value: number | null;
  share: number | null;
  since: number;
  basis: number | null;
  ret: number | null;
  rank: number | null;
  trend: number | null;
}

export interface Change {
  idx: number;
  action: RotationAction;
  before: number | null;
  after: number | null;
  value: number | null;
  rank: number | null;
  trend: number | null;
  reason: RotationReason;
}

export interface Candidate {
  idx: number;
  rank: number;
  trend: number | null;
  usd: number | null;
  held: boolean;
}

export function holdings(p: RotationPreview): Holding[] {
  const b = p.bestand;
  return b.idx.map((idx, k) => ({
    idx,
    shares: b.stueck[k],
    value: b.wert[k],
    share: b.anteil[k],
    since: b.seit[k],
    basis: b.einstand[k],
    ret: b.rendite[k],
    rank: b.platz[k],
    trend: b.trend[k],
  }));
}

/** Änderungen in Ausführungsreihenfolge: erst Verkäufe (bringen Geld), dann Käufe. */
export function changes(p: RotationPreview): Change[] {
  const a = p.aenderungen;
  const rows = a.idx.map((idx, k) => ({
    idx,
    action: a.aktion[k],
    before: a.anteil_vorher[k],
    after: a.anteil_nachher[k],
    value: a.wert[k],
    rank: a.platz[k],
    trend: a.trend[k],
    reason: a.grund[k],
  }));
  const order: Record<RotationAction, number> = { verkauf: 0, reduzieren: 1, aufstocken: 2, kauf: 3 };
  return rows.map((row, k) => ({ row, k })).sort((x, y) => order[x.row.action] - order[y.row.action] || x.k - y.k).map((x) => x.row);
}

export function candidates(p: RotationPreview): Candidate[] {
  const r = p.rangliste;
  return r.idx.map((idx, k) => ({ idx, rank: r.platz[k], trend: r.trend[k], usd: r.umsatz_usd[k], held: r.gehalten[k] }));
}

/** Betrag auf einen anderen Depotwert umgerechnet (gleiche Anteile). */
export function scaled(value: number | null, depotValue: number | null, own: number | null): number | null {
  if (value === null) return null;
  if (own === null || depotValue === null || !(depotValue > 0)) return value;
  return (value * own) / depotValue;
}

export const OWN_DEPOT_MIN = 100;
export const OWN_DEPOT_MAX = 100_000_000;

/** Liest einen Eurobetrag wie „12.500“, „12500,50“ oder „12 500 €“; null bei ungültiger Eingabe. */
export function parseEuro(text: string): number | null {
  const cleaned = text.replace(/[€\s  ]/g, '');
  if (!cleaned || !/^\d{1,3}(\.\d{3})*(,\d{1,2})?$|^\d+(,\d{1,2})?$/.test(cleaned)) return null;
  const value = Number(cleaned.replace(/\./g, '').replace(',', '.'));
  if (!Number.isFinite(value) || value < OWN_DEPOT_MIN || value > OWN_DEPOT_MAX) return null;
  return Math.round(value * 100) / 100;
}

export interface OrderRow {
  idx: number;
  execDay: number;
  action: RotationAction;
  value: number | null;
  before: number | null;
  after: number | null;
  rank: number | null;
  trend: number | null;
  fee: number | null;
  spread: number | null;
  tax: number | null;
  gain: number | null;
}

export interface RebalanceDay {
  /** Prüftag der Entscheidung */
  day: number;
  /** frühester Handelstag der Ausführung */
  execDay: number;
  orders: OrderRow[];
  fees: number;
  taxes: number;
  gains: number;
}

/** Orders je Umschichtungstag, neueste zuerst; Tage ohne Order erscheinen nicht. */
export function rebalanceDays(v: RotationVariant): RebalanceDay[] {
  const o = v.orders;
  const byDay = new Map<number, RebalanceDay>();
  o.tag.forEach((day, k) => {
    let entry = byDay.get(day);
    const execDay = o.ausfuehrung?.[k] ?? day;
    if (!entry) {
      entry = { day, execDay, orders: [], fees: 0, taxes: 0, gains: 0 };
      byDay.set(day, entry);
    }
    entry.execDay = Math.min(entry.execDay, execDay);
    entry.orders.push({
      idx: o.idx[k],
      execDay,
      action: o.aktion[k],
      value: o.wert[k],
      before: o.anteil_vorher[k],
      after: o.anteil_nachher[k],
      rank: o.platz[k],
      trend: o.trend[k],
      fee: o.gebuehr[k],
      spread: o.spanne[k],
      tax: o.steuer[k],
      gain: o.gewinn[k],
    });
    entry.fees += (o.gebuehr[k] ?? 0) + (o.spanne[k] ?? 0);
    entry.taxes += o.steuer[k] ?? 0;
    entry.gains += o.gewinn[k] ?? 0;
  });
  return [...byDay.values()].sort((a, b) => b.day - a.day);
}

/** Verlaufslinie im Punktformat der Diagramme; fehlende Werte werden ausgelassen, nicht ersetzt. */
export function curve(days: number[], values: (number | null)[]): Point[] {
  const out: Point[] = [];
  days.forEach((day, k) => {
    const value = values[k];
    if (value !== null && Number.isFinite(value) && value > 0) out.push({ day, close: value, open: null, high: null, low: null, volume: null, closeRaw: null });
  });
  return out;
}

/** Zeile der Vergleichstabelle (alle Varianten mit gleichem Startkapital). */
export interface CompareRow {
  info: RotationVariantInfo;
  label: string;
}

export function compareRows(index: RotationIndex, capital: number): CompareRow[] {
  return index.varianten
    .filter((v) => v.kapital === capital)
    .map((info) => ({ info, label: `${info.aktien} Aktien, ${rhythmLabel(info.rhythmus).toLowerCase()}, Trend ${info.trend_wochen} Wochen` }))
    .sort((a, b) => a.info.aktien - b.info.aktien || a.info.rhythmus.localeCompare(b.info.rhythmus) || b.info.trend_wochen - a.info.trend_wochen);
}

/** Kurzer Satz zur beschlossenen bzw. nächsten Umschichtung. */
export function nextText(p: RotationPreview | null): string {
  if (!p) return '';
  if (p.beschlossen_am !== null) {
    return `Beschlossen zum Schlusskurs vom ${f.dayLong(p.beschlossen_am)}, umgesetzt zum Schlusskurs des nächsten Handelstags. Danach entscheidet die Regel wieder am ${f.dayLong(p.naechste_entscheidung)}.`;
  }
  return `Nächste Entscheidung: ${f.dayLong(p.naechste_entscheidung)} zum Schlusskurs, umgesetzt am nächsten Handelstag.`;
}

/** Überschrift der Änderungsliste. */
export function changesTitle(p: RotationPreview): string {
  return p.beschlossen_am !== null ? 'Was die Regel jetzt umsetzt' : 'Was die Regel nach heutigem Stand ändern würde';
}

/** Rückblickzeitraum in Monaten (gerundet), für Überschriften. */
export function spanMonths(days: number | null | undefined): number | null {
  if (days === null || days === undefined || !(days > 0)) return null;
  return Math.max(1, Math.round(days / 30.44));
}

export interface Slot {
  /** Instrumentindex; null = Bargeld */
  idx: number | null;
  share: number;
  kind: 'halten' | 'angleichen' | 'neu' | 'bargeld';
}

/** Aufteilung des Regeldepots heute (Positionen nach Wert, dann Bargeld). */
export function allocationNow(p: RotationPreview): Slot[] {
  const total = p.depotwert ?? 0;
  const slots: Slot[] = holdings(p).map((h) => ({ idx: h.idx, share: h.share ?? 0, kind: 'halten' as const }));
  const cash = total > 0 && p.bargeld !== null ? Math.max(0, p.bargeld / total) : 0;
  if (cash > 0.0005) slots.push({ idx: null, share: cash, kind: 'bargeld' });
  return slots;
}

/** Ungefähre Aufteilung nach den Änderungen (vor Kosten und Steuern), nach derselben Regel wie
 * auf dem Server: Verkäufe und Teilverkäufe bringen Geld, Käufe und Aufstockungen bekommen je 1/N;
 * reicht das Geld nicht, werden sie gleichmäßig gekürzt. */
export function allocationAfter(p: RotationPreview, holdingsCount: number): Slot[] {
  const target = targetShare(holdingsCount);
  const total = p.depotwert ?? 0;
  let cash = total > 0 && p.bargeld !== null ? Math.max(0, p.bargeld / total) : 0;
  const weights = new Map<number, number>(holdings(p).map((h) => [h.idx, h.share ?? 0]));
  const kinds = new Map<number, Slot['kind']>();
  const wanted: [number, number][] = [];
  for (const c of changes(p)) {
    const current = weights.get(c.idx) ?? 0;
    if (c.action === 'verkauf') {
      cash += current;
      weights.delete(c.idx);
    } else if (c.action === 'reduzieren') {
      cash += current - target;
      weights.set(c.idx, target);
      kinds.set(c.idx, 'angleichen');
    } else if (c.action === 'aufstocken') {
      wanted.push([c.idx, target - current]);
      kinds.set(c.idx, 'angleichen');
    } else {
      wanted.push([c.idx, target]);
      kinds.set(c.idx, 'neu');
    }
  }
  const need = wanted.reduce((sum, [, amount]) => sum + amount, 0);
  const scale = need > 0 ? Math.min(1, cash / need) : 0;
  for (const [idx, amount] of wanted) {
    weights.set(idx, (weights.get(idx) ?? 0) + amount * scale);
    cash -= amount * scale;
  }
  const slots: Slot[] = [...weights.entries()].map(([idx, share]) => ({ idx, share, kind: kinds.get(idx) ?? 'halten' }));
  const order: Record<Slot['kind'], number> = { halten: 0, angleichen: 0, neu: 1, bargeld: 2 };
  slots.sort((a, b) => order[a.kind] - order[b.kind]);
  if (cash > 0.0005) slots.push({ idx: null, share: cash, kind: 'bargeld' });
  return slots;
}
