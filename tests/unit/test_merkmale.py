"""Merkmale des Depot-Optimierers kommen aus dem zentralen Katalog (Auftrag 19, Abschnitte 2, 3 und 11): jede Kennzahl ist
verwendet oder mit Grund ausgeschlossen, neue Kennzahlen kommen ohne zweite Implementierung hinzu, die Werte sind dieselben wie
im Regelwerk. SYNTHETISCHE Daten."""

from __future__ import annotations

import dataclasses
import unittest

import numpy as np

from traktien.aktienpilot import katalog as kat
from traktien.aktienpilot import merkmale as mk

from tests.unit import ap_szenario as sz


class MerkmalslisteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.S = sz.bauen(fuell=4)
        cls.K = kat.katalog(cls.S.method, cls.S.cfg)
        cls.liste, cls.inventar = mk.merkmale(cls.K)

    def test_every_catalog_metric_is_used_or_excluded_with_reason(self):
        self.assertEqual([x["kennzahl"] for x in self.inventar], list(self.K))
        for x in self.inventar:
            self.assertTrue(x["verwendet"] or x["grund"], x["kennzahl"])
            self.assertEqual(x["ungueltig"], [], x["kennzahl"])
            if x["verwendet"]:
                self.assertTrue(x["merkmale"], x["kennzahl"])
        ausgeschlossen = {x["kennzahl"] for x in self.inventar if not x["verwendet"]}
        self.assertIn("spaeterer_sieger", ausgeschlossen, "rückblickend – nie für Entscheidungen")
        self.assertTrue({"gehalten", "haltedauer", "positionsgewicht"} <= ausgeschlossen, "Depotwerte gehören nicht zur Aktie")
        self.assertIn("kurs", ausgeschlossen)

    def test_keys_unique_and_variants_follow_the_catalog(self):
        keys = [m.schluessel for m in self.liste]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn("rendite", keys)
        self.assertIn("rendite@fenster=60", keys)
        self.assertIn("haeufigkeit@k=1", keys)
        for m in self.liste:
            self.assertEqual(self.K[m.kennzahl].kennzahl.parameter_pruefen(m.params), m.params, m.schluessel)

    def test_new_catalog_metric_is_picked_up_without_extra_code(self):
        k = self.K["rsi"].kennzahl
        neu = dataclasses.replace(k, id="neue_kennzahl", name="Neue Kennzahl")
        katalog = dict(self.K, neue_kennzahl=kat.Eintrag(neu, self.K["rsi"].werte))
        liste, inventar = mk.merkmale(katalog)
        self.assertIn("neue_kennzahl", [m.kennzahl for m in liste])
        self.assertTrue(next(x for x in inventar if x["kennzahl"] == "neue_kennzahl")["verwendet"])

    def test_matrix_uses_the_same_values_as_the_rules(self):
        D = int(self.S.sessions[-1])
        ctx = self.S.kontext(D)
        X, fehlend = mk.matrix(ctx, self.K, self.liste)
        self.assertEqual(X.shape, (len(ctx.isins), len(self.liste)))
        self.assertEqual(X.dtype, np.float32)
        self.assertEqual(fehlend, [])
        j = [m.schluessel for m in self.liste].index("rendite@fenster=60")
        _, _, regel = kat.werte(ctx, self.K, {"id": "rendite", "parameter": {"fenster": 60}})
        np.testing.assert_allclose(X[:, j], np.asarray(regel, dtype=np.float32), equal_nan=True)
        jb = [m.schluessel for m in self.liste].index("ausbruch_hoch")
        self.assertTrue(set(np.unique(X[np.isfinite(X[:, jb]), jb])) <= {0.0, 1.0}, "Wahrheitswerte als 0/1")
        self.assertGreater(float(mk.abdeckung(X)[j]), 0.5)

    def test_inventory_states_source_availability_and_currency(self):
        x = next(i for i in self.inventar if i["kennzahl"] == "kursziel_abstand")
        self.assertEqual(x["historisch"], "nur vorwärts (keine Historie)")
        self.assertIn("Abruf", x["verfuegbar"])
        self.assertEqual(next(i for i in self.inventar if i["kennzahl"] == "rendite")["waehrung"], "währungsneutral")
        self.assertEqual(next(i for i in self.inventar if i["kennzahl"] == "tagesumsatz_usd")["waehrung"], "USD")


if __name__ == "__main__":
    unittest.main()
