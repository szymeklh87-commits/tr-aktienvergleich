/* Musterdepots (ab 1.9) – „Zwei Zehnerdepots · 1–30 Tage · Beiträge“ als Ansicht der App.
 *
 * 1. Welche Aktien erscheinen am häufigsten? Zwei Top-10-Listen (erste Plätze, Top-10-Nennungen),
 *    beide zusammen, gemeinsame grün; Auswahl für ein eigenes Depot.
 * 2. Depot: Depotrendite und Beitrag jeder Aktie für ein Rückblickfenster (1–30 Kalendertage),
 *    gleiche Startbeträge, USD, EUR oder Originalwährung, Startkapital frei wählbar.
 * 3. Alle Depots für 1–30 Tage (Grafik und Tabelle), Kurse im direkten Vergleich, Rechenweg.
 * Alle Zahlen aus dem aktiven Datenstand (Kursreihen, Häufigkeit, Euro-Referenzkurse). */

import { scaleLinear } from 'd3-scale';
import { useMemo, useState } from 'react';
import { useDark } from '../components/charts';
import { CompareBlock } from '../components/compare';
import { IconClose, IconDownload } from '../components/icons';
import { TotalBadge } from '../components/signals';
import { Disclosure, ErrorNote, Loading, Notice, Pct, SectionTitle, Segmented, ViewIntro } from '../components/ui';
import { MAX_SERIES, seriesColor } from '../lib/colors';
import { downloadText, safeFilename, toCsv } from '../lib/csv';
import {
  BASIS_LABEL,
  byTops,
  byWins,
  computeDepot,
  DEFAULT_LIST_SIZE,
  DEPOT_DAYS,
  DEPOT_SIZE,
  depotWindows,
  fxLookup,
  LIST_SIZES,
  MAX_DEPOT_MEMBERS,
  MAX_OWN_DEPOTS,
  ownDepotDefs,
  parseWeightChoice,
  reportDepots,
  selectionFor,
  sortPositions,
  STANDARD_CHOICE,
  topLists,
  WEIGHT_CHOICE_LABEL,
  weightChoiceLabel,
  weightShift,
  winnersByWeight,
  type ContributionSort,
  type DepotBasis,
  type DepotDef,
  type DepotPosition,
  type DepotResult,
  type DepotWindowRow,
  type FreqRow,
  type FrequencySelection,
  type TopLists,
  type WeightChoice,
} from '../lib/depots';
import { PREVIEW } from '../lib/env';
import * as f from '../lib/format';
import { useFrequency, useFx, useSeriesMany, useSignals, useWindowHead } from '../lib/hooks';
import { hasGroupB, rankedEntries, WEIGHTS } from '../lib/scoring';
import { berlinClock, isIntraday } from '../lib/intraday';
import { instName, parseIsinImport } from '../lib/instruments';
import { buildHash, updateParams, type Route } from '../lib/router';
import { totalsByIsin, type TotalEntry } from '../lib/signals';
import { isVeryLow, turnoverOf, veryLowUsd } from '../lib/turnover';
import type { FrequencyData, Instruments, Manifest } from '../lib/types';
import { useApp } from '../state/AppState';

type ListFilter = 'union' | 'beide' | 'erste' | 'top10';
type CompareKind = 'depot' | 'gemeinsam' | 'alle' | 'siege' | 'nennungen';
type Totals = Map<string, TotalEntry> | null;

const QUICK_DAYS = [1, 7, 14, 21, 30];
const FX_FORMAT = new Intl.NumberFormat('de-DE', { maximumSignificantDigits: 5 });
const SCORE_2 = new Intl.NumberFormat('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function pp(fraction: number | null | undefined): string {
  return f.signedPctValue(fraction === null || fraction === undefined ? null : fraction * 100, 2).replace('%', 'PP');
}

function weight(fraction: number): string {
  return f.plainPct(fraction * 100, 1);
}

/** Auswahl der Häufigkeit aus der Adresse (ab 1.10: gw, zr, n). Alte Adressen (auswahl=…) gelten weiter. */
function parseSelection(params: URLSearchParams): { choice: WeightChoice; range: 30 | 90 } {
  const legacy = params.get('auswahl');
  if (legacy === 'bericht') return { choice: 'bericht', range: 30 };
  if (legacy === 'gesamt') return { choice: 'alle', range: 90 };
  if (legacy === 'rendite') return { choice: 0, range: 30 };
  return { choice: parseWeightChoice(params.get('gw')), range: params.get('zr') === '90' ? 90 : 30 };
}

function parseSize(text: string | null): number {
  return text === '10' ? 10 : DEFAULT_LIST_SIZE;
}

function parseFilter(text: string | null): ListFilter {
  return text === 'beide' || text === 'erste' || text === 'top10' ? text : 'union';
}

function parseDays(text: string | null): number {
  const n = Number(text);
  return Number.isInteger(n) && n >= 1 && n <= DEPOT_DAYS ? n : DEPOT_DAYS;
}

function parseSort(text: string | null): ContributionSort {
  return text === 'rendite' || text === 'name' ? text : 'beitrag';
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    area.remove();
    return ok;
  }
}

function Total({ isin, totals }: { isin: string; totals: Totals }) {
  const entry = totals?.get(isin);
  return entry ? <TotalBadge total={entry.total} grade={entry.grade} size="mini" /> : null;
}

/* ------------------------------------------------------------------ 1. Häufigkeit */

/** Zählung mit Rang: innerhalb der Liste „Rang n“, darüber grau „Rang n“ (außerhalb der Top N), ohne Nennung „–“. */
function FreqCount({ value, rank, place, valid, label, size }: { value: number; rank: number | null; place: number | null; valid: number; label: string; size: number }) {
  const share = valid > 0 ? Math.min(1, value / valid) : 0;
  const spoken = rank ? `, Rang ${rank}` : place ? `, Rang ${place}, außerhalb der Top ${size}` : ', kein Rang';
  return (
    <span className="dq-count" aria-label={`${label}: ${value}${spoken}`}>
      <b aria-hidden="true">{f.integer(value)}</b>
      <small aria-hidden="true" className={rank ? undefined : 'is-outside'}>
        {rank ? `Rang ${rank}` : place ? `Rang ${place}` : '–'}
      </small>
      <span className="dq-pulse" aria-hidden="true">
        <span style={{ width: `${Math.round(share * 100)}%` }} />
      </span>
    </span>
  );
}

