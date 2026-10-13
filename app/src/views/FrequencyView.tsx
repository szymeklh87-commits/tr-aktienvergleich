import { useMemo, useState } from 'react';
import { IconDownload, IconGrid } from '../components/icons';
import { InstrumentRow } from '../components/rows';
import { Disclosure, ErrorNote, IsinCopy, KeyValues, Loading, Notice, Pager, Segmented } from '../components/ui';
import { downloadText, safeFilename, toCsv, type CsvValue } from '../lib/csv';
import * as f from '../lib/format';
import { aggregateFrequency, membershipCounts, nK, type FrequencyEntry, type FrequencyOptions, type SortMode, type TopK } from '../lib/frequency';
import { useFrequency, useSeries } from '../lib/hooks';
import { instName } from '../lib/instruments';
import { buildHash, navigate, updateParams, type Route } from '../lib/router';
import { decodeRanks, parsePolicy, parseWeight, rankFromMatrix, WEIGHTS } from '../lib/scoring';
import type { FrequencyData, Policy } from '../lib/types';
import { useApp } from '../state/AppState';
import { PREVIEW } from '../lib/env';

const PAGE = 30;

type Tab = 'alle' | 'eine' | 'rendite';

function parseTopK(text: string | null, fallback: TopK): TopK {
  return text === '1' ? 1 : text === '3' ? 3 : text === '10' ? 10 : fallback;
}

function parseDay(text: string | null, fallback: number): number {
  const n = Number(text);
  return Number.isInteger(n) && n >= 1 && n <= 90 ? n : fallback;
}

function optionsFrom(route: Route, prefs: { frequencyTopK: TopK; frequencyPolicy: Policy; frequencySort: SortMode }): { tab: Tab; options: FrequencyOptions; weight: number } {
  const tabParam = route.params.get('tab');
  const tab: Tab = tabParam === 'eine' || tabParam === 'rendite' ? tabParam : 'alle';
  const weight = parseWeight(route.params.get('w'), 60);
  let from = parseDay(route.params.get('von'), 1);
  let to = parseDay(route.params.get('bis'), 90);
  if (from > to) [from, to] = [to, from];
  const policy: Policy = tab === 'rendite' ? 'native' : parsePolicy(route.params.get('p') ?? prefs.frequencyPolicy);
  const weights = tab === 'alle' ? [...WEIGHTS] : tab === 'rendite' ? [0] : [weight];
  const sortParam = route.params.get('sort');
  const sort: SortMode = sortParam === 'distinct_windows' ? 'distinct_windows' : sortParam === 'occurrences' ? 'occurrences' : prefs.frequencySort;
  return { tab, weight, options: { policy, weights, from, to, topK: parseTopK(route.params.get('k'), prefs.frequencyTopK), sort } };
}

function scopeText(tab: Tab, options: FrequencyOptions, weight: number): string {
  const what = tab === 'alle' ? 'alle elf Gewichtungen' : tab === 'rendite' ? 'nur reine Kursrendite (0/100)' : f.weightLabel(weight);
  const field = options.policy === 'native' ? 'natives Vergleichsfeld' : 'gleiches Vergleichsfeld (U)';
  return `${what}, ${options.from === 1 && options.to === 90 ? 'alle Zeiträume 1–90 Tage' : `Zeiträume ${options.from}–${options.to} Tage`}, Top ${options.topK}, ${field}`;
}

function serverCheck(data: FrequencyData, entries: FrequencyEntry[]): { ok: boolean; compared: number } {
  const ref = data.server_reference.entries;
  const n = Math.min(ref.length, entries.length);
  for (let k = 0; k < n; k += 1) {
    const a = ref[k];
    const b = entries[k];
    if (a.idx !== b.idx || a.n1 !== b.n1 || a.n3 !== b.n3 || a.n10 !== b.n10 || a.A !== b.available || a.H !== b.distinctWindows || a.W !== b.distinctWeights || a.dew !== b.distinctEffective) {
      return { ok: false, compared: k + 1 };
    }
  }
  return { ok: entries.length >= ref.length, compared: n };
}

