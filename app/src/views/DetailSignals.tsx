/* Einzelansicht einer Aktie: Urteil der Signale, Prognose, Analysten und Kennzahlen (ab 1.6). */

import { CommunityBar, ConsistencyStrip, ExplainedTitle, ForecastChart, InfoTip, LightTag, RatingBar, ScoreBar, TargetRange, TotalBadge, TotalPartRow, VerdictCard } from '../components/signals';
import { ErrorNote, Loading, Notice } from '../components/ui';
import * as f from '../lib/format';
import { useHasSignals, useSignalDetail, useSignals } from '../lib/hooks';
import {
  detailConsistency,
  factRows,
  gradeOf,
  MONTH_LABEL,
  probabilityText,
  sectorName,
  signalCount,
  targetText,
  totalParts,
  totalProbabilityText,
  totalSentence,
  verdictSentence,
} from '../lib/signals';
import type { SeriesData, SignalDetail, SignalsData } from '../lib/types';
import { useApp } from '../state/AppState';
import { allPoints, RangeChart } from './RangeChart';

function names(data: SignalsData | null): Record<string, string> {
  return data?.regeln.namen ?? {};
}

function explain(data: SignalsData | null, key: string): string {
  return data?.regeln.erklaerungen[key] ?? '';
}

/** Lädt die Signal-Einzelansicht; zeigt Hinweise, solange es keinen Signal-Stand gibt. */
function useDetail(isin: string): { detail: SignalDetail | null; data: SignalsData | null; state: 'kein_stand' | 'laden' | 'fehler' | 'fehlt' | 'ok'; error: unknown } {
  const { status } = useApp();
  const signals = useSignals();
  const has = useHasSignals(status?.signale ? isin : null);
  const detail = useSignalDetail(status?.signale ? isin : null);
  if (!status?.signale) return { detail: null, data: null, state: 'kein_stand', error: null };
  if (signals.error) return { detail: null, data: null, state: 'fehler', error: signals.error };
  if (has === false) return { detail: null, data: signals.data, state: 'fehlt', error: null };
  if (detail.error) {
    const missing = detail.error instanceof Error && /404|NotFound/i.test(`${detail.error.name} ${detail.error.message}`);
    return { detail: null, data: signals.data, state: missing ? 'fehlt' : 'fehler', error: detail.error };
  }
  if (!detail.data) return { detail: null, data: signals.data, state: 'laden', error: null };
  return { detail: detail.data, data: signals.data, state: 'ok', error: null };
}

function NoSignals({ state, error }: { state: string; error: unknown }) {
  if (state === 'laden') return <Loading height={300} label="Signale werden geladen" />;
  if (state === 'fehler') return <ErrorNote error={error} />;
  if (state === 'fehlt')
    return (
      <Notice tone="info" title="Für diese Aktie gibt es keine Signale">
        <p>Signale gibt es nur für Aktien mit geprüfter Identität und mindestens 25 Tagesschlusskursen.</p>
      </Notice>
    );
  return (
    <Notice tone="info" title="Noch keine Signale berechnet">
      <p>Kennzahlen, Kursziele und Signale lädt der tägliche Lauf nach den Kursen. Sobald der erste Signal-Stand veröffentlicht ist, stehen sie hier.</p>
    </Notice>
  );
}

