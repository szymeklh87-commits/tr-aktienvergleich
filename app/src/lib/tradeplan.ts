/* Kaufsignal nach fester Regel (ab 1.21.0, „signalregel-1“): Der Server rechnet je Aktie Status, Einstiegslimit,
 * Stop, Kursziel und Chance-Risiko-Verhältnis aus den Schlusskursen; die App entscheidet zusätzlich, ob die Daten
 * aktuell und geprüft genug für ein Kaufsignal sind. Ohne aktuelle, geprüfte Daten: KEIN KAUF – gleich was der Server
 * gerechnet hat (Simons Auftrag vom 07.11.2026, Punkt 10: erst die Kursaktualisierung, dann Kaufsignale).
 *
 * Ohne Browser prüfbar (tests/tradeplan.test.ts). */

import { lastOfficialSuccess, officialFailure } from './freshness';
import * as f from './format';
import { thresholdUsd, turnoverOf } from './turnover';
import type { Instruments, Manifest, PlanCheck, PlanStatus, SignalsData, Status } from './types';

/** Hinweis-Bits, die einem Kaufsignal widersprechen (Datenvertrag, Codetabelle im Manifest). */
export const BLOCKING_WARNINGS: Record<number, string> = {
  13: 'Starke Kursbewegung an einem Tag ohne belegten Umsatz',
  18: 'Kurskorrektur des Anbieters ausstehend',
};

export type GateKind = 'offen' | 'demo' | 'veraltet' | 'ungeprueft' | 'fehlt';

export interface SignalGate {
  /** Kaufsignale dürfen als solche gezeigt werden */
  open: boolean;
  kind: GateKind;
  /** Kurzer Grund für „KEIN KAUF“ (null, wenn offen) */
  reason: string | null;
  /** Kursstand, auf dem die Signale beruhen (ISO-Datum) */
  session: string | null;
}

export interface GateInput {
  status: Status | null | undefined;
  manifest: Manifest | null | undefined;
  signals: SignalsData | null | undefined;
  isDemo: boolean;
  now?: number;
}

const DATE = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' });

export function isoDe(iso: string | null | undefined): string {
  if (!iso) return '–';
  const ms = Date.parse(`${iso.slice(0, 10)}T12:00:00Z`);
  return Number.isFinite(ms) ? DATE.format(new Date(ms)) : '–';
}

/** Dürfen heute Kaufsignale gezeigt werden? Reihenfolge der Gründe: Signale fehlen, DEMO, ungeprüfte Grundlage, nicht
 * der neueste offizielle Stand, neuere Schlusskurse berechenbar (veraltet), offizieller Lauf gescheitert. */
export function signalGate({ status, manifest, signals, isDemo, now = Date.now() }: GateInput): SignalGate {
  const session = signals?.kursstand ?? null;
  const closed = (kind: GateKind, reason: string): SignalGate => ({ open: false, kind, reason, session });
  if (!signals?.handel) return closed('fehlt', 'Für diesen Signal-Stand gibt es noch keine Signalregel – sie kommt mit dem nächsten täglichen Lauf.');
  if (isDemo) return closed('demo', 'DEMO – synthetische Testdaten. Die Beispiele zeigen nur, wie ein Signal aussähe; es ist kein echtes Kaufsignal.');
  if (manifest?.art === 'zwischenstand' && manifest.zwischenstand?.basis_geprueft === false) {
    return closed('ungeprueft', 'Der angezeigte Zwischenstand rechnet mit ungeprüften Schlusskursen.');
  }
  const officialId = status?.offiziell?.snapshot_id ?? status?.latest_official_snapshot_id ?? null;
  if (officialId && signals.snapshot_id !== officialId) {
    return closed('veraltet', `Die Signale beruhen auf dem Stand vom ${isoDe(session)}, es gibt einen neueren Stand mit Schlusskursen – neue Signale kommen mit dem Job „Kennzahlen“.`);
  }
  const next = status?.naechster_kursstand ?? null;
  const ready = next?.ab_utc ? Date.parse(next.ab_utc) : NaN;
  if (Number.isFinite(ready) && now >= ready) {
    return closed('veraltet', `Die Schlusskurse vom ${isoDe(next?.datum)} sind da, aber noch nicht geprüft veröffentlicht. Signale vom ${isoDe(session)} gelten nicht mehr.`);
  }
  const failure = officialFailure(status);
  if (failure) return closed('veraltet', 'Der tägliche Lauf ist zuletzt gescheitert – die Daten gelten nicht als aktuell.');
  const beat = lastOfficialSuccess(status);
  const maxAge = (status?.heartbeat_max_age_hours ?? 30) * 3_600_000;
  if (beat && now - Date.parse(beat) > maxAge) return closed('veraltet', 'Der tägliche Lauf hat sich zu lange nicht erfolgreich gemeldet.');
  return { open: true, kind: 'offen', reason: null, session };
}

