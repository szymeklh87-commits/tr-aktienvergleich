/* Kursverlauf mit Zeiträumen 1W, 1M, 3M, 6M, 1J und Max (ab 1.6).
 * Quelle: Tageskurse der Kursreihe, ab 1.6 ergänzt um die längere Tageshistorie (bis gut 1 Jahr) und –
 * für Aktien der Vorauswahl der Umschichtungs-Regel – Wochenkurse bis 3 Jahre. */

import { useState } from 'react';
import { PriceChart } from '../components/charts';
import { Pct, Segmented } from '../components/ui';
import type { Point } from '../lib/chartmath';
import * as f from '../lib/format';
import type { SeriesData } from '../lib/types';
import { berlinClock } from '../lib/intraday';

const RANGES = [
  { key: '1W', days: 7, label: '1 Woche' },
  { key: '1M', days: 31, label: '1 Monat' },
  { key: '3M', days: 92, label: '3 Monate' },
  { key: '6M', days: 183, label: '6 Monate' },
  { key: '1J', days: 366, label: '1 Jahr' },
  { key: 'Max', days: 100_000, label: 'gesamte Historie' },
] as const;

type RangeKey = (typeof RANGES)[number]['key'];

export interface LongHistory {
  verlauf?: { d: number[]; c: (number | null)[] } | null;
  wochen?: { d: number[]; c: (number | null)[] } | null;
}

/** Alle verfügbaren Kurse aufsteigend: Wochenkurse (älter), längere Tageshistorie, Kursreihe des Datenstands. */
export function allPoints(series: SeriesData | null, extra?: LongHistory | null): { pts: Point[]; weeklyUntil: number | null } {
  const byDay = new Map<number, Point>();
  const add = (day: number, close: number | null | undefined, volume: number | null = null) => {
    if (close === null || close === undefined || !Number.isFinite(close)) return;
    byDay.set(day, { day, close, open: null, high: null, low: null, volume, closeRaw: null });
  };
  const firstDaily = Math.min(series?.d[0] ?? Infinity, extra?.verlauf?.d[0] ?? Infinity);
  let weeklyUntil: number | null = null;
  extra?.wochen?.d.forEach((day, k) => {
    if (day < firstDaily) {
      add(day, extra.wochen!.c[k]);
      weeklyUntil = day;
    }
  });
  extra?.verlauf?.d.forEach((day, k) => add(day, extra.verlauf!.c[k]));
  series?.d.forEach((day, k) => add(day, series.c[k], series.v[k] ?? null));
  return { pts: [...byDay.values()].sort((a, b) => a.day - b.day), weeklyUntil };
}

export function RangeChart({ series, extra, unit, cutoff }: { series: SeriesData | null; extra?: LongHistory | null; unit: string | null; cutoff: number }) {
  const [range, setRange] = useState<RangeKey>('3M');
  const { pts, weeklyUntil } = allPoints(series, extra);
  if (pts.length < 2) return null;
  const first = pts[0].day;
  const available = RANGES.filter((r) => r.key === 'Max' || cutoff - r.days >= first - 5);
  const chosen = available.find((r) => r.key === range) ?? available[available.length - 1];
  const start = chosen.key === 'Max' ? first : cutoff - chosen.days;
  const shown = pts.filter((p) => p.day >= start && p.day <= cutoff);
  const change = shown.length >= 2 ? shown[shown.length - 1].close / shown[0].close - 1 : null;
  return (
    <section className="section" aria-labelledby="verlauf">
      <h2 className="section-title" id="verlauf">
        Kursverlauf
      </h2>
      <Segmented label="Zeitraum" hideLabel options={available.map((r) => ({ value: r.key, label: r.key, title: r.label }))} value={chosen.key} onChange={(value) => setRange(value as RangeKey)} />
      {change !== null ? (
        <div className="fig">
          <Pct value={change} strong />
          <span className="fig-label">
            {chosen.key === 'Max' ? 'seit' : `${chosen.label}:`} {f.day(shown[0].day)} bis {f.day(shown[shown.length - 1].day)}
          </span>
        </div>
      ) : null}
      <PriceChart
        title="Kursverlauf"
        pts={shown}
        gaps={[]}
        start={shown[0]?.day ?? start}
        end={cutoff}
        unit={unit}
        mode="absolut"
        showFit={false}
        publishedSlopePct={null}
        height={220}
        caption={
          <span>
            Splitbereinigte Tagesschlusskurse{weeklyUntil !== null && shown[0] && shown[0].day <= weeklyUntil ? `, vor dem ${f.day(weeklyUntil)} Wochenschlusskurse` : ''}. Längere Zeiträume
            erscheinen, sobald genug Historie geladen ist.
            {series?.provisional ? ` Letzter Punkt: vorläufiger Kurs von ${berlinClock(series.provisional.time_utc)} (Zwischenstand).` : ''}
          </span>
        }
      />
    </section>
  );
}
