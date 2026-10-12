"""T86–T98: Häufigkeiten, Renditesieger und Gesamtmaximum (synthetische Ranglisten)."""

from __future__ import annotations

import datetime as dt
import unittest

import numpy as np

from traktien.analytics.engine import compute_snapshot
from traktien.analytics.frequency import aggregate_frequency, build_pure_return_winners, overall_max_return
from traktien.analytics.ranking import rank_window
from traktien.config import CANONICAL_WEIGHTS, MethodConfig
from tests.helpers import day, make_instrument, test_isin, weekday_sessions

CFG = MethodConfig()
CUTOFF = 20000


def synthetic_windows(spec: dict[int, dict], n: int):
    """spec[h] = {"r": {idx: r}, "r2": {idx: r2}, "u": [idx…]}; nicht genannte Fenster sind leer."""
    windows = {}
    r_matrix = np.full((n, 90), np.nan)
    start = np.full((n, 90), -1, dtype=np.int64)
    for h in range(1, 91):
        entry = spec.get(h, {"r": {}, "r2": {}, "u": []})
        r_all = np.full(n, np.nan)
        r2_all = np.full(n, np.nan)
        for idx, value in entry["r"].items():
            r_all[idx] = value
            r_matrix[idx, h - 1] = value
            start[idx, h - 1] = CUTOFF - h - entry.get("shift", 0)
        for idx, value in entry["r2"].items():
            r2_all[idx] = value
        v = np.array(sorted(entry["r"]), dtype=np.int64)
        u = np.array(sorted(entry.get("u", [])), dtype=np.int64)
        windows[h] = rank_window(h, v, u, r_all, r2_all, np.ones(n), np.ones(n))
    return windows, r_matrix, start


def isin_of(idx: int) -> str:
    return f"ZZ{idx:010d}"


def run(windows, r_matrix, start, **kwargs):
    defaults = dict(policy="native", weights=CANONICAL_WEIGHTS, window_days=range(1, 91), top_k=10)
    defaults.update(kwargs)
    return aggregate_frequency(windows, r_matrix=r_matrix, start_matrix=start, cutoff_day=CUTOFF, isin_of=isin_of, **defaults)


