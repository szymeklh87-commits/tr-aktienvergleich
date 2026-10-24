/* Aktualität verständlich (ab 1.17): Wie neu sind die angezeigten Kurse, wann kommt der nächste Stand, und was tun,
 * wenn eine Aktualisierung gescheitert ist? Grundlage sind status.json (vom Server, auch nach einem roten Lauf
 * veröffentlicht) und der angezeigte Stand. Ohne Browser prüfbar (tests/freshness.test.ts).
 *
 * Simons Auftrag vom 24.10.2026: „Zeige Datenstand und Aktualisierungsfehler verständlich in der App an.“ */

import type { Status } from './types';

export type FreshnessTone = 'ok' | 'info' | 'warn';

export interface FreshnessProblem {
  /** fehlgeschlagen: letzter Lauf rot · ueberfaellig: neuer Stand fehlt · stumm: Server meldet sich nicht (zeigt die App
   * schon als Hinweis oben auf jeder Seite) */
  kind: 'fehlgeschlagen' | 'ueberfaellig' | 'stumm';
  title: string;
  text: string;
  todo: string;
}

export interface Freshness {
  tone: FreshnessTone;
  /** Eine Zeile: wie aktuell die angezeigten Kurse sind */
  headline: string;
  /** Was als Nächstes passiert (nächster Stand, geplante Läufe) */
  next: string | null;
  /** Etwas stimmt nicht – mit Erklärung und nächstem Schritt */
  problem: FreshnessProblem | null;
}

/** So lange nach „neuer Stand berechenbar“ gilt ein fehlender Stand noch als unterwegs (GitHub verzögert geplante
 * Läufe um bis zu 5½ Stunden, gemessen 15.–23.10.2026; dazu die Laufzeit). Danach: überfällig. */
export const OVERDUE_HOURS = 12;
const HOUR = 3_600_000;
const FAILED = new Set(['fehlgeschlagen', 'abgebrochen']);

const weekdayDate = new Intl.DateTimeFormat('de-DE', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' });
const weekdayBerlin = new Intl.DateTimeFormat('de-DE', { weekday: 'long', timeZone: 'Europe/Berlin' });
const dateBerlin = new Intl.DateTimeFormat('de-DE', { day: 'numeric', month: 'long', timeZone: 'Europe/Berlin' });
const clockBerlin = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Berlin' });
const ymdBerlin = new Intl.DateTimeFormat('en-CA', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'Europe/Berlin' });

/** „Freitag, 23. Oktober“ für ein Datum „2026-10-23“. */
export function sessionName(iso: string | null | undefined): string {
  if (!iso) return '–';
  const ms = Date.parse(`${iso.slice(0, 10)}T12:00:00Z`);
  return Number.isFinite(ms) ? weekdayDate.format(new Date(ms)) : '–';
}

/** Zeitpunkt in Berliner Zeit relativ zu jetzt: „heute, 00:37 Uhr“, „morgen, 07:00 Uhr“, „Dienstag, 27. Oktober, 07:00 Uhr“. */
export function whenBerlin(ms: number, now: number): string {
  const clock = `${clockBerlin.format(new Date(ms))} Uhr`;
  const day = ymdBerlin.format(new Date(ms));
  if (day === ymdBerlin.format(new Date(now))) return `heute, ${clock}`;
  if (day === ymdBerlin.format(new Date(now + 24 * HOUR))) return `morgen, ${clock}`;
  if (day === ymdBerlin.format(new Date(now - 24 * HOUR))) return `gestern, ${clock}`;
  return `${weekdayBerlin.format(new Date(ms))}, ${dateBerlin.format(new Date(ms))}, ${clock}`;
}

