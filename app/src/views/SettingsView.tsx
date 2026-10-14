import { useState } from 'react';
import { NoiseToggle, WeightControl, WindowRuler } from '../components/controls';
import { KeyValues, Notice, Segmented, SectionTitle } from '../components/ui';
import { downloadText } from '../lib/csv';
import * as f from '../lib/format';
import { exportPersonalData, importPersonalData, sanitizePrefs, type Theme } from '../lib/storage';
import { useApp } from '../state/AppState';
import { PREVIEW } from '../lib/env';

declare const __APP_VERSION__: string;

export function SettingsView() {
  const { prefs, setPrefs, watchlist, setWatchlist, crypto, lock, status } = useApp();
  const [message, setMessage] = useState<{ tone: 'info' | 'error'; text: string } | null>(null);

  const doExport = () => {
    downloadText(`tr-vergleich-persoenlich_${new Date().toISOString().slice(0, 10)}.json`, exportPersonalData(prefs, watchlist), 'application/json');
    setMessage({ tone: 'info', text: 'Datei gespeichert. Sie enthält nur Watchlist und Einstellungen, keinen Zugangsschlüssel.' });
  };

  const doImport = async (file: File | undefined) => {
    if (!file) return;
    try {
      if (file.size > 200_000) throw new Error('Datei ist zu groß');
      const data = importPersonalData(await file.text());
      if (data.prefs) setPrefs(sanitizePrefs({ ...prefs, ...data.prefs }));
      if (data.watchlist) setWatchlist(data.watchlist);
      setMessage({ tone: 'info', text: `Übernommen: ${data.watchlist ? f.plural(data.watchlist.length, 'Aktie', 'Aktien') : 'keine Watchlist'}${data.prefs ? ' und Einstellungen' : ''}.` });
    } catch (exc) {
      setMessage({ tone: 'error', text: `Import nicht möglich: ${exc instanceof Error ? exc.message : String(exc)}` });
    }
  };

  const clearCache = async () => {
    try {
      const names = await caches.keys();
      await Promise.all(names.filter((n) => n.startsWith('tr-daten-') || n === 'tr-meta').map((n) => caches.delete(n)));
      setMessage({ tone: 'info', text: 'Gespeicherte Datenstände gelöscht. Beim nächsten Öffnen werden sie neu geladen.' });
    } catch {
      setMessage({ tone: 'error', text: 'Der Offline-Speicher konnte nicht gelöscht werden.' });
    }
  };

  return (
    <div className="view">
      {message ? (
        <Notice tone={message.tone === 'error' ? 'error' : 'info'}>
          <p role="status">{message.text}</p>
        </Notice>
      ) : null}

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
            <input type="file" accept="application/json,.json" className="visually-hidden" onChange={(e: Event) => void doImport((e.target as HTMLInputElement).files?.[0])} />
          </label>
        </div>
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
        </section>
      ) : null}

      {crypto?.enabled ? (
        <section className="section" aria-labelledby="schluessel">
          <SectionTitle id="schluessel">Zugangsschlüssel</SectionTitle>
          <p className="section-note">Die Daten sind verschlüsselt veröffentlicht. Der daraus abgeleitete Schlüssel liegt nicht auslesbar in diesem Browser; die Passphrase selbst wird nicht gespeichert.</p>
          <div className="toolbar">
            <button type="button" className="btn" onClick={() => void lock()}>
              Schlüssel auf diesem Gerät vergessen
            </button>
          </div>
        </section>
      ) : null}

      <section className="section" aria-labelledby="info">
        <SectionTitle id="info">Über diese App</SectionTitle>
        <KeyValues
          items={[
            ['App-Version', typeof __APP_VERSION__ === 'string' ? __APP_VERSION__ : '–'],
            ['Server-Software', status?.software_version ?? '–'],
            ['Zweck', 'Historische Ranglisten zum persönlichen Vergleich. Keine Anlageberatung, keine Orders, kein Depotzugriff.'],
            ['Verbindung zu Trade Republic', 'keine – unabhängiges Werkzeug, kein Produkt von Trade Republic'],
          ]}
        />
      </section>
    </div>
  );
}
