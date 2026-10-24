/* Zwei Rendite-Ranglisten (Erweiterung 1.1):
 *   1. Höchste Kursrendite – alle Aktien mit veröffentlichter Kursrendite
 *   2. Höchste Kursrendite – Ø Tagesumsatz mindestens 10 Mio. USD
 * Beide nur nach Kursrendite sortiert (0 % Gleichmäßigkeit / 100 % Kursrendite), gleicher
 * Kursstichtag, gleiche Renditeformel. Je Zeitraum zuerst der Sieger; Antippen öffnet die Top 10,
 * von dort die vollständige Rangliste.
 */

import { useEffect, type ReactNode } from 'react';
import { GlossaryTip, Term } from '../components/help';
import { NoiseToggle, WindowChips, WindowRuler } from '../components/controls';
import { LastCloseBadge } from '../components/rows';
import { IconDownload } from '../components/icons';
import { Disclosure, ErrorNote, IsinCopy, Loading, Notice, Pager, Pct, Segmented, ViewIntro, WatchButton } from '../components/ui';
import { EMPTY_REASONS, INSTRUMENT_HINT_SHORT, VENUE_DEVIATION_BIT, WINDOW_HINT_SHORT, hintLabels, sessionRuleText, volumeRuleText } from '../lib/codes';
import { downloadText, safeFilename, toCsv, type CsvValue } from '../lib/csv';
import { PREVIEW } from '../lib/env';
import * as f from '../lib/format';
import { useOverview, useWindowFull, useWindowHead } from '../lib/hooks';
import { exchangeOf, instName, listingShort, trNameIfDifferent, unitOf } from '../lib/instruments';
import { buildHash, updateParams, type Route } from '../lib/router';
import { parseWindow } from '../lib/scoring';
import {
  canHideNoisy,
  countsOf,
  hasCleanWinners,
  hasTurnover,
  isVeryLow,
  JUMP_BIT,
  listEntries,
  listOrder,
  listSize,
  listTitle,
  parseReturnList,
  quietList,
  thresholdLabel,
  turnoverBasis,
  turnoverOf,
  turnoverShort,
  winnersOf,
  type ListEntry,
  type ReturnList,
} from '../lib/turnover';
import type { Instruments, Manifest, Overview, WinnerRow } from '../lib/types';
import { venueListText, venueOf } from '../lib/venue';
import { useApp } from '../state/AppState';
import { ReturnLadderView } from './ReturnLadderView';

const RANGES = {
  '1-7': [1, 7],
  '8-30': [8, 30],
  '31-90': [31, 90],
  alle: [1, 90],
} as const;
type RangeKey = keyof typeof RANGES;
const PAGE = 50;

function parseRange(text: string | null): RangeKey {
  return text === '1-7' || text === '8-30' || text === '31-90' ? text : 'alle';
}

type Mode = ReturnList | 'beide';

/** Ansicht der Übersicht: A und B nebeneinander (Standard ab 1.5) oder eine Gruppe. */
function parseMode(text: string | null): Mode {
  return text === 'alle' || text === 'umsatz' ? text : 'beide';
}

function ListTabs({ list, onChange, withBoth = false }: { list: Mode; onChange: (list: Mode) => void; withBoth?: boolean }) {
  const { manifest } = useApp();
  return (
    <Segmented
      label="Rangliste"
      hideLabel
      options={[
        ...(withBoth ? [{ value: 'beide' as Mode, label: 'A und B' }] : []),
        { value: 'alle' as Mode, label: withBoth ? 'A: alle' : 'Höchste Kursrendite' },
        { value: 'umsatz' as Mode, label: withBoth ? 'B: Umsatz' : `Ø Umsatz ≥ ${thresholdLabel(manifest)}` },
      ]}
      value={list}
      onChange={(value) => onChange(value as Mode)}
    />
  );
}

function ListIntro({ list }: { list: ReturnList }) {
  const { manifest } = useApp();
  return (
    <>
      <h2 className="section-title">{listTitle(list, manifest)}</h2>
      <p className="section-note">
        {list === 'alle'
          ? 'Alle vergleichbaren TR-Aktien, nur nach Kursrendite sortiert (0 % Gleichmäßigkeit / 100 % Kursrendite). Ohne Mindestgrenze für Preis, Börsenwert oder Umsatz; kaum Umsatz und Einzelsprünge sind gekennzeichnet und lassen sich ausblenden.'
          : `Dieselbe Rangliste, aufgenommen sind nur Aktien mit Ø Tagesumsatz ab ${thresholdLabel(manifest)}. Sortiert wird weiter nur nach Kursrendite.`}
      </p>
    </>
  );
}