function berlinOffsetMinutes(ms: number): number {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Europe/Berlin', hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    .formatToParts(new Date(ms))
    .reduce<Record<string, string>>((acc, p) => ((acc[p.type] = p.value), acc), {});
  const asUtc = Date.UTC(Number(parts.year), Number(parts.month) - 1, Number(parts.day), Number(parts.hour) % 24, Number(parts.minute));
  return Math.round((asUtc - Math.floor(ms / 60000) * 60000) / 60000);
}

/** Nächster Start nach ``now``: Nachtlauf (UTC-Uhrzeit, Wochentage 1 = Montag … 7 = Sonntag) bzw. Morgenlauf (Berliner Uhrzeit, täglich). */
export function nextNightRun(status: Status | null | undefined, now: number): number | null {
  const time = status?.schedule?.nachtlauf_utc;
  const days = status?.schedule?.nachtlauf_wochentage;
  if (!time || !/^\d{2}:\d{2}$/.test(time) || !days?.length) return null;
  const [h, m] = time.split(':').map(Number);
  for (let k = 0; k <= 8; k++) {
    const d = new Date(now + k * 24 * HOUR);
    const at = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), h, m);
    const iso = ((new Date(at).getUTCDay() + 6) % 7) + 1;
    if (at > now && days.includes(iso)) return at;
  }
  return null;
}

export function nextMorningRun(status: Status | null | undefined, now: number): number | null {
  const time = status?.schedule?.uhrzeit;
  if (!time || !/^\d{2}:\d{2}$/.test(time)) return null;
  const [h, m] = time.split(':').map(Number);
  for (let k = -1; k <= 2; k++) {
    const d = new Date(now + k * 24 * HOUR);
    const local = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), h, m);
    const at = local - berlinOffsetMinutes(local) * 60000;
    if (at > now) return at;
  }
  return null;
}

/** Technische Meldung des Laufs in Alltagssprache (die Originalmeldung steht unter „Datenstand & Betrieb“). */
export function plainReason(message: string | null | undefined): string | null {
  if (!message) return null;
  const m = message.toLowerCase();
  if (m.includes('drossel') || m.includes('429')) return 'Der Kursanbieter hat zu viele Abfragen auf einmal abgelehnt (Drosselung).';
  if (m.includes('zeitbudget') || m.includes('timeout') || m.includes('zeitüberschreitung')) return 'Die erlaubte Laufzeit war erreicht, bevor alle Kurse geladen waren.';
  if (m.includes('passphrase') || m.includes('entschlüssel') || m.includes('schlüssel')) return 'Die Verschlüsselung passte nicht – das Server-Geheimnis DATA_PASSPHRASE prüfen.';
  if (m.includes('teilstand') || m.includes('unvollständig') || m.includes('stichtagskurs')) return 'Für einige Börsen fehlten noch Schlusskurse.';
  if (m.includes('tr-liste') || m.includes('universum')) return 'Die Aktienliste von Trade Republic war nicht abrufbar oder wurde zur Prüfung zurückgehalten.';
  const short = message.length > 160 ? `${message.slice(0, 157)}…` : message;
  return short;
}

function schedulesText(status: Status | null | undefined, now: number): string {
  const night = nextNightRun(status, now);
  const morning = nextMorningRun(status, now);
  const parts: string[] = [];
  if (night !== null) parts.push(`Nachtlauf ${whenBerlin(night, now)}`);
  if (morning !== null) parts.push(`Morgenlauf ${whenBerlin(morning, now)}`);
  const list = parts.length ? `Geplant: ${parts.join(', ')}` : 'Geplant: täglicher Lauf';
  return `${list} – GitHub startet geplante Läufe oft einige Stunden später.`;
}

export interface FreshnessInput {
  status: Status | null | undefined;
  /** Kursstichtag des angezeigten Stands (ISO-Datum) */
  shownSession: string | null | undefined;
  /** Zwischenstand mit vorläufigen Kursen? */
  intraday?: boolean;
  now?: number;
}

