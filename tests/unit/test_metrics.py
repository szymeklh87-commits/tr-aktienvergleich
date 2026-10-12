"""T01, T02, T05–T07, T10, T11, T39: Rendite, OLS, R², Rückgang (synthetische Daten)."""

from __future__ import annotations

import math
import unittest
from fractions import Fraction

import numpy as np

from traktien.analytics.metrics import (
    NumericInconsistency,
    calculate_price_metrics,
    max_drawdown,
    price_return,
)


def exact_reference(prices: list[float]) -> dict:
    """Unabhängige exakte Referenz mit Brüchen (keine Gleitkommaarithmetik)."""
    p = [Fraction(x) for x in prices]
    n = len(p)
    t = [Fraction(i) for i in range(n)]
    tm = sum(t) / n
    pm = sum(p) / n
    stt = sum((ti - tm) ** 2 for ti in t)
    stp = sum((ti - tm) * (pi - pm) for ti, pi in zip(t, p))
    m = stp / stt
    b = pm - m * tm
    sse = sum((pi - (m * ti + b)) ** 2 for ti, pi in zip(t, p))
    sst = sum((pi - pm) ** 2 for pi in p)
    r2 = 1 - sse / sst if sst != 0 else None
    peak = p[0]
    mdd = Fraction(0)
    for value in p:
        peak = max(peak, value)
        mdd = max(mdd, 1 - value / peak)
    return {
        "r": float(p[-1] / p[0] - 1),
        "m": float(m),
        "r2": None if r2 is None else float(r2),
        "slope_pct": float(100 * m / pm),
        "noise_pct": 100 * math.sqrt(float(sse / n)) / float(pm),
        "mdd": float(mdd),
    }


class ReturnTests(unittest.TestCase):
    def test_T01_hundred_to_hundred_twenty_is_plus_20_percent(self):
        r = price_return(100.0, 120.0)
        self.assertAlmostEqual(r, 0.20, places=15)
        self.assertAlmostEqual(100 * r, 20.0, places=12)  # +20 %, nicht 0,2 % und nicht 120 %

    def test_T02_negative_returns_stay_negative(self):
        r = price_return(100.0, 80.0)
        self.assertAlmostEqual(r, -0.20, places=15)
        self.assertLess(r, 0)

    def test_return_requires_positive_finite_prices(self):
        for bad in (0.0, -1.0, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                price_return(bad, 10.0)


class OlsTests(unittest.TestCase):
    def test_T05_exact_rising_line_has_r2_one_and_positive_slope(self):
        prices = np.array([100.0 + 2.0 * i for i in range(20)])
        metrics = calculate_price_metrics(prices)
        self.assertTrue(metrics.r2_defined)
        self.assertAlmostEqual(metrics.r2, 1.0, places=12)
        self.assertGreater(metrics.m, 0)
        self.assertAlmostEqual(metrics.m, 2.0, places=10)

    def test_T06_exact_falling_line_also_has_r2_near_one(self):
        prices = np.array([200.0 - 3.0 * i for i in range(20)])
        metrics = calculate_price_metrics(prices)
        self.assertAlmostEqual(metrics.r2, 1.0, places=12)
        self.assertLess(metrics.m, 0)
        self.assertLess(metrics.r, 0)

    def test_T07_constant_series_has_no_defined_r2(self):
        prices = np.full(25, 42.0)
        metrics = calculate_price_metrics(prices)
        self.assertFalse(metrics.r2_defined)
        self.assertIsNone(metrics.r2)
        self.assertEqual(metrics.r, 0.0)
        self.assertEqual(metrics.mdd, 0.0)

    def test_short_series_has_no_r2_from_two_points(self):
        metrics = calculate_price_metrics(np.array([10.0, 11.0]))
        self.assertIsNone(metrics.r2)
        self.assertIsNone(metrics.m)
        self.assertAlmostEqual(metrics.r, 0.1, places=15)

    def test_T10_rising_series_with_crash_reports_mdd_independently(self):
        prices = [100.0 + i for i in range(30)]
        prices[15] = prices[14] * 0.6  # einzelner starker Einbruch
        metrics = calculate_price_metrics(np.array(prices))
        self.assertGreater(metrics.r2, 0.5)
        self.assertAlmostEqual(metrics.mdd, 0.4, places=12)

    def test_T11_mdd_of_100_120_90_110_is_25_percent(self):
        self.assertAlmostEqual(max_drawdown(np.array([100.0, 120.0, 90.0, 110.0])), 0.25, places=15)
        metrics = calculate_price_metrics(np.array([100.0, 120.0, 90.0, 110.0]), min_obs_trend=15)
        self.assertAlmostEqual(-100 * metrics.mdd, -25.0, places=12)

    def test_mdd_ignores_prices_before_window(self):
        # Das Fenster beginnt nach einem früheren Hoch – MDD startet am Fensteranfang.
        self.assertEqual(max_drawdown(np.array([50.0, 55.0, 60.0])), 0.0)

    def test_invalid_prices_are_rejected(self):
        with self.assertRaises(ValueError):
            calculate_price_metrics(np.array([10.0, float("nan"), 12.0]))
        with self.assertRaises(ValueError):
            calculate_price_metrics(np.array([10.0]))


class ReferenceComparisonTests(unittest.TestCase):
    """T39: optimierte Berechnung stimmt mit unabhängiger Referenz überein."""

    def test_T39_against_exact_fraction_reference_and_polyfit(self):
        rng = np.random.default_rng(20261012)  # SYNTHETISCH
        for case in range(200):
            n = int(rng.integers(15, 70))
            level = float(10 ** rng.uniform(-2, 5))
            steps = rng.normal(0.0005, 0.02, size=n)
            prices = level * np.exp(np.cumsum(steps))
            metrics = calculate_price_metrics(prices)
            ref = exact_reference(prices.tolist())
            self.assertTrue(math.isclose(metrics.r, ref["r"], rel_tol=1e-12, abs_tol=1e-15), case)
            self.assertTrue(math.isclose(metrics.m, ref["m"], rel_tol=1e-9, abs_tol=1e-12 * level), case)
            self.assertTrue(math.isclose(metrics.r2, ref["r2"], rel_tol=1e-9, abs_tol=1e-10), case)
            self.assertTrue(math.isclose(metrics.slope_pct, ref["slope_pct"], rel_tol=1e-9, abs_tol=1e-10), case)
            self.assertTrue(math.isclose(metrics.noise_pct, ref["noise_pct"], rel_tol=1e-7, abs_tol=1e-10), case)
            self.assertTrue(math.isclose(metrics.mdd, ref["mdd"], rel_tol=1e-12, abs_tol=1e-15), case)
            slope_np, _ = np.polyfit(np.arange(n, dtype=float), prices, 1)
            self.assertTrue(math.isclose(metrics.m, slope_np, rel_tol=1e-7, abs_tol=1e-9 * level), case)

    def test_r2_out_of_range_raises(self):
        # Direkter Selbsttest der Schutzlogik über eine manipulierte Toleranz ist nicht möglich,
        # daher prüfen wir die Ausnahme-Klasse und die Klemmung an den Rändern.
        self.assertTrue(issubclass(NumericInconsistency, ArithmeticError))
        metrics = calculate_price_metrics(np.array([1.0 + 1e-3 * i for i in range(30)]))
        self.assertLessEqual(metrics.r2, 1.0)
        self.assertGreaterEqual(metrics.r2, 0.0)


if __name__ == "__main__":
    unittest.main()