/** Rechenweg und Datenbasis beider Ranglisten (eingeklappt, damit die Liste oben steht). */
function MethodNote() {
  const { manifest, isDemo } = useApp();
  if (!manifest) return null;
  const t = manifest.turnover;
  const fx = t?.wechselkurse;
  return (
    <Disclosure summary="Berechnung und Datenbasis">
      <div className="prose">
        <p>
          Kursstand {f.day(manifest.cutoff_day)}: historische Tagesschlusskurse, keine Livekurse. Kursrendite = Endkurs / Startkurs − 1, in der Notierungswährung, splitbereinigt, ohne Dividenden,
          Gebühren, Steuern und Wechselkurseffekt; sortiert wird mit ungerundeten Werten.
        </p>
        <p>
          „n Tage“ heißt n Kalendertage rückwärts ab dem Kursstand. Fällt der Start auf einen handelsfreien Tag, gilt der letzte reguläre Schlusskurs davor; fehlende Schlusskurse an erwarteten
          Handelstagen werden nicht durch ältere ersetzt. Start- und Enddatum stehen in jeder Zeile. Beide Ranglisten nutzen denselben Kursstand und dieselbe Formel.
        </p>
        <p>
          Ø Tagesumsatz: je Sitzung Schlusskurs × gemeldetes Volumen derselben Notierung, Mittelwert über die letzten {t?.sitzungen ?? 20} abgeschlossenen Sitzungen mit Daten; mindestens{' '}
          {t?.min_sitzungen_mit_umsatz ?? 16} davon mit Umsatz. Fehlende Tage zählen nicht als null; ein Split im Zeitraum macht den Wert unbestimmbar. Sehr niedrig heißt unter{' '}
          {f.money(t?.sehr_niedrig_usd ?? 1_000_000, 'USD')}.
        </p>
        <p>
          Andere Währungen werden nur für diesen Filter indikativ in USD umgerechnet: {fx?.quelle ?? 'Referenzkurse'}
          {fx?.letzter_kurstag ? `, Kurstage ${f.isoDate(fx.erster_kurstag)} bis ${f.isoDate(fx.letzter_kurstag)}` : ''}
          {fx?.abgerufen_utc ? `, abgerufen ${f.berlinTime(fx.abgerufen_utc)}` : ''}. Je Sitzung gilt der Kurs dieses Tages oder der letzte davor (höchstens {fx?.max_alter_tage ?? 5} Tage alt).
        </p>
        <p>
          Quelle der Kurse: {manifest.provider.prices}
          {isDemo ? ' (synthetische DEMO-Daten)' : ''}. Die bestehenden Prüfungen gelten für beide Ranglisten: {sessionRuleText(manifest.method)}, {volumeRuleText(manifest.method)}; Kurssprünge und
          Kapitalmaßnahmen werden geprüft oder gekennzeichnet.
        </p>
      </div>
    </Disclosure>
  );
}

/** Erfasste TR-Instrumente, geladene Kursreihen und tatsächlich ausgewertete Aktien – je Rangliste getrennt. */
function CountsBlock({ list, overview, from, to }: { list: ReturnList; overview: Overview; from: number; to: number }) {
  const { manifest, instruments } = useApp();
  if (!manifest || !instruments) return null;
  const counts = countsOf(overview, list).slice(from - 1, to);
  const filled = counts.filter((n) => n > 0);
  const lo = filled.length ? Math.min(...filled) : 0;
  const hi = filled.length ? Math.max(...filled) : 0;
  const evaluated = lo === hi ? f.integer(lo) : `${f.integer(lo)}–${f.integer(hi)}`;
  const t = manifest.turnover;
  const determined = t?.anzahl.status.ok ?? null;
  const undetermined = t ? Object.entries(t.anzahl.status).filter(([key]) => key !== 'ok' && key !== 'keine_kurse').reduce((sum, [, n]) => sum + n, 0) : null;
  return (
    <div>
      <dl className="stats" aria-label={`Abdeckung: ${listTitle(list, manifest)}`}>
        <div className="stat">
          <dt className="stat-label">Erfasste TR-Instrumente</dt>
          <dd className="stat-value">{f.integer(manifest.coverage.universe_total)}</dd>
        </div>
        <div className="stat">
          <dt className="stat-label">Geladene Kursreihen</dt>
          <dd className="stat-value">{f.integer(manifest.coverage.histories_loaded)}</dd>
        </div>
        {list === 'umsatz' ? (
          <>
            <div className="stat">
              <dt className="stat-label">Ø Umsatz bestimmt</dt>
              <dd className="stat-value">{f.integer(determined)}</dd>
            </div>
            <div className="stat">
              <dt className="stat-label">davon ≥ {thresholdLabel(manifest)}</dt>
              <dd className="stat-value">{f.integer(t?.anzahl.aufgenommen ?? null)}</dd>
            </div>
          </>
        ) : null}
        <div className="stat">
          <dt className="stat-label">
            Ausgewertet ({from}–{to} Tage)
          </dt>
          <dd className="stat-value">{evaluated}</dd>
        </div>
      </dl>
      <p className="section-note">
        Teiluniversum: verglichen werden nur Aktien mit eindeutiger Zuordnung und vergleichbaren Kursdaten – keine vollständige Prüfung aller TR-Aktien.
        {list === 'umsatz' && undetermined !== null ? ` Bei ${f.integer(undetermined)} Aktien mit Kursreihe ist der Ø Umsatz nicht bestimmbar (Volumen, Kurse oder Wechselkurs fehlen); sie können nur in „Höchste Kursrendite“ erscheinen.` : ''}
        {manifest.completeness.status !== 'vollstaendig' ? ' Dieser Stand ist ein Teilstand: für einzelne Börsen fehlten Schlusskurse.' : ''}
      </p>
    </div>
  );
}

