/* Liste zuerst (ab 1.22, Befund F09 der Bestandsaufnahme vom 07.11.2026): Auf dem Galaxy S25+ beginnt jede Hauptliste im
 * ersten Bildschirm. Über der Liste stehen nur die kompakte Zeitraumwahl, eine Zeile „Einstellungen“ und eine Zeile mit der
 * Art der Angaben und den Hinweisen; die Erklärung (Was du siehst, Was du hier tun kannst, So liest du die Zahlen) steht
 * unter der Liste. Inhalt und Bedienung bleiben vollständig – nur Reihenfolge und Aufklappen ändern sich.
 *
 * Simons Auftrag vom 24.10.2026 („Unterscheide historische Ergebnisse, Rangbewertungen und Prognosen eindeutig“) bleibt
 * erfüllt: Die Art der Angaben steht als Text in der Hinweiszeile über jeder Liste, die Renditebasis (nur Kursrendite)
 * ebenso. */

import type { ReactNode } from 'react';
import { Explain, KIND_INFO, type ExplainProps, type InfoKind } from './explain';
import { Disclosure } from './ui';

export const EXPLAIN_ID = 'erklaerung';

/** Eine Zeile „Einstellungen“ mit den gewählten Werten; aufgeklappt die vollständigen Regler. */
export function ListSettings({ summary, children }: { summary: ReactNode; children: ReactNode }) {
  return (
    <div className="list-line list-settings">
      <Disclosure
        summary={
          <>
            <span className="list-line-label">Einstellungen</span> <span className="list-line-value">{summary}</span>
          </>
        }
      >
        {children}
      </Disclosure>
    </div>
  );
}

/** Art der Angaben, Renditebasis und Hinweise in einer Zeile; aufgeklappt die Hinweise im Wortlaut. */
export function ListNotes({ kinds, basis = 'nur Kursrendite, ohne Dividenden', count, children }: { kinds: InfoKind[]; basis?: string | null; count: number; children: ReactNode }) {
  const toExplain = () => {
    const target = document.getElementById(EXPLAIN_ID);
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    target?.scrollIntoView({ block: 'start', behavior: reduced ? 'auto' : 'smooth' });
    target?.focus({ preventScroll: true });
  };
  return (
    <div className="list-line list-notes">
      <Disclosure
        summary={
          <>
            <span className="list-line-label">{kinds.map((k) => KIND_INFO[k].label).join(' · ')}</span>
            {basis ? <span className="list-line-value"> · {basis}</span> : null}
            <span className="list-line-count"> · {count === 1 ? '1 Hinweis' : `${count} Hinweise`}</span>
          </>
        }
      >
        {children}
        <p className="list-notes-more">
          <button type="button" className="link-button" onClick={toExplain}>
            Zur Erklärung unter der Liste
          </button>
        </p>
      </Disclosure>
    </div>
  );
}

/** Erklärung unter der Liste: Was du siehst, Was du hier tun kannst; Zahlen, Rechenweg und Beispiel aufklappbar. */
export function ExplainBelow(props: ExplainProps & { title?: string }) {
  const { title = 'Erklärung', ...rest } = props;
  return (
    <section className="section explain-below" aria-labelledby={`${EXPLAIN_ID}-titel`} id={EXPLAIN_ID} tabIndex={-1}>
      <h2 className="section-title" id={`${EXPLAIN_ID}-titel`}>
        {title}
      </h2>
      <Explain {...rest} />
    </section>
  );
}

/** Kurze Werte für die Einstellungszeile („60/40 · Gruppe A“). */
export function joinSummary(parts: (string | null | undefined | false)[]): string {
  return parts.filter(Boolean).join(' · ');
}
