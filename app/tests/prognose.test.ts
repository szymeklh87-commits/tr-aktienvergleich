/* Wahrscheinlichkeiten, Ereignisse, Analystenszenarien und Gesamtbild (ab 1.25.0) – ohne Browser. Aufruf: npm test
 *
 * Simons Vorgaben vom 07.11.2026 (17:58 und 19:06 Uhr): Prozentzahlen nur aus dem geprüften Modell, sonst „Nicht
 * ausreichend zuverlässig“; heute nur mit Kursen im Tagesverlauf; Kombination ohne erfundene Prozentzahl. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { assessEntry, priceBasis } from '../src/lib/bewertung.ts';
import { classOf, horizonText, horizonView, KAUFWARNUNG, overall, qualityText, scenarios, shownHorizons, todayText, UNRELIABLE, weightedTarget } from '../src/lib/prognose.ts';
import type { AnalystAction, ProbabilityData } from '../src/lib/types.ts';

const CLASSES = [
  { von: 0.4, bis: 0.5, p: 0.46, beob: 0.47, n: 900, mittel: -0.004, q25: -0.03, q75: 0.02 },
  { von: 0.5, bis: 0.6, p: 0.55, beob: 0.56, n: 1200, mittel: 0.006, q25: -0.02, q75: 0.03 },
];

function data(): ProbabilityData {
  const q = (ok: boolean) => ({ n: ok ? 5000 : 800, zuverlaessig: ok, grund: ok ? null : 'nur 800 Testfälle (mindestens 3000)', skill: ok ? 0.012 : 0.0, ece: 0.01, treffer: 0.54, klassen: CLASSES });
  return {
    version: 'wahrscheinlichkeit-1',
    regel: 'Regel',
    horizonte: [1, 5, 10, 20, 30],
    gezeigt: [1, 5, 10, 20, 30],
    grund_horizont: 10,
    testzeitraum: { von: 1, bis: 2, stichtag: 2 },
    faelle: 10000,
    letzter_tag: 2,
    merkmale: [],
    grenzen: { mindestens_testfaelle: 3000, mindestens_verbesserung: 0.001, hoechstens_kalibrierungsfehler: 0.03 },
    grundrate: { '1': 0.51, '5': 0.52, '10': 0.53, '20': 0.54, '30': 0.55 },
    qualitaet: { '1': q(false), '5': q(true), '10': q(true), '20': q(true), '30': q(false) },
    hinweise: [],
    steigt: { '1': [55, null], '5': [57, 48], '10': [58, null], '20': [59, 51], '30': [60, 50] },
    gruende: [['Veränderung 20 Tage +8,0 % – spricht für Anstieg'], []],
  } as ProbabilityData;
}

test('Prozentzahl nur bei zuverlässigem Horizont; sonst „Nicht ausreichend zuverlässig“ mit Grund', () => {
  const views = shownHorizons(data(), 0);
  assert.deepEqual(views.map((v) => v.p), [null, 0.57, 0.58, 0.59, null]);
  assert.match(horizonText(views[0]), new RegExp(`^nächster Handelstag: ${UNRELIABLE} \\(nur 800 Testfälle`));
  assert.match(horizonText(views[1]), /^5 Handelstage: steigt 57 %, fällt 43 %, Ø \+0,6 %, meist −2,0 % bis \+3,0 %$/);
  assert.equal(horizonView(data(), 1, 10).p, null, 'ohne Wert keine Zahl');
  assert.equal(horizonView(null, 0, 10).p, null);
  assert.match(qualityText(data().qualitaet['5']), /5\.000 Testfälle, Brier 1,2 % besser als die Grundrate, Kalibrierungsfehler 1,0 %/);
});

test('Klassen der Testfälle: richtige Klasse, Rand 1,0 gehört zur obersten', () => {
  assert.equal(classOf(CLASSES, 0.45)?.p, 0.46);
  assert.equal(classOf(CLASSES, 0.5)?.p, 0.55);
  assert.equal(classOf(CLASSES, 0.95), null);
  assert.equal(classOf([{ ...CLASSES[0], von: 0.9, bis: 1 }], 1)?.von, 0.9);
});

test('Heute: ohne Kurse im Tagesverlauf keine Aussage, mit Kurs nur der Stand – nie eine Prozentzahl für heute', () => {
  assert.match(todayText(null), /ohne sie keine Aussage/);
  const text = todayText(0.012);
  assert.match(text, /\+1,2 % zum Vortag/);
  assert.doesNotMatch(text, /steigt \d/);
});

test('Kaufwarnung: nie grün, auch bei Kaufsignal im Kaufbereich', () => {
  const basis = priceBasis({ close: 17.5, closeDay: 1, unit: 'USD' });
  const plan = { status: 'kaufsignal' as const, reason: 'alle Bedingungen erfüllt', entry: 17.79, stop: 16.9, target: 19.57, late: false };
  const open = { open: true, kind: 'offen', reason: null };
  assert.equal(assessEntry({ gate: open, issue: null, plan, basis }).light, 'guenstig');
  const warned = assessEntry({ gate: open, issue: null, plan, basis, warning: 'Insolvenz (06.11.2026)' });
  assert.equal(warned.light, 'kein');
  assert.equal(warned.reason, `${KAUFWARNUNG}: Insolvenz (06.11.2026).`);
});

test('Analysten: gewichteter Ø der jüngsten Ziele je Haus, Szenarien nur aus vorhandenen Zielen', () => {
  const today = 20400;
  const acts: AnalystAction[] = [
    { tag: today - 10, haus: 'Haus A', aktion: null, von: null, zu: null, ziel: 120, ziel_vorher: 110, ziel_aktion: null },
    { tag: today - 200, haus: 'Haus A', aktion: null, von: null, zu: null, ziel: 90, ziel_vorher: null, ziel_aktion: null },
    { tag: today - 100, haus: 'Haus B', aktion: null, von: null, zu: null, ziel: 100, ziel_vorher: null, ziel_aktion: null },
    { tag: today - 400, haus: 'Haus C', aktion: null, von: null, zu: null, ziel: 50, ziel_vorher: null, ziel_aktion: null },
  ];
  const w = weightedTarget(acts, today);
  assert.equal(w.count, 2, 'je Haus nur das jüngste Ziel, älter als 12 Monate zählt nicht');
  const wa = 0.5 ** (10 / 90);
  const wb = 0.5 ** (100 / 90);
  assert.ok(Math.abs((w.value ?? 0) - (wa * 120 + wb * 100) / (wa + wb)) < 1e-9);
  const rows = scenarios({ count: 8, mean: 105, median: 102, low: 80, high: 140, weighted: w.value, weightedCount: w.count }, 100);
  assert.deepEqual(rows.map((r) => [r.key, r.target]), [['pessimistisch', 80], ['basis', 102], ['optimistisch', 140]]);
  assert.ok(Math.abs((rows[0].change ?? 0) + 0.2) < 1e-12);
  assert.deepEqual(scenarios({ count: 0, mean: null, median: null, low: null, high: null, weighted: null, weightedCount: 0 }, 100), []);
});

test('Gesamtbild zählt Hinweise – keine neue Prozentzahl', () => {
  const o = overall({ entry: 'guenstig', kurz: 'gruen', lang: 'rot', p20: 0.6, base20: 0.54, news: 'gelb', risk: 'hoch', warning: null });
  assert.deepEqual(o.positive, ['Kaufzeitpunkt', 'kurzfristig', 'Wahrscheinlichkeit 20 Tage']);
  assert.deepEqual(o.negative, ['langfristig', 'Risiko']);
  assert.match(o.text, /^3 von 6 Hinweisen sprechen dafür/);
  assert.doesNotMatch(o.text, /\d+ %/);
  const warned = overall({ entry: 'kein', kurz: 'grau', lang: 'grau', p20: null, base20: null, news: 'rot', risk: 'hoch', warning: 'Insolvenz' });
  assert.ok(warned.text.startsWith(KAUFWARNUNG));
});
