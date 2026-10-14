/* „Top 3 nach Zahlen“ (ab 1.11): feste Rechenregel aus Ranglisten-Nennungen, Steig-Konstanz, Kursziel, Volumen
 * und Börsenwert – SYNTHETISCHE Daten. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { FreqRow } from '../src/lib/depots.ts';
import { capPenalty, hitText, placeOf, rankTop, topReason, volumeBadge, volumeShare } from '../src/lib/top.ts';
import type { SignalsData } from '../src/lib/types.ts';

const isinOf = (k: number) => `ZZ00000000${String(k).padStart(2, '0')}`;
/** Geschützte Leerzeichen der Zahlenformate als normale Leerzeichen (lesbare Erwartungen) */
const plain = (text: string | null) => (text === null ? null : text.replace(/[\u00a0\u202f]/g, ' '));

function row(k: number, n10: number, n1 = 0): FreqRow {
  return { idx: k, isin: isinOf(k), n1, n3: n1, n10, available: 66, rank1: null, rank10: null, place1: null, place10: null, both: false };
}

interface Sig {
  k: number;
  konstanz?: number | null;
  kursziel?: number | null;
  rvol?: number | null;
  r5?: number | null;
  r20?: number | null;
  rsi?: number | null;
  umsatz?: number | null;
  cap?: number | null;
  analysts?: number;
  upside?: number | null;
  total?: number | null;
  hit20?: number | null;
  hit60?: number | null;
}

/** Signal-Stand mit den Feldern, die die Regel liest (Rest leer). */
function signals(rows: Sig[], withCap = true): SignalsData {
  const col = <T>(get: (s: Sig) => T) => rows.map(get);
  return {
    isin: col((s) => isinOf(s.k)),
    gesamt: col((s) => s.total ?? null),
    gesamt_teile: { konstanz: col((s) => s.konstanz ?? null), kursziel: col((s) => s.kursziel ?? null), kurzfristig: col(() => null), qualitaet: col(() => null) },
    gesamt_steigt_20: col((s) => s.hit20 ?? null),
    gesamt_steigt_60: col((s) => s.hit60 ?? null),
    merkmale: { rvol: col((s) => s.rvol ?? null), r5: col((s) => s.r5 ?? null), r20: col((s) => s.r20 ?? null), rsi: col((s) => s.rsi ?? null), umsatz_eur: col((s) => s.umsatz ?? null) },
    potenzial: col((s) => s.upside ?? null),
    analysten: col((s) => s.analysts ?? 0),
    ...(withCap ? { boersenwert_eur: col((s) => s.cap ?? null) } : {}),
  } as unknown as SignalsData;
}

test('Punkte nach der Regel: 40 vorne, 25 steigt, 20 Analysten, 15 Volumen, Abzug Börsenwert', () => {
  const data = signals([
    { k: 0, konstanz: 80, kursziel: 50, rvol: 2.5, r5: 0.04, cap: 1e9, analysts: 8, upside: 0.3, total: 70 },
    { k: 1, konstanz: 100, kursziel: 100, rvol: 3, r5: 0.1, cap: 1e8, analysts: 2, upside: 1.58, total: 75 },
    { k: 2, konstanz: 100, kursziel: 100, rvol: 3, r5: 0.1, cap: 2e7, analysts: 6, upside: 0.9, total: 80 },
  ]);
  const result = rankTop([row(0, 33, 4), row(1, 66, 10), row(2, 66, 2)], 66, data);
  const a = placeOf(result, isinOf(0))!;
  assert.deepEqual(a.parts, { vorne: 20, steigt: 20, analysten: 10, volumen: 15 });
  assert.equal(a.penalty, 0);
  assert.equal(a.points, 65);
  const b = placeOf(result, isinOf(1))!;
  assert.equal(b.penalty, 10, 'unter 300 Mio. € −10');
  assert.equal(b.points, 90);
  const c = placeOf(result, isinOf(2))!;
  assert.equal(c.penalty, 20, 'unter 50 Mio. € −20');
  assert.equal(c.points, 80);
  assert.deepEqual(
    result.entries.map((e) => e.isin),
    [isinOf(1), isinOf(2), isinOf(0)],
  );
  assert.deepEqual(
    result.entries.map((e) => e.place),
    [1, 2, 3],
  );
  assert.ok(result.withSignals && result.withCap);
});

