/* Gleichstand in der App (ab 1.18, ranking-11w-v3) und verständliche Gründe bei fehlenden Kurstagen. SYNTHETISCHE Zahlen.
 *
 * Dieselben Referenzfälle wie tests/unit/test_referenz_gleichstand.py: Die App ordnet Untergruppen (Watchlist) selbst.
 * Bei rechnerisch gleichem Score entscheidet die höhere Kursrendite, dann die ISIN – nicht die letzte Stelle des
 * Gleitkomma-Scores. Erwartet wird mit eigener Bruchrechnung (BigInt), nicht mit den Funktionen der App.
 */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { coverageFacts, missingDataNote } from '../src/lib/codes.ts';
import * as f from '../src/lib/format.ts';
import { exactScoreKey, pctFromDoubled, weightedScore } from '../src/lib/scoring.ts';
import { rankSubgroup } from '../src/lib/subgroup.ts';
import type { WindowData } from '../src/lib/types.ts';

/** 15 Aktien, 60/40: Y (Index 0) und X (Index 1) haben rechnerisch denselben Score 640/7 (siehe Python-Referenzfall). */
const FIRST_G = [15, 13, 14, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
const FIRST_R = [12, 15, 1, 14, 13, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2];
const [Y, X] = [0, 1];

/** Fensterdatei mit allen Aktien in V und U; Werte zu den vorgegebenen Rängen (alle verschieden). */
function windowOf(rankG: number[], rankR: number[]): WindowData {
  const n = rankG.length;
  const idx = rankG.map((_, i) => i);
  const r = rankR.map((x) => 0.001 * x);
  const r2 = rankG.map((g) => 0.3 + (0.6 * g) / (n + 1));
  const byReturn = [...idx].sort((a, b) => r[b] - r[a] || a - b);
  const byR2 = [...idx].sort((a, b) => r2[b] - r2[a] || r[b] - r[a] || a - b);
  return {
    schema: 'test',
    h: 30,
    part: 'vollstaendig',
    cutoff_day: 20000,
    target_start_day: 19970,
    counts: { V: n, U: n },
    m: {
      idx,
      start: idx.map(() => 19970),
      n: idx.map(() => 21),
      n_exp: idx.map(() => 21),
      r,
      r2,
      slope: idx.map(() => 1),
      noise: idx.map(() => 1),
      mdd: idx.map(() => 0),
      vol: idx.map(() => 1),
      wf: idx.map(() => 0),
      a_rv: rankR.map((x) => 2 * x),
      a_gu: rankG.map((g) => 2 * g),
      a_ru: rankR.map((x) => 2 * x),
    },
    orders: { v0: byReturn, u: { '0': byReturn, '100': byR2 } },
    ties: { v0: [], u: {} },
  };
}

/** Score · 2·(M − 1) als exakte Ganzzahl (BigInt): w·(2·Rang_G − 2) + (100 − w)·(2·Rang_R − 2). */
function exactKey(weight: number, rankG: number, rankR: number): bigint {
  return BigInt(weight) * BigInt(2 * rankG - 2) + BigInt(100 - weight) * BigInt(2 * rankR - 2);
}

test('Untergruppe: rechnerisch gleicher Score auf Platz 1 – die höhere Rendite gewinnt, nicht die Rundung', () => {
  const win = windowOf(FIRST_G, FIRST_R);
  const all = win.m.idx;
  assert.equal(exactKey(60, FIRST_G[X], FIRST_R[X]), exactKey(60, FIRST_G[Y], FIRST_R[Y]));
  const m = all.length;
  const floatX = weightedScore(60, pctFromDoubled(2 * FIRST_G[X], m), pctFromDoubled(2 * FIRST_R[X], m));
  const floatY = weightedScore(60, pctFromDoubled(2 * FIRST_G[Y], m), pctFromDoubled(2 * FIRST_R[Y], m));
  assert.ok(floatY > floatX, 'als Gleitkommazahl ist Y eine Stelle größer');
  const result = rankSubgroup(win, all, 'native', 60, 'Test');
  assert.deepEqual(
    result.entries.slice(0, 2).map((e) => e.idx),
    [X, Y],
  );
  assert.deepEqual(
    result.entries.slice(0, 2).map((e) => e.tie),
    [true, true],
  );
  // jede gemischte Gewichtung: Reihenfolge = eigene exakte Rechnung (Score, Rendite, ISIN)
  for (const weight of [10, 20, 30, 40, 50, 60, 70, 80, 90]) {
    const expected = [...all].sort((a, b) => {
      const ka = exactKey(weight, FIRST_G[a], FIRST_R[a]);
      const kb = exactKey(weight, FIRST_G[b], FIRST_R[b]);
      if (ka !== kb) return ka > kb ? -1 : 1;
      return FIRST_R[b] - FIRST_R[a] || a - b;
    });
    assert.deepEqual(
      rankSubgroup(win, all, 'native', weight, 'Test').entries.map((e) => e.idx),
      expected,
      `w=${weight}`,
    );
  }
});

test('Untergruppe: gleicher Score und gleiche Rendite – die kleinere ISIN steht vorn, Gleichstand markiert', () => {
  // Aktie 7 bekommt dieselbe Rendite und dasselbe R² wie Aktie 3 – die App rechnet die Ränge daraus selbst neu
  const win = windowOf([1, 2, 3, 6, 5, 4, 8, 7, 9, 10], [10, 9, 8, 4, 6, 5, 2, 3, 7, 1]);
  win.m.r[7] = win.m.r[3];
  win.m.r2[7] = win.m.r2[3];
  for (const weight of [10, 50, 60, 90]) {
    const entries = rankSubgroup(win, win.m.idx, 'native', weight, 'Test').entries;
    const at3 = entries.findIndex((e) => e.idx === 3);
    const at7 = entries.findIndex((e) => e.idx === 7);
    assert.equal(at7, at3 + 1, `w=${weight}: 3 direkt vor 7`);
    assert.ok(entries[at3].tie && entries[at7].tie, `w=${weight}: Gleichstand markiert`);
    assert.equal(entries[at3].score, entries[at7].score);
  }
});

test('Schlüssel: knapp verschiedene Scores bleiben verschieden (kein Runden auf Stellen)', () => {
  // 1.001 Aktien, 60/40: P (R²-Rang 900, Rendite-Rang 500) 73,90; Q (899, 501) 73,88 – mit einer Stelle beide 73,9
  const keyP = exactScoreKey(60, 2 * 900, 2 * 500);
  const keyQ = exactScoreKey(60, 2 * 899, 2 * 501);
  assert.deepEqual([keyP, keyQ], [147_800, 147_760]);
  assert.ok(keyP > keyQ);
  const scoreP = weightedScore(60, pctFromDoubled(1800, 1001), pctFromDoubled(1000, 1001));
  const scoreQ = weightedScore(60, pctFromDoubled(1798, 1001), pctFromDoubled(1002, 1001));
  assert.equal(f.score(scoreP), f.score(scoreQ), 'Anzeige mit einer Stelle gleich');
  assert.ok(scoreP > scoreQ);
});

test('Fehlende Kurstage: Startkurs fehlt und zu viele Börsentage ohne Kurs mit den Zahlen des Zeitraums', () => {
  // Börsentage 1…23 (Tagesnummern 100…122); Kurse fehlen an 103, 104, 108, 110, 115 (5 von 23 = 22 %)
  const sessions = Array.from({ length: 23 }, (_, k) => 100 + k);
  const gaps = [103, 104, 108, 110, 115];
  const series = { d: sessions.filter((d) => !gaps.includes(d)), gaps, window_start: [] as (number | null)[] };
  series.window_start[29] = 100;
  const facts = coverageFacts(series, 30, 122);
  assert.deepEqual(facts, { start: 100, end: 122, expected: 23, withPrice: 18, missing: 5 });
  const method = { min_session_coverage: { num: 4, den: 5 }, tolerated_missing_sessions: 1 };
  const note = missingDataNote(12, facts, method, (d) => `Tag ${d}`)!;
  assert.match(note, /23 Börsentage/);
  assert.match(note, /Schlusskurse liegen für 18 vor, 5 fehlen \(22 %\)/);
  assert.match(note, /höchstens 20 % fehlende Börsentage/);
  assert.match(note, /weder ersetzt noch als null gezählt/);
  // Startkurs fehlt: der erste Börsentag des Zeitraums selbst ist eine Lücke
  const start = { d: sessions.slice(1), gaps: [100], window_start: [] as (number | null)[] };
  start.window_start[29] = 100;
  assert.match(missingDataNote(11, coverageFacts(start, 30, 122), method, (d) => `Tag ${d}`)!, /dem Tag 100, fehlt der Schlusskurs.*keinen älteren Kurs/);
  // andere Gründe: kein eigener Text (es gilt der Statustext des Datenstands)
  assert.equal(missingDataNote(16, facts, method, (d) => `Tag ${d}`), null);
  assert.equal(coverageFacts({ d: [], gaps: [], window_start: [null] }, 1, 122), null);
});
