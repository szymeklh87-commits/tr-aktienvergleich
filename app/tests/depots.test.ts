/* Musterdepots (ab 1.9): zwei Top-10-Listen aus der Häufigkeit, Rendite je Aktie in USD/EUR/Originalwährung,
 * Beiträge, Gewichte, Fenster 1–30, eigene Depots – SYNTHETISCHE Daten. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  byTops,
  byWins,
  computeDepot,
  depotWindows,
  fxCurrency,
  fxLookup,
  lastAtOrBefore,
  memberReturn,
  ownDepotDefs,
  parseWeightChoice,
  reportDepots,
  sanitizeDepots,
  selectionFor,
  weightShift,
  winnersByWeight,
  sortPositions,
  topLists,
  weekdayAtOrBefore,
  type FreqRow,
} from '../src/lib/depots.ts';
import { DEFAULT_DEPOTS, sanitizePrefs } from '../src/lib/storage.ts';
import type { FrequencyData, FxData, Instruments, SeriesData } from '../src/lib/types.ts';

const isinOf = (k: number) => `ZZ00000000${String(k).padStart(2, '0')}`;
const bits = (windows: number[]) => {
  const bytes = new Array(12).fill(0);
  for (const h of windows) bytes[(h - 1) >> 3] |= 1 << ((h - 1) & 7);
  return btoa(String.fromCharCode(...bytes));
};
const H = Array.from({ length: 30 }, (_, k) => k + 1);

/* A (0/100): Platz 1 = Aktie 0 (1–15 Tage), 1 (16–25), 2 (26–30); Plätze 2–10 = Aktien 3 … 11.
 * B (0/100): Platz 1 = Aktie 12, Platz 2 = Aktie 0. Übrige Gewichtungen ohne Ranglisten. */
function frequency(): FrequencyData {
  const occ = (rows: [number, number, number][]) => ({ h: rows.map((r) => r[0]), rank: rows.map((r) => r[1]), idx: rows.map((r) => r[2]), score: rows.map(() => 50), r: rows.map(() => 0.1), start: rows.map(() => 0) });
  const a: [number, number, number][] = [];
  const b: [number, number, number][] = [];
  for (const h of H) {
    a.push([h, 1, h <= 15 ? 0 : h <= 25 ? 1 : 2]);
    for (let k = 0; k < 9; k += 1) a.push([h, k + 2, k + 3]);
    b.push([h, 1, 12], [h, 2, 0]);
  }
  const zeros = Array(90).fill(0);
  return {
    cutoff_day: 20739,
    M: { v0: Array(90).fill(12), u: zeros, v0l: Array(90).fill(2), ul: zeros },
    occ: { v0: occ(a), u: {}, v0l: occ(b), ul: {} },
    server_reference: { policy: 'native', weights: 'all', top_k: 10, E: 0, cells: 0, entries: [] },
  } as unknown as FrequencyData;
}

const instruments = {
  isin: Array.from({ length: 13 }, (_, k) => isinOf(k)),
  name: Array.from({ length: 13 }, (_, k) => `Aktie ${k}`),
  tr_name: Array(13).fill(''),
  calendar: Array(13).fill('XNYS'),
  turnover: { liquid: Array(13).fill(true) },
  v_bits: Array(13).fill(bits(H)),
  u_bits: Array(13).fill(bits([])),
} as unknown as Instruments;

