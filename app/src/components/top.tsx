/* „Top 3 nach Zahlen“ (ab 1.11): Karte oben auf der Startseite, Zeilen der vollständigen Rangfolge und der
 * Abgleich „Deine Aktien“ (Depots und Watchlist) – Rechenregel in lib/top.ts. */

import { useMemo } from 'react';
import { DEPOT_SIZE, selectionFor, STANDARD_CHOICE, topLists } from '../lib/depots';
import * as f from '../lib/format';
import { useFrequency, useSignals } from '../lib/hooks';
import { berlinClock, closeDaysText, countsWithClose, isIntraday } from '../lib/intraday';
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
    // Ab 1.14: Plätze nur für handelbare Aktien (Gruppe B, Ø Tagesumsatz ab 10 Mio. USD)
    return rankTop(lists.rows, lists.valid, signals.data, instruments.turnover?.liquid ?? null);
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

/** Rechte Spalte einer Zeile: Punkte, „von 100 Punkten“, Börsenwert – gleich in der Rangfolge und bei „Deine Aktien“. */
function TopFigs({ entry }: { entry: TopEntry }) {
  return (
    <>
      <span className="top-points">{entry.points}</span>
      <span className="row-fig-sub">von 100 Punkten</span>
      {entry.capEur !== null ? <span className="row-fig-sub">Börsenwert {capText(entry.capEur)}</span> : null}
    </>
  );
}

/** Zeile der Rangfolge: Punkte, Börsenwert, Teile, Begründung, Warnzeichen, Trefferquote. ``lead`` (eigene Aktien):
 * eine Zeile davor, z. B. „Platz 2 · 1 Aktie liegt vorne“. */
