/* Daten auf Wunsch aktualisieren (ab 1.2).
 *
 * Ohne Zugang startet die App den Serverlauf nicht selbst (die App enthält keinen Schlüssel). Gestartet wird dann auf
 * GitHub mit der eigenen Anmeldung („Run workflow“). Ab 1.21 kann ein eigener, eng begrenzter Zugang hinterlegt werden
 * (state/UpdateState.tsx) – dann startet die App Läufe selbst und zeigt ihren Fortschritt.
 * Danach wartet die App: Sie liest status.json alle 15 Sekunden neu und meldet, sobald ein Lauf fertig ist –
 * mit neuem Kursstand oder mit dem Grund, warum es keinen gibt.
 */

import * as f from './format';
import type { Status } from './types';

const KEY = 'tr-aktualisierung-v1';
// Ab 1.12 alle 15 Sekunden (ein Zwischenstand dauert nur noch wenige Minuten; status.json ist klein)
export const POLL_MS = 15_000;
export const WAIT_MAX_MS = 3 * 60 * 60 * 1000;

export interface UpdateWait {
  since: number;
  baselineGenerated: string | null;
  baselineRun: string | null;
  baselineSnapshot: string | null;
  lastCheck: number | null;
}

export type UpdateOutcome = 'neuer_stand' | 'keine_neuen_daten' | 'lauf_beendet' | 'zeit_abgelaufen';

export interface UpdateResult {
  outcome: UpdateOutcome;
  at: number;
  status: Status | null;
}

export function waitFrom(status: Status | null, now = Date.now()): UpdateWait {
  return {
    since: now,
    baselineGenerated: status?.generated_at_utc ?? null,
    baselineRun: status?.last_run?.run_id ?? null,
    baselineSnapshot: status?.latest_snapshot_id ?? null,
    lastCheck: null,
  };
}

export function loadWait(now = Date.now()): UpdateWait | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<UpdateWait>;
    if (typeof value.since !== 'number' || !Number.isFinite(value.since) || now - value.since > WAIT_MAX_MS * 2) return null;
    const text = (x: unknown) => (typeof x === 'string' ? x : null);
    return {
      since: value.since,
      baselineGenerated: text(value.baselineGenerated),
      baselineRun: text(value.baselineRun),
      baselineSnapshot: text(value.baselineSnapshot),
      lastCheck: typeof value.lastCheck === 'number' ? value.lastCheck : null,
    };
  } catch {
    return null;
  }
}

export function saveWait(wait: UpdateWait | null): void {
  try {
    if (wait) localStorage.setItem(KEY, JSON.stringify(wait));
    else localStorage.removeItem(KEY);
  } catch {
    /* privater Modus: Warten gilt nur bis zum Schließen der App */
  }
}

/** Ergebnis, sobald sich seit Beginn des Wartens ein Lauf gemeldet hat (sonst null). */
export function outcomeFor(wait: UpdateWait, status: Status, now = Date.now()): UpdateOutcome | null {
  if (status.latest_snapshot_id && status.latest_snapshot_id !== wait.baselineSnapshot) return 'neuer_stand';
  const runChanged = (status.last_run?.run_id ?? null) !== wait.baselineRun || status.generated_at_utc !== wait.baselineGenerated;
  if (runChanged) return status.last_run?.status === 'keine_neuen_daten' ? 'keine_neuen_daten' : 'lauf_beendet';
  if (now - wait.since > WAIT_MAX_MS) return 'zeit_abgelaufen';
  return null;
}

const clockFmt = new Intl.DateTimeFormat('de-DE', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Berlin' });
const dayFmt = new Intl.DateTimeFormat('de-DE', { weekday: 'long', day: '2-digit', month: '2-digit', timeZone: 'Europe/Berlin' });

/** „14:05 Uhr“ in Berliner Zeit. */
export function clock(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return '–';
  return `${clockFmt.format(new Date(ms))} Uhr`;
}

/** „heute“, „morgen“ oder „Mittwoch, 14.10.“ – für einen Zeitpunkt in Berliner Zeit. */
export function relativeDay(ms: number, now = Date.now()): string {
  const key = (t: number) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' }).format(new Date(t));
  if (key(ms) === key(now)) return 'heute';
  if (key(ms) === key(now + 86_400_000)) return 'morgen';
  return dayFmt.format(new Date(ms));
}

export interface NextCutoff {
  /** Börsentag, dessen Schlusskurse als nächstes kommen. */
  sessionText: string;
  /** Ab wann ein Lauf ihn berechnen kann, z. B. „heute ab 23:00 Uhr“. */
  readyText: string;
  ready: boolean;
}

export function nextCutoff(status: Status | null, now = Date.now()): NextCutoff | null {
  const next = status?.naechster_kursstand;
  if (!next) return null;
  const at = Date.parse(next.ab_utc);
  if (!Number.isFinite(at)) return null;
  return {
    sessionText: f.dayLong(f.isoToDay(next.datum)),
    readyText: `${relativeDay(at, now)} ab ${clock(at)}`,
    ready: now >= at,
  };
}

/** Kurztext des Ergebnisses für Hinweisleiste und Ansicht. */
export function outcomeText(result: UpdateResult): { title: string; text: string } {
  const run = result.status?.last_run ?? null;
  const reason = run?.message ? ` ${run.message}` : '';
  switch (result.outcome) {
    case 'neuer_stand': {
      const intraday = result.status?.zwischenstand;
      if (intraday && result.status?.latest_snapshot_id === intraday.snapshot_id) {
        const at = Date.parse(intraday.kurse_bis_utc ?? '');
        return {
          title: 'Zwischenstand fertig',
          text: `Vorläufige Ranglisten mit Kursen vom ${f.isoDate(intraday.stichtag)} bis ${Number.isFinite(at) ? clock(at) : '–'} sind veröffentlicht.`,
        };
      }
      return {
        title: 'Aktualisierung fertig',
        text: `Neuer Kursstand vom ${f.isoDate(result.status?.last_price_session ?? null)} ist veröffentlicht.`,
      };
    }
    case 'keine_neuen_daten':
      return { title: 'Lauf beendet – keine neuen Kurse', text: `Seit dem letzten Stand ist kein weiterer Börsentag abgeschlossen.${reason}` };
    case 'lauf_beendet':
      return { title: `Lauf beendet: ${f.runStatus(run?.status)}`, text: reason.trim() || 'Der bisherige Stand bleibt sichtbar.' };
    case 'zeit_abgelaufen':
      return {
        title: 'Noch kein Ergebnis',
        text: 'Seit drei Stunden hat sich kein Lauf gemeldet. Auf GitHub nachsehen, ob der Lauf gestartet wurde oder noch läuft.',
      };
  }
}
