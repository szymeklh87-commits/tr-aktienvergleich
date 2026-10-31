/* Bericht je Spielgelddepot: Anzeige nicht definierter Kennzahlen, CSV-Export aller Ausführungen (Abschnitt 21) und
 * eigenständiger HTML-Bericht (Abschnitt 14) – SYNTHETISCHE Daten. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { PilotBericht, PilotDepot, PilotStand } from '../src/lib/pilot.ts';
import { ausfuehrungenCsv, berichtHtml, huerdeWert, KENNZAHL_ZEILEN, kennzahlWert, loseText, monatText } from '../src/lib/pilotbericht.ts';

const bericht: PilotBericht = {
  version: 'bericht-1',
  bewertungstage: 4,
  unvollstaendig: 0,
  zeitraum: { von: '2026-07-21', bis: '2026-07-24', kalendertage: 3, renditetage: 3 },
  kennzahlen: { rendite_pct: 1.5, cagr_pct: null, volatilitaet_pct: null, sharpe: null, sortino: null, max_rueckgang_pct: 0.4, unter_wasser_tage: 1, trades: 2, trades_unbekannt: 1, trefferquote_pct: 50, profitfaktor: 1.25, gewinn_mittel_eur: 12.5, verlust_mittel_eur: -10, kapitalbindung_pct: 80, kosten_eur: 4, kosten_pct_start: 0.04, ausfuehrungen: 4 },
  nicht_definiert: { cagr_pct: 'Zeitraum unter einem Jahr (3 Kalendertage) – eine Hochrechnung wäre irreführend', volatilitaet_pct: 'zu wenige Tagesrenditen (3 < 20)', sharpe: 'zu wenige Tagesrenditen (3 < 20)', sortino: 'zu wenige Tagesrenditen (3 < 20)' },
  zins: { quelle: 'Geldmarkt-ETF', rendite_pct: 0.01 },
  monate: [{ monat: '2026-07', rendite_pct: 1.5, tage: 3, angebrochen: true }],
  rueckgang: { tag: ['2026-07-21', '2026-07-22', '2026-07-23', '2026-07-24'], pct: [0, -0.4, 0, 0] },
  haelften: { grund: 'zu kurz für einen Hälftenvergleich (3 Tagesrenditen, mindestens 40)' },
  vergleiche: [{ depot: 'v-welt', name: 'Welt-ETF', von: '2026-07-21', bis: '2026-07-24', eigen_pct: 1.5, vergleich_pct: 1.0, abstand_pp: 0.5, max_rueckgang_vergleich_pct: 0.2 }],
  bootstrap: { grund: 'zu wenige Tagesrenditen (3 < 20)' },
  huerden: [{ id: 'trades', text: 'mindestens 50 abgeschlossene Trades im Vorwärtstest', wert: 2, erfuellt: null, grund: 'DEMO – synthetische Kurse' }],
  warnungen: ['Kurzer Zeitraum (4 Bewertungstage): die Kennzahlen schwanken stark.'],
  walk_forward: 'Walk-Forward nach Abschnitt 14 ist mit 4 Bewertungstagen nicht möglich.',
  annahmen: ['DEMO: synthetische Kurse – keine Aussage über echte Märkte.'],
  steuern: { satz_pct: 26.375, jahre: [{ jahr: 2026, aktien_gewinne_eur: 25, aktien_verluste_eur: -10, fonds_ergebnis_eur: 0, unbekannte_kosten: 1, pauschbetrag_genutzt_eur: 15, steuerpflichtig_eur: 0, steuer_eur: 0, verlustvortrag_aktien_eur: 0, verlustvortrag_allgemein_eur: 0 }], verkauf_am_ende: null, hinweise: ['Modellrechnung, keine Steuerabrechnung; Rechtsstand vor Nutzung prüfen.'] },
  reproduzierbar: { datenstand: 's-1', programm: 'aktienpilot-0.2.0', bericht: 'bericht-1', startwert: 42, regeln: ['r-test@1'] },
};

function depot(over: Partial<PilotDepot> = {}): PilotDepot {
  return {
    id: 'f-test',
    name: 'Test <b>&</b> Regel',
    art: 'forschung',
    modus: 'DEMO',
    test_id: 't',
    status: 'aktiv',
    start: '2026-07-21',
    angelegt_am: '2026-07-21T00:00:00Z',
    archiviert_am: null,
    historisch: false,
    synthetisch: true,
    startkapital_eur: 10000,
    strategien: [],
    wert: null,
    kennzahlen: { rendite_zeitgewichtet_pct: 1.5, gewinn_realisiert_eur: 0, gewinn_realisiert_unbekannt: 0, gewinn_offen_eur: 0, kosten_eur: 4, max_rueckgang_pct: 0.4, sitzungen: 4, kaeufe: 2, verkaeufe: 2 },
    beschreibung: '',
    aktiver_anteil: 1,
    kern: null,
    reserviert_eur: 0,
    verlust: { stufe: 'normal', rueckgang: 0, tagesstopp_bis: null, pause_bis_freigabe: false, grenzen: {} },
    pausiert: false,
    letzter_tag: '2026-07-24',
    verlauf: { tag: ['2026-07-21', '2026-07-22', '2026-07-23', '2026-07-24'], gesamt: [10000, 9960, 10100, 10150], kern: [0, 0, 0, 0], aktiv: [10000, 9960, 10100, 10150] },
    positionen: [],
    orders_offen: [],
    orders_zuletzt: [],
    journal: [],
    bericht,
    ausfuehrungen: [
      { datum: '2026-07-21', zeit: '2026-07-22T05:30:00Z', art: 'kauf', isin: 'ZZ0000000001', stueck: 10, kurs: 12.5, waehrung: 'USD', fx_eur: 0.9, fx_quelle: 'EZB', gebuehren_eur: 1, betrag_eur: -113.5, zuordnung: 'r-test', order: 'o-1', ergebnis_eur: null, lose: null },
      { datum: '2026-07-23', zeit: '2026-07-24T05:30:00Z', art: 'verkauf', isin: 'ZZ0000000001', stueck: 10, kurs: 14, waehrung: 'USD', fx_eur: null, fx_quelle: null, gebuehren_eur: 1, betrag_eur: 125, zuordnung: 'r-test', order: 'o-2', ergebnis_eur: 11.5, lose: [{ kauf: '2026-07-21', stueck: 6, kosten_eur: 68.1 }, { kauf: null, stueck: 4, kosten_eur: null }] },
    ],
    ...over,
  };
}

const stand = { id: '2026-07-24_abc', datentag: '2026-07-24', namen: { ZZ0000000001: '=HYPERLINK("x") AG' }, depots: [] } as unknown as PilotStand;

test('nicht definierte Kennzahlen zeigen den Grund statt 0', () => {
  const zeile = (key: string) => KENNZAHL_ZEILEN.find((k) => k.key === key)!;
  assert.deepEqual(kennzahlWert(bericht, zeile('cagr_pct')), { text: 'nicht definiert', grund: bericht.nicht_definiert!.cagr_pct });
  assert.equal(kennzahlWert(bericht, zeile('rendite_pct')).text, '+1,50\u00a0%');
  assert.equal(kennzahlWert(bericht, zeile('trades')).text, '2 (dazu 1 mit unbekannten Kosten)');
  assert.equal(kennzahlWert(bericht, zeile('profitfaktor')).text, '1,25');
});

test('CSV aller Ausführungen: FIFO-Lose, Kennzeichnung unbekannter Kosten und Umrechnungen, Schutz vor Formeln', () => {
  const csv = ausfuehrungenCsv(depot(), stand);
  assert.ok(csv.startsWith('﻿'));
  const lines = csv.trim().split('\r\n');
  assert.ok(lines.some((l) => l.startsWith('# Depot;')));
  const header = lines.find((l) => l.startsWith('Datum;'))!;
  assert.match(header, /Anschaffungslose \(FIFO\);Hinweis$/);
  const rows = lines.slice(lines.indexOf(header) + 1);
  assert.equal(rows.length, 2);
  assert.ok(rows[0].includes(';"\'=HYPERLINK(""x"") AG";'), 'Name als Text, nicht als Formel');
  assert.ok(rows[0].includes(';EZB;1,00;-113,50;'));
  assert.ok(rows[1].includes('2026-07-21: 6 Stück, 68,10 EUR | Anschaffungstag unbekannt: 4 Stück, Kosten unbekannt'));
  assert.ok(rows[1].endsWith(';Anschaffungskosten unbekannt, Umrechnung unbekannt'));
  assert.equal(loseText(null), '');
});

test('HTML-Bericht: eigenständig, ohne Skripte, Texte maskiert, alle Abschnitte', () => {
  const html = berichtHtml(depot(), { ...stand, depots: [depot({ id: 'v-welt', name: 'Welt-ETF', bericht: null })] } as PilotStand, new Date(Date.UTC(2026, 6, 25)));
  assert.ok(html.startsWith('<!doctype html>'));
  assert.ok(!/<script/i.test(html));
  assert.ok(html.includes('Test &lt;b&gt;&amp;&lt;/b&gt; Regel'));
  assert.ok(!html.includes('<b>&</b>'));
  for (const part of ['Kapitalkurve und Vergleich', 'Rückgang vom Höchststand', 'Kennzahlen', 'Vergleichsdepots', 'Monatsrenditen', 'Prüfhürden', 'Steuer-Modellrechnung', 'Annahmen und Einschränkungen', 'Reproduzierbarkeit']) {
    assert.ok(html.includes(part), part);
  }
  assert.ok(html.includes('nicht definiert – Zeitraum unter einem Jahr'));
  assert.ok(html.includes('<polyline'));
  assert.ok(html.includes('kein offizielles Produkt von Trade Republic'));
  const leer = berichtHtml(depot({ bericht: null }), stand);
  assert.ok(leer.includes('noch kein Bericht'));
});

test('Monat und Prüfhürden mit Einheit', () => {
  assert.equal(monatText('2026-09'), 'September 2026');
  assert.equal(huerdeWert({ id: 'benchmark', wert: 6.29 }), '+6,29\u00a0Prozentpunkte');
  assert.equal(huerdeWert({ id: 'benchmark', wert: -0.5 }), '\u22120,50\u00a0Prozentpunkte');
  assert.equal(huerdeWert({ id: 'rueckgang', wert: 4.63 }), '4,6\u00a0%');
  assert.equal(huerdeWert({ id: 'trades', wert: 8 }), '8');
  assert.equal(huerdeWert({ id: 'profitfaktor', wert: null }), '–');
});