test('Volumen zählt nur bei steigendem Kurs; 1,0-fach = 0, ab 2,0-fach voll', () => {
  assert.equal(volumeShare(1.5, 0.02), 0.5);
  assert.equal(volumeShare(2.4, 0.02), 1);
  assert.equal(volumeShare(0.7, 0.02), 0);
  assert.equal(volumeShare(3, -0.01), 0, 'Volumen bei fallendem Kurs zählt nicht');
  assert.equal(volumeShare(3, null), 0);
  assert.equal(volumeShare(null, 0.02), null);
  assert.equal(volumeBadge(1.4), null);
  assert.equal(volumeBadge(2.44), 'Volumen 2,4-fach');
});

test('Abzug für kleinen Börsenwert; ohne Angabe kein Abzug', () => {
  assert.equal(capPenalty(5e9), 0);
  assert.equal(capPenalty(3e8), 0);
  assert.equal(capPenalty(2.99e8), 10);
  assert.equal(capPenalty(4.9e7), 20);
  assert.equal(capPenalty(null), 0);
});

test('Nur Aktien mit Top-10-Nennung; fehlende Signale zählen 0 Punkte und werden genannt', () => {
  const data = signals([{ k: 0, konstanz: 90, kursziel: 90, rvol: 2, r5: 0.1, cap: 5e9, analysts: 10 }]);
  const result = rankTop([row(0, 0, 0), row(1, 22)], 66, data);
  assert.deepEqual(
    result.entries.map((e) => e.isin),
    [isinOf(1)],
    'ohne Top-10-Nennung nicht in der Wertung',
  );
  const only = result.entries[0];
  assert.equal(only.sig, null);
  assert.equal(only.points, 13, '40 × 22/66 = 13,3 → 13; übrige Teile 0');
  assert.ok(only.warnings.some((w) => w.key === 'ohne_signale'));
});

test('Gleiche Punkte: mehr Top-10-Nennungen, dann erste Plätze, dann Gesamtwertung, dann ISIN', () => {
  const data = signals([
    { k: 0, total: 60 },
    { k: 1, total: 70 },
    { k: 2, total: 50 },
    { k: 3, total: 50 },
  ]);
  // je 40 × n10/66 Punkte: 33 → 20, 33 → 20; 33 mit mehr ersten Plätzen; zwei völlig gleiche nach ISIN
  const result = rankTop([row(3, 33, 1), row(2, 33, 1), row(0, 33, 5), row(1, 33, 5)], 66, data);
  assert.deepEqual(
    result.entries.map((e) => e.isin),
    [isinOf(1), isinOf(0), isinOf(2), isinOf(3)],
  );
});

test('Warnzeichen: sehr kleiner Börsenwert, verdoppelt, wenige Analysten, überkauft, wenig Umsatz', () => {
  const data = signals([{ k: 0, konstanz: 70, kursziel: 40, rvol: 5, r5: 0.5, r20: 4.95, rsi: 82, umsatz: 4e5, cap: 4e7, analysts: 2, upside: 1.58 }]);
  const entry = rankTop([row(0, 50, 12)], 66, data).entries[0];
  assert.deepEqual(
    entry.warnings.map((w) => w.key),
    ['kleinstwert', 'verdoppelt', 'wenige_analysten', 'ueberkauft', 'wenig_umsatz'],
  );
  assert.match(plain(entry.warnings[1].text)!, /\+495 % – mehr als verdoppelt/);
  assert.match(plain(topReason(entry))!, /in 50 von 66 Standard-Ranglisten unter den ersten 10 · 12× Platz 1 · Kursziel \+158 % \(2 Analysten\) · Volumen 5,0-fach/);
});

test('Ohne Börsenwert im Signal-Stand (vor 1.11): kein Abzug, kein Warnzeichen dazu', () => {
  const data = signals([{ k: 0, konstanz: 50, kursziel: 50, analysts: 6 }], false);
  const result = rankTop([row(0, 66)], 66, data);
  assert.equal(result.withCap, false);
  assert.equal(result.entries[0].penalty, 0);
  assert.equal(result.entries[0].points, 63, '40 + 12,5 + 10 = 62,5 → 63');
  assert.ok(!result.entries[0].warnings.some((w) => w.key === 'klein' || w.key === 'kleinstwert'));
});

test('Trefferquote als Text mit Vergleich zu allen Aktien', () => {
  const data = signals([{ k: 0, konstanz: 60, hit20: 0.58, hit60: 0.61 }]);
  const entry = rankTop([row(0, 10)], 66, data).entries[0];
  assert.equal(plain(hitText(entry, 0.52)), 'Früher bei ähnlicher Steig-Konstanz 20 Handelstage später höher: 58 % (alle Aktien 52 %), nach 60: 61 %');
  assert.equal(hitText({ ...entry, hit20: null }, 0.52), null);
});
