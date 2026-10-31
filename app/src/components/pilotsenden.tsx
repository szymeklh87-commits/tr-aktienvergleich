/* Eingang an den Spielgeld-Robo senden (Gesamtauftrag): Knopf, Zustand und Ergebnis der Prüfung auf GitHub. Gesendete
 * Eingänge stehen auf diesem Gerät in einer kurzen Liste (nur Kennung, Art, Bezeichnung, Zeit – keine Regelinhalte). */

import { useEffect, useRef, useState } from 'react';
import { useUpdates, type PilotEingangArt, type PilotEingangErgebnis } from '../state/UpdateState';

const LISTE = 'tr-vergleich:spielgeld-eingaenge:v1';
const POLL_MS = 5_000;
const POLL_MAX_MS = 5 * 60_000;

export interface GesendeterEingang {
  kennung: string;
  art: PilotEingangArt;
  bezeichnung: string;
  gesendet: number;
  ergebnis?: PilotEingangErgebnis | null;
}

export function gesendeteEingaenge(): GesendeterEingang[] {
  try {
    const raw = localStorage.getItem(LISTE);
    const list = raw ? (JSON.parse(raw) as GesendeterEingang[]) : [];
    return Array.isArray(list) ? list.filter((x) => x && typeof x.kennung === 'string').slice(0, 20) : [];
  } catch {
    return [];
  }
}

function speichern(list: GesendeterEingang[]) {
  try {
    localStorage.setItem(LISTE, JSON.stringify(list.slice(0, 20)));
  } catch {
    /* nur Anzeige auf diesem Gerät */
  }
}

/** Ergebnis eines gesendeten Eingangs nachverfolgen (alle 5 s, höchstens 5 Minuten, nur bei sichtbarer App). */
function useErgebnis(item: GesendeterEingang | null, onDone: (e: PilotEingangErgebnis) => void) {
  const { readPilotResult } = useUpdates();
  const done = useRef(onDone);
  done.current = onDone;
  useEffect(() => {
    if (!item || item.ergebnis) return;
    let stopped = false;
    let timer: number | undefined;
    const step = async () => {
      if (stopped) return;
      if (Date.now() - item.gesendet > POLL_MAX_MS) return;
      if (document.visibilityState === 'visible') {
        try {
          const e = await readPilotResult(item.kennung);
          if (e && !stopped) {
            done.current(e);
            return;
          }
        } catch {
          /* offline oder Limit: beim nächsten Durchgang */
        }
      }
      timer = window.setTimeout(() => void step(), POLL_MS);
    };
    timer = window.setTimeout(() => void step(), POLL_MS);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [item, readPilotResult]);
}

export function PilotSenden({
  art,
  inhalt,
  bezeichnung,
  label,
  disabled = false,
  primary = false,
}: {
  art: PilotEingangArt;
  inhalt: Record<string, unknown>;
  bezeichnung: string;
  label: string;
  disabled?: boolean;
  primary?: boolean;
}) {
  const { access, sendPilot } = useUpdates();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [item, setItem] = useState<GesendeterEingang | null>(null);
  useErgebnis(item, (e) => {
    setItem((old) => (old ? { ...old, ergebnis: e } : old));
    speichern(gesendeteEingaenge().map((x) => (x.kennung === e.kennung ? { ...x, ergebnis: e } : x)));
    setMessage(e.status === 'angenommen' ? `Angenommen – wirksam mit dem nächsten täglichen Lauf${e.regel ? ` (${e.regel})` : ''}.` : `Abgelehnt: ${e.text}`);
  });
  const send = async () => {
    setBusy(true);
    setMessage(null);
    const result = await sendPilot(art, inhalt);
    setBusy(false);
    setMessage(result.text);
    if (result.ok && result.kennung) {
      const entry: GesendeterEingang = { kennung: result.kennung, art, bezeichnung, gesendet: Date.now(), ergebnis: null };
      speichern([entry, ...gesendeteEingaenge()]);
      setItem(entry);
    }
  };
  return (
    <div className="pilot-send">
      <button type="button" className={`btn${primary ? ' btn-primary' : ''}`} disabled={disabled || busy} onClick={() => void send()}>
        {busy ? 'Wird gesendet …' : label}
      </button>
      {access !== 'bereit' ? (
        <p className="section-note">
          Senden braucht den Zugang von „Jetzt aktualisieren“ (<a href="#/einstellungen">Einstellungen</a>).
        </p>
      ) : null}
      {message ? (
        <p className="section-note" role="status">
          {message}
        </p>
      ) : null}
    </div>
  );
}

/** Gesendete Eingänge dieses Geräts mit dem Ergebnis der Prüfung. */
export function GesendeteListe() {
  const [list] = useState(gesendeteEingaenge);
  if (!list.length) return null;
  return (
    <ul className="plain-list">
      {list.map((x) => (
        <li key={x.kennung} className="pilot-entry">
          <b>{x.bezeichnung}</b> · gesendet {new Date(x.gesendet).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })}
          <br />
          <span className="muted">
            {x.ergebnis ? (x.ergebnis.status === 'angenommen' ? 'auf GitHub angenommen – wirksam mit dem nächsten täglichen Lauf' : `abgelehnt: ${x.ergebnis.text}`) : 'Prüfung auf GitHub ausstehend oder Ergebnis noch nicht abgerufen'}
          </span>
        </li>
      ))}
    </ul>
  );
}