/** Kennzeichen einer Aktie: sehr niedriger Umsatz, Umsatz unbekannt, Fenster- und Instrumenthinweise. */
function Hints({ idx, wf, tie, list }: { idx: number; wf: number; tie?: boolean; list: ReturnList }) {
  const { manifest, instruments } = useApp();
  if (!manifest || !instruments) return null;
  const info = turnoverOf(instruments, idx);
  const badges: ReactNode[] = [];
  if (tie) badges.push(<span key="tie" className="badge">gleichauf</span>);
  if (isVeryLow(info, manifest))
    badges.push(
      <span key="low" className="badge badge-warn" title="Ø Tagesumsatz unter 1 Mio. USD – der Kurs lässt sich leicht bewegen, ein Kauf zum angezeigten Kurs ist oft nicht möglich">
        Kaum Umsatz
      </span>,
    );
  if (list === 'alle' && info && info.status !== 'ok') badges.push(<span key="unk" className="badge badge-warn">Umsatz nicht bestimmbar</span>);
  for (const [bit, label] of Object.entries(WINDOW_HINT_SHORT)) {
    if (!((wf >> Number(bit)) & 1)) continue;
    const warn = Number(bit) === VENUE_DEVIATION_BIT || Number(bit) === JUMP_BIT;
    badges.push(
      <span key={`w${bit}`} className={warn ? 'badge badge-warn' : 'badge'} title={Number(bit) === JUMP_BIT ? 'Ein einzelner Handelstag erklärt mehr als die Hälfte der Kursbewegung' : undefined}>
        {label}
      </span>,
    );
  }
  const other = hintLabels(INSTRUMENT_HINT_SHORT, instruments.warnings[idx] ?? 0);
  if (!badges.length && !other.length) return null;
  return (
    <div className="row-extra">
      {badges.length ? <div className="badges">{badges}</div> : null}
      {other.length ? <span>Hinweise: {other.join('; ')}</span> : null}
    </div>
  );
}

/** Ergebnis des Abgleichs mit dem zweiten Börsenplatz – nur für geprüfte Aktien (erste Plätze). */
function VenueLine({ idx, entry }: { idx: number; entry: ListEntry }) {
  const { manifest, instruments } = useApp();
  if (!manifest || !instruments) return null;
  const text = venueListText(manifest, venueOf(instruments, idx), entry.venue);
  if (!text) return null;
  return <span className={`row-alt venue-line${entry.venue?.status === 'abweichung' ? ' venue-warn' : ''}`}>{text}</span>;
}

/** Alle Angaben zu einer Aktie in einer Rangliste (Rang, Name, Ticker, ISIN, Rendite, Kurse, Börse, Umsatz, Hinweise). */
function StockRow({ entry, list, h, rankLabel, rankNote }: { entry: ListEntry; list: ReturnList; h: number; rankLabel?: ReactNode; rankNote?: ReactNode }) {
  const { manifest, instruments } = useApp();
  if (!manifest || !instruments) return null;
  const idx = entry.idx;
  const isin = instruments.isin[idx];
  const name = instName(instruments, idx);
  const trName = trNameIfDifferent(instruments, idx);
  const unit = unitOf(instruments, idx);
  const ticker = instruments.ticker[idx] ?? instruments.symbol[idx];
  const info = turnoverOf(instruments, idx);
  const detailHref = buildHash(`/aktie/${isin}`, { h, w: 0, p: 'native' });
  return (
    <li className={`row stock-row${entry.tie ? ' row-tie' : ''}`}>
      <div className="row-rank">
        {rankLabel ?? entry.rank}
        {rankNote ? <small>{rankNote}</small> : null}
        <WatchButton isin={isin} name={name} />
      </div>
      <div className="row-main">
        <a className="row-link row-name" href={detailHref} aria-label={`${name}, ${f.pct(entry.r)} in ${f.windowLabel(h)}. Kurschart öffnen`}>
          {name}
        </a>
        {trName ? <span className="row-alt">In der TR-Liste: {trName}</span> : null}
        <div className="row-meta">
          {ticker ? <span className="ticker">{ticker}</span> : null}
          <IsinCopy isin={isin} compact />
          <LastCloseBadge idx={idx} />
        </div>
        <span className="row-alt price-path">
          {f.day(entry.start)}: {f.price(entry.p0, unit)} → {f.day(entry.end)}: {f.price(entry.p1, unit)}
        </span>
        <span className="row-alt">{listingShort(instruments, idx) || 'Börse und Währung unbekannt'}</span>
        {hasTurnover(instruments) ? (
          <span className="row-alt turnover-line">
            {turnoverShort(info, manifest)}
            {info && (info.status === 'ok' || info.withData > 0) ? <span className="turnover-basis"> ({turnoverBasis(info, manifest)})</span> : null}
          </span>
        ) : null}
        <VenueLine idx={idx} entry={entry} />
      </div>
      <div className="row-figs">
        <Pct value={entry.r} strong />
      </div>
      <div className="row-wide">
        <Hints idx={idx} wf={entry.wf} tie={entry.tie} list={list} />
      </div>
    </li>
  );
}

