/* „Top nach Zahlen“ (ab 1.11): vollständige Rangfolge nach der festen Regel, die Regel selbst und die eigenen Aktien. */

import { useMemo, useState } from 'react';
import { OwnStocks, TopRow, useMissingMarkets, useTopRanking } from '../components/top';
import { joinNames } from '../lib/markets';
import { ErrorNote, Loading, Segmented, ViewIntro } from '../components/ui';
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
  const [shown, setShown] = useState(PAGE);
  const entries = useMemo(() => (top.result ? top.result.entries.filter((e) => !clean || !e.warnings.length) : []), [top.result, clean]);
  if (!manifest) return null;
  const leader = top.result?.entries[0] ?? null;

  return (
    <div className="view">
      <header className="view-head">
        <h2 className="view-title">Top nach Zahlen</h2>
        <ViewIntro>
          <p className="view-intro">
            Alle Aktien mit mindestens einer Top-10-Nennung in den Standard-Ranglisten, geordnet nach einer festen Regel: bis 40 Punkte „oft vorne“, 25 „steigt stetig“, 20 Analysten,
            15 Volumen, Abzug bei kleinem Börsenwert – ohne Meinung, jeden Tag gleich gerechnet. Die Regel steht unten; Antippen öffnet die Aktie mit allen Zahlen.
          </p>
        </ViewIntro>
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
            <OwnStocks result={top.result} />
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
            <p className="section-note">
              {f.plural(entries.length, 'Aktie', 'Aktien')}
              {clean ? ' ohne Warnzeichen (Platz wie in der vollständigen Rangfolge)' : ''} · Nenner: {f.integer(top.result.valid)} gültige Standard-Ranglisten
              {top.signals ? ` · Signale vom ${f.berlinTime(top.signals.erstellt_utc)}` : ' · ohne Signal-Stand'}
              {top.result.withSignals && !top.result.withCap ? ' · Börsenwert ab dem nächsten Kennzahlen-Lauf' : ''}.
            </p>
            {missing.length ? (
              <p className="section-note top-missing">
                Im Zwischenstand noch ohne Kurs von heute und deshalb nicht in der Wertung: Aktien aus {joinNames(missing.slice(0, 4))}
                {missing.length > 4 ? ` und ${missing.length - 4} weiteren Börsen` : ''}.
              </p>
            ) : null}
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
          Gewertet werden nur Aktien mit mindestens einer Top-10-Nennung. Fehlende Angaben zählen 0 Punkte, nichts wird geschätzt. Bei gleichen Punkten entscheiden mehr Top-10-Nennungen,
          dann mehr erste Plätze, dann die Gesamtwertung. Eine Rechenregel aus vergangenen Kursen und Angaben Dritter – keine Anlageberatung, keine Kaufempfehlung.
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
