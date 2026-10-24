/* Fehlermeldungen in einfachem Deutsch (ab 1.16): was ist passiert, was bedeutet das, was kann ich tun.
 * Die technische Angabe bleibt erhalten, steht aber nur noch klein unter „Technische Angabe“. */

import { NotFoundError, OfflineError, ServerError } from './api';
import { DecodeError } from './container';

export type ErrorKind = 'offline' | 'server' | 'fehlt' | 'unlesbar' | 'unbekannt';

export interface ErrorText {
  kind: ErrorKind;
  title: string;
  text: string;
  /** Technische Angabe (Dateiname, Statuscode, Meldung des Browsers) */
  detail: string;
}

function technical(error: unknown): string {
  if (error instanceof Error) return error.message || error.name;
  return String(error ?? '');
}

export function describeError(error: unknown): ErrorText {
  const detail = technical(error);
  if (error instanceof OfflineError || /verbindung|offline|failed to fetch|networkerror/i.test(detail)) {
    return {
      kind: 'offline',
      title: 'Keine Internetverbindung',
      text: 'Diese Daten sind auf diesem Gerät noch nicht gespeichert. Verbinde das Handy mit dem Internet und tippe auf „Erneut versuchen“.',
      detail,
    };
  }
  if (error instanceof ServerError) {
    return {
      kind: 'server',
      title: 'Server antwortet nicht',
      text: `Der Server hat mit Fehler ${error.status} geantwortet. Das liegt nicht an deinem Gerät. Warte ein paar Minuten und tippe dann auf „Erneut versuchen“.`,
      detail,
    };
  }
  if (error instanceof NotFoundError) {
    return {
      kind: 'fehlt',
      title: 'Datei nicht gefunden',
      text: 'Ein Teil dieses Datenstands fehlt auf dem Server – meist, weil gerade ein neuer Stand veröffentlicht wurde. Tippe auf „Erneut versuchen“; die App lädt dann den neuesten Stand.',
      detail,
    };
  }
  if (error instanceof DecodeError || error instanceof SyntaxError) {
    return {
      kind: 'unlesbar',
      title: 'Daten nicht lesbar',
      text: 'Eine Datei ist unvollständig angekommen oder passt nicht zum gespeicherten Schlüssel. Tippe auf „Erneut versuchen“. Hilft das nicht: ☰ → Einstellungen → „Gespeicherte Datenstände löschen“ und die App neu öffnen.',
      detail,
    };
  }
  return {
    kind: 'unbekannt',
    title: 'Daten konnten nicht geladen werden',
    text: 'Beim Laden ist ein unerwarteter Fehler aufgetreten. Tippe auf „Erneut versuchen“. Tritt er wieder auf, hilft die technische Angabe unten bei der Suche nach der Ursache.',
    detail,
  };
}
