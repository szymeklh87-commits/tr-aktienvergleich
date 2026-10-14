/* „Top 3 nach Zahlen“ (ab 1.11): Karte oben auf der Startseite, Zeilen der vollständigen Rangfolge und der
 * Abgleich „Deine Aktien“ (Depots und Watchlist) – Rechenregel in lib/top.ts. */

import { useMemo } from 'react';
import { DEPOT_SIZE, selectionFor, STANDARD_CHOICE, topLists } from '../lib/depots';
import * as f from '../lib/format';
import { useFrequency, useSignals } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { berlinClock, isIntraday } from '../lib/intraday';
import { joinNames, marketName } from '../lib/markets';
import { buildHash } from '../lib/router';
import { capText, hitText, placeOf, rankTop, TOP_PART_LABEL, TOP_PARTS, TOP_POINTS, topReason, type TopEntry, type TopResult } from '../lib/top';
import type { SignalsData } from '../lib/types';
import { useApp } from '../state/AppState';
import { InstrumentRow } from './rows';
import { InfoTip } from './signals';
import { ErrorNote, Loading } from './ui';

export interface TopState {
  result: TopResult | null;
  signals: SignalsData | null;
  /** Anteil aller Aktien, die 20 Handelstage später höher standen (Vergleichswert der Trefferquote) */
  base20: number | null;
  error: unknown;
  loading: boolean;
}

/** Rangfolge nach der Regel für den aktiven Stand. Wartet auf den Signal-Stand, solange er lädt (keine springenden Plätze). */
export function useTopRanking(): TopState {
  const { instruments } = useApp();
  const frequency = useFrequency();
  const signals = useSignals();
  const waiting = signals.loading && !signals.data;
  const result = useMemo(() => {
    if (!frequency.data || !instruments || waiting) return null;
    const selection = selectionFor(STANDARD_CHOICE);
    let lists;
    try {
      lists = topLists(frequency.data, instruments, selection, 'ab', DEPOT_SIZE);
    } catch {
      lists = topLists(frequency.data, instruments, selection, 'a', DEPOT_SIZE); // Stand ohne Gruppe B
    }
    return rankTop(lists.rows, lists.valid, signals.data);
  }, [frequency.data, instruments, signals.data, waiting]);
  return {
    result,
    signals: signals.data,
    base20: signals.data?.kalibrierung_konstanz?.alle_steigt_20 ?? null,
    error: frequency.error ?? null,
    loading: !result && !frequency.error,
  };
}

/** Die vier Teile der Punkte als kleine Balken (Punkte von höchstens …) und der Abzug für kleinen Börsenwert. */
export function TopParts({ entry }: { entry: TopEntry }) {
  const label = `${TOP_PARTS.map((p) => `${TOP_PART_LABEL[p]} ${f.score(entry.parts[p])} von ${TOP_POINTS[p]}`).join(', ')}${entry.penalty ? `, Abzug ${entry.penalty} für kleinen Börsenwert` : ''}`;
  return (
    <div className="tparts" role="img" aria-label={`Punkte: ${label}`}>
      {TOP_PARTS.map((p) => (
        <span key={p} className="tpart" aria-hidden="true">
          <small>{TOP_PART_LABEL[p]}</small>
          <span className="tpart-bar">
            <span style={{ width: `${Math.round((entry.parts[p] / TOP_POINTS[p]) * 100)}%` }} />
          </span>
          <b>
            {Math.round(entry.parts[p])}/{TOP_POINTS[p]}
          </b>
        </span>
      ))}
      {entry.penalty ? (
        <span className="tpart tpart-minus" aria-hidden="true">
          <small>Börsenwert</small>
          <b>−{entry.penalty}</b>
        </span>
      ) : null}
    </div>
  );
}