function QuickOverview({
  lists,
  selection,
  choice,
  range,
  filter,
  sortTop,
  instruments,
  manifest,
  totals,
  selected,
  onToggle,
  onRoute,
  frequency,
}: {
  lists: TopLists;
  selection: FrequencySelection;
  choice: WeightChoice;
  range: 30 | 90;
  filter: ListFilter;
  sortTop: boolean;
  instruments: Instruments;
  manifest: Manifest;
  totals: Totals;
  selected: Set<string>;
  onToggle: (isin: string) => void;
  onRoute: (changes: Record<string, string | number | null>) => void;
  frequency: FrequencyData;
}) {
  const [copied, setCopied] = useState<string | null>(null);
  const n = lists.size;
  const base = filter === 'erste' ? lists.firsts : filter === 'top10' ? lists.tops : filter === 'beide' ? lists.both : lists.union;
  const rows = [...base].sort(sortTop ? byTops : byWins);
  const firstWin = lists.firsts[0];
  const firstTop = lists.tops[0];
  const winners = lists.rows.filter((r) => r.n1 > 0).length;
  const description = `${selection.text} · A und B · ${f.integer(lists.valid)} gültige von ${f.integer(lists.possible)} Ranglisten`;
  const summaryText = () =>
    `TR-Aktienvergleich · Kursstand ${f.day(manifest.cutoff_day)}\n${description} · Top ${n}\n\n` +
    rows.map((r) => `${instName(instruments, r.idx)} | ${r.isin} | ${r.n1} erste Plätze | ${r.n10} Top-10-Nennungen${r.both ? ` | in beiden Top ${n}` : ''}`).join('\n') +
    '\n\nHistorische Häufigkeit, keine Gewinnwahrscheinlichkeit.';
  const download = () => {
    const csv = toCsv(
      [
        ['Inhalt', `Häufigste Aktien: Top ${n} nach ersten Plätzen und Top ${n} nach Top-10-Nennungen`],
        ['Auswahl', description],
        ['Kursstichtag', manifest.cutoff_session_date],
        ['Snapshot', manifest.snapshot_id],
      ],
      ['Unternehmen', 'ISIN', 'Erste Plätze', 'Rang erste Plätze', 'Top 3', 'Top-10-Nennungen', 'Rang Top-10-Nennungen', `In beiden Top ${n}`, 'Auswertbare Ranglisten'],
      rows.map((r) => [instName(instruments, r.idx), r.isin, r.n1, r.place1, r.n3, r.n10, r.place10, r.both ? 'ja' : 'nein', r.available]),
    );
    downloadText(safeFilename(`haeufigkeit_${typeof choice === 'number' ? `g${choice}` : choice}_${range}_top${n}_${manifest.snapshot_id}.csv`), csv);
  };
  return (
    <section className="section dq-section" id="depots-haeufig" aria-labelledby="depots-haeufig-titel">
      <SectionTitle id="depots-haeufig-titel">Welche Aktien erscheinen am häufigsten?</SectionTitle>
      <p className="section-note">
        Gezählt wird, wie oft eine Aktie in den Ranglisten auf <strong>Platz 1</strong> stand („erste Plätze“) und wie oft unter den <strong>ersten zehn</strong> („Top-10-Nennungen“). Grün:
        in beiden Top-{n}-Listen. Die zwei Zahlen werden nicht addiert.
      </p>
      <label className="field">
        <span className="field-label">Gewichtungen (Gleichmäßigkeit/Rendite)</span>
        <select
          className="select"
          value={String(choice)}
          onChange={(e: Event) => {
            const value = (e.target as HTMLSelectElement).value;
            onRoute({ gw: value === STANDARD_CHOICE ? null : value, auswahl: null });
          }}
        >
          <option value="kurz">{WEIGHT_CHOICE_LABEL.kurz}</option>
          <option value="alle">{WEIGHT_CHOICE_LABEL.alle}</option>
          <option value="bericht">{WEIGHT_CHOICE_LABEL.bericht}</option>
          {WEIGHTS.map((w) => (
            <option key={w} value={String(w)}>
              {weightChoiceLabel(w)}
            </option>
          ))}
        </select>
      </label>
      <div className="dq-row">
        <Segmented
          label="Zeitraum"
          options={[
            { value: '30', label: '1–30 Tage' },
            { value: '90', label: '1–90 Tage' },
          ]}
          value={String(range)}
          onChange={(value) => onRoute({ zr: value === '30' ? null : value, auswahl: null })}
        />
        <Segmented
          label="Listenlänge"
          options={LIST_SIZES.map((size) => ({ value: String(size), label: `Top ${size}` }))}
          value={String(n)}
          onChange={(value) => onRoute({ n: Number(value) === DEFAULT_LIST_SIZE ? null : value })}
        />
      </div>
      <p className="section-note">{description}</p>
      <dl className="dq-kpis">
        <div>
          <dt>Häufigste erste Plätze</dt>
          <dd>
            <b>{firstWin ? f.integer(firstWin.n1) : '–'}</b>
            <span>{firstWin ? instName(instruments, firstWin.idx) : 'keine Rangliste'}</span>
          </dd>
        </div>
        <div>
          <dt>Häufigste Top-10-Nennungen</dt>
          <dd>
            <b>{firstTop ? f.integer(firstTop.n10) : '–'}</b>
            <span>{firstTop ? instName(instruments, firstTop.idx) : 'keine Rangliste'}</span>
          </dd>
        </div>
        <div>
          <dt>Beide Listen zusammen</dt>
          <dd>
            <b>{f.integer(lists.union.length)}</b>
            <span>Aktien, {f.integer(lists.both.length)} gemeinsam</span>
          </dd>
        </div>
      </dl>
      <Segmented
        label="Liste"
        options={[
          { value: 'union', label: `Beide Top ${n}` },
          { value: 'beide', label: 'Nur gemeinsame' },
          { value: 'erste', label: 'Erste Plätze' },
          { value: 'top10', label: 'Top-10-Nennungen' },
        ]}
        value={filter}
        onChange={(value) => onRoute({ liste: value === 'union' ? null : value, hsort: value === 'top10' ? 'n10' : null })}
      />
      <Segmented
        label="Sortierung"
        options={[
          { value: 'n1', label: 'Meiste erste Plätze' },
          { value: 'n10', label: 'Meiste Top-10-Nennungen' },
        ]}
        value={sortTop ? 'n10' : 'n1'}
        onChange={(value) => onRoute({ hsort: value === 'n10' ? 'n10' : null })}
      />
      {rows.length ? (
        <>
          <p className="dq-head" aria-hidden="true">
            <span>Aktie</span>
            <span>Erste Plätze</span>
            <span>Top 10</span>
          </p>
          <ul className="dq-list">
            {rows.map((r) => {
              const checked = selected.has(r.isin);
              return (
                <li key={r.isin} className={`${r.both ? 'is-both' : ''}${checked ? ' is-picked' : ''}`}>
                  <label className="dq-pick">
                    <input type="checkbox" checked={checked} onChange={() => onToggle(r.isin)} aria-label={`${instName(instruments, r.idx)} für ein eigenes Depot auswählen`} />
                  </label>
                  <span className="dq-name">
                    <span>
                      <a href={buildHash(`/aktie/${r.isin}`, { tab: 'rendite', h: 30 })}>{instName(instruments, r.idx)}</a>
                      <Total isin={r.isin} totals={totals} />
                    </span>
                    <small>
                      <span translate="no">{r.isin}</span> · in {f.integer(r.available)} Ranglisten auswertbar
                    </small>
                    {r.both ? <span className="dq-both">In beiden Top {n}</span> : null}
                  </span>
                  <FreqCount value={r.n1} rank={r.rank1} place={r.place1} valid={lists.valid} label="Erste Plätze" size={n} />
                  <FreqCount value={r.n10} rank={r.rank10} place={r.place10} valid={lists.valid} label="Top-10-Nennungen" size={n} />
                </li>
              );
            })}
          </ul>
        </>
      ) : (
        <Notice tone="info" title="Keine Rangliste in dieser Auswahl">
          <p>Für die Gleichmäßigkeit sind mindestens 15 echte Schlusskurse nötig – kurze Zeiträume bleiben dort leer.</p>
        </Notice>
      )}
      <p className="section-note">
        Die Listen zeigen je {n} Aktien. {f.plural(winners, 'Aktie hat', 'Aktien haben')} in dieser Auswahl mindestens einen ersten Platz; bei gleich vielen Siegen entscheiden Top-3-, dann
        Top-10-Nennungen und ISIN. Ein grauer Rang liegt außerhalb der Top {n}. Häufigkeit ist keine Gewinnwahrscheinlichkeit und keine Kaufempfehlung.
      </p>
      <div className="toolbar no-print">
        <button
          type="button"
          className="btn"
          onClick={async () => {
            const ok = await copyText(summaryText());
            setCopied(ok ? 'Kurzfassung kopiert.' : 'Kopieren ist in diesem Browser nicht möglich – bitte „Tabelle herunterladen“ verwenden.');
          }}
        >
          Kurzfassung kopieren
        </button>
        {!PREVIEW ? (
          <button type="button" className="btn" onClick={download}>
            <IconDownload /> Tabelle herunterladen
          </button>
        ) : null}
        <a className="btn btn-quiet" href={buildHash('/haeufig', { von: 1, bis: range, gruppen: 'ab' })}>
          Alle Filter
        </a>
      </div>
      <p className="section-note" role="status">
        {copied ?? ''}
      </p>
      <FrequencyExplained frequency={frequency} instruments={instruments} range={range} size={n} />
    </section>
  );
}