export function FrequencyView({ route }: { route: Route }) {
  const { manifest, instruments, prefs, setPrefs } = useApp();
  const frequency = useFrequency();
  const { tab, options, weight } = optionsFrom(route, prefs);
  const page = Math.max(1, Number(route.params.get('seite') ?? 1) || 1);
  const [fromDraft, setFromDraft] = useState(String(options.from));
  const [toDraft, setToDraft] = useState(String(options.to));

  const membership = useMemo(() => (instruments ? membershipCounts(instruments, options.from, options.to) : null), [instruments, options.from, options.to]);
  const result = useMemo(() => {
    if (!frequency.data || !instruments || !membership) return null;
    return aggregateFrequency(frequency.data, instruments, options, membership);
  }, [frequency.data, instruments, membership, options.policy, options.weights.join(','), options.from, options.to, options.topK, options.sort]);

  if (!manifest || !instruments) return null;
  const set = (changes: Record<string, string | number | null>) => updateParams(route, { ...changes, seite: null });
  const pages = result ? Math.max(1, Math.ceil(result.entries.length / PAGE)) : 1;
  const current = Math.min(page, pages);
  const visible = result ? result.entries.slice((current - 1) * PAGE, current * PAGE) : [];
  const isDefault = tab === 'alle' && options.policy === 'native' && options.from === 1 && options.to === 90 && options.topK === 10 && options.sort === 'occurrences';
  const check = isDefault && result && frequency.data ? serverCheck(frequency.data, result.entries) : null;

  const exportList = () => {
    if (!result) return;
    const rows: CsvValue[][] = result.entries.map((e, k) => [
      k + 1,
      instName(instruments, e.idx),
      instruments.isin[e.idx],
      e.n10,
      e.n3,
      e.n1,
      e.distinctWindows,
      e.distinctWeights,
      e.available,
      result.validCells,
      e.distinctEffective,
      e.occurrences.filter((o) => o.smallField).length,
    ]);
    const csv = toCsv(
      [
        ['Ansicht', 'Häufigste Aktien'],
        ['Umfang', scopeText(tab, options, weight)],
        ['Sortierung', options.sort === 'occurrences' ? 'Kombinationstreffer' : 'unterschiedliche Zeiträume'],
        ['Zellen theoretisch / gültig (E) / leer', `${result.theoreticalCells} / ${result.validCells} / ${result.emptyCells}`],
        ['Aggregationsversion', frequency.data?.aggregation_version ?? ''],
        ['Snapshot', manifest.snapshot_id],
        ['Kursstichtag', manifest.cutoff_session_date],
        ['Datenmodus', manifest.data_mode === 'demo' ? 'DEMO – synthetische Testdaten' : manifest.data_mode],
        ['Hinweis', 'Trefferzahlen sind keine Gewinnwahrscheinlichkeiten und keine unabhängigen Bestätigungen.'],
      ],
      ['Platz', 'Unternehmen', 'ISIN', 'Top-10-Treffer', 'Top-3-Treffer', 'Platz-1-Treffer', `verschiedene Zeiträume (Top ${options.topK})`, `verschiedene Gewichtungen (Top ${options.topK})`, 'auswertbare Zellen A', 'gültige Zellen E', 'verschiedene tatsächliche Start-/Endpaare', 'Fundstellen mit kleinem Feld (M < K)'],
      rows,
    );
    downloadText(safeFilename(`haeufigkeit_${tab}_k${options.topK}_${options.policy}_${manifest.snapshot_id}.csv`), csv);
  };

  const exportOccurrences = () => {
    if (!result) return;
    const rows: CsvValue[][] = [];
    for (const e of result.entries) {
      for (const o of e.occurrences) {
        rows.push([instName(instruments, e.idx), instruments.isin[e.idx], o.h, o.weight, options.policy, o.rank, o.score, 100 * o.r, f.day(o.start), f.day(o.end), o.cohortSize, o.smallField ? 'ja' : 'nein']);
      }
    }
    const csv = toCsv(
      [
        ['Ansicht', 'Fundstellen der Häufigkeitsliste'],
        ['Umfang', scopeText(tab, options, weight)],
        ['Snapshot', manifest.snapshot_id],
        ['Kursstichtag', manifest.cutoff_session_date],
      ],
      ['Unternehmen', 'ISIN', 'Tage', 'Gewichtung Gleichmäßigkeit %', 'Vergleichsfeld', 'Rang', 'Score', 'Kursrendite %', 'Beginn', 'Ende', 'Kandidaten M', 'kleines Feld'],
      rows,
      [undefined, undefined, undefined, undefined, undefined, undefined, 4, 6],
    );
    downloadText(safeFilename(`fundstellen_${tab}_k${options.topK}_${options.policy}_${manifest.snapshot_id}.csv`), csv);
  };

  return (
    <div className="view">
      <header className="view-head">
        <p className="lede">Welche Aktien tauchen in diesem Datenstand am häufigsten in den Spitzenlisten auf? Gezählt wird je Zeitraum und Gewichtung höchstens ein Treffer pro Aktie.</p>
      </header>

      <Segmented
        label="Umfang"
        hideLabel
        options={[
          { value: 'alle', label: 'Alle Gewichtungen' },
          { value: 'eine', label: 'Eine Gewichtung' },
          { value: 'rendite', label: 'Nur Rendite' },
        ]}
        value={tab}
        onChange={(value) => set({ tab: value === 'alle' ? null : value })}
      />
      {tab === 'eine' ? (
        <div className="chips" role="group" aria-label="Gewichtung wählen">
          {WEIGHTS.map((w) => (
            <button key={w} type="button" className={`chip${w === weight ? ' is-active' : ''}`} aria-pressed={w === weight} onClick={() => set({ w })}>
              {w}/{100 - w}
            </button>
          ))}
        </div>
      ) : null}
      {tab === 'eine' ? <p className="section-note">{f.weightLabel(weight)}</p> : null}

      <Segmented
        label="Spitzenbereich"
        options={[
          { value: '10', label: 'Top 10' },
          { value: '3', label: 'Top 3' },
          { value: '1', label: 'Platz 1' },
        ]}
        value={String(options.topK)}
        onChange={(value) => {
          setPrefs({ frequencyTopK: parseTopK(value, 10) });
          set({ k: value });
        }}
      />
      <Segmented
        label="Sortieren nach"
        options={[
          { value: 'occurrences', label: 'Meiste Treffer' },
          { value: 'distinct_windows', label: 'Meiste verschiedene Zeiträume' },
        ]}
        value={options.sort}
        onChange={(value) => {
          setPrefs({ frequencySort: value as SortMode });
          set({ sort: value });
        }}
      />
      {tab !== 'rendite' ? (
        <Segmented
          label="Vergleichsfeld"
          options={[
            { value: 'native', label: 'Nativ' },
            { value: 'common_trend', label: 'Gleiches Feld' },
          ]}
          value={options.policy}
          onChange={(value) => {
            setPrefs({ frequencyPolicy: value as Policy });
            set({ p: value });
          }}
        />
      ) : null}
      <Disclosure summary={`Zeiträume: ${options.from}–${options.to} Tage`}>
        <form
          className="range-pair"
          onSubmit={(e: Event) => {
            e.preventDefault();
            set({ von: parseDay(fromDraft, 1), bis: parseDay(toDraft, 90) });
          }}
        >
          <label className="field">
            <span className="field-label">von (Tage)</span>
            <input className="input" type="number" inputMode="numeric" min={1} max={90} value={fromDraft} onChange={(e: Event) => setFromDraft((e.target as HTMLInputElement).value)} />
          </label>
          <label className="field">
            <span className="field-label">bis (Tage)</span>
            <input className="input" type="number" inputMode="numeric" min={1} max={90} value={toDraft} onChange={(e: Event) => setToDraft((e.target as HTMLInputElement).value)} />
          </label>
          <button type="submit" className="btn btn-primary">
            Bereich übernehmen
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setFromDraft('1');
              setToDraft('90');
              set({ von: null, bis: null });
            }}
          >
            Alle 1–90
          </button>
        </form>
      </Disclosure>

      {frequency.error ? <ErrorNote error={frequency.error} /> : null}
      {!result && !frequency.error ? <Loading height={600} label="Häufigkeiten werden gezählt" /> : null}

      {result ? (
        <>
          <p className="section-note">
            Umfang: {scopeText(tab, options, weight)}. Gültige Ranglisten (Nenner E): {f.integer(result.validCells)} von {f.integer(result.theoreticalCells)} möglichen Zellen
            {result.emptyCells ? `; ${f.integer(result.emptyCells)} Zellen ohne Rangliste (zum Beispiel kurze Zeiträume ohne 15 Tageskurse)` : ''}.
            {options.policy === 'native' && tab === 'alle' ? ' Nativ: 0/100 zählt auf dem größeren Feld aller Aktien mit Kursrendite, die übrigen Gewichtungen nur gleichmäßig gestiegene Aktien.' : ''}
          </p>
          {check ? (
            <p className="section-note">
              {check.ok ? `Abgleich mit der Serverberechnung: übereinstimmend (erste ${f.integer(check.compared)} Einträge).` : `Abgleich mit der Serverberechnung: Abweichung ab Eintrag ${check.compared}. Bitte melden.`}
            </p>
          ) : null}
          {result.entries.length === 0 ? (
            <Notice tone="info" title="Keine Treffer">
              <p>In diesem Umfang gibt es keine veröffentlichte Rangliste mit Aktien.</p>
            </Notice>
          ) : null}
          <ol className="rows" aria-label="Häufigste Aktien">
            {visible.map((entry, k) => {
              const position = (current - 1) * PAGE + k + 1;
              const isin = instruments.isin[entry.idx];
              const small = entry.occurrences.filter((o) => o.smallField).length;
              return (
                <InstrumentRow
                  key={entry.idx}
                  idx={entry.idx}
                  rank={position}
                  href={buildHash(`/haeufig/${isin}`, { p: options.policy, k: options.topK, tab, w: tab === 'eine' ? weight : null, von: options.from, bis: options.to })}
                  figs={
                    <>
                      <span className="pct pct-strong">{f.integer(options.sort === 'distinct_windows' ? entry.distinctWindows : nK(entry, options.topK))}</span>
                      <span className="row-fig-sub">{options.sort === 'distinct_windows' ? 'Zeiträume' : options.topK === 1 ? 'mal Platz 1' : `Top-${options.topK}-Treffer`}</span>
                    </>
                  }
                >
                  <span>
                    Top 10: <strong>{entry.n10}</strong>, Top 3: <strong>{entry.n3}</strong>, Platz 1: <strong>{entry.n1}</strong>. In {f.plural(entry.distinctWindows, 'verschiedenen Zeitraum', 'verschiedenen Zeiträumen')}
                    {tab === 'alle' ? ` und ${f.plural(entry.distinctWeights, 'Gewichtung', 'Gewichtungen')}` : ''} unter den Top {options.topK}.
                  </span>
                  <Disclosure summary="Nenner, Gewichtungen und Fundstellen">
                    <KeyValues
                      items={[
                        [`Anteil aller gültigen Listen (N${options.topK}/E)`, `${nK(entry, options.topK)} von ${f.integer(result.validCells)} = ${f.share(nK(entry, options.topK), result.validCells)}`],
                        [`Anteil, wenn auswertbar (N${options.topK}/A)`, `${nK(entry, options.topK)} von ${f.integer(entry.available)} = ${f.share(nK(entry, options.topK), entry.available)}`],
                        ['Verschiedene tatsächliche Start-/Endpaare', f.integer(entry.distinctEffective)],
                        ['Fundstellen mit kleinem Feld (weniger Kandidaten als K)', f.integer(small)],
                      ]}
                    />
                    <p className="section-note">Die Anteile sind keine Gewinnwahrscheinlichkeiten. Benachbarte Zeiträume und ähnliche Gewichtungen nutzen stark überlappende Kurse.</p>
                    {tab === 'alle' ? (
                      <p>
                        Treffer je Gewichtung (Top {options.topK}):{' '}
                        {WEIGHTS.map((w) => `${w}/${100 - w}: ${entry.hitsByWeight[w] ?? 0}`).join('; ')}
                      </p>
                    ) : null}
                    <ul className="rows">
                      {entry.occurrences.slice(0, 12).map((o) => (
                        <li key={`${o.h}-${o.weight}`} className="row row-nr">
                          <div className="row-main">
                            <a className="row-link row-name" href={buildHash('/ranking', { h: o.h, w: o.weight, p: options.policy })}>
                              {f.windowLabel(o.h)}, {f.weightLabel(o.weight)}
                            </a>
                            <span className="row-alt">
                              Platz {o.rank} von {f.integer(o.cohortSize)}, Score {f.score(o.score)}, {f.dayRange(o.start, o.end)}
                              {o.smallField ? '. Kleines Vergleichsfeld.' : ''}
                            </span>
                            <div className="row-meta">
                              <a href={buildHash(`/aktie/${isin}`, { h: o.h, w: o.weight, p: options.policy })}>Kurschart</a>
                            </div>
                          </div>
                          <div className="row-figs">
                            <span className={`pct ${o.r > 0 ? 'pct-plus' : o.r < 0 ? 'pct-minus' : 'pct-null'}`}>{f.pct(o.r)}</span>
                          </div>
                        </li>
                      ))}
                    </ul>
                    {entry.occurrences.length > 12 ? (
                      <a className="btn" href={buildHash(`/haeufig/${isin}`, { p: options.policy, k: options.topK })}>
                        Alle {entry.occurrences.length} Fundstellen in der Matrix
                      </a>
                    ) : null}
                  </Disclosure>
                </InstrumentRow>
              );
            })}
          </ol>
          <Pager page={current} pages={pages} onChange={(p) => updateParams(route, { seite: p })} label="Seiten der Häufigkeitsliste" />
          <div className="toolbar no-print">
            <button
              type="button"
              className="btn"
              disabled={!result.entries.length}
              onClick={() => navigate('/raster', { quelle: 'isins', isins: result.entries.slice(0, 10).map((e) => instruments.isin[e.idx]).join(','), titel: 'Top 10 der Häufigkeitsliste' })}
            >
              <IconGrid /> Top 10 im Chart-Raster öffnen
            </button>
            {!PREVIEW ? (
              <>
                <button type="button" className="btn btn-quiet" onClick={exportList}>
                  <IconDownload /> Liste als CSV
                </button>
                <button type="button" className="btn btn-quiet" onClick={exportOccurrences}>
                  <IconDownload /> Fundstellen als CSV
                </button>
              </>
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}

type CellState = 'top1' | 'top3' | 'top10' | 'out' | 'nq' | 'empty';

const BLOCK_SIZE = 15;
const BLOCKS = 90 / BLOCK_SIZE;

/** Treffer-Matrix einer Aktie: 90 Zeiträume × 11 Gewichtungen mit tatsächlichem Rang. */
export function FrequencyMatrixView({ route, isin }: { route: Route; isin: string }) {
  const { manifest, instruments, isinIndex } = useApp();
  const policy = parsePolicy(route.params.get('p'));
  const topK = parseTopK(route.params.get('k'), 10);
  const block = Math.min(BLOCKS - 1, Math.max(0, Number(route.params.get('block') ?? 0) || 0));
  const selected = route.params.get('zelle');
  const series = useSeries(isin);
  const frequency = useFrequency();
  const matrix = useMemo(() => (series.data ? decodeRanks(series.data.ranks_b64) : null), [series.data]);
  if (!manifest || !instruments) return null;
  const idx = isinIndex.get(isin);
  if (idx === undefined) {
    return (
      <Notice tone="warn" title="ISIN nicht in diesem Datenstand">
        <p>{isin} ist in der TR-Aktienliste dieses Stands nicht enthalten.</p>
      </Notice>
    );
  }
  const freq = frequency.data;
  const cellState = (h: number, w: number): { state: CellState; rank: number | null; M: number } => {
    const M = freq ? (policy === 'native' && w === 0 ? freq.M.v0[h - 1] : freq.M.u[h - 1]) : 0;
    if (!M) return { state: 'empty', rank: null, M };
    const rank = matrix ? rankFromMatrix(matrix, h, policy, w) : null;
    if (rank === null) return { state: 'nq', rank, M };
    if (rank <= 1 && topK >= 1) return { state: 'top1', rank, M };
    if (rank <= 3 && topK >= 3) return { state: 'top3', rank, M };
    if (rank <= 10 && topK >= 10) return { state: 'top10', rank, M };
    return { state: 'out', rank, M };
  };

  let n1 = 0;
  let n3 = 0;
  let n10 = 0;
  const windows = new Set<number>();
  const weights = new Set<number>();
  if (matrix && freq) {
    for (let h = 1; h <= 90; h += 1) {
      for (const w of WEIGHTS) {
        const { rank } = cellState(h, w);
        if (rank === null) continue;
        if (rank <= 1) n1 += 1;
        if (rank <= 3) n3 += 1;
        if (rank <= 10) n10 += 1;
        if (rank <= topK) {
          windows.add(h);
          weights.add(w);
        }
      }
    }
  }

  const [selH, selW] = (selected ?? '').split('-').map(Number);
  const sel = selected && Number.isInteger(selH) && Number.isInteger(selW) ? { h: selH, w: selW, ...cellState(selH, selW) } : null;
  const occ = sel && freq ? (policy === 'native' && sel.w === 0 ? freq.occ.v0 : freq.occ.u[String(sel.w)]) : null;
  let occDetail: { score: number; r: number; start: number } | null = null;
  if (sel && occ) {
    for (let k = 0; k < occ.h.length; k += 1) {
      if (occ.h[k] === sel.h && occ.idx[k] === idx) {
        occDetail = { score: occ.score[k], r: occ.r[k], start: occ.start[k] };
        break;
      }
    }
  }
  const from = block * BLOCK_SIZE + 1;
  const to = from + BLOCK_SIZE - 1;
  const label = (state: CellState, rank: number | null) =>
    state === 'empty' ? '–' : state === 'nq' ? '·' : rank !== null && rank > 99 ? '99+' : String(rank);
  const stateText: Record<CellState, string> = {
    top1: 'Platz 1',
    top3: 'Platz 2–3',
    top10: 'Platz 4–10',
    out: `qualifiziert, außerhalb Top ${topK}`,
    nq: 'nicht im Vergleichsfeld (nicht qualifiziert)',
    empty: 'keine gültige Rangliste in dieser Zelle',
  };

  return (
    <div className="view">
      <header className="view-head">
        <a className="view-title" href={buildHash(`/aktie/${isin}`, {})} style={{ textDecoration: 'none' }}>
          {instName(instruments, idx)}
        </a>
        <IsinCopy isin={isin} />
        <p className="lede">
          Tatsächlicher Rang in allen 90 Zeiträumen und elf Gewichtungen ({policy === 'native' ? 'natives Vergleichsfeld' : 'gleiches Vergleichsfeld'}). Eine fehlende Platzierung ist kein Verlust.
        </p>
      </header>
      <div className="stats">
        <div className="stat">
          <span className="stat-value">{n10}</span>
          <span className="stat-label">Top-10-Treffer</span>
        </div>
        <div className="stat">
          <span className="stat-value">{n3}</span>
          <span className="stat-label">Top-3-Treffer</span>
        </div>
        <div className="stat">
          <span className="stat-value">{n1}</span>
          <span className="stat-label">mal Platz 1</span>
        </div>
        <div className="stat">
          <span className="stat-value">{windows.size}</span>
          <span className="stat-label">verschiedene Zeiträume (Top {topK})</span>
        </div>
      </div>
      <Segmented
        label="Vergleichsfeld"
        options={[
          { value: 'native', label: 'Nativ' },
          { value: 'common_trend', label: 'Gleiches Feld' },
        ]}
        value={policy}
        onChange={(value) => updateParams(route, { p: value, zelle: null })}
      />
      <Segmented
        label="Hervorheben"
        options={[
          { value: '10', label: 'Top 10' },
          { value: '3', label: 'Top 3' },
          { value: '1', label: 'Platz 1' },
        ]}
        value={String(topK)}
        onChange={(value) => updateParams(route, { k: value })}
      />
      <ul className="fm-legend" aria-label="Legende">
        {(['top1', 'top3', 'top10', 'out', 'nq', 'empty'] as CellState[])
          .filter((s) => (topK === 1 ? s !== 'top3' && s !== 'top10' : topK === 3 ? s !== 'top10' : true))
          .map((s) => (
            <li key={s}>
              <span className={`fcell is-${s}`} aria-hidden="true">
                {s === 'top1' ? '1' : s === 'top3' ? '2' : s === 'top10' ? '7' : s === 'out' ? '25' : s === 'nq' ? '·' : '–'}
              </span>
              {stateText[s]}
            </li>
          ))}
      </ul>
      {series.error ? <ErrorNote error={series.error} /> : null}
      {frequency.error ? <ErrorNote error={frequency.error} /> : null}
      {!matrix || !freq ? (
        series.error || frequency.error ? null : <Loading height={600} label="Matrix wird geladen" />
      ) : (
        <>
          <nav className="pager" aria-label="Zeiträume der Matrix">
            <button type="button" className="btn btn-quiet" disabled={block === 0} onClick={() => updateParams(route, { block: block - 1 || null })}>
              {from - BLOCK_SIZE}–{from - 1} Tage
            </button>
            <span className="pager-info">
              {from}–{to} Tage
            </span>
            <button type="button" className="btn btn-quiet" disabled={block >= BLOCKS - 1} onClick={() => updateParams(route, { block: block + 1 })}>
              {to + 1}–{to + BLOCK_SIZE} Tage
            </button>
          </nav>
          <div className="fmatrix-wrap" tabIndex={0} role="region" aria-label="Matrix, seitlich blätterbar">
          <div className="fmatrix" role="grid" aria-label={`Rangmatrix ${from} bis ${to} Tage`}>
            <div className="fhead" role="columnheader">
              Tage
            </div>
            {WEIGHTS.map((w) => (
              <div key={w} className="fhead" role="columnheader" title={f.weightLabel(w)}>
                {w}
              </div>
            ))}
            {Array.from({ length: to - from + 1 }, (_, k) => from + k).map((h) => (
              <div key={h} role="row" style={{ display: 'contents' }}>
                <div className="frow-label" role="rowheader">
                  {h}
                </div>
                {WEIGHTS.map((w) => {
                  const cell = cellState(h, w);
                  const key = `${h}-${w}`;
                  return (
                    <button
                      key={w}
                      type="button"
                      role="gridcell"
                      className={`fcell is-${cell.state}${selected === key ? ' is-selected' : ''}`}
                      aria-label={`${f.windowLabel(h)}, ${f.weightLabel(w)}: ${cell.rank !== null ? `Platz ${cell.rank} von ${cell.M}` : stateText[cell.state]}`}
                      onClick={() => updateParams(route, { zelle: selected === key ? null : key })}
                    >
                      {label(cell.state, cell.rank)}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
          </div>
          <p className="section-note">Spalten: Anteil Gleichmäßigkeit in Prozent (0 = reine Rendite, 100 = nur Gleichmäßigkeit). Seitlich wischen für alle elf Spalten; Zelle antippen für Details.</p>
          {sel ? (
            <div className="fm-detail" role="status" aria-live="polite">
              <strong>
                {f.windowLabel(sel.h)}, {f.weightLabel(sel.w)}
              </strong>
              <span>
                {sel.rank !== null ? `Platz ${sel.rank} von ${f.integer(sel.M)}` : stateText[sel.state]}
                {occDetail ? `, Score ${f.score(occDetail.score)}, Kursrendite ${f.pct(occDetail.r)}, ${f.dayRange(occDetail.start, freq.cutoff_day)}` : ''}
                {sel.rank !== null && sel.M < topK ? '. Kleines Vergleichsfeld.' : ''}
              </span>
              <div className="toolbar">
                {sel.state !== 'empty' ? (
                  <a className="btn btn-primary" href={buildHash('/ranking', { h: sel.h, w: sel.w, p: policy, n: sel.rank !== null && sel.rank > 10 ? (sel.rank > 50 ? 'alle' : '50') : null })}>
                    Rangliste öffnen
                  </a>
                ) : null}
                <a className="btn" href={buildHash(`/aktie/${isin}`, { h: sel.h, w: sel.w, p: policy })}>
                  Kurschart
                </a>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
