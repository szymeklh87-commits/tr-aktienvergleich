/* Einstellungen für „Jetzt aktualisieren“ (ab 1.21): Zugang einrichten, prüfen, entfernen; automatische Aktualisierung. */

import { useEffect, useState } from 'react';
import { AUTO_CHOICES } from '../lib/aktualisierung';
import { tokenTemplateUrl } from '../lib/github';
import { useApp } from '../state/AppState';
import { useUpdates } from '../state/UpdateState';
import { Disclosure, Notice, Segmented, SectionTitle } from './ui';

export function AccessSettings() {
  const { keyCanEncrypt, upgradeKey, crypto, prefs, setPrefs } = useApp();
  const { repo, access, saveAccess, removeAccess, testAccess, autoReason } = useUpdates();
  const [token, setToken] = useState('');
  const [passphrase, setPassphrase] = useState('');
  const [message, setMessage] = useState<{ tone: 'info' | 'error'; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  useEffect(() => {
    // „Zugang einrichten“ aus einer Ansicht: direkt zu diesem Abschnitt
    if (window.location.hash.includes('abschnitt=zugang')) document.getElementById('zugang')?.scrollIntoView({ block: 'start' });
  }, []);

  const run = async (action: () => Promise<{ ok: boolean; text: string } | null>) => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await action();
      if (result) setMessage({ tone: result.ok ? 'info' : 'error', text: result.text });
    } finally {
      setBusy(false);
    }
  };

  const save = () =>
    run(async () => {
      if (!keyCanEncrypt) {
        const error = await upgradeKey(passphrase);
        if (error) return { ok: false, text: error };
        setPassphrase('');
      }
      const result = await saveAccess(token);
      if (result.ok) setToken('');
      return result;
    });

  return (
    <>
      <section className="section" id="zugang" aria-labelledby="zugang-titel">
        <SectionTitle id="zugang-titel">Zugang für „Jetzt aktualisieren“</SectionTitle>
        <p className="section-note">
          Damit die App Kurse selbst anfordern und den Fortschritt zeigen kann, braucht sie einmalig einen GitHub-Zugang (ein Token). Er bleibt nur auf diesem Gerät, verschlüsselt mit deinem
          Datenschlüssel; gesperrt ist er nicht nutzbar. Ohne Zugang funktioniert alles wie bisher: Läufe startest du dann auf GitHub selbst.
        </p>
        <p>
          Stand:{' '}
          <strong>
            {access === 'bereit' ? 'eingerichtet' : access === 'gesperrt' ? 'gespeichert, aber gesperrt (erst entsperren)' : access === 'laedt' ? 'wird geprüft …' : 'nicht eingerichtet'}
          </strong>
          {repo ? ` – Repository ${repo}` : ' – nur in der eingerichteten App (GitHub Pages) verfügbar'}
        </p>
        {repo && access !== 'bereit' ? (
          <ol className="steps">
            <li>
              <a href={tokenTemplateUrl(repo)} target="_blank" rel="noopener noreferrer">
                Neues Token auf GitHub anlegen
              </a>{' '}
              (Vorlage mit Name und Recht ist vorausgefüllt). Unter „Repository access“ <strong>„Only select repositories“</strong> und nur <strong>{repo.split('/')[1]}</strong> wählen. Ablauf: 90 Tage.
            </li>
            <li>
              Unter „Permissions“ nur <strong>„Actions: Read and write“</strong> (Metadata „Read“ setzt GitHub automatisch). Nichts weiter – vor allem nicht „Contents“, „Workflows“ oder „Secrets“.
            </li>
            <li>„Generate token“, das Token kopieren und hier einfügen.</li>
          </ol>
        ) : null}
        {repo && access !== 'bereit' ? (
          <div className="field-group">
            <label className="field">
              <span className="field-label">Token (beginnt mit „github_pat_“)</span>
              <input className="input" type="password" autoComplete="off" spellCheck={false} value={token} onChange={(e: Event) => setToken((e.target as HTMLInputElement).value)} />
            </label>
            {crypto?.enabled && !keyCanEncrypt ? (
              <label className="field">
                <span className="field-label">Passphrase (einmal, damit der Zugang verschlüsselt gespeichert werden kann)</span>
                <input className="input" type="password" autoComplete="current-password" value={passphrase} onChange={(e: Event) => setPassphrase((e.target as HTMLInputElement).value)} />
              </label>
            ) : null}
            <div className="toolbar">
              <button type="button" className="btn btn-primary" disabled={busy || !token.trim() || (Boolean(crypto?.enabled) && !keyCanEncrypt && !passphrase)} onClick={() => void save()}>
                {busy ? 'Wird geprüft …' : 'Zugang prüfen und speichern'}
              </button>
            </div>
          </div>
        ) : null}
        {access === 'bereit' ? (
          confirmRemove ? (
            <Notice
              tone="warn"
              title="Zugang auf diesem Gerät entfernen?"
              actions={
                <>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() =>
                      void run(async () => {
                        await removeAccess();
                        setConfirmRemove(false);
                        return { ok: true, text: 'Zugang und gespeicherte Kurslieferungen auf diesem Gerät gelöscht. Auf GitHub das Token zusätzlich widerrufen (Settings → Developer settings → Fine-grained tokens → Delete).' };
                      })
                    }
                  >
                    Ja, entfernen
                  </button>
                  <button type="button" className="btn" onClick={() => setConfirmRemove(false)}>
                    Abbrechen
                  </button>
                </>
              }
            >
              <p>Danach fordert die App keine Kurse mehr selbst an. Das Token auf GitHub bleibt gültig, bis du es dort widerrufst.</p>
            </Notice>
          ) : (
            <div className="toolbar">
              <button type="button" className="btn" disabled={busy} onClick={() => void run(testAccess)}>
                Zugang prüfen
              </button>
              <button type="button" className="btn btn-quiet" onClick={() => setConfirmRemove(true)}>
                Zugang entfernen
              </button>
            </div>
          )
        ) : null}
        {message ? (
          <Notice tone={message.tone === 'error' ? 'error' : 'info'}>
            <p role="status">{message.text}</p>
          </Notice>
        ) : null}
        <Disclosure summary="Was darf dieser Zugang – und was nicht?">
          <ul className="step-options">
            <li>
              <strong>Darf:</strong> Läufe dieses Repositorys starten (z. B. „Kursaktualisierung“, „Täglicher Lauf“), ihren Fortschritt lesen, Läufe abbrechen oder wiederholen, Protokolle löschen und
              Workflows ein- oder ausschalten – so legt GitHub das Recht „Actions: Schreiben“ fest.
            </li>
            <li>
              <strong>Darf nicht:</strong> Code oder Workflow-Dateien ändern, Secrets lesen, den Datenstand im Release ändern, Einstellungen ändern, andere Repositorys sehen – und nichts bei Trade Republic.
            </li>
            <li>
              <strong>Wenn das Handy verloren geht:</strong> auf GitHub unter Settings → Developer settings → Personal access tokens → Fine-grained tokens das Token löschen. Es läuft ohnehin nach der gewählten
              Frist ab; dann hier ein neues eintragen.
            </li>
            <li>
              <strong>Kosten:</strong> keine. Läufe in öffentlichen Repositorys sind bei GitHub kostenlos; die App fordert höchstens 6 automatische Abrufe je Stunde an.
            </li>
          </ul>
        </Disclosure>
      </section>

      <section className="section" aria-labelledby="automatik">
        <SectionTitle id="automatik">Automatisch aktualisieren</SectionTitle>
        <label className="check">
          <input type="checkbox" checked={prefs.autoStand} onChange={(e: Event) => setPrefs({ autoStand: (e.target as HTMLInputElement).checked })} />
          <span>Neu veröffentlichte Datenstände beim nächsten Seitenwechsel automatisch anzeigen (die App schaut jede Minute nach, solange sie offen ist)</span>
        </label>
        <Segmented
          label="Kurse der sichtbaren Aktien und der Merkliste automatisch abrufen (nur mit Zugang, nur während die App offen ist und Börsen handeln)"
          options={AUTO_CHOICES.map((m) => ({ value: m, label: m === 0 ? 'Aus' : `alle ${m} Min.` }))}
          value={prefs.autoKurseMin}
          onChange={(value) => setPrefs({ autoKurseMin: Number(value) })}
        />
        <p className="section-note">
          {access !== 'bereit'
            ? 'Ohne Zugang ruft die App keine Kurse selbst ab – sie zeigt nur neu veröffentlichte Stände.'
            : prefs.autoKurseMin === 0
              ? 'Automatische Kursabrufe sind aus.'
              : `Gerade kein automatischer Abruf: ${autoReason ?? 'wird geprüft'}. Pause nach 10 Minuten ohne Bedienung; höchstens 6 Abrufe je Stunde.`}
        </p>
      </section>
    </>
  );
}