function TopTen({ h, list, size }: { h: number; list: ReturnList; size: number }) {
  const { instruments, manifest, prefs } = useApp();
  const overview = useOverview();
  const clean = prefs.ohneAuffaellige && hasCleanWinners(overview.data) && canHideNoisy(instruments);
  // Ohne Auffällige (ab 1.14): die ersten zehn unauffälligen – zuerst unter den ersten 50 Plätzen (Kopfdatei), die
  // vollständige Datei nur, wenn dort weniger als zehn stehen. Plätze wie in der vollständigen Rangliste.
  const head = useWindowHead(h);
  const headQuiet = clean && head.data && instruments ? quietList(head.data, list, instruments, manifest) : null;
  const needFull = Boolean(head.data && headQuiet && headQuiet.length < 10 && listOrder(head.data, list).length < listSize(head.data, list));
  const full = useWindowFull(h, needFull);
  const source = needFull ? full : head;
  if (source.error) return <ErrorNote error={source.error} />;
  if (!source.data || !instruments) return <Loading height={420} label={`Top 10 für ${f.windowLabel(h)} werden geladen`} />;
  const entries = clean
    ? (needFull ? quietList(source.data, list, instruments, manifest) : headQuiet ?? []).slice(0, 10)
    : listEntries(source.data, list, 0, 10, instruments.last_close_day);
  return (
    <div className="top-ten">
      <ol className="rows" aria-label={`Top 10, ${f.windowLabel(h)}`}>
        {entries.map((entry) => (
          <StockRow key={entry.idx} entry={entry} list={list} h={h} />
        ))}
      </ol>
      <p className="section-note">
        {clean
          ? `Ohne Auffällige: die ersten ${f.integer(entries.length)} unauffälligen Aktien, Plätze wie in der vollständigen Rangliste (${f.integer(size)} Aktien).`
          : `Gezeigt: Platz 1 bis ${f.integer(Math.min(10, size))} von ${f.integer(size)}.`}
      </p>
      {size > 0 ? (
        <a className="btn btn-block" href={buildHash('/rendite/liste', { h, f: list === 'alle' ? null : list })}>
          Vollständige Rangliste ({f.integer(size)} {size === 1 ? 'Aktie' : 'Aktien'})
        </a>
      ) : null}
    </div>
  );
}

function WindowBlock({ row, list, open, onToggle }: { row: WinnerRow; list: ReturnList; open: boolean; onToggle: () => void }) {
  const { manifest } = useApp();
  const winner = row.entries[0];
  const label = (
    <>
      {row.h}
      <small>{row.h === 1 ? 'Tag' : 'Tage'}</small>
    </>
  );
  if (!winner) {
    return (
      <li className="window-block">
        <ol className="rows">
          <li className="row row-empty">
            <div className="row-rank">{label}</div>
            <div className="row-main">
              <span className="row-name">Keine Aktie in dieser Rangliste</span>
              <span className="row-alt">
                {list === 'umsatz' ? `Keine vergleichbare Aktie erreicht für ${f.windowLabel(row.h)} den Ø Tagesumsatz von ${thresholdLabel(manifest)}.` : EMPTY_REASONS[row.empty ?? ''] ?? EMPTY_REASONS.keine_vergleichbare_aktie}
              </span>
            </div>
            <div className="row-figs">
              <span className="pct pct-fehlt">–</span>
            </div>
          </li>
        </ol>
      </li>
    );
  }
  const entry: ListEntry = { rank: row.rank ?? 1, idx: winner.idx, r: winner.r, start: winner.start, end: winner.end, p0: winner.p0 ?? null, p1: winner.p1 ?? null, wf: winner.wf ?? 0, tie: row.tie, venue: winner.xv };
  return (
    <li className={`window-block${open ? ' is-open' : ''}`}>
      <ol className="rows">
        <StockRow entry={entry} list={list} h={row.h} rankLabel={label} rankNote={row.rank && row.rank > 1 ? `Platz ${row.rank}` : undefined} />
      </ol>
      {row.tie ? <p className="section-note">Exakt gleiche Rendite wie {row.entries.length - 1 === 1 ? 'eine weitere Aktie' : `${row.entries.length - 1} weitere Aktien`} – siehe Top 10.</p> : null}
      {row.all_negative ? <p className="section-note">Alle Renditen in diesem Zeitraum sind negativ: vorne steht der geringste Verlust.</p> : null}
      <button type="button" className="btn btn-quiet window-toggle" aria-expanded={open} onClick={onToggle}>
        {open ? 'Top 10 schließen' : `Top 10 anzeigen (${f.integer(row.M)} ${row.M === 1 ? 'Aktie' : 'Aktien'} verglichen)`}
      </button>
      {open ? <TopTen h={row.h} list={list} size={row.M} /> : null}
    </li>
  );
}

