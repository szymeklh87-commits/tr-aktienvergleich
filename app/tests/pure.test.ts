/* Reine Funktionstests der App (ohne Browser, ohne Netz).  Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { commonBase, segments, transform, windowPoints, type Point } from '../src/lib/chartmath.ts';
import { csvCell, toCsv } from '../src/lib/csv.ts';
import * as f from '../src/lib/format.ts';
import { cohortFor, decodeBits, decodeRanks, FIXED_WINDOWS, parsePolicy, parseWeight, parseWindow, pctFromDoubled, rankFromMatrix, rankInColumn, weightedScore, WEIGHTS } from '../src/lib/scoring.ts';
import { listEntries, parseReturnList, thresholdLabel, turnoverBasis, turnoverShort, type TurnoverInfo } from '../src/lib/turnover.ts';
import type { Instruments, Manifest, WindowData } from '../src/lib/types.ts';
import { venueDayRule, venueDetails, venueListText, venueOf, venuePair, venueShort } from '../src/lib/venue.ts';
import { joinNames, marketName, partialSummary } from '../src/lib/markets.ts';
import { nextCutoff, outcomeFor, outcomeText, waitFrom, WAIT_MAX_MS } from '../src/lib/update.ts';
import type { Status } from '../src/lib/types.ts';
import { sanitizePrefs, DEFAULT_PREFS } from '../src/lib/storage.ts';
import { averageRanksDoubled } from '../src/lib/subgroup.ts';
import {
  allocationAfter,
  allocationNow,
  changes,
  changesTitle,
  nextText,
  parseChoice,
  parseEuro,
  rebalanceDays,
  reasonText,
  scaled,
  variantKey,
} from '../src/lib/rotation.ts';
import type { RotationIndex, RotationPreview, RotationVariant } from '../src/lib/types.ts';
import { groupFrequency, markers, markerSlots, matrixCoverage, matrixRows, sameText, tenWindowCounts, tenWindowRows } from '../src/lib/groups.ts';
import { isinCheckDigitOk, parseIsinImport } from '../src/lib/instruments.ts';
import type { FrequencyData, Overview, OverviewRow } from '../src/lib/types.ts';
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

test('Rangmatrix ab 1.1: 13 Spalten mit Ranking 2 (v0l), Zugriff über Spaltennamen', () => {
  const columns = ['v0', ...WEIGHTS.map((w) => `u${w}`), 'v0l'];
  const matrix = new Uint16Array(90 * columns.length);
  matrix[(7 - 1) * columns.length + 0] = 3; // v0, 7 Tage
  matrix[(7 - 1) * columns.length + 12] = 1; // v0l, 7 Tage
  matrix[(7 - 1) * columns.length + 1 + 5] = 40; // u50
  const ranks = decodeRanks(Buffer.from(matrix.buffer).toString('base64'));
  assert.equal(rankFromMatrix(ranks, 7, 'native', 0, columns), 3);
  assert.equal(rankFromMatrix(ranks, 7, 'native', 50, columns), 40);
  assert.equal(rankInColumn(ranks, 7, 'v0l', columns), 1);
  assert.equal(rankInColumn(ranks, 8, 'v0l', columns), null);
  assert.equal(rankInColumn(ranks, 7, 'gibt_es_nicht', columns), null);
});

test('Geldbeträge kompakt und deutsch', () => {
  assert.equal(f.money(12_400_000, 'USD'), `12,4${NBSP}Mio.${NBSP}USD`);
  assert.equal(f.money(850_000, 'USD'), `850.000${NBSP}USD`);
  assert.equal(f.money(1_250_000_000, 'USD'), `1,25${NBSP}Mrd.${NBSP}USD`);
  assert.equal(f.money(null, 'USD'), '–');
  assert.equal(thresholdLabel(null), `10${NBSP}Mio.${NBSP}USD`);
  assert.equal(parseReturnList('umsatz'), 'umsatz');
  assert.equal(parseReturnList('irgendwas'), 'alle');
});

test('Umsatz-Berechnungsbasis: Sitzungen, Tage mit Umsatz, Landeswährung, Wechselkurstag', () => {
  const manifest = {
    turnover: { wechselkurse: { quelle: 'EZB-Referenzkurse (Euro foreign exchange reference rates)' }, sehr_niedrig_usd: 1_000_000, schwelle_usd: 10_000_000 },
    codes: { turnover_status: { daten_fehlen: { key: 'daten_fehlen', kurz: 'Kurse oder Volumen fehlen', text: 'Für weniger als 16 der 20 Sitzungen liegen Schlusskurs und gemeldetes Volumen vor.' } } },
  } as unknown as Manifest;
  const ok: TurnoverInfo = { status: 'ok', usd: 11_000_000, local: 10_000_000, currency: 'EUR', sessions: 20, withData: 19, positive: 18, first: 20711, last: 20738, fxFirst: 20711, fxLast: 20738, liquid: true };
  assert.equal(turnoverShort(ok, manifest), `Ø 11,0${NBSP}Mio.${NBSP}USD je Sitzung`);
  assert.equal(turnoverBasis(ok, manifest), `20 Sitzungen 15.09.–12.10.2026, 18 mit Umsatz, 1 ohne Daten; Ø 10,0${NBSP}Mio.${NBSP}EUR, EZB-Kurs bis 12.10.2026`);
  const missing: TurnoverInfo = { ...ok, status: 'daten_fehlen', usd: null, local: null, withData: 12, positive: 12, liquid: false };
  assert.equal(turnoverShort(missing, manifest), 'Ø Umsatz nicht bestimmbar: Kurse oder Volumen fehlen');
  assert.ok(turnoverBasis(missing, manifest).includes('weniger als 16 der 20 Sitzungen'));
});

test('Rendite-Ranglisten: Plätze kommen in Server-Reihenfolge, Ranking 2 nutzt orders.v0l', () => {
  const win = {
    schema: 'tr-window/1',
    h: 7,
    part: 'kopf_50',
    cutoff_day: 20738,
    target_start_day: 20731,
    counts: { V: 3, U: 0, L: 2 },
    m: { idx: [4, 9, 2], start: [20731, 20731, 20730], n: [6, 6, 6], n_exp: [6, 6, 6], r: [0.5, 0.2, 0.1], p0: [10, 20, 30], p1: [15, 24, 33], r2: [null, null, null], slope: [null, null, null], noise: [null, null, null], mdd: [0, 0, 0], vol: [1, 1, 1], wf: [1, 0, 16], a_rv: [6, 4, 2], a_gu: [null, null, null], a_ru: [null, null, null] },
    orders: { v0: [4, 9, 2], u: {}, v0l: [9, 2] },
    ties: { v0: [], u: {}, v0l: [] },
  } as unknown as WindowData;
  const first = listEntries(win, 'alle', 0, 10);
  assert.deepEqual(first.map((e) => [e.rank, e.idx]), [[1, 4], [2, 9], [3, 2]]);
  const second = listEntries(win, 'umsatz', 0, 10);
  assert.deepEqual(second.map((e) => [e.rank, e.idx, e.r, e.p0, e.p1, e.start, e.end, e.wf]), [
    [1, 9, 0.2, 20, 24, 20731, 20738, 0],
    [2, 2, 0.1, 30, 33, 20730, 20738, 16],
  ]);
  assert.deepEqual(listEntries(win, 'umsatz', 1, 1).map((e) => e.rank), [2]);
});

test('Zweiter Börsenplatz: Kurztext, Details mit Umrechnung, nicht geprüfte und ältere Stände', () => {
  const manifest = {
    venue_check: { plaetze: 10, schwelle_wertentwicklung: 0.1, schwelle_endkurs: 0.1, max_abstand_tage: 4, hinweis: null, anzahl: { kandidaten: 2, aktien: { geprueft: 1, kein_vergleichsplatz: 1 }, auffaellige_aktien: 1, aktie_zeitraum: { abweichung: 1 } } },
    codes: {
      venue_status: { kein_vergleichsplatz: { key: 'kein_vergleichsplatz', kurz: 'kein zweiter Börsenplatz', text: 'Zur ISIN gibt es keine weitere Notierung.' } },
      venue_pair_status: {
        ok: { key: 'ok', kurz: 'unauffällig', text: '…' },
        abweichung: { key: 'abweichung', kurz: 'Kursabweichung zwischen Börsenplätzen', text: '…' },
      },
    },
  } as unknown as Manifest;
  const instruments = {
    currency: ['USD', 'EUR', 'USD'],
    venue: { idx: [0, 2], status: ['geprueft', 'kein_vergleichsplatz'], symbol: ['APC.DE', null], exchange_key: ['XETR', null], exchange: ['Xetra', null], currency: ['EUR', null], price_unit: ['EUR', null], level: [-0.002, null], level_flag: [false, false], end_day: [20738, null], end_price: [210.5, null] },
  } as unknown as Instruments;
  const win = { xv: { idx: [0], status: ['abweichung'], r: [0.38], dev: [-0.096], d0: [20708, 20708], d1: [20738], p0: [150, 150], p1: [210.5] } } as unknown as WindowData;
  const info = venueOf(instruments, 0)!;
  const pair = venuePair(win, 0)!;
  assert.equal(venueShort(manifest, info, pair), 'Auffällig: Kursabweichung zwischen Börsenplätzen');
  const lines = venueDetails(manifest, info, pair, 'USD', 0.527);
  assert.equal(lines[0], 'Xetra (APC.DE), Kurse in EUR');
  assert.equal(lines[1], `Kursrendite dort 12.09.–12.10.2026: +38,00${NBSP}% (in USD umgerechnet, EZB-Referenzkurse)`);
  assert.equal(lines[2], `Referenzbörse: +52,70${NBSP}%; Unterschied der Wertentwicklung ${MINUS}9,60${NBSP}%`);
  assert.ok(lines.some((l) => l.startsWith('Endkurs dort stimmt überein')));
  assert.equal(venueShort(manifest, venueOf(instruments, 2), null), 'kein zweiter Börsenplatz');
  assert.equal(venueShort(manifest, venueOf(instruments, 1), null), 'Nicht geprüft – abgeglichen werden die ersten 10 Plätze beider Rendite-Ranglisten');
  const old = { codes: {} } as unknown as Manifest;
  assert.equal(venueShort(old, null, null), 'In diesem Datenstand nicht abgeglichen');
  // ab 1.5.1: wegen eines Fehlers übersprungen → wie „nicht abgeglichen“, nicht „nicht geprüft (nur erste Plätze)“
  const aborted = { ...manifest, venue_check: { ...manifest.venue_check!, abgebrochen: true, hinweis: 'Abgleich wegen eines Fehlers übersprungen (RuntimeError); Ranglisten unverändert' } } as Manifest;
  assert.equal(venueShort(aborted, null, null), 'In diesem Datenstand nicht abgeglichen');
  assert.equal(venueListText(aborted, info, pair), '');
  assert.deepEqual(venueDetails(old, info, pair, 'USD', 0.5), []);
  // Zeilen in Ranglisten: kurz; ohne Ergebnis für den Zeitraum keine Zeile statt einer falschen Aussage
  assert.equal(venueListText(manifest, info, pair), `Vergleich mit Xetra (APC.DE): auffällige Abweichung – dort +38,00${NBSP}%`);
  assert.equal(venueListText(manifest, info, { ...pair, status: 'ok' }), `Vergleich mit Xetra (APC.DE): unauffällig, dort +38,00${NBSP}%`);
  assert.equal(venueListText(manifest, info, undefined), '');
  assert.equal(venueListText(manifest, venueOf(instruments, 2), undefined), 'Vergleich mit zweitem Börsenplatz: kein zweiter Börsenplatz');
  assert.equal(venueListText(manifest, null, pair), '');
  assert.equal(venueListText(old, info, pair), '');
});

test('Zweiter Börsenplatz: Regel für den Vergleichskurs je nach Version des Abgleichs im Datenstand', () => {
  // v1 (Stände bis 13.10.2026 abends): letzter gelieferter Kurs bis N Tage vorher
  assert.equal(
    venueDayRule({ version: 'boersenplatz-v1', max_abstand_tage: 4 }),
    'Schlusskurs am letzten Handelstag am oder vor dem Start- und dem Enddatum, höchstens 4 Tage früher.',
  );
  // v2: Kurs genau des Tages; Lieferlücke des Anbieters → kein Vergleich statt Vortageskurs
  const v2 = venueDayRule({ version: 'boersenplatz-v2', max_abstand_tage: 3 });
  assert.ok(v2.startsWith('Schlusskurs genau vom Start- und vom Enddatum'), v2);
  assert.ok(v2.includes('(höchstens 3 Tage früher)'), v2);
  assert.ok(v2.endsWith('Fehlt ein solcher Schlusskurs beim Kursanbieter, entfällt der Vergleich.'), v2);
  assert.equal(venueDayRule(null), venueDayRule({ version: 'boersenplatz-v2', max_abstand_tage: 4 }));
});

test('Teilstand: genannt wird die kürzere Liste (fehlende oder enthaltene Börsen), Namen statt Kalendercodes', () => {
  const manifest = (delivered: string[], missing: string[]) => ({ completeness: { status: 'teilstand', delivered_markets: delivered, missing_markets: missing } }) as unknown as Manifest;
  // wenige fehlen: die fehlenden nennen
  const few = partialSummary(manifest(['XNYS', 'XASX', 'XPAR'], ['XLON', 'XETR']));
  assert.deepEqual(few, { mode: 'missing', names: ['London', 'Xetra'], missing: 2, delivered: 3, markets: 5 });
  // wie am 12.10.2026: 3 geliefert, 28 fehlen → die gelieferten nennen
  const europe = ['ASEX', 'XAMS', 'XBKK', 'XBRU', 'XBUD', 'XCSE', 'XDUB', 'XETR', 'XFRA', 'XHEL', 'XHKG', 'XIDX', 'XJSE', 'XLIS', 'XLON', 'XMAD', 'XMEX', 'XMIL', 'XOSL', 'XPAR', 'XPRA', 'XSHG', 'XSTO', 'XSWX', 'XTAE', 'XTAL', 'XWAR', 'XWBO'];
  const many = partialSummary(manifest(['XNYS', 'XASX', 'XNZE'], europe));
  assert.equal(many.mode, 'delivered');
  assert.deepEqual(many.names, ['Australien', 'Neuseeland', 'USA']);
  assert.equal(joinNames(many.names), 'Australien, Neuseeland und USA');
  assert.deepEqual([many.missing, many.delivered, many.markets], [28, 3, 31]);
  // gleich viele oder keine gelieferten: die fehlenden nennen
  assert.equal(partialSummary(manifest(['XNYS'], ['XLON'])).mode, 'missing');
  assert.equal(partialSummary(manifest([], ['XLON', 'XETR'])).mode, 'missing');
  assert.equal(joinNames([]), '');
  assert.equal(joinNames(['USA']), 'USA');
  assert.equal(joinNames(['London', 'Xetra']), 'London und Xetra');
  assert.equal(marketName('XYZZ'), 'XYZZ', 'unbekannter Code bleibt sichtbar');
});

test('Aktualisieren auf Wunsch: Ergebnis erkennen, nächster Kursstand, Zeitüberschreitung', () => {
  const run = { run_id: 'lauf-1', trigger: 'zeitplan', planned_start_utc: null, started_at_utc: '2026-10-13T04:00:00Z', finished_at_utc: '2026-10-13T04:40:00Z', status: 'veroeffentlicht', message: null, cutoff_session_date: '2026-10-12', attempt: 1 };
  const base = {
    generated_at_utc: '2026-10-13T04:40:00Z',
    latest_snapshot_id: '2026-10-12_aaaa',
    last_price_session: '2026-10-12',
    last_run: run,
    naechster_kursstand: { datum: '2026-10-13', ab_utc: '2026-10-13T21:00:00Z', boersen: ['XNYS', 'XETR'] },
  } as unknown as Status;
  const t0 = Date.parse('2026-10-13T12:00:00Z');
  const wait = waitFrom(base, t0);
  assert.equal(outcomeFor(wait, base, t0 + 60_000), null, 'nichts Neues: weiter warten');
  const sameButNoNews = { ...base, generated_at_utc: '2026-10-13T12:10:00Z', last_run: { ...run, run_id: 'lauf-2', status: 'keine_neuen_daten', message: 'Kein neuer abgeschlossener Börsentag seit 2026-10-12' } } as Status;
  assert.equal(outcomeFor(wait, sameButNoNews, t0 + 600_000), 'keine_neuen_daten');
  const waiting = { ...sameButNoNews, last_run: { ...sameButNoNews.last_run!, status: 'wartet_auf_provider' } } as Status;
  assert.equal(outcomeFor(wait, waiting, t0 + 600_000), 'lauf_beendet');
  const fresh = { ...sameButNoNews, latest_snapshot_id: '2026-10-13_bbbb', last_price_session: '2026-10-13' } as Status;
  assert.equal(outcomeFor(wait, fresh, t0 + 600_000), 'neuer_stand');
  assert.equal(outcomeText({ outcome: 'neuer_stand', at: t0, status: fresh }).text, 'Neuer Kursstand vom 13.10.2026 ist veröffentlicht.');
  assert.equal(outcomeFor(wait, base, t0 + WAIT_MAX_MS + 1), 'zeit_abgelaufen');
  // Nächster Kursstand: Dienstag 13.10., ab 23:00 Uhr Berliner Zeit (21:00 UTC)
  const before = nextCutoff(base, t0)!;
  assert.equal(before.sessionText, 'Dienstag, 13. Oktober 2026');
  assert.equal(before.readyText, 'heute ab 23:00 Uhr');
  assert.equal(before.ready, false);
  assert.equal(nextCutoff(base, Date.parse('2026-10-13T21:30:00Z'))!.ready, true);
  assert.equal(nextCutoff(base, Date.parse('2026-10-12T20:00:00Z'))!.readyText, 'morgen ab 23:00 Uhr');
  assert.equal(nextCutoff({ ...base, naechster_kursstand: null } as Status, t0), null);
});

test('Umschichtungs-Regel: Variante aus der Adresse, Beträge, Begründungen, Aufteilung vorher und nachher', () => {
  const index = {
    standard: 'n5-monatlich-w13-k10000',
    regel: { aktien: [5, 10], rhythmus: ['monatlich', 'woechentlich'], trend_wochen: [13, 4], kapital: [5000, 10000, 25000], haltepuffer_faktor: 2, anteil_toleranz: 0.05 },
    varianten: [{ key: 'n5-monatlich-w13-k10000', aktien: 5, rhythmus: 'monatlich', trend_wochen: 13, kapital: 10000 }],
  } as unknown as RotationIndex;
  const standard = parseChoice(new URLSearchParams(''), index);
  assert.equal(variantKey(standard), 'n5-monatlich-w13-k10000');
  const chosen = parseChoice(new URLSearchParams('n=10&r=woechentlich&w=4&k=25000'), index);
  assert.equal(variantKey(chosen), 'n10-woechentlich-w4-k25000');
  // Unbekannte Werte fallen auf den Standard zurück (keine erfundenen Varianten)
  assert.equal(variantKey(parseChoice(new URLSearchParams('n=7&r=taeglich&w=-1&k=1e9'), index)), 'n5-monatlich-w13-k10000');

  assert.equal(parseEuro('12.500'), 12500);
  assert.equal(parseEuro('12500,50 €'), 12500.5);
  assert.equal(parseEuro(' 1 000 '), 1000);
  assert.equal(parseEuro('12,5,0'), null);
  assert.equal(parseEuro('50'), null, 'unter 100 €');
  assert.equal(parseEuro('-500'), null);
  assert.equal(scaled(2000, 10000, 25000), 5000);
  assert.equal(scaled(2000, 10000, null), 2000);
  assert.equal(scaled(null, 10000, 25000), null);

  const ctx = { rank: 12, holdings: 5, keepFactor: 2, band: 0.05, before: 0.27 };
  assert.equal(reasonText('platz_ausserhalb_puffer', ctx), 'nur noch Platz 12 – gehalten wird bis Platz 10');
  assert.equal(reasonText('anteil_angleichen', ctx), `Anteil 27,0${NBSP}% liegt mehr als 5 Prozentpunkte neben dem Ziel von 20${NBSP}%`);
  assert.equal(reasonText('neu_unter_den_besten', { ...ctx, rank: 3 }), 'Platz 3 der Rangliste, noch nicht im Regeldepot');

  // Regeldepot 10.000 €: A 30 %, B 25 %, C 25 %, D 10 %, Bargeld 10 %; verkauft wird D, A wird reduziert, E und F kommen neu
  const preview = {
    tag: 20738,
    beschlossen_am: null,
    naechste_entscheidung: 20763,
    depotwert: 10000,
    bargeld: 1000,
    bestand: { idx: [1, 2, 3, 4], stueck: [1, 1, 1, 1], wert: [3000, 2500, 2500, 1000], anteil: [0.3, 0.25, 0.25, 0.1], seit: [1, 1, 1, 1], einstand: [1, 1, 1, 1], rendite: [0, 0, 0, 0], platz: [1, 2, 3, 30], trend: [0.5, 0.4, 0.3, 0.01] },
    aenderungen: {
      idx: [5, 4, 1, 6],
      aktion: ['kauf', 'verkauf', 'reduzieren', 'kauf'],
      anteil_vorher: [0, 0.1, 0.3, 0],
      anteil_nachher: [0.2, 0, 0.2, 0.2],
      wert: [2000, 1000, 1000, 2000],
      platz: [4, 30, 1, 5],
      trend: [0.2, 0.01, 0.5, 0.19],
      grund: ['neu_unter_den_besten', 'platz_ausserhalb_puffer', 'anteil_angleichen', 'neu_unter_den_besten'],
    },
    rangliste: { idx: [], platz: [], trend: [], umsatz_usd: [], gehalten: [] },
  } as unknown as RotationPreview;
  assert.deepEqual(changes(preview).map((c) => c.action), ['verkauf', 'reduzieren', 'kauf', 'kauf'], 'erst verkaufen, dann kaufen');
  const now = allocationNow(preview);
  assert.equal(now.length, 5);
  assert.ok(Math.abs(now.reduce((a, s) => a + s.share, 0) - 1) < 1e-12);
  const after = allocationAfter(preview, 5);
  const share = (idx: number | null) => after.find((s) => s.idx === idx)?.share ?? 0;
  // Geld: 10 % Bargeld + 10 % (D) + 10 % (A reduziert) = 30 %; gewünscht 2 × 20 % → je 15 % (gleichmäßig gekürzt)
  assert.ok(Math.abs(share(1) - 0.2) < 1e-12 && Math.abs(share(5) - 0.15) < 1e-12 && Math.abs(share(6) - 0.15) < 1e-12);
  assert.equal(share(4), 0);
  assert.equal(after.find((s) => s.idx === null), undefined, 'kein Bargeld übrig');
  assert.deepEqual(after.map((s) => s.kind), ['angleichen', 'halten', 'halten', 'neu', 'neu']);
  assert.ok(Math.abs(after.reduce((a, s) => a + s.share, 0) - 1) < 1e-12);

  assert.equal(changesTitle(preview), 'Was die Regel nach heutigem Stand ändern würde');
  assert.equal(nextText(preview), 'Nächste Entscheidung: Freitag, 6. November 2026 zum Schlusskurs, umgesetzt am nächsten Handelstag.');
  const decided = { ...preview, beschlossen_am: 20735 } as RotationPreview;
  assert.equal(changesTitle(decided), 'Was die Regel jetzt umsetzt');
  assert.ok(nextText(decided).startsWith('Beschlossen zum Schlusskurs vom Freitag, 9. Oktober 2026'));

  const variant = {
    orders: {
      tag: [20609, 20609, 20637, 20637],
      ausfuehrung: [20612, 20613, 20640, 20640],
      idx: [1, 2, 1, 3],
      aktion: ['kauf', 'kauf', 'verkauf', 'kauf'],
      wert: [5000, 5000, 5200, 5100],
      anteil_vorher: [0, 0, 0.5, 0],
      anteil_nachher: [0.5, 0.5, 0, 0.5],
      platz: [1, 2, 9, 1],
      trend: [0.3, 0.2, 0.01, 0.4],
      gebuehr: [1, 1, 1, 1],
      spanne: [5, 5, 5.2, 5.1],
      steuer: [0, 0, 12.5, 0],
      gewinn: [null, null, 150, null],
    },
  } as unknown as RotationVariant;
  const days = rebalanceDays(variant);
  assert.deepEqual(days.map((d) => d.day), [20637, 20609], 'neueste zuerst');
  assert.equal(days[1].execDay, 20612, 'frühester Ausführungstag');
  assert.equal(days[0].taxes, 12.5);
  assert.ok(Math.abs(days[0].fees - 12.3) < 1e-9);
});

test('Gruppenvergleich: Matrix mit identischen Kursfenstern, gleiche Kennzeichnung je ISIN, Häufigkeit nach Platz 1', () => {
  // 3 Zeiträume (Montag als Stichtag: 1–3 Tage beginnen alle am Freitag), Aktien 0–3, Gruppe B nur 0 und 2
  const fri = 20735;
  const row = (h: number, idx: number | undefined, start: number, score = 100): OverviewRow =>
    idx === undefined ? { h, M: 0, empty: 'zu_wenig_tagesdaten' } : { h, M: 5, idx, r: 0.1, score, r2: 0.9, start, tie: false, sole: false };
  const weights = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
  const u: Record<string, OverviewRow[]> = {};
  const ul: Record<string, OverviewRow[]> = {};
  for (const w of weights) {
    // w = 0 im gleichen Vergleichsfeld (U bzw. U ∩ L) – die Matrix nutzt nativ v0 bzw. v0l
    u[String(w)] = [row(1, undefined, fri), row(2, undefined, fri), row(3, 3, fri)];
    ul[String(w)] = [row(1, undefined, fri), row(2, undefined, fri), row(3, 2, fri)];
  }
  const overview = {
    counts: { V: [5, 5, 5], U: [0, 0, 4], L: [2, 2, 2], UL: [0, 0, 2] },
    v0: [row(1, 0, fri), row(2, 0, fri), row(3, 1, fri - 1)],
    u,
    v0l: [row(1, 0, fri), row(2, 0, fri), row(3, 2, fri)],
    ul,
  } as unknown as Overview;
  const instruments = {
    isin: ['ZZ0000000002', 'ZZ0000000001', 'ZZ0000000003', 'ZZ0000000004'],
    calendar: ['XNYS', 'XNYS', 'XETR', 'XNYS'],
    turnover: { liquid: [true, false, true, false] },
    v_bits: [], u_bits: [],
  } as unknown as Instruments;

  const rows = matrixRows(overview, 'a', 1, 3);
  assert.deepEqual(rows[0].cells[0].same, [2], 'Aktie 0: 1 und 2 Tage mit gleichem Start → gleiches Kursfenster');
  assert.deepEqual(rows[2].cells[0].same, [], 'anderer Start → eigenes Fenster');
  assert.equal(sameText(rows[1].cells[0]), 'gleiches Kursfenster wie 1 Tag');
  const coverage = matrixCoverage(rows);
  assert.deepEqual(coverage, { theoretical: 33, computed: 13, empty: { zu_wenig_tagesdaten: 20 } });

  const marks = markers(overview, instruments, 1, 3);
  // Platz 1: Aktie 0 in A (2) und B (2) = 4; Aktie 3 in A 10×; Aktie 2 in B 11×; Aktie 1 einmal
  assert.equal(marks.get(2)!.count, 11);
  assert.equal(marks.get(3)!.count, 10);
  assert.equal(marks.get(0)!.count, 4);
  assert.deepEqual([marks.get(2)!.slot, marks.get(3)!.slot, marks.get(0)!.slot], [0, 1, 2], 'Farbplätze nach Anzahl');
  assert.equal(marks.get(1)!.slot, null, 'einmal ist keine Wiederholung');
  assert.deepEqual([marks.get(0)!.countA, marks.get(0)!.countB], [2, 2]);

  // Häufigkeit: zwei Gewichtungen, Fundstellen Top 3 je Zeitraum
  const occ = (rows: [number, number, number, number][]) => ({ h: rows.map((r) => r[0]), rank: rows.map((r) => r[1]), idx: rows.map((r) => r[2]), score: rows.map(() => 50), r: rows.map(() => 0.1), start: rows.map((r) => r[3]) });
  const freq = {
    cutoff_day: fri + 3,
    M: { v0: [4, 4, 4], u: [0, 0, 3], v0l: [2, 2, 2], ul: [0, 0, 2] },
    occ: {
      v0: occ([[1, 1, 0, fri], [1, 2, 1, fri], [2, 1, 0, fri], [2, 2, 3, fri], [3, 1, 1, fri - 1], [3, 2, 0, fri - 1]]),
      u: { '60': occ([[3, 1, 3, fri - 1], [3, 2, 0, fri - 1], [3, 3, 1, fri - 1]]) },
      v0l: occ([[1, 1, 0, fri], [1, 2, 2, fri], [2, 1, 0, fri], [2, 2, 2, fri], [3, 1, 2, fri], [3, 2, 0, fri - 1]]),
      ul: { '60': occ([[3, 1, 2, fri], [3, 2, 0, fri - 1]]) },
    },
    starts: { XNYS: [fri, fri, fri - 1], XETR: [fri, fri, fri] },
    server_reference: { policy: 'native', weights: 'all', top_k: 10, E: 0, cells: 0, entries: [] },
  } as unknown as FrequencyData;
  const bits = (members: boolean[]) => btoa(String.fromCharCode(...[members.reduce((acc, on, k) => acc | ((on ? 1 : 0) << k), 0), ...new Array(11).fill(0)]));
  const inst = { ...instruments, v_bits: [bits([true, true, true]), bits([true, true, true]), bits([true, true, true]), bits([true, true, true])], u_bits: [bits([false, false, true]), bits([false, false, true]), bits([false, false, true]), bits([false, false, true])] } as unknown as Instruments;

  const a = groupFrequency(freq, inst, { groups: 'a', weights: [0, 60], from: 1, to: 3, dedupe: false });
  assert.deepEqual(a.entries.map((e) => [e.idx, e.a.n1, e.a.n3, e.a.n10, e.a.available]), [
    [0, 2, 4, 4, 4],
    [1, 1, 3, 3, 4],
    [3, 1, 2, 2, 4],
  ], 'Platz 1 zuerst, dann Top 3, Top 10, ISIN; auswertbar = 3 Zeiträume 0/100 + 1 Zeitraum 60/40');
  assert.equal(a.validA, 4);
  const once = groupFrequency(freq, inst, { groups: 'a', weights: [0, 60], from: 1, to: 3, dedupe: true });
  const zero = once.entries.find((e) => e.idx === 0)!;
  assert.deepEqual([zero.a.n1, zero.a.n3, zero.a.n10, zero.a.available], [1, 3, 3, 3], '1 und 2 Tage beginnen beide am Freitag: einmal gezählt');
  assert.equal(once.mergedA, 1);
  const both = groupFrequency(freq, inst, { groups: 'ab', weights: [0, 60], from: 1, to: 3, dedupe: false });
  const first = both.entries[0];
  assert.equal(first.idx, 0);
  assert.deepEqual([first.a.n1, first.b.n1, first.a.available, first.b.available], [2, 2, 4, 4], 'A und B getrennt ausgewiesen');
  const notLiquid = both.entries.find((e) => e.idx === 1)!;
  assert.deepEqual([notLiquid.b.n10, notLiquid.b.available], [0, 0], 'Aktie ohne Umsatzfilter zählt in B nicht');
});

test('1.5: feste Schnellwahl 7–90, Standard 90 Tage, ISIN-Import mit Prüfziffer', () => {
  assert.deepEqual([...FIXED_WINDOWS], [7, 14, 21, 30, 40, 50, 60, 70, 80, 90]);
  assert.equal(parseWindow(null), 90, 'Standardzeitraum 90 Kalendertage');
  assert.equal(DEFAULT_PREFS.h, 90);
  assert.equal(DEFAULT_PREFS.w, 60, 'Standard 60/40');
  assert.equal(sanitizePrefs({ group: 'x' as never, frequencyOrder: 'y' as never }).group, 'a');
  assert.ok(isinCheckDigitOk('US0378331005'));
  assert.ok(isinCheckDigitOk('DE0007164600'));
  assert.ok(!isinCheckDigitOk('US0378331006'), 'falsche Prüfziffer');
  const parsed = parseIsinImport('DE0007164600, US0378331005\nus0378331005; DE0007164601 Apple');
  assert.deepEqual(parsed.valid, ['DE0007164600', 'US0378331005']);
  assert.equal(parsed.duplicates, 1, 'doppelte ISIN zusammengeführt');
  assert.deepEqual(parsed.invalid, ['DE0007164601', 'APPLE'], 'Namen werden nie einer ISIN zugeordnet');
});

test('1.5: identische Kursfenster über gleiche ISIN-/Startdatumsbestände, Sortierung „Meiste Top-10-Nennungen“', () => {
  // 4 Zeiträume; 1 ≡ 2 und 3 ≡ 4 (gleicher Bestand) für 0/100; für 60/40 nur 3 ≡ 4
  const occ = (rows: [number, number, number][]) => ({ h: rows.map((r) => r[0]), rank: rows.map((r) => r[1]), idx: rows.map((r) => r[2]), score: rows.map(() => 50), r: rows.map(() => 0.1), start: rows.map(() => 0) });
  const freq = {
    cutoff_day: 100,
    M: { v0: [2, 2, 2, 2], u: [0, 0, 1, 1] },
    occ: {
      v0: occ([[1, 1, 0], [1, 2, 2], [2, 1, 0], [2, 2, 2], [3, 1, 0], [3, 2, 2], [4, 1, 1], [4, 2, 2]]),
      u: { '60': occ([[3, 1, 2], [4, 1, 2]]) },
    },
    same_set: { v0: [1, 1, 3, 4], u: [1, 2, 3, 3] },
    server_reference: { policy: 'native', weights: 'all', top_k: 10, E: 0, cells: 0, entries: [] },
  } as unknown as FrequencyData;
  const bits = (members: boolean[]) => btoa(String.fromCharCode(...[members.reduce((acc, on, k) => acc | ((on ? 1 : 0) << k), 0), ...new Array(11).fill(0)]));
  const inst = {
    isin: ['ZZ0000000002', 'ZZ0000000001', 'ZZ0000000003'],
    calendar: ['XNYS', 'XNYS', 'XNYS'],
    turnover: { liquid: [true, true, true] },
    v_bits: [bits([true, true, true, true]), bits([true, true, true, true]), bits([true, true, true, true])],
    u_bits: [bits([false, false, false, false]), bits([false, false, false, false]), bits([false, false, true, true])],
  } as unknown as Instruments;

  const n1 = groupFrequency(freq, inst, { groups: 'a', weights: [0], from: 1, to: 4, dedupe: false });
  assert.deepEqual(n1.entries.map((e) => [e.idx, e.a.n1, e.a.n3, e.a.n10]), [[0, 3, 3, 3], [1, 1, 1, 1], [2, 0, 4, 4]], 'gewinnt am häufigsten: Platz 1 zuerst');
  const n10 = groupFrequency(freq, inst, { groups: 'a', weights: [0], from: 1, to: 4, dedupe: false, order: 'n10' });
  assert.deepEqual(n10.entries.map((e) => e.idx), [2, 0, 1], 'Meiste Top-10-Nennungen: Top 10, Top 3, Platz 1, ISIN');

  const once = groupFrequency(freq, inst, { groups: 'a', weights: [0, 60], from: 1, to: 4, dedupe: true });
  const get = (idx: number) => once.entries.find((e) => e.idx === idx)!.a;
  assert.deepEqual([get(0).n1, get(0).n3, get(0).available], [2, 2, 3], 'Aktie 0: Fenster 1 ≡ 2 einmal, 3 eigenes; zugelassen in 3 Beständen (1, 3, 4)');
  assert.deepEqual([get(2).n1, get(2).n10, get(2).available], [1, 4, 4], 'Aktie 2: 60/40 in 3 ≡ 4 einmal; zugelassen 0/100 ×3 und 60/40 ×1');
  assert.equal(once.validA, 3 + 1, 'berechenbar: 0/100 drei Bestände, 60/40 einer');
  assert.equal(once.mergedA, 2 + 1, 'zusammengefasste Top-10-Fundstellen');

  const ov = {
    counts: { V: [2, 2, 2, 2], U: [0, 0, 1, 1] },
    v0: [1, 2, 3, 4].map((h) => ({ h, M: 2, idx: h === 4 ? 1 : 0, r: 0.1, score: 100, start: h <= 2 ? 50 : 40 })),
    u: Object.fromEntries(WEIGHTS.map((w) => [String(w), [1, 2, 3, 4].map((h) => (h >= 3 ? { h, M: 1, idx: 2, r: 0.1, score: 100, start: 40 } : { h, M: 0, empty: 'zu_wenig_tagesdaten' }))])),
    same_set: { v0: [1, 1, 3, 4], u: [1, 2, 3, 3] },
  } as unknown as Overview;
  const rows = matrixRows(ov, 'a', 1, 4);
  assert.deepEqual(rows[0].cells[0].same, [2], '≡ nur bei gleichem Bestand');
  assert.deepEqual(rows[2].cells[0].same, [], 'gleiche Spitzenaktie, anderer Bestand: kein ≡');
  assert.deepEqual(rows[2].cells[6].same, [4], '60/40: 3 ≡ 4');
});

test('1.5: Sieger nach Zeitraum – zehn feste Fenster, eigene Zählung, gleiche Farbe wie in allen Ansichten', () => {
  const winner = (h: number, idx: number | undefined): OverviewRow => (idx === undefined ? { h, M: 0, empty: 'zu_wenig_tagesdaten' } : { h, M: 9, idx, r: 0.05 * idx, score: 90, r2: 0.8, start: 1000 - h, n: h > 20 ? 15 : 5 });
  const days = Array.from({ length: 90 }, (_, k) => k + 1);
  const ov = {
    counts: { V: days.map(() => 9), U: days.map(() => 5), L: days.map(() => 4), UL: days.map(() => 3) },
    v0: days.map((h) => winner(h, h % 3)),
    u: Object.fromEntries(WEIGHTS.map((w) => [String(w), days.map((h) => winner(h, h < 21 ? undefined : 5))])),
    v0l: days.map((h) => winner(h, 7)),
    ul: Object.fromEntries(WEIGHTS.map((w) => [String(w), days.map((h) => winner(h, h < 21 ? undefined : 7))])),
  } as unknown as Overview;
  const instruments = { isin: Array.from({ length: 8 }, (_, k) => `ZZ00000000${k}0`) } as unknown as Instruments;
  const pure = tenWindowRows(ov, 0);
  assert.deepEqual(pure.map((r) => r.h), [7, 14, 21, 30, 40, 50, 60, 70, 80, 90]);
  pure.forEach((r) => {
    assert.equal(r.a.idx, ov.v0[r.h - 1].idx, `0/100, ${r.h} Tage: Sieger A = Platz 1 der Renditeliste`);
    assert.equal(r.b?.idx, 7);
  });
  const mixed = tenWindowRows(ov, 60);
  assert.equal(mixed[0].a.empty, 'zu_wenig_tagesdaten', '7 Tage: Gleichmäßigkeit nicht berechenbar, kein Ersatz durch längeres Fenster');
  assert.equal(mixed[1].a.idx, undefined);
  assert.equal(mixed[2].a.idx, 5, 'ab 21 Tagen berechenbar');
  const counts = tenWindowCounts(mixed, instruments);
  assert.deepEqual(counts.map((c) => [c.idx, c.a, c.b]), [[5, 8, 0], [7, 0, 8]].sort((x, y) => (instruments.isin[x[0]] < instruments.isin[y[0]] ? -1 : 1)), 'Zählung nur über diese zehn Fenster');
  const slots = markerSlots(ov, instruments);
  const marks = markers(ov, instruments, 7, 14);
  for (const [idx, slot] of slots) assert.equal(marks.get(idx)?.slot ?? slot, slot, 'Farbe kommt aus dem ganzen Stand, nicht aus dem Ausschnitt');
});
