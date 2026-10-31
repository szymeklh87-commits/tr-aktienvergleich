"""Depotoptimierung (Auftrag 18, Abschnitte 8–10): Grenzen je Aktie und Branche, keine zwei fast gleich laufenden Aktien,
keine Aktie ohne Vorteil nach Kosten, Kennzahlen des Depots, Umschichtung nur mit Vorteil nach Kosten. SYNTHETISCHE Werte."""

from __future__ import annotations

import unittest

import numpy as np

from traktien.aktienpilot import portfolio as pf


def kand(n=12, seed=3):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        out.append(pf.Kandidat(isin=f"ZZ{i:010d}", erwartet_pct=float(2 + i), kosten_pct=0.5, wertung_rang=i / n,
                               branche="Technik" if i % 2 == 0 else f"B{i}", waehrung="EUR" if i % 3 else "USD", umsatz_eur=1e7))
    return out, rng


class OptimierungTests(unittest.TestCase):
    def test_limits_count_weight_and_sector(self):
        k, rng = kand()
        r = rng.normal(0, 0.01, (120, len(k)))
        S = pf.kovarianz(r) * 60
        w = pf.optimieren(k, S, anzahl=6, lam=4.0, max_gewicht=0.25, max_branche=0.35)
        self.assertLessEqual(int((w > 1e-9).sum()), 6)
        self.assertLessEqual(float(w.max()), 0.25 + 1e-6)
        tech = sum(wi for wi, x in zip(w, k) if x.branche == "Technik")
        self.assertLessEqual(tech, 0.35 + 1e-6)
        self.assertAlmostEqual(float(w.sum()), 1.0, places=5)
        # höhere Erwartung bei gleichem Risiko bekommt nicht weniger Gewicht als die schwächste gewählte
        chosen = np.nonzero(w > 1e-9)[0]
        self.assertIn(len(k) - 1, chosen, "beste Erwartung ist dabei")

    def test_no_position_without_positive_expectation_after_costs(self):
        k, rng = kand(5)
        for x in k:
            x.erwartet_pct = 0.3  # unter den Kosten von 0,5
        k[4].erwartet_pct = 3.0
        S = pf.kovarianz(rng.normal(0, 0.01, (120, 5))) * 20
        w = pf.optimieren(k, S, anzahl=5, lam=1.0, max_gewicht=1.0, max_branche=1.0)
        self.assertEqual(list(np.nonzero(w > 1e-9)[0]), [4])

    def test_nearly_identical_stocks_are_not_both_chosen(self):
        rng = np.random.default_rng(1)
        base = rng.normal(0, 0.01, 120)
        r = np.column_stack([base, base + rng.normal(0, 0.0005, 120), rng.normal(0, 0.01, 120), rng.normal(0, 0.01, 120)])
        k = [pf.Kandidat(f"ZZ{i:010d}", erwartet_pct=e, kosten_pct=0.2, wertung_rang=0.5) for i, e in enumerate((6.0, 5.9, 4.0, 3.0))]
        w = pf.optimieren(k, pf.kovarianz(r) * 60, anzahl=3, lam=2.0, max_gewicht=0.6, max_branche=1.0, korr=pf.korrelation(r))
        self.assertFalse(w[0] > 0 and w[1] > 0, "Korrelation über der Grenze")

    def test_covariance_is_positive_semidefinite_and_portfolio_figures(self):
        k, rng = kand(6)
        r = rng.normal(0.0005, 0.012, (200, 6))
        S = pf.kovarianz(r)
        self.assertGreaterEqual(float(np.linalg.eigvalsh(S).min()), -1e-12)
        w = np.array([0.5, 0.5, 0, 0, 0, 0])
        kz = pf.depot_kennzahlen(w, k, S * 20, r, 20)
        self.assertAlmostEqual(kz["erwartet_pct"], 0.5 * 2 + 0.5 * 3)
        self.assertAlmostEqual(kz["erwartet_nach_kosten_pct"], kz["erwartet_pct"] - 0.5)
        self.assertEqual(kz["positionen"], 2)
        self.assertAlmostEqual(kz["effektive_anzahl"], 2.0)
        self.assertLess(kz["verlustszenario_pct"], 0)
        self.assertAlmostEqual(sum(kz["branchen"].values()), 100.0, places=1)

    def test_return_matrix_aligns_days_and_fills_gaps(self):
        reihen = {"A": (np.array([1, 2, 3, 5]), np.array([10.0, 11.0, 12.1, 13.31])), "B": (np.array([1, 3, 5]), np.array([5.0, 5.0, 5.0]))}
        r = pf.renditen_matrix(reihen, ["A", "B"], bis_tag=5, tage=10)
        self.assertEqual(r.shape, (3, 2))
        np.testing.assert_allclose(r[:, 1], 0.0)
        np.testing.assert_allclose(np.exp(r[:, 0].sum()), 1.331, rtol=1e-9)


class UmschichtungTests(unittest.TestCase):
    def setUp(self):
        self.e = pf.Einstellungen(anzahl=3, mindestverbesserung_pp=1.0, toleranz_pp=3.0, halte_faktor=2.0)

    def k(self, isin, netto):
        return pf.Kandidat(isin, erwartet_pct=netto + 0.5, kosten_pct=0.5, wertung_rang=0.5)

    def test_hold_inside_band_when_switch_brings_too_little(self):
        kand = {"A": self.k("A", 4.0), "B": self.k("B", 3.0), "C": self.k("C", 2.6), "D": self.k("D", 2.9)}
        alt = {"A": 33.3, "B": 33.3, "C": 33.4}
        ziel = {"A": 34.0, "B": 33.0, "D": 33.0}  # D knapp vor C
        rang = {"A": 1, "B": 2, "D": 3, "C": 4}
        neu, zeilen = pf.veraenderungen(alt, ziel, kand, rang, self.e)
        self.assertIn("C", neu, "C bleibt: Tausch bringt nach Kosten weniger als die Mindestverbesserung")
        self.assertNotIn("D", neu)
        z = {x["isin"]: x for x in zeilen}
        self.assertEqual(z["C"]["art"], "halten")
        self.assertIn("Mindestverbesserung", z["C"]["grund"])
        self.assertEqual(z["A"]["art"], "halten", "Gewichtsänderung unter der Toleranz")
        self.assertAlmostEqual(sum(neu.values()), 100.0, places=1)

    def test_sell_outside_band_and_buy_replacement(self):
        kand = {"A": self.k("A", 4.0), "B": self.k("B", 3.0), "C": self.k("C", 0.5), "D": self.k("D", 5.0)}
        alt = {"A": 33.3, "B": 33.3, "C": 33.4}
        ziel = {"D": 40.0, "A": 30.0, "B": 30.0}
        rang = {"D": 1, "A": 2, "B": 3, "C": 9}
        neu, zeilen = pf.veraenderungen(alt, ziel, kand, rang, self.e)
        z = {x["isin"]: x for x in zeilen}
        self.assertEqual(z["C"]["art"], "verkaufen")
        self.assertIn("nicht mehr unter den besten 6", z["C"]["grund"])
        self.assertEqual(z["D"]["art"], "kaufen")
        self.assertNotIn("C", neu)


if __name__ == "__main__":
    unittest.main()
