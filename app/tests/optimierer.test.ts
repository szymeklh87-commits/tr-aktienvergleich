/* Depot-Empfehlungen in der App (Aufträge 18 und 19): reine Hilfen der Ansicht – Sortierung der Depottabelle, Anteile,
 * Formate, Standardvariante, bestätigte Merkmale und dieselben Grenzen der Depotparameter wie auf dem Server. SYNTHETISCHE Werte. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  anteile,
  bestaetigte,
  depotErwartung,
  einstellungenFehler,
  ic,
  pp,
  sortieren,
  spanne,
  standardVariante,
  variantenListe,
  type OptEinstellungen,
  type OptStand,
  type OptZeile,
} from '../src/lib/optimierer.ts';

const zeile = (isin: string, over: Partial<OptZeile> = {}): OptZeile => ({
  platz: 1,
  isin,
  name: `DEMO ${isin}`,
  branche: null,
  waehrung: 'EUR',
  eignung: 50,
  erwartet_pct: 1,
  kosten_pct: 0.8,
  positiv_pct: 55,
  q10_pct: -3,
  q50_pct: 1,
  q90_pct: 5,
  dezil: 6,
  umsatz_eur: 1e7,
  kurs: null,
  dafuer: [],
  dagegen: [],
  ...over,
});

const EINST: OptEinstellungen = {
  variante: 'ausgewogen',
  horizont: 'w12',
  anzahl: 10,
  kapital_eur: 10000,
  max_gewicht_pct: 20,
  max_branche_pct: 35,
  min_umsatz_eur: 2e6,
  reserve_pct: 0,
  umschichtung: 'woechentlich',
  mindestverbesserung_pp: 1,
  toleranz_pp: 3,
  halte_faktor: 2,
};

function stand(): OptStand {
  const v = (variante: 'ausgewogen' | 'kurz' | 'lang', verfuegbar: boolean) => ({
    variante,
    name: variante,
    erklaerung: '',
    horizont: variante === 'kurz' ? ('w2' as const) : variante === 'lang' ? ('w52' as const) : ('w12' as const),
    horizont_text: '',
    verfuegbar,
    positionen: verfuegbar ? [zeile('ZZ0000000001', { gewicht_pct: 60 }), zeile('ZZ0000000002', { gewicht_pct: 40 })] : [],
    kennzahlen: null,
    veraenderungen: [],
  });
  return {
    modell: {
      forschung: {
        faktoren: {
          zeilen: [
            { merkmal: 'a', horizont: 'w2', richtung: 1, bestaetigt: true, auffaellig: true, urteil: '', entwicklung: { ic: 0.05, t: 3, tage: 10, trefferquote_pct: 60, unabhaengig: 10 }, validierung: { ic: 0.04, t: 2, tage: 4, trefferquote_pct: 60, unabhaengig: 4 }, test: { ic: 0.03, t: 1, tage: 4, trefferquote_pct: 55, unabhaengig: 4 } },
            { merkmal: 'b', horizont: 'w2', richtung: -1, bestaetigt: true, auffaellig: true, urteil: '', entwicklung: { ic: -0.09, t: -4, tage: 10, trefferquote_pct: 30, unabhaengig: 10 }, validierung: { ic: -0.05, t: -2, tage: 4, trefferquote_pct: 40, unabhaengig: 4 }, test: { ic: -0.02, t: -1, tage: 4, trefferquote_pct: 45, unabhaengig: 4 } },
            { merkmal: 'c', horizont: 'w2', richtung: 1, bestaetigt: false, auffaellig: false, urteil: '', entwicklung: { ic: 0.2, t: 1, tage: 10, trefferquote_pct: 50, unabhaengig: 10 }, validierung: { ic: 0, t: 0, tage: 4, trefferquote_pct: 50, unabhaengig: 4 }, test: { ic: 0, t: 0, tage: 4, trefferquote_pct: 50, unabhaengig: 4 } },
          ],
          fdr_q: 0.1,
          validierung_t: 1,
        },
        redundanz: { rho: 0.8, paare: [] },
        horizonte: {},
        namen: {},
      },
    } as unknown as OptStand['modell'],
    heute: {
      datentag: '2026-10-30',
      tage: 1,
      varianten: {
        lang: v('lang', false),
        kurz: v('kurz', true),
        ausgewogen: v('ausgewogen', true),
        rangliste: { horizonte: {}, einstellungen: { ...EINST, variante: 'kurz' }, herkunft: 'app', aktien_geprueft: 10 },
      },
    },
    kontrolle: null,
  };
}

test('Depottabelle sortiert stabil, fehlende Werte zuletzt, Namen alphabetisch', () => {
  const z = [zeile('A', { gewicht_pct: 10, erwartet_pct: 2, name: 'Beta' }), zeile('B', { gewicht_pct: 30, erwartet_pct: null, name: 'alpha' }), zeile('C', { gewicht_pct: 30, erwartet_pct: 5, name: 'Gamma' })];
  assert.deepEqual(sortieren(z, 'gewicht', true).map((x) => x.isin), ['B', 'C', 'A'], 'gleich: ursprüngliche Reihenfolge');
  assert.deepEqual(sortieren(z, 'erwartet', true).map((x) => x.isin), ['C', 'A', 'B']);
  assert.deepEqual(sortieren(z, 'erwartet', false).map((x) => x.isin), ['A', 'C', 'B'], 'fehlende Erwartung bleibt hinten');
  assert.deepEqual(sortieren(z, 'name', false).map((x) => x.isin), ['B', 'A', 'C']);
});

test('Anteile: absteigend, kleine Reste zusammengefasst', () => {
  const a = anteile({ A: 5, B: 40, C: 20, D: 10, E: 10, F: 8, G: 7 }, 4);
  assert.deepEqual(
    a.map((x) => x.name),
    ['B', 'C', 'D', 'übrige (4)'],
  );
  assert.equal(a[3].pct, 30);
});

test('Formate: Rang-IC, Prozentpunkte, Spanne, Erwartung mit Unsicherheit', () => {
  assert.equal(ic(0.0456), '+0,046');
  assert.equal(ic(-0.2), '−0,200');
  assert.equal(ic(null), '–');
  assert.equal(pp(1.25).replace(/\s/g, ' '), '+1,3 pp');
  assert.equal(spanne({ q10_pct: -3.14, q90_pct: 6.4 }).replace(/\s/g, ' '), '−3,1 % bis +6,4 %');
  assert.equal(spanne({ q10_pct: null, q90_pct: 1 }), '–');
  const k = { erwartet_pct: 3, kosten_pct: 0.8, erwartet_nach_kosten_pct: 2.2, schwankung_pct: 4.5, verlustszenario_pct: -7, positionen: 10, effektive_anzahl: 8, mittlere_korrelation: 0.3, branchen: {}, waehrungen: {} };
  assert.equal(depotErwartung(k).replace(/\s/g, ' '), '+2,2 % ± 4,5 %');
});

test('Standardvariante aus den Einstellungen, Varianten in fester Reihenfolge, bestätigte Merkmale nach Stärke', () => {
  const o = stand();
  assert.equal(standardVariante(o), 'kurz');
  assert.deepEqual(
    variantenListe(o).map((v) => v.variante),
    ['ausgewogen', 'kurz', 'lang'],
  );
  assert.deepEqual(
    bestaetigte(o, 'w2').map((z) => z.merkmal),
    ['b', 'a'],
    'nur bestätigte, stärkster Zusammenhang zuerst (auch umgekehrte Richtung)',
  );
});

test('Depotparameter: dieselben Grenzen wie auf dem Server', () => {
  assert.equal(einstellungenFehler(EINST), null);
  assert.match(einstellungenFehler({ ...EINST, anzahl: 25 }) ?? '', /3 bis 20/);
  assert.match(einstellungenFehler({ ...EINST, anzahl: 4.5 }) ?? '', /3 bis 20/);
  assert.match(einstellungenFehler({ ...EINST, anzahl: 4, max_gewicht_pct: 20 }) ?? '', /zu klein/);
  assert.equal(einstellungenFehler({ ...EINST, anzahl: 4, max_gewicht_pct: 20, reserve_pct: 20 }), null, 'mit Reserve passt es');
  assert.match(einstellungenFehler({ ...EINST, max_branche_pct: 5 }) ?? '', /Branche/);
  assert.match(einstellungenFehler({ ...EINST, kapital_eur: 100 }) ?? '', /Spielgeldkapital/);
  assert.match(einstellungenFehler({ ...EINST, toleranz_pp: 30 }) ?? '', /Umschichtungsschutz/);
  assert.match(einstellungenFehler({ ...EINST, kapital_eur: Number.NaN }) ?? '', /Spielgeldkapital/, 'leeres Feld');
});
