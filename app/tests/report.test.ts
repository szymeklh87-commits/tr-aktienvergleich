/* Bericht „1–30 Tage · Rendite und Gleichmäßigkeit“ (ab 1.8.1): Spitzenreiter je Zeitraum, Zusammenfassen
 * leerer Zeiträume, Matrix mit vier Gewichtungen, Zählung, Einstieg und CSV – SYNTHETISCHE Daten. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  firstReportCell,
  parseReportPick,
  pickedWeights,
  REPORT_WEIGHTS,
  reportBlocks,
  reportCsvRows,
  reportLeaders,
  reportMarkers,
  reportMatrix,
  reportRows,
  reportStats,
} from '../src/lib/report.ts';
import { WEIGHTS } from '../src/lib/scoring.ts';
import type { Instruments, Overview, OverviewRow } from '../src/lib/types.ts';

const DAYS = Array.from({ length: 90 }, (_, k) => k + 1);
const CUTOFF = 20738;

function winner(h: number, idx: number | undefined, empty = 'zu_wenig_tagesdaten'): OverviewRow {
  return idx === undefined ? { h, M: 0, empty } : { h, M: 9, idx, r: 0.01 * idx + h / 1000, score: 80 + idx, r2: 0.9, start: CUTOFF - h };
}

/* Alle Aktien (bis 1.22 „A“): 0/100 → Aktie 1 (1–10 Tage), Aktie 2 (11–90); übrige Gewichtungen erst ab 20 Tagen → Aktie 3.
 * Mit Mindestumsatz (ab 1.23 die einzige Liste, bisher „B“): 0/100 → Aktie 2; übrige ab 20 Tagen → Aktie 4, bei 40/60 und
 * 25 Tagen keine Aktie mit Umsatz. */
function overview(): Overview {
  return {
    counts: { V: DAYS.map(() => 9), U: DAYS.map(() => 5), L: DAYS.map(() => 4), UL: DAYS.map(() => 3) },
    v0: DAYS.map((h) => winner(h, h <= 10 ? 1 : 2)),
    u: Object.fromEntries(WEIGHTS.map((w) => [String(w), DAYS.map((h) => winner(h, h < 20 ? undefined : 3))])),
    v0l: DAYS.map((h) => winner(h, 2)),
    ul: Object.fromEntries(
      WEIGHTS.map((w) => [String(w), DAYS.map((h) => (w === 40 && h === 25 ? winner(h, undefined, 'keine_aktie_mit_umsatz') : winner(h, h < 20 ? undefined : 4)))]),
    ),
  } as unknown as Overview;
}

/** Älterer Datenstand ohne Ranglisten mit Mindestumsatz (vor 1.4): nur „alle Aktien“. */
function oldOverview(): Overview {
  const { counts, v0, u } = overview() as unknown as { counts: Record<string, number[]>; v0: OverviewRow[]; u: Record<string, OverviewRow[]> };
  return { counts: { V: counts.V, U: counts.U }, v0, u } as unknown as Overview;
}

const bits = (windows: number[]) => {
  const bytes = new Array(12).fill(0);
  for (const h of windows) bytes[(h - 1) >> 3] |= 1 << ((h - 1) & 7);
  return btoa(String.fromCharCode(...bytes));
};

const instruments = {
  isin: ['ZZ0000000000', 'ZZ0000000001', 'ZZ0000000002', 'ZZ0000000003', 'ZZ0000000004', 'ZZ0000000005'],
  name: ['Null AG', 'Eins AG', 'Zwei AG', 'Drei AG', 'Vier AG', ''],
  tr_name: ['', '', '', '', '', 'Fünf (TR)'],
  price_unit: [null, 'USD', 'EUR', null, 'AUD', null],
  currency: ['EUR', 'USD', 'EUR', 'JPY', 'AUD', 'EUR'],
  v_bits: [bits([]), bits([1, 2, 30]), bits(DAYS), bits([40, 90]), bits([31]), bits([5])],
  u_bits: [bits([]), bits([]), bits([]), bits([]), bits([]), bits([])],
  calendar: ['XNYS', 'XNYS', 'XETR', 'XTKS', 'XASX', 'XETR'],
} as unknown as Instruments;

test('Bericht (ab 1.23): je Zeitraum 1–30 der Spitzenreiter der Rangliste mit Mindestumsatz, Wiederholungen gezählt', () => {
  const ov = overview();
  const rows = reportRows(ov, 0);
  assert.equal(rows.length, 30);
  assert.deepEqual([rows[0].h, rows[29].h], [1, 30]);
  assert.equal(rows[0].cell.group, 'b', 'nur die Rangliste mit Mindestumsatz');
  assert.equal(rows[0].cell.idx, 2, 'Aktie 1 führt nur ohne Mindestumsatz und erscheint nicht');
  assert.equal(rows[0].cell.repeats, 30);
  assert.ok(rows.every((r) => r.cell.idx !== 1), 'keine Aktie unter dem Mindestumsatz');
  const mixed = reportRows(ov, 40);
  assert.equal(mixed[18].cell.idx, null, '19 Tage: weniger als 15 Tageskurse – kein Ersatz durch ein längeres Fenster');
  assert.equal(mixed[18].cell.repeats, 0);
  assert.equal(mixed[19].cell.idx, 4);
  assert.equal(mixed[19].cell.repeats, 10, '20–30 Tage ohne 25 Tage');
  assert.equal(mixed[24].cell.idx, null);
  assert.equal(mixed[24].cell.row?.empty, 'keine_aktie_mit_umsatz');
  // älterer Datenstand ohne Mindestumsatz-Ranglisten: alle vergleichbaren Aktien
  const old = reportRows(oldOverview(), 0);
  assert.deepEqual([old[0].cell.group, old[0].cell.idx, old[0].cell.repeats, old[10].cell.idx, old[10].cell.repeats], ['a', 1, 10, 2, 20]);
});

