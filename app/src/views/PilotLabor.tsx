/* Strategielabor unter „Pilot“ (Gesamtauftrag vom 31.10.2026, Abschnitte 12, 13, 15): was das Labor geprüft hat, was es
 * verworfen und warum, welche Varianten validiert sind und vorwärts laufen, wie das Auswahlverfahren im Walk-forward abschneidet.
 * Nur Anzeige: Gerechnet wird im Lauf; eine Variante übernimmt nie ungefragt das Pilotdepot. */

import { useState } from 'react';
import { Disclosure, EmptyState, KeyValues, Notice, SectionTitle, Segmented } from '../components/ui';
import { useUpdates } from '../state/UpdateState';
import * as f from '../lib/format';
import {
  kennzahlenKurz,
  MODUS_TEXT,
  nachFamilie,
  PARAMETER_TEXT,
  parameterText,
  signalZeilen,
  STATUS_TEXT,
  vorschlaege,
  vorwaertsDepotId,
  zeitraum,
  type LaborErgebnis,
  type LaborKennzahlen,
  type LaborVariante,
  type LaborZeitraum,
} from '../lib/labor';
import type { PilotStand } from '../lib/pilot';
import { buildHash } from '../lib/router';

const pct = (v: number | null | undefined) => f.signedPctValue(v ?? null, 1);

/** „04.09.–14.09.“ – mit Jahr nur, wenn die Spanne nicht im Jahr des Laborlaufs liegt. */
function spanne(von: string, bis: string, bezug: string): string {
  const kurzDatum = (iso: string) => `${iso.slice(8, 10)}.${iso.slice(5, 7)}.`;
  const jahr = bezug.slice(0, 4);
  return von.slice(0, 4) === jahr && bis.slice(0, 4) === jahr ? `${kurzDatum(von)}–${kurzDatum(bis)}` : `${f.isoDate(von)}–${f.isoDate(bis)}`;
}

function zr(z: LaborZeitraum | undefined): string {
  return z ? `${f.isoDate(z.von)} – ${f.isoDate(z.bis)} (${f.integer(z.tage)} Handelstage)` : '–';
}

const kurz = (k: LaborKennzahlen | undefined | null) => kennzahlenKurz(k);

/** Laborlauf auf GitHub starten (Abschnitt 17: historischen Test aus der App). Rechnet nicht im Handy und ändert kein Depot. */
function LaborStarten({ offen = false }: { offen?: boolean }) {
  const { startLabor } = useUpdates();
  const [tage, setTage] = useState('120');
  const [busy, setBusy] = useState(false);
  const [antwort, setAntwort] = useState<{ ok: boolean; text: string; runUrl?: string | null } | null>(null);
  return (
    <Disclosure summary="Neuen Laborlauf starten" defaultOpen={offen}>
      <p className="section-note">
        Rechnet alle Varianten über die gewählten Handelstage auf GitHub nach – mit echten Kursen dauert das etwa so lange wie eine historische Simulation derselben
        Länge (rund eine halbe Minute je Handelstag). Das Ergebnis übernimmt der nächste tägliche Lauf; erst dann steht es hier, und validierte Varianten starten als
        eigene Spielgelddepots. Es läuft nur, wenn du es startest.
      </p>
      <Segmented
        label="Handelstage"
        value={tage}
        onChange={setTage}
        options={[
          { value: '60', label: '60' },
          { value: '120', label: '120' },
          { value: '250', label: '250' },
        ]}
      />
      <div className="toolbar">
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setAntwort(await startLabor(Number(tage)));
            setBusy(false);
          }}
        >
          Laborlauf starten
        </button>
      </div>
      {antwort ? (
        <p className="section-note" role="status">
          {antwort.text}
          {antwort.runUrl ? (
            <>
              {' '}
              <a href={antwort.runUrl} target="_blank" rel="noreferrer">
                Lauf auf GitHub
              </a>
            </>
          ) : null}
        </p>
      ) : null}
    </Disclosure>
  );
}

