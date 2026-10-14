/* Musterdepots (ab 1.9) – „Zwei Zehnerdepots · 1–30 Tage · Beiträge“ als Ansicht der App.
 *
 * 1. Welche Aktien erscheinen am häufigsten? Zwei Top-10-Listen (erste Plätze, Top-10-Nennungen),
 *    beide zusammen, gemeinsame grün; Auswahl für ein eigenes Depot.
 * 2. Depot: Depotrendite und Beitrag jeder Aktie für ein Rückblickfenster (1–30 Kalendertage),
 *    gleiche Startbeträge, USD, EUR oder Originalwährung, Startkapital frei wählbar.
 * 3. Alle Depots für 1–30 Tage (Grafik und Tabelle), Kurse im direkten Vergleich, Rechenweg.
 * Alle Zahlen aus dem aktiven Datenstand (Kursreihen, Häufigkeit, Euro-Referenzkurse). */

import { useMemo, useState } from 'react';
import { useDark } from '../components/charts';
import { CompareBlock } from '../components/compare';
import { IconClose, IconDownload } from '../components/icons';
import { TotalBadge } from '../components/signals';
import { Disclosure, ErrorNote, Loading, Notice, Pct, Segmented, SectionTitle } from '../components/ui';
import { MAX_SERIES, seriesColor } from '../lib/colors';
import { downloadText, safeFilename, toCsv } from '../lib/csv';
import {
  BASIS_LABEL,
  computeDepot,
  DEPOT_DAYS,
  depotWindows,
  FREQUENCY_PRESETS,
  fxLookup,
  MAX_DEPOT_MEMBERS,
  MAX_OWN_DEPOTS,
  ownDepotDefs,
  reportDepots,
  sortPositions,
  topLists,
  type ContributionSort,
  type DepotBasis,
  type DepotDef,
  type DepotPosition,
  type DepotResult,
  type DepotWindowRow,
  type FrequencyPreset,
  type TopLists,
} from '../lib/depots';
import { PREVIEW } from '../lib/env';
import * as f from '../lib/format';
import { useFrequency, useFx, useSeriesMany, useSignals } from '../lib/hooks';
import { berlinClock, isIntraday } from '../lib/intraday';
import { instName, parseIsinImport } from '../lib/instruments';
import { buildHash, updateParams, type Route } from '../lib/router';
import { totalsByIsin, type TotalEntry } from '../lib/signals';
import { isVeryLow, turnoverOf, veryLowUsd } from '../lib/turnover';
import type { Instruments, Manifest } from '../lib/types';
import { useApp } from '../state/AppState';

type ListFilter = 'union' | 'beide' | 'erste' | 'top10';
type Totals = Map<string, TotalEntry> | null;

const QUICK_DAYS = [1, 7, 14, 21, 30];
const FX_FORMAT = new Intl.NumberFormat('de-DE', { maximumSignificantDigits: 5 });

function pp(fraction: number | null | undefined): string {
  return f.signedPctValue(fraction === null || fraction === undefined ? null : fraction * 100, 2).replace('%', 'PP');
}

function weight(fraction: number): string {
  return f.plainPct(fraction * 100, 1);
}