test('Zwei Top-10-Listen wie im Bericht: erste Plätze, Top-10-Nennungen, beide zusammen, gemeinsame', () => {
  const lists = topLists(frequency(), instruments, 'bericht');
  assert.deepEqual(
    lists.firsts.map((r) => [r.idx, r.n1]),
    [[12, 30], [0, 15], [1, 10], [2, 5], [3, 0], [4, 0], [5, 0], [6, 0], [7, 0], [8, 0]],
    'ab 1.14: zuerst die Aktien mit ersten Plätzen, dann aufgefüllt nach Top 3, Top 10, ISIN – immer zehn',
  );
  assert.equal(lists.filled, 6);
  assert.deepEqual(lists.firsts.map((r) => Boolean(r.filled)), [false, false, false, false, true, true, true, true, true, true]);
  assert.deepEqual(lists.tops.map((r) => r.idx), [0, 12, 3, 4, 5, 6, 7, 8, 9, 10], 'Top-10-Nennungen, bei Gleichstand erste Plätze, Top 3, ISIN');
  assert.equal(lists.tops[0].n10, 45);
  assert.deepEqual(lists.both.map((r) => r.idx), [12, 0, 3, 4, 5, 6, 7, 8]);
  assert.equal(lists.union.length, 12, 'jede ISIN nur einmal');
  assert.equal(lists.union.find((r) => r.idx === 0)!.rank1, 2);
  assert.equal(lists.union.find((r) => r.idx === 0)!.rank10, 1);
  assert.equal(lists.union.find((r) => r.idx === 1)!.rank10, null, 'außerhalb der Top-10-Liste');
  const one = lists.union.find((r) => r.idx === 1)!;
  assert.ok(one.place10 !== null && one.place10 > 10, 'Rang in der vollständigen Reihenfolge, auch über 10 (Anzeige statt „außerhalb“)');
  assert.equal(one.place1, one.rank1, 'innerhalb der Top 10: Rang = Platz');
  assert.equal(lists.union.find((r) => r.idx === 3)!.place1, null, 'ohne ersten Platz kein Rang');
  for (const r of lists.union) {
    if (r.rank1 !== null && !r.filled) assert.equal(r.place1, r.rank1);
    if (r.filled) assert.equal(r.place1, null, 'aufgefüllt: Platz im Depot, aber kein Rang nach ersten Plätzen');
    if (r.rank10 !== null) assert.equal(r.place10, r.rank10);
  }
  assert.equal(lists.valid, 60, 'gültig: 30 Zeiträume 0/100 in A und B; 40/60, 50/50, 60/40 ohne Rangliste');
  assert.equal(lists.possible, 240);
  const depots = reportDepots(lists);
  assert.deepEqual(depots.map((d) => [d.key, d.isins.length]), [['siege', 10], ['top10', 10]], 'beide Zehnerdepots vollständig');
  const onlyA = topLists(frequency(), instruments, 'bericht', 'a');
  assert.deepEqual(onlyA.firsts.map((r) => r.idx), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
  assert.equal(onlyA.possible, 120);
  const row = (isin: string, n1: number, n3: number, n10: number): FreqRow => ({ idx: 0, isin, n1, n3, n10, available: 0, rank1: null, rank10: null, place1: null, place10: null, both: false });
  assert.ok(byWins(row('B', 2, 2, 2), row('A', 1, 9, 9)) < 0, 'erste Plätze zuerst');
  assert.ok(byTops(row('B', 0, 0, 9), row('A', 5, 5, 8)) < 0, 'Top-10-Nennungen zuerst');
  assert.ok(byTops(row('B', 2, 0, 9), row('A', 1, 5, 9)) < 0, 'dann erste Plätze vor Top 3');
});

test('Ab 1.10: Standard 40/60, 50/50, 60/40, ausführlich alle elf (Datei v3), Top 20, Sieger je Gewichtung, Vergleich Standard → 11', () => {
  assert.equal(parseWeightChoice(null), 'kurz', 'Standard: 40/60, 50/50, 60/40');
  assert.equal(parseWeightChoice('alle'), 'alle');
  assert.equal(parseWeightChoice('bericht'), 'bericht');
  assert.equal(parseWeightChoice('40'), 40);
  assert.equal(parseWeightChoice('45'), 'kurz', 'nur die elf Gewichtungen');
  assert.deepEqual(selectionFor('kurz').weights, [40, 50, 60]);
  assert.deepEqual(selectionFor('alle').weights, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]);
  assert.equal(selectionFor('alle', 90).to, 90);
  const all = topLists(frequency(), instruments, selectionFor('alle'), 'ab', 20);
  assert.equal(all.size, 20);
  assert.equal(all.possible, 660, '30 Zeiträume × 11 Gewichtungen × 2 Gruppen');
  assert.equal(all.valid, 60, 'nur 0/100 hat in den Testdaten Ranglisten');
  assert.deepEqual(all.firsts.map((r) => r.idx), [12, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], 'Top 20: alle 13 genannten Aktien, 9 aufgefüllt');
  assert.equal(all.filled, 9);
  assert.equal(all.tops.length, 13, 'Top 20: alle 13 genannten Aktien');
  assert.ok(all.tops.every((r) => r.rank10 !== null && r.rank10 <= 20));
  assert.equal(topLists(frequency(), instruments, selectionFor('kurz')).valid, 0, 'kurz: ohne Ranglisten in den Testdaten');
  const winners = winnersByWeight(frequency(), instruments, 30);
  assert.equal(winners.length, 11);
  assert.equal(winners[0].weight, 0);
  assert.equal(winners[0].row?.idx, 12);
  assert.equal(winners[0].row?.n1, 30);
  assert.equal(winners[0].valid, 60);
  assert.equal(winners[5].row, null, '50/50 ohne Rangliste');
  assert.equal(winners[5].valid, 0);
  const shift = weightShift(frequency(), instruments, 20);
  assert.equal(shift.validBefore, 0, 'Standard 40/60–60/40: in den Testdaten ohne Ranglisten');
  assert.equal(shift.validAfter, 60);
  assert.equal(shift.shifts.length, 13);
  assert.ok(shift.shifts.every((s) => s.before === null && s.n10Before === 0), 'ohne Nennung in der Standardauswahl kein Rang');
});