/** Überblick: zwei Urteile, erwartete Steigerung, Prognose-Grafik, Trefferquote, Signale im Einzelnen. */
export function SignalOverview({ isin, unit, series }: { isin: string; unit: string | null; series: SeriesData | null }) {
  const { detail, data, state, error } = useDetail(isin);
  const { manifest } = useApp();
  if (!detail) {
    return (
      <>
        <NoSignals state={state} error={error} />
        {series && manifest ? <RangeChart series={series} unit={unit} cutoff={manifest.cutoff_day} /> : null}
      </>
    );
  }
  const n = names(data);
  const shortCount = signalCount(detail.komponenten, 'kurz');
  const longCount = signalCount(detail.komponenten, 'lang');
  const prob = probabilityText(detail, data?.kalibrierung);
  const target = targetText(detail, unit);
  const history = allPoints(series, detail).pts.filter((p) => p.day >= (detail.kurs_tag ?? 0) - 366);
  const closes = history.map((p) => p.close);
  const days = history.map((p) => p.day);
  return (
    <>
      <TotalSection detail={detail} data={data} />

      <section className="section" aria-labelledby="urteil">
        <ExplainedTitle id="urteil" title="Urteil der Signale">
          Zwei Blickwinkel: <strong>kurzfristig</strong> (Tage bis wenige Wochen) aus Kursverlauf, Umsatz, Nachrichten und Community; <strong>langfristig</strong> (etwa 12 Monate)
          aus Kurszielen der Analysten, Bewertung, Wachstum und Trend. Jedes Signal hat 0 bis 100 Punkte, 50 ist neutral. {data?.regeln.hinweis}
        </ExplainedTitle>
        <div className="verdicts">
          <VerdictCard
            title="Kurzfristig"
            light={detail.kurz_ampel}
            points={detail.kurz}
            sentence={verdictSentence(detail, 'kurz', n)}
            hint={<>Regel: {data?.regeln.ampel_kurz ?? ''}</>}
          />
          <VerdictCard
            title="Langfristig"
            light={detail.lang_ampel}
            points={detail.lang}
            sentence={verdictSentence(detail, 'lang', n)}
            hint={<>Regel: {data?.regeln.ampel_lang ?? ''}</>}
          />
        </div>
        {detail.kurz_ampel !== 'gruen' && detail.lang_ampel === 'gruen' ? (
          <p className="callout callout-calm">Kurzfristig ist das Bild nicht eindeutig – langfristig sprechen die Signale aber dafür, vor allem das Kursziel der Analysten.</p>
        ) : null}
        {detail.kurz_ampel === 'gruen' && detail.lang_ampel === 'rot' ? (
          <p className="callout callout-warn">Kurzfristig stark, langfristig schwach: Der Anstieg stützt sich nicht auf Kursziele oder Bewertung – Vorsicht vor einem Rücksetzer.</p>
        ) : null}
      </section>

      <section className="section" aria-labelledby="prognose">
        <ExplainedTitle id="prognose" title="Prognose (12 Monate)">
          Links der tatsächliche Kursverlauf, rechts der Blick 12 Monate voraus. Der Punkt am rechten Rand ist das durchschnittliche Kursziel der Analysten, der senkrechte Strich die
          Spanne vom tiefsten zum höchsten Ziel. Das graue Band zeigt die übliche Schwankung dieser Aktie: Bei gleichbleibender Schwankung landet der Kurs in etwa 2 von 3 Fällen
          innerhalb – es sagt nichts über die Richtung. Kursziele sind Einschätzungen Dritter und oft zu optimistisch.
        </ExplainedTitle>
        {detail.potenzial !== null ? (
          <div className="fig">
            <span className={`pct pct-strong ${detail.potenzial >= 0 ? 'pct-plus' : 'pct-minus'}`}>{f.pct(detail.potenzial, 0)}</span>
            <span className="fig-label">erwartete Steigerung bis zum Ø Kursziel der Analysten (etwa 12 Monate)</span>
          </div>
        ) : (
          <p className="section-note">Für diese Aktie liegen keine Kursziele von Analysten vor.</p>
        )}
        {target ? <p className="section-note">{target}</p> : null}
        {detail.ziel !== null && detail.kurs ? <TargetRange close={detail.kurs} low={detail.ziel_tief} mean={detail.ziel} high={detail.ziel_hoch} unit={unit} /> : null}
        {detail.kurs && closes.length > 5 && manifest ? (
          <ForecastChart
            days={days}
            closes={closes}
            close={detail.kurs}
            today={detail.kurs_tag ?? manifest.cutoff_day}
            targetLow={detail.ziel_tief}
            targetMean={detail.ziel}
            targetHigh={detail.ziel_hoch}
            band={detail.prognose?.band_12m ?? null}
            unit={unit}
          />
        ) : null}
        {detail.kennzahlen?.wachstum && (detail.kennzahlen.wachstum.gewinn_naechstes_jahr != null || detail.kennzahlen.wachstum.umsatz_naechstes_jahr != null) ? (
          <p className="section-note">
            Prognose der Analysten für das nächste Geschäftsjahr:{' '}
            {[
              detail.kennzahlen.wachstum.gewinn_naechstes_jahr != null ? `Gewinn je Aktie ${f.pct(detail.kennzahlen.wachstum.gewinn_naechstes_jahr, 0)}` : null,
              detail.kennzahlen.wachstum.umsatz_naechstes_jahr != null ? `Umsatz ${f.pct(detail.kennzahlen.wachstum.umsatz_naechstes_jahr, 0)}` : null,
            ]
              .filter(Boolean)
              .join(', ')}
            .
          </p>
        ) : null}
        {prob ? (
          <p className="section-note prob-note">
            <strong>Trefferquote der Vergangenheit:</strong> {prob}
          </p>
        ) : null}
      </section>

      {manifest ? <RangeChart series={series} extra={detail} unit={unit} cutoff={manifest.cutoff_day} /> : null}

      <section className="section" aria-labelledby="signale">
        <ExplainedTitle id="signale" title="Signale im Einzelnen">
          Jedes Signal mit Punkten (0–100, Strich bei 50 = neutral) und dem Grund in Worten. Grün ab 60 Punkten, rot bis 40. Tippe auf „i“ neben einem Signal für die genaue Regel.
          Fehlen Daten, entfällt das Signal – es wird nichts geschätzt.
        </ExplainedTitle>
        <h3 className="sub-title">
          Kurzfristig <small>{shortCount.positive} von {shortCount.available} positiv</small>
        </h3>
        <ul className="signal-list">
          {detail.komponenten
            .filter((c) => c.horizont === 'kurz')
            .map((c) => (
              <li key={c.key} className={c.punkte === null ? 'is-empty' : ''}>
                <span className="signal-name">
                  {n[c.key] ?? c.key}
                  <InfoTip label={n[c.key] ?? c.key}>{explain(data, c.key)}</InfoTip>
                </span>
                <ScoreBar points={c.punkte} label={n[c.key] ?? c.key} />
                <span className="signal-text">{c.text}</span>
              </li>
            ))}
        </ul>
        <h3 className="sub-title">
          Langfristig <small>{longCount.positive} von {longCount.available} positiv</small>
        </h3>
        <ul className="signal-list">
          {detail.komponenten
            .filter((c) => c.horizont === 'lang')
            .map((c) => (
              <li key={c.key} className={c.punkte === null ? 'is-empty' : ''}>
                <span className="signal-name">
                  {n[c.key] ?? c.key}
                  <InfoTip label={n[c.key] ?? c.key}>{explain(data, c.key)}</InfoTip>
                </span>
                <ScoreBar points={c.punkte} label={n[c.key] ?? c.key} />
                <span className="signal-text">{c.text}</span>
              </li>
            ))}
        </ul>
        <p className="section-note">
          Signale vom {f.berlinTime(data?.erstellt_utc)}, Kurse bis {f.isoDate(detail.kursstand)}
          {detail.abgerufen.kennzahlen_abgerufen ? `, Kennzahlen abgerufen ${f.berlinTime(detail.abgerufen.kennzahlen_abgerufen)}` : ''}. Quellen: eigene Tageskurse; Yahoo Finance (Kursziele,
          Kennzahlen, Nachrichten); bei US-Aktien zusätzlich Trading Central, Nasdaq und Stocktwits.
        </p>
      </section>
    </>
  );
}

