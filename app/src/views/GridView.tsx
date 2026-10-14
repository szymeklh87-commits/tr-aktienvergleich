import { useEffect, useMemo, useState } from 'react';
import { MiniChart } from '../components/charts';
import { CompareBlock } from '../components/compare';
import { WeightControl, WindowRuler } from '../components/controls';
import { IconDownload } from '../components/icons';
import { ErrorNote, IsinCopy, Loading, Notice, Pager, Pct, SectionTitle, Segmented, ViewIntro } from '../components/ui';
import { transform, windowPoints, type Point, type ValueMode } from '../lib/chartmath';
import { statusInfo } from '../lib/codes';
import { downloadBlob, safeFilename } from '../lib/csv';
import { PNG_COLORS, renderPng, type PngPanel } from '../lib/exportpng';
import * as f from '../lib/format';
import { useFrequency, useOverview, useSeriesMany, useWindowHead } from '../lib/hooks';
import { idxList, instName, parseIsinList, unitOf } from '../lib/instruments';
import { buildHash, updateParams, type Route } from '../lib/router';
import { hasGroupB, memberIndex, parseGroup, parsePolicy, parseWeight, parseWindow, rankedEntries } from '../lib/scoring';
import type { SeriesData, WindowData } from '../lib/types';
import { useApp } from '../state/AppState';
import { PREVIEW } from '../lib/env';

type Source = 'ranking' | 'watchlist' | 'sieger' | 'haeufig' | 'isins' | 'alle';
type Mode = 'kacheln' | 'zeitraeume' | 'gemeinsam';
type Scale = 'index' | 'einzeln' | 'kurs';

const PAGE_SIZE: Record<Mode, number> = { kacheln: 12, zeitraeume: 6, gemeinsam: 8 };
const DEFAULT_COLUMNS = [1, 7, 14, 30, 60, 90];

function parseColumns(text: string | null, fallback: number[]): number[] {
  if (!text) return fallback;
  const list = text
    .split(',')
    .filter((x) => /^\d{1,2}$/.test(x.trim()))
    .map(Number)
    .filter((h) => Number.isInteger(h) && h >= 1 && h <= 90);
  const unique = [...new Set(list)].slice(0, 8);
  return unique.length ? unique : fallback;
}

interface Cell {
  pts: Point[];
  start: number | null;
  change: number | null;
  fallback: boolean;
}

function cellFor(series: SeriesData | undefined, h: number, cutoff: number): Cell | null {
  if (!series) return null;
  const { pts, start, fallback } = windowPoints(series, h, cutoff);
  const change = pts.length >= 2 ? pts[pts.length - 1].close / pts[0].close - 1 : null;
  return { pts, start, change, fallback };
}

function indexDomain(cells: (Cell | null)[], mode: ValueMode): [number, number] | null {
  let lo = Infinity;
  let hi = -Infinity;
  for (const cell of cells) {
    if (!cell || !cell.pts.length) continue;
    const base = cell.pts[0].close;
    for (const p of cell.pts) {
      const v = transform(p.close, base, mode);
      lo = Math.min(lo, v);
      hi = Math.max(hi, v);
    }
  }
  if (!Number.isFinite(lo)) return null;
  const neutral = mode === 'index' ? 100 : 0;
  lo = Math.min(lo, neutral);
  hi = Math.max(hi, neutral);
  const pad = (hi - lo) * 0.06 || 1;
  return [lo - pad, hi + pad];
}

