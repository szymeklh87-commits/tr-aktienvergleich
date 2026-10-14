/* Signale und Potenzial (ab 1.6): Sortierung, Filter, Gründe und Sätze – ohne Browser. Aufruf: npm test */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  analystSummary,
  consistencyCells,
  dayTraderChecks,
  percentileOf,
  proContra,
  traderTally,
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

function richDetail(): SignalDetail {
  const d = detail();
  d.kurs = 100;
  d.kurs_tag = 20739;
  d.potenzial = 0.3;
  d.ziel = 130;
  d.ziel_tief = 110;
  d.ziel_hoch = 170;
  d.ziel_quellen = [
    { quelle: 'Yahoo Finance (Konsens)', ziel: 128, tief: 110, hoch: 170, anzahl: 12 },
    { quelle: 'Nasdaq (Konsens)', ziel: 132, tief: null, hoch: null, anzahl: 10 },
  ];
  d.konstanz = [
    { tage: 30, steigtage: 15, vergleiche: 21, rendite: 0.08, punkte: 100 },
    { tage: 60, steigtage: 19, vergleiche: 42, rendite: -0.02, punkte: 25 },
    { tage: 90, steigtage: 35, vergleiche: 63, rendite: 0.1, punkte: 62 },
  ];
  d.merkmale = { umsatz_eur: 3_200_000, rvol: 2.1, atr: 0.034, gap: 0.031, sma20: 95, sma50: 90, hoch20: 100, rsi: 78, r20: 0.12, up10: 0.7, serie: 3, nachrichten: { meldungen_3_tage: 2, positiv: 2, negativ: 0 } };
  d.kennzahlen = {
    analysten: { anzahl: 12, ziel_mittel: 128, ziel_median: 125, ziel_hoch: 170, ziel_tief: 110, kurs: 100, empfehlung_mittel: 1.8, empfehlung: 'buy', kaufen_anteil: 0.83, empfehlungen_anzahl: 12 },
    empfehlungen: [
      { monat: '0m', stark_kaufen: 4, kaufen: 6, halten: 2, verkaufen: 0, stark_verkaufen: 0 },
      { monat: '-3m', stark_kaufen: 2, kaufen: 5, halten: 5, verkaufen: 0, stark_verkaufen: 0 },
    ],
    urteile: [
      { tag: 20730, haus: 'A', aktion: 'hochgestuft', von: 'Hold', zu: 'Buy', ziel: 140, ziel_vorher: 120, ziel_aktion: 'angehoben' },
      { tag: 20700, haus: 'B', aktion: 'bestätigt', von: 'Buy', zu: 'Buy', ziel: 125, ziel_vorher: 130, ziel_aktion: 'gesenkt' },
      { tag: 20690, haus: 'C', aktion: 'bestätigt', von: 'Buy', zu: 'Buy', ziel: 150, ziel_vorher: 135, ziel_aktion: 'angehoben' },
    ],
    urteile_anzahl: 3,
    bewertung: null,
    wachstum: { gewinn_naechstes_jahr: 0.25, umsatz_naechstes_jahr: 0.12 },
    finanzen: null,
    risiko: { leerverkauf: 0.18 },
    termine: { zahlen: 20741 },
    branche: null,
    waehrung_bilanz: 'USD',
  } as unknown as SignalDetail['kennzahlen'];
  d.bewertung_tc = { bewertung: 'unterbewertet', abschlag: 0.12, bewertung_quelle: null, ausblick: {}, ausblick_quelle: null, research: null };
  d.community = { beitraege: 30, bullish: 16, bearish: 4, je_tag: 22.5, erster: null, letzter: null, beobachter: null };
  return d;
}

test('Was die Analysten denken: Empfehlungen mit Richtung, Kursziel mit Spanne, Quellen, Urteile, Bewertung, Prognose, Termin', () => {
  const text = analystSummary(richDetail(), 'USD').map(norm);
  assert.equal(text[0], '10 von 12 Analysten empfehlen Kaufen (83 %), 2 Halten, keiner Verkaufen – vor drei Monaten waren es 58 %: Die Analysten sind optimistischer geworden.');
  assert.match(text[1], /^Im Durchschnitt erwarten die 12 Analysten mit Kursziel in etwa 12 Monaten einen Kurs von 130,00 USD – 30 % über dem aktuellen Kurs; das vorsichtigste Ziel liegt bei 110,00 USD \(\+10 %\), das höchste bei 170,00 USD \(\+70 %\)\.$/);
  assert.equal(text[2], 'Die 2 Quellen (Yahoo Finance, Nasdaq) liegen zwischen +28 % und +32 %.');
  assert.match(text[3], /^Bei den letzten 3 Urteilen der Analystenhäuser \(seit .+\): 2 Kursziele angehoben und 1 gesenkt, 1 Hochstufung\.$/);
  assert.equal(text[4], 'Trading Central hält die Aktie für unterbewertet (12 % unter dem geschätzten fairen Wert).');
  assert.equal(text[5], 'Für das nächste Geschäftsjahr erwarten sie beim Gewinn je Aktie +25 % und beim Umsatz +12 %.');
  assert.match(text[6], /^Die nächsten Geschäftszahlen kommen voraussichtlich am /);
  const none = detail();
  none.potenzial = null;
  none.kennzahlen = null;
  assert.deepEqual(analystSummary(none, 'EUR').length, 1);
});