export function freshness({ status, shownSession, intraday = false, now = Date.now() }: FreshnessInput): Freshness {
  const latest = status?.last_price_session ?? shownSession ?? null;
  const nextStand = status?.naechster_kursstand ?? null;
  const readyMs = nextStand?.ab_utc ? Date.parse(nextStand.ab_utc) : NaN;
  const run = status?.last_run ?? null;
  let tone: FreshnessTone = 'ok';
  let problem: FreshnessProblem | null = null;
  let next: string | null = null;

  const headline = intraday
    ? `Zwischenstand mit vorläufigen Kursen; letzte Schlusskurse vom ${sessionName(latest)}`
    : `Schlusskurse vom ${sessionName(shownSession ?? latest)}`;

  if (nextStand && Number.isFinite(readyMs)) {
    if (now < readyMs) {
      next = `Neue Schlusskurse (${sessionName(nextStand.datum)}) gibt es ab ${whenBerlin(readyMs, now)}. ${schedulesText(status, now)}`;
    } else if (now - readyMs < OVERDUE_HOURS * HOUR) {
      tone = 'info';
      next = `Die Schlusskurse vom ${sessionName(nextStand.datum)} sind seit ${whenBerlin(readyMs, now)} berechenbar und kommen mit dem nächsten Lauf. ${schedulesText(status, now)} Sofort geht es mit „Kurse jetzt aktualisieren“.`;
    } else {
      tone = 'warn';
      problem = {
        kind: 'ueberfaellig',
        title: 'Neuer Kursstand überfällig',
        text: `Die Schlusskurse vom ${sessionName(nextStand.datum)} hätten seit ${whenBerlin(readyMs, now)} berechnet werden können, sind aber noch nicht da. Meist hat GitHub den geplanten Lauf verzögert oder ausgelassen.`,
        todo: '„Kurse jetzt aktualisieren“ startet den Lauf sofort (etwa 20 bis 90 Minuten mit neuen Schlusskursen).',
      };
    }
  } else {
    next = schedulesText(status, now);
  }

  if (run && FAILED.has(run.status)) {
    tone = 'warn';
    const reason = plainReason(run.message);
    problem = {
      kind: 'fehlgeschlagen',
      title: 'Letzte Aktualisierung fehlgeschlagen',
      text: `Der Lauf von ${whenBerlin(Date.parse(run.finished_at_utc ?? run.started_at_utc), now)} ist nicht fertig geworden${reason ? `: ${reason}` : '.'} Angezeigt wird weiter der letzte geprüfte Stand.`,
      todo: 'Der nächste geplante Lauf versucht es von selbst noch einmal; sofort geht es mit „Kurse jetzt aktualisieren“. Bleibt es dabei, steht der genaue Grund auf GitHub unter Actions → Täglicher Lauf.',
    };
  } else if (run?.status === 'wartet_auf_provider' && !problem) {
    tone = tone === 'warn' ? tone : 'info';
    next = `Einige Börsen haben ihre Schlusskurse noch nicht geliefert; der Lauf versucht es von selbst erneut. ${next ?? ''}`.trim();
  }

  const beat = status?.last_successful_check_utc ? Date.parse(status.last_successful_check_utc) : NaN;
  const maxAge = (status?.heartbeat_max_age_hours ?? 30) * HOUR;
  if (status && Number.isFinite(beat) && now - beat > maxAge && !problem) {
    tone = 'warn';
    problem = {
      kind: 'stumm',
      title: 'Server meldet sich nicht',
      text: `Der tägliche Lauf hat sich zuletzt ${whenBerlin(beat, now)} erfolgreich gemeldet. Vielleicht hat GitHub den Zeitplan pausiert (nach 60 Tagen ohne Aktivität) oder Läufe ausgelassen.`,
      todo: '„Kurse jetzt aktualisieren“ startet einen Lauf; auf GitHub unter Actions → Täglicher Lauf zeigt „Enable workflow“, ob der Zeitplan ausgeschaltet ist.',
    };
  }
  return { tone, headline, next, problem };
}