/** Zeile der Rangfolge: Punkte, Börsenwert, Teile, Begründung, Warnzeichen, Trefferquote. */
export function TopRow({ entry, base20, compact = false }: { entry: TopEntry; base20: number | null; compact?: boolean }) {
  const { instruments } = useApp();
  if (!instruments) return null;
  const hit = hitText(entry, base20);
  return (
    <InstrumentRow
      idx={entry.idx}
      rank={entry.place}
      href={buildHash(`/aktie/${entry.isin}`, { tab: 'ueberblick' })}
      className="top-row"
      figs={
        <>
          <span className="top-points">{entry.points}</span>
          <span className="row-fig-sub">von 100 Punkten</span>
          {entry.capEur !== null ? <span className="row-fig-sub">Börsenwert {capText(entry.capEur)}</span> : null}
        </>
      }
    >
      <TopParts entry={entry} />
      <p className="top-why">{topReason(entry)}</p>
      {entry.warnings.length ? (
        <ul className="top-warn" aria-label="Warnzeichen">
          {entry.warnings.map((w) => (
            <li key={w.key}>{w.text}</li>
          ))}
        </ul>
      ) : null}
      {hit && !compact ? <p className="top-hit">{hit}</p> : null}
    </InstrumentRow>
  );
}

/** Eigene Aktien (Musterdepots und Watchlist) in der Reihenfolge der Regel: Platz, Punkte, wie viele vorne liegen. */
export function OwnStocks({ result, limit }: { result: TopResult; limit?: number }) {
  const { instruments, isinIndex, prefs, watchlist, manifest } = useApp();
  if (!instruments) return null;
  // Im Zwischenstand fehlen Aktien ohne Kurs von heute (z. B. USA vor Börsenbeginn) in den Ranglisten
  const noPriceToday = (idx: number) =>
    Boolean(manifest && isIntraday(manifest) && (instruments.last_close_day[idx] === null || instruments.last_close_day[idx]! < manifest.cutoff_day));
  const isins = [...new Set([...(prefs.depots ?? []).flatMap((d) => d.isins), ...watchlist])].filter((isin) => isinIndex.has(isin));
  if (!isins.length) {
    return <p className="section-note">Noch keine eigenen Aktien: Aktien in der Watchlist oder in einem Musterdepot erscheinen hier mit ihrem Platz.</p>;
  }
  const rows = isins
    .map((isin) => ({ isin, idx: isinIndex.get(isin)!, entry: placeOf(result, isin) }))
    .sort((a, b) => (a.entry?.place ?? Infinity) - (b.entry?.place ?? Infinity));
  const shown = limit ? rows.slice(0, limit) : rows;
  return (
    <>
      <ul className="top-own">
        {shown.map(({ isin, idx, entry }) => (
          <li key={isin}>
            <a href={buildHash(`/aktie/${isin}`, { tab: 'ueberblick' })}>
              <span className="top-own-name">{instName(instruments, idx)}</span>
              {entry ? (
                <span className="top-own-fig">
                  <b>Platz {f.integer(entry.place)}</b> · {entry.points} Punkte
                  <small>{entry.place === 1 ? 'vorne' : `${f.plural(entry.place - 1, 'Aktie liegt', 'Aktien liegen')} vorne`}</small>
                </span>
              ) : (
                <span className="top-own-fig">
                  <small>{noPriceToday(idx) ? 'noch ohne Kurs von heute – zählt erst ab Börsenbeginn' : 'keine Top-10-Nennung in der Standardauswahl'}</small>
                </span>
              )}
            </a>
          </li>
        ))}
      </ul>
      {limit && rows.length > limit ? <p className="section-note">Weitere {rows.length - limit} eigene Aktien in der vollständigen Rangfolge.</p> : null}
    </>
  );
}

/** Stand der Daten in einem Satz (offiziell oder Zwischenstand). */
function useStandText(): string {
  const { manifest } = useApp();
  if (!manifest) return '';
  return isIntraday(manifest)
    ? `Zwischenstand ${f.dayShort(manifest.cutoff_day)}, Kurse bis ${berlinClock(manifest.zwischenstand?.kurse_bis_utc)} (vorläufig)`
    : `Kursstand ${f.day(manifest.cutoff_day)}`;
}

