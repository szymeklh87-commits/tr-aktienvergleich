import { useState } from 'react';
import { Notice } from '../components/ui';
import { useApp } from '../state/AppState';

export function UnlockView() {
  const { unlock } = useApp();
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(false);

  const submit = async (event: Event) => {
    event.preventDefault();
    if (!value || busy) return;
    setBusy(true);
    setError(null);
    const message = await unlock(value);
    setBusy(false);
    if (message) setError(message);
    else setValue('');
  };

  return (
    <div className="view">
      <header className="view-head">
        <h2 className="view-title">Zugangsschlüssel eingeben</h2>
        <p className="lede">Die Ranglisten sind verschlüsselt veröffentlicht. Einmal die Passphrase eingeben, die beim Einrichten als GitHub-Secret „DATA_PASSPHRASE“ festgelegt wurde.</p>
      </header>
      <form className="field" onSubmit={submit}>
        <label className="field-label" htmlFor="passphrase">
          Passphrase
        </label>
        <input
          id="passphrase"
          className="input"
          type={visible ? 'text' : 'password'}
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          value={value}
          onChange={(e: Event) => setValue((e.target as HTMLInputElement).value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? 'passphrase-fehler' : 'passphrase-hinweis'}
        />
        <label className="check">
          <input type="checkbox" checked={visible} onChange={(e: Event) => setVisible((e.target as HTMLInputElement).checked)} />
          <span>Passphrase anzeigen</span>
        </label>
        <div className="toolbar">
          <button type="submit" className="btn btn-primary" disabled={!value || busy}>
            {busy ? 'Wird geprüft …' : 'Entsperren'}
          </button>
        </div>
        <p id="passphrase-hinweis" className="section-note">
          Die Prüfung dauert einige Sekunden. Gespeichert wird nur ein daraus abgeleiteter, nicht auslesbarer Schlüssel in diesem Browser – nicht die Passphrase selbst. Unter „Einstellungen“ lässt er sich wieder vergessen.
        </p>
      </form>
      {error ? (
        <Notice tone="error" title="Nicht entsperrt">
          <p id="passphrase-fehler">{error}</p>
        </Notice>
      ) : null}
    </div>
  );
}
