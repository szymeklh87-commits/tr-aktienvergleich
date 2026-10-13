/* „Jetzt aktualisieren“: den Serverlauf auf Wunsch starten und auf das Ergebnis warten.
 *
 * Gestartet wird auf GitHub mit der eigenen Anmeldung – die App enthält bewusst keinen Schlüssel,
 * mit dem sie den Lauf selbst auslösen könnte. Danach liest die App status.json jede Minute neu und
 * meldet das Ergebnis: neuer Kursstand, „keine neuen Kurse“ (mit Grund) oder ein anderer Laufstatus.
 */

import { useState } from 'react';
import { KeyValues, Notice, SectionTitle } from '../components/ui';
import * as f from '../lib/format';
import { clock, nextCutoff, outcomeText } from '../lib/update';
import { useApp } from '../state/AppState';

export function UpdateView() {
  const { status, active, offline, updateWait, updateResult, startUpdateWait, stopUpdateWait, clearUpdateResult, checkNow, reload } = useApp();
  const [checked, setChecked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const links = status?.aktualisieren ?? null;
  const next = nextCutoff(status);
  const run = status?.last_run ?? null;

  const check = async () => {
    setBusy(true);
    const reached = await checkNow();
    setBusy(false);
    setChecked(reached ? `Geprüft um ${clock(Date.now())}.` : 'Server nicht erreichbar – später noch einmal versuchen.');
  };

  const result = updateResult ? outcomeText(updateResult) : null;

  return (
    <div className="view update-view">
      <header className="view-head">
        <p className="lede">Holt die neuesten Schlusskurse und rechnet alle Ranglisten neu – jederzeit, zusätzlich zum täglichen Lauf um {status?.schedule?.uhrzeit ?? '06:00'} Uhr.</p>
      </header>

      {result ? (
        <Notice
          tone={updateResult!.outcome === 'neuer_stand' ? 'info' : 'warn'}
          title={result.title}
          actions={
            updateResult!.outcome === 'neuer_stand' ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  clearUpdateResult();
                  reload();
                }}
              >
                Neuen Stand anzeigen
              </button>
            ) : (
              <button type="button" className="btn" onClick={clearUpdateResult}>
                Ausblenden
              </button>
            )
          }
        >
          <p>{result.text}</p>
        </Notice>
      ) : null}

      <section className="section" aria-labelledby="starten">
        <SectionTitle id="starten">Lauf starten</SectionTitle>
        {links ? (
          <div className="toolbar">
            <a className="btn btn-primary" href={links.starten_url} target="_blank" rel="noopener noreferrer" onClick={startUpdateWait}>
              Lauf auf GitHub starten
            </a>
            <button type="button" className="btn" onClick={() => void check()} disabled={busy}>
              Jetzt nach neuem Stand schauen
            </button>
          </div>
        ) : (
          <Notice tone="info" title="In dieser Umgebung nicht verfügbar">
            <p>Der Start über GitHub steht nur in der eingerichteten App zur Verfügung (GitHub Pages).</p>
            <div className="toolbar">
              <button type="button" className="btn" onClick={() => void check()} disabled={busy}>
                Jetzt nach neuem Stand schauen
              </button>
            </div>
          </Notice>
        )}
        {next ? (
          <p className={`section-note${next.ready ? '' : ' update-hint'}`}>
            {next.ready
              ? `Neue Schlusskurse für ${next.sessionText} liegen vor – ein Lauf jetzt bringt einen neuen Stand.`
              : `Neue Schlusskurse für ${next.sessionText} gibt es ${next.readyText}. Ein Lauf vorher bringt keinen neuen Kursstand, setzt aber die Zuordnung der Aktien fort und übernimmt nachgelieferte Kurse.`}
          </p>
        ) : null}
        {checked ? <p role="status" className="section-note">{checked}</p> : null}
        {offline ? <p className="section-note">Offline: Die App kann gerade nicht nachsehen.</p> : null}
        {links ? (
          <ol className="steps">
            <li>„Lauf auf GitHub starten“ antippen. GitHub öffnet die Seite „Täglicher Lauf“ – falls nötig dort anmelden.</li>
            <li>„Run workflow“ antippen und mit dem grünen Knopf „Run workflow“ bestätigen. Die Eingabefelder leer lassen.</li>
            <li>Zurück in diese App wechseln. Sie schaut jede Minute nach und meldet das Ergebnis; ein Lauf dauert einige Minuten bis etwa eine Stunde.</li>
          </ol>
        ) : null}
      </section>

      {updateWait ? (
        <Notice
          tone="info"
          title="Warte auf das Ergebnis"
          actions={
            <button type="button" className="btn" onClick={stopUpdateWait}>
              Warten beenden
            </button>
          }
        >
          <p>
            Angefordert um {clock(updateWait.since)}. Die App schaut jede Minute nach, solange sie geöffnet ist{updateWait.lastCheck ? ` (zuletzt ${clock(updateWait.lastCheck)})` : ''}.
          </p>
          {links ? (
            <p>
              <a href={links.laeufe_url} target="_blank" rel="noopener noreferrer">
                Läufe auf GitHub ansehen
              </a>
            </p>
          ) : null}
        </Notice>
      ) : null}

      <section className="section" aria-labelledby="stand-jetzt">
        <SectionTitle id="stand-jetzt">Stand jetzt</SectionTitle>
        <KeyValues
          items={[
            ['Kursstand in der App', active ? `${f.isoDate(active.cutoff_session_date)} (berechnet ${f.berlinTime(active.computed_at_utc)})` : 'noch kein Datenstand'],
            [
              'Letzter Lauf',
              run
                ? `${f.berlinTime(run.finished_at_utc ?? run.started_at_utc)}: ${f.runStatus(run.status)}${run.message && run.status !== 'veroeffentlicht' ? ` – ${run.message}` : ''}`
                : 'noch keiner',
            ],
            ['Nächste neue Schlusskurse', next ? `für ${next.sessionText}: ${next.ready ? 'liegen vor' : next.readyText}` : 'einmal je Börsentag, frühestens etwa eine Stunde nach Handelsschluss in New York (meist gegen 23 Uhr)'],
          ]}
        />
      </section>

      <section className="section" aria-labelledby="warum">
        <SectionTitle id="warum">Warum über GitHub?</SectionTitle>
        <p>
          Die App enthält absichtlich keinen Zugangsschlüssel, mit dem sie Läufe selbst starten könnte – Schlüssel gehören nicht ins Handy. Gestartet wird deshalb mit deiner eigenen GitHub-Anmeldung. Ein
          laufender Lauf wird nie doppelt gestartet: Ein zweiter Start wartet, bis der erste fertig ist.
        </p>
        <p>Neue Kurse gibt es nur für abgeschlossene Börsentage. Livekurse während des Handels liefert die App nicht.</p>
      </section>
    </div>
  );
}
