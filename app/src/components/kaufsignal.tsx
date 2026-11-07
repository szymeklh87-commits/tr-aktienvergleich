/* Startseite ab 1.21.0: „Kaufsignal heute“ und die zehn aktuellen Kaufkandidaten nach der Signalregel – mit
 * Einstiegslimit, Stop-Loss, Kursziel, Chance-Risiko-Verhältnis, Begründung, Nachrichten und Datenstand. Kein Kauf, wenn
 * die Daten nicht aktuell und geprüft sind (Regeln in lib/tradeplan.ts). Simons Auftrag vom 07.11.2026: „Ich möchte die
 * App öffnen und sofort sehen, welche Aktie aktuell das stärkste geprüfte Kaufsignal hat, ob ein Einstieg noch sinnvoll
 * ist und warum. Falls keine ausreichenden Daten oder Signale vorliegen, zeige KEIN KAUF.“ */

import { useMemo } from 'react';
import * as f from '../lib/format';
import { useSeries, useSignalDetail, useSignals } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { berlinClock, isIntraday } from '../lib/intraday';
import { buildHash } from '../lib/router';
import { candidates, crvText, signalGate, STATUS_LABEL, strongest, type Candidate, type SignalGate } from '../lib/tradeplan';
import type { AiSummary, Instruments, Manifest, NewsItem, PlanCheck, PlanStatus, SignalDetail, SignalsData } from '../lib/types';
import { useApp } from '../state/AppState';
import { Disclosure, ErrorNote, IsinCopy, Loading } from './ui';

export interface BuyState {
  gate: SignalGate | null;
  list: Candidate[];
  best: Candidate | null;
  signals: SignalsData | null;
  loading: boolean;
  error: unknown;
}

/** Vorläufige Kurse eines Zwischenstands mit geprüfter Grundlage (Index → Kurs), sonst leer. */
export function liveMap(manifest: Manifest | null | undefined, instruments: Instruments | null | undefined): Map<number, number> {
  const out = new Map<number, number>();
  if (!manifest || !instruments || !isIntraday(manifest) || manifest.zwischenstand?.basis_geprueft === false) return out;
  for (let i = 0; i < instruments.count; i++) {
    const price = instruments.last_close[i];
    if (price !== null && instruments.last_close_day[i] === manifest.cutoff_day) out.set(i, price);
  }
  return out;
}

export function useBuyCandidates(limit = 10): BuyState {
  const { status, manifest, instruments, isinIndex, isDemo } = useApp();
  const signals = useSignals();
  return useMemo(() => {
    const data = signals.data ?? null;
    if (!data) return { gate: null, list: [], best: null, signals: null, loading: signals.loading, error: signals.error ?? null };
    const gate = signalGate({ status, manifest, signals: data, isDemo });
    const list = candidates(data, { gate, instruments, index: isinIndex, live: liveMap(manifest, instruments), limit });
    return { gate, list, best: strongest(list, gate), signals: data, loading: false, error: null };
  }, [signals.data, signals.loading, signals.error, status, manifest, instruments, isinIndex, isDemo, limit]);
}

const DOT: Record<PlanStatus, string> = { kaufsignal: 'go', beobachten: 'wait', kein_kauf: 'stop' };

/** Status als Ampelpunkt mit Wort. DEMO: nie in Ampelfarben, sondern als „DEMO-Beispiel“ in der Farbe der DEMO-Hinweise. */
export function StatusBadge({ status, demo = false }: { status: PlanStatus; demo?: boolean }) {
  if (demo && status !== 'kein_kauf') {
    return (
      <span className="plan-badge plan-demo">
        <span className="plan-dot" aria-hidden="true" />
        DEMO-Beispiel: {STATUS_LABEL[status]}
      </span>
    );
  }
  return (
    <span className={`plan-badge plan-${DOT[status]}`}>
      <span className="plan-dot" aria-hidden="true" />
      {STATUS_LABEL[status]}
    </span>
  );
}

