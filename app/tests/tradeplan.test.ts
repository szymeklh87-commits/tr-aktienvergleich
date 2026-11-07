/* Kaufsignal nach Signalregel 1 in der App (ab 1.21.0): Datentor und Prüfungen je Aktie – ohne Browser. Aufruf: npm test
 *
 * Kern des Auftrags vom 07.11.2026: „Keine ungeprüften Kurse als aktuelle Kaufempfehlungen anzeigen.“ Jede Lage, in der
 * die Daten nicht aktuell oder nicht geprüft sind, muss das Tor schließen – dann gibt es kein Kaufsignal. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { candidates, crvText, isoDe, priceUnconfirmed, signalGate, stockIssue, strongest, venueDeviation, type SignalGate } from '../src/lib/tradeplan.ts';
import type { Instruments, Manifest, PlanStatus, SignalsData, Status } from '../src/lib/types.ts';

const NOW = Date.parse('2026-11-07T08:00:00Z');

function signals(over: Partial<SignalsData> = {}, plans: Array<[PlanStatus, number | null, number | null]> = []): SignalsData {
  const rows = plans.length
    ? plans
    : ([
        ['kaufsignal', 100.5, 96.5],
        ['beobachten', 50.2, 47.1],
        ['kaufsignal', 20.4, 19.1],
        ['kein_kauf', null, null],
      ] as Array<[PlanStatus, number | null, number | null]>);
  return {
    snapshot_id: 'S-06',
    kursstand: '2026-11-06',
    isin: rows.map((_, k) => `ZZ000000000${k}`),
    gesamt: rows.map((_, k) => 90 - k),
    listen: { beide: [], kurz: [], lang: [], potenzial: [], handel: rows.map((_, k) => k).filter((k) => rows[k][0] !== 'kein_kauf') },
    handel: {
      regeln: { version: 'signalregel-2', beschreibung: 'Regel' } as never,
      status: rows.map((r) => r[0]),
      grund: rows.map((r) => (r[0] === 'kaufsignal' ? 'alle Bedingungen erfüllt' : r[0] === 'beobachten' ? 'Einstieg zu spät (RSI)' : 'Trend')),
      einstieg: rows.map((r) => r[1]),
      stop: rows.map((r) => r[2]),
      ziel: rows.map((r) => (r[1] === null || r[2] === null ? null : r[1] + 2 * (r[1] - r[2]))),
      ziel_basis: rows.map((r) => (r[1] === null ? null : '2R')),
      crv: rows.map((r) => (r[1] === null ? null : 2)),
      zu_spaet: rows.map((r) => r[0] === 'beobachten'),
      anzahl: { kaufsignal: 2, beobachten: 1, kein_kauf: 1 },
    },
    ...over,
  } as unknown as SignalsData;
}

function status(over: Partial<Status> = {}): Status {
  return {
    schema: 'tr-status/1',
    latest_snapshot_id: 'S-06',
    latest_official_snapshot_id: 'S-06',
    last_successful_check_utc: '2026-11-07T05:30:00Z',
    heartbeat_max_age_hours: 30,
    naechster_kursstand: { datum: '2026-11-09', ab_utc: '2026-11-09T22:00:00Z', boersen: ['XNYS'] },
    offiziell: {
      snapshot_id: 'S-06',
      kursstand: '2026-11-06',
      letzter_lauf: { run_id: 'r1', trigger: 'zeitplan', status: 'veroeffentlicht' },
      letzte_erfolgreiche_pruefung_utc: '2026-11-07T05:30:00Z',
      letzter_fehlschlag: null,
      fehlschlaege_seit_erfolg: 0,
    },
    ...over,
  } as unknown as Status;
}

function instruments(n = 4, over: Partial<Instruments> = {}): Instruments {
  return {
    count: n,
    isin: Array.from({ length: n }, (_, k) => `ZZ000000000${k}`),
    level_status: Array(n).fill(0),
    warnings: Array(n).fill(0),
    last_close: Array(n).fill(null),
    last_close_day: Array(n).fill(null),
    venue: null,
    ...over,
  } as unknown as Instruments;
}

const index = (n = 4) => new Map(Array.from({ length: n }, (_, k) => [`ZZ000000000${k}`, k] as [string, number]));
const OPEN: SignalGate = { open: true, kind: 'offen', reason: null, session: '2026-11-06' };

test('Tor offen nur mit echten, geprüften, aktuellen Daten', () => {
  const gate = signalGate({ status: status(), manifest: null, signals: signals(), isDemo: false, now: NOW });
  assert.deepEqual(gate, { open: true, kind: 'offen', reason: null, session: '2026-11-06' });
});

test('Tor zu: Signalregel fehlt, DEMO, ungeprüfter Zwischenstand', () => {
  const none = signalGate({ status: status(), manifest: null, signals: signals({ handel: undefined }), isDemo: false, now: NOW });
  assert.equal(none.kind, 'fehlt');
  const demo = signalGate({ status: status(), manifest: null, signals: signals(), isDemo: true, now: NOW });
  assert.equal(demo.kind, 'demo');
  assert.match(demo.reason ?? '', /DEMO – synthetische Testdaten/);
  const interim = { art: 'zwischenstand', zwischenstand: { basis_geprueft: false } } as unknown as Manifest;
  const unchecked = signalGate({ status: status(), manifest: interim, signals: signals(), isDemo: false, now: NOW });
  assert.equal(unchecked.kind, 'ungeprueft');
  assert.equal(unchecked.open, false);
  // geprüfte Grundlage: Zwischenstand allein schließt das Tor nicht
  const checked = { art: 'zwischenstand', zwischenstand: { basis_geprueft: true } } as unknown as Manifest;
  assert.equal(signalGate({ status: status(), manifest: checked, signals: signals(), isDemo: false, now: NOW }).open, true);
});

test('Tor zu: Signal-Stand nach älterer Regel (ohne 10 Mio. USD) gilt nie als bestätigt (ab 1.24)', () => {
  const old = signals();
  (old.handel!.regeln as { version: string }).version = 'signalregel-1';
  const gate = signalGate({ status: status(), manifest: null, signals: old, isDemo: false, now: NOW });
  assert.equal(gate.kind, 'alte_regel');
  assert.equal(gate.open, false);
  assert.match(gate.reason ?? '', /10 Mio\. USD/);
  const list = candidates(old, { gate, instruments: instruments(), index: index() });
  assert.ok(list.every((c) => c.shown !== 'kaufsignal'), 'kein Kaufsignal aus einer alten Regel');
  assert.equal(strongest(list, gate), null);
});

test('Abweichung am zweiten Börsenplatz so lesen, wie der Server sie liefert (ab 1.24): Endkurs oder ein Zeitraum auffällig', () => {
  const venue = { idx: [0, 1, 2], status: ['geprueft', 'geprueft', 'geprueft'], level_flag: [true, false, false], auffaellig: [true, true, false] } as unknown as Instruments['venue'];
  const data = instruments(4, { venue });
  assert.equal(venueDeviation(data, 0), 'Schlusskurs am zweiten Börsenplatz weicht ab');
  assert.equal(venueDeviation(data, 1), 'Kurs am zweiten Börsenplatz weicht ab');
  assert.equal(venueDeviation(data, 2), null);
  assert.equal(venueDeviation(data, 3), null, 'nicht geprüft ist keine Abweichung');
  assert.equal(stockIssue(data, 1), 'Kurs am zweiten Börsenplatz weicht ab – nicht bestätigt');
  assert.equal(priceUnconfirmed(data, 0), 'Schlusskurs am zweiten Börsenplatz weicht ab');
  // Datenstand bis 1.23 ohne „auffaellig“: der auffällige Endkurs genügt
  const legacy = { idx: [0, 1], status: ['geprueft', 'geprueft'], level_flag: [false, true] } as unknown as Instruments['venue'];
  assert.equal(stockIssue(instruments(4, { venue: legacy }), 0), null);
  assert.match(stockIssue(instruments(4, { venue: legacy }), 1) ?? '', /nicht bestätigt/);
  const list = candidates(signals(), { gate: OPEN, instruments: data, index: index() });
  assert.equal(list.find((c) => c.k === 0)?.shown, 'kein_kauf', 'kein Kaufsignal bei ungeklärter Abweichung');
});

test('Tor zu: Signale nicht auf dem neuesten Stand mit Schlusskursen', () => {
  const newer = status({ offiziell: { ...status().offiziell!, snapshot_id: 'S-09' } } as Partial<Status>);
  const gate = signalGate({ status: newer, manifest: null, signals: signals(), isDemo: false, now: NOW });
  assert.equal(gate.kind, 'veraltet');
  assert.match(gate.reason ?? '', /06\.11\.2026/);
  assert.doesNotMatch(gate.reason ?? '', /[Oo]ffiziell/, 'Texte ohne „offiziell“ (seit 1.12.1 „Stand mit Schlusskursen“)');
});

test('Tor zu: neue Schlusskurse fällig, tägliche Aktualisierung gescheitert oder zu lange still', () => {
  const due = signalGate({ status: status(), manifest: null, signals: signals(), isDemo: false, now: Date.parse('2026-11-09T22:00:00Z') });
  assert.equal(due.kind, 'veraltet');
  assert.match(due.reason ?? '', /09\.11\.2026/);
  const failedStatus = status({
    offiziell: { ...status().offiziell!, letzter_fehlschlag: { run_id: 'r2', trigger: 'zeitplan', status: 'fehlgeschlagen' } },
  } as Partial<Status>);
  assert.equal(signalGate({ status: failedStatus, manifest: null, signals: signals(), isDemo: false, now: NOW }).kind, 'veraltet');
  const quiet = signalGate({ status: status(), manifest: null, signals: signals(), isDemo: false, now: Date.parse('2026-11-08T12:00:00Z') });
  assert.equal(quiet.kind, 'veraltet', '30 Stunden ohne erfolgreiche Prüfung');
});

test('Kandidaten in der Reihenfolge des Servers, Kaufsignale zuerst; bei offenem Tor bleibt das Kaufsignal', () => {
  const list = candidates(signals(), { gate: OPEN, instruments: instruments(), index: index() });
  assert.deepEqual(
    list.map((c) => [c.k, c.shown]),
    [
      [0, 'kaufsignal'],
      [2, 'kaufsignal'],
      [1, 'beobachten'],
    ],
  );
  assert.equal(strongest(list, OPEN)?.k, 0);
  assert.equal(list[0].entry, 100.5);
  assert.equal(list[0].stop, 96.5);
  assert.equal(list[0].target, 108.5);
  assert.equal(candidates(signals(), { gate: OPEN, instruments: instruments(), index: index(), limit: 1 }).length, 1);
});

test('Geschlossenes Tor: kein Kaufsignal (Plan bleibt sichtbar); DEMO bleibt gekennzeichnetes Beispiel', () => {
  const stale: SignalGate = { open: false, kind: 'veraltet', reason: 'Der tägliche Lauf ist zuletzt gescheitert', session: '2026-11-06' };
  const list = candidates(signals(), { gate: stale, instruments: instruments(), index: index() });
  assert.ok(list.every((c) => c.shown !== 'kaufsignal'));
  const first = list.find((c) => c.k === 0)!;
  assert.equal(first.shown, 'kein_kauf');
  assert.equal(first.reason, stale.reason);
  assert.equal(first.entry, 100.5, 'Plan zur Ansicht');
  assert.equal(strongest(list, stale), null);
  const demo: SignalGate = { open: false, kind: 'demo', reason: 'DEMO', session: '2026-11-06' };
  const demoList = candidates(signals(), { gate: demo, instruments: instruments(), index: index() });
  assert.equal(demoList.find((c) => c.k === 0)?.shown, 'kaufsignal', 'als DEMO-Beispiel');
  assert.equal(strongest(demoList, demo), null, 'aber nie das Kaufsignal der Startseite');
});

test('Prüfungen je Aktie: ohne Schlusskurs, mit Warnhinweis, Abweichung am zweiten Börsenplatz – kein Kauf', () => {
  assert.equal(stockIssue(instruments(), -1), 'Aktie im angezeigten Datenstand nicht gefunden');
  assert.equal(stockIssue(instruments(4, { level_status: [3, 0, 0, 0] }), 0), 'Kein geprüfter Schlusskurs am Stichtag');
  assert.equal(stockIssue(instruments(4, { warnings: [1 << 13, 0, 0, 0] }), 0), 'Starke Kursbewegung an einem Tag ohne belegten Umsatz');
  assert.equal(stockIssue(instruments(4, { warnings: [1 << 18, 0, 0, 0] }), 0), 'Kurskorrektur des Anbieters ausstehend');
  assert.equal(stockIssue(instruments(4, { warnings: [1 << 2, 0, 0, 0] }), 0), null, 'andere Hinweise blockieren nicht');
  const venue = { idx: [0, 2], status: ['abweichung', 'gleich'] } as unknown as Instruments['venue'];
  assert.equal(stockIssue(instruments(4, { venue }), 0), 'Kurs am zweiten Börsenplatz weicht ab – nicht bestätigt');
  assert.equal(stockIssue(instruments(4, { venue }), 2), null);
  const list = candidates(signals(), { gate: OPEN, instruments: instruments(4, { venue, warnings: [0, 0, 1 << 18, 0] }), index: index() });
  assert.deepEqual(
    list.map((c) => [c.k, c.shown]),
    [
      [1, 'beobachten'],
      [0, 'kein_kauf'],
      [2, 'kein_kauf'],
    ],
  );
  assert.equal(strongest(list, OPEN), null, 'beide Kaufsignale fallen weg – KEIN KAUF');
});

test('Aktueller Kurs aus dem Zwischenstand: über dem Limit zu spät, am Stop hinfällig', () => {
  const live = new Map([
    [0, 101.0],
    [2, 19.0],
  ]);
  const list = candidates(signals(), { gate: OPEN, instruments: instruments(), index: index(), live });
  const late = list.find((c) => c.k === 0)!;
  assert.equal(late.shown, 'beobachten');
  assert.match(late.reason, /Einstieg zu spät/);
  assert.equal(late.late, true);
  const below = list.find((c) => c.k === 2)!;
  assert.equal(below.shown, 'kein_kauf');
  assert.match(below.reason, /am oder unter dem Stop/);
  const fine = candidates(signals(), { gate: OPEN, instruments: instruments(), index: index(), live: new Map([[0, 100.4]]) });
  assert.equal(fine.find((c) => c.k === 0)?.shown, 'kaufsignal', 'unter dem Limit: Kaufsignal bleibt');
});

test('Anzeige: CRV und Datum', () => {
  assert.equal(crvText(2), '2,0 : 1');
  assert.equal(crvText(1.12), '1,1 : 1');
  assert.equal(crvText(null), '–');
  assert.equal(crvText(Number.NaN), '–');
  assert.equal(isoDe('2026-11-06'), '06.11.2026');
  assert.equal(isoDe(null), '–');
});

test('Ranglisten (ab 1.22, F03): „Kurs nicht bestätigt“ bei Hinweis 13 oder 18 oder Abweichung am zweiten Börsenplatz', () => {
  const venue = { idx: [1], status: ['abweichung'] } as unknown as Instruments['venue'];
  const data = instruments(4, { venue, warnings: [1 << 13, 0, 1 << 18, 1 << 2], level_status: [0, 0, 0, 3] });
  assert.equal(priceUnconfirmed(data, 0), 'Starke Kursbewegung an einem Tag ohne belegten Umsatz');
  assert.equal(priceUnconfirmed(data, 1), 'Kurs am zweiten Börsenplatz weicht ab');
  assert.equal(priceUnconfirmed(data, 2), 'Kurskorrektur des Anbieters ausstehend');
  assert.equal(priceUnconfirmed(data, 3), null, 'fehlender Schlusskurs ist eine eigene Kennzeichnung, kein „nicht bestätigt“');
  assert.equal(priceUnconfirmed(null, 0), null);
  assert.equal(priceUnconfirmed(data, -1), null);
});

test('Kaufwarnung aus Nachrichten (ab 1.25): kein Kaufsignal, Grund genannt', () => {
  const data = signals({ ereignisse: { version: 'ereignisse-1', warnung: ['Insolvenz (06.11.2026)', null, null, null], ampel: ['rot', 'grau', 'grau', 'grau'], anzahl: { kaufwarnungen: 1, mit_ereignissen: 1 }, regel: '' } } as Partial<SignalsData>);
  const list = candidates(data, { gate: OPEN, instruments: instruments(), index: index() });
  const warned = list.find((c) => c.k === 0)!;
  assert.equal(warned.shown, 'kein_kauf');
  assert.equal(warned.reason, 'Hohes Unternehmensrisiko – Kaufwarnung: Insolvenz (06.11.2026)');
  assert.equal(list.find((c) => c.k === 2)?.shown, 'kaufsignal', 'andere Aktien unberührt');
  assert.equal(strongest(list, OPEN)?.k, 2);
});
