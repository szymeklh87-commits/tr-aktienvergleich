/* Einschätzung je Aktie direkt am angezeigten Kurs (ab 1.24.0, Simons Aufträge vom 07.11.2026, 17:09–17:42 Uhr).
 *
 * Kaufzeitpunkt (🟢 Günstiger Einstieg · 🟡 Abwarten · 🔴 Kein Kaufsignal · ⚪ Nicht beurteilbar) entsteht nur aus der
 * getesteten Signalregel des Servers (Status, Einstiegslimit, Stop, Ziel zum Schlusskurs) und dem gerade angezeigten Kurs:
 *   • Grün nur, wenn der Server ein Kaufsignal gerechnet hat und der Kurs zwischen Stop und Einstiegslimit liegt –
 *     ein gefallener Kurs allein macht nie grün (ohne Kaufsignal bleibt es gelb oder rot).
 *   • Über dem Einstiegslimit: Abwarten, mit dem Limit als Marke. Am oder unter dem Stop: Kein Kaufsignal.
 *   • Ohne aktuelle, geprüfte Daten (Signal-Tor geschlossen, Kurs nicht bestätigt, kein Plan): Nicht beurteilbar.
 * Die Kursbasis steht immer dabei: aktueller Kurs, verzögerter Kurs oder Schlusskurs.
 *
 * Eigene Position (🔵 Halten · 🔴 Verkaufen): dieselbe Regel ab dem eigenen Einstandskurs – Stop = Einstand − 2 ATR,
 * Ziel = Einstand + 2 R; am Stop oder Ziel verkaufen, dazwischen halten.
 *
 * Ohne Browser prüfbar (tests/bewertung.test.ts). */

import * as f from './format';
import { quoteStatus, type LiveQuote } from './livekurse';
import type { Backtest, BacktestStats, PlanStatus, RiskLevel, SignalsData } from './types';

export type EntryLight = 'guenstig' | 'abwarten' | 'kein' | 'unklar';

export const ENTRY_LABEL: Record<EntryLight, string> = {
  guenstig: 'Günstiger Einstieg',
  abwarten: 'Abwarten',
  kein: 'Kein Kaufsignal',
  unklar: 'Nicht beurteilbar',
};

export const ENTRY_EMOJI: Record<EntryLight, string> = { guenstig: '🟢', abwarten: '🟡', kein: '🔴', unklar: '⚪' };

export type BasisKind = 'aktuell' | 'verzoegert' | 'vorlaeufig' | 'boerse_zu' | 'schluss';

/** Der Kurs, an dem bewertet wird, mit seiner Zeitangabe. */
export interface PriceBasis {
  kind: BasisKind;
  price: number | null;
  unit: string | null;
  /** Kurszeit (ms UTC), wenn bekannt */
  time: number | null;
  /** Handelstag des Schlusskurses (Tagnummer), wenn Schlusskursbasis */
  day: number | null;
  /** „Kurs 18,20 USD · 15:42 Uhr, 15 Min. verzögert“ */
  label: string;
  /** Hinweis zur Basis (null nur bei einem aktuellen Kurs ohne Verzögerung) */
  note: string | null;
}

export interface BasisInput {
  close: number | null;
  closeDay: number | null;
  unit: string | null;
  quote?: LiveQuote | null;
  /** vorläufiger Kurs eines geprüften Zwischenstands */
  provisional?: { price: number; timeIso: string | null } | null;
  now?: number;
}

const CLOCK = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Berlin' });

function clock(ms: number): string {
  return `${CLOCK.format(new Date(ms))} Uhr`;
}

function sameUnit(a: string | null | undefined, b: string | null | undefined): boolean {
  return !a || !b || a === b;
}