/** Drei Erklärblöcke wie in der Datei „Zwei Zehnerdepots“ (v3); gerechnet erst beim Aufklappen. */
function FrequencyExplained({ frequency, instruments, range, size }: { frequency: FrequencyData; instruments: Instruments; range: 30 | 90; size: number }) {
  return (
    <div className="dq-explain">
      <Disclosure summary="Welche Aktie gewinnt bei welcher Gewichtung am häufigsten?">
        <WinnersByWeight frequency={frequency} instruments={instruments} range={range} />
      </Disclosure>
      <Disclosure summary="Wie werden 0/100 bis 100/0 berechnet? Mit echtem 30-Tage-Beispiel">
        <ScoreExample />
      </Disclosure>
      <Disclosure summary="Was ändert sich mit allen elf Gewichtungen?">
        <WeightShiftTable frequency={frequency} instruments={instruments} size={size} />
      </Disclosure>
    </div>
  );
}

function StockCell({ instruments, idx, isin }: { instruments: Instruments; idx: number; isin: string }) {
  return (
    <>
      <a href={buildHash(`/aktie/${isin}`, { tab: 'rendite', h: 30 })}>{instName(instruments, idx)}</a>
      <br />
      <small className="muted" translate="no">
        {isin}
      </small>
    </>
  );
}