/** Börsen ohne Kurs von heute im Zwischenstand (Namen), sonst leer. */
export function useMissingMarkets(): string[] {
  const { manifest } = useApp();
  if (!manifest || !isIntraday(manifest) || !manifest.zwischenstand) return [];
  return [...new Set(manifest.zwischenstand.boersen_ohne_kurs.map(marketName))].sort((a, b) => a.localeCompare(b, 'de'));
}

/** Erklärung der Regel (Startseite: zum Antippen, Seite „Top nach Zahlen“: ausführlich). */
export function TopRuleText() {
  return (
    <>
      Punkte von 0 bis 100 für jede Aktie mit mindestens einer Top-10-Nennung: <strong>40</strong> für „oft vorne“ (Anteil der gültigen Standard-Ranglisten 40/60, 50/50, 60/40 über
      1–30 Tage in Gruppe A und B, in denen die Aktie unter den ersten 10 steht), <strong>25</strong> für „steigt stetig“ (Steig-Konstanz über 30, 60 und 90 Tage), <strong>20</strong> für
      die Analysten (Abstand zum Ø Kursziel, voll erst ab 5 Analysten) und <strong>15</strong> für das Volumen (letzte Sitzung im Vergleich zum Ø der 20 davor, nur bei steigendem Kurs;
      ab doppelt so hoch voll). Abzug für kleinen Börsenwert: unter 300 Mio. € −10, unter 50 Mio. € −20. Fehlende Angaben zählen 0 Punkte. Eine Rechenregel aus vergangenen Kursen und
      Angaben Dritter – keine Anlageberatung, keine Kaufempfehlung.
    </>
  );
}

/** Startseite ganz oben: die drei Aktien mit den meisten Punkten und die eigenen Aktien. */
export function TopThree() {
  const top = useTopRanking();
  const stand = useStandText();
  const missing = useMissingMarkets();
  const entries = top.result?.entries.slice(0, 3) ?? [];
  return (
    <section className="section top3" aria-labelledby="top3">
      <h2 className="section-title explained" id="top3">
        <span>Top 3 nach Zahlen</span>
        <InfoTip label="Top 3 nach Zahlen">
          <TopRuleText />
        </InfoTip>
      </h2>
      <p className="section-note">
        Feste Rechenregel über alle Aktien: Ranglisten, Kursverlauf, Analysten, Volumen und Börsenwert. {stand}.
      </p>
      {top.error ? <ErrorNote error={top.error} /> : null}
      {top.loading ? <Loading height={300} label="Top 3 werden berechnet" /> : null}
      {top.result && !entries.length ? <p className="empty-body">In diesem Datenstand steht keine Aktie in einer gültigen Standard-Rangliste unter den ersten 10.</p> : null}
      {missing.length ? (
        <p className="section-note top-missing">
          Im Zwischenstand noch ohne Kurs von heute und deshalb nicht in der Wertung: Aktien aus {joinNames(missing.slice(0, 4))}
          {missing.length > 4 ? ` und ${missing.length - 4} weiteren Börsen` : ''}. Sie zählen ab Börsenbeginn; der offizielle Stand zeigt sie mit Schlusskursen.
        </p>
      ) : null}
      {top.result && !top.result.withSignals ? (
        <p className="section-note">Ohne Signal-Stand zählen nur die Ranglisten (bis zu 40 Punkte); Steigen, Analysten und Volumen kommen mit dem nächsten Kennzahlen-Lauf.</p>
      ) : null}
      {entries.length ? (
        <ol className="rows top-rows" aria-label="Top 3 nach Zahlen">
          {entries.map((entry) => (
            <TopRow key={entry.isin} entry={entry} base20={top.base20} />
          ))}
        </ol>
      ) : null}
      {top.result ? (
        <div className="top-own-block">
          <h3 className="sub-title">Deine Aktien nach derselben Regel</h3>
          <OwnStocks result={top.result} limit={6} />
        </div>
      ) : null}
      <div className="toolbar">
        <a className="btn btn-primary" href="#/top">
          Alle Plätze und Regel
        </a>
      </div>
      <p className="top-foot">Rechnung aus vergangenen Kursen und Angaben Dritter – keine Anlageberatung. Kurse können jederzeit fallen.</p>
    </section>
  );
}
