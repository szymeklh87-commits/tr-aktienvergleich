"""T12–T20, T80–T85: Perzentile, elf Gewichtungen, Vergleichsmengen (synthetische Daten)."""

from __future__ import annotations

import datetime as dt
import math
import unittest

import numpy as np

from traktien.analytics.codes import Status
from traktien.analytics.engine import compute_snapshot
from traktien.analytics.ranking import group_b_ranking, percentile_average_rank, pure_return_subset, rank_subgroup, rank_window, weighted_score
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


class TieRuleTests(unittest.TestCase):
    """ranking-11w-v3 (ab tr-methode-1.10.0): Score (exakt verglichen), dann Kursrendite, dann ISIN. Referenzfälle mit
    unabhängiger Nachrechnung in test_referenz_gleichstand.py."""

    def test_full_order_score_then_return_then_isin_for_all_weights(self):
        # Aktie 0 und 1: gleiches R² (100/0 gleichauf) – die höhere Rendite (1) steht vorn,
        # obwohl Aktie 0 die steilere Gerade und weniger Rauschen hat (alte Regel v1: 0 vorn)
        window, *_ = build_window(r=[0.10, 0.20, 0.05], r2=[0.9, 0.9, 0.5], slope=[2.0, 1.0, 1.0], noise=[0.1, 0.5, 0.5])
        self.assertEqual(window.trend[100].order.tolist(), [1, 0, 2])
        self.assertEqual(window.trend[100].tie_positions.tolist(), [0, 1], "gleicher Score bleibt als gleichauf markiert")
        legacy = rank_window(30, np.arange(3), np.arange(3), np.array([0.10, 0.20, 0.05]), np.array([0.9, 0.9, 0.5]), np.array([2.0, 1.0, 1.0]), np.array([0.1, 0.5, 0.5]), tie_rule="v1")
        self.assertEqual(legacy.trend[100].order.tolist(), [0, 1, 2])

    def test_equal_score_and_return_fall_back_to_isin_not_r2(self):
        # 50/50: Aktie 0 (R-Perzentil 100, G-Perzentil 0) und Aktie 1 (R 0, G 100) → beide Score 50;
        # Aktie 2 dazwischen. Gleiche Rendite für 0 und 3 erzwingt den ISIN-Entscheid.
        r = np.array([0.30, 0.10, 0.20, 0.30])
        r2 = np.array([0.50, 0.95, 0.70, 0.60])
        window = rank_window(30, np.arange(4), np.arange(4), r, r2, np.ones(4), np.ones(4))
        scores = dict(zip(window.trend[50].order.tolist(), window.trend[50].scores.tolist()))
        order = window.trend[50].order.tolist()
        for a, b in zip(order, order[1:]):
            key_a = (-scores[a], -r[a], a)
            key_b = (-scores[b], -r[b], b)
            self.assertLess(key_a, key_b, f"{a} vor {b}")

    def test_unknown_tie_rule_is_rejected(self):
        with self.assertRaises(ValueError):
            rank_window(1, np.arange(1), np.arange(1), np.ones(1), np.ones(1), np.ones(1), np.ones(1), tie_rule="v9")


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

    def test_T17_exact_scores_decide_order(self):
        """ranking-11w-v3 (ab tr-methode-1.10.0): der Score exakt als Bruch aus den Rängen, dann die Rendite, dann die ISIN –
        weder ein gerundeter noch der Gleitkomma-Score. Dieser darf nur innerhalb rechnerisch gleicher Scores in den letzten
        Stellen „falsch herum“ stehen."""
        from fractions import Fraction

        rng = np.random.default_rng(7)  # SYNTHETISCH
        n = 400
        r = rng.normal(0.05, 0.03, n)
        r2 = rng.uniform(0.2, 0.99, n)
        r2[::7] = r2[0]  # Gleichstände im R²
        r[::11] = r[0]  # Gleichstände in der Rendite
        window, r, r2, *_ = build_window(r, r2)
        m = len(window.u_idx)
        pos = {int(i): k for k, i in enumerate(window.u_idx.tolist())}

        def pct(doubled: int) -> Fraction:
            return Fraction(100 * (int(doubled) - 2), 2 * (m - 1))

        flipped = 0
        for weight in range(10, 100, 10):
            ranking = window.trend[weight]
            exact = {i: Fraction(weight, 100) * pct(window.ar2_g_u[k]) + Fraction(100 - weight, 100) * pct(window.ar2_r_u[k]) for i, k in pos.items()}
            order = ranking.order.tolist()
            for a, b in zip(order, order[1:]):
                self.assertGreater((exact[a], r[a], -a), (exact[b], r[b], -b), (weight, a, b))
            for k in range(len(order) - 1):
                if ranking.scores[k] < ranking.scores[k + 1]:
                    flipped += 1
                    self.assertEqual(exact[order[k]], exact[order[k + 1]], "nur bei rechnerisch gleichem Score")
                    self.assertLess(ranking.scores[k + 1] - ranking.scores[k], 1e-9)
        self.assertGreater(flipped, 0, "die Daten enthalten rechnerisch gleiche Scores mit verschiedenen Gleitkommawerten")


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