/* Kursreihen: Stichtag D (Dienstag); Aktie U in USD, Aktie J in JPY (Feiertage am 05. und 06.10.), Aktie N erst ab D − 5 */
const D = 20739; // 13.10.2026, Dienstag
const days = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, k) => from + k).filter((d) => ![0, 6].includes((((d + 4) % 7) + 7) % 7));
function series(isin: string, currency: string, d: number[], close: (day: number) => number, volume: (day: number) => number = () => 1000): SeriesData {
  return { isin, listing: { currency, price_unit: currency, unit_factor: 1 }, d, c: d.map(close), v: d.map(volume), provisional: null } as unknown as SeriesData;
}
const U = series('US0000000001', 'USD', days(D - 60, D), (day) => 100 + (day - (D - 60)));
const J = series(
  'JP0000000002',
  'JPY',
  days(D - 60, D).filter((day) => day !== D - 7 && day !== D - 8),
  (day) => 1000 + 10 * (day - (D - 60)),
  (day) => (day === D - 11 ? 0 : 500),
);
const N = series('CA0000000003', 'USD', days(D - 5, D), () => 50);
const fx: FxData = {
  schema: 'tr-fx/1',
  snapshot_id: 'x',
  quelle: 'Test',
  url: null,
  abgerufen_utc: null,
  max_alter_tage: 5,
  basis: '',
  tage: days(D - 60, D),
  je_eur: {
    USD: days(D - 60, D).map((day) => (day <= D - 7 ? 1.1 : 1.2)),
    JPY: days(D - 60, D).map((day) => (day <= D - 7 ? 160 : 150)),
  },
};

test('Rendite je Aktie: Startkurs am oder vor Stichtag − h, Wechselkurs des Kurstags, nichts aufgefüllt', () => {
  const look = fxLookup(fx);
  const u = memberReturn(U.isin, U, D, 7, 'usd', look);
  assert.ok(u.ok);
  assert.equal(u.startDay, D - 7);
  assert.equal(u.endDay, D);
  assert.equal(u.ret, u.localReturn, 'USD-Aktie in USD: keine Umrechnung');
  assert.ok(Math.abs(u.localReturn - (160 / 153 - 1)) < 1e-12);
  // JPY: am 06.10. (D − 7) und 05.10. (D − 8) kein Kurs → Start = Freitag 02.10. (D − 11)
  const j = memberReturn(J.isin, J, D, 7, 'usd', look);
  assert.ok(j.ok);
  assert.equal(j.startDay, D - 11);
  const c0 = 1000 + 10 * 49;
  const c1 = 1000 + 10 * 60;
  assert.ok(Math.abs(j.ret - (c1 * (1.2 / 150)) / (c0 * (1.1 / 160)) + 1) < 1e-12, 'USD-Rendite mit Kreuzkurs USD je JPY');
  assert.deepEqual(j.flags, ['Startkurs ohne gemeldeten Umsatz']);
  const jEur = memberReturn(J.isin, J, D, 7, 'eur', look);
  assert.ok(jEur.ok && Math.abs(jEur.ret - (c1 / 150 / (c0 / 160) - 1)) < 1e-12, 'EUR-Rendite');
  const jLocal = memberReturn(J.isin, J, D, 7, 'lokal', null);
  assert.ok(jLocal.ok && Math.abs(jLocal.ret - (c1 / c0 - 1)) < 1e-12, 'Originalwährung');
  const n = memberReturn(N.isin, N, D, 30, 'usd', look);
  assert.equal(n.ok, false);
  assert.match((n as { reason: string }).reason, /kein Startkurs/);
  assert.equal(memberReturn('XX0000000000', undefined, D, 5, 'usd', look).ok, false);
  const noFx = memberReturn(J.isin, J, D, 7, 'usd', fxLookup({ ...fx, je_eur: { USD: fx.je_eur.USD } }));
  assert.equal(noFx.ok, false);
  assert.match((noFx as { reason: string }).reason, /kein Wechselkurs für JPY/);
  assert.equal(fxCurrency('GBp'), 'GBP');
  assert.equal(fxCurrency('ZAc'), 'ZAR');
});

