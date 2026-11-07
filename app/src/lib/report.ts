/* Bericht „1–30 Tage · Rendite und Gleichmäßigkeit“ (ab 1.8.1) – wie der Bericht 30D-4W-two-groups:
 * je Zeitraum 1–30 Tage der Spitzenreiter für 0/100, 40/60, 50/50 und 60/40, Gruppe A und B nebeneinander.
 * Reine Funktionen auf den Daten des Datenstands (Übersicht, Instrumente) – ohne Browser testbar. */

import { endDayOf } from './instruments';
import { hasGroups, markers, matrixRows, overviewRow, type Marker, type MatrixRow } from './groups';
import { decodeBits } from './scoring';
import type { Group, Instruments, Overview, OverviewRow } from './types';

export const REPORT_WEIGHTS = [0, 40, 50, 60] as const;
export const REPORT_DAYS = 30;

/** Auswahl der Tabellen: alle vier Gewichtungen untereinander (wie die Berichtsdatei) oder eine. */
export type ReportPick = 'alle' | (typeof REPORT_WEIGHTS)[number];

export function parseReportPick(text: string | null): ReportPick {
  if (text === null || text === '' || text === 'alle') return 'alle';
  const n = Number(text);
  return (REPORT_WEIGHTS as readonly number[]).includes(n) ? (n as ReportPick) : 'alle';
}

export function pickedWeights(pick: ReportPick): number[] {
  return pick === 'alle' ? [...REPORT_WEIGHTS] : [pick];
}

export interface ReportCell {
  h: number;
  group: Group;
  weight: number;
  row: OverviewRow | undefined;
  /** Index der Spitzenaktie oder null, wenn die Rangliste leer bzw. nicht berechenbar ist */
  idx: number | null;
  /** Wie oft dieselbe Aktie in dieser Spalte (Gruppe, Gewichtung) über 1–30 Tage vorne liegt */
  repeats: number;
}

export interface ReportRow {
  h: number;
  /** Platz 1 der Rangliste mit Mindestumsatz (ab 1.23 die einzige; ältere Stände ohne sie: alle vergleichbaren Aktien) */
  cell: ReportCell;
}

function cell(overview: Overview, group: Group, weight: number, h: number): ReportCell {
  const row = overviewRow(overview, group, weight, h);
  const idx = row && row.idx !== undefined && row.idx !== null && !row.empty ? row.idx : null;
  return { h, group, weight, row, idx, repeats: 0 };
}

/** Ab 1.23 nur die Ranglisten mit Mindestumsatz (Ø Tagesumsatz ab 10 Mio. USD); ältere Stände ohne sie: alle Aktien. */
export function reportGroup(overview: Overview): Group {
  return hasGroups(overview) ? 'b' : 'a';
}

/** 30 Zeilen einer Gewichtung; ``repeats`` zählt, wie oft derselbe Sieger in dieser Spalte vorn liegt. */
export function reportRows(overview: Overview, weight: number, days = REPORT_DAYS): ReportRow[] {
  const group = reportGroup(overview);
  const rows: ReportRow[] = [];
  for (let h = 1; h <= days; h++) rows.push({ h, cell: cell(overview, group, weight, h) });
  const counts = new Map<number, number>();
  for (const row of rows) if (row.cell.idx !== null) counts.set(row.cell.idx, (counts.get(row.cell.idx) ?? 0) + 1);
  for (const row of rows) row.cell.repeats = row.cell.idx !== null ? counts.get(row.cell.idx) ?? 0 : 0;
  return rows;
}

export type ReportBlock = { kind: 'row'; row: ReportRow } | { kind: 'leer'; from: number; to: number; reason: string };

function emptyReason(c: ReportCell): string | null {
  return c.idx === null ? c.row?.empty ?? 'keine_vergleichbare_aktie' : null;
}

/** Aufeinanderfolgende Zeiträume ohne Spitzenreiter aus demselben Grund werden zu einer Zeile „1–20 Tage: nicht
 * berechenbar …“ zusammengefasst. */
export function reportBlocks(rows: ReportRow[]): ReportBlock[] {
  const out: ReportBlock[] = [];
  for (const row of rows) {
    const reason = emptyReason(row.cell);
    if (reason !== null) {
      const last = out[out.length - 1];
      if (last && last.kind === 'leer' && last.reason === reason && last.to === row.h - 1) last.to = row.h;
      else out.push({ kind: 'leer', from: row.h, to: row.h, reason });
    } else {
      out.push({ kind: 'row', row });
    }
  }
  return out;
}