function money(value: number | null, unit: string | null): string {
  if (value === null || !Number.isFinite(value)) return '–';
  const digits = Math.abs(value) < 1 ? 4 : 2;
  const text = value.toLocaleString('de-DE', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return unit ? `${text} ${unitLabel(unit)}` : text;
}

function unitLabel(unit: string): string {
  return ({ EUR: '€', USD: '$', GBp: 'Pence', GBP: '£', CHF: 'CHF' } as Record<string, string>)[unit] ?? unit;
}

function share(a: number | null, b: number | null): string {
  if (a === null || b === null || !b) return '';
  return f.pct(a / b - 1, 1);
}

/** Einstieg, Stop, Ziel und CRV als Raster – auf dem S25+ zwei mal zwei, breiter vier nebeneinander. */
export function PlanFigures({ c, unit, compact = false }: { c: Pick<Candidate, 'entry' | 'stop' | 'target' | 'crv' | 'targetBasis'>; unit: string | null; compact?: boolean }) {
  return (
    <dl className={`plan-figs${compact ? ' plan-figs-compact' : ''}`}>
      <div>
        <dt>{compact ? 'Einstieg' : 'Einstieg bis'}</dt>
        <dd>{money(c.entry, compact ? null : unit)}</dd>
      </div>
      <div>
        <dt>{compact ? 'Stop' : 'Stop-Loss'}</dt>
        <dd>
          {money(c.stop, compact ? null : unit)}
          {!compact && c.stop !== null && c.entry ? <small className="down"> {share(c.stop, c.entry)}</small> : null}
        </dd>
      </div>
      <div>
        <dt>{compact ? 'Ziel' : 'Kursziel'}</dt>
        <dd>
          {money(c.target, compact ? null : unit)}
          {!compact && c.target !== null && c.entry ? <small className="up"> {share(c.target, c.entry)}</small> : null}
        </dd>
      </div>
      <div>
        <dt>{compact ? 'CRV' : 'Chance : Risiko'}</dt>
        <dd>{crvText(c.crv)}</dd>
      </div>
    </dl>
  );
}

const CHECK_ORDER = ['trend', 'staerke', 'hoch', 'volumen', 'umsatz', 'ueberdehnung', 'rsi', 'kursluecke', 'zahlen', 'nachrichten', 'crv', 'daten', 'handelbar'];

function sortedChecks(checks: PlanCheck[]): PlanCheck[] {
  return [...checks].sort((a, b) => CHECK_ORDER.indexOf(a.key) - CHECK_ORDER.indexOf(b.key));
}

/** Alle Bedingungen der Signalregel mit dem Wert der Aktie: ✓ erfüllt, ✗ nicht erfüllt, ? nicht bewertbar. */
export function PlanChecks({ checks, limit }: { checks: PlanCheck[]; limit?: number }) {
  const list = sortedChecks(checks).slice(0, limit ?? checks.length);
  return (
    <ul className="plan-checks">
      {list.map((c) => (
        <li key={c.key} className={c.ok === true ? 'is-ok' : c.ok === false ? 'is-bad' : 'is-unknown'}>
          <span className="plan-check-mark" aria-label={c.ok === true ? 'erfüllt' : c.ok === false ? 'nicht erfüllt' : 'nicht bewertbar'}>
            {c.ok === true ? '✓' : c.ok === false ? '✗' : '?'}
          </span>
          <span className="plan-check-text">
            <b>{c.label}:</b> {c.wert}
            <small> Regel: {c.regel}</small>
          </span>
        </li>
      ))}
    </ul>
  );
}

function newsTime(item: NewsItem, now = Date.now()): string {
  const ms = item.zeit * 1000;
  const hours = (now - ms) / 3_600_000;
  if (hours < 1) return 'vor weniger als 1 Stunde';
  if (hours < 24) return `vor ${Math.round(hours)} Std.`;
  return f.berlinTime(new Date(ms).toISOString());
}

/** Die neuesten Schlagzeilen zur Aktie (Quelle, Zeit, Tendenz nach Wortliste). */
export function NewsList({ items, limit = 3 }: { items: NewsItem[]; limit?: number }) {
  const shown = [...items].sort((a, b) => b.zeit - a.zeit).slice(0, limit);
  if (!shown.length) return <p className="section-note">Keine aktuellen Schlagzeilen beim Kursanbieter.</p>;
  return (
    <ul className="plan-news">
      {shown.map((n) => (
        <li key={`${n.zeit}-${n.titel}`}>
          <a href={n.link} target="_blank" rel="noopener noreferrer">
            {n.titel}
          </a>
          <small>
            {n.quelle ? `${n.quelle} · ` : ''}
            {newsTime(n)}
            {n.tendenz === 1 ? ' · eher positiv' : n.tendenz === -1 ? ' · eher negativ' : ''}
          </small>
        </li>
      ))}
    </ul>
  );
}

/** Woher der Kurs stammt: Schlusskurs mit Datum, Börse, Quelle und Abrufzeit; im Zwischenstand der vorläufige Kurs. */
function PriceLine({ c, signals }: { c: Candidate; signals: SignalsData }) {
  const { instruments, manifest } = useApp();
  const series = useSeries(c.isin);
  if (!instruments) return null;
  const listing = series.data?.listing;
  const source = series.data?.source;
  const unit = instruments.price_unit[c.idx] ?? instruments.currency[c.idx] ?? null;
  const exchange = listing?.exchange ?? instruments.exchange[c.idx] ?? instruments.exchange_key[c.idx] ?? 'Börse unbekannt';
  const code = source?.provider ?? manifest?.provider?.prices ?? null;
  const provider = code === 'yahoo' ? 'Yahoo Finance (inoffiziell, nicht der Handelsplatz von Trade Republic)' : code === 'demo' ? 'DEMO (synthetische Kurse)' : code ?? 'Kursanbieter';
  const day = signals.kurs_tag[c.k];
  return (
    <p className="plan-price">
      Schlusskurs {money(signals.kurs[c.k], unit)} vom {day !== null ? f.day(day) : '–'} · {exchange}
      {listing?.mic ? ` (${listing.mic})` : ''} · Quelle: {provider}
      {source?.fetched_at ? `, abgerufen ${f.berlinTime(source.fetched_at)}` : ''}
      {c.livePrice !== null && manifest?.zwischenstand ? (
        <>
          {' '}
          · <b>Aktuell {money(c.livePrice, unit)}</b> (vorläufig, Kurse bis {berlinClock(manifest.zwischenstand.kurse_bis_utc)}, verzögert)
        </>
      ) : null}
    </p>
  );
}

/** Ist der Einstieg noch sinnvoll? Ein Satz aus Status, Limit und – im Zwischenstand – dem aktuellen Kurs. */
function timingText(c: Candidate, unit: string | null): string {
  if (c.shown === 'kaufsignal') {
    return c.livePrice !== null
      ? `Ja – der aktuelle Kurs ${money(c.livePrice, unit)} liegt unter dem Einstiegslimit ${money(c.entry, unit)}.`
      : `Ja, solange der Kurs das Einstiegslimit ${money(c.entry, unit)} nicht überschreitet; Kauf nur als Limit-Order, Stop gleich mit anlegen.`;
  }
  if (c.late) return `Nein – ${c.reason}`;
  return c.reason;
}

const NEWS_WORD: Record<string, string> = { positiv: 'eher positiv', gemischt: 'gemischt', negativ: 'eher negativ', keine: 'keine Meldungen' };

/** Die KI-Auswertung zum Kandidaten, wenn eingerichtet (ab 1.21.0, serverseitig mit Claude). Die KI entscheidet nichts:
 * Status, Einstieg, Stop und Ziel kommen allein aus der Signalregel. Ohne Auswertung: ein ehrlicher Hinweis. */
function AiReview({ detail, summary }: { detail: SignalDetail | null; summary: AiSummary | null | undefined }) {
  const ki = detail?.ki ?? null;
  if (!ki) {
    const why = !summary
      ? 'Für diesen Signal-Stand gibt es keine KI-Auswertung.'
      : summary.hinweis
        ? `Keine KI-Auswertung (${summary.hinweis}).`
        : !summary.eingerichtet
          ? 'Noch nicht eingerichtet – die KI-Auswertung startet, sobald der Zugang auf dem Server hinterlegt ist.'
          : 'Keine KI-Auswertung für diese Aktie (nur die vorderen Kandidaten werden ausgewertet).';
    return (
      <div className="plan-ai plan-ai-none">
        <h3 className="sub-title">KI-Auswertung</h3>
        <p className="section-note">{why}</p>
      </div>
    );
  }
  return (
    <div className="plan-ai">
      <h3 className="sub-title">KI-Auswertung</h3>
      <p>{ki.einordnung}</p>
      {ki.risiken.length ? (
        <ul>
          {ki.risiken.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      ) : null}
      <p className="plan-ai-facts">
        Einstieg laut KI: {ki.zu_spaet === true ? 'eher zu spät' : ki.zu_spaet === false ? 'noch nicht zu spät' : 'nicht beurteilt'}
        {ki.nachrichtenlage ? ` · Nachrichtenlage: ${NEWS_WORD[ki.nachrichtenlage] ?? ki.nachrichtenlage}` : ''}
      </p>
      <p className="plan-ai-foot">
        Automatisch erstellt von {ki.modell} am {f.berlinTime(ki.erstellt_utc)} aus Handelsplan, Kennzahlen und Schlagzeilen – kann irren, entscheidet nicht über das
        Signal, keine Anlageberatung.
      </p>
    </div>
  );
}

/** Ausklappbar je Zeile der Kandidatenliste: Nachrichten, KI-Auswertung und alle Bedingungen (lädt erst beim Öffnen). */
function RowDetails({ c, signals }: { c: Candidate; signals: SignalsData }) {
  const detail = useSignalDetail(c.isin);
  if (detail.error) return <ErrorNote error={detail.error} />;
  if (!detail.data) return <Loading height={60} label="Nachrichten und Auswertung werden geladen" />;
  const plan = detail.data.handel ?? null;
  return (
    <div className="buy-details">
      <PriceLine c={c} signals={signals} />
      <h3 className="sub-title">Aktuelle Nachrichten</h3>
      <NewsList items={detail.data.nachrichten ?? []} />
      <AiReview detail={detail.data} summary={signals.ki} />
      {plan ? (
        <>
          <h3 className="sub-title">Bedingungen der Signalregel</h3>
          <PlanChecks checks={plan.pruefungen} />
        </>
      ) : null}
    </div>
  );
}

/** Karte „Kaufsignal heute“ für einen Kandidaten. */
function SignalCard({ c, signals, demo }: { c: Candidate; signals: SignalsData; demo: boolean }) {
  const { instruments } = useApp();
  const detail = useSignalDetail(c.isin);
  if (!instruments) return null;
  const unit = instruments.price_unit[c.idx] ?? instruments.currency[c.idx] ?? null;
  const plan = detail.data?.handel ?? null;
  const reasons = plan ? plan.pruefungen.filter((p) => p.gruppe === 'ausgangslage') : [];
  return (
    <article className={`plan-card${demo ? ' plan-card-demo' : ''}`} aria-labelledby="signal-name">
      <div className="plan-head">
        <StatusBadge status={c.shown} demo={demo} />
        {c.total !== null ? <span className="plan-total">Gesamtwertung {Math.round(c.total)}</span> : null}
      </div>
      <a className="plan-name" id="signal-name" href={buildHash(`/aktie/${c.isin}`, { tab: 'ueberblick' })}>
        {instName(instruments, c.idx)}
      </a>
      <IsinCopy isin={c.isin} />
      <PriceLine c={c} signals={signals} />
      <PlanFigures c={c} unit={unit} />
      <p className="plan-timing">
        <b>Einstieg noch sinnvoll?</b> {timingText(c, unit)}
      </p>
      {reasons.length ? (
        <div className="plan-why">
          <h3 className="sub-title">Warum</h3>
          <PlanChecks checks={reasons} />
        </div>
      ) : null}
      {detail.error ? <ErrorNote error={detail.error} /> : null}
      {detail.data ? (
        <>
          <div className="plan-news-block">
            <h3 className="sub-title">Aktuelle Nachrichten</h3>
            <NewsList items={detail.data.nachrichten ?? []} />
          </div>
          <AiReview detail={detail.data} summary={signals.ki} />
          {plan ? (
            <Disclosure summary="Alle Bedingungen der Signalregel">
              <PlanChecks checks={plan.pruefungen} />
            </Disclosure>
          ) : null}
        </>
      ) : !detail.error ? (
        <Loading height={80} label="Begründung und Nachrichten werden geladen" />
      ) : null}
    </article>
  );
}

/** Startseite ganz oben: das stärkste geprüfte Kaufsignal – oder KEIN KAUF mit Grund. */
export function SignalHero({ state, rulesOnly = false }: { state: BuyState; rulesOnly?: boolean }) {
  const { isDemo, status } = useApp();
  const { gate, best, list, signals } = state;
  if (rulesOnly) {
    return (
      <section className="section" aria-labelledby="signalregel">
        <h2 className="section-title" id="signalregel">
          Die Signalregel
        </h2>
        <p className="section-note">{signals?.handel?.regeln.beschreibung ?? 'Die Signalregel kommt mit dem nächsten Signal-Stand.'}</p>
      </section>
    );
  }
  const watch = list.filter((c) => c.shown === 'beobachten').length;
  const example = isDemo ? list.find((c) => c.status === 'kaufsignal' && c.shown === 'kaufsignal') ?? null : null;
  return (
    <section className="section signal-hero" aria-labelledby="kaufsignal-heute">
      <h2 className="section-title" id="kaufsignal-heute">
        Kaufsignal heute
      </h2>
      {state.error ? <ErrorNote error={state.error} /> : null}
      {state.loading ? <Loading height={220} label="Signale werden geladen" /> : null}
      {!state.loading && !state.error && !status?.signale ? (
        <div className="no-buy">
          <p className="no-buy-word">KEIN KAUF</p>
          <p>Noch kein Signal-Stand – Signale kommen nach dem nächsten täglichen Lauf.</p>
        </div>
      ) : null}
      {signals && best ? <SignalCard c={best} signals={signals} demo={false} /> : null}
      {signals && !best && gate ? (
        <div className="no-buy" role="status">
          <p className="no-buy-word">KEIN KAUF</p>
          <p>{gate.open ? 'Heute erfüllt keine Aktie alle Bedingungen der Signalregel.' : gate.reason}</p>
          {gate.open && watch ? <p className="section-note">{f.plural(watch, 'Aktie', 'Aktien')} zum Beobachten unten – meist ist der Einstieg zu spät.</p> : null}
        </div>
      ) : null}
      {signals && example && !gate?.open ? (
        <Disclosure summary="So sähe ein Signal aus (DEMO-Beispiel)">
          <SignalCard c={{ ...example, shown: example.status }} signals={signals} demo />
        </Disclosure>
      ) : null}
      <Disclosure summary="Wie entsteht ein Kaufsignal?">
        <p className="section-note">{signals?.handel?.regeln.beschreibung ?? 'Die Signalregel kommt mit dem nächsten Signal-Stand.'}</p>
        <p className="section-note">
          Kaufsignale gibt es nur mit geprüften Schlusskursen des letzten Börsentags. Ist der tägliche Lauf gescheitert, veraltet, ein Zwischenstand ungeprüft oder sind es
          DEMO-Daten, zeigt die App „KEIN KAUF“. Signale nach fester Regel – keine Anlageberatung, Kurse können jederzeit fallen.
        </p>
      </Disclosure>
    </section>
  );
}

/** Die zehn aktuellen Kaufkandidaten: Status, Einstieg, Stop, Ziel, CRV und Grund in einer Zeile je Aktie. */
export function BuyCandidates({ state, title = 'Aktuelle Kaufkandidaten – Top 10', more = true }: { state: BuyState; title?: string; more?: boolean }) {
  const { instruments, isDemo } = useApp();
  const { list, signals, gate } = state;
  if (state.loading) return <Loading height={240} label="Kaufkandidaten werden geladen" />;
  if (!signals || !instruments) return null;
  const counts = signals.handel?.anzahl ?? null;
  const ai = signals.ki ?? null;
  const aiIsins = new Set(ai?.isin ?? []);
  return (
    <section className="section buy-list" aria-labelledby="kaufkandidaten">
      <h2 className="section-title" id="kaufkandidaten">
        {title}
      </h2>
      <p className="section-note">
        Nach der Signalregel{gate?.session ? `, Schlusskurse vom ${f.isoDate(gate.session)}` : ''}
        {counts ? ` · ${f.plural(counts.kaufsignal, 'Kaufsignal', 'Kaufsignale')}, ${counts.beobachten} zum Beobachten von ${f.integer(signals.isin.length)} Aktien` : ''}.
        {gate && !gate.open ? ' Wegen der Datenlage gilt heute kein Signal als Kaufsignal.' : ''}
      </p>
      <p className="section-note buy-ai-state">
        {!ai
          ? 'KI-Auswertung: für diesen Signal-Stand keine.'
          : ai.hinweis
            ? `KI-Auswertung: ${ai.hinweis}.`
            : !ai.eingerichtet
              ? 'KI-Auswertung: noch nicht eingerichtet (Zugang auf dem Server fehlt).'
              : `KI-Auswertung: ${ai.beantwortet} von ${ai.gefragt} Kandidaten (${ai.modell}).`}
      </p>
      {!list.length ? <p className="empty-body">Heute erfüllt keine Aktie die Ausgangslage der Signalregel.</p> : null}
      {list.length ? (
        <ol className="rows buy-rows">
          {list.map((c, n) => {
            const unit = instruments.price_unit[c.idx] ?? instruments.currency[c.idx] ?? null;
            return (
              <li key={c.isin} className={`row buy-row buy-${DOT[c.shown]}`}>
                <div className="row-rank">{n + 1}</div>
                <div className="row-main">
                  <div className="buy-head">
                    <a className="row-link row-name" href={buildHash(`/aktie/${c.isin}`, { tab: 'ueberblick' })}>
                      {c.idx >= 0 ? instName(instruments, c.idx) : c.isin}
                    </a>
                    <StatusBadge status={c.shown} demo={isDemo} />
                  </div>
                  <div className="row-meta">
                    <IsinCopy isin={c.isin} compact />
                    {unit ? <span className="buy-unit">in {unitLabel(unit)}</span> : null}
                  </div>
                  <PlanFigures c={c} unit={unit} compact />
                  {c.shown !== 'kaufsignal' ? <p className="buy-reason">{c.reason}</p> : null}
                  <Disclosure summary={aiIsins.has(c.isin) ? 'Nachrichten, KI-Auswertung, Bedingungen' : 'Nachrichten und Bedingungen'}>
                    <RowDetails c={c} signals={signals} />
                  </Disclosure>
                </div>
              </li>
            );
          })}
        </ol>
      ) : null}
      {more ? (
        <div className="toolbar">
          <a className="btn btn-primary" href="#/kandidaten">
            Alle Kandidaten
          </a>
          <a className="btn" href="#/potenzial">
            Weitere Listen
          </a>
        </div>
      ) : null}
      <p className="top-foot">Signale nach fester Regel aus Schlusskursen und Angaben Dritter – keine Anlageberatung. Kurse können jederzeit fallen.</p>
    </section>
  );
}