function WinnersByWeight({ frequency, instruments, range }: { frequency: FrequencyData; instruments: Instruments; range: 30 | 90 }) {
  const rows = useMemo(() => winnersByWeight(frequency, instruments, range), [frequency, instruments, range]);
  const pure = rows.find((r) => r.weight === 0);
  const mixed = rows.find((r) => r.weight === 50);
  return (
    <>
      <p className="section-note">
        Häufigste erste Plätze über 1–{range} Kalendertage, Gruppe A und B. 0/100 ist in {f.integer(pure?.valid ?? 0)} Ranglisten berechenbar, jede andere Gewichtung nur in{' '}
        {f.integer(mixed?.valid ?? 0)}, weil die Gleichmäßigkeit mindestens 15 echte Schlusskurse braucht. Der Nenner steht deshalb immer daneben.
      </p>
      <div className="table-wrap">
        <table className="table dq-weights">
          <thead>
            <tr>
              <th scope="col">G/R</th>
              <th scope="col">Häufigster Sieger</th>
              <th scope="col" className="n">
                Siege /<br />
                Ranglisten
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.weight}>
                <th scope="row">{f.weightShort(r.weight)}</th>
                <td>{r.row ? <StockCell instruments={instruments} idx={r.row.idx} isin={r.row.isin} /> : <span className="muted">keine Rangliste</span>}</td>
                <td className="n">
                  {f.integer(r.row?.n1 ?? 0)} / {f.integer(r.valid)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function ScoreExample() {
  const { instruments } = useApp();
  const head = useWindowHead(30);
  if (head.error) return <ErrorNote error={head.error} />;
  if (!head.data || !instruments) return <Loading height={160} label="Beispiel wird geladen" />;
  const win = head.data;
  const groupB = hasGroupB(win);
  const group = groupB ? 'b' : 'a';
  const rows = WEIGHTS.map((w) => ({ w, entry: rankedEntries(win, 'native', w, 0, 1, group)[0] ?? null }));
  return (
    <>
      <p>
        <strong>Kursrendite</strong> = 100 × (Endkurs ÷ Startkurs − 1). <strong>Gleichmäßigkeit</strong> = R² einer Geraden durch die täglichen Schlusskurse (1 = perfekt gleichmäßig). Beide
        werden innerhalb derselben Gruppe und desselben Zeitraums in <strong>Rangwerte 0–100</strong> umgerechnet: Rangwert = 100 × (mittlerer Rang − 1) ÷ (Anzahl − 1).
      </p>
      <p>
        <strong>Score = G/100 × Gleichmäßigkeits-Rangwert + (100 − G)/100 × Rendite-Rangwert.</strong> 0/100 sortiert nur nach Rendite, 100/0 nur nach Gleichmäßigkeit; ab 10/90 zählen nur
        Aktien mit steigender Gerade und positiver Rendite. Bei gleichem Score entscheiden die höhere Rendite, dann die ISIN.
      </p>
      <p className="section-note">
        Echtes Beispiel: <strong>30 Kalendertage, Gruppe {groupB ? 'B (Ø Tagesumsatz ab 10 Mio. USD)' : 'A'}</strong>, Kursstand {f.day(win.cutoff_day)} – der Sieger jeder Gewichtung.
      </p>
      <div className="table-wrap">
        <table className="table dq-weights">
          <thead>
            <tr>
              <th scope="col">G/R</th>
              <th scope="col">Sieger</th>
              <th scope="col" className="n">
                Score
                <br />
                <span className="muted">Rendite · R²</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ w, entry }) => (
              <tr key={w}>
                <th scope="row">{f.weightShort(w)}</th>
                <td>{entry ? <StockCell instruments={instruments} idx={entry.idx} isin={instruments.isin[entry.idx]} /> : <span className="muted">keine Rangliste</span>}</td>
                <td className="n">
                  {entry ? (
                    <>
                      {SCORE_2.format(entry.score)}
                      <br />
                      <small>
                        <Pct value={entry.r} digits={1} /> · {entry.r2 === null ? '–' : f.r2(entry.r2)}
                      </small>
                    </>
                  ) : (
                    '–'
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="section-note">Score, R² und Häufigkeit sind keine Gewinnwahrscheinlichkeit.</p>
    </>
  );
}

function WeightShiftTable({ frequency, instruments, size }: { frequency: FrequencyData; instruments: Instruments; size: number }) {
  const data = useMemo(() => weightShift(frequency, instruments, size), [frequency, instruments, size]);
  return (
    <>
      <p className="section-note">
        Gleicher Kursstand, gleiche Zeiträume 1–30 Tage und Gruppen. Statt der Standardauswahl 40/60, 50/50, 60/40 zählen ausführlich alle elf Gewichtungen: Die Zahl gültiger
        Ranglisten steigt von <strong>{f.integer(data.validBefore)}</strong> auf <strong>{f.integer(data.validAfter)}</strong> – höhere Zählungen allein bedeuten deshalb keine bessere
        Kursentwicklung. Gezeigt: die Top {size} der Top-10-Nennungen mit allen elf Gewichtungen.
      </p>
      <div className="table-wrap">
        <table className="table dq-weights">
          <thead>
            <tr>
              <th scope="col">Mit 11</th>
              <th scope="col">Aktie</th>
              <th scope="col" className="n">
                Rang
                <br />
                Standard → 11
              </th>
              <th scope="col" className="n">
                Top 10
                <br />
                Standard → 11
              </th>
            </tr>
          </thead>
          <tbody>
            {data.shifts.map((s) => (
              <tr key={s.row.isin}>
                <th scope="row">{s.after}</th>
                <td>
                  <StockCell instruments={instruments} idx={s.row.idx} isin={s.row.isin} />
                </td>
                <td className="n">
                  {s.before ?? '–'} → {s.after}
                </td>
                <td className="n">
                  {f.integer(s.n10Before)} → {f.integer(s.row.n10)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="section-note">Zeiträume, Gewichtungen und Gruppen überschneiden sich; die Zählung ist keine Abstimmung unabhängiger Signale.</p>
    </>
  );
}

/* ------------------------------------------------------------------ 2. Depot */

function PositionRow({ p, rank, max, instruments, isinIndex, totals, unit, basis }: { p: DepotPosition; rank: number; max: number; instruments: Instruments; isinIndex: Map<string, number>; totals: Totals; unit: string; basis: DepotBasis }) {
  const idx = isinIndex.get(p.isin) ?? -1;
  const name = idx >= 0 ? instName(instruments, idx) : p.isin;
  const widthPct = max > 0 ? Math.round((Math.abs(p.contribution) / max) * 100) : 0;
  const negative = p.contribution < 0;
  const notes = [...p.flags, ...p.warnings];
  return (
    <li className="dp-row">
      <span className="dp-rank">{rank}</span>
      <div className="dp-main">
        <span className="dp-name">
          <a href={buildHash(`/aktie/${p.isin}`, { tab: 'rendite', h: DEPOT_DAYS })}>{name}</a>
          {notes.length ? <span className="dp-dagger" aria-label="mit Hinweis">†</span> : null}
          <Total isin={p.isin} totals={totals} />
        </span>
        <small translate="no">{p.isin}</small>
        <span className="dp-bar" aria-hidden="true">
          <span className={negative ? 'is-neg' : 'is-pos'} style={{ width: `${widthPct}%` }} />
        </span>
        <span className="dp-figs">
          Aktie <Pct value={p.ret} /> · Start {weight(p.w0)} → Ende {weight(p.w1)} · Endwert {f.price(p.endValue, unit)}
        </span>
        <span className="dp-price">
          {f.dayShort(p.startDay)}: {f.price(p.startClose, p.currency)} → {f.dayShort(p.endDay)}: {f.price(p.endClose, p.currency)}
          {basis !== 'lokal' && p.currency && p.currency !== unit && p.fxStart && p.fxEnd ? ` · ${unit} je ${p.currency} ${FX_FORMAT.format(p.fxStart.value)} → ${FX_FORMAT.format(p.fxEnd.value)}` : ''}
        </span>
        {notes.length ? <span className="dp-notes">† {notes.join(' · ')}</span> : null}
      </div>
      <b className={`dp-pp ${negative ? 'is-neg' : 'is-pos'}`}>{pp(p.contribution)}</b>
    </li>
  );
}

function DepotDetail({
  depot,
  result,
  sort,
  instruments,
  isinIndex,
  manifest,
  totals,
  basis,
  onRoute,
}: {
  depot: DepotDef;
  result: DepotResult;
  sort: ContributionSort;
  instruments: Instruments;
  isinIndex: Map<string, number>;
  manifest: Manifest;
  totals: Totals;
  basis: DepotBasis;
  onRoute: (changes: Record<string, string | number | null>) => void;
}) {
  const unit = basis === 'usd' ? 'USD' : basis === 'eur' ? 'EUR' : '';
  const nameOf = (isin: string) => {
    const idx = isinIndex.get(isin) ?? -1;
    return idx >= 0 ? instName(instruments, idx) : isin;
  };
  const sorted = sortPositions(result.positions, sort, nameOf);
  const max = Math.max(0, ...result.positions.map((p) => Math.abs(p.contribution)));
  const leader = [...result.positions].sort((a, b) => b.contribution - a.contribution)[0];
  const download = () => {
    const csv = toCsv(
      [
        ['Inhalt', `Musterdepot „${depot.name}“: Beitrag jeder Aktie`],
        ['Zeitraum', `${result.h} Kalendertage bis ${f.day(manifest.cutoff_day)} (gewünschter Start ${f.day(result.targetDay)})`],
        ['Basis', basis === 'lokal' ? 'Originalwährung je Aktie (ohne Umrechnung)' : `${unit}, Euro-Referenzkurse`],
        ['Startkapital', `${result.capital} ${unit}`.trim()],
        ['Depotrendite', result.ret === null ? 'nicht berechenbar' : f.pct(result.ret)],
        ['Snapshot', manifest.snapshot_id],
      ],
      ['Unternehmen', 'ISIN', 'Aktienrendite', 'Beitrag PP', 'Startgewicht %', 'Endgewicht %', 'Endwert', 'Starttag', 'Startkurs', 'Endtag', 'Endkurs', 'Währung', 'Hinweise'],
      [
        ...sorted.map((p) => [
          nameOf(p.isin),
          p.isin,
          p.ret,
          p.contribution * 100,
          p.w0 * 100,
          p.w1 * 100,
          p.endValue,
          f.day(p.startDay),
          p.startClose,
          f.day(p.endDay),
          p.endClose,
          p.currency,
          [...p.flags, ...p.warnings].join('; ') || null,
        ]),
        ...result.missing.map((m) => [nameOf(m.isin), m.isin, null, null, null, null, null, null, null, null, null, null, `nicht im Depot: ${m.reason}`]),
      ],
      [undefined, undefined, 6, 4, 2, 2, 2],
    );
    downloadText(safeFilename(`depot_${depot.key}_${result.h}T_${manifest.snapshot_id}.csv`), csv);
  };
  return (
    <>
      <p className="section-note">
        {result.h} Kalendertage · gewünschter Start {f.day(result.targetDay)} · Ende {f.day(manifest.cutoff_day)} · {f.integer(result.positions.length)}{' '}
        {result.positions.length === 1 ? 'Position' : 'Positionen'} zu je {result.positions.length ? weight(result.positions[0].w0) : '–'} Startgewicht
      </p>
      {sorted.length ? (
        <dl className="dp-kpis">
          <div className="dp-kpi-main">
            <dt>Depotrendite</dt>
            <dd>
              <Pct value={result.ret} strong />
              {result.flagged ? <span className="dp-dagger" aria-label="mit Hinweis">†</span> : null}
            </dd>
            <dd className="dp-kpi-note">Summe der Beiträge</dd>
          </div>
          <div>
            <dt>Endwert aus {f.price(result.capital, unit)}</dt>
            <dd>
              <b>{f.price(result.endValue, unit)}</b>
            </dd>
            <dd className="dp-kpi-note">ohne Kosten und Dividenden</dd>
          </div>
          <div>
            <dt>Größter Beitrag</dt>
            <dd>
              <b>{leader ? pp(leader.contribution) : '–'}</b>
            </dd>
            <dd className="dp-kpi-note">{leader ? nameOf(leader.isin) : '–'}</dd>
          </div>
        </dl>
      ) : null}
      {sorted.length ? (
        <>
          <Segmented
            label="Sortieren nach"
            options={[
              { value: 'beitrag', label: 'Beitrag' },
              { value: 'rendite', label: 'Aktienrendite' },
              { value: 'name', label: 'A–Z' },
            ]}
            value={sort}
            onChange={(value) => onRoute({ bsort: value === 'beitrag' ? null : value })}
          />
          <p className="section-note">
            PP = Prozentpunkte der Depotrendite. Bei {weight(result.positions[0].w0)} Startgewicht trägt ein Aktienplus von 50 % genau {pp(result.positions[0].w0 * 0.5)} bei. Die Balken zeigen
            Betrag und Vorzeichen, keine Wahrscheinlichkeit.
          </p>
        </>
      ) : null}
      {sorted.length ? (
        <ol className="dp-list" aria-label={`Beitrag zum Depot ${depot.name}`}>
          {sorted.map((p, k) => (
            <PositionRow key={p.isin} p={p} rank={k + 1} max={max} instruments={instruments} isinIndex={isinIndex} totals={totals} unit={unit} basis={basis} />
          ))}
        </ol>
      ) : (
        <Notice tone="info" title="Keine Aktie dieses Depots hat Kurse für diesen Zeitraum">
          <p>Die Gründe stehen unten je Aktie. Eigene Depots lassen sich mit „bearbeiten“ ändern.</p>
        </Notice>
      )}
      {sorted.length ? (
        <p className="dp-total">
          <span>Depot gesamt</span>
          <b className={(result.ret ?? 0) < 0 ? 'is-neg' : 'is-pos'}>{pp(result.ret)}</b>
          <span>
            {weight(1)} → {weight(1)} · {f.price(result.endValue, unit)}
          </span>
        </p>
      ) : null}
      {result.missing.length ? (
        <p className="section-note dp-missing">
          Nicht im Depot für diesen Zeitraum (Gewichte auf die übrigen verteilt): {result.missing.map((m) => `${nameOf(m.isin)} – ${m.reason}`).join('; ')}.
        </p>
      ) : null}
      {result.flagged ? <p className="section-note">† Hinweis zu Umsatz oder Kurs – die Rechnung belegt keine damalige Ausführbarkeit.</p> : null}
      <div className="toolbar no-print">
        {!PREVIEW ? (
          <button type="button" className="btn" onClick={download}>
            <IconDownload /> Depot herunterladen
          </button>
        ) : null}
        <a className="btn" href={buildHash('/raster', { quelle: 'isins', isins: depot.isins.join(','), titel: depot.name, h: result.h, modus: 'kacheln' })}>
          Diese Aktien im Kursraster
        </a>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ 3. Alle Depots 1–30 */

function HorizonChart({ rows, depots, activeH, onPick }: { rows: DepotWindowRow[]; depots: DepotDef[]; activeH: number; onPick: (h: number) => void }) {
  const dark = useDark();
  const shown = depots.slice(0, MAX_SERIES);
  const [readH, setReadH] = useState<number | null>(null);
  const W = 360;
  const Hh = 200;
  const m = { l: 44, r: 10, t: 12, b: 26 };
  const values = rows.flatMap((r) => r.values.slice(0, shown.length).map((v) => v.ret)).filter((v): v is number => v !== null && Number.isFinite(v));
  if (!values.length) return <p className="section-note">Keine berechenbaren Fenster.</p>;
  // Runde Achsenschritte (z. B. 0, 10, 20, 30, 40 %) mit der Nulllinie; die Achse umfasst alle Werte
  const scale = scaleLinear()
    .domain([Math.min(0, ...values), Math.max(0, ...values, Math.min(0, ...values) + 0.01)])
    .nice(4);
  const [lo, hi] = scale.domain() as [number, number];
  const ticks = scale.ticks(4);
  const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) * 100 : 1;
  const tickDigits = step >= 1 ? 0 : step >= 0.1 ? 1 : 2;
  const x = (h: number) => m.l + ((h - 1) / (DEPOT_DAYS - 1)) * (W - m.l - m.r);
  const y = (v: number) => m.t + (1 - (v - lo) / (hi - lo)) * (Hh - m.t - m.b);
  const shownH = readH ?? activeH;
  const row = rows.find((r) => r.h === shownH);
  const pick = (event: PointerEvent | MouseEvent, commit: boolean) => {
    const svg = event.currentTarget as SVGSVGElement;
    const box = svg.getBoundingClientRect();
    const px = ((event.clientX - box.left) / box.width) * W;
    const h = Math.min(DEPOT_DAYS, Math.max(1, Math.round(1 + ((px - m.l) / (W - m.l - m.r)) * (DEPOT_DAYS - 1))));
    setReadH(h);
    if (commit) onPick(h);
  };
  return (
    <figure className="hz-chart">
      <svg
        viewBox={`0 0 ${W} ${Hh}`}
        role="img"
        aria-label="Depotrendite je Rückblickfenster 1 bis 30 Kalendertage, eine Linie je Depot"
        onPointerMove={(e: PointerEvent) => pick(e, false)}
        onPointerLeave={() => setReadH(null)}
        onClick={(e: MouseEvent) => pick(e, true)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.l} x2={W - m.r} y1={y(t)} y2={y(t)} className="hz-grid" />
            <text x={m.l - 6} y={y(t) + 4} textAnchor="end" className="hz-tick">
              {f.signedPctValue(t * 100, tickDigits)}
            </text>
          </g>
        ))}
        <line x1={m.l} x2={W - m.r} y1={y(0)} y2={y(0)} className="hz-zero" />
        {[1, 7, 14, 21, 30].map((h) => (
          <text key={h} x={x(h)} y={Hh - 8} textAnchor="middle" className="hz-tick">
            {h}
          </text>
        ))}
        <line x1={x(shownH)} x2={x(shownH)} y1={m.t} y2={Hh - m.b} className="hz-cross" />
        {shown.map((depot, k) => {
          const pts = rows
            .map((r) => ({ h: r.h, v: r.values[k]?.ret }))
            .filter((p): p is { h: number; v: number } => p.v !== null && p.v !== undefined && Number.isFinite(p.v));
          const path = pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.h).toFixed(1)},${y(p.v).toFixed(1)}`).join('');
          const color = seriesColor(k, dark);
          const at = pts.find((p) => p.h === shownH);
          return (
            <g key={depot.key}>
              <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
              {at ? <circle cx={x(at.h)} cy={y(at.v)} r={4} fill={color} className="hz-dot" /> : null}
            </g>
          );
        })}
      </svg>
      <figcaption>
        <span className="hz-read">
          {row ? (
            <>
              <b>{f.windowLabel(row.h)}</b> (Start {f.dayShort(row.anchorDay)}):{' '}
              {shown.map((depot, k) => `${depot.name} ${f.pct(row.values[k]?.ret ?? null, 1)}`).join(' · ')}
            </>
          ) : null}
        </span>
        <span className="hz-legend">
          {shown.map((depot, k) => (
            <span key={depot.key}>
              <i style={{ background: seriesColor(k, dark) }} aria-hidden="true" />
              {depot.name}
            </span>
          ))}
        </span>
      </figcaption>
    </figure>
  );
}

function AllDepots({ rows, depots, activeH, activeKey, onRoute }: { rows: DepotWindowRow[]; depots: DepotDef[]; activeH: number; activeKey: string; onRoute: (changes: Record<string, string | number | null>) => void }) {
  return (
    <section className="section" id="depots-alle" aria-labelledby="depots-alle-titel">
      <SectionTitle id="depots-alle-titel">{`Alle Depots · 1–${DEPOT_DAYS} Tage`}</SectionTitle>
      <p className="section-note">
        Grafik = Depotrendite für 30 getrennte Rückblickfenster, <strong>kein</strong> fortlaufender Depotverlauf. Alle Fenster enden am Kursstichtag; die Starttage unterscheiden sich. Antippen wählt
        den Zeitraum.
      </p>
      <HorizonChart rows={rows} depots={depots} activeH={activeH} onPick={(h) => onRoute({ t: h === DEPOT_DAYS ? null : h })} />
      <div className="table-wrap">
        <table className="table hz-table">
          <thead>
            <tr>
              <th scope="col" className="sticky">
                Tage / Start
              </th>
              {depots.map((d) => (
                <th scope="col" key={d.key} className={`n${d.key === activeKey ? ' is-active' : ''}`}>
                  {d.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.h} className={r.h === activeH ? 'is-active' : undefined} aria-current={r.h === activeH ? 'true' : undefined}>
                <th scope="row" className="sticky">
                  <button type="button" className="table-pick" onClick={() => onRoute({ t: r.h === DEPOT_DAYS ? null : r.h })}>
                    {r.h === 1 ? '1 Tag' : `${r.h} Tage`}
                    <small>{f.dayShort(r.anchorDay)}</small>
                  </button>
                </th>
                {r.values.map((v) => (
                  <td key={v.key} className="n">
                    <Pct value={v.ret} digits={1} />
                    {v.flagged ? ' †' : ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ Eigene Depots bearbeiten */

function DepotEditor({ initial, index, onSave, onDelete, onCancel, instruments, isinIndex }: { initial: { name: string; isins: string[] }; index: number | null; onSave: (name: string, isins: string[]) => void; onDelete: (() => void) | null; onCancel: () => void; instruments: Instruments; isinIndex: Map<string, number> }) {
  const [name, setName] = useState(initial.name);
  const [text, setText] = useState(initial.isins.join(', '));
  const parsed = parseIsinImport(text);
  const unknown = parsed.valid.filter((isin) => !isinIndex.has(isin));
  const tooMany = parsed.valid.length > MAX_DEPOT_MEMBERS;
  const ok = name.trim().length > 0 && parsed.valid.length > 0 && !tooMany;
  return (
    <section className="dp-editor" aria-label={index === null ? 'Neues Depot' : `Depot ${initial.name} bearbeiten`}>
      <label className="field">
        <span className="field-label">Name</span>
        <input className="input" type="text" maxLength={40} value={name} onInput={(e: Event) => setName((e.target as HTMLInputElement).value)} />
      </label>
      <label className="field">
        <span className="field-label">ISINs (durch Komma, Leerzeichen oder Zeilen getrennt, höchstens {MAX_DEPOT_MEMBERS})</span>
        <textarea className="input" rows={4} value={text} onInput={(e: Event) => setText((e.target as HTMLTextAreaElement).value)} spellCheck={false} />
      </label>
      <p className="section-note">
        {parsed.valid.length ? `${f.integer(parsed.valid.length)} gültige ISINs: ${parsed.valid.map((isin) => (isinIndex.has(isin) ? instName(instruments, isinIndex.get(isin)!) : isin)).join(', ')}.` : 'Noch keine gültige ISIN.'}
        {parsed.invalid.length ? ` Ungültig (Prüfziffer): ${parsed.invalid.join(', ')}.` : ''}
        {unknown.length ? ` Nicht im Datenstand: ${unknown.join(', ')}.` : ''}
        {tooMany ? ` Höchstens ${MAX_DEPOT_MEMBERS} Aktien je Depot.` : ''}
      </p>
      <div className="toolbar">
        <button type="button" className="btn btn-primary" disabled={!ok} onClick={() => onSave(name.trim(), parsed.valid)}>
          Depot speichern
        </button>
        <button type="button" className="btn btn-quiet" onClick={onCancel}>
          Abbrechen
        </button>
        {onDelete ? (
          <button type="button" className="btn btn-quiet" onClick={onDelete}>
            Depot löschen
          </button>
        ) : null}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ Ansicht */

export function DepotsView({ route }: { route: Route }) {
  const { manifest, instruments, isinIndex, prefs, setPrefs } = useApp();
  const frequency = useFrequency();
  const fxState = useFx();
  const signals = useSignals();
  const totals = useMemo(() => totalsByIsin(signals.data), [signals.data]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [newName, setNewName] = useState('');

  const { choice, range } = parseSelection(route.params);
  const size = parseSize(route.params.get('n'));
  const filter = parseFilter(route.params.get('liste'));
  const sortTop = route.params.get('hsort') === 'n10';
  const h = parseDays(route.params.get('t'));
  const sort = parseSort(route.params.get('bsort'));
  const editing = route.params.get('bearbeiten');
  const basisWanted: DepotBasis = prefs.depotBasis;
  const fxReady = Boolean(manifest?.fx);
  const basis: DepotBasis = basisWanted !== 'lokal' && !fxReady ? 'lokal' : basisWanted;
  const capital = prefs.depotCapital;

  // Die beiden Zehnerdepots: Top 10 der Standardauswahl 40/60, 50/50, 60/40 (ab 1.10), unabhängig von der Anzeige oben
  const reportLists = useMemo(() => {
    if (!frequency.data || !instruments) return null;
    try {
      return topLists(frequency.data, instruments, selectionFor(STANDARD_CHOICE), 'ab', DEPOT_SIZE);
    } catch {
      return null;
    }
  }, [frequency.data, instruments]);
  // Häufigkeit (ab 1.10): Standard alle elf Gewichtungen, 1–30 Tage, Top 20 – wie in der Datei „Zwei Zehnerdepots“ v3
  const selection = useMemo(() => selectionFor(choice, range), [choice, range]);
  const shownLists = useMemo(() => {
    if (!frequency.data || !instruments) return null;
    try {
      return topLists(frequency.data, instruments, selection, 'ab', size);
    } catch {
      return null;
    }
  }, [frequency.data, instruments, selection, size]);

  const depots: DepotDef[] = useMemo(() => [...(reportLists ? reportDepots(reportLists) : []), ...ownDepotDefs(prefs.depots)], [reportLists, prefs.depots]);
  // Nur Kursreihen laden, die es im Datenstand gibt (eigene Depots können ISINs ohne Kursreihe enthalten)
  const allIsins = useMemo(() => {
    if (!instruments) return [];
    return [...new Set(depots.flatMap((d) => d.isins))].filter((isin) => {
      const idx = isinIndex.get(isin);
      return idx !== undefined && Boolean(instruments.has_series?.[idx]);
    }).sort();
  }, [depots, instruments, isinIndex]);
  const many = useSeriesMany(allIsins);
  const fx = useMemo(() => (fxState.data ? fxLookup(fxState.data) : null), [fxState.data]);
  const fxPending = basis !== 'lokal' && !fx && !fxState.error;

  if (!manifest || !instruments) return null;
  const set = (changes: Record<string, string | number | null>) => updateParams(route, changes);
  const depotKey = route.params.get('depot') ?? 'siege';
  const depot = depots.find((d) => d.key === depotKey) ?? depots[0] ?? null;
  const warningsFor = (isin: string): string[] => {
    const idx = isinIndex.get(isin) ?? -1;
    const info = idx >= 0 ? turnoverOf(instruments, idx) : null;
    return info && isVeryLow(info, manifest) ? [`sehr geringer Ø Tagesumsatz (unter ${f.money(veryLowUsd(manifest), 'USD')})`] : [];
  };
  const seriesReady = many.pending === 0;
  const ready = seriesReady && !fxPending;
  const result = depot && ready ? computeDepot(depot.isins, many.data, manifest.cutoff_day, h, basis, fx, capital, warningsFor) : null;
  const windowRows = ready && depots.length ? depotWindows(depots, many.data, manifest.cutoff_day, basis, fx, DEPOT_DAYS, warningsFor) : [];
  const intraday = isIntraday(manifest);
  // Kursvergleich (ab 1.10): Depot oder die Listen der Häufigkeit oben (gemeinsame, alle, Top N je Liste)
  const compareParam = route.params.get('vgl');
  const compareKind: CompareKind = compareParam === 'gemeinsam' || compareParam === 'alle' || compareParam === 'siege' || compareParam === 'nennungen' ? compareParam : 'depot';
  const listIsins = (rows: FreqRow[] | undefined) => (rows ?? []).map((r) => r.isin);
  const compareSource =
    compareKind === 'gemeinsam'
      ? listIsins(shownLists?.both)
      : compareKind === 'alle'
        ? listIsins(shownLists?.union)
        : compareKind === 'siege'
          ? listIsins(shownLists?.firsts)
          : compareKind === 'nennungen'
            ? listIsins(shownLists?.tops)
            : depot?.isins ?? [];
  const hasSeries = (isin: string) => {
    const idx = isinIndex.get(isin);
    return idx !== undefined && Boolean(instruments.has_series?.[idx]);
  };
  const compareIsins = compareSource.filter(hasSeries);
  const compareTitle =
    compareKind === 'depot'
      ? depot?.name ?? 'Depot'
      : compareKind === 'gemeinsam'
        ? `In beiden Top ${size}`
        : compareKind === 'alle'
          ? `Beide Top ${size}`
          : compareKind === 'siege'
            ? `Top ${size} · erste Plätze`
            : `Top ${size} · Top-10-Nennungen`;
  const ownIndex = depot && depot.kind === 'eigen' ? Number(depot.key.slice('eigen-'.length)) - 1 : null;

  const toggle = (isin: string) => {
    const next = new Set(selected);
    if (next.has(isin)) next.delete(isin);
    else next.add(isin);
    setSelected(next);
  };
  const saveNew = (name: string, isins: string[]) => {
    if (prefs.depots.length >= MAX_OWN_DEPOTS) return;
    const list = [...prefs.depots, { name, isins }];
    setPrefs({ depots: list });
    setSelected(new Set());
    setNewName('');
    set({ depot: `eigen-${list.length}`, bearbeiten: null });
  };

  return (
    <div className="view depots-view">
      <header className="view-head">
        <ViewIntro>
          <p className="lede">
            Musterdepots aus der Standardauswahl (40/60, 50/50, 60/40 · 1–30 Tage · Gruppe A und B): die zehn Aktien mit den meisten <strong>ersten Plätzen</strong> und die zehn mit den
            meisten <strong>Top-10-Nennungen</strong> – dazu deine eigenen Depots. Gleiche Startbeträge je Aktie, danach unveränderte Stückzahlen; jeder Zeitraum von 1 bis 30 Tagen ist eine
            eigene Rechnung.
          </p>
          <p className="section-note">
            {intraday
              ? `Zwischenstand vom ${f.dayLong(manifest.cutoff_day)}, Kurse bis ${berlinClock(manifest.zwischenstand?.kurse_bis_utc)} (vorläufig).`
              : `Kursstichtag ${f.dayLong(manifest.cutoff_day)}, Tagesschlusskurse.`}{' '}
            Gespeicherte Tagesdaten, kein Livekurs.
          </p>
        </ViewIntro>
      </header>
      <Notice tone="warn" title="Rückblickende Auswahl">
        <p>
          Die Aktien sind mit Kenntnis der späteren Gewinner ausgewählt – die Depotrendite zeigt, was diese Auswahl im Rückblick gebracht hätte, nicht was sie künftig bringt. Ohne Spread, Gebühren,
          Steuern und Dividenden; dünn gehandelte Werte (†) belegen keine damalige Ausführbarkeit. Keine Kaufempfehlung.
        </p>
      </Notice>

      <nav className="rep-jump" aria-label="Auf der Seite springen">
        {[
          { id: 'depots-haeufig', label: 'Häufigkeit' },
          { id: 'depots-depot', label: 'Depot' },
          { id: 'depots-alle', label: 'Alle Depots' },
          { id: 'depots-kurse', label: 'Kursvergleich' },
        ].map((s) => (
          <button
            key={s.id}
            type="button"
            className="chip"
            onClick={() => document.getElementById(s.id)?.scrollIntoView({ block: 'start', behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })}
          >
            {s.label}
          </button>
        ))}
      </nav>

      {frequency.error ? <ErrorNote error={frequency.error} /> : null}
      {!frequency.data && !frequency.error ? <Loading height={420} label="Häufigkeiten werden gezählt" /> : null}
      {shownLists && frequency.data ? (
        <QuickOverview
          lists={shownLists}
          selection={selection}
          choice={choice}
          range={range}
          frequency={frequency.data}
          filter={filter}
          sortTop={sortTop}
          instruments={instruments}
          manifest={manifest}
          totals={totals}
          selected={selected}
          onToggle={toggle}
          onRoute={set}
        />
      ) : null}

      {selected.size ? (
        <section className="dp-pickbar" aria-label="Auswahl für ein eigenes Depot">
          <p>
            <strong>{f.integer(selected.size)} ausgewählt</strong> für ein eigenes Depot
          </p>
          <div className="dp-pickbar-row">
            <input className="input" type="text" maxLength={40} placeholder="Name, z. B. Dreierdepot" value={newName} onInput={(e: Event) => setNewName((e.target as HTMLInputElement).value)} aria-label="Name des Depots" />
            <button type="button" className="btn btn-primary" disabled={!newName.trim() || prefs.depots.length >= MAX_OWN_DEPOTS} onClick={() => saveNew(newName.trim(), [...selected].slice(0, MAX_DEPOT_MEMBERS))}>
              Als Depot speichern
            </button>
            <button type="button" className="icon-btn" aria-label="Auswahl aufheben" onClick={() => setSelected(new Set())}>
              <IconClose />
            </button>
          </div>
          {prefs.depots.length >= MAX_OWN_DEPOTS ? <p className="section-note">Höchstens {MAX_OWN_DEPOTS} eigene Depots – bitte zuerst eines löschen.</p> : null}
        </section>
      ) : null}

      <section className="section dp-section" id="depots-depot" aria-labelledby="depots-depot-titel">
        <SectionTitle id="depots-depot-titel">Depotrendite und Beitrag jeder Aktie</SectionTitle>
        {depots.length ? (
          <Segmented label="Depot" options={depots.map((d) => ({ value: d.key, label: d.name }))} value={depot?.key ?? ''} onChange={(value) => set({ depot: value === 'siege' ? null : value, bearbeiten: null })} />
        ) : null}
        <div className="toolbar dp-own">
          <button type="button" className="btn btn-quiet" onClick={() => set({ bearbeiten: 'neu' })} disabled={prefs.depots.length >= MAX_OWN_DEPOTS}>
            Neues Depot
          </button>
          {ownIndex !== null ? (
            <button type="button" className="btn btn-quiet" onClick={() => set({ bearbeiten: depot!.key })}>
              „{depot!.name}“ bearbeiten
            </button>
          ) : null}
        </div>
        {editing === 'neu' && prefs.depots.length < MAX_OWN_DEPOTS ? (
          <DepotEditor initial={{ name: '', isins: [] }} index={null} instruments={instruments} isinIndex={isinIndex} onSave={saveNew} onDelete={null} onCancel={() => set({ bearbeiten: null })} />
        ) : null}
        {prefs.depots.length >= MAX_OWN_DEPOTS ? <p className="section-note">Höchstens {MAX_OWN_DEPOTS} eigene Depots – für ein neues bitte zuerst eines löschen.</p> : null}
        {editing && editing !== 'neu' && ownIndex !== null && depot && editing === depot.key ? (
          <DepotEditor
            key={depot.key}
            initial={{ name: depot.name, isins: depot.isins }}
            index={ownIndex}
            instruments={instruments}
            isinIndex={isinIndex}
            onSave={(name, isins) => {
              const list = prefs.depots.map((d, k) => (k === ownIndex ? { name, isins } : d));
              setPrefs({ depots: list });
              set({ bearbeiten: null });
            }}
            onDelete={() => {
              const list = prefs.depots.filter((_, k) => k !== ownIndex);
              setPrefs({ depots: list });
              set({ bearbeiten: null, depot: null });
            }}
            onCancel={() => set({ bearbeiten: null })}
          />
        ) : null}

        <div className="dp-controls">
          <div className="segmented-wrap">
            <span className="control-label" id="dp-tage">
              Kalendertage: {h}
            </span>
            <div className="chips" role="group" aria-labelledby="dp-tage">
              {QUICK_DAYS.map((d) => (
                <button key={d} type="button" className={`chip${d === h ? ' is-active' : ''}`} aria-pressed={d === h} onClick={() => set({ t: d === DEPOT_DAYS ? null : d })}>
                  {d}
                </button>
              ))}
              <button type="button" className="chip" aria-label="Einen Tag weniger" disabled={h <= 1} onClick={() => set({ t: h - 1 })}>
                −
              </button>
              <button type="button" className="chip" aria-label="Einen Tag mehr" disabled={h >= DEPOT_DAYS} onClick={() => set({ t: h + 1 === DEPOT_DAYS ? null : h + 1 })}>
                +
              </button>
            </div>
          </div>
          <Segmented
            label="Rechenbasis"
            options={(['usd', 'eur', 'lokal'] as DepotBasis[]).map((b) => ({ value: b, label: BASIS_LABEL[b] }))}
            value={basis}
            onChange={(value) => setPrefs({ depotBasis: value as DepotBasis })}
          />
          {!fxReady && basisWanted !== 'lokal' ? (
            <p className="section-note">Dieser Datenstand enthält noch keine Wechselkurse (ab Version 1.9) – gerechnet wird in Originalwährung je Aktie.</p>
          ) : null}
          <label className="field dp-capital">
            <span className="field-label">Rechnerisches Startkapital{basis === 'lokal' ? '' : ` in ${BASIS_LABEL[basis]}`}</span>
            <input
              className="input"
              type="number"
              inputMode="decimal"
              min={1}
              step={100}
              value={capital}
              onChange={(e: Event) => {
                const value = Number((e.target as HTMLInputElement).value);
                if (Number.isFinite(value) && value >= 1 && value <= 100_000_000) setPrefs({ depotCapital: value });
              }}
            />
          </label>
        </div>

        {!seriesReady ? <Loading height={420} label={`Kursreihen werden geladen (${f.integer(allIsins.length - many.pending)} von ${f.integer(allIsins.length)})`} /> : null}
        {fxState.error && basis !== 'lokal' ? <ErrorNote error={fxState.error} /> : null}
        {depot && result ? (
          <DepotDetail depot={depot} result={result} sort={sort} instruments={instruments} isinIndex={isinIndex} manifest={manifest} totals={totals} basis={basis} onRoute={set} />
        ) : null}
        {!depots.length && frequency.data ? (
          <Notice tone="info" title="Noch kein Depot">
            <p>In diesem Datenstand gibt es keine Häufigkeitsliste; lege mit „Neues Depot“ ein eigenes an.</p>
          </Notice>
        ) : null}
      </section>

      {windowRows.length ? <AllDepots rows={windowRows} depots={depots} activeH={h} activeKey={depot?.key ?? ''} onRoute={set} /> : null}

      {depot && seriesReady ? (
        <section className="section" id="depots-kurse" aria-labelledby="depots-kurse-titel">
          <SectionTitle id="depots-kurse-titel">Kurse im direkten Vergleich</SectionTitle>
          <label className="field">
            <span className="field-label">Auswahl</span>
            <select className="select" value={compareKind} onChange={(e: Event) => set({ vgl: (e.target as HTMLSelectElement).value === 'depot' ? null : (e.target as HTMLSelectElement).value })}>
              <option value="depot">Depot „{depot.name}“</option>
              <option value="gemeinsam">
                In beiden Top {size} ({f.integer(shownLists?.both.length ?? 0)})
              </option>
              <option value="alle">
                Beide Top {size} zusammen ({f.integer(shownLists?.union.length ?? 0)})
              </option>
              <option value="siege">Top {size} · erste Plätze</option>
              <option value="nennungen">Top {size} · Top-10-Nennungen</option>
            </select>
          </label>
          <p className="section-note">
            {compareKind === 'depot' ? `Aktien des Depots „${depot.name}“` : `${compareTitle} aus der Häufigkeit oben (${selection.text})`}, {f.windowLabel(h)} bis {f.day(manifest.cutoff_day)}, Start = 100 in
            Originalwährung. Linien nur aus vorhandenen Tagesschlusskursen.
          </p>
          {compareIsins.length ? <CompareBlock isins={compareIsins} h={h} cutoffDay={manifest.cutoff_day} /> : <p className="section-note">Keine Aktie mit Kursreihe in dieser Auswahl.</p>}
          {compareIsins.length ? (
            <div className="toolbar">
              <a className="btn" href={buildHash('/raster', { quelle: 'isins', isins: compareIsins.join(','), titel: compareTitle, h, modus: 'kacheln' })}>
                Alle {f.integer(compareIsins.length)} im Kursraster
              </a>
            </div>
          ) : null}
        </section>
      ) : null}

      <Disclosure summary="So werden Währungen, Startdaten und Kosten behandelt">
        <p>
          <strong>Start:</strong> der letzte echte Schlusskurs am oder vor dem Kalendertag „Stichtag minus Tage“, höchstens 7 Tage davor – wie in den Ranglisten. An Börsenfeiertagen gilt der
          vorherige echte Kurs; fehlt er, bleibt die Aktie in diesem Zeitraum draußen und die Gewichte verteilen sich auf die übrigen. Nichts wird aufgefüllt.
        </p>
        <p>
          <strong>Währung:</strong> {BASIS_LABEL.usd} und {BASIS_LABEL.eur} mit den Euro-Referenzkursen der EZB vom jeweiligen Kurstag (oder dem letzten davor, höchstens 5 Tage alt):
          Rendite = (Endkurs × Wechselkurs Ende) / (Startkurs × Wechselkurs Start) − 1. In Originalwährung zählt nur die Kursänderung jeder Aktie. Die Umrechnung ist indikativ, keine
          ausführbare Devisenorder.
        </p>
        <p>
          <strong>Beitrag:</strong> Startgewicht × Aktienrendite, in Prozentpunkten; die Summe ist die Depotrendite. Endgewicht = Endwert der Position / Endwert des Depots.
        </p>
        <p>
          <strong>Nicht enthalten:</strong> Spread, Ordergebühren, Steuern, Dividenden, Wechselkurskosten. Die beiden Zehnerdepots entstehen immer aus der Standardauswahl (40/60, 50/50,
          60/40, 1–30 Tage, Gruppe A und B); eine andere Auswahl der Häufigkeit oben ändert ihre Zusammensetzung nicht.
        </p>
      </Disclosure>
    </div>
  );
}

