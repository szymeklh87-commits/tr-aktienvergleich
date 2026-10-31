/* Musterbereiche in der App: Auswahl nach Zustand, getrennte Sortierung nach Score bzw. Rendite, Regeltext aus den Parametern
 * des Laufs (keine zweiten Standardwerte) – SYNTHETISCHE Daten. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { auswahl, nichtPruefbarSumme, regelText, type MusterModul, type MusterStand, type MusterTreffer } from '../src/lib/muster.ts';

function t(isin: string, zustand: string, score: number | null, rendite: number | null): MusterTreffer {
  return { isin, zustand, tag: '2026-10-30', schluss: 10, score, volumenfaktor: 1.2, reaktion: true, rendite_n_pct: rendite, ueberdehnt: false, wenig_umsatz: false, umsatz_usd: null, id: null };
}

const modul: MusterModul = {
  name: 'Vor-Ausbruch',
  geprueft: 5,
  zustaende: { bestaetigt: 1, kandidat: 2, abgelaufen: 1 },
  top: ['AA0000000001'],
  // Reihenfolge des Laufs: Zustand, Score, ISIN
  treffer: [t('AA0000000001', 'bestaetigt', 80, 2), t('AA0000000002', 'kandidat', 70, 9), t('AA0000000003', 'kandidat', 60, null), t('AA0000000004', 'abgelaufen', 50, 30)],
  nicht_pruefbar: { zu_kurz: ['AA0000000009'], datenalter: ['AA0000000008', 'AA0000000007'] },
};

test('Auswahl: aktive Zustände in der Reihenfolge des Laufs, eigener Zustand, Rendite als eigene Sortierung', () => {
  assert.deepEqual(auswahl(modul, 'A', 'aktiv', 'score').map((x) => x.isin), ['AA0000000001', 'AA0000000002', 'AA0000000003']);
  assert.deepEqual(auswahl(modul, 'A', 'abgelaufen', 'score').map((x) => x.isin), ['AA0000000004']);
  assert.deepEqual(auswahl(modul, 'A', 'aktiv', 'rendite').map((x) => x.isin), ['AA0000000002', 'AA0000000001', 'AA0000000003'], 'ohne Rendite ans Ende');
  assert.equal(nichtPruefbarSumme(modul), 3);
});

test('Regeltext kommt aus den Parametern des Laufs', () => {
  const stand = {
    parameter: {
      atr_sitzungen: 14, volumen_vergleich_sitzungen: 20, volumen_min_vergleich: 15, ueberdehnt_pct: 25, ueberdehnt_sitzungen: 20, wenig_umsatz_usd: 1_000_000,
      A: { basis_sitzungen: 20, max_bandbreite_pct: 12, max_bandbreite_atr: 6, max_drift_pct: 4, naehe_pct: 3, oberer_anteil: 0.75, bestaetigung_pct: 1, bestaetigung_volumen: 1.5, ablauf_sitzungen: 10 },
      B: { schwelle: 3, positive_reaktion: true },
      C: { basis_sitzungen: 40, max_bandbreite_pct: 15, max_bandbreite_atr: 8, max_drift_pct: 5, naehe_pct: 3, oberer_anteil: 0.75, bestaetigung_pct: 1, bestaetigung_volumen: 1.5, ablauf_sitzungen: 10 },
    },
  } as unknown as MusterStand;
  const a = regelText(stand, 'A').join(' ');
  assert.match(a, /die 20 abgeschlossenen Sitzungen vor dem Stichtag/);
  assert.match(a, /bis 12 % und bis 6 ATR\(14\)/);
  assert.match(a, /oberen 25 %-Teil/);
  assert.match(a, /abgelaufen/);
  assert.match(regelText(stand, 'C').join(' '), /zurück in der Basis/);
  const b = regelText(stand, 'B').join(' ');
  assert.match(b, /mindestens 3 × Ø der 20 vollständigen Sitzungen/);
  assert.match(b, /nicht der 5-\/15-Minuten-Faktor/);
});