class FrequencyCountingTests(unittest.TestCase):
    def test_T86_same_window_all_weights_counts_eleven_hits_one_window(self):
        spec = {30: {"r": {0: 0.5, 1: 0.1}, "r2": {0: 0.99, 1: 0.5}, "u": [0, 1]}}
        windows, r, start = synthetic_windows(spec, 2)
        result = run(windows, r, start)
        entry = next(e for e in result.entries if e.idx == 0)
        self.assertEqual(entry.n10, 11)
        self.assertEqual(entry.distinct_windows_k, 1)
        self.assertEqual(entry.distinct_weights_k, 11)
        self.assertEqual(result.valid_cells, 11)
        self.assertEqual(result.theoretical_cells, 990)

    def test_T87_eleven_windows_one_weight_counts_eleven_distinct_windows(self):
        spec = {h: {"r": {0: 0.3}, "r2": {0: 0.9}, "u": [0]} for h in range(20, 31)}
        windows, r, start = synthetic_windows(spec, 1)
        result = run(windows, r, start, weights=[60])
        entry = result.entries[0]
        self.assertEqual(entry.n10, 11)
        self.assertEqual(entry.distinct_windows_k, 11)
        self.assertEqual(result.mode, "single")

    def test_T88_repeated_aggregation_does_not_increase_counts(self):
        spec = {h: {"r": {0: 0.3, 1: 0.2}, "r2": {0: 0.9, 1: 0.8}, "u": [0, 1]} for h in range(1, 91)}
        windows, r, start = synthetic_windows(spec, 2)
        first = run(windows, r, start)
        second = run(windows, r, start)
        self.assertEqual([(e.idx, e.n1, e.n3, e.n10) for e in first.entries], [(e.idx, e.n1, e.n3, e.n10) for e in second.entries])

    def test_T88_duplicate_isin_listings_are_rejected_upstream(self):
        sessions = weekday_sessions(dt.date(2026, 7, 1), dt.date(2026, 10, 12))
        a = make_instrument(test_isin(1), sessions, lambda k: 10 + k)
        b = make_instrument(test_isin(1), sessions, lambda k: 10 + k)
        with self.assertRaises(ValueError):
            compute_snapshot([a, b], day(2026, 10, 12), CFG)

    def test_T89_empty_cells_and_unqualified_instruments(self):
        spec = {h: {"r": {0: 0.3}, "r2": {0: 0.9}, "u": [0]} for h in range(1, 46)}
        for h in range(46, 91):
            spec[h] = {"r": {0: 0.3, 1: -0.1}, "r2": {}, "u": []}
        windows, r, start = synthetic_windows(spec, 3)
        result = run(windows, r, start, weights=[60])
        self.assertEqual(result.valid_cells, 45)
        self.assertEqual(result.empty_cells, 45)
        all_weights = run(windows, r, start)
        entry1 = next(e for e in all_weights.entries if e.idx == 1)
        self.assertEqual(entry1.available_cells, 45)  # nur native 0/100-Zellen h=46…90
        self.assertFalse(any(e.idx == 2 for e in all_weights.entries))

    def test_T90_invariants_hold_on_random_data(self):
        rng = np.random.default_rng(99)  # SYNTHETISCH
        n = 40
        spec = {}
        for h in range(1, 91):
            members = sorted(rng.choice(n, size=int(rng.integers(0, n)), replace=False).tolist())
            r_map = {i: float(rng.normal(0.02, 0.1)) for i in members}
            u = [i for i in members if r_map[i] > 0 and rng.random() < 0.7]
            r2_map = {i: float(rng.uniform(0, 1)) for i in u}
            spec[h] = {"r": r_map, "r2": r2_map, "u": u}
        windows, r, start = synthetic_windows(spec, n)
        for policy in ("native", "common_trend"):
            for weights in ([60], list(CANONICAL_WEIGHTS)):
                for k in (1, 3, 10):
                    result = run(windows, r, start, policy=policy, weights=weights, top_k=k)
                    for e in result.entries:
                        self.assertLessEqual(e.n1, e.n3)
                        self.assertLessEqual(e.n3, e.n10)
                        self.assertLessEqual(e.n10, e.available_cells)
                        self.assertLessEqual(e.available_cells, result.valid_cells)
                        self.assertLessEqual(e.distinct_windows_k, 90)
                        self.assertLessEqual(e.distinct_weights_k, 11)
                        # T92: Nachzählen der Fundstellen
                        self.assertEqual(len(e.occurrences), e.n_k(k))
                        self.assertEqual(len({(o.h, o.weight) for o in e.occurrences}), e.n_k(k))
                        self.assertEqual(sum(e.hits_by_weight.values()), e.n_k(k))
                    self.assertLessEqual(result.valid_cells, 990)

    def test_T91_one_hit_with_full_share_does_not_outrank_frequent_titles(self):
        spec = {h: {"r": {0: 0.5, 1: 0.1}, "r2": {0: 0.9, 1: 0.1}, "u": [0, 1]} for h in range(1, 91)}
        spec[90] = {"r": {2: 0.9}, "r2": {2: 0.9}, "u": [2]}
        windows, r, start = synthetic_windows(spec, 3)
        result = run(windows, r, start, weights=[60], top_k=1)
        self.assertEqual(result.entries[0].idx, 0)
        e2 = next(e for e in result.entries if e.idx == 2)
        self.assertEqual((e2.n1, e2.available_cells), (1, 1))

    def test_T93_sorting_rules_per_top_k(self):
        # idx0: viele Top-10, wenig Platz 1; idx1: mehr Platz-1-Treffer
        spec = {}
        for h in range(1, 91):
            if h <= 10:
                spec[h] = {"r": {1: 0.9, 0: 0.5}, "r2": {1: 0.99, 0: 0.9}, "u": [0, 1]}
            else:
                spec[h] = {"r": {0: 0.5}, "r2": {0: 0.9}, "u": [0]}
        windows, r, start = synthetic_windows(spec, 2)
        top10 = run(windows, r, start, weights=[60], top_k=10)
        self.assertEqual([e.idx for e in top10.entries], [0, 1])
        top1 = run(windows, r, start, weights=[60], top_k=1)
        self.assertEqual(top1.entries[0].idx, 0)  # 80 Platz-1 gegenüber 10
        by_windows = run(windows, r, start, top_k=10, sort="distinct_windows")
        self.assertEqual(by_windows.entries[0].idx, 0)

    def test_T93_all_weights_tiebreak_uses_distinct_windows(self):
        # Beide: elf Top-10-Treffer; idx0 in einem Zeitraum über alle Gewichte, idx1 in elf Zeiträumen bei 60/40.
        spec = {30: {"r": {0: 0.9, 2: 0.1}, "r2": {0: 0.99, 2: 0.1}, "u": [0, 2]}}
        for h in range(40, 51):
            spec[h] = {"r": {1: 0.2}, "r2": {1: 0.5}, "u": [1]}
        windows, r, start = synthetic_windows(spec, 3)
        result = run(windows, r, start, policy="common_trend", top_k=10)
        e0 = next(e for e in result.entries if e.idx == 0)
        e1 = next(e for e in result.entries if e.idx == 1)
        self.assertEqual(e0.n10, 11)
        self.assertEqual(e1.n10, 121)
        result_one = run(windows, r, start, policy="common_trend", weights=[60], top_k=10)
        e1s = next(e for e in result_one.entries if e.idx == 1)
        self.assertEqual((e1s.n10, e1s.distinct_windows_k), (11, 11))

    def test_T98_small_fields_are_flagged(self):
        spec = {30: {"r": {0: 0.5, 1: 0.4}, "r2": {0: 0.9, 1: 0.8}, "u": [0, 1]}}
        windows, r, start = synthetic_windows(spec, 2)
        result = run(windows, r, start, weights=[60], top_k=10)
        for e in result.entries:
            for occ in e.occurrences:
                self.assertTrue(occ.small_field)
                self.assertEqual(occ.cohort_size, 2)

    def test_T96_new_snapshot_is_counted_alone(self):
        spec_a = {30: {"r": {0: 0.5}, "r2": {0: 0.9}, "u": [0]}}
        spec_b = {31: {"r": {1: 0.5}, "r2": {1: 0.9}, "u": [1]}}
        wa, ra, sa = synthetic_windows(spec_a, 2)
        wb, rb, sb = synthetic_windows(spec_b, 2)
        run(wa, ra, sa)
        result_b = run(wb, rb, sb)
        self.assertEqual([e.idx for e in result_b.entries], [1])
        self.assertEqual(result_b.entries[0].n10, 11)


