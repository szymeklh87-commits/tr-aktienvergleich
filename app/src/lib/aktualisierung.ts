/* „Jetzt aktualisieren“ aus der App (ab 1.21): Anfragen, Fortschritt, automatische Aktualisierung – reine Funktionen.
 *
 * Zwei Wege:
 *   Kurse einzelner Aktien (Aktie mit Kursverlauf, Merkliste, Depot, sichtbare Aktien): Workflow „aktualisieren.yml“,
 *     Lieferung verschlüsselt über den Branch „kurse-aktuell“ – zuerst die sichtbaren Aktien, dann der Rest.
 *   Gesamter Datenbestand: der tägliche Lauf als Zwischenstand („taeglich.yml“, wie bisher über GitHub), neue Daten über
 *     die Website. */

export const WORKFLOW_KURSE = 'aktualisieren.yml';
export const WORKFLOW_ALLES = 'taeglich.yml';
export const DELIVERY_BRANCH = 'kurse-aktuell';
export const REQUEST_SCHEMA = 'tr-aktualisierung-anfrage/1';
export const MAX_VALUES = 250;
export const MAX_COURSES = 3;

export type UpdateScope = 'aktie' | 'merkliste' | 'depot' | 'sichtbar' | 'auswahl' | 'alles';
export type JobPhase = 'senden' | 'wartet' | 'laeuft' | 'teil' | 'fertig' | 'fehler' | 'ohne_ergebnis';

export interface UpdateJob {
  kennung: string;
  scope: UpdateScope;
  label: string;
  isins: string[];
  automatic: boolean;
  requestedAt: number;
  dispatchedAt: number | null;
  runId: number | null;
  runUrl: string | null;
  runStartedAt: number | null;
  phase: JobPhase;
  stepName: string | null;
  stepIndex: number;
  stepCount: number;
  partsReceived: number;
  partsTotal: number | null;
  quotesReceived: number;
  missing: number;
  finishedAt: number | null;
  error: string | null;
  /** Gesamter Datenbestand: Stand, der vor dem Start veröffentlicht war (zum Erkennen des neuen) */
  baselineSnapshot?: string | null;
}

const DIGITS = '0123456789abcdefghijklmnopqrstuvwxyz';

/** Kennung wie im Server erwartet: „k“ + Sekunden (Basis 36) + „-“ + 16 Zufallszeichen. */
export function newKennung(now = Date.now(), random: (n: number) => Uint8Array = (n) => crypto.getRandomValues(new Uint8Array(n))): string {
  const stamp = Math.floor(now / 1000).toString(36);
  const tail = Array.from(random(16), (b) => DIGITS[b % 36]).join('');
  return `k${stamp}-${tail}`;
}

export interface RequestValue {
  isin: string;
  symbol: string;
}

export function requestPayload(kennung: string, scope: Exclude<UpdateScope, 'alles'>, values: RequestValue[], visible: number, courses: string[], now = Date.now()) {
  const unique: RequestValue[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    if (seen.has(value.isin)) continue;
    seen.add(value.isin);
    unique.push(value);
    if (unique.length >= MAX_VALUES) break;
  }
  return {
    schema: REQUEST_SCHEMA,
    kennung,
    erstellt_utc: new Date(Math.floor(now / 1000) * 1000).toISOString().replace('.000Z', 'Z'),
    umfang: scope,
    werte: unique,
    sichtbar: Math.max(0, Math.min(visible, unique.length)),
    kursverlauf: courses.filter((isin) => seen.has(isin)).slice(0, MAX_COURSES),
  };
}

export function requestAad(kennung: string): string {
  return `anfrage/${kennung}`;
}

export function deliveryPath(kennung: string, part: number): string {
  return `aktuell/${kennung}-${part}.bin`;
}

export function errorPath(kennung: string): string {
  return `aktuell/${kennung}-fehler.json`;
}

/** Werte für eine Anfrage: nur Aktien mit Yahoo-Symbol; Reihenfolge bleibt (sichtbare zuerst). */
export function valuesFor(isins: string[], symbolOf: (isin: string) => string | null): { values: RequestValue[]; without: string[] } {
  const values: RequestValue[] = [];
  const without: string[] = [];
  for (const isin of isins) {
    const symbol = symbolOf(isin);
    if (symbol && /^[A-Za-z0-9.^=-]{1,24}$/.test(symbol)) values.push({ isin, symbol });
    else without.push(isin);
  }
  return { values, without };
}

