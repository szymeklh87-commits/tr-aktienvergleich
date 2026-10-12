/* Reine Funktionstests der App (ohne Browser, ohne Netz).  Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { commonBase, segments, transform, windowPoints, type Point } from '../src/lib/chartmath.ts';
import { csvCell, toCsv } from '../src/lib/csv.ts';
import * as f from '../src/lib/format.ts';
import { cohortFor, decodeBits, decodeRanks, parsePolicy, parseWeight, parseWindow, pctFromDoubled, rankFromMatrix, weightedScore, WEIGHTS } from '../src/lib/scoring.ts';
import { sanitizePrefs, DEFAULT_PREFS } from '../src/lib/storage.ts';
import { averageRanksDoubled } from '../src/lib/subgroup.ts';
import type { SeriesData } from '../src/lib/types.ts';

const NBSP = ' ';
const MINUS = '−';

test('T54: CSV schützt vor Formel-Injection, Zahlen bleiben Zahlen', () => {
  assert.equal(csvCell('=SUMME(A1:A9)'), "'=SUMME(A1:A9)");
  assert.equal(csvCell('+49 30 1234'), "'+49 30 1234");
  assert.equal(csvCell('-Kurs'), "'-Kurs");
  assert.equal(csvCell('@cmd'), "'@cmd");
  assert.equal(csvCell('\tTab'), "'\tTab");
  assert.equal(csvCell('\rWagenrücklauf'), "\"'\rWagenrücklauf\"");
  assert.equal(csvCell(-5.25, 2), '-5,25');
  assert.equal(csvCell(0.123456789, 6), '0,123457');
  assert.equal(csvCell('DE0007164600'), 'DE0007164600');
  assert.equal(csvCell('Name; mit Semikolon'), '"Name; mit Semikolon"');
  assert.equal(csvCell('Er sagte "Hallo"'), '"Er sagte ""Hallo"""');
  assert.equal(csvCell('A"; B'), '"A""; B"');
  assert.equal(csvCell(null), '');
  assert.equal(csvCell(true), 'ja');
  const csv = toCsv([['Snapshot', '2026-10-12_x']], ['Rang', 'Name'], [[1, '=1+1']]);
  assert.ok(csv.startsWith('﻿'), 'UTF-8-BOM für Excel');
  assert.equal(csv, "﻿# Snapshot;2026-10-12_x\r\nRang;Name\r\n1;'=1+1\r\n");
});

test('Prozentformat: Vorzeichen, echtes Minuszeichen, geschütztes Leerzeichen', () => {
  assert.equal(f.pct(0.12), `+12,00${NBSP}%`);
  assert.equal(f.pct(-0.05), `${MINUS}5,00${NBSP}%`);
  assert.equal(f.pct(0), `0,00${NBSP}%`);
  assert.equal(f.pct(-0.000001), `0,00${NBSP}%`, 'gerundet null ohne Vorzeichen');
  assert.equal(f.pct(2.610916583619342), `+261,09${NBSP}%`);
  assert.equal(f.pct(null), '–');
  assert.equal(f.pct(Number.NaN), '–');
  assert.equal(f.r2(0.93264), '0,9326');
  assert.equal(f.score(91.36), '91,4');
  assert.equal(f.weightLabel(60), '60 % Gleichmäßigkeit · 40 % Rendite');
  assert.equal(f.weightLabel(0), 'Nur Kursrendite (0 % Gleichmäßigkeit · 100 % Rendite)');
  assert.equal(f.day(20738), '12.10.2026');
  assert.equal(f.dayLong(20738), 'Montag, 12. Oktober 2026');
  assert.equal(f.share(3, 0), 'nicht berechenbar');
  // T57: gültige Nullrendite und fehlende Rendite sind sichtbar verschieden
  assert.equal(f.direction(0), 'null');
  assert.equal(f.directionWord(0), 'unverändert');
  assert.equal(f.direction(null), 'fehlt');
  assert.equal(f.directionWord(null), 'nicht berechenbar');
  assert.notEqual(f.pct(0), f.pct(null));
});

test('Zeitraum- und Gewichtungsparameter werden streng geprüft', () => {
  for (const bad of ['0', '91', '-1', '1.5', 'abc', '', '100']) assert.equal(parseWindow(bad, 30), 30, bad);
  assert.equal(parseWindow(' 7 ', 30), 7);
  assert.equal(parseWindow('90', 30), 90);
  assert.equal(parseWindow(null, 14), 14);
  assert.equal(parseWeight('mix60', 0), 60);
  assert.equal(parseWeight('return', 50), 0);
  assert.equal(parseWeight('consistency', 50), 100);
  assert.equal(parseWeight('65', 50), 50);
  assert.equal(parseWeight('100', 50), 100);
  assert.equal(parsePolicy('common_trend'), 'common_trend');
  assert.equal(parsePolicy('irgendwas'), 'native');
  assert.deepEqual([...WEIGHTS], [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100], 'T80: genau elf Gewichtungen');
  assert.equal(cohortFor('native', 0), 'v0');
  assert.equal(cohortFor('native', 10), 'u');
  assert.equal(cohortFor('common_trend', 0), 'u');
});

test('Perzentil und Score: exakte Operationsfolge', () => {
  assert.equal(pctFromDoubled(2, 1), 100, 'M = 1 → 100');
  assert.equal(pctFromDoubled(2, 5), 0);
  assert.equal(pctFromDoubled(10, 5), 100);
  assert.equal(pctFromDoubled(5, 5), 37.5);
  assert.equal(weightedScore(0, 80, 60), 60);
  assert.equal(weightedScore(100, 80, 60), 80);
  assert.equal(weightedScore(60, 80, 60), 0.6 * 80 + (1 - 0.6) * 60);
  assert.deepEqual(averageRanksDoubled([3, 1, 3]), [5, 2, 5], 'Gleichstand erhält denselben Durchschnittsrang');
  assert.deepEqual(averageRanksDoubled([]), []);
});

test('Bitmasken und Rangmatrix werden korrekt dekodiert', () => {
  const bytes = new Uint8Array(12);
  bytes[0] = 0b0000_0101; // Fenster 1 und 3
  bytes[11] = 0b0000_0010; // Fenster 90 (Bit 89)
  const b64 = Buffer.from(bytes).toString('base64');
  const bits = decodeBits(b64);
  assert.equal(bits.length, 90);
  assert.equal(bits[0], true);
  assert.equal(bits[1], false);
  assert.equal(bits[2], true);
  assert.equal(bits[89], true);
  const matrix = new Uint16Array(90 * 12);
  matrix[(30 - 1) * 12 + 0] = 5; // v0, 30 Tage
  matrix[(30 - 1) * 12 + 1 + 6] = 513; // u60
  const ranks = decodeRanks(Buffer.from(matrix.buffer).toString('base64'));
  assert.equal(rankFromMatrix(ranks, 30, 'native', 0), 5);
  assert.equal(rankFromMatrix(ranks, 30, 'native', 60), 513);
  assert.equal(rankFromMatrix(ranks, 30, 'common_trend', 0), null);
});

function series(days: number[], closes: number[], gaps: number[] = [], starts: (number | null)[] = []): SeriesData {
  return {
    schema: 'tr-series/1',
    isin: 'ZZ0000000016',
    listing: { symbol: null, exchange: null, mic: null, tz: null, currency: 'EUR', price_unit: 'EUR', unit_factor: 1, calendar: null },
    price_basis: 'split_adjusted_close',
    resolution: 'daily',
    source: { provider: 'test', fetched_at: null, revision: 1 },
    d: days,
    c: closes,
    v: days.map(() => 100),
    o: null,
    h: null,
    l: null,
    c_raw: null,
    ohlc_complete: false,
    gaps,
    window_start: Array.from({ length: 90 }, (_, k) => starts[k] ?? null),
    window_status: Array.from({ length: 90 }, () => 18),
    rank_columns: [],
    ranks_b64: '',
    events: [],
  };
}

test('T68: Lücken unterbrechen die Linie, es werden keine Kurse erzeugt', () => {
  const pts: Point[] = [10, 11, 13].map((day, i) => ({ day, close: 100 + i, open: null, high: null, low: null, volume: null, closeRaw: null }));
  const segs = segments(pts, [12]);
  assert.equal(segs.length, 2);
  assert.deepEqual(
    segs.map((s) => s.map((p) => p.day)),
    [[10, 11], [13]],
  );
  assert.equal(transform(125, 100, 'index'), 125);
  assert.equal(transform(125, 100, 'prozent'), 25, 'T65: 125 entspricht +25 %');
});

test('Fenster nutzt die veröffentlichte Startsitzung; ohne Startsitzung gekennzeichneter Rückgriff', () => {
  const s = series([100, 101, 102, 103, 106], [10, 11, 12, 13, 14], [], [103, 102]);
  const w1 = windowPoints(s, 1, 106);
  assert.deepEqual(
    w1.pts.map((p) => p.day),
    [103, 106],
  );
  assert.equal(w1.fallback, false);
  const w2 = windowPoints(s, 2, 106);
  assert.deepEqual(
    w2.pts.map((p) => p.day),
    [102, 103, 106],
  );
  const w3 = windowPoints(s, 3, 106);
  assert.equal(w3.fallback, true);
});

test('T67: gemeinsamer Basistag ohne Auffüllen; Verschiebung wird gemeldet', () => {
  const a = series([90, 91, 92, 95, 96], [1, 1, 1, 1, 1]);
  const b = series([91, 92, 95, 96], [1, 1, 1, 1]);
  const base = commonBase([a, b], 4, 96);
  assert.equal(base.day, 92);
  assert.equal(base.shifted, false);
  const c = series([94, 95, 96], [1, 1, 1]);
  const shifted = commonBase([a, c], 4, 96);
  assert.equal(shifted.day, 95);
  assert.equal(shifted.shifted, true);
  const none = commonBase([series([96], [1]), series([95], [1])], 4, 96);
  assert.equal(none.day, null);
});

test('Gespeicherte und importierte Einstellungen werden bereinigt', () => {
  const clean = sanitizePrefs({ h: 500, w: 65, policy: 'x' as never, theme: 'lila' as never, gridColumns: [1, 0, 95], frequencyTopK: 7 as never, compareA: 33 });
  assert.equal(clean.h, DEFAULT_PREFS.h);
  assert.equal(clean.w, DEFAULT_PREFS.w);
  assert.equal(clean.policy, 'native');
  assert.equal(clean.theme, 'system');
  assert.deepEqual(clean.gridColumns, DEFAULT_PREFS.gridColumns);
  assert.equal(clean.frequencyTopK, 10);
  assert.equal(clean.compareA, DEFAULT_PREFS.compareA);
  const ok = sanitizePrefs({ h: 7, w: 40, policy: 'common_trend', theme: 'dunkel', gridColumns: [3, 3, 9] });
  assert.equal(ok.h, 7);
  assert.equal(ok.w, 40);
  assert.equal(ok.policy, 'common_trend');
  assert.deepEqual(ok.gridColumns, [3, 9]);
  assert.equal(Object.keys(sanitizePrefs({ fremd: 1 } as never)).includes('fremd'), false);
});

test('T50: Name, Alias, Ticker und ISIN finden dieselbe Aktie', async () => {
  const { buildSearchIndex, search } = await import('../src/lib/search.ts');
  const inst = {
    count: 3,
    isin: ['DE0007164600', 'US0378331005', 'GB00B03MLX29'],
    name: ['SAP SE', 'Apple Inc.', 'Shell plc'],
    tr_name: ['SAP', 'Apple', 'Shell'],
    aliases: [['SAP AG'], [], ['Royal Dutch Shell']],
    ticker: ['SAP', 'AAPL', 'SHEL'],
    symbol: ['SAP.DE', 'AAPL', 'SHEL.L'],
  } as unknown as import('../src/lib/types.ts').Instruments;
  const index = buildSearchIndex(inst);
  assert.deepEqual(search(index, inst, 'apple'), [1]);
  assert.deepEqual(search(index, inst, 'AAPL'), [1]);
  assert.deepEqual(search(index, inst, 'US0378331005'), [1]);
  assert.deepEqual(search(index, inst, 'us0378331005'), [1]);
  assert.deepEqual(search(index, inst, 'royal dutch'), [2]);
  assert.deepEqual(search(index, inst, 'SAP AG'), [0]);
  assert.deepEqual(search(index, inst, ''), []);
});
