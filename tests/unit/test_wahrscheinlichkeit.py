"""Wahrscheinlichkeiten 1–30 Handelstage (ab 1.25.0, ``wahrscheinlichkeit-1``): Test ohne Zukunftsdaten, Kalibrierung,
„Nicht ausreichend zuverlässig“ bei Zufall, erkannte Regelmäßigkeit bei echtem Muster."""

from __future__ import annotations

import unittest

import numpy as np

from traktien.analytics import signals as sg
from traktien.analytics import wahrscheinlichkeit as wk


def raw(seed: int, n_stocks: int, n_days: int, momentum: float) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """Kursreihen: tägliche Veränderung = momentum × tanh(Veränderung der letzten 5 Tage / 2 %) + Rauschen."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_stocks):
        close = np.empty(n_days)
        close[:6] = 100.0 * (1 + rng.normal(0, 0.01, 6)).cumprod()
        for t in range(6, n_days):
            trend = np.tanh((close[t - 1] / close[t - 6] - 1.0) / 0.02)
            close[t] = close[t - 1] * (1.0 + momentum * trend + rng.normal(0, 0.012))
        spread_hi = 1 + np.abs(rng.normal(0, 0.004, n_days))
        spread_lo = 1 - np.abs(rng.normal(0, 0.004, n_days))
        volume = rng.uniform(4e5, 6e5, n_days)
        out.append((close, spread_hi, spread_lo, volume))
    return out


def build(series, n_days: int) -> list[wk.StockPanel]:
    days = np.arange(20000, 20000 + n_days, dtype=np.int64)
    out = []
    for s, (close, hi, lo, volume) in enumerate(series):
        ts = sg.tech_series(close, close * hi, close * lo, close, volume)
        out.append(wk.stock_panel(f"ZZ{s:010d}", days, ts, np.full(n_days, 5e7)))
    return out


def panel(seed: int, n_stocks: int, n_days: int, momentum: float) -> list[wk.StockPanel]:
    return build(raw(seed, n_stocks, n_days, momentum), n_days)


class ProbabilityTests(unittest.TestCase):
    def test_logistic_fit_recovers_known_relation(self):
        rng = np.random.default_rng(1)
        X = rng.normal(size=(20000, 2))
        p = 1 / (1 + np.exp(-(0.3 + 1.2 * X[:, 0] - 0.5 * X[:, 1])))
        y = (rng.random(20000) < p).astype(float)
        w = wk.fit_logistic(X, y, l2=0.1)
        self.assertAlmostEqual(w[0], 0.3, delta=0.08)
        self.assertAlmostEqual(w[1], 1.2, delta=0.1)
        self.assertAlmostEqual(w[2], -0.5, delta=0.08)

    def test_calibration_bins_and_metrics(self):
        p = np.array([0.05, 0.15, 0.15, 0.95])
        y = np.array([0.0, 0.0, 1.0, 1.0])
        bins = wk.calibration_bins(p, y, np.array([-0.01, 0.0, 0.02, 0.05]))
        self.assertEqual([b["n"] for b in bins], [1, 2, 1])
        self.assertEqual(bins[1]["beob"], 0.5)
        self.assertAlmostEqual(wk._ece(bins, 4), (0.05 + 2 * 0.35 + 0.05) / 4, places=4)

    def test_pure_noise_is_not_reliable_and_shows_no_percentages(self):
        result = wk.compute(panel(7, 40, 320, momentum=0.0))
        q = result.payload["qualitaet"]
        self.assertEqual(sorted(int(h) for h in q), list(range(1, 31)))
        unreliable = [h for h in wk.HORIZONS if not q[str(h)]["zuverlaessig"]]
        self.assertGreaterEqual(len(unreliable), 27, "Zufall darf höchstens ausnahmsweise als zuverlässig gelten")
        for h in unreliable:
            self.assertTrue(all(v is None for v in result.probabilities[h]), "ohne Zuverlässigkeit keine Prozentzahl")
            self.assertTrue(q[str(h)]["grund"])

    def test_planted_momentum_is_found_calibrated_and_explained(self):
        stocks = panel(3, 40, 420, momentum=0.004)
        result = wk.compute(stocks)
        q1 = result.payload["qualitaet"]["1"]
        self.assertTrue(q1["zuverlaessig"], q1)
        self.assertGreater(q1["skill"], 0.005)
        self.assertLessEqual(q1["ece"], wk.MAX_ECE)
        self.assertGreater(q1["n"], wk.MIN_TEST)
        # Vorhersage folgt dem Muster: nach steigenden 5 Tagen eher Anstieg
        p1 = result.probabilities[1]
        ups = [p1[i] for i, s in enumerate(stocks) if s.feats["r5"][-1] > 0.01 and p1[i] is not None]
        downs = [p1[i] for i, s in enumerate(stocks) if s.feats["r5"][-1] < -0.01 and p1[i] is not None]
        self.assertTrue(ups and downs)
        self.assertGreater(np.mean(ups), 55)
        self.assertLess(np.mean(downs), 45)
        if result.payload["qualitaet"][str(wk.REASON_HORIZON)]["zuverlaessig"]:
            some = [r for r in result.reasons if r]
            self.assertTrue(some)
            self.assertTrue(all(len(r) <= 3 for r in result.reasons))

    def test_no_look_ahead_training_ends_before_test_block(self):
        """Veränderte Kurse ganz am Ende dürfen den ersten Testblock nicht berühren: Training dort endet, bevor der Block
        beginnt; die Merkmale früherer Tage hängen nicht von späteren Kursen ab."""
        series = raw(5, 30, 360, momentum=0.003)
        stocks = build(series, 360)
        changed = []
        for close, hi, lo, volume in series:
            c = close.copy()
            c[-3:] *= 3.0
            changed.append((c, hi, lo, volume))
        poisoned = build(changed, 360)
        for h in (1, 5, 20):
            a = wk.walk_forward(wk._samples(stocks, wk._market(stocks)), h)
            b = wk.walk_forward(wk._samples(poisoned, wk._market(poisoned)), h)
            self.assertEqual(len(a), wk.FOLDS)
            np.testing.assert_array_equal(a[0][0], b[0][0])
            np.testing.assert_allclose(a[0][1], b[0][1], rtol=0, atol=1e-12, err_msg=f"erster Testblock h={h} unverändert")
        # die Ergebnisse der letzten Testfälle ändern sich – die Prüfung misst sie
        before = wk.evaluate_horizon(wk._samples(stocks, wk._market(stocks)), 1)
        after = wk.evaluate_horizon(wk._samples(poisoned, wk._market(poisoned)), 1)
        self.assertNotEqual(before["beob"], after["beob"])

    def test_illiquid_stocks_get_no_probability(self):
        stocks = panel(3, 30, 400, momentum=0.004)
        thin = stocks[0]
        thin.liquid[:] = False
        result = wk.compute(stocks)
        for h in wk.HORIZONS:
            self.assertIsNone(result.probabilities[h][0])


if __name__ == "__main__":
    unittest.main()
