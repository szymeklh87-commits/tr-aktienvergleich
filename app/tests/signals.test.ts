/* Signale und Potenzial (ab 1.6): Sortierung, Filter, Gründe und Sätze – ohne Browser. Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { probabilityText, rankSignals, ratingShares, reasonChips, signalCount, targetText, verdictSentence } from '../src/lib/signals.ts';
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

test('Beides stark: grün/grün zuerst, dann nach Mittel beider Punktzahlen', () => {
  assert.deepEqual(rankSignals(data(), { kind: 'beide', ...base }), [0, 1, 3, 2]);
  assert.deepEqual(rankSignals(data(), { kind: 'beide', ...base, onlyGreen: true }), [0]);
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