function parsePreset(text: string | null): FrequencyPreset {
  return text === 'gesamt' || text === 'rendite' ? text : 'bericht';
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

function FreqCount({ value, rank, valid, label }: { value: number; rank: number | null; valid: number; label: string }) {
  const share = valid > 0 ? Math.min(1, value / valid) : 0;
  return (
    <span className="dq-count" aria-label={`${label}: ${value}${rank ? `, Rang ${rank}` : ', außerhalb der Top 10'}`}>
      <b aria-hidden="true">{f.integer(value)}</b>
      <small aria-hidden="true">{rank ? `Rang ${rank}` : 'außerhalb Top 10'}</small>
      <span className="dq-pulse" aria-hidden="true">
        <span style={{ width: `${Math.round(share * 100)}%` }} />
      </span>
    </span>
  );
}

function QuickOverview({
  lists,
  preset,
  filter,
  sortTop,
  instruments,
  manifest,
  totals,
  selected,
  onToggle,
  onRoute,
}: {
  lists: TopLists;
  preset: FrequencyPreset;
  filter: ListFilter;
  sortTop: boolean;
  instruments: Instruments;
  manifest: Manifest;
  totals: Totals;
  selected: Set<string>;
  onToggle: (isin: string) => void;
  onRoute: (changes: Record<string, string | number | null>) => void;
}) {
  const [copied, setCopied] = useState<string | null>(null);
  const base = filter === 'erste' ? lists.firsts : filter === 'top10' ? lists.tops : filter === 'beide' ? lists.both : lists.union;
  const rows = [...base].sort(sortTop ? (a, b) => b.n10 - a.n10 || b.n1 - a.n1 || b.n3 - a.n3 || (a.isin < b.isin ? -1 : 1) : (a, b) => b.n1 - a.n1 || b.n3 - a.n3 || b.n10 - a.n10 || (a.isin < b.isin ? -1 : 1));
  const firstWin = lists.firsts[0];
  const firstTop = lists.tops[0];
  const description = `${FREQUENCY_PRESETS[preset].text} · A und B · ${f.integer(lists.valid)} gültige von ${f.integer(lists.possible)} Kombinationen`;
  const summaryText = () =>
    `TR-Aktienvergleich · Kursstand ${f.day(manifest.cutoff_day)}\n${description}\n\n` +
    rows.map((r) => `${instName(instruments, r.idx)} | ${r.isin} | ${r.n1} erste Plätze | ${r.n10} Top-10-Nennungen${r.both ? ' | in beiden Top 10' : ''}`).join('\n') +
    '\n\nHistorische Häufigkeit, keine Gewinnwahrscheinlichkeit.';
  const download = () => {
    const csv = toCsv(
      [
        ['Inhalt', 'Häufigste Aktien: zehn häufigste erste Plätze und zehn häufigste Top-10-Nennungen'],
        ['Auswahl', description],
        ['Kursstichtag', manifest.cutoff_session_date],
        ['Snapshot', manifest.snapshot_id],
      ],
      ['Unternehmen', 'ISIN', 'Erste Plätze', 'Rang erste Plätze', 'Top 3', 'Top-10-Nennungen', 'Rang Top-10-Nennungen', 'In beiden Top 10', 'Auswertbare Kombinationen'],
      rows.map((r) => [instName(instruments, r.idx), r.isin, r.n1, r.rank1, r.n3, r.n10, r.rank10, r.both ? 'ja' : 'nein', r.available]),
    );
    downloadText(safeFilename(`haeufigkeit_${preset}_${manifest.snapshot_id}.csv`), csv);
  };
  return (
    <section className="section dq-section" id="depots-haeufig" aria-labelledby="depots-haeufig-titel">
      <SectionTitle id="depots-haeufig-titel">Welche Aktien erscheinen am häufigsten?</SectionTitle>
      <p className="section-note">
        „Erste Plätze“ zählt die Siege, „Top 10“ die regelmäßige Präsenz weit oben. Grün hinterlegt: in beiden Top-10-Listen. Die Zählungen werden nicht addiert – ein erster Platz ist zugleich
        eine Top-10-Nennung.
      </p>
      <Segmented
        label="Auswertung"
        options={(Object.keys(FREQUENCY_PRESETS) as FrequencyPreset[]).map((key) => ({ value: key, label: FREQUENCY_PRESETS[key].label }))}
        value={preset}
        onChange={(value) => onRoute({ auswahl: value === 'bericht' ? null : value })}
      />
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
          { value: 'union', label: 'Beide Top 10' },
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
                      <span translate="no">{r.isin}</span> · in {f.integer(r.available)} Kombinationen auswertbar
                    </small>
                    {r.both ? <span className="dq-both">In beiden Top 10</span> : null}
                  </span>
                  <FreqCount value={r.n1} rank={r.rank1} valid={lists.valid} label="Erste Plätze" />
                  <FreqCount value={r.n10} rank={r.rank10} valid={lists.valid} label="Top-10-Nennungen" />
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
        <a className="btn btn-quiet" href={buildHash('/haeufig', { von: 1, bis: 30, gruppen: 'ab' })}>
          Alle Filter
        </a>
      </div>
      <p className="section-note" role="status">
        {copied ?? ''}
      </p>
      <p className="section-note">Rangangaben beziehen sich auf die beiden Häufigkeitslisten. Eine häufige Nennung ist eine Übereinstimmung rückblickender Vergleiche, keine Kaufempfehlung.</p>
    </section>
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
  let lo = Math.min(0, ...values);
  let hi = Math.max(0, ...values);
  if (lo === hi) hi = lo + 0.01;
  const pad = (hi - lo) * 0.06;
  lo -= pad;
  hi += pad;
  const x = (h: number) => m.l + ((h - 1) / (DEPOT_DAYS - 1)) * (W - m.l - m.r);
  const y = (v: number) => m.t + (1 - (v - lo) / (hi - lo)) * (Hh - m.t - m.b);
  const ticks = [0, 1, 2, 3].map((k) => lo + ((hi - lo) * k) / 3);
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
              {f.signedPctValue(t * 100, 0)}
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
                    {r.h} Tage
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

  const preset = parsePreset(route.params.get('auswahl'));
  const filter = parseFilter(route.params.get('liste'));
  const sortTop = route.params.get('hsort') === 'n10';
  const h = parseDays(route.params.get('t'));
  const sort = parseSort(route.params.get('bsort'));
  const editing = route.params.get('bearbeiten');
  const basisWanted: DepotBasis = prefs.depotBasis;
  const fxReady = Boolean(manifest?.fx);
  const basis: DepotBasis = basisWanted !== 'lokal' && !fxReady ? 'lokal' : basisWanted;
  const capital = prefs.depotCapital;

  const reportLists = useMemo(() => {
    if (!frequency.data || !instruments) return null;
    try {
      return topLists(frequency.data, instruments, 'bericht');
    } catch {
      return null;
    }
  }, [frequency.data, instruments]);
  const shownLists = useMemo(() => {
    if (!frequency.data || !instruments) return null;
    if (preset === 'bericht') return reportLists;
    try {
      return topLists(frequency.data, instruments, preset);
    } catch {
      return null;
    }
  }, [frequency.data, instruments, preset, reportLists]);

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
        <p className="lede">
          Musterdepots aus dem Bericht 1–30: die zehn Aktien mit den meisten <strong>ersten Plätzen</strong> und die zehn mit den meisten <strong>Top-10-Nennungen</strong> – dazu deine eigenen
          Depots. Gleiche Startbeträge je Aktie, danach unveränderte Stückzahlen; jeder Zeitraum von 1 bis 30 Tagen ist eine eigene Rechnung.
        </p>
        <p className="section-note">
          {intraday
            ? `Zwischenstand vom ${f.dayLong(manifest.cutoff_day)}, Kurse bis ${berlinClock(manifest.zwischenstand?.kurse_bis_utc)} (vorläufig).`
            : `Kursstichtag ${f.dayLong(manifest.cutoff_day)}, Tagesschlusskurse.`}{' '}
          Gespeicherte Tagesdaten, kein Livekurs.
        </p>
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
      {shownLists ? (
        <QuickOverview
          lists={shownLists}
          preset={preset}
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
          <p className="section-note">
            Aktien des Depots „{depot.name}“, {f.windowLabel(h)} bis {f.day(manifest.cutoff_day)}, Start = 100 in Originalwährung. Linien nur aus vorhandenen Tagesschlusskursen.
          </p>
          <CompareBlock isins={depot.isins.filter((isin) => allIsins.includes(isin))} h={h} cutoffDay={manifest.cutoff_day} />
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
          <strong>Nicht enthalten:</strong> Spread, Ordergebühren, Steuern, Dividenden, Wechselkurskosten. Die beiden Zehnerdepots entstehen immer aus der Auswahl des Berichts 1–30 (vier
          Gewichtungen, Gruppe A und B); die Anzeige der Häufigkeit oben ändert ihre Zusammensetzung nicht.
        </p>
      </Disclosure>
    </div>
  );
}