class GroupBTests(unittest.TestCase):
    """Gruppe B (ab 1.4): eigene Vergleichsmenge V ∩ L bzw. U ∩ L mit eigenen Perzentilen."""

    def setUp(self):
        # 6 Aktien; 0, 2, 3, 5 sind liquide (L). U = {0, 1, 2, 3, 4}; 5 nur in V (nicht gleichmäßig gestiegen)
        self.r = [0.30, 0.50, 0.10, 0.20, 0.40, 0.60]
        self.r2 = [0.70, 0.90, 0.95, 0.60, 0.80, 0.10]
        self.window, *_ = build_window(self.r, self.r2, u=[0, 1, 2, 3, 4])
        self.liquid = np.array([True, False, True, True, False, True])
        self.b = group_b_ranking(self.window, self.liquid, np.array(self.r), np.array(self.r2), np.ones(6), np.ones(6))

    def test_comparison_sets_are_intersections_with_l(self):
        self.assertEqual(self.b.v_idx.tolist(), [0, 2, 3, 5])
        self.assertEqual(self.b.u_idx.tolist(), [0, 2, 3])
        self.assertEqual(self.b.label, "gruppe_b")
        self.assertEqual(self.window.trend[60].size, 5, "Gruppe A bleibt unverändert")

    def test_percentiles_are_recomputed_inside_the_group(self):
        # Rendite in U ∩ L: 0.30 (Aktie 0), 0.10 (2), 0.20 (3) → Perzentile 100, 0, 50
        order0 = self.b.trend[0].order.tolist()
        self.assertEqual(order0, [0, 3, 2])
        np.testing.assert_allclose(self.b.trend[0].scores, [100.0, 50.0, 0.0])
        # R² in U ∩ L: 0.70 (0), 0.95 (2), 0.60 (3) → 50, 100, 0
        self.assertEqual(self.b.trend[100].order.tolist(), [2, 0, 3])
        np.testing.assert_allclose(self.b.trend[100].scores, [100.0, 50.0, 0.0])
        # 60/40: Aktie 0: 0,6·50 + 0,4·100 = 70; Aktie 2: 0,6·100 + 0,4·0 = 60; Aktie 3: 0,6·0 + 0,4·50 = 20
        np.testing.assert_allclose(self.b.trend[60].scores, [70.0, 60.0, 20.0])
        self.assertEqual(self.b.trend[60].order.tolist(), [0, 2, 3])

    def test_pure_return_and_pure_smoothness_keep_group_a_order(self):
        for w in (0, 100):
            expected = [i for i in self.window.trend[w].order.tolist() if self.liquid[i]]
            self.assertEqual(self.b.trend[w].order.tolist(), expected, w)
        ranking2 = pure_return_subset(self.window.native0, self.liquid, np.array(self.r))
        self.assertEqual(self.b.native0.order.tolist(), ranking2.order.tolist())
        np.testing.assert_allclose(self.b.native0.scores, ranking2.scores)

    def test_mixed_weights_may_order_differently_than_filtering_group_a(self):
        # In Gruppe A (U = 0…4) liegt bei 60/40 Aktie 2 vor Aktie 0 – in Gruppe B umgekehrt,
        # weil die Perzentile innerhalb der Gruppe neu berechnet werden (dokumentierte Vergleichsmenge).
        a_order = [i for i in self.window.trend[60].order.tolist() if self.liquid[i]]
        self.assertEqual(a_order, [2, 0, 3])
        self.assertEqual(self.b.trend[60].order.tolist(), [0, 2, 3])

    def test_empty_group_has_empty_rankings(self):
        none = group_b_ranking(self.window, np.zeros(6, dtype=bool), np.array(self.r), np.array(self.r2), np.ones(6), np.ones(6))
        self.assertEqual(none.native0.size, 0)
        self.assertTrue(all(none.trend[w].size == 0 for w in CANONICAL_WEIGHTS))


if __name__ == "__main__":
    unittest.main()