/** Matrix 1–30 Tage × vier Gewichtungen (Zellen wie in der großen Matrix, inkl. ≡). */
export function reportMatrix(overview: Overview, group: Group = reportGroup(overview), days = REPORT_DAYS): MatrixRow[] {
  return matrixRows(overview, group, 1, days).map((row) => ({ h: row.h, cells: row.cells.filter((c) => (REPORT_WEIGHTS as readonly number[]).includes(c.weight)) }));
}

/** Platz-1-Zählung über 1–30 Tage und die vier Gewichtungen (Farbe wie in allen Ansichten). */
export function reportMarkers(overview: Overview, instruments: Instruments, days = REPORT_DAYS): Map<number, Marker> {
  return markers(overview, instruments, 1, days, REPORT_WEIGHTS);
}

/** Die häufigsten Spitzenreiter des Berichts: Platz-1-Vorkommen absteigend, bei Gleichstand nach ISIN. */
export function reportLeaders(markerMap: Map<number, Marker>, instruments: Instruments, limit = 5): Marker[] {
  return [...markerMap.values()]
    .sort((a, b) => b.count - a.count || (instruments.isin[a.idx] < instruments.isin[b.idx] ? -1 : instruments.isin[a.idx] > instruments.isin[b.idx] ? 1 : 0))
    .slice(0, limit);
}

/** Erste Zelle (kleinster Zeitraum, dann Gewichtung) einer Aktie im Bericht – Einstieg für den Kursverlauf. */
export function firstReportCell(overview: Overview, idx: number, days = REPORT_DAYS): { h: number; weight: number; group: Group } | null {
  const group = reportGroup(overview);
  for (let h = 1; h <= days; h++) {
    for (const weight of REPORT_WEIGHTS) {
      if (overviewRow(overview, group, weight, h)?.idx === idx) return { h, weight, group };
    }
  }
  return null;
}

export interface ReportStats {
  /** ISINs im öffentlichen TR-Verzeichnis */
  isins: number;
  /** geladene Kursreihen */
  series: number;
  /** Aktien mit Kursrendite in mindestens einem 1–30-Tage-Fenster */
  computed: number;
  /** berechenbare Kombinationen (Zeitraum × Gewichtung) mit Spitzenreiter */
  combos: number;
  /** alle Kombinationen (30 × 4) */
  combosTotal: number;
}

export function reportStats(overview: Overview, instruments: Instruments, universeTotal: number, loaded: number, days = REPORT_DAYS): ReportStats {
  let computed = 0;
  for (let i = 0; i < instruments.isin.length; i++) {
    const bits = decodeBits(instruments.v_bits[i]);
    if (bits.slice(0, days).some(Boolean)) computed++;
  }
  let combos = 0;
  const group = reportGroup(overview);
  for (const weight of REPORT_WEIGHTS) {
    for (let h = 1; h <= days; h++) if (cell(overview, group, weight, h).idx !== null) combos++;
  }
  return { isins: universeTotal, series: loaded, computed, combos, combosTotal: days * REPORT_WEIGHTS.length };
}

/** Zeilen für den CSV-Export: alle 30 × 4 Spitzenreiter. */
export function reportCsvRows(overview: Overview, instruments: Instruments, cutoffDay: number, iso: (day: number) => string): (string | number | null)[][] {
  const out: (string | number | null)[][] = [];
  for (const weight of REPORT_WEIGHTS) {
    for (const row of reportRows(overview, weight)) {
      for (const c of [row.cell]) {
        const r = c.row;
        out.push([
          `${weight}/${100 - weight}`,
          row.h,
          c.idx !== null ? instruments.name[c.idx] || instruments.tr_name[c.idx] : null,
          c.idx !== null ? instruments.isin[c.idx] : null,
          c.idx !== null && r?.r !== undefined && r?.r !== null ? r.r : null,
          c.idx !== null && r?.score !== undefined && r?.score !== null ? r.score : null,
          c.idx !== null && r?.r2 !== undefined && r?.r2 !== null ? r.r2 : null,
          c.idx !== null && r?.start !== undefined ? iso(r.start) : null,
          c.idx !== null ? iso(endDayOf(instruments, c.idx, cutoffDay)) : null,
          c.idx !== null ? instruments.price_unit[c.idx] ?? instruments.currency[c.idx] : null,
          c.idx === null ? r?.empty ?? 'nicht berechenbar' : null,
        ]);
      }
    }
  }
  return out;
}
