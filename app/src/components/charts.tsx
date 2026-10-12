/* Kursgrafiken aus echten numerischen Tageskursen.
 * Linien verbinden tatsächliche Beobachtungen; an erwarteten, aber fehlenden Sitzungen wird
 * die Linie unterbrochen und die Lücke markiert. Tooltips zeigen nur echte Datenpunkte. */

import { scaleLinear, scaleUtc } from 'd3-scale';
import { line } from 'd3-shape';
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { fitLine, fitMatches, nearestIndex, segments, transform, type Point, type ValueMode } from '../lib/chartmath';
import { prefersDark, seriesColor } from '../lib/colors';
import * as f from '../lib/format';
import { IconMinus, IconPlus, IconReset } from './icons';

const DAY = 86_400_000;
const toDate = (day: number) => new Date(day * DAY);
const shortFmt = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', timeZone: 'UTC' });
const monthFmt = new Intl.DateTimeFormat('de-DE', { month: 'short', timeZone: 'UTC' });

/** Gemessene Breite eines Elements (Callback-Ref: funktioniert auch, wenn das Element erst später erscheint). */
function useWidth<T extends HTMLElement>(minimum = 240): [(el: T | null) => void, number] {
  const [element, setElement] = useState<T | null>(null);
  const [width, setWidth] = useState(Math.max(minimum, 320));
  useEffect(() => {
    if (!element) return;
    const update = () => setWidth(Math.max(minimum, Math.floor(element.getBoundingClientRect().width)));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [element, minimum]);
  return [setElement, width];
}

function useDark(): boolean {
  const [dark, setDark] = useState(() => prefersDark());
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    const update = () => setDark(prefersDark());
    media?.addEventListener('change', update);
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => {
      media?.removeEventListener('change', update);
      observer.disconnect();
    };
  }, []);
  return dark;
}

function niceTicks(domain: [number, number], count: number): number[] {
  return scaleLinear().domain(domain).nice(count).ticks(count);
}

function formatAxis(value: number, mode: ValueMode): string {
  if (mode === 'prozent') return `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`;
  if (Math.abs(value) >= 10000) return value.toLocaleString('de-DE', { notation: 'compact', maximumFractionDigits: 1 });
  return value.toLocaleString('de-DE', { maximumSignificantDigits: 4 });
}

export interface PriceChartProps {
  title: string;
  pts: Point[];
  gaps: number[];
  start: number | null;
  end: number;
  unit: string | null;
  mode: ValueMode;
  publishedSlopePct?: number | null;
  showFit?: boolean;
  candles?: boolean;
  height?: number;
  caption?: ReactNode;
}