/** Bewertungsbasis: geprüfter aktueller Kurs (Jetzt aktualisieren) vor vorläufigem Zwischenstand vor Schlusskurs. */
export function priceBasis({ close, closeDay, unit, quote = null, provisional = null, now = Date.now() }: BasisInput): PriceBasis {
  const closeBasis = (note: string): PriceBasis => ({
    kind: 'schluss',
    price: close,
    unit,
    time: null,
    day: closeDay,
    label: close !== null ? `Schlusskurs ${f.price(close, unit)} vom ${f.day(closeDay)}` : 'kein Schlusskurs',
    note,
  });
  if (quote && Number.isFinite(quote.price) && quote.price > 0 && sameUnit(quote.unit, unit)) {
    const st = quoteStatus(quote, now);
    const shown = f.price(quote.price, quote.unit ?? unit);
    if (st.state === 'aktuell') {
      const delay = quote.delayMin ?? 0;
      return {
        kind: delay > 0 ? 'verzoegert' : 'aktuell',
        price: quote.price,
        unit: quote.unit ?? unit,
        time: quote.quoteTime,
        day: null,
        label: `Kurs ${shown} · ${clock(quote.quoteTime)}${delay > 0 ? `, ${f.integer(delay)} Min. verzögert` : ''}`,
        note: delay > 0 ? `Bewertung auf verzögerter Kursbasis (${f.integer(delay)} Min.)` : null,
      };
    }
    if (st.state === 'boerse_zu') {
      return {
        kind: 'boerse_zu',
        price: quote.price,
        unit: quote.unit ?? unit,
        time: quote.quoteTime,
        day: null,
        label: `Letzter Kurs ${shown} · ${clock(quote.quoteTime)}`,
        note: 'Börse geschlossen – Bewertung mit dem letzten Kurs',
      };
    }
    return closeBasis('Aktueller Einstieg nicht beurteilbar (abgerufener Kurs veraltet) – Einschätzung auf Schlusskursbasis');
  }
  if (provisional && Number.isFinite(provisional.price) && provisional.price > 0) {
    const ms = provisional.timeIso ? Date.parse(provisional.timeIso) : NaN;
    return {
      kind: 'vorlaeufig',
      price: provisional.price,
      unit,
      time: Number.isFinite(ms) ? ms : null,
      day: null,
      label: `Vorläufiger Kurs ${f.price(provisional.price, unit)}${Number.isFinite(ms) ? ` · ${clock(ms)}` : ''}`,
      note: 'Bewertung auf verzögerter Kursbasis (Zwischenstand)',
    };
  }
  return closeBasis('Einschätzung auf Schlusskursbasis');
}

export interface PlanInput {
  status: PlanStatus;
  reason: string;
  entry: number | null;
  stop: number | null;
  target: number | null;
  late: boolean;
}

export interface EntryInput {
  /** Signal-Tor der App; ``kind === 'demo'`` bewertet zur Ansicht, kennzeichnet aber als DEMO */
  gate: { open: boolean; kind: string; reason: string | null } | null;
  /** Prüfung der App je Aktie (``stockIssue``) */
  issue: string | null;
  plan: PlanInput | null;
  basis: PriceBasis;
}

export interface EntryAssessment {
  light: EntryLight;
  label: string;
  /** ein Satz mit den Marken */
  reason: string;
  /** Kurzform für Listen */
  short: string;
  demo: boolean;
  price: number | null;
  /** Kurs zum Einstiegslimit (Anteil, + = darüber) */
  vsEntry: number | null;
  /** möglicher Verlust bis zum Stop (Anteil, negativ) */
  toStop: number | null;
  /** mögliche Steigerung bis zum Ziel (Anteil) */
  toTarget: number | null;
  basisNote: string | null;
}

const LIQUIDITY_HINT = 'Ø Tagesumsatz';

function ratio(a: number | null, b: number | null): number | null {
  return a !== null && b !== null && b > 0 && Number.isFinite(a) ? a / b - 1 : null;
}