export const ERROR_TEXTS: Record<string, string> = {
  anfrage_zu_alt: 'Die Anfrage kam zu spät beim Server an (älter als 20 Minuten). Bitte noch einmal tippen.',
  anfrage_nicht_entschluesselbar: 'Der Server konnte die Anfrage nicht entschlüsseln – die Passphrase in der App passt nicht zum Datenstand.',
  zeit_ungueltig: 'Die Uhrzeit des Handys weicht zu stark ab. Uhrzeit automatisch stellen lassen und noch einmal versuchen.',
  kein_schluessel: 'Dem Server fehlt der Datenschlüssel (Secret DATA_PASSPHRASE).',
  zu_viele_werte: 'Zu viele Aktien auf einmal (höchstens 250).',
  keine_werte: 'Für diese Aktien kennt die App kein Kurssymbol.',
};

export function errorFor(code: string): string {
  return ERROR_TEXTS[code] ?? `Der Server hat die Anfrage abgelehnt (Grund: ${code}).`;
}

/** Übliche Dauern (Messung vom 30.10.2026, Läufe 41037525075 und 41055711727): Grundlage der Restzeit-Schätzung. */
export const TYPICAL_SECONDS = { kurse: 30, alles: 140 };

export interface ProgressInfo {
  title: string;
  detail: string;
  /** 0–1, wenn sich der Fortschritt schätzen lässt */
  fraction: number | null;
  done: boolean;
  failed: boolean;
}

