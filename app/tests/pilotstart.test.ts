/* Robo-Startseite (Gesamtauftrag 31.10.2026, Abschnitt 16): Herleitung der Kacheln aus dem Spielgeld-Stand – SYNTHETISCHE Daten. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { gruppieren, type PilotDepot, type PilotStand } from '../src/lib/pilot.ts';
import { letzteAusfuehrung, roboKacheln, warnungen } from '../src/lib/pilotstart.ts';
import type { Status } from '../src/lib/types.ts';

function depot(id: string, art: PilotDepot['art'], rendite: number | null, over: Partial<PilotDepot> = {}): PilotDepot {
  return {
    id,
    name: id,
    art,
    modus: 'DEMO',
    test_id: 't',
    status: 'aktiv',
    start: '2026-07-01',
    angelegt_am: '2026-07-01T00:00:00Z',
    archiviert_am: null,
    historisch: false,
    synthetisch: true,
    startkapital_eur: 10000,
    strategien: [],
    wert: { datum: '2026-10-12', gesamt_eur: 10000, kern_eur: 0, aktiv_eur: 0, guthaben_eur: 10000, einzahlungen_eur: 10000, gebuehren_eur: 0, vollstaendig: true, fehlend: [], stufe: 'normal' },
    kennzahlen: { rendite_zeitgewichtet_pct: rendite, gewinn_realisiert_eur: 0, gewinn_realisiert_unbekannt: 0, gewinn_offen_eur: 0, kosten_eur: 1, max_rueckgang_pct: 2, sitzungen: 60, kaeufe: 1, verkaeufe: 0 },
    beschreibung: '',
    aktiver_anteil: 0.3,
    kern: null,
    reserviert_eur: 0,
    verlust: { stufe: 'normal', rueckgang: 0, tagesstopp_bis: null, pause_bis_freigabe: false, grenzen: {} },
    pausiert: false,
    letzter_tag: '2026-10-12',
    verlauf: { tag: [], gesamt: [], kern: [], aktiv: [] },
    positionen: [],
    orders_offen: [],
    orders_zuletzt: [],
    journal: [],
    ...over,
  };
}

const ausf = (datum: string, art: 'kauf' | 'verkauf', isin: string) => ({
  datum, zeit: '17:30', art, isin, stueck: 1, kurs: 1, waehrung: 'EUR', fx_eur: 1, fx_quelle: null, gebuehren_eur: 1, betrag_eur: 1, zuordnung: 'x', order: null, ergebnis_eur: null, lose: null,
});

function stand(depots: PilotDepot[], labor: PilotStand['labor'] = null): PilotStand {
  return { schema: 'tr-spielgeld/1', id: 's', erstellt_utc: '', datentag: '2026-10-12', snapshot_id: 'x', modus: 'DEMO', version: 'v', katalog_version: 'k', hinweis: '', ueberwachung: '',
    depots, chronik: [], regeln: {}, namen: { AA0000000001: 'Alpha AG', AA0000000002: 'Beta AG' }, labor } as PilotStand;
}

const STATUS = { last_successful_check_utc: '2026-10-12T19:00:00Z', last_price_session: '2026-10-12', last_run: { status: 'veroeffentlicht' } } as unknown as Status;

test('Kacheln: Kapital mit Gewinn, Rendite zum Welt-ETF, Positionen, beste Forschungsstrategie, letzte Ausführungen, Optimierung', () => {
  const pilot = depot('demo-pilot', 'pilot', 4.2, {
    wert: { datum: '2026-10-12', gesamt_eur: 10420, kern_eur: 7000, aktiv_eur: 2000, guthaben_eur: 1420, einzahlungen_eur: 10000, gebuehren_eur: 10, vollstaendig: true, fehlend: [], stufe: 'normal' },
    strategien: [{ zuordnung: 'r-s1', regel: 'r-s1@1', name: 'S1 Momentum-Rotation', anteil: 0.5 }, { zuordnung: 'r-s2', regel: 'r-s2@1', name: 'S2 Swing-Breakout', anteil: 0.5 }],
    positionen: [{ isin: 'AA0000000001', name: 'Alpha AG', zuordnung: 'r-s1', stueck: 1, einstand_eur: 1, kurs_eur: 1, wert_eur: 1, gewinn_eur: 0, gewinn_pct: 0, stop: null, eroeffnet: null, gm: {}, regel: null, branche: null },
      { isin: 'IE00B4L5Y983', name: 'Welt', zuordnung: 'kern', stueck: 1, einstand_eur: 1, kurs_eur: 1, wert_eur: 1, gewinn_eur: 0, gewinn_pct: 0, stop: null, eroeffnet: null, gm: {}, regel: null, branche: null }],
    ausfuehrungen: [ausf('2026-10-09', 'kauf', 'AA0000000001')],
  });
  const welt = depot('demo-v-welt', 'vergleich', 1.2);
  const a = depot('demo-f-a', 'forschung', 6.5, { name: 'Vorlage: Gleichmäßigkeit 100/0, 30 Tage', ausfuehrungen: [ausf('2026-10-10', 'kauf', 'AA0000000002'), ausf('2026-10-11', 'verkauf', 'AA0000000002')] });
  const b = depot('demo-f-b', 'forschung', -1.0);
  const labor = { erstellt_utc: '2026-10-13T06:00:00Z', zaehlung: { verworfen: 10, nicht_ausgewaehlt: 12, validierung_verfehlt: 1, validiert: 2, vorwaerts: 3 }, kennzahlen: { varianten: 28 } } as unknown as PilotStand['labor'];
  const s = stand([pilot, welt, a, b], labor);
  const g = gruppieren(s.depots)[0];
  const k = Object.fromEntries(roboKacheln(s, g, STATUS).map((x) => [x.id, x]));
  assert.deepEqual(Object.keys(k), ['kapital', 'rendite', 'positionen', 'strategie', 'beste', 'entscheidungen', 'naechste', 'kurse', 'warnungen', 'optimierung']);
  assert.match(k.kapital.zusatz, /^\+420\s€/);
  assert.equal(k.kapital.ton, 'plus');
  assert.match(k.rendite.zusatz, /\+3,0\s*pp zum Welt-ETF/);
  assert.equal(k.positionen.wert, '2');
  assert.match(k.positionen.zusatz, /1 aktiv, 1 Robo-Kern/);
  assert.equal(k.strategie.wert, 'S1 · S2');
  assert.equal(k.beste.wert, 'Gleichmäßigkeit 100/0, 30 Tage');
  assert.equal(k.beste.link, '#/pilot/depot/demo-f-a');
  assert.equal(k.entscheidungen.wert, 'Beta AG', 'neuester Kauf über alle Depots');
  assert.match(k.entscheidungen.zusatz, /Verkauf Beta AG 11\.10\.2026/);
  assert.equal(k.warnungen.wert, 'keine');
  assert.equal(k.optimierung.wert, '5 validiert');
  assert.match(k.optimierung.zusatz, /28 Varianten, 3 im Vorwärtstest/);
  assert.equal(k.optimierung.link, '#/pilot/labor');
});

test('Warnungen: einzeln pausierte Strategien (Abschnitt 17) werden gezählt, ohne die Pilot-Pause zu melden', () => {
  const pilot = depot('demo-pilot', 'pilot', 1);
  const a = depot('demo-f-a', 'forschung', 2, { pausiert: true });
  const b = depot('demo-f-b', 'forschung', 3, { pausiert: true });
  const c = depot('demo-f-c', 'forschung', 4);
  const g = gruppieren(stand([pilot, a, b, c]).depots)[0];
  assert.deepEqual(warnungen(g, STATUS), ['2 Strategien pausiert']);
  const g1 = gruppieren(stand([pilot, a, c]).depots)[0];
  assert.deepEqual(warnungen(g1, STATUS), ['1 Strategie pausiert']);
});

test('Warnungen: Pause, Verluststufe, unvollständige Bewertung, gescheiterter Lauf; ohne Labor ein klarer Hinweis', () => {
  const pilot = depot('demo-pilot', 'pilot', 0, {
    pausiert: true,
    verlust: { stufe: 'stufe2', rueckgang: 0.12, tagesstopp_bis: null, pause_bis_freigabe: false, grenzen: {} },
    wert: { datum: '2026-10-12', gesamt_eur: 9000, kern_eur: 0, aktiv_eur: 0, guthaben_eur: 9000, einzahlungen_eur: 10000, gebuehren_eur: 0, vollstaendig: false, fehlend: ['x'], stufe: 'normal' },
  });
  const s = stand([pilot]);
  const g = gruppieren(s.depots)[0];
  const status = { ...STATUS, last_run: { status: 'fehlgeschlagen' } } as unknown as Status;
  const w = warnungen(g, status);
  assert.equal(w.length, 4);
  assert.ok(w[0].startsWith('Neue Käufe pausiert'));
  const k = Object.fromEntries(roboKacheln(s, g, status).map((x) => [x.id, x]));
  assert.equal(k.warnungen.ton, 'warn');
  assert.equal(k.kapital.ton, 'minus');
  assert.equal(k.optimierung.wert, 'noch kein Lauf');
  assert.equal(k.beste.wert, '–');
  assert.equal(letzteAusfuehrung(s.depots, 'kauf'), null);
  assert.equal(k.entscheidungen.wert, 'noch keine Ausführung');
  assert.doesNotMatch(roboKacheln(stand([depot('demo-f-x', 'forschung', 1, { kennzahlen: { ...depot('x', 'forschung', 1).kennzahlen, max_rueckgang_pct: -0 } })]), gruppieren([depot('demo-f-x', 'forschung', 1, { kennzahlen: { ...depot('x', 'forschung', 1).kennzahlen, max_rueckgang_pct: -0 } })])[0], STATUS).find((x) => x.id === 'beste')!.zusatz, /-0/, 'nie „-0,0 %“');
});