/** Kaufzeitpunkt am angezeigten Kurs. */
export function assessEntry({ gate, issue, plan, basis }: EntryInput): EntryAssessment {
  const unit = basis.unit;
  const price = basis.price;
  const demo = gate?.kind === 'demo';
  const make = (light: EntryLight, reason: string, short: string): EntryAssessment => ({
    light,
    label: ENTRY_LABEL[light],
    reason,
    short,
    demo,
    price,
    vsEntry: plan ? ratio(price, plan.entry) : null,
    toStop: plan && price !== null && plan.stop !== null ? ratio(plan.stop, price) : null,
    toTarget: plan && price !== null && plan.target !== null ? ratio(plan.target, price) : null,
    basisNote: basis.note,
  });
  if (!gate) return make('unklar', 'Signal-Stand wird geladen.', 'lädt');
  if (!gate.open && !demo) return make('unklar', gate.reason ?? 'Daten nicht aktuell genug für eine Bewertung.', 'Daten nicht aktuell');
  if (issue) {
    if (issue.startsWith(LIQUIDITY_HINT)) return make('kein', issue, 'Umsatz unter 10 Mio. USD');
    return make('unklar', issue, 'Kurs nicht bestätigt');
  }
  if (!plan) return make('unklar', 'Für diese Aktie gibt es im Signal-Stand keinen Handelsplan (zu kurze Kurshistorie oder ohne Kurs).', 'ohne Handelsplan');
  if (price === null) return make('unklar', 'Kein Kurs für eine Bewertung vorhanden.', 'ohne Kurs');
  if (plan.status === 'kein_kauf') return make('kein', plan.reason || 'Die Bedingungen der Signalregel sind nicht erfüllt.', 'Regel nicht erfüllt');
  if (plan.status === 'beobachten') {
    const why = (plan.reason || 'einzelne Bedingungen fehlen').replace(/\.$/, '');
    return make('abwarten', `Noch kein Kaufsignal: ${why}.`, plan.late ? 'zu spät' : 'noch kein Signal');
  }
  // Kaufsignal zum Schlusskurs – jetzt am angezeigten Kurs prüfen
  if (plan.late) return make('abwarten', `Einstieg zu spät: ${plan.reason}`, 'zu spät');
  if (plan.stop !== null && price <= plan.stop) {
    return make('kein', `Kurs ${f.price(price, unit)} am oder unter dem Stop ${f.price(plan.stop, unit)} – das Signal ist hinfällig.`, 'unter dem Stop');
  }
  if (plan.entry !== null && price > plan.entry) {
    return make(
      'abwarten',
      `Kurs ${f.price(price, unit)} über dem Einstiegslimit ${f.price(plan.entry, unit)} – Kauf erst bei ${f.price(plan.entry, unit)} oder darunter (Limit-Order).`,
      `über Limit ${f.price(plan.entry, unit)}`,
    );
  }
  const stop = plan.stop !== null ? `, Stop ${f.price(plan.stop, unit)}` : '';
  const target = plan.target !== null ? `, Ziel ${f.price(plan.target, unit)}` : '';
  return make('guenstig', `Kurs ${f.price(price, unit)} im Kaufbereich bis zum Einstiegslimit ${f.price(plan.entry, unit)}${stop}${target}.`, `bis ${f.price(plan.entry, unit)}`);
}

/* ---------------------------------------------------------------- eigene Position */

export type PositionLight = 'halten' | 'verkaufen' | 'unklar';

export const POSITION_LABEL: Record<PositionLight, string> = { halten: 'Halten', verkaufen: 'Verkaufen', unklar: 'Nicht beurteilbar' };
export const POSITION_EMOJI: Record<PositionLight, string> = { halten: '🔵', verkaufen: '🔴', unklar: '⚪' };

export interface Position {
  /** Einstandskurs je Aktie in der Notierungseinheit */
  kurs: number;
  einheit: string | null;
  /** Kaufdatum JJJJ-MM-TT (freiwillig) */
  datum: string | null;
}

export interface PositionInput {
  position: Position;
  basis: PriceBasis;
  /** ATR in Prozent des Schlusskurses (Signal-Stand) und dieser Schlusskurs */
  atrPct: number | null;
  close: number | null;
  stopAtr: number;
  targetR: number;
}

export interface PositionAssessment {
  light: PositionLight;
  label: string;
  reason: string;
  stop: number | null;
  target: number | null;
  /** Gewinn oder Verlust seit Einstand (Anteil, ohne Kosten) */
  pnl: number | null;
}

