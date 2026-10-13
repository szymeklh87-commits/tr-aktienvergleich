/* Reine Funktionstests der App (ohne Browser, ohne Netz).  Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { commonBase, segments, transform, windowPoints, type Point } from '../src/lib/chartmath.ts';
import { csvCell, toCsv } from '../src/lib/csv.ts';
import * as f from '../src/lib/format.ts';
import { cohortFor, decodeBits, decodeRanks, parsePolicy, parseWeight, parseWindow, pctFromDoubled, rankFromMatrix, rankInColumn, weightedScore, WEIGHTS } from '../src/lib/scoring.ts';
import { listEntries, parseReturnList, thresholdLabel, turnoverBasis, turnoverShort, type TurnoverInfo } from '../src/lib/turnover.ts';
import type { Instruments, Manifest, WindowData } from '../src/lib/types.ts';
import { venueDetails, venueListText, venueOf, venuePair, venueShort } from '../src/lib/venue.ts';
import { nextCutoff, outcomeFor, outcomeText, waitFrom, WAIT_MAX_MS } from '../src/lib/update.ts';
import type { Status } from '../src/lib/types.ts';
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
  assert.deepEqual(venueDetails(old, info, pair, 'USD', 0.5), []);
  // Zeilen in Ranglisten: kurz; ohne Ergebnis für den Zeitraum keine Zeile statt einer falschen Aussage
  assert.equal(venueListText(manifest, info, pair), `Vergleich mit Xetra (APC.DE): auffällige Abweichung – dort +38,00${NBSP}%`);
  assert.equal(venueListText(manifest, info, { ...pair, status: 'ok' }), `Vergleich mit Xetra (APC.DE): unauffällig, dort +38,00${NBSP}%`);
  assert.equal(venueListText(manifest, info, undefined), '');
  assert.equal(venueListText(manifest, venueOf(instruments, 2), undefined), 'Vergleich mit zweitem Börsenplatz: kein zweiter Börsenplatz');
  assert.equal(venueListText(manifest, null, pair), '');
  assert.equal(venueListText(old, info, pair), '');
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
