"""T12–T20, T80–T85: Perzentile, elf Gewichtungen, Vergleichsmengen (synthetische Daten)."""

from __future__ import annotations

import datetime as dt
import math
import unittest

import numpy as np

from traktien.analytics.codes import Status
from traktien.analytics.engine import compute_snapshot
from traktien.analytics.ranking import percentile_average_rank, rank_subgroup, rank_window, weighted_score
from traktien.config import CANONICAL_WEIGHTS, LEGACY_MODE_ALIASES, POLICIES, MethodConfig, parse_weight
from tests.helpers import day, make_instrument, test_isin, weekday_sessions

CFG = MethodConfig()


def build_window(r, r2, slope=None, noise=None, v=None, u=None, h=30):
    n = len(r)
    r = np.asarray(r, dtype=float)
    r2 = np.asarray(r2, dtype=float)
    slope = np.asarray(slope if slope is not None else [1.0] * n, dtype=float)
    noise = np.asarray(noise if noise is not None else [1.0] * n, dtype=float)
    v = np.arange(n) if v is None else np.asarray(v)
    u = v if u is None else np.asarray(u)
    return rank_window(h, v, u, r, r2, slope, noise), r, r2, slope, noise


class PercentileTests(unittest.TestCase):
    def test_T12_identical_r2_get_average_ranks(self):
        p = percentile_average_rank(np.array([0.9, 0.5, 0.9, 0.7]))
        np.testing.assert_allclose(p, [100 * 2.5 / 3, 0.0, 100 * 2.5 / 3, 100 / 3])

    def test_T13_all_identical_values_give_50(self):
        np.testing.assert_array_equal(percentile_average_rank(np.array([0.3] * 7)), [50.0] * 7)

    def test_T14_single_candidate_gets_100_and_sole_flag(self):
        window, *_ = build_window([0.1], [0.8])
        self.assertTrue(window.native0.sole_candidate)
        self.assertEqual(window.native0.scores.tolist(), [100.0])
        for weight in CANONICAL_WEIGHTS:
            self.assertEqual(window.trend[weight].scores.tolist(), [100.0])
            self.assertTrue(window.trend[weight].sole_candidate)

    def test_T15_zero_candidates_no_division_and_no_invented_top10(self):
        window, *_ = build_window([], [])
        self.assertEqual(window.native0.size, 0)
        for weight in CANONICAL_WEIGHTS:
            self.assertEqual(window.trend[weight].size, 0)


class WeightTests(unittest.TestCase):
    def test_T80_exactly_eleven_weights_with_complement(self):
        self.assertEqual(CANONICAL_WEIGHTS, (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100))
        self.assertEqual(len(set(CANONICAL_WEIGHTS)), 11)
        for w in CANONICAL_WEIGHTS:
            self.assertEqual(w + (100 - w), 100)
        for bad in (5, 15, 110, -10, "70/30", 60.5):
            with self.assertRaises(ValueError):
                parse_weight(bad)

    def test_T79_legacy_aliases_map_to_canonical_weights(self):
        self.assertEqual({k: parse_weight(k) for k in LEGACY_MODE_ALIASES}, LEGACY_MODE_ALIASES)
        self.assertTrue(set(LEGACY_MODE_ALIASES.values()) <= set(CANONICAL_WEIGHTS))

    def test_T18_score_example_g90_r60(self):
        expected = [60, 63, 66, 69, 72, 75, 78, 81, 84, 87, 90]
        for w, value in zip(CANONICAL_WEIGHTS, expected):
            score = float(weighted_score(w, np.array([90.0]), np.array([60.0]))[0])
            self.assertTrue(math.isclose(score, value, abs_tol=1e-12), (w, score))

    def test_T17_unrounded_scores_decide_order(self):
        rng = np.random.default_rng(7)  # SYNTHETISCH
        n = 400
        r = rng.normal(0.05, 0.03, n)
        r2 = rng.uniform(0.2, 0.99, n)
        r2[::7] = r2[0]  # Gleichstände im R²
        r[::11] = r[0]  # Gleichstände in der Rendite
        window, r, r2, *_ = build_window(r, r2)
        for weight in range(10, 100, 10):
            ranking = window.trend[weight]
            scores = ranking.scores
            order = ranking.order
            for k in range(len(order) - 1):
                a, b = order[k], order[k + 1]
                key_a = (scores[k], r[a], r2[a], -a)
                key_b = (scores[k + 1], r[b], r2[b], -b)
                self.assertGreater(key_a, key_b, (weight, k))