/** Großer Einzelchart mit Fadenkreuz, Tastatursteuerung, Zoom (Knöpfe, Zwei-Finger) und Verschieben. */
export function PriceChart({ title, pts, gaps, start, end, unit, mode, publishedSlopePct, showFit = true, candles = false, height = 260, caption }: PriceChartProps) {
  const [wrapRef, width] = useWidth<HTMLDivElement>();
  const dark = useDark();
  const clipId = `clip${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const [hover, setHover] = useState<number | null>(null);
  const [view, setView] = useState<[number, number] | null>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<{ dist: number; view: [number, number]; x: number } | null>(null);
  const margin = { top: 12, right: 12, bottom: 28, left: 52 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;

  const base = pts.length ? pts[0].close : 1;
  const full: [number, number] = pts.length ? [pts[0].day, pts[pts.length - 1].day] : [end - 1, end];
  const domain = view ?? full;
  const visible = pts.filter((p) => p.day >= domain[0] && p.day <= domain[1]);
  useEffect(() => setView(null), [pts.length, start, end]);

  const x = useMemo(() => scaleUtc().domain([toDate(domain[0]), toDate(domain[1] === domain[0] ? domain[0] + 1 : domain[1])]).range([0, innerW]), [domain[0], domain[1], innerW]);
  const values = visible.flatMap((p) => (candles && p.high !== null && p.low !== null ? [p.high, p.low] : [p.close])).map((v) => transform(v, base, mode));
  let lo = values.length ? Math.min(...values) : 0;
  let hi = values.length ? Math.max(...values) : 1;
  if (lo === hi) {
    lo -= Math.abs(lo) * 0.01 || 1;
    hi += Math.abs(hi) * 0.01 || 1;
  }
  const pad = (hi - lo) * 0.08;
  const y = scaleLinear().domain([lo - pad, hi + pad]).range([innerH, 0]).nice(5);
  const color = seriesColor(0, dark);
  const segs = segments(pts, gaps).map((seg) => seg.filter((p) => p.day >= domain[0] - 7 && p.day <= domain[1] + 7));
  const path = line<Point>()
    .x((p) => x(toDate(p.day)))
    .y((p) => y(transform(p.close, base, mode)));
  const fit = showFit && start !== null && pts.length >= 15 ? fitLine(pts) : null;
  const fitOk = fitMatches(fit, publishedSlopePct ?? null);
  const span = domain[1] - domain[0];
  const xTicks = x.ticks(Math.max(2, Math.floor(innerW / 80)));
  const yTicks = niceTicks(y.domain() as [number, number], 5);
  const days = pts.map((p) => p.day);
  const hovered = hover !== null ? pts[hover] : null;
  const visibleGaps = gaps.filter((d) => d >= domain[0] && d <= domain[1]);

  const pickAt = (clientX: number, rect: DOMRect) => {
    const px = clientX - rect.left - margin.left;
    const day = x.invert(px).getTime() / DAY;
    const i = nearestIndex(days, day);
    if (i >= 0) setHover(i);
  };

  const zoom = (factor: number, centerDay?: number) => {
    const [a, b] = domain;
    const center = centerDay ?? (a + b) / 2;
    const width2 = Math.max(4, (b - a) / factor);
    let na = center - (center - a) / factor;
    let nb = na + width2;
    if (na < full[0]) {
      na = full[0];
      nb = na + width2;
    }
    if (nb > full[1]) {
      nb = full[1];
      na = Math.max(full[0], nb - width2);
    }
    setView(nb - na >= full[1] - full[0] ? null : [na, nb]);
  };

  const onPointerDown = (e: PointerEvent) => {
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 2) {
      const [p1, p2] = [...pointers.current.values()];
      gesture.current = { dist: Math.hypot(p1.x - p2.x, p1.y - p2.y), view: domain, x: (p1.x + p2.x) / 2 };
    } else {
      gesture.current = { dist: 0, view: domain, x: e.clientX };
      pickAt(e.clientX, (e.currentTarget as Element).getBoundingClientRect());
    }
  };
  const onPointerMove = (e: PointerEvent) => {
    const rect = (e.currentTarget as Element).getBoundingClientRect();
    if (!pointers.current.has(e.pointerId)) {
      if (e.pointerType === 'mouse') pickAt(e.clientX, rect);
      return;
    }
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const g = gesture.current;
    if (pointers.current.size === 2 && g && g.dist > 0) {
      const [p1, p2] = [...pointers.current.values()];
      const dist = Math.hypot(p1.x - p2.x, p1.y - p2.y);
      const factor = dist / g.dist;
      const center = x.invert(g.x - rect.left - margin.left).getTime() / DAY;
      const [a, b] = g.view;
      const width2 = Math.min(full[1] - full[0], Math.max(4, (b - a) / factor));
      let na = center - ((center - a) / (b - a)) * width2;
      na = Math.max(full[0], Math.min(na, full[1] - width2));
      setView(width2 >= full[1] - full[0] ? null : [na, na + width2]);
      return;
    }
    if (view && g && e.pointerType !== 'mouse') {
      const shift = ((g.x - e.clientX) / innerW) * (g.view[1] - g.view[0]);
      let na = g.view[0] + shift;
      const w2 = g.view[1] - g.view[0];
      na = Math.max(full[0], Math.min(na, full[1] - w2));
      setView([na, na + w2]);
      return;
    }
    pickAt(e.clientX, rect);
  };
  const onPointerUp = (e: PointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) gesture.current = null;
  };
  const onKey = (e: KeyboardEvent) => {
    if (!pts.length) return;
    let handled = true;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      const current = hover ?? (e.key === 'ArrowLeft' ? pts.length : -1);
      setHover(Math.min(pts.length - 1, Math.max(0, current + (e.key === 'ArrowLeft' ? -1 : 1))));
    } else if (e.key === 'Home') setHover(0);
    else if (e.key === 'End') setHover(pts.length - 1);
    else if (e.key === 'Escape') setHover(null);
    else if (e.key === '+') zoom(1.5);
    else if (e.key === '-') zoom(1 / 1.5);
    else handled = false;
    // Bediente Tasten dürfen die Seite nicht zusätzlich scrollen (Pos1/Ende springen sonst ans Seitenende).
    if (handled) e.preventDefault();
  };

  const first = pts[0];
  const last = pts[pts.length - 1];
  const summary = pts.length
    ? `${title}: Schlusskurs ${f.price(first.close, unit)} am ${f.day(first.day)} und ${f.price(last.close, unit)} am ${f.day(last.day)}, Veränderung ${f.pct(last.close / first.close - 1)}. ${pts.length} echte Tageskurse${gaps.length ? `, ${gaps.length} fehlende erwartete Sitzungen` : ''}.`
    : `${title}: keine Kursdaten im gewählten Zeitraum.`;

  return (
    <figure className="chart" aria-label={summary}>
      <div className="chart-toolbar" role="group" aria-label="Zoom">
        <button type="button" className="icon-btn" onClick={() => zoom(1.5)} aria-label="Vergrößern" disabled={span <= 4}>
          <IconPlus />
        </button>
        <button type="button" className="icon-btn" onClick={() => zoom(1 / 1.5)} aria-label="Verkleinern" disabled={!view}>
          <IconMinus />
        </button>
        <button type="button" className="icon-btn" onClick={() => setView(null)} aria-label="Ansicht zurücksetzen" disabled={!view}>
          <IconReset />
        </button>
        {view ? <span className="chart-zoom-note">Ausschnitt {f.dayShort(Math.ceil(domain[0]))} – {f.dayShort(Math.floor(domain[1]))}</span> : null}
      </div>
      <div ref={wrapRef} className="chart-surface" style={{ height }}>
        <svg width={width} height={height} role="img" aria-label={summary}>
          <g transform={`translate(${margin.left},${margin.top})`}>
            {yTicks.map((t) => (
              <g key={t} transform={`translate(0,${y(t)})`}>
                <line x1={0} x2={innerW} className="grid" />
                <text x={-8} dy="0.32em" textAnchor="end" className="axis-label">
                  {formatAxis(t, mode)}
                </text>
              </g>
            ))}
            {mode !== 'absolut' ? <line x1={0} x2={innerW} y1={y(mode === 'index' ? 100 : 0)} y2={y(mode === 'index' ? 100 : 0)} className="baseline" /> : null}
            {xTicks.map((t) => (
              <text key={t.getTime()} x={x(t)} y={innerH + 18} textAnchor="middle" className="axis-label">
                {span > 120 ? monthFmt.format(t) : shortFmt.format(t)}
              </text>
            ))}
            <line x1={0} x2={innerW} y1={innerH} y2={innerH} className="axis" />
            <clipPath id={clipId}>
              <rect x={0} y={-4} width={innerW} height={innerH + 8} />
            </clipPath>
            <g clipPath={`url(#${clipId})`}>
              {candles
                ? visible.map((p) => {
                    if (p.open === null || p.high === null || p.low === null) return null;
                    const cx = x(toDate(p.day));
                    const bodyW = Math.max(2, Math.min(10, (innerW / Math.max(1, visible.length)) * 0.6));
                    const up = p.close >= p.open;
                    const o = y(transform(p.open, base, mode));
                    const c = y(transform(p.close, base, mode));
                    return (
                      <g key={p.day} className={up ? 'candle candle-up' : 'candle candle-down'}>
                        <line x1={cx} x2={cx} y1={y(transform(p.high, base, mode))} y2={y(transform(p.low, base, mode))} />
                        <rect x={cx - bodyW / 2} width={bodyW} y={Math.min(o, c)} height={Math.max(1, Math.abs(o - c))} />
                      </g>
                    );
                  })
                : segs.map((seg, i) => (seg.length > 1 ? <path key={i} d={path(seg) ?? ''} className="price-line" stroke={color} /> : null))}
              {!candles && segs.some((s) => s.length === 1)
                ? segs.filter((s) => s.length === 1).map((s) => <circle key={s[0].day} cx={x(toDate(s[0].day))} cy={y(transform(s[0].close, base, mode))} r={4} fill={color} className="ringed" />)
                : null}
              {!candles && pts.length <= 12
                ? pts.map((p) => <circle key={`d${p.day}`} cx={x(toDate(p.day))} cy={y(transform(p.close, base, mode))} r={4} fill={color} className="ringed" />)
                : null}
              {fit && fitOk ? (
                <line
                  className="fit-line"
                  x1={x(toDate(pts[0].day))}
                  x2={x(toDate(pts[pts.length - 1].day))}
                  y1={y(transform(fit.b, base, mode))}
                  y2={y(transform(fit.m * (pts.length - 1) + fit.b, base, mode))}
                />
              ) : null}
              {visibleGaps.map((d) => (
                <line key={`gap${d}`} className="gap-mark" x1={x(toDate(d))} x2={x(toDate(d))} y1={innerH - 6} y2={innerH} />
              ))}
            </g>
            {hovered ? (
              <g>
                <line className="crosshair" x1={x(toDate(hovered.day))} x2={x(toDate(hovered.day))} y1={0} y2={innerH} />
                <circle cx={x(toDate(hovered.day))} cy={y(transform(hovered.close, base, mode))} r={5} fill={color} className="ringed" />
              </g>
            ) : null}
            <rect
              className="hit"
              x={0}
              y={0}
              width={innerW}
              height={innerH}
              tabIndex={0}
              aria-label="Diagramm: mit Pfeiltasten durch die Tageskurse bewegen, Plus und Minus zum Zoomen"
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
              onPointerCancel={onPointerUp}
              onPointerLeave={(e: PointerEvent) => {
                if (e.pointerType === 'mouse') setHover(null);
              }}
              onKeyDown={onKey}
            />
          </g>
        </svg>
        {hovered ? (
          <div className="tooltip" style={{ left: Math.min(width - 190, Math.max(0, margin.left + x(toDate(hovered.day)) - 90)) }} role="status" aria-live="polite">
            <strong>{mode === 'absolut' ? f.price(hovered.close, unit) : mode === 'index' ? `${f.score(transform(hovered.close, base, mode))} (Index)` : f.signedPctValue(transform(hovered.close, base, mode))}</strong>
            <span>{f.dayWithWeekday(hovered.day)} · Schlusskurs</span>
            {mode !== 'absolut' ? <span>Kurs {f.price(hovered.close, unit)}</span> : null}
            {candles && hovered.open !== null ? (
              <span>
                E {f.price(hovered.open)} · H {f.price(hovered.high)} · T {f.price(hovered.low)}
              </span>
            ) : null}
            <span>Volumen {f.volume(hovered.volume)}</span>
          </div>
        ) : null}
      </div>
      <figcaption className="chart-caption">
        {caption}
        {fit && !fitOk && publishedSlopePct !== undefined && publishedSlopePct !== null ? (
          <span className="muted"> Anpassungsgerade ausgeblendet: Abweichung zur veröffentlichten Kennzahl.</span>
        ) : null}
        {fit && fitOk ? <span className="legend-key"><span className="key-line key-fit" aria-hidden="true" /> Anpassung an vergangene Kurse (endet am Stichtag, keine Prognose)</span> : null}
        {gaps.length ? <span className="legend-key"><span className="key-gap" aria-hidden="true" /> Lücke: erwartete Börsensitzung ohne gültigen Kurs</span> : null}
      </figcaption>
    </figure>
  );
}

