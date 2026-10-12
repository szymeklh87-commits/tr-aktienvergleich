/* PNG-Export von Einzelchart, Rasterseite oder gemeinsamem Vergleich.
 * Gezeichnet werden ausschließlich die tatsächlich geladenen Tageskurse; Lücken bleiben Lücken.
 * Jeder Export trägt Name/ISIN, Zeitraum, Basis, Kursstand, Snapshot und Quelle und ist als
 * Momentaufnahme gekennzeichnet (keine Liveansicht). */

import { scaleLinear } from 'd3-scale';
import { SERIES_LIGHT } from './colors';
import * as f from './format';

export interface PngLine {
  color: string;
  points: { day: number; value: number }[];
  gaps?: number[];
}

export interface PngPanel {
  title: string;
  subtitle: string[];
  lines: PngLine[];
  xDomain: [number, number];
  yMode: 'absolut' | 'index' | 'prozent';
  yDomain?: [number, number] | null;
  legend?: { color: string; text: string }[];
  emptyText?: string;
}

export interface PngDocument {
  heading: string;
  meta: string[];
  panels: PngPanel[];
  columns: number;
  panelWidth?: number;
  plotHeight?: number;
  footer: string[];
}

const INK = '#16191d';
const INK2 = '#4b525b';
const GRID = '#e1e0d9';
const AXIS = '#c3c2b7';
const FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif";

export const PNG_COLORS = SERIES_LIGHT;

function wrap(ctx: CanvasRenderingContext2D, text: string, width: number): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let current = '';
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (ctx.measureText(candidate).width <= width || !current) current = candidate;
    else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  return lines;
}

/** Teilt eine Reihe an fehlenden erwarteten Sitzungen (keine Verbindung über Lücken). */
export function splitByGaps<T extends { day: number }>(points: T[], gaps: number[]): T[][] {
  if (!points.length) return [];
  const sorted = [...gaps].sort((a, b) => a - b);
  const out: T[][] = [[points[0]]];
  for (let i = 1; i < points.length; i += 1) {
    const prev = points[i - 1].day;
    const cur = points[i].day;
    if (sorted.some((g) => g > prev && g < cur)) out.push([points[i]]);
    else out[out.length - 1].push(points[i]);
  }
  return out;
}

function axisText(value: number, mode: PngPanel['yMode']): string {
  if (mode === 'prozent') return `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toLocaleString('de-DE', { maximumFractionDigits: 1 })} %`;
  return value.toLocaleString('de-DE', { maximumSignificantDigits: 5 });
}

function panelHeaderHeight(ctx: CanvasRenderingContext2D, panel: PngPanel, width: number): number {
  ctx.font = `650 15px ${FONT}`;
  const titleLines = wrap(ctx, panel.title, width).length;
  ctx.font = `13px ${FONT}`;
  const subLines = panel.subtitle.reduce((n, s) => n + wrap(ctx, s, width).length, 0);
  return titleLines * 19 + subLines * 17 + 8;
}

