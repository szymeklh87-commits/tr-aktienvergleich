/* Einrichtung des Spielgelddepots (Abschnitte 11 und 29.2): Startkapital (Spielgeld), fünf Fragen, aktiver Anteil – daraus
 * das Testprofil des Robo-Kerns mit offener Herleitung, vor dem Start sichtbar. Kein echtes Vermögen, keine Anlageberatung. */

import { useState } from 'react';
import { PilotSenden } from '../components/pilotsenden';
import { EmptyState, KeyValues, Notice, SectionTitle, Segmented } from '../components/ui';
import * as f from '../lib/format';
import { profilAusTabelle, type PilotStand } from '../lib/pilot';

export function PilotEinrichtung({ stand }: { stand: PilotStand }) {
  const e = stand.einrichtung;
  const aktuell = e?.aktuell ?? null;
  const [kapital, setKapital] = useState<number>(aktuell?.startkapital_eur ?? e?.startkapital_vorgabe ?? 10_000);
  const [antworten, setAntworten] = useState<Record<string, number>>(() => ({ ...(aktuell?.profil.antworten ?? {}) }));
  const [aktiv, setAktiv] = useState<number>(aktuell?.aktiver_anteil ?? e?.aktiver_anteil_max ?? 0.3);
  if (!e) return <EmptyState title="Einrichtung noch nicht verfügbar">Sie kommt mit dem nächsten Spielgeld-Stand.</EmptyState>;
  const vorschau = profilAusTabelle(e.tabelle, antworten);
  const kapitalOk = Number.isFinite(kapital) && kapital >= e.startkapital_min && kapital <= e.startkapital_max;
  const pilot = stand.depots.find((d) => d.art === 'pilot' && !d.historisch);
  const grenzen = pilot?.verlust?.grenzen ?? {};
  return (
    <section className="section pilot-editor">
      <SectionTitle>Einrichtung des Spielgelddepots</SectionTitle>
      <Notice tone="info" compact>
        Testprofil für das Spielgeld – keine Anlageberatung und keine bestätigte persönliche Zielaufteilung. Echtes Vermögen wird nicht abgefragt.
      </Notice>
      {aktuell ? (
        <p className="section-note">
          Aktuell: {f.euro(aktuell.startkapital_eur)} Spielgeld, {aktuell.profil.name} ({f.plainPct(aktuell.profil.welt * 100, 0)} Welt / {f.plainPct(aktuell.profil.geldmarkt * 100, 0)}{' '}
          Geldmarkt), aktiver Anteil höchstens {f.plainPct(aktuell.aktiver_anteil * 100, 0)}.
        </p>
      ) : (
        <p className="section-note">Noch keine Einrichtung: der Robo nutzt die Vorgabe „Ausgewogen (nicht bestätigt)“ mit 70 % Welt / 30 % Geldmarkt.</p>
      )}
      <fieldset className="pilot-fieldset">
        <legend>Startkapital (Spielgeld)</legend>
        <label className="field">
          <span className="field-label">
            Betrag in Euro ({f.euro(e.startkapital_min)} bis {f.euro(e.startkapital_max)})
          </span>
          <input className="input" type="number" inputMode="decimal" min={e.startkapital_min} max={e.startkapital_max} step={100} value={String(kapital)} onInput={(ev: Event) => setKapital(Number((ev.target as HTMLInputElement).value))} />
        </label>
        <p className="section-note">Frei wählbar und keine Aussage über dein echtes Kapital. Gebühren und ganze Stücke werden auch bei kleinen Beträgen berücksichtigt.</p>
      </fieldset>
      {e.fragen.map((q, qi) => (
        <fieldset className="pilot-fieldset" key={q.id}>
          <legend>
            {qi + 1}. {q.frage}
          </legend>
          {q.antworten.map((text, i) => (
            <label className="check" key={i}>
              <input type="radio" name={`frage-${q.id}`} checked={antworten[q.id] === i} onChange={() => setAntworten({ ...antworten, [q.id]: i })} />
              <span>{text}</span>
            </label>
          ))}
        </fieldset>
      ))}
      <fieldset className="pilot-fieldset">
        <legend>Aktive Strategien S1–S3</legend>
        <Segmented
          label="höchstens"
          value={String(aktiv)}
          onChange={(v) => setAktiv(Number(v))}
          options={e.aktiv_anteile.filter((a) => a <= e.aktiver_anteil_max + 1e-9).map((a) => ({ value: String(a), label: `${Math.round(a * 100)} %` }))}
        />
      </fieldset>
      <section className="section" aria-labelledby="ein-vorschau">
        <SectionTitle id="ein-vorschau">Vor dem Start</SectionTitle>
        {vorschau ? (
          <KeyValues
            items={[
              ['Punkte', `${vorschau.punkte} von 20`],
              ['Robo-Kern', `${f.plainPct(vorschau.welt * 100, 0)} Welt-Aktien-ETF / ${f.plainPct(100 - vorschau.welt * 100, 0)} Geldmarkt-ETF`],
              [
                'Herleitung',
                `30 % plus 3,5 Prozentpunkte je Punkt, auf 5 abgerundet${vorschau.begrenzt ? `; begrenzt durch den verkraftbaren Rückgang von ${e.verlust_pct[antworten.verlust]} % (Szenario: Welt-ETF vorübergehend −${Math.round(e.welt_rueckgang * 100)} %)` : ''}`,
              ],
              ['Aufteilung des Depots', `Kern ${f.plainPct(100 - aktiv * 100, 0)}, aktive Strategien höchstens ${f.plainPct(aktiv * 100, 0)}`],
              [
                'Risikogrenzen des aktiven Teils',
                grenzen.tag !== undefined
                  ? `Tagesverlust ≥ ${f.plainPct(grenzen.tag * 100, 0)}: keine neuen Käufe bis zur nächsten Sitzung; Rückgang ≥ ${f.plainPct(grenzen.nur_risikosenkend * 100, 0)}: nur risikosenkend; ≥ ${f.plainPct(grenzen.schliessen * 100, 0)}: aktive Positionen schließen`
                  : 'zentrale Grenzen des Risiko-Managers',
              ],
              ['Wirkung', 'ab dem nächsten täglichen Lauf: Pilotdepot und Vergleichsdepots starten als neuer Test; der bisherige Lauf bleibt in der Chronik'],
            ]}
          />
        ) : (
          <p className="section-note">Bitte alle fünf Fragen beantworten.</p>
        )}
        {!kapitalOk ? <p className="section-note">Startkapital außerhalb der Grenzen.</p> : null}
        <PilotSenden
          art="pilot_einrichten"
          inhalt={{ startkapital_eur: kapital, antworten, aktiver_anteil: aktiv }}
          bezeichnung={`Einrichtung: ${f.euro(kapital)}, ${vorschau ? `${Math.round(vorschau.welt * 100)} % Welt` : '–'}`}
          label="Einrichtung an den Robo senden"
          disabled={!vorschau || !kapitalOk}
          primary
        />
      </section>
    </section>
  );
}
