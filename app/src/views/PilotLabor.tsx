/* Strategielabor unter „Pilot“ (Gesamtauftrag vom 31.10.2026, Abschnitte 12, 13, 15): was das Labor geprüft hat, was es
 * verworfen und warum, welche Varianten validiert sind und vorwärts laufen, wie das Auswahlverfahren im Walk-forward abschneidet.
 * Nur Anzeige: Gerechnet wird im Lauf; eine Variante übernimmt nie ungefragt das Pilotdepot. */

import { Disclosure, EmptyState, KeyValues, Notice, SectionTitle } from '../components/ui';
import * as f from '../lib/format';
import {
  MODUS_TEXT,
  nachFamilie,
  PARAMETER_TEXT,
  parameterText,
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

function kurz(k: LaborKennzahlen | undefined | null): string {
  if (!k) return '–';
  return `${pct(k.rendite_pct)}, Rückgang ${f.plainPct(k.max_rueckgang_pct, 1)}, ${f.plural(k.kaeufe, 'Kauf', 'Käufe')}`;
}

export function PilotLabor({ stand }: { stand: PilotStand }) {
  const e = stand.labor;
  if (!e) {
    return (
      <EmptyState title="Noch kein Laborlauf">
        <p>
          Das Strategielabor erzeugt Varianten aus den Familien A–H (zum Beispiel viele Platz-1-Platzierungen, gleichmäßiger Anstieg, kurzfristige Spitzenreiter),
          rechnet sie über vergangene Handelstage nach und prüft sie zeitlich getrennt. Es läuft auf Anforderung (Befehl <code>spielgeld-labor</code>), nicht
          ständig im Hintergrund; sein Ergebnis erscheint hier mit dem nächsten Spielgeld-Stand.
        </p>
      </EmptyState>
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

      <WalkForward e={e} />

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