/** Ein Zeitraum mit den Siegern beider Gruppen nebeneinander (Gruppe A: alle, Gruppe B: Ø Umsatz ≥ Schwelle). */
function PairBlock({ rowA, rowB, open, jumped, onToggle }: { rowA: WinnerRow; rowB: WinnerRow | null; open: boolean; jumped: boolean; onToggle: () => void }) {
  const h = rowA.h;
  return (
    <li className={`pair-block${open ? ' is-open' : ''}${jumped ? ' is-jump' : ''}`} id={`rw-${h}`} aria-current={jumped ? 'true' : undefined}>
      <div className="pair-h">
        {h}
        <small>{h === 1 ? 'Tag' : 'Tage'}</small>
        {jumped ? <small className="jump-note">gewählt</small> : null}
      </div>
      <div className="pair-cells">
        <PairCell row={rowA} list="alle" />
        {rowB ? <PairCell row={rowB} list="umsatz" /> : null}
      </div>
      <button type="button" className="btn btn-quiet window-toggle" aria-expanded={open} onClick={onToggle}>
        {open ? 'Top 10 schließen' : 'Top 10 von A und B'}
      </button>
      {open ? (
        <div className="pair-top">
          <section aria-label={`Top 10 Gruppe A, ${f.windowLabel(h)}`}>
            <h3 className="pair-top-title">A – alle Aktien</h3>
            <TopTen h={h} list="alle" size={rowA.M} />
          </section>
          {rowB ? (
            <section aria-label={`Top 10 Gruppe B, ${f.windowLabel(h)}`}>
              <h3 className="pair-top-title">B – Ø Umsatz ≥ Schwelle</h3>
              <TopTen h={h} list="umsatz" size={rowB.M} />
            </section>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function PairCell({ row, list }: { row: WinnerRow; list: ReturnList }) {
  const { manifest, instruments } = useApp();
  if (!manifest || !instruments) return null;
  const label = list === 'alle' ? 'A – alle Aktien' : `B – Ø Umsatz ≥ ${thresholdLabel(manifest)}`;
  const winner = row.entries[0];
  if (!winner) {
    return (
      <div className="pair-cell is-empty">
        <span className="tenw-group">{label}</span>
        <span className="row-alt">{list === 'umsatz' ? `Keine vergleichbare Aktie erreicht den Ø Tagesumsatz von ${thresholdLabel(manifest)}.` : EMPTY_REASONS[row.empty ?? ''] ?? EMPTY_REASONS.keine_vergleichbare_aktie}</span>
      </div>
    );
  }
  const isin = instruments.isin[winner.idx];
  const name = instName(instruments, winner.idx);
  return (
    <div className="pair-cell">
      <span className="tenw-group">{label}</span>
      <a className="row-link row-name" href={buildHash('/rendite/liste', { h: row.h, f: list === 'alle' ? null : list })} aria-label={`${label}: ${name}, ${f.pct(winner.r)} in ${f.windowLabel(row.h)}. Vollständige Rangliste öffnen`}>
        {name}
      </a>
      <span className="gcell-isin" translate="no">
        {isin}
      </span>
      <span className="pair-figs">
        <Pct value={winner.r} strong />
        <span className="row-alt">
          {f.day(winner.start)} – {f.day(winner.end)}
        </span>
      </span>
      {row.tie ? <span className="badge">gleichauf mit {row.entries.length - 1 === 1 ? 'einer weiteren Aktie' : `${row.entries.length - 1} weiteren`}</span> : null}
      {row.rank && row.rank > 1 ? <span className="row-alt">Platz {f.integer(row.rank)} der vollständigen Rangliste – davor nur Auffällige</span> : null}
      {row.all_negative ? <span className="row-alt">Alle Renditen negativ: vorne steht der geringste Verlust.</span> : null}
    </div>
  );
}

function exportMeta(manifest: Manifest, list: ReturnList, extra: [string, string][]): [string, string][] {
  return [
    ['Ansicht', listTitle(list, manifest)],
    ['Gewichtung', '0 % Gleichmäßigkeit / 100 % Kursrendite'],
    ...extra,
    ['Snapshot', manifest.snapshot_id],
    ['Kursstichtag', manifest.cutoff_session_date],
    ['Datenmodus', manifest.data_mode === 'demo' ? 'DEMO – synthetische Testdaten' : manifest.data_mode],
    ['Kursquelle', manifest.provider.prices],
    ['Basis', manifest.currency_basis],
    ['Umsatz', manifest.turnover?.berechnung ?? ''],
    ['Wechselkurse', manifest.turnover ? `${manifest.turnover.wechselkurse.quelle ?? ''}, Kurstage bis ${manifest.turnover.wechselkurse.letzter_kurstag ?? '–'} (indikativ)` : ''],
  ];
}

function csvRow(instruments: Instruments, manifest: Manifest, h: number, e: ListEntry): CsvValue[] {
  const info = turnoverOf(instruments, e.idx);
  return [
    h,
    e.rank,
    instName(instruments, e.idx),
    instruments.ticker[e.idx] ?? instruments.symbol[e.idx] ?? '',
    instruments.isin[e.idx],
    100 * e.r,
    f.day(e.start),
    e.p0,
    f.day(e.end),
    e.p1,
    exchangeOf(instruments, e.idx) ?? '',
    unitOf(instruments, e.idx) ?? '',
    info?.status === 'ok' ? info.usd : null,
    info ? turnoverBasis(info, manifest) : '',
    venueCsv(instruments, manifest, e),
    [isVeryLow(info, manifest) ? 'kaum Umsatz' : '', ...hintLabels(WINDOW_HINT_SHORT, e.wf), ...hintLabels(INSTRUMENT_HINT_SHORT, instruments.warnings[e.idx] ?? 0), e.tie ? 'gleichauf' : '']
      .filter(Boolean)
      .join('; '),
  ];
}

function venueCsv(instruments: Instruments, manifest: Manifest, e: ListEntry): string {
  if (!manifest.venue_check) return '';
  const info = venueOf(instruments, e.idx);
  return info ? venueListText(manifest, info, e.venue) : 'nicht geprüft (nur erste Plätze)';
}

const CSV_HEAD = ['Tage', 'Rang', 'Unternehmen', 'Ticker', 'ISIN', 'Kursrendite %', 'Start', 'Startkurs', 'Ende', 'Endkurs', 'Referenzbörse', 'Kurseinheit', 'Ø Tagesumsatz USD', 'Umsatz-Berechnungsbasis', 'Zweiter Börsenplatz', 'Hinweise'];

export function ReturnRankingsView({ route }: { route: Route }) {
  const { manifest, instruments, prefs } = useApp();
  const overview = useOverview();
  const jump = Number(route.params.get('zeile')) || null;
  useEffect(() => {
    if (!jump) return;
    const el = document.getElementById(`rw-${jump}`);
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    el?.scrollIntoView({ block: 'start', behavior: reduced ? 'auto' : 'smooth' });
  }, [jump, overview.data]);
  if (route.params.get('modus') === 'gewichtung') return <ReturnLadderView route={route} />;
  if (!manifest || !instruments) return null;
  const mode = parseMode(route.params.get('f'));
  const list: ReturnList = mode === 'beide' ? 'alle' : mode;
  const rangeKey = parseRange(route.params.get('z'));
  const [from, to] = RANGES[rangeKey];
  const openH = parseWindow(route.params.get('offen'), 0);
  const ov = overview.data;
  const clean = prefs.ohneAuffaellige && hasCleanWinners(ov);
  const rows = ov ? winnersOf(ov, list, clean).slice(from - 1, to) : [];
  const rowsB = ov && ov.winners_l ? winnersOf(ov, 'umsatz', clean).slice(from - 1, to) : [];
  const supported = !ov || list === 'alle' || Boolean(ov.winners_l);
  const pickWindow = (h: number) => updateParams(route, { zeile: h, offen: null, z: h >= from && h <= to ? route.params.get('z') : null });

  const exportCsv = () => {
    if (!ov) return;
    const lists: ReturnList[] = mode === 'beide' ? (ov.winners_l ? ['alle', 'umsatz'] : ['alle']) : [list];
    const csvRows: CsvValue[][] = [];
    for (const which of lists) {
      for (const row of winnersOf(ov, which, clean)) {
        row.entries.forEach((w) => {
          const values = csvRow(instruments, manifest, row.h, { rank: 1, idx: w.idx, r: w.r, start: w.start, end: w.end, p0: w.p0 ?? null, p1: w.p1 ?? null, wf: w.wf ?? 0, tie: row.tie, venue: w.xv });
          csvRows.push(mode === 'beide' ? [which === 'alle' ? 'A' : 'B', ...values] : values);
        });
      }
    }
    const head = mode === 'beide' ? ['Gruppe', ...CSV_HEAD] : CSV_HEAD;
    const csv = toCsv(exportMeta(manifest, list, [['Inhalt', mode === 'beide' ? 'Sieger je Zeitraum 1–90 Tage, Gruppe A und B' : 'Sieger je Zeitraum 1–90 Tage']]), head, csvRows, mode === 'beide' ? [undefined, undefined, undefined, undefined, undefined, undefined, 6] : [undefined, undefined, undefined, undefined, undefined, 6]);
    downloadText(safeFilename(`sieger-1-90_${mode}_${manifest.snapshot_id}.csv`), csv);
  };

  return (
    <div className="view">
      <header className="view-head">
        <ViewIntro>
          <p className="lede">
            Hier siehst du für jeden Zeitraum von 1 bis 90 Tagen die Aktie, die am stärksten gestiegen ist. Tippe auf einen Zeitraum, um die ganze Rangliste zu sehen,
            oder auf „Top 10“ für die ersten zehn.
          </p>
          <p className="lede">
            <Term id="gruppe">Gruppe A</Term> enthält alle vergleichbaren Aktien, Gruppe B nur gut gehandelte (Ø Tagesumsatz ab {thresholdLabel(manifest)}). Sortiert wird
            nur nach der <Term id="kursrendite">Kursrendite</Term> – auch ein schwankender Verlauf kann vorn liegen. Für „stark und gleichmäßig“ wähle oben „Gleichmäßig +
            Rendite“.
          </p>
        </ViewIntro>
      </header>

      <ListTabs list={mode} withBoth={Boolean(ov?.winners_l) || !ov} onChange={(next) => updateParams(route, { f: next === 'beide' ? null : next, offen: null })} />
      {mode === 'beide' ? (
        <p className="section-note">
          Beide Listen nur nach Kursrendite sortiert (0 % Gleichmäßigkeit / 100 % Kursrendite), gleicher Kursstand, gleiche Formel. B ist eine Teilmenge von A – keine unabhängige Bestätigung.
        </p>
      ) : (
        <ListIntro list={list} />
      )}
      <MethodNote />
      {ov && hasCleanWinners(ov) ? <NoiseToggle /> : null}

      {!supported ? (
        <Notice tone="info" title="In diesem Datenstand noch nicht enthalten">
          <p>Der Umsatzfilter wird ab Softwareversion 1.1 berechnet. Der nächste tägliche Lauf veröffentlicht beide Ranglisten.</p>
        </Notice>
      ) : null}
      {ov ? <CountsBlock list={list} overview={ov} from={from} to={to} /> : null}

      <Segmented
        label="Zeiträume in Tagen"
        options={[
          { value: '1-7', label: '1–7' },
          { value: '8-30', label: '8–30' },
          { value: '31-90', label: '31–90' },
          { value: 'alle', label: 'Alle 90' },
        ]}
        value={rangeKey}
        onChange={(value) => updateParams(route, { z: value === 'alle' ? null : value, offen: null, zeile: null })}
      />
      <WindowChips value={jump} onPick={pickWindow} label="Zu Zeitraum springen" onPage />

      {overview.error ? <ErrorNote error={overview.error} /> : null}
      {!ov && !overview.error ? <Loading height={700} label="Ranglisten werden geladen" /> : null}
      {ov && supported && mode === 'beide' ? (
        <ol className="window-list pair-list" aria-label={`Höchste Kursrendite, Gruppe A und B: Sieger je Zeitraum ${from} bis ${to} Tage`}>
          {rows.map((row, k) => (
            <PairBlock
              key={row.h}
              rowA={row}
              rowB={rowsB[k] ?? null}
              open={openH === row.h}
              jumped={jump === row.h}
              onToggle={() => updateParams(route, { offen: openH === row.h ? null : row.h })}
            />
          ))}
        </ol>
      ) : null}
      {ov && supported && mode !== 'beide' ? (
        <ol className="window-list" aria-label={`${listTitle(list, manifest)}: Sieger je Zeitraum ${from} bis ${to} Tage`}>
          {rows.map((row) => (
            <WindowBlock key={row.h} row={row} list={list} open={openH === row.h} onToggle={() => updateParams(route, { offen: openH === row.h ? null : row.h })} />
          ))}
        </ol>
      ) : null}

      <div className="toolbar no-print">
        <a className="btn btn-quiet" href={buildHash('/rendite', { modus: 'gewichtung' })}>
          Spitzenreiter anderer Gewichtungen
        </a>
        {!PREVIEW ? (
          <button type="button" className="btn btn-quiet" disabled={!ov || !supported} onClick={exportCsv}>
            <IconDownload /> CSV
          </button>
        ) : null}
      </div>
    </div>
  );
}

/** Vollständige Rendite-Rangliste eines Zeitraums, seitenweise. */
export function ReturnListView({ route }: { route: Route }) {
  const { manifest, instruments, prefs, isDemo } = useApp();
  const list = parseReturnList(route.params.get('f'));
  const h = parseWindow(route.params.get('h'), Math.min(prefs.h, 7));
  const page = Math.max(1, Number(route.params.get('seite') ?? 1) || 1);
  const full = useWindowFull(h);
  if (!manifest || !instruments) return null;
  const win = full.data;
  const clean = prefs.ohneAuffaellige && canHideNoisy(instruments);
  // Ohne Auffällige (ab 1.14): gefilterte Liste, Plätze wie in der vollständigen Rangliste
  const shown = win && clean ? quietList(win, list, instruments, manifest) : null;
  const size = shown ? shown.length : win ? listSize(win, list) : 0;
  const pages = Math.max(1, Math.ceil(size / PAGE));
  const current = Math.min(page, pages);
  const entries = shown ? shown.slice((current - 1) * PAGE, current * PAGE) : win ? listEntries(win, list, (current - 1) * PAGE, PAGE, instruments.last_close_day) : [];
  const supported = !win || list === 'alle' || Boolean(win.orders.v0l);

  const exportCsv = () => {
    if (!win) return;
    // gezeigte Liste: ohne Auffällige gefiltert, sonst vollständig
    const all = shown ?? listEntries(win, list, 0, size, instruments?.last_close_day);
    const csv = toCsv(exportMeta(manifest, list, [['Zeitraum', f.windowLabel(h)], ['Vergleichsfeld M', String(size)]]), CSV_HEAD, all.map((e) => csvRow(instruments, manifest, h, e)), [undefined, undefined, undefined, undefined, undefined, 6]);
    downloadText(safeFilename(`rendite_${list}_${h}T_${manifest.snapshot_id}.csv`), csv);
  };

  return (
    <div className="view">
      <WindowRuler value={h} onChange={(next) => updateParams(route, { h: next, seite: null })}>
        {win ? (
          <p>
            Rückblick ab <strong>{f.dayWithWeekday(win.target_start_day)}</strong> bis Kursstand <strong>{f.dayWithWeekday(win.cutoff_day)}</strong>. Startkurs ist der letzte Börsenschluss am oder vor dem Ziel-Startdatum.
          </p>
        ) : null}
      </WindowRuler>
      <ListTabs list={list} onChange={(next) => updateParams(route, { f: next === 'alle' ? null : next, seite: null })} />
      <ListIntro list={list} />
      {canHideNoisy(instruments) ? <NoiseToggle /> : null}
      <div className="row-legend">
        <p>So liest du eine Zeile:</p>
        <ul>
          <li>
            <strong>Prozentzahl rechts</strong> – die Kursrendite im Zeitraum <GlossaryTip id="kursrendite" label="Kursrendite" />
          </li>
          <li>
            <strong>„Kaum Umsatz“, „Einzelsprung“</strong> – hier genauer hinsehen <GlossaryTip id="auffaellig" label="Kaum Umsatz und Einzelsprung" />
          </li>
          <li>
            <strong>„Schlusskurs“ mit Datum</strong> – es zählt ein älterer Schlusskurs <GlossaryTip id="schlusskurs" label="Schlusskurs" />
          </li>
        </ul>
      </div>

      {full.error ? <ErrorNote error={full.error} /> : null}
      {!win && !full.error ? <Loading height={1200} label="Rangliste wird geladen" /> : null}
      {win && !supported ? (
        <Notice tone="info" title="In diesem Datenstand noch nicht enthalten">
          <p>Der Umsatzfilter wird ab Softwareversion 1.1 berechnet.</p>
        </Notice>
      ) : null}
      {win && supported ? (
        <>
          <p className="section-note">
            {size > 0
              ? clean
                ? `${f.windowLabel(h)}: ${f.integer(size)} unauffällige von ${f.integer(listSize(win, list))} Aktien in dieser Rangliste (ohne kaum Umsatz und Einzelsprünge). Plätze wie in der vollständigen Rangliste.`
                : `${f.windowLabel(h)}: ${f.integer(size)} ${size === 1 ? 'Aktie' : 'Aktien'} in dieser Rangliste (von ${f.integer(win.counts.V)} mit veröffentlichter Kursrendite und ${f.integer(manifest.coverage.universe_total)} erfassten TR-Instrumenten). Gezeigt: Platz ${f.integer((current - 1) * PAGE + 1)} bis ${f.integer(Math.min(size, current * PAGE))}.`
              : `${f.windowLabel(h)}: keine Aktie in dieser Rangliste.`}
          </p>
          {size > 0 ? (
            <ol className="rows" aria-label={`${listTitle(list, manifest)}, ${f.windowLabel(h)}`} start={clean ? undefined : (current - 1) * PAGE + 1}>
              {entries.map((entry) => (
                <StockRow key={entry.idx} entry={entry} list={list} h={h} />
              ))}
            </ol>
          ) : null}
          <Pager page={current} pages={pages} onChange={(p) => updateParams(route, { seite: p })} label="Seiten der Rangliste" />
          <div className="toolbar no-print">
            <a className="btn btn-quiet" href={buildHash('/rendite', { f: list, z: h <= 7 ? '1-7' : h <= 30 ? '8-30' : '31-90', offen: h })}>
              Zur Übersicht
            </a>
            {!PREVIEW ? (
              <button type="button" className="btn btn-quiet" onClick={exportCsv} disabled={!size}>
                <IconDownload /> CSV
              </button>
            ) : null}
          </div>
        </>
      ) : null}
      {isDemo ? <p className="section-note">DEMO: synthetische Testdaten, keine echten Unternehmen.</p> : null}
    </div>
  );
}
