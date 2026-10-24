/* Hilfe direkt an der Stelle (ab 1.16): Begriffe zum Antippen, Kurzerklärung beim ersten Start. */

import { useId, useState } from 'react';
import type { ReactNode } from 'react';
import { glossaryEntry } from '../lib/glossary';
import { isinCheckDigitOk } from '../lib/instruments';
import { buildHash } from '../lib/router';
import { InfoTip } from './signals';
import { Notice } from './ui';

/** Link auf einen Begriff der Hilfe. */
export function helpLink(id?: string): string {
  return buildHash('/hilfe', id ? { begriff: id } : undefined);
}

function GlossaryText({ id }: { id: string }) {
  const entry = glossaryEntry(id);
  if (!entry) return null;
  return (
    <>
      {entry.text}
      {entry.example ? (
        <>
          {' '}
          <em>Beispiel:</em> {entry.example}
        </>
      ) : null}{' '}
      <a href={helpLink(id)}>Alle Begriffe</a>
    </>
  );
}

/** Fachbegriff im Fließtext: antippen zeigt die Erklärung mit Beispiel direkt darunter. */
export function Term({ id, children }: { id: string; children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const panel = useId();
  const entry = glossaryEntry(id);
  if (!entry) return <>{children}</>;
  return (
    <>
      <button type="button" className={`term${open ? ' is-open' : ''}`} aria-expanded={open} aria-controls={panel} onClick={() => setOpen(!open)}>
        {children ?? entry.term}
      </button>
      {open ? (
        <span className="info-text" id={panel} role="note">
          <GlossaryText id={id} />
        </span>
      ) : null}
    </>
  );
}

/** ⓘ mit der Erklärung eines Begriffs aus der Hilfe. */
export function GlossaryTip({ id, label }: { id: string; label?: string }) {
  const entry = glossaryEntry(id);
  if (!entry) return null;
  return (
    <InfoTip label={label ?? entry.term}>
      <GlossaryText id={id} />
    </InfoTip>
  );
}

/** Kurzerklärung beim ersten Start (bis „Verstanden“). */
export function IntroCard({ onDone }: { onDone: () => void }) {
  return (
    <section className="intro-card" aria-labelledby="intro-titel">
      <h2 id="intro-titel" className="intro-title">
        Neu hier? So funktioniert die App
      </h2>
      <p>
        Die App vergleicht jeden Tag alle Aktien aus der Liste von Trade Republic. Sie zeigt, welche Aktien in den letzten 1 bis 90 Tagen am stärksten und am
        gleichmäßigsten gestiegen sind.
      </p>
      <ol className="intro-steps">
        <li>
          <strong>Oben:</strong> die Top 3 nach einer festen Punkteregel. Darunter steht der Kursstand – der Börsentag, dessen Schlusskurse verwendet werden.
        </li>
        <li>
          <strong>Unten „Rendite“:</strong> die Ranglisten. Wähle einen Zeitraum, zum Beispiel 30 Tage.
        </li>
        <li>
          <strong>Eine Aktie antippen:</strong> Kursverlauf und alle Zahlen. Mit dem Stern ☆ merkst du sie dir.
        </li>
      </ol>
      <p className="intro-note">Alle Zahlen beruhen auf vergangenen Kursen. Sie sagen nichts über die Zukunft und sind keine Kaufempfehlung.</p>
      <div className="toolbar">
        <a className="btn btn-primary" href={helpLink()}>
          Hilfe und Begriffe
        </a>
        <button type="button" className="btn" onClick={onDone}>
          Verstanden
        </button>
      </div>
    </section>
  );
}

/** Aktie aus einem Link nicht gefunden (ab 1.16): unterscheidet leere, ungültige und unbekannte ISIN und nennt den nächsten Schritt. */
export function IsinMissing({ isin }: { isin: string }) {
  const clean = isin.trim().toUpperCase();
  const valid = clean.length > 0 && isinCheckDigitOk(clean);
  const title = !clean ? 'Keine Aktie angegeben' : valid ? 'Aktie nicht in diesem Datenstand' : 'Keine gültige ISIN';
  const text = !clean
    ? 'Der Link nennt keine Aktie.'
    : valid
      ? `Die Aktie mit der ISIN ${clean} steht nicht in der Trade-Republic-Liste dieses Datenstands. Vielleicht wurde sie aus der Liste genommen, oder der Link stammt aus einem älteren Stand.`
      : `„${isin}“ ist keine gültige ISIN. Eine ISIN hat 12 Zeichen: zwei Buchstaben für das Land, neun Zeichen und eine Prüfziffer – zum Beispiel DE0007164600.`;
  return (
    <Notice
      tone="warn"
      title={title}
      actions={
        <>
          <a className="btn btn-primary" href={buildHash('/aktien', valid ? { q: clean } : undefined)}>
            Aktie suchen
          </a>
          <a className="btn" href="#/">
            Zur Startseite
          </a>
        </>
      }
    >
      <p>{text}</p>
      <p>Unter „Aktien“ findest du jede Aktie der Liste mit Namen, Ticker oder ISIN.</p>
    </Notice>
  );
}
