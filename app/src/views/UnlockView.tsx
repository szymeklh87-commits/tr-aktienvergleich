import { useRef, useState } from 'react';
import { Notice } from '../components/ui';
import { useApp } from '../state/AppState';

/* Sperrbildschirm (ab 1.16 neu formuliert): zuerst wofür die App ist, dann was einzugeben ist und was danach passiert.
 * Fehler stehen direkt am Feld und nennen den nächsten Schritt; die Eingabe bleibt zum Korrigieren erhalten. */
export function UnlockView({ early = false }: { early?: boolean } = {}) {
  const { unlock } = useApp();
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(false);
  const input = useRef<HTMLInputElement | null>(null);

  const submit = async (event: Event) => {
    event.preventDefault();
    if (busy) return;
    if (!value.trim()) {
      setError('Gib zuerst die Passphrase ein. Ohne sie lassen sich die Daten nicht öffnen.');
      input.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    const message = await unlock(value);
    setBusy(false);
    if (message) {
      setError(message);
      input.current?.focus();
    } else setValue('');
  };

  return (
    <div className="view">
      <header className="view-head">
        <h2 className="view-title">{early ? 'Passphrase schon jetzt speichern' : 'App entsperren'}</h2>
        {early ? (
          <p className="lede">
            Du kannst die Passphrase schon jetzt eingeben und prüfen. Sobald der erste Datenstand veröffentlicht ist, öffnen sich die Ranglisten ohne weitere Eingabe.
          </p>
        ) : (
          <>
            <p className="lede">
              Der TR-Aktienvergleich zeigt jeden Tag, welche Aktien aus der Liste von Trade Republic in den letzten 1 bis 90 Tagen am stärksten und am gleichmäßigsten
              gestiegen sind. Die Kursdaten sind verschlüsselt.
            </p>
            <ol className="lock-steps">
              <li>Gib deine Passphrase ein. Das ist das Kennwort, mit dem die Kursdaten verschlüsselt sind.</li>
              <li>Tippe auf „Entsperren“. Die Prüfung dauert ein bis zwei Sekunden.</li>
              <li>Danach öffnet sich die Startseite. Auf diesem Gerät musst du die Passphrase nicht noch einmal eingeben.</li>
            </ol>
          </>
        )}
      </header>
      <form className="field" onSubmit={submit} noValidate>
        <label className="field-label" htmlFor="passphrase">
          Passphrase
        </label>
        <input
          id="passphrase"
          ref={input}
          className="input"
          type={visible ? 'text' : 'password'}
          autoComplete="current-password"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="go"
          value={value}
          onInput={(e: Event) => {
            setValue((e.target as HTMLInputElement).value);
            if (error) setError(null);
          }}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? 'passphrase-fehler' : 'passphrase-hinweis'}
        />
        {error ? (
          <p id="passphrase-fehler" className="field-error" role="alert">
            {error}
          </p>
        ) : null}
        <label className="check">
          <input type="checkbox" checked={visible} onChange={(e: Event) => setVisible((e.target as HTMLInputElement).checked)} />
          <span>Passphrase anzeigen</span>
        </label>
        <div className="toolbar">
          <button type="submit" className="btn btn-primary" disabled={busy} aria-busy={busy || undefined}>
            {busy ? 'Wird geprüft …' : early ? 'Prüfen und speichern' : 'Entsperren'}
          </button>
          <a className="btn btn-quiet" href="#/hilfe">
            Hilfe
          </a>
        </div>
        <p id="passphrase-hinweis" className="section-note">
          Gespeichert wird nur ein daraus berechneter Schlüssel, nicht die Passphrase selbst. Unter ☰ → Einstellungen kannst du ihn wieder löschen.
        </p>
      </form>
      {error && !early ? (
        <Notice tone="info" title="Passphrase vergessen?">
          <p>
            Die Passphrase hat festgelegt, wer die App eingerichtet hat. Sie steht bei GitHub als Secret „DATA_PASSPHRASE“; GitHub zeigt den Wert nicht wieder an. Ohne
            die richtige Passphrase lassen sich die Daten nicht öffnen.
          </p>
        </Notice>
      ) : null}
    </div>
  );
}
