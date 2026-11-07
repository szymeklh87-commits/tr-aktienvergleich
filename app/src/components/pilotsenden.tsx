/* Eingang an den Spielgeld-Robo senden (Gesamtauftrag; ab 1.22 Start auf GitHub mit eigener Anmeldung): Knopf, Start auf
 * GitHub, Zustand und Ergebnis der Prüfung. Gesendete Eingänge stehen auf diesem Gerät in einer kurzen Liste (nur Kennung,
 * Art, Bezeichnung, Zeit – keine Regelinhalte). */

import { useEffect, useRef, useState } from 'react';
import { useUpdates, WORKFLOW_PILOT, type PilotEingangArt, type PilotEingangErgebnis } from '../state/UpdateState';
import { GitHubStart } from './githubstart';

const LISTE = 'tr-vergleich:spielgeld-eingaenge:v1';
/** ohne Anmeldung erlaubt GitHub 60 Abfragen je Stunde – deshalb alle 20 s und nur, solange die App sichtbar ist */
const POLL_MS = 20_000;
/** der Server nimmt höchstens 20 Minuten alte Eingänge an; danach kommt kein Ergebnis mehr */
const POLL_MAX_MS = 25 * 60_000;

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

/** Ergebnis eines gesendeten Eingangs nachverfolgen (alle 20 s und beim Zurückkehren, höchstens 25 Minuten, nur bei sichtbarer App). */
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
    const onVisible = () => {
      if (document.visibilityState !== 'visible' || stopped) return;
      window.clearTimeout(timer);
      void step();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
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
  const { repo, preparePilot } = useUpdates();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [item, setItem] = useState<GesendeterEingang | null>(null);
  const [eingabe, setEingabe] = useState<string | null>(null);
  const [opened, setOpened] = useState(false);
  useErgebnis(opened ? item : null, (e) => {
    setItem((old) => (old ? { ...old, ergebnis: e } : old));
    setEingabe(null);
    speichern(gesendeteEingaenge().map((x) => (x.kennung === e.kennung ? { ...x, ergebnis: e } : x)));
    setMessage(e.status === 'angenommen' ? `Angenommen – wirksam mit dem nächsten täglichen Lauf${e.regel ? ` (${e.regel})` : ''}.` : `Abgelehnt: ${e.text}`);
  });
  const prepare = async () => {
    setBusy(true);
    setMessage(null);
    setOpened(false);
    const result = await preparePilot(art, inhalt);
    setBusy(false);
    setMessage(result.text);
    if (result.ok && result.kennung && result.eingabe) {
      const entry: GesendeterEingang = { kennung: result.kennung, art, bezeichnung, gesendet: Date.now(), ergebnis: null };
      speichern([entry, ...gesendeteEingaenge()]);
      setItem(entry);
      setEingabe(result.eingabe);
    }
  };
  return (
    <div className="pilot-send">
      <button type="button" className={`btn${primary ? ' btn-primary' : ''}`} disabled={disabled || busy} onClick={() => void prepare()}>
        {busy ? 'Wird vorbereitet …' : label}
      </button>
      {message ? (
        <p className="section-note" role="status">
          {message}
        </p>
      ) : null}
      {eingabe && item ? <GitHubStart repo={repo} workflow={WORKFLOW_PILOT} eingabe={eingabe} feld="eingang" onOpened={() => setOpened(true)} /> : null}
      {opened && item && !item.ergebnis ? <p className="section-note">Die App wartet auf das Ergebnis der Prüfung auf GitHub …</p> : null}
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
            {x.ergebnis ? (x.ergebnis.status === 'angenommen' ? 'auf GitHub angenommen – wirksam mit dem nächsten täglichen Lauf' : `abgelehnt: ${x.ergebnis.text}`) : 'auf GitHub nicht gestartet, Prüfung ausstehend oder Ergebnis noch nicht abgerufen'}
          </span>
        </li>
      ))}
    </ul>
  );
}