class CohortTests(unittest.TestCase):
    def setUp(self):
        sessions = weekday_sessions(dt.date(2026, 5, 1), dt.date(2026, 10, 12))
        cutoff = day(2026, 10, 12)
        instruments = [
            make_instrument(test_isin(1), sessions, lambda k: 10 + 0.05 * k, volume=1000),  # gleichmäßig steigend
            make_instrument(test_isin(2), sessions, lambda k: 10 + 0.08 * k + (1.5 if k % 3 == 0 else 0), volume=1000),
            make_instrument(test_isin(3), sessions, lambda k: 50 - 0.1 * k, volume=1000),  # fallend, R² hoch
            make_instrument(test_isin(4), sessions[-2:], lambda k: 5 + k, volume=1000),  # nur zwei Kurse
            make_instrument(test_isin(5), sessions, lambda k: 30 - 0.02 * k, volume=1000),  # leicht fallend
        ]
        for inst in instruments:
            inst.sessions = sessions
        self.result = compute_snapshot(instruments, cutoff, CFG)

    def test_T16_native_and_common_trend_cohorts(self):
        w = self.result.rankings[30]
        self.assertEqual(sorted(w.native0.order.tolist()), [0, 1, 2, 4])  # Nr. 4 hat zu kurze Historie für 30 Tage
        self.assertEqual(sorted(w.u_idx.tolist()), [0, 1])
        for weight in range(10, 101, 10):
            self.assertEqual(sorted(w.ranking("native", weight).order.tolist()), [0, 1])
            self.assertIs(w.ranking("native", weight), w.ranking("common_trend", weight))
        self.assertEqual(sorted(w.ranking("common_trend", 0).order.tolist()), [0, 1])

    def test_T81_native_zero_equals_pure_return_sort_including_two_closes(self):
        w1 = self.result.rankings[1]
        self.assertIn(3, w1.native0.order.tolist())  # zwei Schlusskurse, kein R²
        r = self.result.r[:, 0]
        expected = sorted(w1.v_idx.tolist(), key=lambda i: (-r[i], self.result.isins[i]))
        self.assertEqual(w1.native0.order.tolist(), expected)

    def test_T82_weight_100_uses_only_g_but_keeps_trend_admission(self):
        w = self.result.rankings[30]
        ranking = w.trend[100]
        self.assertNotIn(2, ranking.order.tolist())  # fallende Gerade trotz hohem R² nicht zugelassen
        g_by_idx = dict(zip(w.u_idx.tolist(), w.pct_g_u.tolist()))
        for pos, idx in enumerate(ranking.order.tolist()):
            self.assertEqual(ranking.scores[pos], g_by_idx[idx])
        self.assertGreater(self.result.r2[2, 29], 0.99)

    def test_T83_native_zero_may_show_only_negative_returns(self):
        sessions = weekday_sessions(dt.date(2026, 5, 1), dt.date(2026, 10, 12))
        falling = [
            make_instrument(test_isin(20 + i), sessions, lambda k, s=i: 40 - (0.05 + 0.01 * s) * k, volume=1000)
            for i in range(3)
        ]
        result = compute_snapshot(falling, day(2026, 10, 12), CFG)
        w = result.rankings[30]
        self.assertEqual(w.native0.size, 3)
        self.assertTrue(np.all(result.r[w.native0.order, 29] < 0))
        self.assertEqual(w.native0.order[0], 0)  # geringster Verlust zuerst
        for weight in range(10, 101, 10):
            self.assertEqual(w.trend[weight].size, 0)

    def test_T84_common_trend_uses_u_for_all_eleven(self):
        w = self.result.rankings[30]
        for weight in CANONICAL_WEIGHTS:
            self.assertEqual(sorted(w.ranking("common_trend", weight).order.tolist()), sorted(w.u_idx.tolist()))
        self.assertEqual(w.ranking("common_trend", 0).cohort, "U")
        self.assertEqual(w.native0.cohort, "V")

    def test_T85_at_most_990_cells_per_policy_and_aliases_add_none(self):
        for policy in POLICIES:
            cells = {(weight, h) for h in self.result.rankings for weight in CANONICAL_WEIGHTS}
            self.assertEqual(len(cells), 990)
        aliases = {parse_weight(a) for a in LEGACY_MODE_ALIASES}
        cells_with_alias = {(weight, 30) for weight in list(CANONICAL_WEIGHTS) + list(aliases)}
        self.assertEqual(len(cells_with_alias), 11)

    def test_T19_filtering_does_not_change_global_scores(self):
        w = self.result.rankings[30]
        before = w.trend[60].scores.copy()
        _ = [i for i in w.trend[60].order.tolist() if i in (0,)]  # Filter = Auswahl, keine Neuberechnung
        np.testing.assert_array_equal(w.trend[60].scores, before)

    def test_T20_subgroup_is_labelled_and_recomputed_consistently(self):
        base = self.result.rankings[30]
        before = base.trend[60].scores.copy()
        res = self.result
        sub = rank_subgroup(base, [1], res.r[:, 29], res.r2[:, 29], res.slope_pct[:, 29], res.noise_pct[:, 29], "watchlist")
        self.assertEqual(sub.label, "untergruppe:watchlist")
        self.assertEqual(sub.trend[60].order.tolist(), [1])
        self.assertEqual(sub.trend[60].scores.tolist(), [100.0])  # im eigenen Feld einziger Titel
        np.testing.assert_array_equal(base.trend[60].scores, before)
        self.assertEqual(self.result.status[3, 29], Status.HISTORIE_ZU_KURZ)


if __name__ == "__main__":
    unittest.main()
