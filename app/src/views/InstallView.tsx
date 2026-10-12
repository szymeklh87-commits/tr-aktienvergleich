import { useState } from 'react';
import { Notice, SectionTitle } from '../components/ui';
import { promptInstall, useInstallState } from '../lib/install';
import { useApp } from '../state/AppState';

export function InstallView() {
  const { canPrompt, installed, standalone } = useInstallState();
  const { crypto } = useApp();
  const [result, setResult] = useState<string | null>(null);

  return (
    <div className="view">
      <header className="view-head">
        <p className="lede">Als App auf dem Startbildschirm öffnet sich der Aktienvergleich in einem eigenen Fenster ohne Adressleiste. Die Ranglisten werden jeden Morgen auf dem Server neu berechnet – das Handy muss dafür nicht eingeschaltet sein.</p>
      </header>

      {standalone || installed ? (
        <Notice tone="info" title="Bereits installiert">
          <p>Die App läuft im eigenen Fenster. Neue Versionen werden automatisch geladen; ein Hinweis bietet dann „Aktualisieren“ an.</p>
        </Notice>
      ) : null}

      {canPrompt && !standalone ? (
        <div className="toolbar">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() =>
              void promptInstall().then((outcome) =>
                setResult(outcome === 'angenommen' ? 'Installation gestartet. Das Symbol erscheint gleich auf dem Startbildschirm.' : outcome === 'abgelehnt' ? 'Installation abgebrochen.' : 'Der Browser bietet gerade keine direkte Installation an. Bitte die Schritte unten nutzen.'),
              )
            }
          >
            Jetzt installieren
          </button>
        </div>
      ) : null}
      {result ? <p role="status">{result}</p> : null}

      <section className="section" aria-labelledby="chrome">
        <SectionTitle id="chrome">Chrome auf dem Galaxy S25+</SectionTitle>
        <ol className="steps">
          <li>Die Adresse der App in Chrome öffnen.</li>
          <li>Oben rechts auf das Menü mit den drei Punkten tippen.</li>
          <li>„App installieren“ wählen. Steht dort nur „Zum Startbildschirm hinzufügen“, dieses wählen und anschließend „Installieren“.</li>
          <li>Bestätigen. Das Symbol „TR-Vergleich“ liegt danach auf dem Startbildschirm.</li>
        </ol>
      </section>

      <section className="section" aria-labelledby="samsung">
        <SectionTitle id="samsung">Samsung Internet</SectionTitle>
        <ol className="steps">
          <li>Die Adresse der App in Samsung Internet öffnen.</li>
          <li>Unten rechts auf das Menü mit den drei Strichen tippen.</li>
          <li>„Seite hinzufügen zu“ und dann „Startbildschirm“ wählen. Manche Versionen zeigen stattdessen in der Adressleiste ein Symbol zum Installieren.</li>
          <li>Mit „Hinzufügen“ bestätigen.</li>
        </ol>
        <p className="section-note">Die Menübezeichnungen können je nach Browserversion leicht abweichen.</p>
      </section>

      <section className="section" aria-labelledby="danach">
        <SectionTitle id="danach">Nach der Installation</SectionTitle>
        <ul className="prose">
          <li>Beim ersten Öffnen ist eine Internetverbindung nötig. Danach bleibt der zuletzt geladene Stand auch offline lesbar.</li>
          {crypto?.enabled ? <li>Einmalig den Zugangsschlüssel eingeben. Er wird nur auf diesem Gerät als nicht auslesbarer Schlüssel gespeichert.</li> : null}
          <li>Watchlist und Einstellungen liegen nur auf diesem Gerät. Unter „Einstellungen“ lassen sie sich als Datei sichern.</li>
          <li>Die App ist kein Produkt von Trade Republic und kann keine Orders ausführen.</li>
        </ul>
      </section>
    </div>
  );
}
