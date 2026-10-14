/* „Jetzt aktualisieren“: den Serverlauf auf Wunsch starten und auf das Ergebnis warten.
 *
 * Gestartet wird auf GitHub mit der eigenen Anmeldung – die App enthält bewusst keinen Schlüssel,
 * mit dem sie den Lauf selbst auslösen könnte. Danach liest die App status.json alle 15 Sekunden neu und
 * meldet das Ergebnis: neuer Kursstand, „keine neuen Kurse“ (mit Grund) oder ein anderer Laufstatus.
 */

import { useState } from 'react';
import { Disclosure, KeyValues, Notice, SectionTitle } from '../components/ui';
import * as f from '../lib/format';
import { clock, nextCutoff, outcomeText } from '../lib/update';
import { berlinClock } from '../lib/intraday';
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
        <p className="lede">
          Ein Lauf holt die <strong>aktuellen Kurse</strong> und rechnet <strong>alles neu</strong> – jederzeit, zusätzlich zum täglichen Lauf um {status?.schedule?.uhrzeit ?? '07:00'} Uhr:
        </p>
        <ul className="update-list">
          <li>alle Ranglisten 1–90 Tage, Gruppe A und B, alle elf Gewichtungen</li>
          <li>Bericht 1–30, Top-10-Listen und Häufigkeit</li>
          <li>Musterdepots mit Beiträgen</li>
          <li>Kennzahlen, Kursziele und Gesamtwertung, sobald neue Schlusskurse da sind</li>
        </ul>
        <p className="section-note">
          Während des Handelstags als <strong>Zwischenstand</strong> mit den zuletzt gemeldeten Kursen (vorläufig, etwa 15–20 Minuten verzögert). Gibt es neue Schlusskurse, rechnet derselbe Lauf
          zuerst den Stand mit Schlusskursen.
        </p>
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
              Jetzt aktualisieren
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
            <li>„Jetzt aktualisieren“ antippen. GitHub öffnet die Seite „Täglicher Lauf“ – beim ersten Mal dort anmelden.</li>
            <li>
              „Run workflow“ antippen und mit dem grünen Knopf <strong>„Run workflow“</strong> bestätigen. Nichts ändern: „Alles aktualisieren“ ist voreingestellt.
            </li>
            <li>Zurück in diese App wechseln. Sie schaut alle 15 Sekunden nach und meldet „Neuer Stand“ – ein Zwischenstand dauert meist 2–3 Minuten, ein Lauf mit neuen Schlusskursen länger.</li>
          </ol>
        ) : null}
        {links ? (
          <Disclosure summary="Weitere Möglichkeiten im Formular „Run workflow“">
            <ul className="step-options">
              <li>
                <strong>Nur Kennzahlen, Kursziele und Signale</strong>: Haken bei „Nur Kennzahlen, Kursziele und Signale aktualisieren“ (etwa 20–40 Minuten, ohne neue Kurse).
              </li>
              <li>
                <strong>Stand mit Schlusskursen neu rechnen</strong>: Haken bei „Neu berechnen, auch wenn kein neuer Börsenschluss vorliegt“.
              </li>
              <li>
                Aktien von Börsen, die heute noch nicht geöffnet haben (z. B. New York vor 15:30 Uhr), fehlen in einem Zwischenstand – nichts wird geschätzt.
              </li>
            </ul>
          </Disclosure>
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
            Angefordert um {clock(updateWait.since)}. Die App schaut alle 15 Sekunden nach, solange sie geöffnet ist{updateWait.lastCheck ? ` (zuletzt ${clock(updateWait.lastCheck)})` : ''}.
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
            [
              'Kursstand in der App',
              active
                ? active.art === 'zwischenstand'
                  ? `Zwischenstand ${f.isoDate(active.cutoff_session_date)}, Kurse bis ${berlinClock(active.kurse_bis_utc)} (vorläufig)`
                  : `${f.isoDate(active.cutoff_session_date)} (berechnet ${f.berlinTime(active.computed_at_utc)})`
                : 'noch kein Datenstand',
            ],
            ...(status?.zwischenstand && active?.snapshot_id !== status.zwischenstand.snapshot_id
              ? ([['Zwischenstand', `${f.isoDate(status.zwischenstand.stichtag)}, Kurse bis ${berlinClock(status.zwischenstand.kurse_bis_utc)}`]] as [string, string][])
              : []),
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
        <p>
          Neue Schlusskurse gibt es nur für abgeschlossene Börsentage. Während des Handels rechnet ein Zwischenstand mit den zuletzt gemeldeten Kursen (verzögert) – Livekurse in
          Echtzeit liefert die App nicht.
        </p>
      </section>
    </div>
  );
}
