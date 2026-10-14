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

/* A: 0/100 → Aktie 1 (1–10 Tage), Aktie 2 (11–90); übrige Gewichtungen erst ab 20 Tagen → Aktie 3.
 * B: 0/100 → Aktie 2; übrige ab 20 Tagen → Aktie 4, bei 40/60 und 25 Tagen keine Aktie mit Umsatz. */
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

test('Bericht: je Zeitraum 1–30 der Spitzenreiter in A und B, Wiederholungen je Spalte', () => {
  const ov = overview();
  const rows = reportRows(ov, 0);
  assert.equal(rows.length, 30);
  assert.deepEqual([rows[0].h, rows[29].h], [1, 30]);
  assert.equal(rows[0].a.idx, 1);
  assert.equal(rows[0].a.repeats, 10, 'Aktie 1 liegt in 1–10 Tagen vorne');
  assert.equal(rows[10].a.idx, 2);
  assert.equal(rows[10].a.repeats, 20);
  assert.equal(rows[0].b.idx, 2);
  assert.equal(rows[0].b.repeats, 30, 'B zählt getrennt');
  const mixed = reportRows(ov, 40);
  assert.equal(mixed[18].a.idx, null, '19 Tage: weniger als 15 Tageskurse – kein Ersatz durch ein längeres Fenster');
  assert.equal(mixed[18].a.repeats, 0);
  assert.equal(mixed[19].a.idx, 3);
  assert.equal(mixed[24].b.idx, null);
  assert.equal(mixed[24].b.row?.empty, 'keine_aktie_mit_umsatz');
});

test('Bericht: leere Zeiträume mit gleichem Grund in A und B werden zu einer Zeile zusammengefasst', () => {
  const ov = overview();
  const blocks = reportBlocks(reportRows(ov, 40), true);
  assert.deepEqual(blocks[0], { kind: 'leer', from: 1, to: 19, reason: 'zu_wenig_tagesdaten' });
  assert.equal(blocks.length, 1 + 11, '20–30 Tage einzeln');
  const at25 = blocks.find((b) => b.kind === 'row' && b.row.h === 25);
  assert.ok(at25, 'A berechnet, B leer: bleibt eine eigene Zeile');
  // 0/100: nichts leer
  assert.equal(reportBlocks(reportRows(ov, 0), true).filter((b) => b.kind === 'leer').length, 0);
  // Ohne Gruppe B entscheidet nur A
  const onlyA = reportBlocks(reportRows(ov, 60), false);
  assert.deepEqual(onlyA[0], { kind: 'leer', from: 1, to: 19, reason: 'zu_wenig_tagesdaten' });
});

test('Bericht: Matrix 1–30 × 0/100, 40/60, 50/50, 60/40 und Zählung über A und B', () => {
  const ov = overview();
  const matrix = reportMatrix(ov, 'a');
  assert.equal(matrix.length, 30);
  assert.deepEqual(matrix[0].cells.map((c) => c.weight), [...REPORT_WEIGHTS]);
  assert.deepEqual(matrix[25].cells.map((c) => c.row.idx), [2, 3, 3, 3]);
  const b = reportMatrix(ov, 'b');
  assert.deepEqual(b[24].cells.map((c) => c.row.idx), [2, undefined, 4, 4]);
  const marks = reportMarkers(ov, instruments);
  assert.equal(marks.get(1)!.count, 10);
  assert.deepEqual([marks.get(2)!.count, marks.get(2)!.countA, marks.get(2)!.countB], [50, 20, 30]);
  assert.equal(marks.get(3)!.count, 33, '3 Gewichtungen × 11 Zeiträume (20–30)');
  assert.equal(marks.get(4)!.count, 32, 'bei 40/60 und 25 Tagen keine Aktie mit Umsatz');
  assert.deepEqual(reportLeaders(marks, instruments, 3).map((m) => m.idx), [2, 3, 4]);
  assert.deepEqual(firstReportCell(ov, 3), { h: 20, weight: 40, group: 'a' });
  assert.deepEqual(firstReportCell(ov, 4), { h: 20, weight: 40, group: 'b' });
  assert.deepEqual(firstReportCell(ov, 2), { h: 1, weight: 0, group: 'b' });
  assert.equal(firstReportCell(ov, 5), null);
});

test('Bericht: Kennzahlen, Auswahl der Gewichtung und CSV mit allen 240 Kombinationen', () => {
  const ov = overview();
  const stats = reportStats(ov, instruments, 11531, 10836);
  assert.equal(stats.isins, 11531);
  assert.equal(stats.series, 10836);
  assert.equal(stats.computed, 3, 'Aktien 1, 2 und 5 haben eine Rendite in einem 1–30-Tage-Fenster');
  assert.equal(stats.combosTotal, 240);
  // A: 30 (0/100) + 3 × 11; B: 30 + 3 × 11 − 1
  assert.equal(stats.combos, 30 + 33 + 30 + 32);

  assert.equal(parseReportPick(null), 'alle');
  assert.equal(parseReportPick('50'), 50);
  assert.equal(parseReportPick('70'), 'alle', 'nur die vier Berichtsgewichtungen');
  assert.deepEqual(pickedWeights('alle'), [0, 40, 50, 60]);
  assert.deepEqual(pickedWeights(60), [60]);

  const csv = reportCsvRows(ov, instruments, CUTOFF, (day) => `T${day}`);
  assert.equal(csv.length, 240);
  assert.deepEqual(csv[0], ['0/100', 1, 'A', 'Eins AG', 'ZZ0000000001', 0.011, 81, 0.9, `T${CUTOFF - 1}`, `T${CUTOFF}`, 'USD', null]);
  const empty = csv.find((row) => row[0] === '40/60' && row[1] === 1 && row[2] === 'A')!;
  assert.deepEqual(empty.slice(3), [null, null, null, null, null, null, null, null, 'zu_wenig_tagesdaten']);
});
