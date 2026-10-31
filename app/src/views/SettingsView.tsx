import { useState } from 'react';
import { NoiseToggle, WeightControl, WindowRuler } from '../components/controls';
import { KeyValues, Notice, Segmented, SectionTitle } from '../components/ui';
import { downloadText } from '../lib/csv';
import * as f from '../lib/format';
import { exportPersonalData, importPersonalData, sanitizePrefs, type Theme } from '../lib/storage';
import { useApp } from '../state/AppState';
import { PREVIEW } from '../lib/env';
import { AccessSettings } from '../components/zugang';

declare const __APP_VERSION__: string;

export function SettingsView() {
  const { prefs, setPrefs, watchlist, setWatchlist, crypto, lock, status } = useApp();
  // Rückmeldung direkt unter der Aktion, die sie ausgelöst hat (ab 1.16; vorher oben auf der Seite, außer Sicht)
  const [message, setMessage] = useState<{ where: 'sichern' | 'speicher'; tone: 'info' | 'error'; text: string } | null>(null);
  const [confirmForget, setConfirmForget] = useState(false);

  const doExport = () => {
    downloadText(`tr-vergleich-persoenlich_${new Date().toISOString().slice(0, 10)}.json`, exportPersonalData(prefs, watchlist), 'application/json');
    setMessage({ where: 'sichern', tone: 'info', text: 'Datei gespeichert (im Ordner „Downloads“). Sie enthält nur Watchlist und Einstellungen, keine Passphrase und keinen Schlüssel.' });
  };

  const doImport = async (input: HTMLInputElement) => {
    const file = input.files?.[0];
    input.value = ''; // dieselbe Datei lässt sich danach erneut wählen
    if (!file) return;
    if (file.size > 200_000) {
      setMessage({ where: 'sichern', tone: 'error', text: 'Diese Datei ist zu groß für eine Sicherung dieser App. Wähle die Datei „tr-vergleich-persoenlich_….json“, die „Als Datei sichern“ erstellt hat.' });
      return;
    }
    try {
      const data = importPersonalData(await file.text());
      if (data.prefs) setPrefs(sanitizePrefs({ ...prefs, ...data.prefs }));
      if (data.watchlist) setWatchlist(data.watchlist);
      setMessage({ where: 'sichern', tone: 'info', text: `Eingelesen: ${data.watchlist ? `${f.plural(data.watchlist.length, 'Aktie', 'Aktien')} auf der Watchlist` : 'keine Watchlist'}${data.prefs ? ' und deine Einstellungen' : ''}.` });
    } catch {
      setMessage({
        where: 'sichern',
        tone: 'error',
        text: 'Diese Datei ist keine Sicherung dieser App. Wähle die Datei „tr-vergleich-persoenlich_….json“, die du hier mit „Als Datei sichern“ erstellt hast. Deine Watchlist und Einstellungen bleiben unverändert.',
      });
    }
  };

  const clearCache = async () => {
    try {
      const names = await caches.keys();
      await Promise.all(names.filter((n) => n.startsWith('tr-daten-') || n === 'tr-meta').map((n) => caches.delete(n)));
      setMessage({ where: 'speicher', tone: 'info', text: 'Gespeicherte Datenstände gelöscht. Beim nächsten Öffnen lädt die App sie neu aus dem Internet.' });
    } catch {
      setMessage({ where: 'speicher', tone: 'error', text: 'Der Offline-Speicher ließ sich nicht löschen. Schließe die App ganz, öffne sie neu und versuche es noch einmal.' });
    }
  };

  const feedback = (where: 'sichern' | 'speicher') =>
    message && message.where === where ? (
      <Notice tone={message.tone === 'error' ? 'error' : 'info'}>
        <p role="status">{message.text}</p>
      </Notice>
    ) : null;

  return (
    <div className="view">

      <section className="section" aria-labelledby="darstellung">
        <SectionTitle id="darstellung">Darstellung</SectionTitle>
        <Segmented
          label="Farbschema"
          options={[
            { value: 'system', label: 'Wie das Handy' },
            { value: 'hell', label: 'Hell' },
            { value: 'dunkel', label: 'Dunkel' },
          ]}
          value={prefs.theme}
          onChange={(theme) => setPrefs({ theme: theme as Theme })}
        />
      </section>

      <section className="section" aria-labelledby="standard">
        <SectionTitle id="standard">Standard beim Öffnen</SectionTitle>
        <p className="section-note">Diese Auswahl nutzen Start, Rangliste und Chart-Raster, solange in der Ansicht nichts anderes gewählt ist.</p>
        <WindowRuler value={prefs.h} onChange={(h) => setPrefs({ h })} compact />
        <WeightControl weight={prefs.w} onWeight={(w) => setPrefs({ w })} policy={prefs.policy} onPolicy={(policy) => setPrefs({ policy })} />
        <NoiseToggle />
      </section>

      {!PREVIEW ? <AccessSettings /> : null}

      <section className="section" aria-labelledby="sichern">
        <SectionTitle id="sichern">Watchlist und Einstellungen sichern</SectionTitle>
        <p className="section-note">
          Gespeichert wird nur in diesem Browser auf diesem Gerät ({f.plural(watchlist.length, 'Aktie', 'Aktien')} auf der Watchlist). Beim Löschen der Browserdaten gehen sie verloren – eine gesicherte Datei lässt sich hier wieder einlesen, auch auf einem anderen Gerät.
        </p>
        <div className="toolbar">
          {!PREVIEW ? (
            <button type="button" className="btn" onClick={doExport}>
              Als Datei sichern
            </button>
          ) : null}
          <label className="btn">
            Datei einlesen
            <input type="file" accept="application/json,.json" className="visually-hidden" onChange={(e: Event) => void doImport(e.target as HTMLInputElement)} />
          </label>
        </div>
        {feedback('sichern')}
      </section>

      {!PREVIEW ? (
        <section className="section" aria-labelledby="speicher">
          <SectionTitle id="speicher">Offline-Speicher</SectionTitle>
          <p className="section-note">Die App speichert die zuletzt geöffneten Datenstände (höchstens drei), damit sie ohne Netz lesbar bleiben.</p>
          <div className="toolbar">
            <button type="button" className="btn" onClick={() => void clearCache()}>
              Gespeicherte Datenstände löschen
            </button>
          </div>
          {feedback('speicher')}
        </section>
      ) : null}

      {crypto?.enabled ? (
        <section className="section" aria-labelledby="schluessel">
          <SectionTitle id="schluessel">Passphrase auf diesem Gerät</SectionTitle>
          <p className="section-note">
            Die Kursdaten sind verschlüsselt. Nach dem Entsperren speichert die App einen daraus berechneten Schlüssel in diesem Browser – nicht die Passphrase selbst.
            Vergisst du den Schlüssel, fragt die App beim nächsten Öffnen wieder nach der Passphrase.
          </p>
          {confirmForget ? (
            <Notice
              tone="warn"
              title="Schlüssel wirklich vergessen?"
              actions={
                <>
                  <button type="button" className="btn btn-primary" onClick={() => void lock()}>
                    Ja, vergessen
                  </button>
                  <button type="button" className="btn" onClick={() => setConfirmForget(false)}>
                    Abbrechen
                  </button>
                </>
              }
            >
              <p>Danach musst du die Passphrase neu eingeben, um die Ranglisten zu sehen. Halte sie bereit.</p>
            </Notice>
          ) : (
            <div className="toolbar">
              <button type="button" className="btn" onClick={() => setConfirmForget(true)}>
                Schlüssel auf diesem Gerät vergessen
              </button>
            </div>
          )}
        </section>
      ) : null}

      <section className="section" aria-labelledby="info">
        <SectionTitle id="info">Über diese App</SectionTitle>
        <KeyValues
          items={[
            ['App-Version', typeof __APP_VERSION__ === 'string' ? __APP_VERSION__ : '–'],
            ['Server-Software', status?.software_version ?? '–'],
            ['Zweck', 'Historische Ranglisten zum persönlichen Vergleich. Keine Anlageberatung, keine Orders, kein Depotzugriff.'],
            ['GitHub-Zugang', 'optional, nur für „Jetzt aktualisieren“ – verschlüsselt nur auf diesem Gerät, darf nur Läufe starten und lesen'],
            ['Verbindung zu Trade Republic', 'keine – unabhängiges Werkzeug, kein Produkt von Trade Republic'],
          ]}
        />
      </section>
    </div>
  );
}
