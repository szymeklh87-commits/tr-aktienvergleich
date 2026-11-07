/* „Jetzt aktualisieren“ für einzelne Aktien (ab 1.21; ab 1.22 ohne Zugang in der App) – reine Funktionen.
 *
 * Kurse einzelner Aktien (Aktie mit Kursverlauf, Merkliste, Depot, sichtbare Aktien): Workflow „aktualisieren.yml“. Die App
 * verschlüsselt die Anfrage und kopiert sie als eine Zeile „<Kennung>.<verschlüsselt>“; gestartet wird auf GitHub mit der
 * eigenen Anmeldung („Run workflow“, Zeile einfügen). Die Lieferung kommt verschlüsselt über den Branch „kurse-aktuell“ –
 * zuerst die sichtbaren Aktien, dann der Rest. Den gesamten Datenbestand aktualisiert weiterhin der tägliche Lauf
 * („taeglich.yml“, Start ebenfalls auf GitHub), neue Daten kommen über die Website. */

export const WORKFLOW_KURSE = 'aktualisieren.yml';
export const DELIVERY_BRANCH = 'kurse-aktuell';
export const REQUEST_SCHEMA = 'tr-aktualisierung-anfrage/1';
export const MAX_VALUES = 250;
export const MAX_COURSES = 3;

export type UpdateScope = 'aktie' | 'merkliste' | 'depot' | 'sichtbar' | 'auswahl';
/** start: Zeile vorbereitet, Start auf GitHub steht aus · wartet: Lauf angelegt · laeuft · teil: erste Lieferung da */
export type JobPhase = 'start' | 'wartet' | 'laeuft' | 'teil' | 'fertig' | 'fehler' | 'ohne_ergebnis';

export interface UpdateJob {
  kennung: string;
  scope: UpdateScope;
  label: string;
  isins: string[];
  requestedAt: number;
  /** GitHub geöffnet (Kopieren und Öffnen) – ab hier sucht die App den Lauf */
  openedAt: number | null;
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
  /** zuletzt gelesener Stand des Lieferkanals (Commit) – neue Teile erst bei einem neuen Stand suchen */
  lastHead?: string | null;
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

/** Zeile zum Einfügen auf GitHub: Kennung und verschlüsselter Text (Base64), getrennt durch einen Punkt. */
export function eingabeZeile(kennung: string, base64: string): string {
  return `${kennung}.${base64}`;
}

/** GitHub erlaubt für alle Eingaben eines Laufs zusammen höchstens 65.535 Zeichen. */
export const MAX_EINGABE = 65_000;

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
  anfrage_zu_alt: 'Die Anfrage wurde zu spät auf GitHub gestartet (älter als 20 Minuten). Bitte neu anfordern und gleich starten.',
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
export const TYPICAL_SECONDS = { kurse: 30 };

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
  const end = job.finishedAt ?? now;
  const elapsed = seconds(end - job.requestedAt);
  const since = job.openedAt ?? job.requestedAt;
  const estimate = Math.min(0.95, (end - since) / 1000 / TYPICAL_SECONDS.kurse);
  switch (job.phase) {
    case 'start':
      return {
        title: 'Start auf GitHub',
        detail: job.openedAt
          ? `GitHub geöffnet vor ${seconds(now - job.openedAt)} – dort „Run workflow“, Zeile einfügen, starten. Die App sucht den Lauf, sobald sie wieder sichtbar ist.`
          : 'Zeile kopieren und GitHub öffnen – dort „Run workflow“, Zeile einfügen, starten.',
        fraction: null,
        done: false,
        failed: false,
      };
    case 'wartet':
      return { title: 'Wartet auf einen GitHub-Rechner', detail: `Lauf angelegt – meist 5–30 s (seit ${elapsed})`, fraction: Math.min(estimate, 0.15), done: false, failed: false };
    case 'laeuft': {
      const step = job.stepName ? `Schritt ${job.stepIndex} von ${job.stepCount}: ${job.stepName}` : 'Lauf gestartet';
      return { title: 'Kurse werden abgerufen', detail: `${step} – seit ${elapsed}`, fraction: Math.max(0.15, estimate), done: false, failed: false };
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
        title: 'Kurse aktualisiert',
        detail: `${job.quotesReceived} Kurse${job.missing ? `, ${job.missing} ohne Kurs` : ''} – nach ${elapsed}`,
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
