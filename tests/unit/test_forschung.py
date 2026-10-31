"""Forschungsmotor des Depot-Optimierers (Aufträge 18 und 19) auf einem SYNTHETISCHEN Panel mit eingepflanzten Zusammenhängen:
ein Merkmal sagt die spätere Rendite voraus, eines davon fast eine Kopie (Redundanz), eines wirkt umgekehrt, der Rest ist
Rauschen. Geprüft wird, dass die Prüfung genau das findet, Rauschen nicht als Nutzen ausgibt, Redundanz erkennt, im
Walk-forward nichts aus der Zukunft lernt und bei zu kurzer Historie „nicht belastbar“ sagt."""

from __future__ import annotations

import math
import unittest

import numpy as np

from traktien.aktienpilot import forschung as fo

MERKMALE = ["signal", "signal_kopie", "rauschen_a", "gegen", "rauschen_b", "rendite@fenster=20", "rendite@fenster=60", "rendite@fenster=90"]


def panel(T: int = 140, N: int = 300, schritt: int = 5, staerke: float = 1.0, seed: int = 7) -> fo.Panel:
    """Synthetisches Panel: Rendite über h Handelstage = staerke·(Signal − Gegen)·√(h/5) + Rauschen·√(h/5) (in Prozent)."""
    rng = np.random.default_rng(seed)
    tage = 20000 + np.arange(T) * 7
    raw = rng.standard_normal((T, N, len(MERKMALE)))
    raw[:, :, 1] = raw[:, :, 0] + 0.15 * rng.standard_normal((T, N))  # fast dieselbe Information
    X = np.empty_like(raw)
    for t in range(T):
        X[t] = fo.raenge(raw[t])
    R = {}
    for h, n in fo.HORIZONTE.items():
        skala = math.sqrt(n / 5.0)
        r = staerke * (raw[:, :, 0] - raw[:, :, 3]) * skala + 4.0 * rng.standard_normal((T, N)) * skala
        # Folgerendite erst bekannt, wenn h Handelstage nach dem Tag vergangen sind
        bekannt = T - int(math.ceil(n / schritt))
        r[max(bekannt, 0):] = np.nan
        R[h] = r.astype(np.float32)
    X[5, :20, 2] = np.nan  # einzelne fehlende Werte
    return fo.Panel(tage=tage, isins=[f"ZZ{i:010d}" for i in range(N)], merkmale=list(MERKMALE), X=X.astype(np.float32), R=R, schritt=schritt)


class GrundlagenTests(unittest.TestCase):
    def test_ranks_and_spearman_by_hand(self):
        x = np.array([3.0, 1.0, 2.0, np.nan, 2.0])
        np.testing.assert_allclose(fo.raenge(x), [1.0, 0.25, 0.625, np.nan, 0.625])
        a = np.arange(40, dtype=float)
        self.assertAlmostEqual(fo.rang_ic(a, a ** 3), 1.0)
        self.assertAlmostEqual(fo.rang_ic(a, -a), -1.0)
        self.assertTrue(math.isnan(fo.rang_ic(a[:10], a[:10])), "zu wenige Aktien")

    def test_independent_periods_and_benjamini_hochberg(self):
        self.assertEqual(fo.unabhaengige(100, 5, 5), 100)
        self.assertEqual(fo.unabhaengige(100, 5, 260), 100 * 5 / 260)
        self.assertEqual(fo.benjamini_hochberg([0.001, 0.02, 0.03, 0.5], q=0.1), [True, True, True, False])
        self.assertEqual(fo.benjamini_hochberg([0.2, 0.3], q=0.1), [False, False])

    def test_isotonic_smoothing(self):
        self.assertEqual(fo._isoton([1.0, 3.0, 2.0, 4.0], [1, 1, 1, 1]), [1.0, 2.5, 2.5, 4.0])


class FaktorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = panel()
        cls.fp = fo.faktorpruefung(cls.p, ["w1", "w4"])

    def row(self, m, h):
        return next(z for z in self.fp["zeilen"] if z["merkmal"] == m and z["horizont"] == h)

    def test_planted_signals_are_confirmed_with_direction(self):
        for h in ("w1", "w4"):
            self.assertTrue(self.row("signal", h)["bestaetigt"], h)
            self.assertEqual(self.row("signal", h)["richtung"], 1)
            self.assertTrue(self.row("gegen", h)["bestaetigt"], h)
            self.assertEqual(self.row("gegen", h)["richtung"], -1, "umgekehrter Zusammenhang erkannt")
            self.assertGreater(self.row("signal", h)["entwicklung"]["spanne_pp"], 0)

    def test_noise_is_not_reported_as_useful(self):
        for m in ("rauschen_a", "rauschen_b", "rendite@fenster=20", "rendite@fenster=60"):
            for h in ("w1", "w4"):
                self.assertFalse(self.row(m, h)["bestaetigt"], (m, h))

    def test_periods_are_disjoint_and_ordered(self):
        idx = self.p.bekannt("w4")
        zr = fo.zeitraeume(idx)
        self.assertLess(zr["entwicklung"].max(), zr["validierung"].min())
        self.assertLess(zr["validierung"].max(), zr["test"].min())
        self.assertEqual(len(zr["entwicklung"]) + len(zr["validierung"]) + len(zr["test"]), len(idx))

    def test_redundancy_and_incremental_value(self):
        red = fo.redundanz(self.p, np.arange(len(self.p.tage)))
        self.assertIn(("signal", "signal_kopie"), [(x["a"], x["b"]) for x in red["paare"]])
        zr = fo.zeitraeume(self.p.bekannt("w1"))
        auswahl = fo.zusatznutzen(self.p, "w1", self.fp["zeilen"], red, zr)
        self.assertIn("signal", auswahl["merkmale"] + ["signal_kopie"])
        self.assertFalse({"signal", "signal_kopie"} <= set(auswahl["merkmale"]), "Kopie bringt keinen Zusatznutzen")
        self.assertIn("gegen", auswahl["merkmale"])
        grund = {x["merkmal"]: x["grund"] for x in auswahl["uebersprungen"]}
        self.assertTrue(any("überschneidet sich" in g for g in grund.values()))


class ModellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = panel()
        T = len(cls.p.tage)
        cls.res = fo.forschen(cls.p, ["w1", "w4", "w52"], benchmarks={"w4": {"welt": np.full(T, 0.5), "kern": np.full(T, 0.3)}})

    def test_walk_forward_prefers_real_signal_over_null_and_momentum(self):
        h = self.res["horizonte"]["w1"]
        m = h["walk_forward"]["modelle"]
        self.assertGreater(m["linear"]["ic"], 0.05)
        self.assertGreaterEqual(m["linear"]["t"], fo.MODELL_MIN_T)
        self.assertLess(abs(m["momentum"]["ic"]), 0.05, "Momentum ist hier Rauschen")
        self.assertIn(h["modell"], ("linear", "aehnlichkeit", "kombination"))
        self.assertIn(h["belastbarkeit"], ("belastbar", "eingeschränkt belastbar"))
        self.assertGreater(m["linear"]["top_ueberschuss_pp"], 0)

    def test_calibration_is_monotone_and_informative(self):
        kal = self.res["horizonte"]["w1"]["kalibrierung"]
        d = kal["dezile"]
        self.assertEqual(len(d), 10)
        self.assertTrue(all(a["mittel_pct"] <= b["mittel_pct"] for a, b in zip(d, d[1:])))
        self.assertTrue(all(a["positiv_pct"] <= b["positiv_pct"] for a, b in zip(d, d[1:])))
        self.assertGreater(d[-1]["mittel_pct"], d[0]["mittel_pct"])
        self.assertLessEqual(kal["brier"]["modell"], kal["brier"]["basis"])
        self.assertTrue(all(x["q10_pct"] <= x["q50_pct"] <= x["q90_pct"] for x in d))

    def test_long_horizon_without_enough_history_is_not_reliable(self):
        h = self.res["horizonte"]["w52"]
        self.assertEqual(h["belastbarkeit"], "nicht belastbar")
        self.assertIsNone(h["endmodell"], "keine Zahlen ohne belastbare Grundlage")

    def test_training_never_sees_future_returns(self):
        """Ein Modell, trainiert mit Tagen bis X, ändert sich nicht, wenn sich die Renditen ab X ändern (Purging eingeschlossen)."""
        p = panel()
        zr = fo.zeitraeume(p.bekannt("w4"))
        auswahl = {"merkmale": ["signal", "gegen"], "richtungen": [1, -1]}
        train = fo._gereinigt(zr["entwicklung"], int(zr["validierung"][0]), fo.HORIZONTE["w4"], p.schritt)
        self.assertLessEqual(train.max(), zr["validierung"][0] - math.ceil(fo.HORIZONTE["w4"] / p.schritt))
        a = fo.trainieren("linear", p, "w4", train, auswahl)
        p.R["w4"][int(train.max()) + 1:] = 999.0
        b = fo.trainieren("linear", p, "w4", train, auswahl)
        self.assertEqual(a.koeffizienten, b.koeffizienten)

    def test_scoring_today_matches_panel_scoring_and_model_round_trip(self):
        p = self.p
        mdict = self.res["horizonte"]["w1"]["endmodell"]
        m = fo.Modell.from_dict(mdict)
        t = 30
        a = fo.wertung(m, p, t)
        b = fo.bewerten(m, lambda key: p.X[t, :, p.j(key)], p.X.shape[1])
        np.testing.assert_allclose(a, b)
        self.assertEqual(fo.Modell.from_dict(m.as_dict()).as_dict(), m.as_dict())

    def test_retrospective_portfolio_out_of_sample(self):
        """„Bestes historisch getestetes Depot“: nur Walk-forward-Tage, nicht überlappend; das Modell mit echtem Signal schlägt
        gleich gewichtete und Rausch-Strategien; Welt-ETF-Vergleich je Periode."""
        rb = self.res["horizonte"]["w4"]["rueckblick"]
        s = rb["strategien"]
        self.assertGreater(rb["perioden"], 2)
        self.assertLessEqual(rb["perioden"], len(self.p.tage) // (fo.HORIZONTE["w4"] // self.p.schritt))
        self.assertGreater(s["modell"]["mittel_pct"], s["markt"]["mittel_pct"])
        self.assertGreater(s["modell"]["mittel_pct"], s["momentum"]["mittel_pct"])
        self.assertEqual(rb["beste"], "modell")
        self.assertEqual(s["welt"]["mittel_pct"], 0.5)
        self.assertIsNotNone(s["modell"]["besser_als_welt"])
        self.assertEqual(s["platz1"]["perioden"], 0, "Merkmal fehlt im Panel: keine Zahl statt einer erfundenen")
        self.assertIsNone(self.res["horizonte"]["w1"]["rueckblick"], "Rückblick nur für 4, 12 und 26 Wochen")

    def test_counts_are_reported(self):
        z = self.res["zaehlung"]
        self.assertEqual(z["merkmale"], len(MERKMALE))
        self.assertEqual(z["pruefungen"], len(MERKMALE) * 3)
        self.assertGreater(z["modelle"], 0)


if __name__ == "__main__":
    unittest.main()