function seconds(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s`;
}

export function progress(job: UpdateJob, now = Date.now()): ProgressInfo {
  const elapsed = seconds((job.finishedAt ?? now) - job.requestedAt);
  const typical = job.scope === 'alles' ? TYPICAL_SECONDS.alles : TYPICAL_SECONDS.kurse;
  const estimate = Math.min(0.95, ((job.finishedAt ?? now) - job.requestedAt) / 1000 / typical);
  switch (job.phase) {
    case 'senden':
      return { title: 'Anfrage wird gesendet', detail: `seit ${elapsed}`, fraction: 0.02, done: false, failed: false };
    case 'wartet':
      return { title: 'Wartet auf einen GitHub-Rechner', detail: `angefordert vor ${elapsed} – meist 5–30 s`, fraction: Math.min(estimate, 0.15), done: false, failed: false };
    case 'laeuft': {
      const step = job.stepName ? `Schritt ${job.stepIndex} von ${job.stepCount}: ${job.stepName}` : 'Lauf gestartet';
      return { title: job.scope === 'alles' ? 'Daten werden aktualisiert' : 'Kurse werden abgerufen', detail: `${step} – seit ${elapsed}`, fraction: Math.max(0.15, estimate), done: false, failed: false };
    }
    case 'teil':
      return {
        title: `Teil ${job.partsReceived} von ${job.partsTotal ?? '?'} angekommen`,
        detail: `${job.quotesReceived} Kurse aktualisiert, die übrigen folgen – seit ${elapsed}`,
        fraction: job.partsTotal ? Math.max(estimate, job.partsReceived / job.partsTotal) : estimate,
        done: false,
        failed: false,
      };
    case 'fertig':
      return {
        title: job.scope === 'alles' ? 'Neuer Datenstand ist da' : 'Kurse aktualisiert',
        detail: job.scope === 'alles' ? `nach ${elapsed}` : `${job.quotesReceived} Kurse${job.missing ? `, ${job.missing} ohne Kurs` : ''} – nach ${elapsed}`,
        fraction: 1,
        done: true,
        failed: false,
      };
    case 'ohne_ergebnis':
      return { title: 'Lauf beendet – nichts Neues', detail: job.error ?? `nach ${elapsed}`, fraction: 1, done: true, failed: false };
    case 'fehler':
    default:
      return { title: 'Aktualisierung fehlgeschlagen', detail: job.error ?? 'Unbekannter Fehler', fraction: null, done: true, failed: true };
  }
}

/** Schrittname aus dem Workflow in kurzes Deutsch. */
export function stepLabel(name: string): string {
  const lower = name.toLowerCase();
  if (lower.startsWith('set up job') || lower.startsWith('run actions/checkout') || lower.startsWith('run actions/setup-python')) return 'Rechner wird vorbereitet';
  if (lower.includes('zwischenspeicher') || lower.includes('abhängigkeiten') || lower.includes('umgebung')) return 'Programme werden geladen';
  if (lower.includes('schlüsselparameter')) return 'Schlüssel wird geladen';
  if (lower.includes('kurse abrufen')) return 'Kurse werden abgerufen und geliefert';
  if (lower.startsWith('täglicher lauf')) return 'Kurse abrufen und alles neu rechnen';
  if (lower.includes('veröffentlichte dateien prüfen')) return 'Dateien werden geprüft';
  if (lower.includes('website')) return 'Website wird bereitgestellt';
  if (lower.includes('sichern')) return 'Daten werden gesichert';
  if (lower.startsWith('post ') || lower.startsWith('complete job')) return 'Lauf wird abgeschlossen';
  return name;
}

// ------------------------------------------------------------------ Automatische Aktualisierung

export interface AutoSettings {
  /** Minuten zwischen automatischen Kursabrufen während der Nutzung; 0 = aus */
  minutes: number;
}

export const AUTO_CHOICES = [0, 5, 10, 15, 30, 60];
export const AUTO_DEFAULT = 15;
export const AUTO_MAX_PER_HOUR = 6;
export const IDLE_STOP_MS = 10 * 60_000;

export interface AutoInput {
  now: number;
  settings: AutoSettings;
  visible: boolean;
  lastInteraction: number;
  lastAutomatic: number | null;
  automaticTimes: number[];
  running: boolean;
  failuresInRow: number;
  /** mindestens eine der betroffenen Börsen handelt gerade (ungefähr, siehe marketMaybeOpen) */
  marketOpen: boolean;
  hasAccess: boolean;
  count: number;
}

export type AutoDecision = { due: true } | { due: false; reason: string };

/** Soll jetzt automatisch aktualisiert werden? Nur sichtbar, bei Nutzung, während des Handels, höchstens 6-mal je Stunde. */
export function autoDue(input: AutoInput): AutoDecision {
  if (!input.hasAccess) return { due: false, reason: 'kein Zugang eingerichtet' };
  if (input.settings.minutes <= 0) return { due: false, reason: 'ausgeschaltet' };
  if (!input.visible) return { due: false, reason: 'App im Hintergrund' };
  if (input.now - input.lastInteraction > IDLE_STOP_MS) return { due: false, reason: 'seit 10 Minuten nicht benutzt' };
  if (input.running) return { due: false, reason: 'Aktualisierung läuft schon' };
  if (input.failuresInRow >= 3) return { due: false, reason: 'drei Fehler nacheinander – pausiert bis zum nächsten Tippen' };
  if (!input.count) return { due: false, reason: 'keine Aktien sichtbar' };
  if (!input.marketOpen) return { due: false, reason: 'Börsen geschlossen' };
  if (input.lastAutomatic !== null && input.now - input.lastAutomatic < input.settings.minutes * 60_000) return { due: false, reason: 'noch nicht fällig' };
  if (input.automaticTimes.filter((t) => input.now - t < 3_600_000).length >= AUTO_MAX_PER_HOUR) return { due: false, reason: 'Obergrenze je Stunde erreicht' };
  return { due: true };
}

/** Handelszeiten (Ortszeit) der wichtigsten Kalender – nur für die Entscheidung, ob ein automatischer Abruf lohnt. */
const HOURS: Record<string, [string, number, number]> = {
  XNYS: ['America/New_York', 9.5, 16], XNAS: ['America/New_York', 9.5, 16], XTSE: ['America/Toronto', 9.5, 16],
  XETR: ['Europe/Berlin', 9, 17.5], XFRA: ['Europe/Berlin', 8, 22], XLON: ['Europe/London', 8, 16.5], XPAR: ['Europe/Paris', 9, 17.5],
  XAMS: ['Europe/Amsterdam', 9, 17.5], XMIL: ['Europe/Rome', 9, 17.5], XMAD: ['Europe/Madrid', 9, 17.5], XSWX: ['Europe/Zurich', 9, 17.5],
  XSTO: ['Europe/Stockholm', 9, 17.5], XCSE: ['Europe/Copenhagen', 9, 17], XHEL: ['Europe/Helsinki', 10, 18.5], XOSL: ['Europe/Oslo', 9, 16.5],
  XWBO: ['Europe/Vienna', 9, 17.5], XWAR: ['Europe/Warsaw', 9, 17], XBRU: ['Europe/Brussels', 9, 17.5], XLIS: ['Europe/Lisbon', 8, 16.5],
  XTKS: ['Asia/Tokyo', 9, 15.5], XHKG: ['Asia/Hong_Kong', 9.5, 16], XASX: ['Australia/Sydney', 10, 16], XSES: ['Asia/Singapore', 9, 17],
};

function localHour(tz: string, now: number): { weekday: number; hour: number } | null {
  try {
    const parts = new Intl.DateTimeFormat('en-US', { timeZone: tz, weekday: 'short', hour: 'numeric', minute: 'numeric', hourCycle: 'h23' }).formatToParts(new Date(now));
    const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
    const weekday = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].indexOf(get('weekday'));
    return { weekday, hour: Number(get('hour')) + Number(get('minute')) / 60 };
  } catch {
    return null;
  }
}

/** Ungefähr: läuft an der Börse dieses Kalenders gerade der Handel (Mo–Fr, übliche Zeiten, ohne Feiertage)? Unbekannte
 * Kalender: werktags 8–22 Uhr Berliner Zeit. */
export function marketMaybeOpen(calendar: string | null | undefined, now = Date.now()): boolean {
  const [tz, open, close] = HOURS[calendar ?? ''] ?? ['Europe/Berlin', 8, 22];
  const local = localHour(tz, now);
  if (!local) return true;
  return local.weekday >= 1 && local.weekday <= 5 && local.hour >= open && local.hour < close + 0.5;
}