/** Halten oder Verkaufen ab dem eigenen Einstandskurs – dieselben Stop- und Zielmarken wie die getestete Signalregel. */
export function assessPosition({ position, basis, atrPct, close, stopAtr, targetR }: PositionInput): PositionAssessment {
  const unit = basis.unit;
  const none = (reason: string): PositionAssessment => ({ light: 'unklar', label: POSITION_LABEL.unklar, reason, stop: null, target: null, pnl: null });
  if (!(position.kurs > 0)) return none('Einstandskurs fehlt.');
  if (!sameUnit(position.einheit, unit)) return none(`Einstandskurs in ${position.einheit}, Kurs in ${unit} – bitte in der Einheit des Kurses eingeben.`);
  if (basis.price === null) return none('Kein Kurs für eine Bewertung vorhanden.');
  if (atrPct === null || close === null || !(atrPct > 0) || !(close > 0)) return none('Tagesschwankung (ATR) unbekannt – Stop und Ziel nicht berechenbar.');
  const atr = atrPct * close;
  const stop = position.kurs - stopAtr * atr;
  const target = position.kurs + targetR * (position.kurs - stop);
  const pnl = basis.price / position.kurs - 1;
  const base = { stop, target, pnl };
  if (basis.price <= stop) {
    return { ...base, light: 'verkaufen', label: POSITION_LABEL.verkaufen, reason: `Kurs ${f.price(basis.price, unit)} am oder unter dem Stop ${f.price(stop, unit)} (Einstand − ${f.integer(stopAtr)} ATR) – Verkaufen nach der Regel.` };
  }
  if (basis.price >= target) {
    return { ...base, light: 'verkaufen', label: POSITION_LABEL.verkaufen, reason: `Kursziel ${f.price(target, unit)} (Einstand + ${f.integer(targetR)} R) erreicht – Gewinn nach der Regel mitnehmen.` };
  }
  return {
    ...base,
    light: 'halten',
    label: POSITION_LABEL.halten,
    reason: `Kurs zwischen Stop ${f.price(stop, unit)} und Ziel ${f.price(target, unit)} – ${pnl >= 0 ? 'Gewinn' : 'Verlust'} bisher ${f.pct(pnl, 1)} (ohne Kosten und Steuern).`,
  };
}

/* ---------------------------------------------------------------- Rückblick der Regel */

/** Haltedauern für Anzeige: Handelstage → Beschriftung. */
export const HOLD_LABELS: [string, string][] = [
  ['1', '1 Tag'],
  ['5', '5 Tage'],
  ['10', '10 Tage'],
  ['20', '20 Tage'],
  ['21', '1 Monat'],
  ['63', '3 Monate'],
  ['126', '6 Monate'],
  ['252', '12 Monate'],
];

export const STATUS_GROUP: Record<PlanStatus, 'kaufsignal' | 'beobachten' | 'vergleich'> = {
  kaufsignal: 'kaufsignal',
  beobachten: 'beobachten',
  kein_kauf: 'vergleich',
};

export const GROUP_TITLE = {
  kaufsignal: 'Frühere Kaufsignale dieser Regel',
  beobachten: 'Frühere „Beobachten“-Fälle dieser Regel',
  vergleich: 'Alle Aktien mit Mindestumsatz (Vergleich)',
} as const;

/** „Ø +1,2 % nach 10 Tagen, Trefferquote 54 % (312 Fälle)“ – oder warum keine Aussage möglich ist. */
export function statsText(stats: BacktestStats | null | undefined, horizon: string, min: number): string {
  if (!stats || !stats.n) return `nach ${horizon}: keine Fälle`;
  if (!stats.belegt || stats.mittel === undefined || stats.treffer === undefined) return `nach ${horizon}: erst ${f.integer(stats.n)} Fälle – zu wenige für eine Aussage (mindestens ${f.integer(min)})`;
  return `nach ${horizon} Ø ${f.pct(stats.mittel, 1)}, Trefferquote ${f.plainPct(stats.treffer * 100, 0)} (${f.integer(stats.n)} Fälle)`;
}

export interface HistoryRow {
  key: string;
  label: string;
  stats: BacktestStats | null;
}

/** Zeilen des Rückblicks für den Status einer Aktie: Kaufsignal mit Plan (Stop/Ziel) und Haltedauern, sonst Haltedauern. */
export function historyRows(bt: Backtest | null | undefined, status: PlanStatus | null): { group: 'kaufsignal' | 'beobachten' | 'vergleich'; plan: HistoryRow[]; hold: HistoryRow[] } | null {
  if (!bt) return null;
  const group = STATUS_GROUP[status ?? 'kein_kauf'];
  const g = bt.status[group];
  if (!g) return null;
  const plan = group === 'kaufsignal' && g.plan ? HOLD_LABELS.filter(([k]) => k in (g.plan ?? {})).map(([key, label]) => ({ key, label, stats: g.plan?.[key] ?? null })) : [];
  const hold = HOLD_LABELS.map(([key, label]) => ({ key, label, stats: g.halten[key] ?? null }));
  return { group, plan, hold };
}