export interface Candidate {
  /** Index im Signal-Stand */
  k: number;
  isin: string;
  /** Index im Datenstand (instruments) oder -1 */
  idx: number;
  status: PlanStatus;
  /** Status nach Daten- und Aktienprüfung der App (ein Kaufsignal kann hier zu „kein_kauf“ werden) */
  shown: PlanStatus;
  reason: string;
  entry: number | null;
  stop: number | null;
  target: number | null;
  targetBasis: '2R' | 'analysten' | null;
  crv: number | null;
  late: boolean;
  total: number | null;
  /** Aktueller Kurs aus dem Zwischenstand (vorläufig) und ob er schon über dem Einstiegslimit liegt */
  livePrice: number | null;
  liveLate: boolean;
}

/** Kurs nicht bestätigt (ab 1.22, Befund F03: in den Ranglisten sichtbar kennzeichnen): Hinweis-Bit 13 oder 18 oder eine
 * Abweichung am zweiten Börsenplatz – Grund als kurzer Satz, sonst null. Kein Kaufsignal (siehe ``stockIssue``). */
export function priceUnconfirmed(instruments: Instruments | null | undefined, idx: number): string | null {
  if (!instruments || idx < 0) return null;
  const warnings = instruments.warnings[idx] ?? 0;
  for (const [bit, text] of Object.entries(BLOCKING_WARNINGS)) {
    if (warnings & (1 << Number(bit))) return text;
  }
  const venue = instruments.venue;
  if (venue) {
    const pos = venue.idx.indexOf(idx);
    if (pos >= 0 && venue.status[pos] === 'abweichung') return 'Kurs am zweiten Börsenplatz weicht ab';
  }
  return null;
}

/** Mindestumsatz regulärer Kaufkandidaten (ab 1.23.0, Simons Vorgabe vom 07.11.2026, dauerhaft): Ø Tagesumsatz der letzten
 * 20 Sitzungen nachgewiesen und mindestens 10 Mio. USD – aus dem Datenstand, also derselben Rechnung wie die Ranglisten. */
export const MIN_TURNOVER_RULE = 'mindestens 10 Mio. USD pro Handelstag (Ø 20 Sitzungen, nachgewiesen)';

/** Die Bedingung „Ø Tagesumsatz“ der Signalregel aus dem Datenstand (ersetzt die Zeile des Signal-Stands, die bis
 * Signalregel 1 mit 1 Mio. € rechnete). null, wenn der Datenstand keinen Umsatz enthält. */
export function turnoverCheck(instruments: Instruments | null | undefined, idx: number, manifest?: Manifest | null): PlanCheck | null {
  if (!instruments?.turnover || idx < 0) return null;
  const info = turnoverOf(instruments, idx);
  if (!info) return null;
  const threshold = thresholdUsd(manifest ?? null);
  const proven = info.status === 'ok' && info.usd !== null;
  const why = manifest?.codes.turnover_status?.[info.status]?.kurz ?? 'nicht bestimmbar';
  return {
    key: 'umsatz',
    label: 'Ø Tagesumsatz',
    ok: info.liquid && proven && (info.usd ?? 0) >= threshold,
    wert: proven ? `${f.money(info.usd, 'USD')} je Handelstag` : `nicht nachgewiesen (${why})`,
    regel: MIN_TURNOVER_RULE,
    gruppe: 'basis',
  };
}

/** Bedingungen eines Handelsplans für die Anzeige: die Umsatzzeile kommt aus dem Datenstand (siehe ``turnoverCheck``). */
export function shownChecks(checks: PlanCheck[], instruments: Instruments | null | undefined, idx: number, manifest?: Manifest | null): PlanCheck[] {
  const own = turnoverCheck(instruments, idx, manifest);
  if (!own) return checks;
  return checks.some((c) => c.key === 'umsatz') ? checks.map((c) => (c.key === 'umsatz' ? own : c)) : [own, ...checks];
}

/** Prüfungen der App je Aktie: Kurs am Stichtag vorhanden, Mindestumsatz nachgewiesen (ab 1.23.0), keine widersprechenden
 * Hinweise, zweiter Börsenplatz ohne Abweichung (Befund F03: nicht bestätigte Kurse nie als Kaufsignal). */
