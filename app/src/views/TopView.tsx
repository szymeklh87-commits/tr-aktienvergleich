/* „Top nach Zahlen“ (ab 1.11): vollständige Rangfolge nach der festen Regel, die Regel selbst und die eigenen Aktien. */

import { useMemo, useState } from 'react';
import { MissingMarkets, OwnStocks, TopRow, useMissingMarkets, useTopRanking } from '../components/top';
import { ErrorNote, Loading, Segmented } from '../components/ui';
import { Explain } from '../components/explain';
import * as f from '../lib/format';
import { updateParams, type Route } from '../lib/router';
import { MICRO_CAP_EUR, MICRO_CAP_PENALTY, SMALL_CAP_EUR, SMALL_CAP_PENALTY, TOP_PART_LABEL, TOP_PARTS, TOP_POINTS, VOLUME_FULL } from '../lib/top';
import { useApp } from '../state/AppState';

const PAGE = 20;

export function TopView({ route }: { route: Route }) {
  const { manifest } = useApp();
  const top = useTopRanking();
  const missing = useMissingMarkets();
  const clean = route.params.get('ohne') === '1';
  // Ab 1.14: Rangfolge nur mit handelbaren Aktien (Gruppe B); „Auch wenig gehandelte“ zeigt alle mit Punkten, ohne Platz
  const withIlliquid = route.params.get('alle') === '1';
  const [shown, setShown] = useState(PAGE);
  const entries = useMemo(
    () => (top.result ? (withIlliquid ? top.result.entries : top.result.ranked).filter((e) => !clean || !e.warnings.length) : []),
    [top.result, clean, withIlliquid],
  );
  if (!manifest) return null;
  const leader = top.result?.ranked[0] ?? null;
  const illiquid = top.result ? top.result.entries.length - top.result.ranked.length : 0;

  return (
    <div className="view">
      <header className="view-head">
        <h2 className="view-title">Top nach Zahlen</h2>
        <Explain
          kinds={['rueckblick', 'rang', 'prognose']}
          term="top-nach-zahlen"
          sees={
            <>
              Gut gehandelte Aktien (Ø Tagesumsatz ab 10 Mio. USD), die in den Standard-Ranglisten mindestens einmal unter den ersten zehn standen – geordnet nach Punkten
              (höchstens 100). Die Regel ist jeden Tag gleich.
            </>
          }
          todo={<>Eine Aktie antippen: Sie zeigt, woher jeder Punkt kommt. „Ohne Warnzeichen“ blendet auffällige Werte aus.</>}
          numbers={[
            [`${TOP_POINTS.vorne} Punkte · ${TOP_PART_LABEL.vorne}`, 'Anteil der gültigen Standard-Ranglisten, in denen die Aktie unter den ersten zehn steht (Rückblick).'],
            [`${TOP_POINTS.steigt} Punkte · ${TOP_PART_LABEL.steigt}`, 'An wie vielen Handelstagen der letzten 30, 60 und 90 Tage der Kurs gestiegen ist (Rückblick).'],
            [`${TOP_POINTS.analysten} Punkte · ${TOP_PART_LABEL.analysten}`, 'Abstand des Kurses zum Ø Kursziel der Analysten – eine Prognose Dritter, nicht dieser App.'],
            [`${TOP_POINTS.volumen} Punkte · ${TOP_PART_LABEL.volumen}`, 'Umsatz der letzten Sitzung im Vergleich zu den 20 davor, nur bei steigendem Kurs (Rückblick).'],
            ['Abzug', `Bei kleinem Börsenwert: unter ${SMALL_CAP_EUR / 1e6} Mio. € −${SMALL_CAP_PENALTY}, unter ${MICRO_CAP_EUR / 1e6} Mio. € −${MICRO_CAP_PENALTY} Punkte.`],
          ]}
          how={<>Die vier Teile werden addiert, dann der Abzug abgezogen. Fehlende Angaben zählen 0 Punkte, nichts wird geschätzt. Alle Teilregeln stehen unten unter „So wird gerechnet“.</>}
          example={<>30 + 20 + 10 + 5 Punkte, Börsenwert 200 Mio. € (Abzug 10): 30 + 20 + 10 + 5 − 10 = 55 Punkte.</>}
        />
      </header>

      {top.error ? <ErrorNote error={top.error} /> : null}
      {top.loading ? <Loading height={320} label="Rangfolge wird berechnet" /> : null}

      {top.result ? (
        <>
          <section className="section" aria-labelledby="eigene">
            <h2 className="section-title" id="eigene">
              Deine Aktien
            </h2>
            <p className="section-note">Aktien aus deinen Musterdepots und der Watchlist mit ihrem Platz nach derselben Regel.</p>
            <OwnStocks result={top.result} detailed base20={top.base20} />
          </section>

          <section className="section" aria-labelledby="rangfolge">
            <h2 className="section-title" id="rangfolge">
              Rangfolge
            </h2>
            <Segmented
              label="Auswahl"
              options={[
                { value: 'alle', label: 'Alle' },
                { value: 'ohne', label: 'Ohne Warnzeichen' },
              ]}
              value={clean ? 'ohne' : 'alle'}
              onChange={(value) => {
                setShown(PAGE);
                updateParams(route, { ohne: value === 'ohne' ? '1' : null });
              }}
            />
            {illiquid ? (
              <label className="check">
                <input
                  type="checkbox"
                  checked={withIlliquid}
                  onChange={(e: Event) => {
                    setShown(PAGE);
                    updateParams(route, { alle: (e.target as HTMLInputElement).checked ? '1' : null });
                  }}
                />
                <span>Auch wenig gehandelte Aktien zeigen ({f.integer(illiquid)}, mit Punkten, ohne Platz)</span>
              </label>
            ) : null}
            <p className="section-note">
              {f.plural(entries.length, 'Aktie', 'Aktien')}
              {withIlliquid ? ' (handelbare mit Platz, wenig gehandelte ohne)' : ' mit Ø Tagesumsatz ab 10 Mio. USD'}
              {clean ? ' ohne Warnzeichen (Platz wie in der vollständigen Rangfolge)' : ''} · Nenner: {f.integer(top.result.valid)} gültige Standard-Ranglisten
              {top.signals ? ` · Signale vom ${f.berlinTime(top.signals.erstellt_utc)}` : ' · ohne Signal-Stand'}
              {top.result.withSignals && !top.result.withCap ? ' · Börsenwert ab dem nächsten Kennzahlen-Lauf' : ''}.
            </p>
            {missing.length ? <MissingMarkets names={missing} /> : null}
            {entries.length ? (
              <ol className="rows top-rows">
                {entries.slice(0, shown).map((entry) => (
                  <TopRow key={entry.isin} entry={entry} base20={top.base20} compact />
                ))}
              </ol>
            ) : (
              <p className="empty-body">{clean ? 'Keine Aktie ohne Warnzeichen. „Alle“ zeigt die vollständige Rangfolge.' : 'In diesem Datenstand steht keine Aktie in einer gültigen Standard-Rangliste unter den ersten 10.'}</p>
            )}
            {entries.length > shown ? (
              <div className="toolbar">
                <button type="button" className="btn" onClick={() => setShown(shown + PAGE)}>
                  Weitere {Math.min(PAGE, entries.length - shown)} anzeigen
                </button>
              </div>
            ) : null}
          </section>
        </>
      ) : null}

      <section className="section" aria-labelledby="regel">
        <h2 className="section-title" id="regel">
          So wird gerechnet
        </h2>
        <ul className="top-rule">
          {TOP_PARTS.map((p) => (
            <li key={p}>
              <b>
                {TOP_POINTS[p]} Punkte · {TOP_PART_LABEL[p]}
              </b>
              <span>
                {p === 'vorne'
                  ? 'Anteil der gültigen Standard-Ranglisten (40/60, 50/50, 60/40 · 1–30 Tage · Gruppe A und B), in denen die Aktie unter den ersten 10 steht. Gültig ist eine Rangliste ab 15 Schlusskursen im Zeitraum.'
                  : p === 'steigt'
                    ? 'Steig-Konstanz: an wie vielen Handelstagen der letzten 30, 60 und 90 Tage der Kurs gestiegen ist (40 % der Tage = 0, 65 % und mehr = voll; fallender Zeitraum höchstens ein Viertel).'
                    : p === 'analysten'
                      ? 'Abstand zum Ø Kursziel der Analysten (+25 % ≈ halbe, +100 % ≈ volle Punkte), voll erst ab 5 Analysten; Kursziel unter dem Kurs = 0.'
                      : `Volumen der letzten Sitzung im Vergleich zum Ø der 20 Sitzungen davor, nur wenn der Kurs in den letzten 5 Sitzungen gestiegen ist: gleich hoch = 0, ab ${VOLUME_FULL}-fach voll.`}
              </span>
            </li>
          ))}
          <li>
            <b>Abzug · Börsenwert</b>
            <span>
              unter {SMALL_CAP_EUR / 1e6} Mio. € −{SMALL_CAP_PENALTY}, unter {MICRO_CAP_EUR / 1e6} Mio. € −{MICRO_CAP_PENALTY}. Kleine Werte schwanken stärker und werden bei
              Kapitalerhöhungen leichter verwässert.
            </span>
          </li>
        </ul>
        <p className="section-note">
          Gewertet werden alle Aktien mit mindestens einer Top-10-Nennung; einen Platz und damit die Chance auf die Top 3 bekommen nur handelbare Aktien mit Ø Tagesumsatz ab 10 Mio.
          USD (Gruppe B) – bei wenig gehandelten Aktien lässt sich der Kurs leicht bewegen und ein Kauf zum angezeigten Kurs ist oft nicht möglich. Fehlende Angaben zählen 0 Punkte,
          nichts wird geschätzt. Bei gleichen Punkten entscheiden mehr Top-10-Nennungen, dann mehr erste Plätze, dann die Gesamtwertung. Eine Rechenregel aus vergangenen Kursen und
          Angaben Dritter – keine Anlageberatung, keine Kaufempfehlung.
        </p>
        {leader ? (
          <p className="section-note">
            Beispiel Platz 1: {TOP_PARTS.map((p) => `${TOP_PART_LABEL[p]} ${f.score(leader.parts[p])}`).join(' + ')}
            {leader.penalty ? ` − ${leader.penalty}` : ''} = {leader.points} Punkte.
          </p>
        ) : null}
      </section>
    </div>
  );
}
