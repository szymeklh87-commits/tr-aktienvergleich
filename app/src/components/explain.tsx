/* Erklärung an Ort und Stelle (ab 1.17): Was sehe ich? Was bedeutet die Zahl? Wie entsteht das Ergebnis? Was kann
 * ich hier tun? – und welche Art von Angabe ist das: Rückblick, Rangbewertung oder Prognose Dritter.
 *
 * Simons Auftrag vom 24.10.2026: „Erkläre direkt an der jeweiligen Stelle … Unterscheide historische Ergebnisse,
 * Rangbewertungen und Prognosen eindeutig. Zeige wesentliche Erklärungen sofort und weiterführende Details bei Bedarf.“
 * Sofort sichtbar sind deshalb die Art der Angaben, „Was du siehst“ und „Was du hier tun kannst“; Zahlen, Rechenweg
 * und Rechenbeispiel stehen unter „So liest du die Zahlen“. */

import type { ReactNode } from 'react';
import { helpLink } from './help';
import { Disclosure } from './ui';

export type InfoKind = 'rueckblick' | 'rang' | 'prognose';

export const KIND_INFO: Record<InfoKind, { label: string; text: string }> = {
  rueckblick: {
    label: 'Rückblick',
    text: 'Zahlen aus vergangenen Kursen bis zum Kursstand. Sie zeigen, was war – nicht, wie es weitergeht.',
  },
  rang: {
    label: 'Rangbewertung',
    text: 'Platz im Vergleich mit den anderen Aktien dieser Auswahl, nach einer festen Regel der App. Keine Vorhersage und keine Empfehlung.',
  },
  prognose: {
    label: 'Prognose Dritter',
    text: 'Einschätzung von Analysten, zum Beispiel ein Kursziel – nicht von dieser App. Prognosen können falsch sein.',
  },
};

/** Art der Angaben als kurze Kennzeichen (Text, nicht nur Farbe). */
export function KindChips({ kinds, label = 'Art der Angaben' }: { kinds: InfoKind[]; label?: string }) {
  if (!kinds.length) return null;
  return (
    <ul className="kind-chips" aria-label={label}>
      {kinds.map((kind) => (
        <li key={kind} className={`kind-chip kind-${kind}`} title={KIND_INFO[kind].text}>
          {KIND_INFO[kind].label}
        </li>
      ))}
    </ul>
  );
}

export interface ExplainProps {
  kinds: InfoKind[];
  /** Was siehst du? – ein bis zwei kurze Sätze, immer sichtbar */
  sees: ReactNode;
  /** Was kannst du hier tun? – ein Satz, immer sichtbar */
  todo?: ReactNode;
  /** Was bedeuten die Zahlen? – Begriff und Erklärung */
  numbers?: [ReactNode, ReactNode][];
  /** Wie entsteht das Ergebnis? */
  how?: ReactNode;
  /** Kurzes Rechenbeispiel */
  example?: ReactNode;
  /** Begriff der Hilfe, auf den „Alle Begriffe“ springt */
  term?: string;
  children?: ReactNode;
}

export function Explain({ kinds, sees, todo, numbers, how, example, term, children }: ExplainProps) {
  const details = Boolean(numbers?.length || how || example || children);
  return (
    <div className="explain">
      <KindChips kinds={kinds} />
      <p className="explain-sees">{sees}</p>
      {todo ? (
        <p className="explain-todo">
          <strong>Was du hier tun kannst:</strong> {todo}
        </p>
      ) : null}
      {details ? (
        <Disclosure summary="So liest du die Zahlen">
          {numbers?.length ? (
            <>
              <p className="explain-h">Was bedeuten die Zahlen?</p>
              <dl className="explain-dl">
                {numbers.map(([name, text], k) => (
                  <div key={k}>
                    <dt>{name}</dt>
                    <dd>{text}</dd>
                  </div>
                ))}
              </dl>
            </>
          ) : null}
          {how ? (
            <>
              <p className="explain-h">Wie entsteht das Ergebnis?</p>
              <div className="explain-how">{how}</div>
            </>
          ) : null}
          {example ? (
            <>
              <p className="explain-h">Rechenbeispiel</p>
              <p className="explain-example">{example}</p>
            </>
          ) : null}
          {children}
          <ul className="explain-kinds">
            {kinds.map((kind) => (
              <li key={kind}>
                <strong>{KIND_INFO[kind].label}:</strong> {KIND_INFO[kind].text}
              </li>
            ))}
          </ul>
          <p className="explain-more">
            <a href={helpLink(term)}>Alle Begriffe mit Beispielen</a>
          </p>
        </Disclosure>
      ) : null}
    </div>
  );
}