export function stockIssue(instruments: Instruments | null | undefined, idx: number): string | null {
  if (!instruments || idx < 0) return 'Aktie im angezeigten Datenstand nicht gefunden';
  if (instruments.level_status[idx] !== 0) return 'Kein geprüfter Schlusskurs am Stichtag';
  const liquid = instruments.turnover?.liquid;
  if (liquid && !liquid[idx]) return 'Ø Tagesumsatz unter 10 Mio. USD oder nicht nachgewiesen – kein regulärer Kaufkandidat';
  const warnings = instruments.warnings[idx] ?? 0;
  for (const [bit, text] of Object.entries(BLOCKING_WARNINGS)) {
    if (warnings & (1 << Number(bit))) return text;
  }
  const venue = instruments.venue;
  if (venue) {
    const pos = venue.idx.indexOf(idx);
    if (pos >= 0 && venue.status[pos] === 'abweichung') return 'Kurs am zweiten Börsenplatz weicht ab – nicht bestätigt';
  }
  return null;
}

export interface CandidateOptions {
  gate: SignalGate;
  instruments: Instruments | null | undefined;
  /** ISIN → Index im Datenstand */
  index: Map<string, number>;
  /** Vorläufiger Kurs je Index aus einem Zwischenstand (geprüfte Grundlage), sonst leer */
  live?: Map<number, number>;
  limit?: number;
}

/** Kaufkandidaten in der Reihenfolge des Servers (erst Kaufsignale, dann „beobachten“, je nach Gesamtwertung), mit den
 * Prüfungen der App. Bei geschlossenem Tor wird jedes Kaufsignal zu „kein_kauf“ (der Plan bleibt zur Ansicht). */
export function candidates(signals: SignalsData, { gate, instruments, index, live, limit = 10 }: CandidateOptions): Candidate[] {
  const h = signals.handel;
  if (!h) return [];
  const order = signals.listen.handel ?? [];
  const out: Candidate[] = [];
  for (const k of order) {
    const isin = signals.isin[k];
    const idx = index.get(isin) ?? -1;
    // ab 1.23 (Simons Vorgabe vom 07.11.2026, dauerhaft): reguläre Kaufkandidaten nur mit nachgewiesenem Ø Tagesumsatz ab
    // 10 Mio. USD – Aktien darunter oder ohne bestimmbaren Umsatz erscheinen hier nicht
    const liquid = instruments?.turnover?.liquid;
    if (liquid && (idx < 0 || !liquid[idx])) continue;
    const status = h.status[k];
    let shown: PlanStatus = status;
    let reason = h.grund[k];
    const issue = stockIssue(instruments, idx);
    const price = live?.get(idx) ?? null;
    const entry = h.einstieg[k];
    const stop = h.stop[k];
    const liveLate = price !== null && entry !== null && price > entry;
    if (issue) {
      shown = 'kein_kauf';
      reason = issue;
    } else if (status === 'kaufsignal' && price !== null && stop !== null && price <= stop) {
      shown = 'kein_kauf';
      reason = 'Aktueller Kurs am oder unter dem Stop – Signal hinfällig';
    } else if (status === 'kaufsignal' && liveLate) {
      shown = 'beobachten';
      reason = 'Einstieg zu spät – aktueller Kurs liegt über dem Einstiegslimit';
    }
    // Geschlossenes Tor: kein Kaufsignal. Ausnahme DEMO – dort bleibt der Status als gekennzeichnetes Beispiel stehen
    // (die Startseite zeigt trotzdem „KEIN KAUF“, die Liste „DEMO-Beispiel“ in der Farbe der DEMO-Hinweise)
    if (!gate.open && shown === 'kaufsignal' && gate.kind !== 'demo') {
      shown = 'kein_kauf';
      reason = gate.reason ?? 'Daten nicht aktuell';
    }
    out.push({
      k,
      isin,
      idx,
      status,
      shown,
      reason,
      entry,
      stop,
      target: h.ziel[k],
      targetBasis: h.ziel_basis[k],
      crv: h.crv[k],
      late: h.zu_spaet[k] || liveLate,
      total: signals.gesamt?.[k] ?? null,
      livePrice: price,
      liveLate,
    });
    if (out.length >= limit) break;
  }
  const rank: Record<PlanStatus, number> = { kaufsignal: 0, beobachten: 1, kein_kauf: 2 };
  return out.sort((a, b) => rank[a.shown] - rank[b.shown]);
}

/** Das stärkste geprüfte Kaufsignal (erster Kandidat mit Status „kaufsignal“ nach allen Prüfungen) oder null – nur bei
 * offenem Tor (aktuelle, geprüfte, echte Daten). */
export function strongest(list: Candidate[], gate: SignalGate | null): Candidate | null {
  if (!gate?.open) return null;
  return list.find((c) => c.shown === 'kaufsignal') ?? null;
}

export const STATUS_LABEL: Record<PlanStatus, string> = {
  kaufsignal: 'Kaufsignal',
  beobachten: 'Beobachten',
  kein_kauf: 'Kein Kauf',
};

/** „2,0 : 1“ */
export function crvText(crv: number | null | undefined): string {
  if (crv === null || crv === undefined || !Number.isFinite(crv)) return '–';
  return `${crv.toFixed(1).replace('.', ',')} : 1`;
}