function drawPanel(ctx: CanvasRenderingContext2D, panel: PngPanel, x0: number, y0: number, width: number, headerH: number, plotH: number): void {
  let y = y0;
  ctx.fillStyle = INK;
  ctx.font = `650 15px ${FONT}`;
  ctx.textBaseline = 'top';
  for (const line of wrap(ctx, panel.title, width)) {
    ctx.fillText(line, x0, y);
    y += 19;
  }
  ctx.font = `13px ${FONT}`;
  ctx.fillStyle = INK2;
  for (const sub of panel.subtitle) {
    for (const line of wrap(ctx, sub, width)) {
      ctx.fillText(line, x0, y);
      y += 17;
    }
  }
  const plotTop = y0 + headerH;
  const left = x0 + 54;
  const right = x0 + width - 6;
  const bottom = plotTop + plotH;
  const values = panel.lines.flatMap((l) => l.points.map((p) => p.value));
  if (!values.length) {
    ctx.strokeStyle = AXIS;
    ctx.setLineDash([4, 4]);
    ctx.strokeRect(x0 + 0.5, plotTop + 0.5, width - 1, plotH - 1);
    ctx.setLineDash([]);
    ctx.fillStyle = INK2;
    ctx.textAlign = 'center';
    ctx.fillText(panel.emptyText ?? 'Keine Kurse im Zeitraum', x0 + width / 2, plotTop + plotH / 2 - 8);
    ctx.textAlign = 'left';
    return;
  }
  let lo = panel.yDomain ? panel.yDomain[0] : Math.min(...values);
  let hi = panel.yDomain ? panel.yDomain[1] : Math.max(...values);
  if (panel.yMode === 'index') {
    lo = Math.min(lo, 100);
    hi = Math.max(hi, 100);
  }
  if (panel.yMode === 'prozent') {
    lo = Math.min(lo, 0);
    hi = Math.max(hi, 0);
  }
  if (lo === hi) {
    lo -= Math.abs(lo) * 0.01 || 1;
    hi += Math.abs(hi) * 0.01 || 1;
  }
  const yScale = scaleLinear().domain([lo, hi]).range([bottom, plotTop + 4]).nice(4);
  const [d0, d1] = panel.xDomain;
  const xScale = scaleLinear().domain([d0, d1 === d0 ? d0 + 1 : d1]).range([left, right]);
  ctx.lineWidth = 1;
  ctx.font = `11px ${FONT}`;
  ctx.textBaseline = 'middle';
  for (const tick of yScale.ticks(4)) {
    const ty = Math.round(yScale(tick)) + 0.5;
    ctx.strokeStyle = GRID;
    ctx.beginPath();
    ctx.moveTo(left, ty);
    ctx.lineTo(right, ty);
    ctx.stroke();
    ctx.fillStyle = INK2;
    ctx.textAlign = 'right';
    ctx.fillText(axisText(tick, panel.yMode), left - 6, ty);
  }
  if (panel.yMode !== 'absolut') {
    const by = Math.round(yScale(panel.yMode === 'index' ? 100 : 0)) + 0.5;
    ctx.strokeStyle = AXIS;
    ctx.beginPath();
    ctx.moveTo(left, by);
    ctx.lineTo(right, by);
    ctx.stroke();
  }
  ctx.strokeStyle = AXIS;
  ctx.beginPath();
  ctx.moveTo(left, bottom + 0.5);
  ctx.lineTo(right, bottom + 0.5);
  ctx.stroke();
  ctx.fillStyle = INK2;
  ctx.textBaseline = 'top';
  ctx.textAlign = 'left';
  ctx.fillText(f.day(d0), left, bottom + 5);
  ctx.textAlign = 'right';
  ctx.fillText(f.day(d1), right, bottom + 5);
  ctx.textAlign = 'left';

  ctx.save();
  ctx.beginPath();
  ctx.rect(left - 2, plotTop, right - left + 4, plotH + 2);
  ctx.clip();
  for (const series of panel.lines) {
    ctx.strokeStyle = series.color;
    ctx.fillStyle = series.color;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    for (const seg of splitByGaps(series.points, series.gaps ?? [])) {
      if (seg.length === 1) {
        ctx.beginPath();
        ctx.arc(xScale(seg[0].day), yScale(seg[0].value), 3.5, 0, Math.PI * 2);
        ctx.fill();
        continue;
      }
      ctx.beginPath();
      seg.forEach((p, i) => (i === 0 ? ctx.moveTo(xScale(p.day), yScale(p.value)) : ctx.lineTo(xScale(p.day), yScale(p.value))));
      ctx.stroke();
    }
    if (series.points.length <= 12) {
      for (const p of series.points) {
        ctx.beginPath();
        ctx.arc(xScale(p.day), yScale(p.value), 3.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
  ctx.restore();

  if (panel.legend?.length) {
    let ly = bottom + 24;
    ctx.font = `12px ${FONT}`;
    ctx.textBaseline = 'middle';
    for (const item of panel.legend) {
      ctx.fillStyle = item.color;
      ctx.fillRect(x0, ly - 1.5, 14, 3);
      ctx.fillStyle = INK;
      ctx.fillText(item.text, x0 + 20, ly);
      ly += 18;
    }
  }
}

export async function renderPng(doc: PngDocument): Promise<Blob> {
  const scale = 2;
  const margin = 28;
  const panelWidth = doc.panelWidth ?? 520;
  const plotH = doc.plotHeight ?? 170;
  const columns = Math.max(1, Math.min(doc.columns, doc.panels.length || 1));
  const gapX = 28;
  const gapY = 30;
  const width = margin * 2 + columns * panelWidth + (columns - 1) * gapX;

  const probe = document.createElement('canvas').getContext('2d');
  if (!probe) throw new Error('Zeichenfläche nicht verfügbar');
  probe.font = `700 20px ${FONT}`;
  const headingLines = wrap(probe, doc.heading, width - margin * 2);
  probe.font = `13px ${FONT}`;
  const metaLines = doc.meta.flatMap((m) => wrap(probe, m, width - margin * 2));
  const footLines = doc.footer.flatMap((m) => wrap(probe, m, width - margin * 2));
  const headers = doc.panels.map((p) => panelHeaderHeight(probe, p, panelWidth));
  const legendH = doc.panels.map((p) => (p.legend?.length ? 14 + p.legend.length * 18 : 0));
  const rows = Math.ceil(doc.panels.length / columns);
  const rowHeights: number[] = [];
  for (let r = 0; r < rows; r += 1) {
    const slice = (list: number[]) => list.slice(r * columns, Math.min(doc.panels.length, r * columns + columns));
    rowHeights.push(Math.max(...slice(headers)) + plotH + 22 + Math.max(0, ...slice(legendH)));
  }
  const headH = headingLines.length * 26 + metaLines.length * 18 + 16;
  const height = margin * 2 + headH + rowHeights.reduce((a, b) => a + b, 0) + Math.max(0, rows - 1) * gapY + 16 + footLines.length * 18;

  const canvas = document.createElement('canvas');
  canvas.width = Math.ceil(width * scale);
  canvas.height = Math.ceil(height * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Zeichenfläche nicht verfügbar');
  ctx.scale(scale, scale);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);

  let y = margin;
  ctx.textBaseline = 'top';
  ctx.fillStyle = INK;
  ctx.font = `700 20px ${FONT}`;
  for (const line of headingLines) {
    ctx.fillText(line, margin, y);
    y += 26;
  }
  ctx.font = `13px ${FONT}`;
  ctx.fillStyle = INK2;
  for (const line of metaLines) {
    ctx.fillText(line, margin, y);
    y += 18;
  }
  y += 16;

  for (let r = 0; r < rows; r += 1) {
    const rowHeader = Math.max(...headers.slice(r * columns, r * columns + columns));
    for (let c = 0; c < columns; c += 1) {
      const k = r * columns + c;
      if (k >= doc.panels.length) continue;
      drawPanel(ctx, doc.panels[k], margin + c * (panelWidth + gapX), y, panelWidth, rowHeader, plotH);
    }
    y += rowHeights[r] + gapY;
  }
  y += 4 - gapY + 16;
  ctx.font = `12px ${FONT}`;
  ctx.fillStyle = INK2;
  ctx.textBaseline = 'top';
  for (const line of footLines) {
    ctx.fillText(line, margin, y);
    y += 18;
  }

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('PNG konnte nicht erzeugt werden'))), 'image/png');
  });
}