/** Kleine Kachel-Grafik (Small Multiple). */
export function MiniChart({
  pts,
  gaps,
  yDomain,
  xDomain,
  height = 64,
  label,
  base,
  mode = 'absolut',
  slot = 0,
  emptyText = 'Keine Kurse im Zeitraum',
}: {
  pts: Point[];
  gaps: number[];
  yDomain?: [number, number] | null;
  xDomain?: [number, number] | null;
  height?: number;
  label: string;
  base?: number;
  mode?: ValueMode;
  slot?: number;
  emptyText?: string;
}) {
  const dark = useDark();
  const [wrapRef, w] = useWidth<HTMLDivElement>(120);
  if (!pts.length) {
    return (
      <div className="mini-empty" style={{ height }}>
        {emptyText}
      </div>
    );
  }
  const b = base ?? pts[0].close;
  const vals = pts.map((p) => transform(p.close, b, mode));
  let lo = yDomain ? yDomain[0] : Math.min(...vals);
  let hi = yDomain ? yDomain[1] : Math.max(...vals);
  if (mode === 'index' && !yDomain) {
    lo = Math.min(lo, 100);
    hi = Math.max(hi, 100);
  }
  if (mode === 'prozent' && !yDomain) {
    lo = Math.min(lo, 0);
    hi = Math.max(hi, 0);
  }
  const d0 = xDomain ? xDomain[0] : pts[0].day;
  const d1 = xDomain ? xDomain[1] : pts[pts.length - 1].day;
  const x = scaleLinear().domain([d0, d1 === d0 ? d0 + 1 : d1]).range([5, w - 5]);
  const y = scaleLinear().domain(lo === hi ? [lo - 1, hi + 1] : [lo, hi]).range([height - 5, 5]);
  const path = line<Point>()
    .x((p) => x(p.day))
    .y((p) => y(transform(p.close, b, mode)));
  const color = seriesColor(slot, dark);
  const segs = segments(pts, gaps);
  const lastPt = pts[pts.length - 1];
  const visibleGaps = gaps.filter((d) => d >= d0 && d <= d1);
  return (
    <div ref={wrapRef} className="mini-wrap" style={{ height }}>
      <svg className="mini" width={w} height={height} role="img" aria-label={label}>
        {mode !== 'absolut' ? <line x1={0} x2={w} y1={y(mode === 'index' ? 100 : 0)} y2={y(mode === 'index' ? 100 : 0)} className="baseline" /> : null}
        {segs.map((seg, i) => (seg.length > 1 ? <path key={i} d={path(seg) ?? ''} stroke={color} className="mini-line" /> : null))}
        {segs.filter((seg) => seg.length === 1).map((seg) => (
          <circle key={`s${seg[0].day}`} cx={x(seg[0].day)} cy={y(transform(seg[0].close, b, mode))} r={4} fill={color} className="ringed" />
        ))}
        {pts.length <= 3 ? pts.map((p) => <circle key={p.day} cx={x(p.day)} cy={y(transform(p.close, b, mode))} r={4} fill={color} className="ringed" />) : null}
        {pts.length > 3 ? <circle cx={x(lastPt.day)} cy={y(transform(lastPt.close, b, mode))} r={4} fill={color} className="ringed" /> : null}
        {visibleGaps.map((d) => (
          <line key={`g${d}`} className="gap-mark" x1={x(d)} x2={x(d)} y1={height - 8} y2={height} />
        ))}
      </svg>
    </div>
  );
}