test('Depot: gleiche Startgewichte, Beiträge ergeben die Depotrendite, Endgewichte und Endwerte', () => {
  const map = new Map([U, J, N].map((s) => [s.isin, s]));
  const look = fxLookup(fx);
  const depot = computeDepot([U.isin, J.isin, N.isin, U.isin], map, D, 5, 'usd', look, 1000, (isin) => (isin === J.isin ? ['sehr geringer Ø Tagesumsatz'] : []));
  assert.equal(depot.positions.length, 3, 'doppelte ISIN nur einmal, N hat bei 5 Tagen einen Startkurs');
  const w0 = depot.positions[0].w0;
  assert.ok(Math.abs(w0 - 1 / 3) < 1e-12);
  const sum = depot.positions.reduce((s, p) => s + p.contribution, 0);
  assert.ok(Math.abs(sum - depot.ret!) < 1e-12, 'Summe der Beiträge = Depotrendite');
  assert.ok(Math.abs(depot.positions.reduce((s, p) => s + p.w1, 0) - 1) < 1e-12, 'Endgewichte ergeben 100 %');
  assert.ok(Math.abs(depot.positions.reduce((s, p) => s + p.endValue, 0) - depot.endValue!) < 1e-9);
  assert.ok(Math.abs(depot.endValue! - 1000 * (1 + depot.ret!)) < 1e-9);
  assert.equal(depot.flagged, true, '† bei Umsatzhinweis');
  const thirty = computeDepot([U.isin, J.isin, N.isin], map, D, 30, 'usd', look, 1000);
  assert.equal(thirty.positions.length, 2);
  assert.deepEqual(thirty.missing.map((m) => m.isin), [N.isin], 'ohne Startkurs draußen, Gewichte auf die übrigen verteilt');
  assert.ok(Math.abs(thirty.positions[0].w0 - 0.5) < 1e-12);
  const sorted = sortPositions(depot.positions, 'beitrag', (isin) => isin);
  for (let k = 1; k < sorted.length; k += 1) assert.ok(sorted[k - 1].contribution >= sorted[k].contribution);
  assert.deepEqual(sortPositions(depot.positions, 'name', (isin) => ({ [U.isin]: 'Zeta', [J.isin]: 'Alpha', [N.isin]: 'Mitte' })[isin]!).map((p) => p.isin), [J.isin, N.isin, U.isin]);
  const empty = computeDepot(['XX0000000000'], map, D, 7, 'usd', look, 1000);
  assert.equal(empty.ret, null);
  assert.equal(empty.endValue, null);
});

test('Alle Depots für 1–30 Tage: getrennte Fenster mit Bewertungsstart am Werktag', () => {
  const map = new Map([U, J, N].map((s) => [s.isin, s]));
  const defs = [...ownDepotDefs([{ name: 'Zwei', isins: [U.isin, J.isin] }]), { key: 'n', name: 'N', isins: [N.isin], kind: 'eigen' as const }];
  const rows = depotWindows(defs, map, D, 'lokal', null, 30);
  assert.equal(rows.length, 30);
  assert.deepEqual(rows.map((r) => r.h).slice(0, 3), [1, 2, 3]);
  assert.equal(rows[0].values[0].members, 2);
  assert.equal(rows[29].values[1].ret, null, 'N: ab 6 Tagen kein Startkurs');
  assert.equal(rows[4].values[1].ret, 0, 'N: unveränderter Kurs');
  // 13.10.2026 (Di) − 2 = So 11.10. → Fr 09.10.
  assert.equal(weekdayAtOrBefore(D - 2), D - 4);
  assert.equal(weekdayAtOrBefore(D - 3), D - 4, 'Samstag → Freitag');
  assert.equal(weekdayAtOrBefore(D), D);
  assert.equal(lastAtOrBefore([1, 3, 5], 4), 1);
  assert.equal(lastAtOrBefore([1, 3, 5], 0), -1);
});

test('Eigene Depots: Name und ISINs geprüft, Standard Dreier- und Viererdepot, Löschen bleibt gelöscht', () => {
  const clean = sanitizeDepots([
    { name: '  Mein Depot  ', isins: ['us74624m1027', 'US74624M1027', 'kein', 'US50015M1099'] },
    { name: '', isins: ['US74624M1027'] },
    { name: 'Leer', isins: [] },
    'Unsinn',
  ]);
  assert.deepEqual(clean, [{ name: 'Mein Depot', isins: ['US74624M1027', 'US50015M1099'] }]);
  assert.equal(sanitizeDepots(Array.from({ length: 12 }, (_, k) => ({ name: `D${k}`, isins: ['US74624M1027'] }))).length, 8);
  assert.deepEqual(sanitizePrefs(null).depots, DEFAULT_DEPOTS);
  assert.deepEqual(DEFAULT_DEPOTS.map((d) => d.isins.length), [3, 4]);
  assert.deepEqual(sanitizePrefs({ depots: [] }).depots, [], 'alle gelöscht: keine Standarddepots zurückholen');
  assert.equal(sanitizePrefs({ depotBasis: 'chf' as never }).depotBasis, 'usd');
  assert.equal(sanitizePrefs({ depotCapital: -5 }).depotCapital, 1000);
  assert.equal(sanitizePrefs({ depotCapital: 2500 }).depotCapital, 2500);
});
