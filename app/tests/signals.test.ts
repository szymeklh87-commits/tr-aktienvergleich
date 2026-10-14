/* Signale und Potenzial (ab 1.6): Sortierung, Filter, Gründe und Sätze – ohne Browser. Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  consistencyCells,
  detailConsistency,
  gradeOf,
  parseListKind,
  probabilityText,
  rankSignals,
  ratingShares,
  reasonChips,
  signalCount,
  targetText,
  totalParts,
  totalProbabilityText,
  totalSentence,
  verdictSentence,
} from '../src/lib/signals.ts';
import type { SignalDetail, SignalsData } from '../src/lib/types.ts';

function data(): SignalsData {
  const n = 5;
  const col = <T,>(values: T[]) => values;
  return {
    schema: 'tr-signale/1',
    id: 'S1',
    snapshot_id: 'X',
    cutoff_day: 20739,
    kursstand: '2026-10-13',
    erstellt_utc: '2026-10-14T06:00:00Z',
    version: 'signale-v1',
    regeln: {
      kurz_gewichte: {},
      kurz_nachrichten_gewicht: 0.15,
      lang_gewichte: {},
      mindestumsatz_eur: 250000,
      namen: { volumen: 'Relatives Volumen', kursziel: 'Kursziel', rsi: 'RSI (14)', bewertung: 'Bewertung' },
      erklaerungen: {},
      ampel_kurz: '',
      ampel_lang: '',
      hinweis: '',
    },
    kalibrierung: {
      bereiche: [0, 50, 100],
      faelle: [10, 10],
      steigt_5: [0.4, 0.6],
      mittel_5: [0, 0.01],
      steigt_20: [0.4, 0.62],
      mittel_20: [0, 0.03],
      alle_steigt_5: 0.52,
      alle_mittel_5: 0.004,
      alle_steigt_20: 0.55,
      alle_mittel_20: 0.012,
      faelle_gesamt: 20,
      erster_tag: 1,
      last_day: 2,
    } as unknown as SignalsData['kalibrierung'],
    anzahl: { aktien: n, mit_kennzahlen: n, mit_kursziel: 4, beide_gruen: 1, kurz: { gruen: 2, gelb: 1, rot: 1, grau: 1 }, lang: { gruen: 2, gelb: 2, rot: 1, grau: 0 } },
    sektoren: ['Technology', 'Energy'],
    isin: ['A', 'B', 'C', 'D', 'E'],
    sektor: [0, 0, 1, 1, -1],
    kurz: col([80, 70, 30, 66, null]),
    kurz_ampel: col(['gruen', 'gelb', 'rot', 'gruen', 'grau'] as const).slice(),
    kurz_grund: [null, null, null, null, 'zu kurze Kurshistorie'],
    lang: col([75, 80, 20, 60, 50]),
    lang_ampel: col(['gruen', 'gruen', 'rot', 'gelb', 'gelb'] as const).slice(),
    lang_grund: [null, null, 'Kursziel unter dem aktuellen Kurs', null, null],
    potenzial: [0.3, 0.6, -0.1, 0.12, null],
    ziel: [130, 160, 90, 112, null],
    ziel_tief: [100, 120, 80, 100, null],
    ziel_hoch: [170, 200, 95, 130, null],
    analysten: [12, 2, 5, 8, 0],
    kaufen: [0.8, 1, 0.2, 0.5, null],
    handelbar: [true, true, true, false, true],
    kurs: [100, 100, 100, 100, 100],
    kurs_tag: [20739, 20739, 20739, 20739, 20739],
    punkte: {},
    merkmale: { rvol: [2.1, 1, 0.8, 1.6, null], up10: [0.8, 0.5, 0.2, 0.9, null], serie: [4, 0, -3, 1, 0], r20: [0.12, 0.03, -0.1, 0.05, null], r250: [0.4, 0.1, -0.3, 0.2, null], rsi: [64, 50, 35, 78, null] },
    steigt_5: [0.6, null, null, null, null],
    steigt_20: [0.62, null, null, null, null],
    listen: { beide: [], kurz: [], lang: [], potenzial: [] },
  } as SignalsData;
}

const base = { minAnalysts: 0, onlyGreen: false, liquidOnly: false, sector: null };
const norm = (text: string) => text.replace(/[\u00a0\u202f]/g, ' ');

function withTotal(): SignalsData {
  const d = data();
  d.gesamt = [72, 81, 20, 55, null];
  d.gesamt_stufe = ['stark', 'stark', 'schwach', 'mittel', 'ohne'];
  d.regeln.gesamt_stark_ab = 65;
  d.regeln.gesamt_mittel_ab = 50;
  d.regeln.konstanz_zeitraeume = [30, 60, 90];
  d.merkmale.steig_30 = [15, 10, 6, 12, null];
  d.merkmale.tage_30 = [21, 21, 21, 21, null];
  d.merkmale.r_30k = [0.08, 0.01, -0.06, 0.03, null];
  d.merkmale.steig_60 = [31, 22, 15, 24, null];
  d.merkmale.tage_60 = [42, 42, 42, 42, null];
  d.merkmale.r_60k = [0.15, 0.02, -0.1, 0.04, null];
  d.merkmale.steig_90 = [45, null, 25, 33, null];
  d.merkmale.tage_90 = [63, null, 63, 63, null];
  d.merkmale.r_90k = [0.22, null, -0.2, 0.05, null];
  d.gesamt_steigt_20 = [0.58, null, null, null, null];
  return d;
}

test('Gesamt: nach Gesamtwertung, „nur stark“ ab 65 Punkten; alte Stände nach dem Mittel aus kurz und lang', () => {
  assert.deepEqual(rankSignals(withTotal(), { kind: 'gesamt', ...base }), [1, 0, 3, 2]);
  assert.deepEqual(rankSignals(withTotal(), { kind: 'gesamt', ...base, onlyGreen: true }), [1, 0]);
  assert.deepEqual(rankSignals(withTotal(), { kind: 'gesamt', ...base, minAnalysts: 5 }), [0, 3, 2]);
  // Signal-Stand vor 1.7 (ohne Spalte „gesamt“): Mittel aus kurz und lang, „nur grün“ = beide Ampeln grün
  assert.deepEqual(rankSignals(data(), { kind: 'gesamt', ...base }), [0, 1, 3, 2]);
  assert.deepEqual(rankSignals(data(), { kind: 'gesamt', ...base, onlyGreen: true }), [0]);
  assert.equal(parseListKind('beide'), 'gesamt', 'alte Links');
  assert.equal(parseListKind(null), 'gesamt');
  assert.equal(parseListKind('kurz'), 'kurz');
  assert.equal(gradeOf(65), 'stark');
  assert.equal(gradeOf(64.9), 'mittel');
  assert.equal(gradeOf(49), 'schwach');
  assert.equal(gradeOf(null), 'ohne');
});

test('Steig-Konstanz je Zeile: Anstiegstage von Handelstagen, Ton nach Anteil und Kursrichtung', () => {
  const cells = consistencyCells(withTotal(), 0);
  assert.deepEqual(
    cells.map((c) => [c.tage, c.auf, c.von, c.ton]),
    [
      [30, 15, 21, 'pos'],
      [60, 31, 42, 'pos'],
      [90, 45, 63, 'pos'],
    ],
  );
  assert.deepEqual(consistencyCells(withTotal(), 1).map((c) => c.tage), [30, 60], 'fehlende 90 Tage entfallen');
  assert.ok(consistencyCells(withTotal(), 2).every((c) => c.ton === 'neg'), 'gefallen = negativ');
  assert.equal(consistencyCells(withTotal(), 3)[0].ton, 'neu', '12 von 21 = 57 %: neutral');
  assert.deepEqual(consistencyCells(data(), 0), [], 'alter Stand ohne Steig-Konstanz');
  assert.ok(reasonChips(withTotal(), 0, 'gesamt').map(norm).includes('Trefferquote 58 %'));
  assert.equal(norm(reasonChips(withTotal(), 0, 'gesamt')[0]), 'Kursziel +30 % (12 Anal.)');
});

test('Kurzfristig: nur handelbare Aktien, Ampel vor Punkten', () => {
  assert.deepEqual(rankSignals(data(), { kind: 'kurz', ...base }), [0, 1, 2]);
});

test('Langfristig und Kursziel: Analysten-Mindestzahl, Branche und Gruppe B', () => {
  assert.deepEqual(rankSignals(data(), { kind: 'lang', ...base }), [1, 0, 3, 4, 2]);
  assert.deepEqual(rankSignals(data(), { kind: 'potenzial', ...base, minAnalysts: 3 }), [3, 0, 2].sort((a, b) => [0.3, 0.6, -0.1, 0.12][b] - [0.3, 0.6, -0.1, 0.12][a]));
  assert.deepEqual(rankSignals(data(), { kind: 'potenzial', ...base, minAnalysts: 1 }), [1, 0, 3, 2]);
  assert.deepEqual(rankSignals(data(), { kind: 'lang', ...base, sector: 1 }), [3, 2]);
  assert.deepEqual(rankSignals(data(), { kind: 'lang', ...base, liquidOnly: true }, (isin) => isin === 'B'), [1]);
});

test('Gründe passen zur Liste und sind kurz', () => {
  const d = data();
  assert.deepEqual(reasonChips(d, 0, 'kurz').slice(0, 2).map(norm), ['Umsatz 2,1× üblich', '8 von 10 Tagen gestiegen']);
  assert.equal(norm(reasonChips(d, 0, 'lang')[0]), 'Kursziel +30 % (12 Anal.)');
  assert.ok(reasonChips(d, 3, 'kurz').map(norm).includes('RSI 78 – überkauft'));
  assert.ok(reasonChips(d, 0, 'kurz').length <= 4);
});

function detail(): SignalDetail {
  return {
    schema: 'tr-signal-detail/1',
    id: 'S1',
    isin: 'A',
    kursstand: '2026-10-13',
    kurs: 100,
    kurs_tag: 20739,
    einheit: 'EUR',
    kurz: 80,
    kurz_technik: 82,
    kurz_ampel: 'gruen',
    kurz_grund: null,
    lang: 40,
    lang_ampel: 'rot',
    lang_grund: 'Kursziel unter dem aktuellen Kurs',
    handelbar: true,
    komponenten: [
      { key: 'volumen', punkte: 75, text: '', ton: 1, horizont: 'kurz' },
      { key: 'rsi', punkte: 30, text: '', ton: -1, horizont: 'kurz' },
      { key: 'kursziel', punkte: 35, text: '', ton: -1, horizont: 'lang' },
      { key: 'bewertung', punkte: null, text: '', ton: 0, horizont: 'lang' },
    ],
    merkmale: {},
    potenzial: -0.05,
    ziel: 95,
    ziel_tief: 80,
    ziel_hoch: 110,
    ziel_quellen: [],
    wahrscheinlichkeit: { bereich: [80, 100.0001], faelle: 1234, steigt_5: 0.61, mittel_5: 0.008, steigt_20: 0.64, mittel_20: 0.025 },
    prognose: null,
    kennzahlen: null,
    bewertung_tc: null,
    nasdaq: null,
    nachrichten: [],
    community: null,
    abgerufen: {},
  };
}

test('Sätze zum Urteil nennen Zahl, starke und schwache Signale und den Grund', () => {
  const names = data().regeln.namen;
  assert.equal(verdictSentence(detail(), 'kurz', names), '1 von 2 Signalen positiv – stark: Relatives Volumen – schwach: RSI (14).');
  assert.equal(verdictSentence(detail(), 'lang', names), '0 von 1 Signalen positiv – schwach: Kursziel. Kursziel unter dem aktuellen Kurs.');
  assert.deepEqual(signalCount(detail().komponenten, 'lang'), { positive: 0, negative: 1, available: 1 });
});

test('Trefferquote und Kursziel als Satz', () => {
  const text = norm(probabilityText(detail(), data().kalibrierung)!);
  assert.match(text, /\(80–100 Punkte\)/);
  assert.match(text, /in 5 Handelstagen in 61 % der Fälle \(im Mittel \+0,8 %\)/);
  assert.match(text, /Zum Vergleich alle Aktien: 52 % bzw\. 55 %/);
  assert.match(text, /1\.234 Vergleichsfälle/);
  assert.match(norm(targetText(detail(), 'EUR')!), /erwartete Steigerung −5 %/);
});

test('Anteile Kaufen/Halten/Verkaufen', () => {
  assert.deepEqual(ratingShares({ stark_kaufen: 1, kaufen: 2, halten: 1, verkaufen: 0, stark_verkaufen: 0 }), { kaufen: 0.75, halten: 0.25, verkaufen: 0, total: 4 });
  assert.equal(ratingShares({ stark_kaufen: 0, kaufen: 0, halten: 0, verkaufen: 0, stark_verkaufen: 0 }), null);
});

test('Gesamtwertung in der Einzelansicht: Teile mit Beitrag, Satz und Trefferquote', () => {
  const d = detail();
  d.gesamt = 75.9;
  d.gesamt_stufe = 'stark';
  d.gesamt_teile = { konstanz: 85, kursziel: 76, kurzfristig: 70, qualitaet: 60 };
  d.konstanz = [
    { tage: 30, steigtage: 15, vergleiche: 21, rendite: 0.08, punkte: 100 },
    { tage: 60, steigtage: 31, vergleiche: 42, rendite: 0.15, punkte: 95 },
    { tage: 90, steigtage: null, vergleiche: null, rendite: null, punkte: null },
  ];
  d.potenzial = 0.5;
  d.ziel_quellen = [{ quelle: 'Yahoo Finance (Konsens)', ziel: 150, tief: 120, hoch: 200, anzahl: 12 }];
  d.wahrscheinlichkeit_gesamt = { bereich: [80, 100.0001], faelle: 5432, steigt_20: 0.58, mittel_20: 0.019, steigt_60: 0.61, mittel_60: 0.048 };
  const parts = totalParts(d, null);
  assert.deepEqual(
    parts.map((p) => [p.key, p.weight, p.points]),
    [
      ['konstanz', 0.35, 85],
      ['kursziel', 0.35, 76],
      ['kurzfristig', 0.15, 70],
      ['qualitaet', 0.15, 60],
    ],
  );
  assert.ok(Math.abs(parts.reduce((sum, p) => sum + (p.contribution ?? 0), 0) - 75.85) < 0.01);
  assert.equal(norm(totalSentence(d)!), 'Gestiegen an 15 von 21, 31 von 42 Handelstagen (30/60 Tage); Kursziel +50 % (12 Analysten).');
  assert.deepEqual(detailConsistency(d.konstanz).map((c) => c.tage), [30, 60]);
  const cal = { alle_steigt_20: 0.53, alle_steigt_60: 0.55 } as unknown as Parameters<typeof totalProbabilityText>[1];
  const text = norm(totalProbabilityText(d, cal)!);
  assert.match(text, /\(80–100 Punkte\)/);
  assert.match(text, /20 Handelstage später in 58 % der Fälle höher \(im Mittel \+1,9 %\)/);
  assert.match(text, /60 Handelstage später in 61 % \(\+4,8 %\)/);
  assert.match(text, /alle Aktien: 53 % bzw\. 55 %/);
  assert.match(text, /Kursziele lassen sich so nicht prüfen/);
  d.gesamt = null;
  assert.equal(totalSentence(d), null);
});