/** Gesamtwertung: Zahl mit Stufe, Satz, vier Teile mit Beitrag, Steig-Konstanz je Zeitraum, Trefferquote. */
function TotalSection({ detail, data }: { detail: SignalDetail; data: SignalsData | null }) {
  if (detail.gesamt === undefined) return null; // Signal-Stand vor 1.7
  const parts = totalParts(detail, data);
  const cells = detailConsistency(detail.konstanz);
  const sentence = totalSentence(detail);
  const prob = totalProbabilityText(detail, data?.kalibrierung_konstanz);
  const explain = data?.regeln.gesamt_erklaerungen;
  return (
    <section className="section" aria-labelledby="gesamt">
      <ExplainedTitle id="gesamt" title="Gesamtwertung">
        {data?.regeln.gesamt_regel ??
          'Gesamtwertung = 35 % Steig-Konstanz + 35 % Kursziel-Potenzial + 15 % Aufmerksamkeit & Schwung + 15 % Qualität. Ab 65 Punkten stark, ab 50 mittel.'}{' '}
        Sie ordnet alle Aktien der Trade-Republic-Liste, damit die aussichtsreichsten oben stehen – keine Kaufempfehlung.
      </ExplainedTitle>
      {detail.gesamt === null ? (
        <p className="section-note">Keine Gesamtwertung – dafür braucht es mindestens 60 Tage Kurshistorie.</p>
      ) : (
        <>
          <div className="total-head">
            <TotalBadge total={detail.gesamt} grade={detail.gesamt_stufe ?? gradeOf(detail.gesamt, data)} size="big" />
            {sentence ? <p className="total-sentence">{sentence}</p> : null}
          </div>
          <ul className="tp-list" aria-label="Teile der Gesamtwertung">
            {parts.map((part) => (
              <TotalPartRow key={part.key} name={part.name} weight={part.weight} points={part.points} contribution={part.contribution} explain={explain?.[part.key] ?? ''} />
            ))}
          </ul>
          <p className="section-note tp-note">Rechts: Beitrag zur Gesamtwertung (Punkte × Gewicht). Summe = {detail.gesamt.toFixed(1).replace('.', ',')} von 100.</p>
        </>
      )}
      {cells.length ? (
        <>
          <h3 className="sub-title">
            Steig-Konstanz <small>an wie vielen Handelstagen gestiegen</small>
          </h3>
          <ConsistencyStrip cells={cells} wide />
          <table className="kons-table">
            <thead>
              <tr>
                <th scope="col">Zeitraum</th>
                <th scope="col">gestiegen an</th>
                <th scope="col">Anteil</th>
                <th scope="col">Kurs</th>
              </tr>
            </thead>
            <tbody>
              {cells.map((c) => (
                <tr key={c.tage}>
                  <th scope="row">{c.tage} Tage</th>
                  <td>
                    {c.auf} von {c.von} Tagen
                  </td>
                  <td>{f.plainPct(c.anteil * 100, 0)}</td>
                  <td className={c.rendite !== null && c.rendite >= 0 ? 'pct-plus' : 'pct-minus'}>{f.pct(c.rendite, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
      {prob ? (
        <p className="section-note prob-note">
          <strong>Trefferquote der Vergangenheit:</strong> {prob}
        </p>
      ) : null}
    </section>
  );
}

/** Analysten, Nachrichten und Community. */
export function AnalystPanel({ isin, unit }: { isin: string; unit: string | null }) {
  const { detail, state, error } = useDetail(isin);
  if (!detail) return <NoSignals state={state} error={error} />;
  const k = detail.kennzahlen;
  const months = k?.empfehlungen ?? [];
  const current = months.find((m) => m.monat === '0m');
  const tc = detail.bewertung_tc;
  return (
    <>
      <section className="section" aria-labelledby="ziele">
        <ExplainedTitle id="ziele" title="Kursziele nach Quelle">
          Kursziele sind die Kurse, die Analysten in etwa 12 Monaten erwarten. Yahoo Finance liefert den Durchschnitt aller erfassten Analysten weltweit. Bei US-Aktien kommen der
          Konsens von Nasdaq und der Durchschnitt der Einzelziele der Häuser aus den letzten 90 Tagen hinzu. Das Ø Kursziel der App ist der Mittelwert dieser Quellen.
          Trade Republic nutzt einen eigenen Datenanbieter – dort können die Zahlen abweichen.
        </ExplainedTitle>
        {detail.ziel_quellen.length ? (
          <ul className="source-list">
            {detail.ziel_quellen.map((s) => (
              <li key={s.quelle}>
                <span className="source-name">{s.quelle}</span>
                <span className="source-main">
                  Ø <strong>{f.price(s.ziel, unit)}</strong>
                  {detail.kurs ? <span className={s.ziel >= detail.kurs ? 'pct-plus' : 'pct-minus'}> {f.pct(s.ziel / detail.kurs - 1, 0)}</span> : null}
                </span>
                <span className="source-meta">
                  {s.tief !== null && s.hoch !== null ? `Spanne ${f.price(s.tief, unit)} – ${f.price(s.hoch, unit)}` : 'ohne Spanne'}
                  {s.anzahl ? ` · ${f.plural(s.anzahl, 'Analyst', 'Analysten')}` : ''}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="section-note">Keine Kursziele erfasst – bei kleineren Werten oft, weil keine Bank sie beobachtet.</p>
        )}
      </section>

      {current ? (
        <section className="section" aria-labelledby="empfehlungen">
          <ExplainedTitle id="empfehlungen" title="Empfehlungen: Kaufen, Halten, Verkaufen">
            Wie viele Analysten die Aktie zum Kaufen, Halten oder Verkaufen einstufen – aktuell und in den drei Monaten davor. Grün = Kaufen (inkl. „stark kaufen“), grau = Halten, rot =
            Verkaufen. Zahlen rechts: Kaufen · Halten · Verkaufen.
          </ExplainedTitle>
          <p className="rating-legend" aria-hidden="true">
            <span className="rl rl-buy">Kaufen</span>
            <span className="rl rl-hold">Halten</span>
            <span className="rl rl-sell">Verkaufen</span>
            <span className="rl-nums">Anzahl: Kaufen · Halten · Verkaufen</span>
          </p>
          {months.map((row) => (
            <RatingBar key={row.monat} row={row} label={MONTH_LABEL[row.monat]} />
          ))}
        </section>
      ) : null}

      {k?.urteile?.length ? (
        <section className="section" aria-labelledby="urteile">
          <ExplainedTitle id="urteile" title="Neueste Urteile der Analystenhäuser">
            Einzelne Hoch- und Herabstufungen sowie Kursziel-Änderungen der letzten 180 Tage (frei verfügbar meist nur für US-Aktien).
          </ExplainedTitle>
          <ul className="action-list">
            {k.urteile.map((a, i) => (
              <li key={`${a.tag}-${a.haus}-${i}`}>
                <span className="action-day">{f.dayShort(a.tag)}</span>
                <span className="action-firm">{a.haus ?? '–'}</span>
                <span className="action-what">
                  {a.aktion ?? ''}
                  {a.zu ? ` – ${a.von && a.von !== a.zu ? `${a.von} → ` : ''}${a.zu}` : ''}
                  {a.ziel !== null ? (
                    <span className={a.ziel_aktion === 'gesenkt' ? 'action-down' : a.ziel_aktion === 'angehoben' ? 'action-up' : ''}>
                      {' '}
                      · Ziel {a.ziel_vorher !== null && a.ziel_vorher !== a.ziel ? `${f.price(a.ziel_vorher, unit)} → ` : ''}
                      {f.price(a.ziel, unit)}
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {tc ? (
        <section className="section" aria-labelledby="bewertung">
          <ExplainedTitle id="bewertung" title="Bewertung und Ausblick (Trading Central)">
            Trading Central schätzt einen fairen Wert der Aktie und vergleicht ihn mit dem Kurs: unterbewertet = Kurs unter dem fairen Wert. Der technische Ausblick beschreibt die Richtung des
            Kursverlaufs kurz-, mittel- und langfristig. Nur für US-Aktien verfügbar.
          </ExplainedTitle>
          <ul className="fact-list">
            {tc.bewertung ? (
              <li>
                <strong>{tc.bewertung === 'unterbewertet' ? 'Unterbewertet' : tc.bewertung === 'ueberbewertet' ? 'Überbewertet' : 'Fair bewertet'}</strong>
                {tc.abschlag !== null ? ` – ${tc.abschlag >= 0 ? `${f.plainPct(tc.abschlag * 100, 0)} unter` : `${f.plainPct(-tc.abschlag * 100, 0)} über`} dem fairen Wert` : ''}
              </li>
            ) : null}
            {Object.keys(tc.ausblick ?? {}).length ? (
              <li>
                Ausblick:{' '}
                {(['kurz', 'mittel', 'lang'] as const)
                  .filter((key) => tc.ausblick[key])
                  .map((key) => `${key === 'kurz' ? 'kurzfristig' : key === 'mittel' ? 'mittelfristig' : 'langfristig'} ${tc.ausblick[key]}`)
                  .join(', ')}
              </li>
            ) : null}
            {tc.research?.einstufung ? (
              <li>
                {tc.research.quelle ?? 'Research'}: {tc.research.einstufung}
                {tc.research.ziel ? `, Kursziel ${f.price(tc.research.ziel, unit)}` : ''}
              </li>
            ) : null}
          </ul>
        </section>
      ) : null}

      <section className="section" aria-labelledby="nachrichten">
        <ExplainedTitle id="nachrichten" title="Nachrichten">
          Aktuelle Schlagzeilen zur Aktie. Das Zeichen davor ist eine einfache automatische Einordnung nach Wortlisten (▲ eher positiv, ▼ eher negativ, ● neutral) – sie erkennt keinen
          Zusammenhang. Antippen öffnet die Meldung beim Herausgeber.
        </ExplainedTitle>
        {detail.nachrichten.length ? (
          <ul className="news-list">
            {detail.nachrichten.map((n) => (
              <li key={n.link + n.zeit}>
                <span className={`news-tone news-tone-${n.tendenz > 0 ? 'pos' : n.tendenz < 0 ? 'neg' : 'neu'}`} aria-label={n.tendenz > 0 ? 'eher positiv' : n.tendenz < 0 ? 'eher negativ' : 'neutral'}>
                  {n.tendenz > 0 ? '▲' : n.tendenz < 0 ? '▼' : '●'}
                </span>
                <a href={n.link} target="_blank" rel="noopener noreferrer">
                  {n.titel}
                </a>
                <span className="news-meta">
                  {n.quelle ?? ''} · {f.berlinTime(new Date(n.zeit * 1000).toISOString())}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="section-note">
            {detail.abgerufen.nachrichten_abgerufen
              ? 'Keine aktuellen Meldungen gefunden.'
              : 'Nachrichten werden nur für die vorderen Kandidaten geladen (täglich). Für diese Aktie liegen noch keine vor.'}
          </p>
        )}
      </section>

      <section className="section" aria-labelledby="community">
        <ExplainedTitle id="community" title="Stimmung der Community">
          Stocktwits ist eine Plattform, auf der Anleger kurze Beiträge zu Aktien schreiben und sie als „bullish“ (steigend) oder „bearish“ (fallend) markieren können. Gezählt werden die
          letzten 30 Beiträge. Viele Beiträge pro Tag zeigen „Hype“ – das kann Kurse treiben, endet aber oft in Rücksetzern. Nur für US-Kürzel verfügbar.
        </ExplainedTitle>
        {detail.community ? (
          <CommunityBar bull={detail.community.bullish} bear={detail.community.bearish} perDay={detail.community.je_tag} posts={detail.community.beitraege} />
        ) : (
          <p className="section-note">Keine Community-Daten (nur für US-Aktien unter den vorderen Kandidaten).</p>
        )}
      </section>
    </>
  );
}

/** Kennzahlen mit Erklärung je Zeile. */
export function FactsPanel({ isin, unit }: { isin: string; unit: string | null }) {
  const { detail, state, error } = useDetail(isin);
  if (!detail) return <NoSignals state={state} error={error} />;
  const groups = factRows(detail, unit);
  const k = detail.kennzahlen;
  return (
    <section className="section" aria-labelledby="fakten">
      <ExplainedTitle id="fakten" title="Kennzahlen">
        Die wichtigsten Zahlen zu Bewertung, erwartetem Wachstum, Finanzkraft und Risiko – jeweils mit kurzer Erklärung (auf „i“ tippen). Quelle: Yahoo Finance. Beträge in der
        Bilanzwährung {k?.waehrung_bilanz ?? '–'}.
      </ExplainedTitle>
      {k?.branche?.sektor ? (
        <p className="section-note">
          Branche: <strong>{sectorName(k.branche.sektor)}</strong>
          {k.branche.industrie ? ` (${k.branche.industrie})` : ''}
        </p>
      ) : null}
      {groups.length ? (
        groups.map((g) => (
          <div key={g.group} className="fact-group">
            <h3 className="sub-title">{g.group}</h3>
            <dl className="kv">
              {g.rows.map(([label, value, why]) => (
                <div className="kv-row" key={label}>
                  <dt>
                    {label}
                    <InfoTip label={label}>{why}</InfoTip>
                  </dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))
      ) : (
        <p className="section-note">Für diese Aktie liegen keine Kennzahlen vor.</p>
      )}
    </section>
  );
}

/** Kompakte Ampeln für den Kopf der Einzelansicht. */
export function HeaderLights({ isin }: { isin: string }) {
  const { detail } = useDetail(isin);
  if (!detail) return null;
  return (
    <p className="head-lights">
      {detail.gesamt !== undefined && detail.gesamt !== null ? (
        <span className="head-total">
          Gesamt <TotalBadge total={detail.gesamt} grade={detail.gesamt_stufe ?? gradeOf(detail.gesamt)} />
        </span>
      ) : null}
      <LightTag light={detail.kurz_ampel} label="Kurzfristig" />
      <LightTag light={detail.lang_ampel} label="Langfristig" />
      {detail.potenzial !== null ? (
        <span className="head-target">
          Kursziel <strong className={detail.potenzial >= 0 ? 'pct-plus' : 'pct-minus'}>{f.pct(detail.potenzial, 0)}</strong>
        </span>
      ) : null}
    </p>
  );
}