export interface CompareLine {
  isin: string;
  name: string;
  slot: number;
  pts: Point[];
  basePrice: number;
  currency: string | null;
}

/** Gemeinsamer Linienvergleich, indexiert auf 100 am gemeinsamen Basistag. */
export function CompareChart({
  lines,
  baseDay,
  end,
  hidden,
  highlight,
  onHighlight,
  onToggle,
  height = 300,
}: {
  lines: CompareLine[];
  baseDay: number;
  end: number;
  hidden: Set<string>;
  highlight: string | null;
  onHighlight: (isin: string | null) => void;
  onToggle?: (isin: string) => void;
  height?: number;
}) {
  const [wrapRef, width] = useWidth<HTMLDivElement>();
  const dark = useDark();
  const [hoverDay, setHoverDay] = useState<number | null>(null);
  const margin = { top: 12, right: 14, bottom: 28, left: 48 };
  const innerW = width - margin.left - margin.right;
  const innerH = height - margin.top - margin.bottom;
  const shown = lines.filter((l) => !hidden.has(l.isin));
  const allVals = shown.flatMap((l) => l.pts.map((p) => (100 * p.close) / l.basePrice));
  let lo = allVals.length ? Math.min(...allVals, 100) : 90;
  let hi = allVals.length ? Math.max(...allVals, 100) : 110;
  if (lo === hi) {
    lo -= 1;
    hi += 1;
  }
  const x = scaleUtc().domain([toDate(baseDay), toDate(end === baseDay ? end + 1 : end)]).range([0, innerW]);
  const y = scaleLinear().domain([lo, hi]).range([innerH, 0]).nice(5);
  const path = line<Point>()
    .x((p) => x(toDate(p.day)))
    .y((p, _i) => y(p.close));
  const unionDays = [...new Set(shown.flatMap((l) => l.pts.map((p) => p.day)))].sort((a, b) => a - b);
  const pick = (clientX: number, rect: DOMRect) => {
    const day = x.invert(clientX - rect.left - margin.left).getTime() / DAY;
    const i = nearestIndex(unionDays, day);
    if (i >= 0) setHoverDay(unionDays[i]);
  };
  return (
    <figure className="chart">
      <div ref={wrapRef} className="chart-surface" style={{ height }}>
        <svg width={width} height={height} role="img" aria-label={`Gemeinsamer Vergleich von ${shown.length} Aktien, indexiert auf 100 am ${f.day(baseDay)}`}>
          <g transform={`translate(${margin.left},${margin.top})`}>
            {y.ticks(5).map((t) => (
              <g key={t} transform={`translate(0,${y(t)})`}>
                <line x1={0} x2={innerW} className="grid" />
                <text x={-8} dy="0.32em" textAnchor="end" className="axis-label">
                  {t.toLocaleString('de-DE', { maximumFractionDigits: 1 })}
                </text>
              </g>
            ))}
            <line x1={0} x2={innerW} y1={y(100)} y2={y(100)} className="baseline" />
            {x.ticks(Math.max(2, Math.floor(innerW / 80))).map((t) => (
              <text key={t.getTime()} x={x(t)} y={innerH + 18} textAnchor="middle" className="axis-label">
                {shortFmt.format(t)}
              </text>
            ))}
            {shown.map((l) => {
              const indexed = l.pts.map((p) => ({ ...p, close: (100 * p.close) / l.basePrice }));
              const dim = highlight !== null && highlight !== l.isin;
              return (
                <path
                  key={l.isin}
                  d={path(indexed) ?? ''}
                  stroke={seriesColor(l.slot, dark)}
                  className={`price-line${dim ? ' is-dim' : ''}${highlight === l.isin ? ' is-strong' : ''}`}
                />
              );
            })}
            {hoverDay !== null ? <line className="crosshair" x1={x(toDate(hoverDay))} x2={x(toDate(hoverDay))} y1={0} y2={innerH} /> : null}
            {hoverDay !== null
              ? shown.map((l) => {
                  const p = l.pts.find((q) => q.day === hoverDay);
                  return p ? <circle key={l.isin} cx={x(toDate(p.day))} cy={y((100 * p.close) / l.basePrice)} r={4} fill={seriesColor(l.slot, dark)} className="ringed" /> : null;
                })
              : null}
            <rect
              className="hit"
              x={0}
              y={0}
              width={innerW}
              height={innerH}
              tabIndex={0}
              aria-label="Vergleichsdiagramm: Pfeiltasten wählen den Tag"
              onPointerMove={(e: PointerEvent) => pick(e.clientX, (e.currentTarget as Element).getBoundingClientRect())}
              onPointerDown={(e: PointerEvent) => pick(e.clientX, (e.currentTarget as Element).getBoundingClientRect())}
              onKeyDown={(e: KeyboardEvent) => {
                if (!unionDays.length) return;
                const i = hoverDay === null ? unionDays.length - 1 : unionDays.indexOf(hoverDay);
                let handled = true;
                if (e.key === 'ArrowLeft') setHoverDay(unionDays[Math.max(0, i - 1)]);
                else if (e.key === 'ArrowRight') setHoverDay(unionDays[Math.min(unionDays.length - 1, i + 1)]);
                else if (e.key === 'Home') setHoverDay(unionDays[0]);
                else if (e.key === 'End') setHoverDay(unionDays[unionDays.length - 1]);
                else if (e.key === 'Escape') setHoverDay(null);
                else handled = false;
                if (handled) e.preventDefault();
              }}
            />
          </g>
        </svg>
        {hoverDay !== null ? (
          <div className="tooltip tooltip-wide" style={{ left: 8 }} role="status" aria-live="polite">
            <span>{f.dayWithWeekday(hoverDay)}</span>
            {shown.map((l) => {
              const p = l.pts.find((q) => q.day === hoverDay);
              return (
                <span key={l.isin} className="tooltip-row">
                  <span className="key-line" style={{ background: seriesColor(l.slot, dark) }} aria-hidden="true" />
                  <strong>{p ? f.signedPctValue(100 * (p.close / l.basePrice - 1)) : 'kein Datenpunkt'}</strong>
                  <span className="tooltip-name">{l.name}</span>
                </span>
              );
            })}
          </div>
        ) : null}
      </div>
      <ul className="legend" aria-label="Legende">
        {lines.map((l) => {
          const off = hidden.has(l.isin);
          const lastP = l.pts[l.pts.length - 1];
          return (
            <li key={l.isin} className={off ? 'is-off' : ''}>
              {onToggle ? (
                <label className="legend-check">
                  <input type="checkbox" checked={!off} onChange={() => onToggle(l.isin)} aria-label={`${l.name} im Diagramm zeigen`} />
                </label>
              ) : null}
              <button type="button" className="legend-btn" aria-pressed={highlight === l.isin} onClick={() => onHighlight(highlight === l.isin ? null : l.isin)}>
                <span className="key-line" style={{ background: seriesColor(l.slot, dark) }} aria-hidden="true" />
                <span className="legend-name">
                  {l.name}
                  <small>{l.isin}</small>
                </span>
                <span className="legend-value">{lastP ? f.signedPctValue(100 * (lastP.close / l.basePrice - 1)) : '–'}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </figure>
  );
}

/** Rendite-Leiter: 90 schmale Balken (höchste Kursrendite je Zeitraum) über einem Zollstock 1–90.
 * Antippen oder Pfeiltasten wählen einen Zeitraum, Antippen/Enter öffnet ihn. */
export function LadderStrip({
  values,
  labels,
  onPick,
  height = 168,
}: {
  values: (number | null)[];
  labels?: (string | null)[];
  onPick: (h: number) => void;
  height?: number;
}) {
  const [wrapRef, width] = useWidth<HTMLDivElement>();
  const dark = useDark();
  const [hover, setHover] = useState<number | null>(null);
  const finite = values.filter((v): v is number => v !== null && Number.isFinite(v));
  const maxV = finite.length ? Math.max(0, ...finite) : 1;
  const minV = finite.length ? Math.min(0, ...finite) : 0;
  const rulerH = 26;
  const top = 24;
  const plotBottom = height - rulerH - 6;
  const y = scaleLinear()
    .domain([minV, maxV === minV ? minV + 1 : maxV])
    .range([plotBottom, top]);
  const zeroY = y(0);
  const pad = 4;
  const slotW = (width - pad * 2) / 90;
  const barW = Math.max(1.5, Math.min(6, slotW - 1.5));
  const color = seriesColor(0, dark);
  const best = finite.length ? values.indexOf(Math.max(...finite)) : -1;
  const xOf = (i: number) => pad + i * slotW + slotW / 2;
  const rulerY = height - rulerH;
  const pickFromEvent = (e: PointerEvent | MouseEvent) => {
    const rect = (e.currentTarget as Element).getBoundingClientRect();
    return Math.min(89, Math.max(0, Math.floor(((e.clientX - rect.left - pad) / (rect.width - pad * 2)) * 90)));
  };
  const label = (i: number) => {
    const v = values[i];
    const name = labels?.[i];
    return `${i + 1} ${i === 0 ? 'Kalendertag' : 'Kalendertage'}: ${v === null || v === undefined ? 'keine vergleichbare Aktie' : `${f.pct(v)}${name ? `, ${name}` : ''}`}`;
  };
  return (
    <div ref={wrapRef} className="ladder-strip" style={{ height }}>
      <svg width={width} height={height} role="img" aria-label="Höchste Kursrendite je Zeitraum von 1 bis 90 Kalendertagen. Die vollständige Tabelle steht in der Ansicht „Höchste Rendite 1–90 Tage“.">
        {values.map((v, i) => {
          if (v === null || !Number.isFinite(v)) return null;
          const yv = y(v);
          const hpx = Math.max(1, Math.abs(zeroY - yv));
          return (
            <rect
              key={i}
              x={xOf(i) - barW / 2}
              width={barW}
              y={v >= 0 ? zeroY - hpx : zeroY}
              height={hpx}
              rx={Math.min(2, barW / 2)}
              fill={v >= 0 ? color : 'var(--down)'}
              opacity={hover === null || hover === i ? 1 : 0.4}
            />
          );
        })}
        <line x1={0} x2={width} y1={zeroY} y2={zeroY} className="axis" />
        {best >= 0 ? (
          <text x={Math.min(width - 4, Math.max(4, xOf(best)))} y={14} textAnchor={best > 60 ? 'end' : best < 20 ? 'start' : 'middle'} className="axis-label strong-label">
            Höchster Wert {f.pct(values[best])} bei {best + 1} T
          </text>
        ) : null}
        <rect className="ladder-ruler" x={0} y={rulerY} width={width} height={rulerH} rx={5} />
        {Array.from({ length: 90 }, (_, i) => {
          const h = i + 1;
          const len = h === 1 || h % 30 === 0 ? 11 : h % 7 === 0 ? 8 : 4;
          return <line key={h} className="ladder-tick" x1={xOf(i)} x2={xOf(i)} y1={rulerY} y2={rulerY + len} />;
        })}
        {[1, 7, 14, 30, 60, 90].map((h) => (
          <text key={h} x={xOf(h - 1)} y={rulerY + rulerH - 5} textAnchor={h === 1 ? 'start' : h === 90 ? 'end' : 'middle'} className="ladder-tick-label">
            {h}
          </text>
        ))}
        <rect
          className="hit"
          x={0}
          y={0}
          width={width}
          height={height}
          tabIndex={0}
          role="slider"
          aria-label="Zeitraum wählen; Enter öffnet die reine Renditeliste"
          aria-valuemin={1}
          aria-valuemax={90}
          aria-valuenow={(hover ?? 0) + 1}
          aria-valuetext={hover === null ? 'kein Zeitraum gewählt' : label(hover)}
          onPointerMove={(e: PointerEvent) => setHover(pickFromEvent(e))}
          onPointerLeave={(e: PointerEvent) => {
            if (e.pointerType === 'mouse') setHover(null);
          }}
          onClick={(e: MouseEvent) => onPick(pickFromEvent(e) + 1)}
          onKeyDown={(e: KeyboardEvent) => {
            const current = hover ?? (best >= 0 ? best : 0);
            if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
              e.preventDefault();
              setHover(Math.min(89, current + (hover === null ? 0 : 1)));
            } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
              e.preventDefault();
              setHover(Math.max(0, current - (hover === null ? 0 : 1)));
            } else if (e.key === 'Home' || e.key === 'End') {
              e.preventDefault();
              setHover(e.key === 'Home' ? 0 : 89);
            } else if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onPick(current + 1);
            } else if (e.key === 'Escape') setHover(null);
          }}
          onBlur={() => setHover(null)}
        />
      </svg>
      {hover !== null ? (
        <div className="tooltip" style={{ left: Math.min(Math.max(0, width - 190), Math.max(0, xOf(hover) - 90)), top: 22 }} role="status" aria-live="polite">
          <strong>{values[hover] === null || values[hover] === undefined ? 'keine vergleichbare Aktie' : f.pct(values[hover])}</strong>
          <span>{f.windowLabel(hover + 1)}</span>
          {labels?.[hover] ? <span>{labels[hover]}</span> : null}
        </div>
      ) : null}
    </div>
  );
}
