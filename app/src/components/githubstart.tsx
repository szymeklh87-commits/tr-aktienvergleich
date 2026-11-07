/* Lauf auf GitHub starten – mit der eigenen Anmeldung, ohne Zugang in der App (ab 1.22).
 *
 * Die App kopiert, wenn nötig, eine verschlüsselte Zeile „<Kennung>.<Text>“ und öffnet die Seite des Workflows. Dort tippst
 * du auf „Run workflow“, fügst die Zeile ein und startest. Zurück in der App erscheint der Fortschritt von selbst. */

import { useState } from 'react';
import { workflowPage } from '../lib/github';

export interface GitHubStartProps {
  repo: string | null;
  workflow: string;
  /** Zeile zum Einfügen; ohne Zeile wird der Lauf nur gestartet */
  eingabe?: string | null;
  /** Name des Feldes auf GitHub */
  feld?: string;
  /** zusätzlicher Schritt vor dem Start, z. B. „Handelstage eintragen“ */
  hinweis?: string | null;
  onOpened?: () => void;
}

type Copy = 'kopiert' | 'nicht_kopiert' | null;

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* ohne Berechtigung: Zeile von Hand kopieren */
  }
  return false;
}

export function GitHubStart({ repo, workflow, eingabe = null, feld = 'anfrage', hinweis = null, onOpened }: GitHubStartProps) {
  const [copy, setCopy] = useState<Copy>(null);
  if (!repo) {
    return <p className="section-note">Starten auf GitHub gibt es nur in der eingerichteten App (GitHub Pages) – das Repository ist hier unbekannt.</p>;
  }
  const url = workflowPage(repo, workflow);
  const doCopy = () => {
    if (!eingabe) return;
    void copyText(eingabe).then((ok) => setCopy(ok ? 'kopiert' : 'nicht_kopiert'));
  };
  return (
    <div className="gh-start">
      <ol className="gh-start-steps">
        <li>{eingabe ? '„Kopieren und GitHub öffnen“ antippen (bei GitHub angemeldet sein).' : '„GitHub öffnen“ antippen (bei GitHub angemeldet sein).'}</li>
        <li>Auf GitHub „Run workflow“ antippen.</li>
        {eingabe ? <li>Ins Feld „{feld}“ lange tippen und „Einfügen“ wählen.</li> : null}
        {hinweis ? <li>{hinweis}</li> : null}
        <li>Den grünen Knopf „Run workflow“ antippen und zur App zurückkehren – der Fortschritt erscheint hier von selbst.</li>
      </ol>
      <div className="toolbar">
        <a
          className="btn btn-primary"
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => {
            doCopy();
            onOpened?.();
          }}
        >
          {eingabe ? 'Kopieren und GitHub öffnen' : 'GitHub öffnen'}
        </a>
        {eingabe ? (
          <button type="button" className="btn" onClick={doCopy}>
            Nur kopieren
          </button>
        ) : null}
      </div>
      {copy === 'kopiert' ? (
        <p className="section-note" role="status">
          Zeile kopiert – auf GitHub einfügen.
        </p>
      ) : copy === 'nicht_kopiert' ? (
        <p className="section-note warn-text" role="status">
          Kopieren war nicht möglich. Die Zeile unten antippen, alles markieren und kopieren.
        </p>
      ) : null}
      {eingabe ? (
        <details className="disclosure gh-start-line" open={copy === 'nicht_kopiert'}>
          <summary>Zeile anzeigen ({eingabe.length.toLocaleString('de-DE')} Zeichen, verschlüsselt)</summary>
          <textarea readOnly rows={3} value={eingabe} aria-label="Zeile zum Einfügen auf GitHub" spellCheck={false} onFocus={(e: FocusEvent) => (e.currentTarget as HTMLTextAreaElement).select()} />
        </details>
      ) : null}
      <p className="section-note">
        Die App enthält keinen GitHub-Zugang. Gestartet wird mit deiner Anmeldung bei GitHub; öffentlich sichtbar sind nur eine Zufallskennung und verschlüsselter
        Text.
      </p>
    </div>
  );
}
