/* Strategielabor in der App (Gesamtauftrag 31.10.2026, Abschnitte 12–15, 17): Zuordnung der historischen Zahlen zu einem
 * Spielgelddepot – laufende Strategie oder Variante eines Labor-Vorwärtsdepots. SYNTHETISCHE Werte. */

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { historischImLabor, kennzahlenKurz, vorwaertsDepotId, type LaborErgebnis, type LaborKennzahlen } from '../src/lib/labor.ts';

const k = (rendite: number, rueckgang = 2, kaeufe = 3): LaborKennzahlen => ({
  rendite_pct: rendite,
  abstand_welt_pp: null,
  max_rueckgang_pct: rueckgang,
  rendite_je_rueckgang: rendite / Math.max(rueckgang, 1),
  gewinnquote_pct: null,
  kaeufe,
  verkaeufe: 0,
  kosten_eur: 3,
  profitfaktor: null,
});

function ergebnis(over: Partial<LaborErgebnis> = {}): LaborErgebnis {
  return {
    schema: 'tr-labor/1',
    id: 'lab-000000000001',
    version: 'labor-1',
    modus: 'DEMO',
    synthetisch: true,
    erstellt_utc: '2026-10-31T06:00:00Z',
    datenstand: 's',
    datentag: '2026-10-30',
    zeitraeume: [],
    vergleich: {},
    uebernahme: { modus: 'nur_vorschlagen', vorwaerts: ['r-lab-c-1-60'] },
    hinweise: [],
    kennzahlen: { varianten: 2, depots: 6, tage: 40, rechnungen: 40, sekunden: {} },
    varianten: [
      { id: 'r-lab-c-1-60', familie: 'C', familie_name: 'Gleichmäßig', name: 'Labor C: x', parameter: {}, fingerabdruck: 'a', status: 'vorwaerts', grund: '', entwicklung: k(4), validierung: k(2), test: k(1) },
      { id: 'r-lab-a-30', familie: 'A', familie_name: 'Platz 1', name: 'Labor A: y', parameter: {}, fingerabdruck: 'b', status: 'verworfen', grund: 'g', entwicklung: k(-1) },
    ],
    walk_forward: { faltungen: [], zusammenfassung: { faltungen: 0, mit_wahl: 0, mittel_rendite_pct: null, mittel_welt_pct: null, besser_als_welt: 0, positiv: 0, wechsel: 0 } },
    parameterwirkung: [],
    zaehlung: { verworfen: 1, nicht_ausgewaehlt: 0, validierung_verfehlt: 0, validiert: 0, vorwaerts: 1 },
    positiv_entwicklung: 1,
    ...over,
  };
}

test('historischImLabor: laufende Strategie über ihre Depotkennung', () => {
  const e = ergebnis({ laufende: [{ depot: 'demo-f-s2', name: 'Vorlage: S2', quelle: 'vorlage', fingerabdruck: 'x', entwicklung: k(5), validierung: k(-2), test: k(0.5) }] });
  const h = historischImLabor(e, 'demo-f-s2');
  assert.equal(h?.art, 'laufend');
  assert.equal(h?.validierung?.rendite_pct, -2);
  assert.equal(historischImLabor(e, 'demo-f-s3'), null, 'nicht mitgerechnet');
  assert.equal(historischImLabor(null, 'demo-f-s2'), null);
});

test('historischImLabor: Labor-Vorwärtsdepot findet seine Variante, auch nach einem Neustart mit Kennungszusatz', () => {
  const e = ergebnis();
  const id = vorwaertsDepotId(e, 'r-lab-c-1-60');
  assert.equal(id, 'demo-l-lab-c-1-60');
  assert.equal(historischImLabor(e, id)?.art, 'variante');
  assert.equal(historischImLabor(e, `${id}-a1b2c3`)?.test?.rendite_pct, 1);
  assert.equal(historischImLabor(e, `${id}-extra-lang`), null, 'nur der sechsstellige Zusatz eines neuen Tests');
  assert.equal(historischImLabor(e, 'demo-l-lab-a-30')?.validierung, undefined, 'verworfene Variante: nur Entwicklung');
});

test('kennzahlenKurz: Vorzeichen, Rückgang ohne „-0“, Käufe in Einzahl und Mehrzahl', () => {
  assert.match(kennzahlenKurz(k(3.24, 4.1, 5)), /^\+3,2\s?%, Rückgang 4,1\s?%, 5 Käufe$/);
  assert.match(kennzahlenKurz(k(-1, -0, 1)), /^−1,0\s?%, Rückgang 0,0\s?%, 1 Kauf$/, 'echtes Minuszeichen, kein „-0,0“');
  assert.equal(kennzahlenKurz(undefined), '–');
});