export function TopRow({ entry, base20, compact = false, lead = null }: { entry: TopEntry; base20: number | null; compact?: boolean; lead?: string | null }) {
  const { instruments } = useApp();
  if (!instruments) return null;
  const hit = hitText(entry, base20);
  return (
    <InstrumentRow
      idx={entry.idx}
      rank={entry.place || '–'}
      href={buildHash(`/aktie/${entry.isin}`, { tab: 'ueberblick' })}
      className={entry.place ? 'top-row' : 'top-row top-row-none'}
      figs={<TopFigs entry={entry} />}
    >
      {lead ? <p className="top-place">{lead}</p> : null}
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

/** „Platz 4 · 3 Aktien liegen vorne“ */
function aheadText(place: number): string {
  return place === 1 ? 'Platz 1 · keine Aktie liegt vorne' : `Platz ${f.integer(place)} · ${f.plural(place - 1, 'Aktie liegt', 'Aktien liegen')} vorne`;
}

/** Ab 1.14: Punkte ohne Platz – Ø Tagesumsatz unter 10 Mio. USD */
export const ILLIQUID_TEXT = 'Wenig gehandelt (Ø Tagesumsatz unter 10 Mio. USD) – Punkte ohne Platz';

/** Eigene Aktien (Musterdepots und Watchlist) in der Reihenfolge der Regel. Ab 1.12.1 dieselben Zeilen wie in der
 * Rangfolge (Platz, Name, ISIN, Punkte); Aktien ohne Platz mit „–“ und dem Grund in einer Zeile darunter – vorher
 * stand der Grund rechts neben dem Namen und drückte ihn auf dem Handy auf wenige Buchstaben je Zeile zusammen.
 * ``detailed`` (Seite „Top nach Zahlen“): mit Teilen, Begründung und Warnzeichen wie die Rangfolge. */
export function OwnStocks({ result, limit, detailed = false, base20 = null }: { result: TopResult; limit?: number; detailed?: boolean; base20?: number | null }) {
  const { instruments, isinIndex, prefs, watchlist, manifest } = useApp();
  if (!instruments) return null;
  const info = manifest && isIntraday(manifest) ? manifest.zwischenstand : null;
  // Zwischenstand: Aktien ohne Kurs von heute (z. B. USA vor Börsenbeginn) zählen ab 1.13 mit dem letzten Schlusskurs;
  // in Zwischenständen bis 1.12 fehlen sie in den Ranglisten
  const noPriceToday = (idx: number) => Boolean(manifest && info && (instruments.last_close_day[idx] === null || instruments.last_close_day[idx]! < manifest.cutoff_day));
  const withClose = countsWithClose(info);
  // Börsenbeginn heute (Berliner Zeit), wenn die Börse beim Abruf noch geschlossen war
  const opensAt = (idx: number): string | null => {
    const code = instruments.calendar?.[idx] ?? instruments.mic[idx];
    const at = info && code ? info.oeffnung_utc?.[code] : null;
    return at && info && Date.parse(at) > Date.parse(info.abgerufen_utc) ? berlinClock(at) : null;
  };
  const isins = [...new Set([...(prefs.depots ?? []).flatMap((d) => d.isins), ...watchlist])].filter((isin) => isinIndex.has(isin));
  if (!isins.length) {
    return <p className="section-note">Noch keine eigenen Aktien: Aktien in der Watchlist oder in einem Musterdepot erscheinen hier mit ihrem Platz.</p>;
  }
  // Reihenfolge: handelbare nach Platz, dann wenig gehandelte nach der Regel, dann Aktien ohne Punkte
  const order = (entry: ReturnType<typeof placeOf>) => (!entry ? Infinity : entry.place > 0 ? entry.place : 1e6 + entry.overall);
  const rows = isins.map((isin) => ({ isin, idx: isinIndex.get(isin)!, entry: placeOf(result, isin) })).sort((a, b) => order(a.entry) - order(b.entry));
  const shown = limit ? rows.slice(0, limit) : rows;
  return (
    <>
      <ol className="rows top-own" aria-label="Deine Aktien nach derselben Regel">
        {shown.map(({ isin, idx, entry }) => {
          const href = buildHash(`/aktie/${isin}`, { tab: 'ueberblick' });
          if (entry) {
            const opens = noPriceToday(idx) ? opensAt(idx) : null;
            const lead = `${entry.place ? aheadText(entry.place) : ILLIQUID_TEXT}${opens ? ` · Kurs von heute ab Börsenbeginn um ${opens}` : ''}`;
            if (detailed) return <TopRow key={isin} entry={entry} base20={base20} compact lead={lead} />;
            return (
              <InstrumentRow key={isin} idx={idx} rank={entry.place || '–'} href={href} className={entry.place ? 'top-row' : 'top-row top-row-none'} figs={<TopFigs entry={entry} />}>
                <p className="top-place">{lead}</p>
              </InstrumentRow>
            );
          }
          const opens = noPriceToday(idx) ? opensAt(idx) : null;
          return (
            <InstrumentRow
              key={isin}
              idx={idx}
              rank="–"
              href={href}
              className="top-row top-row-none"
              figs={
                <>
                  <span className="top-points top-points-none">–</span>
                  <span className="row-fig-sub">ohne Punkte</span>
                </>
              }
            >
              <p className="top-why">
                {noPriceToday(idx) && !withClose
                  ? `Noch ohne Kurs von heute – zählt ab Börsenbeginn${opens ? ` um ${opens}` : ''}.`
                  : 'Keine Top-10-Nennung in den Standard-Ranglisten – deshalb ohne Punkte.'}
              </p>
            </InstrumentRow>
          );
        })}
      </ol>
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

/** Hinweis im Zwischenstand: Börsen ohne Kurs von heute fehlen in der Wertung – mit Wechsel zum Stand mit den
 * Schlusskursen (ab 1.12.1 heißt der Knopf nach dem, was er zeigt: „Top 3 mit Schlusskursen 13.10.“ statt „… im
 * offiziellen Stand“). */
export function MissingMarkets({ names }: { names: string[] }) {
  const { manifest, status, switchSnapshot } = useApp();
  const officialId = manifest?.zwischenstand?.offizieller_stand ?? status?.latest_official_snapshot_id ?? null;
  const officialDay = manifest?.zwischenstand?.offizieller_stichtag ?? null;
  const info = manifest?.zwischenstand ?? null;
  if (info && countsWithClose(info)) {
    // Ab 1.13 (Simons Wahl 15:20 Uhr): alle Aktien in der Wertung – ohne Kurs von heute mit dem letzten Schlusskurs
    const fetched = Date.parse(info.abgerufen_utc);
    const opens = [...new Set(Object.keys(info.boersen_mit_schlusskurs ?? {}).map((code) => info.oeffnung_utc?.[code] ?? null))].filter(
      (at): at is string => Boolean(at) && Date.parse(at!) > fetched,
    );
    const opensText = opens.length === 1 ? ` (Börsenbeginn ${berlinClock(opens[0])})` : '';
    return (
      <div className="top-missing">
        <p>
          Noch ohne Kurs von heute: Aktien aus {joinNames(names.slice(0, 4))}
          {names.length > 4 ? ` und ${names.length - 4} weiteren Börsen` : ''}
          {opensText}. Sie zählen mit dem Schlusskurs {closeDaysText(info)}; ein Zwischenstand nach Börsenbeginn rechnet sie mit dem Kurs von heute.
        </p>
      </div>
    );
  }
  return (
    <div className="top-missing">
      <p>
        Im Zwischenstand noch ohne Kurs von heute und deshalb nicht in der Wertung: Aktien aus {joinNames(names.slice(0, 4))}
        {names.length > 4 ? ` und ${names.length - 4} weiteren Börsen` : ''}. Sie zählen ab Börsenbeginn. Mit den Schlusskursen
        {officialDay ? ` vom ${f.isoDate(officialDay)}` : ''} sind alle Aktien dabei.
      </p>
      {officialId ? (
        <button type="button" className="btn" onClick={() => switchSnapshot(officialId)}>
          Top 3 mit Schlusskursen{officialDay ? ` ${f.isoDate(officialDay).slice(0, 6)}` : ''}
        </button>
      ) : null}
    </div>
  );
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
      ab doppelt so hoch voll). Abzug für kleinen Börsenwert: unter 300 Mio. € −10, unter 50 Mio. € −20. Fehlende Angaben zählen 0 Punkte. Einen Platz – und damit die Top 3 – bekommen
      nur handelbare Aktien mit Ø Tagesumsatz ab 10 Mio. USD (Gruppe B). Eine Rechenregel aus vergangenen Kursen und Angaben Dritter – keine Anlageberatung, keine Kaufempfehlung.
    </>
  );
}

/** Startseite ganz oben: die drei Aktien mit den meisten Punkten und die eigenen Aktien. */
export function TopThree() {
  const top = useTopRanking();
  const stand = useStandText();
  const missing = useMissingMarkets();
  const entries = top.result?.ranked.slice(0, 3) ?? [];
  return (
    <section className="section top3" aria-labelledby="top3">
      <h2 className="section-title explained" id="top3">
        <span>Top 3 nach Zahlen</span>
        <InfoTip label="Top 3 nach Zahlen">
          <TopRuleText />
        </InfoTip>
      </h2>
      <p className="section-note">
        Die drei gut gehandelten Aktien mit den meisten Punkten nach einer festen Regel: oft vorn in den Ranglisten, regelmäßig gestiegen, Kursziel der Analysten,
        steigendes Volumen. Höchstens 100 Punkte. {stand}.
      </p>
      {top.error ? <ErrorNote error={top.error} /> : null}
      {top.loading ? <Loading height={300} label="Top 3 werden berechnet" /> : null}
      {top.result && !entries.length ? <p className="empty-body">In diesem Datenstand steht keine handelbare Aktie (Ø Tagesumsatz ab 10 Mio. USD) in einer gültigen Standard-Rangliste unter den ersten 10.</p> : null}
      {missing.length ? <MissingMarkets names={missing} /> : null}
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