export function PilotLabor({ stand }: { stand: PilotStand }) {
  const e = stand.labor;
  if (!e) {
    return (
      <>
        <EmptyState title="Noch kein Laborlauf">
          <p>
            Das Strategielabor erzeugt Varianten aus den Familien A–H (zum Beispiel viele Platz-1-Platzierungen, gleichmäßiger Anstieg, kurzfristige Spitzenreiter),
            rechnet sie über vergangene Handelstage nach und prüft sie zeitlich getrennt. Es läuft nur auf Anforderung, nicht ständig im Hintergrund; sein Ergebnis
            erscheint hier mit dem nächsten Spielgeld-Stand.
          </p>
        </EmptyState>
        <LaborStarten offen />
      </>
    );
  }
  const e1 = zeitraum(e, 'entwicklung');
  const v1 = zeitraum(e, 'validierung');
  const t1 = zeitraum(e, 'test');
  const z = e.zaehlung;
  const vor = vorschlaege(e);
  return (
    <>
      <Notice tone={e.synthetisch ? 'demo' : 'info'} compact>
        <strong>Strategielabor</strong> · nachgerechnet über vergangene Handelstage, kein Vorwärtsergebnis · Lauf vom {f.isoDate(e.erstellt_utc.slice(0, 10))}
      </Notice>

      <section className="section" aria-labelledby="labor-kurz">
        <SectionTitle id="labor-kurz">Ergebnis auf einen Blick</SectionTitle>
        <KeyValues
          items={[
            ['Varianten geprüft', `${f.integer(e.kennzahlen.varianten)} aus ${f.integer(new Set(e.varianten.map((v) => v.familie)).size)} Familien`],
            ['Verworfen', f.integer(z.verworfen)],
            ['Robust, nicht ausgewählt', f.integer(z.nicht_ausgewaehlt)],
            ['In der Validierung verworfen', f.integer(z.validierung_verfehlt)],
            ['Validiert', f.integer(z.validiert + z.vorwaerts)],
            ['Im Vorwärtstest', f.integer(z.vorwaerts)],
            ['Entwicklung', zr(e1)],
            ['Validierung', zr(v1)],
            ['Test (wählt nichts aus)', zr(t1)],
            ['Übernahme', MODUS_TEXT[e.uebernahme.modus] ?? e.uebernahme.modus],
          ]}
        />
      </section>

      <section className="section" aria-labelledby="labor-vorschlag">
        <SectionTitle id="labor-vorschlag">Vorschlag für den Vorwärtstest</SectionTitle>
        {vor.length ? (
          <ol className="labor-list">
            {vor.map((v) => (
              <Vorschlag key={v.id} v={v} e={e} stand={stand} />
            ))}
          </ol>
        ) : (
          <p className="section-note">
            Keine Variante hat Entwicklung und Validierung bestanden – also gibt es diesmal keinen Vorschlag. Das ist ein Ergebnis, kein Fehler: Lieber keine Strategie
            als eine, die nur im Rückblick gut aussieht.
          </p>
        )}
      </section>

      <Laufende e={e} stand={stand} />

      <WalkForward e={e} />

      <Signalpruefung e={e} />

      <section className="section" aria-labelledby="labor-varianten">
        <SectionTitle id="labor-varianten">Alle Varianten</SectionTitle>
        <p className="section-note">
          Je Familie zuerst die weitergekommenen Varianten. „Entwicklung“: Rendite nach Kosten im ersten Zeitraum, aus dem allein ausgewählt wird. Welt-ETF im
          selben Zeitraum: {pct(e.vergleich[e1?.schluessel ?? 'e']?.rendite_pct)}.
        </p>
        {nachFamilie(e).map((g) => {
          const weiter = g.varianten.filter((v) => v.status === 'validiert' || v.status === 'vorwaerts').length;
          const beste = Math.max(...g.varianten.map((v) => v.entwicklung.rendite_pct));
          return (
            <div key={g.familie} className="labor-family" data-familie={g.familie}>
              <Disclosure
                defaultOpen={weiter > 0}
                summary={
                  <>
                    <b>
                      {g.familie}: {g.name}
                    </b>{' '}
                    <span className="muted">
                      · {f.plural(g.varianten.length, 'Variante', 'Varianten')}, {weiter ? `${weiter} validiert` : 'keine validiert'}, beste Entwicklung {pct(beste)}
                    </span>
                  </>
                }
              >
                <ul className="labor-list">
                  {g.varianten.map((v) => (
                    <VarianteZeile key={v.id} v={v} />
                  ))}
                </ul>
              </Disclosure>
            </div>
          );
        })}
      </section>

      {e.parameterwirkung.length ? (
        <section className="section" aria-labelledby="labor-wirkung">
          <SectionTitle id="labor-wirkung">Wirkung der Parameter</SectionTitle>
          <p className="section-note">Median der Entwicklungsrendite aller Varianten einer Familie mit diesem Wert – Hinweis auf wirksame Parameter, kein Beweis.</p>
          <ul className="plain-list">
            {e.parameterwirkung.map((w) => (
              <li key={`${w.familie}-${w.parameter}`}>
                <b>
                  {w.familie} · {PARAMETER_TEXT[w.parameter] ?? w.parameter}:
                </b>{' '}
                {w.werte.map((x) => `${String(x.wert).replace('.', ',')} → ${pct(x.median_rendite_pct)} (${x.positiv} von ${x.varianten} positiv)`).join('; ')}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="section" aria-labelledby="labor-grenzen">
        <SectionTitle id="labor-grenzen">So ist das Ergebnis zu lesen</SectionTitle>
        <ul className="plain-list">
          {e.hinweise.map((h) => (
            <li key={h}>{h}</li>
          ))}
        </ul>
        <LaborStarten />
        <Disclosure summary="Verfahren und Rechenaufwand">
          <p className="section-note">
            Je Variante und Zeitraum ein eigenes Spielgelddepot mit gleichem Startkapital und demselben Tagesschritt wie im Vorwärtstest (Kosten, Ausführung am
            Folgetag, Stops, Risikogrenzen). Robust heißt: genug Käufe, Rückgang unter der Grenze, nach Kosten positiv und mindestens eine benachbarte Variante im
            Gitter ebenfalls positiv. Die besten robusten Varianten müssen danach in der Validierung bestehen; der Testzeitraum wird nur berichtet.
          </p>
          <KeyValues
            items={[
              ['Spielgelddepots', f.integer(e.kennzahlen.depots)],
              ['Handelstage nachgerechnet', f.integer(e.kennzahlen.tage)],
              ['Rechenkern-Läufe', f.integer(e.kennzahlen.rechnungen)],
              ['Rechenzeit', `${f.integer(Math.round(e.kennzahlen.sekunden.gesamt ?? 0))} s`],
              ['Datenstand', e.datenstand],
              ['Laborversion', e.version],
            ]}
          />
        </Disclosure>
      </section>
    </>
  );
}

function Vorschlag({ v, e, stand }: { v: LaborVariante; e: LaborErgebnis; stand: PilotStand }) {
  const depotId = vorwaertsDepotId(e, v.id);
  const depot = stand.depots.find((d) => d.id === depotId || d.id.startsWith(`${depotId}-`));
  const welt = (k: string) => e.vergleich[k]?.rendite_pct ?? null;
  return (
    <li className="labor-item labor-item-lead">
      <div className="labor-head">
        <span className="labor-name">{v.name}</span>
        <span className="badge badge-ok badge-wrap">{STATUS_TEXT[v.status]}</span>
      </div>
      <KeyValues
        items={[
          ['Entwicklung', `${kurz(v.entwicklung)} · Welt‑ETF ${pct(welt('e'))}`],
          ['Validierung', `${kurz(v.validierung)} · Welt‑ETF ${pct(welt('v'))}`],
          ['Test (nur berichtet)', `${kurz(v.test)} · Welt‑ETF ${pct(welt('t'))}`],
          ['Parameter', parameterText(v.parameter)],
        ]}
      />
      <p className="section-note">{v.regel?.beschreibung}</p>
      <div className="toolbar">
        {depot ? (
          <a className="btn btn-primary" href={`#/pilot/depot/${encodeURIComponent(depot.id)}`}>
            Vorwärtsdepot öffnen
          </a>
        ) : (
          <span className="section-note">Das Vorwärtsdepot startet mit dem nächsten täglichen Lauf.</span>
        )}
        {v.regel ? (
          <a className="btn btn-quiet" href={buildHash('/pilot/neu', { labor: v.id })}>
            Als Kopie bearbeiten
          </a>
        ) : null}
      </div>
    </li>
  );
}

function VarianteZeile({ v }: { v: LaborVariante }) {
  const tone = v.status === 'vorwaerts' || v.status === 'validiert' ? 'badge-ok' : v.status === 'verworfen' ? '' : 'badge-warn';
  return (
    <li className="labor-item">
      <div className="labor-head">
        <span className="labor-name">{v.name.replace(/^Labor [A-H]: /, '')}</span>
        <span className="labor-fig">{pct(v.entwicklung.rendite_pct)}</span>
      </div>
      <div className="labor-meta">
        <span className={`badge badge-wrap ${tone}`.trim()}>{STATUS_TEXT[v.status]}</span>
        {v.grund && v.status !== 'vorwaerts' ? <span className="muted">{v.grund}</span> : null}
      </div>
      <p className="labor-zahlen">
        <b>Entwicklung</b> {kurz(v.entwicklung)}, Wertung {f.integer(Math.round(v.entwicklung.wertung ?? 0))} von 100
        {v.validierung ? (
          <>
            {' · '}
            <b>Validierung</b> {kurz(v.validierung)}
          </>
        ) : null}
        {v.test ? (
          <>
            {' · '}
            <b>Test</b> {kurz(v.test)}
          </>
        ) : null}
      </p>
    </li>
  );
}

/** Abschnitte 14 und 17: die laufenden Strategien (Vorlagen, eigene Regeln) über dieselben drei Zeiträume – nur zum Vergleich. */
function Laufende({ e, stand }: { e: LaborErgebnis; stand: PilotStand }) {
  const kurzName = (name: string) => name.replace(/^(Vorlage|Eigene Regel): /, '');
  const rows = [...(e.laufende ?? [])].sort((a, b) => kurzName(a.name).localeCompare(kurzName(b.name), 'de') || a.depot.localeCompare(b.depot));
  if (!rows.length) return null;
  const welt = (k: string) => e.vergleich[k]?.rendite_pct ?? null;
  /** ohne Kauf im Zeitraum kein Ergebnis – „0,0 %“ sähe wie eines aus */
  const zahl = (k: LaborKennzahlen) => (k.kaeufe ? pct(k.rendite_pct) : '–');
  const ohneKauf = rows.some((x) => !x.entwicklung.kaeufe || !x.validierung.kaeufe || !x.test.kaeufe);
  return (
    <section className="section" aria-labelledby="labor-laufende">
      <SectionTitle id="labor-laufende">Laufende Strategien im selben Zeitraum</SectionTitle>
      <p className="section-note">
        Vorlagen und eigene Regeln aus dem Vorwärtstest, mit demselben Motor über Entwicklung, Validierung und Test nachgerechnet – nur zum Vergleich. Sie gehen in
        keine Auswahl ein; ihr Vorwärtstest läuft unverändert weiter. Rendite nach Kosten.
      </p>
      <div className="table-wrap">
        <table className="table pilot-table labor-table labor-laufende">
          <thead>
            <tr>
              <th>Strategie</th>
              <th className="n">Entw.</th>
              <th className="n">Valid.</th>
              <th className="n">Test</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((x) => {
              const offen = stand.depots.some((d) => d.id === x.depot);
              return (
                <tr key={x.depot} data-depot={x.depot}>
                  <td>
                    {offen ? <a href={`#/pilot/depot/${encodeURIComponent(x.depot)}`}>{kurzName(x.name)}</a> : kurzName(x.name)}
                    <br />
                    <span className="muted">{x.quelle === 'eigene' ? 'eigene Regel' : 'Vorlage'}</span>
                  </td>
                  <td className="n">{zahl(x.entwicklung)}</td>
                  <td className="n">{zahl(x.validierung)}</td>
                  <td className="n">{zahl(x.test)}</td>
                </tr>
              );
            })}
            <tr className="labor-ref">
              <td>Welt-ETF (kaufen und halten)</td>
              <td className="n">{pct(welt('e'))}</td>
              <td className="n">{pct(welt('v'))}</td>
              <td className="n">{pct(welt('t'))}</td>
            </tr>
          </tbody>
        </table>
      </div>
      {ohneKauf ? <p className="section-note">„–“: kein Kauf im Zeitraum – die Bedingungen der Regel waren an keinem Tag erfüllt oder nicht prüfbar.</p> : null}
    </section>
  );
}

/** Abschnitte 5.2, 5.3, 6: Ließen Platz-1-Häufigkeit, Top-10-Stabilität und Trendqualität bessere Folgerenditen erwarten? */
function Signalpruefung({ e }: { e: LaborErgebnis }) {
  const zeilen = signalZeilen(e);
  if (!zeilen.length) return null;
  const pp = (v: number | undefined) => (v === undefined ? '–' : f.signedPctValue(v, 1).replace('%', 'pp'));
  return (
    <section className="section" aria-labelledby="labor-signale">
      <SectionTitle id="labor-signale">Signale im Rückblick: Folgerendite</SectionTitle>
      <p className="section-note">
        Hatten Aktien mit dem Signal danach eine höhere Rendite als das Mittel aller Aktien desselben Tages? „Besser an“: Anteil der Tage, an denen das so war.
      </p>
      <ul className="labor-list">
        {zeilen.map((z) => (
          <li key={z.signal} className="labor-item" data-signal={z.signal}>
            <div className="labor-head">
              <span className="labor-name">{z.text}</span>
            </div>
            <p className="labor-zahlen">
              {z.je.map((x, i) => (
                <span key={x.horizont}>
                  {i ? ' · ' : ''}
                  <b>{x.horizont} Tage</b>{' '}
                  {x.tage ? `${pp(x.mittel_ueberschuss_pp)} zum Tagesmittel, besser an ${f.plainPct(x.trefferquote_pct ?? null, 0)} von ${f.plural(x.tage, 'Tag', 'Tagen')}` : 'keine Fälle mit Folgekursen'}
                </span>
              ))}
            </p>
          </li>
        ))}
      </ul>
      <p className="section-note">{e.signalpruefung?.hinweis}</p>
    </section>
  );
}

function WalkForward({ e }: { e: LaborErgebnis }) {
  const w = e.walk_forward;
  const s = w.zusammenfassung;
  const by = new Map(e.varianten.map((v) => [v.id, v]));
  return (
    <section className="section" aria-labelledby="labor-wf">
      <SectionTitle id="labor-wf">Walk-forward: taugt das Auswahlverfahren?</SectionTitle>
      {s.faltungen ? (
        <>
          <p className="section-note">
            In {f.integer(s.faltungen)} Faltungen wählte dasselbe Verfahren im Training eine Variante; gezählt wird nur ihr Ergebnis im anschließenden
            Prüfzeitraum. Mittel {pct(s.mittel_rendite_pct)} gegenüber Welt-ETF {pct(s.mittel_welt_pct)}; besser als der Welt-ETF in {f.integer(s.besser_als_welt)} von{' '}
            {f.integer(s.mit_wahl)}, positiv in {f.integer(s.positiv)}; die Wahl wechselte {f.plural(s.wechsel, 'Mal', 'Mal')}.
          </p>
          <div className="table-wrap">
            <table className="table pilot-table labor-table">
              <thead>
                <tr>
                  <th>Prüfzeitraum</th>
                  <th>Gewählt im Training</th>
                  <th className="n">Ergebnis</th>
                  <th className="n">Welt-ETF</th>
                </tr>
              </thead>
              <tbody>
                {w.faltungen.map((x) => (
                  <tr key={x.faltung}>
                    <td>{spanne(x.pruefung.von, x.pruefung.bis, e.datentag)}</td>
                    <td>{x.gewaehlt ? (by.get(x.gewaehlt)?.name ?? x.gewaehlt).replace(/^Labor /, '') : 'keine robuste Variante'}</td>
                    <td className="n">{x.gewaehlt ? pct(x.rendite_pct) : '–'}</td>
                    <td className="n">{pct(x.welt_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="section-note">Der Zeitraum reicht für keine Faltung aus Training und Prüfung.</p>
      )}
    </section>
  );
}
