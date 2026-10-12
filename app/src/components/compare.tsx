import { useMemo, useState } from 'react';
import { commonBase, points, valueAt } from '../lib/chartmath';
import { assignSlots, MAX_SERIES } from '../lib/colors';
import * as f from '../lib/format';
import { useSeriesMany } from '../lib/hooks';
import { instName } from '../lib/instruments';
import type { SeriesData } from '../lib/types';
import { useApp } from '../state/AppState';
import { CompareChart, type CompareLine } from './charts';
import { Disclosure, Loading, Notice } from './ui';

export interface CompareResult {
  baseDay: number;
  shifted: boolean;
  lines: CompareLine[];
}

/** Gemeinsamer Basistag ohne Auffüllen; Basispreis ist der echte Schlusskurs an diesem Tag. */
export function buildCompare(list: SeriesData[], h: number, cutoffDay: number, names: Map<string, string>, slots: Record<string, number>): CompareResult | { error: string } {
  const base = commonBase(list, h, cutoffDay);
  if (base.day === null) return { error: base.reason ?? 'Kein gemeinsamer Basiszeitpunkt' };
  const day = base.day;
  const lines: CompareLine[] = [];
  for (const series of list) {
    const basePrice = valueAt(series, day);
    if (basePrice === null) continue;
    lines.push({
      isin: series.isin,
      name: names.get(series.isin) ?? series.isin,
      slot: slots[series.isin] ?? 0,
      pts: points(series).filter((p) => p.day >= day && p.day <= cutoffDay),
      basePrice,
      currency: series.listing.price_unit ?? series.listing.currency,
    });
  }
  return { baseDay: day, shifted: base.shifted, lines };
}

/** „Auswahl gemeinsam vergleichen“: höchstens acht indexierte Linien mit Legende und Tabelle. */
export function CompareBlock({ isins, h, cutoffDay, rankingReturns }: { isins: string[]; h: number; cutoffDay: number; rankingReturns?: Map<string, number> }) {
  const { instruments, isinIndex } = useApp();
  const shown = isins.slice(0, MAX_SERIES);
  const many = useSeriesMany(shown);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [highlight, setHighlight] = useState<string | null>(null);
  const slots = useMemo(() => assignSlots({}, shown), [shown.join(',')]);
  if (!instruments) return null;
  const names = new Map(shown.map((isin) => [isin, instName(instruments, isinIndex.get(isin) ?? -1) ?? isin]));
  const list = shown.map((isin) => many.data.get(isin)).filter((s): s is SeriesData => Boolean(s));
  const missing = shown.filter((isin) => many.errors.has(isin));
  if (many.pending > 0) return <Loading height={360} label="Kursverläufe werden geladen" />;
  if (!list.length) return <Notice tone="info" title="Keine Kursdaten"><p>Für die Auswahl liegen keine Kursreihen vor.</p></Notice>;
  const result = buildCompare(list, h, cutoffDay, names, slots);
  if ('error' in result) {
    return (
      <Notice tone="info" title="Kein synchroner Vergleich möglich">
        <p>{result.error}. Die Einzelcharts bleiben im Raster verfügbar.</p>
      </Notice>
    );
  }
  const toggle = (isin: string) => {
    const next = new Set(hidden);
    if (next.has(isin)) next.delete(isin);
    else next.add(isin);
    setHidden(next);
  };
  return (
    <div className="chart-block">
      {result.shifted ? (
        <Notice tone="info" title={`Vergleich beginnt am ${f.day(result.baseDay)} wegen gemeinsamer Datenverfügbarkeit`}>
          <p>Die Rankingrenditen der einzelnen Aktien bleiben unverändert; die Vergleichsrendite unten bezieht sich auf diesen Basistag.</p>
        </Notice>
      ) : null}
      {isins.length > MAX_SERIES ? (
        <p className="section-note">
          Gezeigt werden die ersten {MAX_SERIES} von {isins.length} ausgewählten Aktien, damit die Linien unterscheidbar bleiben. Alle Aktien bleiben im Raster erreichbar.
        </p>
      ) : null}
      <CompareChart lines={result.lines} baseDay={result.baseDay} end={cutoffDay} hidden={hidden} highlight={highlight} onHighlight={setHighlight} onToggle={toggle} />
      <p className="section-note">
        Indexiert: 100 = echter Schlusskurs am gemeinsamen Basistag {f.dayWithWeekday(result.baseDay)}; eine Linie bei 125 bedeutet +25 % seit diesem Tag. 100 ist kein Eurobetrag, Währungen werden nicht umgerechnet. Stand: {f.day(cutoffDay)}.
      </p>
      {missing.length ? <p className="section-note">Ohne Kursreihe: {missing.join(', ')}.</p> : null}
      <Disclosure summary="Vergleich als Tabelle">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Aktie</th>
                <th className="n">Basiskurs</th>
                <th className="n">Letzter Kurs</th>
                <th className="n">Vergleich</th>
                {rankingReturns ? <th className="n">Ranking</th> : null}
              </tr>
            </thead>
            <tbody>
              {result.lines.map((line) => {
                const last = line.pts[line.pts.length - 1];
                return (
                  <tr key={line.isin}>
                    <td>
                      {line.name}
                      <br />
                      <span className="muted">{line.isin}</span>
                    </td>
                    <td className="n">{f.price(line.basePrice, line.currency)}</td>
                    <td className="n">{last ? f.price(last.close, line.currency) : '–'}</td>
                    <td className="n">{last ? f.pct(last.close / line.basePrice - 1) : '–'}</td>
                    {rankingReturns ? <td className="n">{rankingReturns.has(line.isin) ? f.pct(rankingReturns.get(line.isin)) : '–'}</td> : null}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Disclosure>
    </div>
  );
}