/** Ein Satz für die Übersicht: wie liefen Fälle mit demselben Status bisher nach 10 Handelstagen (Plan bzw. Halten)? */
export function historySentence(bt: Backtest | null | undefined, status: PlanStatus | null): string | null {
  const rows = historyRows(bt, status);
  if (!rows || !bt) return null;
  const row = (rows.plan.length ? rows.plan : rows.hold).find((r) => r.key === '10');
  if (!row) return null;
  const how = rows.plan.length ? ' mit Stop und Ziel' : '';
  const ok = Boolean(row.stats?.belegt);
  return `${GROUP_TITLE[rows.group]}${how}, ${statsText(row.stats, '10 Handelstagen', bt.mindestens_faelle)}${ok ? ', nach Kosten' : ''}.`;
}

export interface OwnHistory {
  n: number;
  mittel: number | null;
  treffer: number | null;
  belegt: boolean;
  text: string;
}

/** Frühere Kaufsignale genau dieser Aktie (Plan, 10 Handelstage). */
export function ownHistory(data: SignalsData | null | undefined, k: number): OwnHistory | null {
  const own = data?.rueckblick_eigen;
  if (!own || k < 0 || k >= own.n.length) return null;
  const n = own.n[k] ?? 0;
  const min = data?.rueckblick?.mindestens_faelle_aktie ?? 10;
  const mittel = own.mittel[k] ?? null;
  const treffer = own.treffer[k] ?? null;
  const belegt = n >= min && mittel !== null && treffer !== null;
  const text = !n
    ? 'Bei dieser Aktie gab es im Rückblick kein Kaufsignal.'
    : belegt
      ? `Bei dieser Aktie: ${f.integer(n)} frühere Kaufsignale, nach 10 Handelstagen Ø ${f.pct(mittel, 1)}, Trefferquote ${f.plainPct((treffer ?? 0) * 100, 0)}.`
      : `Bei dieser Aktie nur ${f.integer(n)} frühere Kaufsignale – zu wenige für eine Aussage (mindestens ${f.integer(min)}).`;
  return { n, mittel, treffer, belegt, text };
}

/* ---------------------------------------------------------------- Risiko */

export const RISK_LABEL: Record<RiskLevel, string> = { niedrig: 'Risiko niedrig', mittel: 'Risiko mittel', hoch: 'Risiko hoch', unbekannt: 'Risiko nicht beurteilbar' };

export interface RiskView {
  level: RiskLevel;
  label: string;
  reasons: string[];
  complete: boolean;
}

export function riskOf(data: SignalsData | null | undefined, k: number): RiskView | null {
  const r = data?.risiko;
  if (!r || k < 0 || k >= r.stufe.length) return null;
  const level = r.stufe[k] ?? 'unbekannt';
  return { level, label: RISK_LABEL[level] ?? RISK_LABEL.unbekannt, reasons: (r.gruende[k] ?? []).slice(0, 3), complete: Boolean(r.vollstaendig[k]) };
}

/* ---------------------------------------------------------------- Lage zum Kurs */

/** Lage des Kurses zu den Durchschnittslinien und Hochs (nur Werte aus dem Signal-Stand, keine Schätzung). */
export function positionLines(data: SignalsData, k: number, price: number | null, unit: string | null): string[] {
  if (price === null) return [];
  const m = data.merkmale;
  const val = (key: string): number | null => {
    const v = m[key]?.[k];
    return v !== null && v !== undefined && Number.isFinite(v) ? v : null;
  };
  const out: string[] = [];
  const sma20 = val('sma20');
  const sma50 = val('sma50');
  if (sma20 !== null) out.push(`${price >= sma20 ? 'über' : 'unter'} der 20-Tage-Linie (${f.price(sma20, unit)}, ${f.pct(price / sma20 - 1, 1)})`);
  if (sma50 !== null) out.push(`${price >= sma50 ? 'über' : 'unter'} der 50-Tage-Linie (${f.price(sma50, unit)}, ${f.pct(price / sma50 - 1, 1)})`);
  const high20 = val('hoch20');
  if (high20 !== null) out.push(`${f.pct(price / high20 - 1, 1)} zum 20-Tage-Hoch (${f.price(high20, unit)})`);
  const high250 = val('hoch250');
  if (high250 !== null) out.push(`${f.pct(price / high250 - 1, 1)} zum 52-Wochen-Hoch (${f.price(high250, unit)})`);
  return out;
}