export function GridView({ route }: { route: Route }) {
  const { manifest, instruments, isinIndex, watchlist, prefs, setPrefs, isDemo } = useApp();
  const sourceParam = route.params.get('quelle');
  const source: Source = (['ranking', 'watchlist', 'sieger', 'haeufig', 'isins', 'alle'] as Source[]).includes(sourceParam as Source) ? (sourceParam as Source) : 'ranking';
  const modeParam = route.params.get('modus');
  const mode: Mode = modeParam === 'zeitraeume' || modeParam === 'gemeinsam' ? modeParam : 'kacheln';
  const scaleParam = route.params.get('skala');
  const scale: Scale = scaleParam === 'einzeln' || scaleParam === 'kurs' ? scaleParam : 'index';
  const h = parseWindow(route.params.get('h'), prefs.h);
  const weight = parseWeight(route.params.get('w'), prefs.w);
  const policy = parsePolicy(route.params.get('p') ?? prefs.policy);
  const nParam = Number(route.params.get('n'));
  const topN = nParam === 25 || nParam === 50 ? nParam : 10;
  const columns = parseColumns(route.params.get('spalten'), prefs.gridColumns.length ? prefs.gridColumns : DEFAULT_COLUMNS);
  const page = Math.max(1, Number(route.params.get('seite') ?? 1) || 1);
  const manual = parseIsinList(route.params.get('isins'));
  const title = route.params.get('titel');
  const [isinDraft, setIsinDraft] = useState(manual.join(', '));
  const [addDraft, setAddDraft] = useState('');
  const [exporting, setExporting] = useState(false);

  const head = useWindowHead(h);
  const overview = useOverview();
  const frequency = useFrequency(source === 'haeufig');

  useEffect(() => {
    if (route.params.get('spalten') && columns.join(',') !== prefs.gridColumns.join(',')) setPrefs({ gridColumns: columns });
  }, [columns.join(',')]);

  const selection = useMemo<number[] | null>(() => {
    if (!instruments) return null;
    switch (source) {
      case 'ranking':
        return head.data ? rankedEntries(head.data, policy, weight, 0, topN, parseGroup(route.params.get('g')) === 'b' && hasGroupB(head.data) ? 'b' : 'a').map((e) => e.idx) : null;
      case 'watchlist':
        return idxList(isinIndex, watchlist);
      case 'sieger': {
        if (!overview.data) return null;
        const out: number[] = [];
        for (const row of overview.data.winners) for (const e of row.entries) if (!out.includes(e.idx)) out.push(e.idx);
        return out;
      }
      case 'haeufig':
        return frequency.data ? frequency.data.server_reference.entries.slice(0, 10).map((e) => e.idx) : null;
      case 'isins':
        return idxList(isinIndex, manual);
      case 'alle':
      default:
        return Array.from({ length: instruments.count }, (_, i) => i).filter((i) => instruments.has_series[i]);
    }
  }, [instruments, source, head.data, policy, weight, topN, watchlist, overview.data, frequency.data, manual.join(',')]);

  const pageSize = PAGE_SIZE[mode];
  const total = selection?.length ?? 0;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const current = Math.min(page, pages);
  const visible = selection ? selection.slice((current - 1) * pageSize, current * pageSize) : [];
  const loadIsins = mode === 'gemeinsam' || !instruments ? [] : visible.filter((i) => instruments.has_series[i]).map((i) => instruments.isin[i]);
  const many = useSeriesMany(loadIsins);

  if (!manifest || !instruments) return null;
  const cutoff = manifest.cutoff_day;
  const headInfo = (win: WindowData | null, idx: number) => {
    if (!win) return null;
    const pos = memberIndex(win).get(idx);
    if (pos === undefined) return null;
    return { r: win.m.r[pos], r2: win.m.r2[pos] };
  };
  const valueMode: ValueMode = scale === 'kurs' ? 'absolut' : 'index';
  const tileCells = visible.map((idx) => cellFor(many.data.get(instruments.isin[idx]), h, cutoff));
  const tileDomain = scale === 'index' ? indexDomain(tileCells, 'index') : null;
  const sourceLabel: Record<Source, string> = {
    ranking: `Top ${topN} der Rangliste (${f.windowLabel(h)}, ${f.weightLabel(weight)}${policy === 'common_trend' ? ', gleiches Feld' : ''})`,
    watchlist: 'Watchlist',
    sieger: 'Alle Renditesieger 1–90 Tage (ohne Doppelte)',
    haeufig: 'Häufigste Aktien (Top 10, alle Gewichtungen, nativ)',
    isins: title ?? 'Eigene ISIN-Auswahl',
    alle: 'Alle Aktien mit Kursdaten',
  };

  const setSource = (value: string) => {
    const [src, n] = value.split(':');
    updateParams(route, { quelle: src === 'ranking' ? null : src, n: src === 'ranking' && n !== '10' ? n : null, seite: null, titel: null });
  };

  const exportPng = async () => {
    setExporting(true);
    try {
      const panels: PngPanel[] = [];
      if (mode === 'kacheln') {
        visible.forEach((idx, k) => {
          const cell = tileCells[k];
          const unit = unitOf(instruments, idx);
          panels.push({
            title: instName(instruments, idx),
            subtitle: [
              `${instruments.isin[idx]}, ${scale === 'kurs' ? `Originalkurs in ${unit ?? '–'}` : 'Index: Start = 100'}`,
              cell && cell.pts.length ? `${f.windowLabel(h)}: ${f.dayRange(cell.pts[0].day, cell.pts[cell.pts.length - 1].day)}, Veränderung ${f.pct(cell.change)}` : 'Keine Kurse im Zeitraum',
            ],
            lines: cell && cell.pts.length ? [{ color: PNG_COLORS[0], points: cell.pts.map((p) => ({ day: p.day, value: transform(p.close, cell.pts[0].close, valueMode) })), gaps: many.data.get(instruments.isin[idx])?.gaps }] : [],
            xDomain: [cell?.start ?? cutoff - h, cutoff],
            yMode: valueMode,
            yDomain: tileDomain,
          });
        });
      } else if (mode === 'zeitraeume') {
        for (const idx of visible) {
          const series = many.data.get(instruments.isin[idx]);
          for (const colH of columns) {
            const cell = cellFor(series, colH, cutoff);
            panels.push({
              title: `${instName(instruments, idx)} – ${f.windowLabel(colH)}`,
              subtitle: [cell && cell.pts.length ? `${f.dayRange(cell.pts[0].day, cell.pts[cell.pts.length - 1].day)}, ${f.pct(cell.change)}, ${cell.pts.length} Tageskurse` : 'Keine Kurse'],
              lines: cell && cell.pts.length ? [{ color: PNG_COLORS[0], points: cell.pts.map((p) => ({ day: p.day, value: transform(p.close, cell.pts[0].close, 'index') })), gaps: series?.gaps }] : [],
              xDomain: [cell?.start ?? cutoff - colH, cutoff],
              yMode: 'index',
            });
          }
        }
      }
      const blob = await renderPng({
        heading: `Chart-Raster: ${sourceLabel[source]}`,
        meta: [
          `${mode === 'kacheln' ? `Gleicher Zeitraum: ${f.windowLabel(h)}` : `Zeiträume: ${columns.join(', ')} Kalendertage`}. Seite ${current} von ${pages}.`,
          `Kursstand ${f.day(cutoff)}, Snapshot ${manifest.snapshot_id}. Splitbereinigte Tagesschlusskurse, Quelle: ${manifest.provider.prices}${isDemo ? ' (DEMO – synthetische Testdaten)' : ''}.`,
        ],
        panels,
        columns: mode === 'kacheln' ? 3 : Math.min(columns.length, 4),
        panelWidth: mode === 'kacheln' ? 420 : 320,
        plotHeight: mode === 'kacheln' ? 150 : 110,
        footer: ['Momentaufnahme der historischen Tagesschlusskurse; keine Liveansicht, keine Prognose. Index 100 ist kein Eurobetrag.'],
      });
      downloadBlob(safeFilename(`chart-raster_${mode}_${manifest.snapshot_id}_s${current}.png`), blob);
    } finally {
      setExporting(false);
    }
  };

  const addColumn = () => {
    const value = Number(addDraft);
    if (!Number.isInteger(value) || value < 1 || value > 90) return;
    const next = [...new Set([...columns, value])].sort((a, b) => a - b).slice(0, 8);
    setAddDraft('');
    updateParams(route, { spalten: next.join(',') });
  };

  const selectionError = source === 'ranking' ? head.error : source === 'sieger' ? overview.error : source === 'haeufig' ? frequency.error : null;

  return (
    <div className="view">
      <header className="view-head">
        <ViewIntro>
          <p className="lede">Kursverläufe mehrerer Aktien nebeneinander. Die Auswahl und Reihenfolge können aus einer Rangliste stammen; die Kursdaten einer Aktie sind in jeder Gewichtung dieselben.</p>
        </ViewIntro>
      </header>

      <label className="field">
        <span className="field-label">Auswahl</span>
        <select className="select" value={source === 'ranking' ? `ranking:${topN}` : source} onChange={(e: Event) => setSource((e.target as HTMLSelectElement).value)}>
          <option value="ranking:10">Top 10 der Rangliste</option>
          <option value="ranking:25">Top 25 der Rangliste</option>
          <option value="ranking:50">Top 50 der Rangliste</option>
          <option value="watchlist">Watchlist ({watchlist.length})</option>
          <option value="sieger">Alle Renditesieger 1–90 Tage</option>
          <option value="haeufig">Häufigste Aktien (Top 10)</option>
          <option value="isins">Eigene ISIN-Liste</option>
          <option value="alle">Alle Aktien mit Kursdaten (seitenweise)</option>
        </select>
      </label>

      {source === 'isins' ? (
        <form
          className="field"
          onSubmit={(e: Event) => {
            e.preventDefault();
            updateParams(route, { isins: parseIsinList(isinDraft).join(',') || null, titel: null, seite: null });
          }}
        >
          <label className="field-label" htmlFor="isin-liste">
            ISINs (durch Komma oder Leerzeichen getrennt)
          </label>
          <textarea id="isin-liste" className="input" rows={3} value={isinDraft} onChange={(e: Event) => setIsinDraft((e.target as HTMLTextAreaElement).value)} />
          <div className="toolbar">
            <button type="submit" className="btn btn-primary">
              Auswahl übernehmen
            </button>
          </div>
          {manual.length && manual.length !== idxList(isinIndex, manual).length ? (
            <p className="section-note">Nicht in diesem Datenstand: {manual.filter((isin) => !isinIndex.has(isin)).join(', ')}</p>
          ) : null}
        </form>
      ) : null}

      <WindowRuler value={h} onChange={(next) => updateParams(route, { h: next, seite: source === 'ranking' ? null : route.params.get('seite') })} compact>
        <p>{mode === 'zeitraeume' ? 'Bestimmt die Rangliste für die Auswahl; die Spalten unten haben eigene Zeiträume.' : 'Gilt für alle Kacheln und die Auswahl aus der Rangliste.'}</p>
      </WindowRuler>
      {source === 'ranking' ? <WeightControl weight={weight} onWeight={(w) => updateParams(route, { w, seite: null })} policy={policy} onPolicy={(p) => updateParams(route, { p, seite: null })} /> : null}

      <Segmented
        label="Darstellung"
        options={[
          { value: 'kacheln', label: 'Gleicher Zeitraum' },
          { value: 'zeitraeume', label: 'Mehrere Zeiträume' },
          { value: 'gemeinsam', label: 'Gemeinsam' },
        ]}
        value={mode}
        onChange={(value) => updateParams(route, { modus: value === 'kacheln' ? null : value, seite: null })}
      />

      {mode === 'kacheln' ? (
        <Segmented
          label="Skala"
          options={[
            { value: 'index', label: 'Vergleichbar (Index)' },
            { value: 'einzeln', label: 'Index, je Kachel' },
            { value: 'kurs', label: 'Originalkurs' },
          ]}
          value={scale}
          onChange={(value) => updateParams(route, { skala: value === 'index' ? null : value })}
        />
      ) : null}

      {mode === 'zeitraeume' ? (
        <div className="field">
          <span className="field-label">Spalten (Kalendertage)</span>
          <div className="chips">
            {columns.map((c) => (
              <button
                key={c}
                type="button"
                className="chip is-active"
                aria-label={`Spalte ${c} Tage entfernen`}
                disabled={columns.length <= 1}
                onClick={() => updateParams(route, { spalten: columns.filter((x) => x !== c).join(',') })}
              >
                {c} T ×
              </button>
            ))}
          </div>
          <form
            className="toolbar"
            onSubmit={(e: Event) => {
              e.preventDefault();
              addColumn();
            }}
          >
            <label className="visually-hidden" htmlFor="spalte-neu">
              Zeitraum hinzufügen (1 bis 90 Tage)
            </label>
            <input id="spalte-neu" className="input" style={{ width: '7em' }} type="number" inputMode="numeric" min={1} max={90} placeholder="Tage" value={addDraft} onChange={(e: Event) => setAddDraft((e.target as HTMLInputElement).value)} />
            <button type="submit" className="btn" disabled={columns.length >= 8}>
              Spalte hinzufügen
            </button>
            <button type="button" className="btn btn-quiet" onClick={() => updateParams(route, { spalten: DEFAULT_COLUMNS.join(',') })}>
              Standard
            </button>
          </form>
        </div>
      ) : null}

      <p className="section-note">
        {sourceLabel[source]}: {f.plural(total, 'Aktie', 'Aktien')}
        {pages > 1 ? `, Seite ${current} von ${pages}` : ''}. Kursstand {f.day(cutoff)}.
        {mode === 'kacheln' && scale === 'index' ? ' Alle Kacheln: Index mit Startwert 100 und gemeinsamer Skala.' : ''}
        {mode === 'kacheln' && scale === 'einzeln' ? ' Index mit Startwert 100, Skala je Kachel automatisch – die Steilheit ist zwischen Kacheln nicht vergleichbar.' : ''}
        {mode === 'kacheln' && scale === 'kurs' ? ' Originalkurs in Notierungswährung, Skala je Kachel automatisch – zum Vergleich die Prozentwerte lesen.' : ''}
      </p>

      {selectionError ? <ErrorNote error={selectionError} /> : null}
      {selection === null && !selectionError ? <Loading height={400} label="Auswahl wird geladen" /> : null}
      {selection !== null && total === 0 ? (
        <Notice tone="info" title="Keine Aktien in dieser Auswahl">
          <p>{source === 'watchlist' ? 'Die Watchlist ist leer. In jeder Liste lässt sich eine Aktie mit dem Stern merken.' : source === 'isins' ? 'Bitte gültige ISINs eingeben.' : 'Für diese Auswahl gibt es keine Rangliste.'}</p>
        </Notice>
      ) : null}

      {selection !== null && total > 0 && mode === 'kacheln' ? (
        <ul className="tiles" aria-label="Kacheln">
          {visible.map((idx, k) => {
            const isin = instruments.isin[idx];
            const series = many.data.get(isin);
            const cell = tileCells[k];
            const info = headInfo(source === 'ranking' ? head.data : head.data, idx);
            const status = series ? series.window_status[h - 1] : null;
            const unit = unitOf(instruments, idx);
            const lastPt = cell?.pts[cell.pts.length - 1];
            return (
              <li key={idx} className="tile">
                <div className="tile-head">
                  <a className="tile-name row-link" href={buildHash(`/aktie/${isin}`, { h, w: weight, p: policy })}>
                    {instName(instruments, idx)}
                  </a>
                  <span className="muted small">{source === 'ranking' ? `Platz ${(current - 1) * pageSize + k + 1}` : ''}</span>
                </div>
                <div className="row-meta">
                  <IsinCopy isin={isin} compact />
                </div>
                {!instruments.has_series[idx] ? (
                  <div className="mini-empty" style={{ height: 96 }}>
                    Keine Kursdaten: {statusInfo(manifest, instruments.level_status[idx]).kurz}
                  </div>
                ) : many.errors.has(isin) ? (
                  <div className="mini-empty" style={{ height: 96 }}>
                    Kursreihe nicht verfügbar (offline?)
                  </div>
                ) : !cell ? (
                  <div className="placeholder" style={{ height: 96 }} aria-hidden="true" />
                ) : (
                  <MiniChart
                    pts={cell.pts}
                    gaps={series?.gaps ?? []}
                    height={96}
                    mode={valueMode}
                    yDomain={tileDomain}
                    xDomain={[cell.start ?? cutoff - h, cutoff]}
                    label={`${instName(instruments, idx)}: ${f.windowLabel(h)}, Veränderung ${f.pct(cell.change)}`}
                  />
                )}
                <div className="tile-figs">
                  {cell ? <Pct value={cell.change} strong /> : null}
                  {info?.r2 !== null && info?.r2 !== undefined ? <span>R² {f.r2(info.r2)}</span> : null}
                  {lastPt ? <span>Kurs {f.price(lastPt.close, unit)}</span> : null}
                </div>
                <p className="tile-foot">
                  {cell && cell.pts.length
                    ? `${f.dayRange(cell.pts[0].day, cell.pts[cell.pts.length - 1].day)}, ${f.plural(cell.pts.length, 'Tageskurs', 'Tageskurse')}${h === 1 ? ', keine Intradaydaten' : ''}`
                    : 'Keine Kurse im Zeitraum'}
                  {cell?.fallback ? '. Kein gültiger Startkurs für das Ranking; gezeigt wird die verfügbare Historie.' : ''}
                  {status !== null && status !== undefined && status < 15 ? `. Ranking: ${statusInfo(manifest, status).kurz}` : ''}
                </p>
              </li>
            );
          })}
        </ul>
      ) : null}

      {selection !== null && total > 0 && mode === 'zeitraeume' ? (
        <div className="table-wrap" role="region" aria-label="Aktien mal Zeiträume, seitlich blätterbar" tabIndex={0}>
          <table className="wmatrix">
            <thead>
              <tr>
                <th className="sticky" scope="col">
                  Aktie
                </th>
                {columns.map((c) => (
                  <th key={c} scope="col">
                    {f.windowLabel(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((idx) => {
                const isin = instruments.isin[idx];
                const series = many.data.get(isin);
                return (
                  <tr key={idx}>
                    <th scope="row" className="sticky">
                      <a href={buildHash(`/aktie/${isin}`, { h })}>{instName(instruments, idx)}</a>
                      <br />
                      <span className="muted small">{isin}</span>
                    </th>
                    {columns.map((c) => {
                      if (!instruments.has_series[idx]) {
                        return (
                          <td key={c}>
                            <span className="muted">keine Kursdaten</span>
                          </td>
                        );
                      }
                      const cell = cellFor(series, c, cutoff);
                      const columnCells = visible.map((j) => cellFor(many.data.get(instruments.isin[j]), c, cutoff));
                      const starts = columnCells.map((x) => x?.start).filter((x): x is number => x !== null && x !== undefined);
                      const xDomain: [number, number] = [starts.length ? Math.min(...starts) : cutoff - c, cutoff];
                      return (
                        <td key={c}>
                          <a className="wcell" href={buildHash(`/aktie/${isin}`, { h: c })}>
                            {cell ? (
                              <MiniChart pts={cell.pts} gaps={series?.gaps ?? []} height={56} mode="index" yDomain={indexDomain(columnCells, 'index')} xDomain={xDomain} label={`${f.windowLabel(c)}: ${f.pct(cell.change)}`} />
                            ) : (
                              <span className="placeholder" style={{ height: 56, display: 'block' }} aria-hidden="true" />
                            )}
                            <Pct value={cell?.change ?? null} />
                            <span className="muted">
                              {cell && cell.pts.length ? `${f.dayShort(cell.pts[0].day)}–${f.dayShort(cell.pts[cell.pts.length - 1].day)}, ${cell.pts.length} Kurse` : 'keine Kurse'}
                            </span>
                            {c === 1 ? <span className="muted">nur Tagesschlusskurse</span> : null}
                          </a>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {selection !== null && total > 0 && mode === 'gemeinsam' ? (
        <section className="section">
          <SectionTitle>Auswahl gemeinsam vergleichen</SectionTitle>
          <CompareBlock
            isins={visible.filter((i) => instruments.has_series[i]).map((i) => instruments.isin[i])}
            h={h}
            cutoffDay={cutoff}
            rankingReturns={head.data ? new Map(visible.map((i) => [instruments.isin[i], headInfo(head.data, i)?.r]).filter((x): x is [string, number] => x[1] !== undefined)) : undefined}
          />
        </section>
      ) : null}

      <Pager page={current} pages={pages} onChange={(p) => updateParams(route, { seite: p })} label="Seiten des Rasters" />

      {!PREVIEW && mode !== 'gemeinsam' && total > 0 ? (
        <div className="toolbar no-print">
          <button type="button" className="btn" disabled={exporting || many.pending > 0} onClick={() => void exportPng()}>
            <IconDownload /> {exporting ? 'PNG wird erstellt …' : 'Diese Seite als PNG'}
          </button>
          <button type="button" className="btn btn-quiet" onClick={() => window.print()}>
            Drucken
          </button>
        </div>
      ) : null}
    </div>
  );
}