class WinnerTests(unittest.TestCase):
    def test_T94_return_winners_have_exactly_90_rows(self):
        spec = {h: {"r": {0: 0.1 * h, 1: -0.2}, "r2": {}, "u": []} for h in range(1, 61)}
        windows, r, start = synthetic_windows(spec, 2)
        rows = build_pure_return_winners(windows, r_matrix=r, start_matrix=start, cutoff_day=CUTOFF)
        self.assertEqual(len(rows), 90)
        for row in rows:
            ranking = windows[row.h].native0
            if ranking.size:
                self.assertEqual(row.entries[0]["idx"], int(ranking.order[0]))
            else:
                self.assertEqual(row.empty_reason, "keine_vergleichbare_aktie")
                self.assertEqual(row.entries, [])

    def test_T94_ties_are_visible(self):
        spec = {5: {"r": {0: 0.25, 1: 0.25, 2: 0.1}, "r2": {}, "u": []}}
        windows, r, start = synthetic_windows(spec, 3)
        rows = build_pure_return_winners(windows, r_matrix=r, start_matrix=start, cutoff_day=CUTOFF)
        row = rows[4]
        self.assertTrue(row.tie)
        self.assertEqual([e["idx"] for e in row.entries], [0, 1])

    def test_T95_overall_maximum_names_isin_window_and_endpoints(self):
        spec = {h: {"r": {0: 0.01 * h, 1: 0.2}, "r2": {}, "u": []} for h in range(1, 91)}
        windows, r, start = synthetic_windows(spec, 2)
        rows = build_pure_return_winners(windows, r_matrix=r, start_matrix=start, cutoff_day=CUTOFF)
        best = overall_max_return(rows)
        self.assertEqual(best["entries"][0]["idx"], 0)
        self.assertEqual(best["entries"][0]["h"], 90)
        self.assertEqual(best["entries"][0]["start_day"], CUTOFF - 90)
        self.assertEqual(best["entries"][0]["end_day"], CUTOFF)
        self.assertFalse(best["tie"])
        self.assertEqual(best["pairs_evaluated"], 180)

    def test_T97_identical_effective_windows_counted_separately(self):
        sessions = weekday_sessions(dt.date(2026, 5, 1), dt.date(2026, 10, 12))
        cutoff = day(2026, 10, 12)  # Montag: h = 1, 2, 3 starten alle am Freitag
        inst = [make_instrument(test_isin(1), sessions, lambda k: 10 + 0.05 * k, volume=1000)]
        result = compute_snapshot(inst, cutoff, CFG)
        freq = aggregate_frequency(
            result.rankings, policy="native", weights=[0], window_days=[1, 2, 3], top_k=1,
            r_matrix=result.r, start_matrix=result.start_day, cutoff_day=cutoff, isin_of=result.isin_of,
        )
        entry = freq.entries[0]
        self.assertEqual(entry.n1, 3)
        self.assertEqual(entry.distinct_windows_k, 3)
        self.assertEqual(entry.distinct_effective_windows_k, 1)


if __name__ == "__main__":
    unittest.main()


class OverallMaximumDedupTests(unittest.TestCase):
    def test_same_stock_same_effective_window_is_not_a_tie(self):
        from traktien.analytics.frequency import WinnerRow, overall_max_return

        rows = [
            WinnerRow(h=h, cohort_size=5, entries=[{"idx": 3, "r": 0.5, "start_day": 100, "end_day": 130}], tie=False, empty_reason=None, all_negative=False)
            for h in (30, 31, 32)
        ]
        rows.append(WinnerRow(h=10, cohort_size=5, entries=[{"idx": 4, "r": 0.2, "start_day": 120, "end_day": 130}], tie=False, empty_reason=None, all_negative=False))
        result = overall_max_return(rows)
        self.assertFalse(result["tie"])
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(result["entries"][0]["h"], 30)
        self.assertEqual(result["entries"][0]["same_effective_h"], [31, 32])
        rows.append(WinnerRow(h=40, cohort_size=5, entries=[{"idx": 9, "r": 0.5, "start_day": 90, "end_day": 130}], tie=False, empty_reason=None, all_negative=False))
        self.assertTrue(overall_max_return(rows)["tie"], "verschiedene Aktien mit exakt gleichem Maximum")
