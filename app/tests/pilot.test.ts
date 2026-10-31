/* Autopilot – Spielgeld: Gruppierung, Vergleich mit dem Welt-ETF, Sortierung, Journal und Regeltexte – SYNTHETISCHE Daten. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  abstandPp,
  ausdruckText,
  bedingungAusPfad,
  benchmark,
  gruppieren,
  journalNachTag,
  kennzahlText,
  kernReferenz,
  regelZusammenfassung,
  sortiereDepots,
  type Katalog,
  type PilotDepot,
  type Regel,
} from '../src/lib/pilot.ts';

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
    aktiver_anteil: 1,
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

const KATALOG: Katalog = {
  schema: 'tr-kennzahlenkatalog/1',
  version: 'test',
  methode: 'test',
  bereiche: ['Lineal'],
  kennzahlen: [
    { id: 'rendite', name: 'Rendite', erklaerung: '', typ: 'zahl', einheit: '%', gruppe: 'Lineal', parameter: [], operatoren: ['>', 'zwischen'], rollen: ['filter'], quelle: '', backtest: 'ja', paper: true, rueckblickend: false, besser: 'hoch', vergleichsklasse: 'prozent', reihe: false, hinweis: '' },
    { id: 'ma', name: 'Gleitender Durchschnitt', erklaerung: '', typ: 'zahl', einheit: 'Kurs', gruppe: 'Kurs und Technik', parameter: [], operatoren: ['>'], rollen: ['filter'], quelle: '', backtest: 'ja', paper: true, rueckblickend: false, besser: null, vergleichsklasse: 'kurs', reihe: true, hinweis: '' },
    { id: 'kurs', name: 'Schlusskurs', erklaerung: '', typ: 'zahl', einheit: 'Kurs', gruppe: 'Kurs und Technik', parameter: [], operatoren: ['>', 'gekreuzt_aufwaerts'], rollen: ['filter'], quelle: '', backtest: 'ja', paper: true, rueckblickend: false, besser: null, vergleichsklasse: 'kurs', reihe: true, hinweis: '' },
  ],
};

const REGEL: Regel = {
  schema: 'tr-regel/1',
  id: 'r-test',
  version: 2,
  name: 'Test',
  kandidaten: [{ art: 'rangliste', gruppe: 'A', politik: 'native', gewichte: [0], fenster: { von: 1, bis: 30 }, platz_bis: 1, variante: 'heute' }],
  filter: { und: [{ kennzahl: { id: 'rendite', parameter: { fenster: 30 } }, op: '>', wert: 5 }, { kennzahl: { id: 'kurs', parameter: {} }, op: '>', vergleich: { id: 'ma', parameter: { sitzungen: 50 } } }] },
  sortierung: { score: [{ kennzahl: { id: 'rendite', parameter: { fenster: 30 } }, gewicht: 0.6, richtung: 'ab' }], normierung: 'perzentil' },
  auswahl: { anzahl: 5, max_je_branche: 2 },
  kapital: { art: 'gleich' },
  kauf: { ausloeser: 'termin' },
  verkauf: {
    herausfallen: { aktiv: true, puffer: 3 },
    gewinnmitnahme: { art: 'leiter', basis: 'nach_kosten', bezug: 'urspruenglich', stufen: [{ schwelle_pct: 30, anteil_pct: 25 }, { schwelle_pct: 100, anteil_pct: 50 }] },
    wiedereinstieg: { art: 'pause', pause_sitzungen: 5 },
  },
  stop: { initial: { art: 'atr', faktor: 2, sitzungen: 14 }, trailing: { art: 'prozent', wert: 15 } },
  zeitplan: { intervall: 'woechentlich', wochentag: 4 },
  profil: 'FOLGETAG-SCHLUSS',
};

test('Gruppen: Vorwärtstest und historische Simulation getrennt, Vergleichsdepots erkannt', () => {
  const ds = [
    depot('demo-pilot', 'pilot', 1),
    depot('demo-v-welt', 'vergleich', 0.5),
    depot('demo-v-kern', 'vergleich', 0.7),
    depot('demo-f-lineal', 'forschung', 3),
    depot('h-pilot-002', 'pilot', 2, { historisch: true }),
    depot('h-v-welt-002', 'vergleich', 1, { historisch: true }),
  ];
  const g = gruppieren(ds);
  assert.equal(g.length, 2);
  assert.equal(g[0].historisch, false);
  assert.equal(g[0].pilot?.id, 'demo-pilot');
  assert.equal(benchmark(g[0])?.id, 'demo-v-welt');
  assert.equal(kernReferenz(g[0])?.id, 'demo-v-kern');
  assert.equal(g[1].historisch, true);
  assert.equal(benchmark(g[1])?.id, 'h-v-welt-002');
  assert.equal(kernReferenz(g[1]), null);
});

test('Abstand zum Vergleich nur über denselben Zeitraum', () => {
  const a = depot('a', 'forschung', 4.5);
  const b = depot('b', 'vergleich', 1.25);
  assert.equal(abstandPp(a, b), 3.25);
  assert.equal(abstandPp(a, depot('c', 'vergleich', 1, { start: '2026-08-01' })), null, 'anderer Start');
  assert.equal(abstandPp(a, depot('d', 'vergleich', null)), null, 'fehlende Rendite');
  assert.equal(abstandPp(a, null), null);
});

test('Sortierung: Rendite absteigend, fehlende Werte zuletzt, Gleichstand nach Name', () => {
  const ds = [depot('x', 'forschung', null), depot('b', 'forschung', 2), depot('a', 'forschung', 2), depot('c', 'forschung', 5)];
  assert.deepEqual(sortiereDepots(ds, 'rendite').map((d) => d.id), ['c', 'a', 'b', 'x']);
  assert.deepEqual(sortiereDepots(ds, 'name').map((d) => d.id), ['a', 'b', 'c', 'x']);
});

test('Journal nach Tag: neueste zuerst, Reihenfolge innerhalb des Tages bleibt', () => {
  const j = [
    { tag: 1, datum: '2026-10-09', art: 'entscheidung', text: 'a', zuordnung: null },
    { tag: 2, datum: '2026-10-12', art: 'ausfuehrung', text: 'b', zuordnung: null },
    { tag: 2, datum: '2026-10-12', art: 'ausfuehrung', text: 'c', zuordnung: null },
  ];
  const days = journalNachTag(j);
  assert.deepEqual(days.map((d) => d.datum), ['2026-10-12', '2026-10-09']);
  assert.deepEqual(days[0].eintraege.map((e) => e.text), ['b', 'c']);
});

test('Regeltext: Kennzahlen mit Namen und Parametern, Gruppen, Vergleiche, Gewinnleiter, Stops', () => {
  assert.equal(kennzahlText({ id: 'rendite', parameter: { fenster: 30 } }, KATALOG), 'Rendite (30 Tage)');
  assert.equal(kennzahlText({ id: 'unbekannt', parameter: {} }, KATALOG), 'unbekannt');
  assert.equal(ausdruckText(REGEL.filter, KATALOG), 'Rendite (30 Tage) > 5 % UND Schlusskurs > Gleitender Durchschnitt (50 Sitzungen)');
  assert.equal(
    ausdruckText({ oder: [{ nicht: { kennzahl: { id: 'rendite', parameter: { fenster: 7 } }, op: 'zwischen', von: -2, bis: 2 } }, { kennzahl: { id: 'kurs', parameter: {} }, op: 'gekreuzt_aufwaerts', vergleich: { id: 'ma', parameter: { sitzungen: 20 } } }] }, KATALOG),
    'NICHT Rendite (7 Tage) zwischen −2 % und 2 % ODER Schlusskurs kreuzt von unten nach oben Gleitender Durchschnitt (20 Sitzungen)'.replace('−2', '-2'),
  );
  const lines = new Map(regelZusammenfassung(REGEL, KATALOG));
  assert.match(lines.get('Kandidaten')!, /^Platz 1 der Lineal-Rangliste 0\/100 \(Gruppe A\), 1–30 Tage, heute$/);
  assert.match(lines.get('Score')!, /0,6 × Rendite/);
  assert.match(lines.get('Auswahl')!, /bis zu 5 Aktien, höchstens 2 je Branche/);
  assert.match(lines.get('Gewinnmitnahme')!, /Gewinnleiter \(Gewinn nach Kosten, Anteile der ursprünglichen Menge\): \+30 % → 25 %, \+100 % → 50 %/);
  assert.match(lines.get('Wiedereinstieg')!, /nach 5 Sitzungen Pause/);
  assert.match(lines.get('Stop')!, /2 × ATR \(14 Sitzungen\); nachgezogen: 15 % unter dem Einstieg/);
  assert.match(lines.get('Zeitplan')!, /wöchentlich am Donnerstag/);
  for (const [, text] of lines) assert.doesNotMatch(text, /undefined|NaN/);
});

test('Bedingung aus dem Journal-Pfad: Teilbedingung der Regel lesbar', () => {
  assert.equal(bedingungAusPfad(REGEL, 'filter.und[1]', KATALOG), 'Schlusskurs > Gleitender Durchschnitt (50 Sitzungen)');
  assert.equal(bedingungAusPfad(REGEL, 'filter.und[7]', KATALOG), 'filter.und[7]', 'unbekannter Pfad bleibt sichtbar');
  assert.equal(bedingungAusPfad(null, 'filter', KATALOG), 'filter');
});