test('Bericht: leere Zeiträume mit gleichem Grund werden zu einer Zeile zusammengefasst', () => {
  const ov = overview();
  const blocks = reportBlocks(reportRows(ov, 40));
  assert.deepEqual(blocks[0], { kind: 'leer', from: 1, to: 19, reason: 'zu_wenig_tagesdaten' });
  assert.deepEqual(blocks.find((b) => b.kind === 'leer' && b.from === 25), { kind: 'leer', from: 25, to: 25, reason: 'keine_aktie_mit_umsatz' });
  assert.equal(blocks.length, 1 + 5 + 1 + 5, '20–24 und 26–30 einzeln, 25 eigener Grund');
  // 0/100: nichts leer
  assert.equal(reportBlocks(reportRows(ov, 0)).filter((b) => b.kind === 'leer').length, 0);
  // älterer Datenstand: dieselbe Zusammenfassung auf allen Aktien
  const old = reportBlocks(reportRows(oldOverview(), 60));
  assert.deepEqual(old[0], { kind: 'leer', from: 1, to: 19, reason: 'zu_wenig_tagesdaten' });
  assert.equal(old.length, 1 + 11);
});

test('Bericht: Matrix 1–30 × 0/100, 40/60, 50/50, 60/40 und Zählung nur mit Mindestumsatz', () => {
  const ov = overview();
  const matrix = reportMatrix(ov);
  assert.equal(matrix.length, 30);
  assert.deepEqual(matrix[0].cells.map((c) => c.weight), [...REPORT_WEIGHTS]);
  assert.deepEqual(matrix[24].cells.map((c) => c.row.idx), [2, undefined, 4, 4]);
  assert.deepEqual(matrix[25].cells.map((c) => c.row.idx), [2, 4, 4, 4]);
  assert.deepEqual(reportMatrix(oldOverview())[25].cells.map((c) => c.row.idx), [2, 3, 3, 3], 'älterer Stand: alle Aktien');
  const marks = reportMarkers(ov, instruments);
  assert.equal(marks.get(1), undefined, 'Aktie 1 nur ohne Mindestumsatz vorne – nicht gezählt');
  assert.equal(marks.get(3), undefined, 'Aktie 3 nur ohne Mindestumsatz vorne – nicht gezählt');
  assert.deepEqual([marks.get(2)!.count, marks.get(2)!.countA, marks.get(2)!.countB], [30, 0, 30]);
  assert.equal(marks.get(4)!.count, 32, '3 Gewichtungen × 11 Zeiträume, bei 40/60 und 25 Tagen keine Aktie mit Umsatz');
  assert.deepEqual(reportLeaders(marks, instruments, 3).map((m) => m.idx), [4, 2]);
  assert.deepEqual(firstReportCell(ov, 4), { h: 20, weight: 40, group: 'b' });
  assert.deepEqual(firstReportCell(ov, 2), { h: 1, weight: 0, group: 'b' });
  assert.equal(firstReportCell(ov, 3), null, 'nur ohne Mindestumsatz vorne');
  assert.equal(firstReportCell(ov, 5), null);
  assert.deepEqual(firstReportCell(oldOverview(), 3), { h: 20, weight: 40, group: 'a' });
});

test('Bericht: Kennzahlen, Auswahl der Gewichtung und CSV mit allen 120 Kombinationen', () => {
  const ov = overview();
  const stats = reportStats(ov, instruments, 11531, 10836);
  assert.equal(stats.isins, 11531);
  assert.equal(stats.series, 10836);
  assert.equal(stats.computed, 3, 'Aktien 1, 2 und 5 haben eine Rendite in einem 1–30-Tage-Fenster');
  assert.equal(stats.combosTotal, 120);
  // 30 (0/100) + 3 × 11 − 1 (40/60 bei 25 Tagen)
  assert.equal(stats.combos, 30 + 32);
  assert.equal(reportStats(oldOverview(), instruments, 11531, 10836).combos, 30 + 33, 'älterer Stand: alle Aktien');

  assert.equal(parseReportPick(null), 'alle');
  assert.equal(parseReportPick('50'), 50);
  assert.equal(parseReportPick('70'), 'alle', 'nur die vier Berichtsgewichtungen');
  assert.deepEqual(pickedWeights('alle'), [0, 40, 50, 60]);
  assert.deepEqual(pickedWeights(60), [60]);

  const csv = reportCsvRows(ov, instruments, CUTOFF, (day) => `T${day}`);
  assert.equal(csv.length, 120);
  assert.deepEqual(csv[0], ['0/100', 1, 'Zwei AG', 'ZZ0000000002', 0.021, 82, 0.9, `T${CUTOFF - 1}`, `T${CUTOFF}`, 'EUR', null]);
  const empty = csv.find((row) => row[0] === '40/60' && row[1] === 1)!;
  assert.deepEqual(empty.slice(2), [null, null, null, null, null, null, null, null, 'zu_wenig_tagesdaten']);
  const at25 = csv.find((row) => row[0] === '40/60' && row[1] === 25)!;
  assert.equal(at25[10], 'keine_aktie_mit_umsatz');
});