test('Dafür/Dagegen: Steig-Konstanz, Kursziel, Signale; überkaufter RSI und nahe Zahlen dagegen', () => {
  const d = richDetail();
  d.komponenten = [
    { key: 'volumen', punkte: 75, text: 'Umsatz 2,1× des 20-Tage-Durchschnitts', ton: 1, horizont: 'kurz' },
    { key: 'rsi', punkte: 60, text: 'RSI 78 – überkauft', ton: 1, horizont: 'kurz' },
    { key: 'kursziel', punkte: 70, text: '…', ton: 1, horizont: 'lang' },
    { key: 'wachstum', punkte: 30, text: 'Gewinn nächstes Jahr −8 %', ton: -1, horizont: 'lang' },
  ];
  const { pro, contra } = proContra(d, { volumen: 'Relatives Volumen', rsi: 'RSI (14)', wachstum: 'Wachstum & Finanzen' });
  assert.equal(norm(pro[0]), 'Oft gestiegen: an 15 von 21 Handelstagen (30 Tage)');
  assert.equal(norm(pro[1]), 'Kursziel +30 % über dem Kurs (12 Analysten)');
  assert.ok(pro.includes('Relatives Volumen: Umsatz 2,1× des 20-Tage-Durchschnitts'));
  assert.ok(!pro.some((p) => p.startsWith('RSI')), 'überkauft steht nie unter „dafür“');
  assert.ok(contra.some((c) => c.startsWith('RSI (14): 78 – überkauft')));
  assert.ok(contra.some((c) => norm(c).startsWith('Selten gestiegen oder gefallen: 60 Tage – 19 von 42 Handelstagen, Kurs −2 %')));
  assert.ok(contra.includes('Wachstum & Finanzen: Gewinn nächstes Jahr −8 %'));
  assert.ok(contra.some((c) => c.startsWith('Geschäftszahlen am')), 'Zahlen in 2 Tagen');
});

test('Daytrader-Check: Werte, Urteil je Punkt, relative Stärke und Zählung', () => {
  const d = richDetail();
  const data0 = data();
  data0.merkmale.r20 = Array.from({ length: 40 }, (_, i) => -0.1 + i * 0.005);
  const checks = dayTraderChecks(d, data0);
  const by = Object.fromEntries(checks.map((c) => [c.key, c]));
  assert.equal(norm(by.umsatz.value), 'Ø 3,2 Mio. € Umsatz am Tag');
  assert.equal(by.umsatz.ok, true);
  assert.equal(by.rvol.ok, true);
  assert.equal(by.atr.ok, true);
  assert.equal(by.gap.ok, true);
  assert.equal(by.trend.ok, true);
  assert.equal(by.hoch.value, 'neues 20-Tage-Hoch');
  assert.equal(by.rsi.value, '78 – überkauft');
  assert.equal(by.rsi.ok, null, '78: grenzwertig, neutral');
  assert.match(norm(by.staerke.value), /^\+12,0 % – besser als 100 % der Aktien$/);
  assert.equal(by.serie.value, '7 von 10 Tagen gestiegen, 3 in Folge');
  assert.equal(by.nachrichten.ok, true);
  assert.equal(by.zahlen.ok, false, 'Zahlen in 2 Tagen: Risiko');
  assert.equal(by.short.ok, null);
  assert.equal(norm(by.community.value), "23 Beiträge am Tag, 80 % bullish");
  assert.ok(checks.every((c) => c.why.length > 40), 'jede Zeile erklärt, warum');
  const tally = traderTally(checks);
  assert.equal(tally.rated, checks.filter((c) => c.ok !== null).length);
  assert.ok(tally.good >= 9);
  assert.equal(percentileOf([1, 2, 3], 2), null, 'zu wenige Vergleichswerte');
});
