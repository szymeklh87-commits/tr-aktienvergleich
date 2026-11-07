/* Einschätzung direkt am angezeigten Kurs (ab 1.24.0) – ohne Browser. Aufruf: npm test
 *
 * Simons Vorgaben vom 07.11.2026 (17:09 und 17:13 Uhr): Ampel neben jedem Kurs, bei jedem Kurs neu bewertet; ein
 * gefallener Kurs allein macht nie grün; über dem Einstiegslimit „Abwarten“ mit der Marke; verzögerte Kurse und
 * Schlusskurse sind als solche gekennzeichnet; steigende, fallende, gleichbleibende und veraltete Kurse geprüft. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  assessEntry,
  assessPosition,
  historyRows,
  historySentence,
  ownHistory,
  positionLines,
  priceBasis,
  riskOf,
  statsText,
  type PlanInput,
  type PriceBasis,
} from '../src/lib/bewertung.ts';
import type { LiveQuote } from '../src/lib/livekurse.ts';
import type { Backtest, SignalsData } from '../src/lib/types.ts';

const NOW = Date.parse('2026-11-09T15:00:00Z');
const OPEN = { open: true, kind: 'offen', reason: null };
const STALE = { open: false, kind: 'veraltet', reason: 'Der tägliche Lauf hat sich zu lange nicht erfolgreich gemeldet.' };
const DEMO = { open: false, kind: 'demo', reason: 'DEMO' };
// Beispiel aus Simons Auftrag: Schluss 17,52 USD, Einstiegslimit 17,79 USD, Stop 16,90 USD, Ziel 19,57 USD
const SIGNAL: PlanInput = { status: 'kaufsignal', reason: 'alle Bedingungen erfüllt', entry: 17.79, stop: 16.9, target: 19.57, late: false };

function quote(price: number, over: Partial<LiveQuote> = {}): LiveQuote {
  return {
    isin: 'US0000000001',
    symbol: 'ABC',
    price,
    unit: 'USD',
    quoteTime: NOW - 16 * 60_000,
    session: '2026-11-09',
    marketState: 'REGULAR',
    delayMin: 15,
    delaySource: 'yahoo_antwort',
    previousClose: 17.52,
    open: 17.5,
    high: 18.3,
    low: 17.4,
    volume: 1000,
    fetchedAt: NOW - 60_000,
    kennung: 'k',
    ...over,
  };
}

function basisAt(price: number, over: Partial<LiveQuote> = {}): PriceBasis {
  return priceBasis({ close: 17.52, closeDay: 20400, unit: 'USD', quote: quote(price, over), now: NOW });
}

test('Kursbasis: verzögerter aktueller Kurs, Börse zu, veralteter Abruf, Zwischenstand, Schlusskurs', () => {
  const delayed = basisAt(18.2);
  assert.equal(delayed.kind, 'verzoegert');
  assert.equal(delayed.price, 18.2);
  assert.match(delayed.note ?? '', /verzögerter Kursbasis \(15 Min\.\)/);
  const live = basisAt(18.2, { delayMin: 0, quoteTime: NOW - 60_000 });
  assert.equal(live.kind, 'aktuell');
  assert.equal(live.note, null);
  const closed = basisAt(18.2, { marketState: 'POST' });
  assert.equal(closed.kind, 'boerse_zu');
  assert.match(closed.note ?? '', /Börse geschlossen/);
  const stale = basisAt(18.2, { quoteTime: NOW - 3 * 3_600_000, fetchedAt: NOW - 3 * 3_600_000 });
  assert.equal(stale.kind, 'schluss', 'veralteter Abruf zählt nicht als aktueller Kurs');
  assert.equal(stale.price, 17.52);
  assert.match(stale.note ?? '', /Aktueller Einstieg nicht beurteilbar/);
  const other = basisAt(1820, { unit: 'USc' });
  assert.equal(other.kind, 'schluss', 'Kurs in anderer Einheit wird nicht verglichen');
  const interim = priceBasis({ close: 17.52, closeDay: 20400, unit: 'USD', provisional: { price: 17.6, timeIso: '2026-11-09T14:40:00Z' }, now: NOW });
  assert.equal(interim.kind, 'vorlaeufig');
  assert.match(interim.note ?? '', /verzögerter Kursbasis \(Zwischenstand\)/);
  const close = priceBasis({ close: 17.52, closeDay: 20400, unit: 'USD', now: NOW });
  assert.equal(close.kind, 'schluss');
  assert.equal(close.note, 'Einschätzung auf Schlusskursbasis');
});

test('Kaufsignal: gleichbleibender Kurs im Kaufbereich → Günstiger Einstieg mit Stop und Ziel', () => {
  const a = assessEntry({ gate: OPEN, issue: null, plan: SIGNAL, basis: priceBasis({ close: 17.52, closeDay: 20400, unit: 'USD', now: NOW }) });
  assert.equal(a.light, 'guenstig');
  assert.equal(a.label, 'Günstiger Einstieg');
  assert.match(a.reason, /bis zum Einstiegslimit 17,79/);
  assert.ok(a.toStop !== null && a.toStop < 0, 'möglicher Verlust bis zum Stop');
  assert.ok(a.toTarget !== null && a.toTarget > 0);
  assert.equal(a.basisNote, 'Einschätzung auf Schlusskursbasis');
});

test('Steigender Kurs über dem Einstiegslimit → Abwarten mit der Marke (18,20 USD gegen 17,79 USD)', () => {
  const a = assessEntry({ gate: OPEN, issue: null, plan: SIGNAL, basis: basisAt(18.2) });
  assert.equal(a.light, 'abwarten');
  assert.match(a.reason, /18,20 USD über dem Einstiegslimit 17,79 USD/);
  assert.match(a.short, /über Limit 17,79/);
  assert.ok(a.vsEntry !== null && a.vsEntry > 0);
  assert.match(a.basisNote ?? '', /verzögerter Kursbasis/);
});

test('Fallender Kurs: über dem Stop bleibt es günstig, am Stop kein Kaufsignal', () => {
  assert.equal(assessEntry({ gate: OPEN, issue: null, plan: SIGNAL, basis: basisAt(17.1) }).light, 'guenstig');
  const atStop = assessEntry({ gate: OPEN, issue: null, plan: SIGNAL, basis: basisAt(16.9) });
  assert.equal(atStop.light, 'kein');
  assert.match(atStop.reason, /Stop 16,90/);
});

test('Ein gefallener Kurs allein macht nie grün: „Beobachten“ bleibt gelb, „Kein Kauf“ bleibt rot', () => {
  const watch: PlanInput = { status: 'beobachten', reason: 'Einstieg zu spät – RSI: 78', entry: 17.79, stop: 16.9, target: 19.57, late: true };
  for (const price of [15, 16.95, 17.5]) {
    assert.equal(assessEntry({ gate: OPEN, issue: null, plan: watch, basis: basisAt(price) }).light, 'abwarten');
    assert.equal(assessEntry({ gate: OPEN, issue: null, plan: { ...watch, status: 'kein_kauf', reason: 'Trend fällt' }, basis: basisAt(price) }).light, 'kein');
  }
  assert.match(assessEntry({ gate: OPEN, issue: null, plan: watch, basis: basisAt(15) }).reason, /^Noch kein Kaufsignal: Einstieg zu spät – RSI: 78\.$/);
});

test('Veraltete Daten, nicht bestätigter Kurs, fehlender Plan → Nicht beurteilbar; Umsatz unter 10 Mio. USD → kein Kaufsignal', () => {
  const stale = assessEntry({ gate: STALE, issue: null, plan: SIGNAL, basis: basisAt(17.5) });
  assert.equal(stale.light, 'unklar');
  assert.match(stale.reason, /zu lange nicht erfolgreich/);
  assert.equal(assessEntry({ gate: null, issue: null, plan: SIGNAL, basis: basisAt(17.5) }).light, 'unklar');
  const venue = assessEntry({ gate: OPEN, issue: 'Kurs am zweiten Börsenplatz weicht ab – nicht bestätigt', plan: SIGNAL, basis: basisAt(17.5) });
  assert.equal(venue.light, 'unklar');
  const thin = assessEntry({ gate: OPEN, issue: 'Ø Tagesumsatz unter 10 Mio. USD oder nicht nachgewiesen – kein regulärer Kaufkandidat', plan: SIGNAL, basis: basisAt(17.5) });
  assert.equal(thin.light, 'kein');
  assert.equal(assessEntry({ gate: OPEN, issue: null, plan: null, basis: basisAt(17.5) }).light, 'unklar');
  const noPrice = priceBasis({ close: null, closeDay: null, unit: 'USD', now: NOW });
  assert.equal(assessEntry({ gate: OPEN, issue: null, plan: SIGNAL, basis: noPrice }).light, 'unklar');
});

test('DEMO: bewertet zur Ansicht, aber als DEMO gekennzeichnet', () => {
  const a = assessEntry({ gate: DEMO, issue: null, plan: SIGNAL, basis: basisAt(17.5) });
  assert.equal(a.light, 'guenstig');
  assert.equal(a.demo, true);
});

test('Eigene Position: Halten zwischen Stop und Ziel, Verkaufen am Stop und am Ziel', () => {
  const position = { kurs: 100, einheit: 'EUR', datum: '2026-10-01' };
  const at = (price: number) => priceBasis({ close: price, closeDay: 20400, unit: 'EUR', now: NOW });
  // ATR 3 % von 100 = 3 → Stop 94, Ziel 112
  const hold = assessPosition({ position, basis: at(103), atrPct: 0.03, close: 100, stopAtr: 2, targetR: 2 });
  assert.equal(hold.light, 'halten');
  assert.equal(hold.stop, 94);
  assert.equal(hold.target, 112);
  assert.match(hold.reason, /Gewinn bisher \+3,0/);
  assert.equal(assessPosition({ position, basis: at(93.5), atrPct: 0.03, close: 100, stopAtr: 2, targetR: 2 }).light, 'verkaufen');
  const target = assessPosition({ position, basis: at(112.5), atrPct: 0.03, close: 100, stopAtr: 2, targetR: 2 });
  assert.equal(target.light, 'verkaufen');
  assert.match(target.reason, /Kursziel/);
  assert.equal(assessPosition({ position: { ...position, einheit: 'USD' }, basis: at(103), atrPct: 0.03, close: 100, stopAtr: 2, targetR: 2 }).light, 'unklar');
  assert.equal(assessPosition({ position, basis: at(103), atrPct: null, close: 100, stopAtr: 2, targetR: 2 }).light, 'unklar');
});

const BT: Backtest = {
  version: 'rueckblick-1',
  regel: 'signalregel-2',
  zeitraum: { von: 19000, bis: 20400, stichtag: 20410 },
  mindestens_faelle: 30,
  mindestens_faelle_aktie: 10,
  horizonte: { tage: [1, 5, 10, 20], monate: [[1, 21], [3, 63], [6, 126], [12, 252]] },
  kosten: { position_eur: 1000, mit_kosten: true },
  status: {
    kaufsignal: {
      faelle: 80,
      ausgefuehrt: 60,
      halten: { '10': { n: 60, belegt: true, mittel: 0.012, treffer: 0.55 } },
      plan: { '1': { n: 60, belegt: true, mittel: 0.001, treffer: 0.5 }, '10': { n: 60, belegt: true, mittel: 0.0123, treffer: 0.5417 } },
    },
    beobachten: { faelle: 12, ausgefuehrt: 10, halten: { '10': { n: 10, belegt: false, mittel: 0.02, treffer: 0.6 } } },
    vergleich: { faelle: 500, ausgefuehrt: 480, halten: { '10': { n: 480, belegt: true, mittel: 0.004, treffer: 0.51 } } },
  },
  markt: { steigend: { n: 0, belegt: false }, fallend: { n: 0, belegt: false } },
  hinweise: [],
};

test('Rückblick: Kennzahlen nur mit genug Fällen, sonst ausdrücklich „zu wenige“', () => {
  assert.equal(historySentence(BT, 'kaufsignal'), 'Frühere Kaufsignale dieser Regel mit Stop und Ziel, nach 10 Handelstagen Ø +1,2 %, Trefferquote 54 % (60 Fälle), nach Kosten.');
  assert.match(historySentence(BT, 'beobachten') ?? '', /erst 10 Fälle – zu wenige für eine Aussage \(mindestens 30\)\.$/);
  assert.match(historySentence(BT, 'kein_kauf') ?? '', /^Alle Aktien mit Mindestumsatz \(Vergleich\)/);
  assert.equal(historySentence(null, 'kaufsignal'), null);
  const rows = historyRows(BT, 'kaufsignal');
  assert.deepEqual(rows?.plan.map((r) => r.key), ['1', '5', '10', '20'].filter((k) => k in BT.status.kaufsignal!.plan!));
  assert.equal(rows?.hold.length, 8, 'Haltedauern 1/5/10/20 Tage und 1/3/6/12 Monate');
  assert.equal(statsText(undefined, '5 Tagen', 30), 'nach 5 Tagen: keine Fälle');
});

function data(over: Partial<SignalsData> = {}): SignalsData {
  return {
    isin: ['A', 'B'],
    merkmale: { sma20: [10, null], sma50: [9, null], hoch20: [11, null], hoch250: [12, null] },
    rueckblick: BT,
    rueckblick_eigen: { tage: 10, n: [12, 3], mittel: [0.02, 0.05], treffer: [0.58, 0.67] },
    risiko: {
      version: 'risiko-1',
      regel: '',
      stufe: ['hoch', 'unbekannt'],
      punkte: [5, null],
      gruende: [['sehr hohe Kursschwankung (70 % pro Jahr)', 'Verlust (Nettomarge −12,0 %)', 'kleiner Börsenwert (210 Mio. €)', 'vierter'], []],
      vollstaendig: [true, false],
      anzahl: { niedrig: 0, mittel: 0, hoch: 1, unbekannt: 1 },
    },
    ...over,
  } as unknown as SignalsData;
}

test('Eigene frühere Kaufsignale, Risiko mit höchstens drei Gründen, Lage zu Linien und Hochs', () => {
  assert.match(ownHistory(data(), 0)?.text ?? '', /12 frühere Kaufsignale, nach 10 Handelstagen Ø \+2,0 %, Trefferquote 58 %/);
  assert.match(ownHistory(data(), 1)?.text ?? '', /nur 3 frühere Kaufsignale – zu wenige/);
  assert.equal(ownHistory(data({ rueckblick_eigen: undefined }), 0), null);
  const risk = riskOf(data(), 0);
  assert.equal(risk?.level, 'hoch');
  assert.equal(risk?.reasons.length, 3);
  assert.equal(riskOf(data(), 1)?.label, 'Risiko nicht beurteilbar');
  const lines = positionLines(data(), 0, 10.5, 'EUR');
  assert.equal(lines.length, 4);
  assert.match(lines[0], /^über der 20-Tage-Linie/);
  assert.deepEqual(positionLines(data(), 1, 10.5, 'EUR'), []);
});

test('Eigene Positionen: deutsche Zahlen, nur gültige Einträge, Sicherung enthält sie', async () => {
  const { parseAmount, sanitizePositions } = await import('../src/lib/positionen.ts');
  const { exportPersonalData, importPersonalData } = await import('../src/lib/storage.ts');
  assert.equal(parseAmount('17,79'), 17.79);
  assert.equal(parseAmount('1.234,5'), 1234.5);
  assert.equal(parseAmount(' 18.2 '), 18.2);
  assert.equal(parseAmount('0'), null);
  assert.equal(parseAmount('-3'), null);
  assert.equal(parseAmount('abc'), null);
  const clean = sanitizePositions({ US0378331005: { kurs: 180.5, einheit: 'USD', datum: '2026-10-01' }, kaputt: { kurs: 1 }, DE0007164600: { kurs: -1 }, DE0005140008: { kurs: 9, datum: 'gestern' } });
  assert.deepEqual(Object.keys(clean).sort(), ['DE0005140008', 'US0378331005']);
  assert.equal(clean.DE0005140008.datum, null);
  const text = exportPersonalData({} as never, ['US0378331005'], clean);
  const back = importPersonalData(text);
  assert.deepEqual(back.positionen, clean);
  assert.equal(importPersonalData(JSON.stringify({ format: 'tr-vergleich-persoenlich/1', watchlist: [] })).positionen, undefined, 'ältere Sicherung ohne Positionen');
});
