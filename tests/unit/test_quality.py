"""T04, T06, T08, T09, T29–T35: Zulassungsregeln und Datenprüfungen (synthetische Daten)."""

from __future__ import annotations

import datetime as dt
import unittest

import numpy as np

from traktien.analytics.codes import InstrumentWarning, Status, WindowWarning
from traktien.analytics.engine import compute_snapshot
from traktien.analytics.metrics import calculate_price_metrics
from traktien.analytics.quality import SplitEvent, classify_window, detect_jumps, detect_unadjusted_splits
from traktien.analytics.windows import ResolvedWindow
from traktien.config import MethodConfig
from tests.helpers import day, make_instrument, test_isin, weekday_sessions

CFG = MethodConfig()
SESSIONS = weekday_sessions(dt.date(2026, 5, 1), dt.date(2026, 10, 12))
CUTOFF = day(2026, 10, 12)


def col(h: int) -> int:
    return h - 1


class EligibilityTests(unittest.TestCase):
    def test_T04_two_rising_closes_give_return_but_no_trend_score(self):
        inst = make_instrument(test_isin(1), SESSIONS, lambda k: 100 + k, volume=1000)
        result = compute_snapshot([inst], CUTOFF, CFG)
        self.assertEqual(int(result.n_obs[0, col(1)]), 2)
        self.assertEqual(result.status[0, col(1)], Status.ZU_WENIG_TAGESDATEN_TREND)
        self.assertGreater(result.r[0, col(1)], 0)
        ranking = result.rankings[1]
        self.assertEqual(ranking.native0.order.tolist(), [0])
        for weight in range(10, 101, 10):
            self.assertEqual(ranking.trend[weight].size, 0)

    def test_T06_exact_falling_line_is_excluded_from_up_and_mixed_rankings(self):
        falling = make_instrument(test_isin(2), SESSIONS, lambda k: 500.0 - 2.0 * k, volume=1000)
        rising = make_instrument(test_isin(3), SESSIONS, lambda k: 100.0 + 0.5 * k, volume=1000)
        result = compute_snapshot([falling, rising], CUTOFF, CFG)
        self.assertGreater(result.r2[0, col(30)], 0.999, "rechnerisch fast perfekte Gerade")
        self.assertEqual(result.status[0, col(30)], Status.NICHT_STEIGEND)
        ranking = result.rankings[30]
        for weight in range(10, 101, 10):
            self.assertEqual(ranking.trend[weight].order.tolist(), [1], f"Gewichtung {weight}: nur die steigende Aktie")
        self.assertEqual(ranking.native0.order.tolist(), [1, 0], "reine Renditeliste (0/100) zeigt auch den Verlust, hinten")

    def test_T08_positive_return_with_negative_slope_is_not_trend_eligible(self):
        prices = [100.0 - 1.2 * i for i in range(19)] + [101.0]
        metrics = calculate_price_metrics(np.array(prices))
        self.assertGreater(metrics.r, 0)
        self.assertLess(metrics.m, 0)
        rw = ResolvedWindow(30, 0, None, 0, 0, 19, 20, 20)
        status = classify_window(rw, vol_positive=20, held_in_window=False, metrics=metrics, cfg=CFG)
        self.assertEqual(status, Status.NICHT_STEIGEND)

    def test_T09_positive_slope_with_negative_return_is_not_trend_eligible(self):
        prices = [100.0 + 3.0 * i for i in range(19)] + [99.0]
        metrics = calculate_price_metrics(np.array(prices))
        self.assertLess(metrics.r, 0)
        self.assertGreater(metrics.m, 0)
        rw = ResolvedWindow(30, 0, None, 0, 0, 19, 20, 20)
        self.assertEqual(
            classify_window(rw, vol_positive=20, held_in_window=False, metrics=metrics, cfg=CFG), Status.NICHT_STEIGEND
        )


class ThresholdTests(unittest.TestCase):
    def _rw(self, n_obs: int, n_exp: int) -> ResolvedWindow:
        return ResolvedWindow(30, 0, None, 0, 0, n_obs - 1, n_obs, n_exp)

    def test_T29_session_coverage_98_percent_checked_exactly(self):
        metrics = calculate_price_metrics(np.linspace(10, 20, 98))
        self.assertNotEqual(
            classify_window(self._rw(98, 100), vol_positive=98, held_in_window=False, metrics=metrics, cfg=CFG),
            Status.SITZUNGSABDECKUNG_ZU_GERING,
        )
        metrics97 = calculate_price_metrics(np.linspace(10, 20, 97))
        self.assertEqual(
            classify_window(self._rw(97, 100), vol_positive=97, held_in_window=False, metrics=metrics97, cfg=CFG),
            Status.SITZUNGSABDECKUNG_ZU_GERING,
        )
        metrics49 = calculate_price_metrics(np.linspace(10, 20, 49))
        self.assertEqual(
            classify_window(self._rw(49, 50), vol_positive=49, held_in_window=False, metrics=metrics49, cfg=CFG),
            Status.TREND_BEWERTBAR,
        )
        metrics60 = calculate_price_metrics(np.linspace(10, 20, 60))
        self.assertEqual(
            classify_window(self._rw(60, 62), vol_positive=60, held_in_window=False, metrics=metrics60, cfg=CFG),
            Status.SITZUNGSABDECKUNG_ZU_GERING,
        )

    def test_T29_volume_coverage_80_percent_checked_exactly(self):
        metrics = calculate_price_metrics(np.linspace(10, 20, 15))
        self.assertEqual(
            classify_window(self._rw(15, 15), vol_positive=12, held_in_window=False, metrics=metrics, cfg=CFG),
            Status.TREND_BEWERTBAR,
        )
        self.assertEqual(
            classify_window(self._rw(15, 15), vol_positive=11, held_in_window=False, metrics=metrics, cfg=CFG),
            Status.VOLUMEN_UNZUREICHEND,
        )

    def test_T30_unknown_volume_is_neither_zero_nor_positive(self):
        unknown = make_instrument(test_isin(2), SESSIONS, lambda k: 50 + 0.2 * k, volume=None)
        zero = make_instrument(test_isin(3), SESSIONS, lambda k: 50 + 0.2 * k, volume=0.0)
        result = compute_snapshot([unknown, zero], CUTOFF, CFG)
        self.assertEqual(result.status[0, col(30)], Status.VOLUMEN_UNZUREICHEND)
        self.assertEqual(result.status[1, col(30)], Status.VOLUMEN_UNZUREICHEND)
        self.assertTrue(result.warnings[0] & (1 << InstrumentWarning.VOLUMEN_OFT_UNBEKANNT))
        self.assertFalse(result.warnings[0] & (1 << InstrumentWarning.WENIGE_AKTIVE_HANDELSTAGE))
        self.assertTrue(result.warnings[1] & (1 << InstrumentWarning.WENIGE_AKTIVE_HANDELSTAGE))
        self.assertFalse(result.warnings[1] & (1 << InstrumentWarning.VOLUMEN_OFT_UNBEKANNT))
        self.assertEqual(result.vol_cov[0, col(30)], 0.0)

    def test_T31_no_monetary_minimum_removes_small_stocks(self):
        tiny = make_instrument(test_isin(4), SESSIONS, lambda k: 0.0012 + 0.00001 * k, volume=3.0)
        result = compute_snapshot([tiny], CUTOFF, CFG)
        self.assertEqual(result.status[0, col(30)], Status.TREND_BEWERTBAR)
        self.assertEqual(result.rankings[30].native0.order.tolist(), [0])


class CorporateActionTests(unittest.TestCase):
    def test_T32_split_adjusted_flat_position_has_no_artificial_gain(self):
        split_day = day(2026, 9, 15)
        inst = make_instrument(
            test_isin(5), SESSIONS, lambda k: 50.0 + (0.01 if k % 2 else 0.0), volume=1000,
            splits=[SplitEvent(split_day, 2.0)],
        )
        result = compute_snapshot([inst], CUTOFF, CFG)
        self.assertLess(abs(result.r[0, col(60)]), 0.001)
        self.assertNotEqual(result.status[0, col(60)], Status.KURSSPRUNG_PRUEFEN)
        self.assertTrue(result.wflags[0, col(60)] & (1 << WindowWarning.SPLIT_IM_FENSTER))

    def test_T32_unadjusted_two_for_one_split_is_held(self):
        split_day = day(2026, 9, 15)
        price = lambda k, d=SESSIONS: 100.0 if d[k] < split_day else 50.0  # noqa: E731
        inst = make_instrument(test_isin(6), SESSIONS, price, volume=1000, splits=[SplitEvent(split_day, 2.0)])
        result = compute_snapshot([inst], CUTOFF, CFG)
        self.assertEqual(result.status[0, col(60)], Status.KURSSPRUNG_PRUEFEN)
        self.assertNotIn(0, result.rankings[60].native0.order.tolist())
        # Fenster nach dem Ex-Datum bleiben unberührt.
        self.assertNotEqual(result.status[0, col(10)], Status.KURSSPRUNG_PRUEFEN)

    def test_T33_reverse_split_and_unit_change_create_no_fake_return(self):
        event = day(2026, 9, 15)
        reverse_unadjusted = lambda k, d=SESSIONS: 1.0 if d[k] < event else 10.0  # noqa: E731
        gbp_unit_error = lambda k, d=SESSIONS: 5.0 if d[k] == event else 500.0 + 0.1 * k  # noqa: E731
        a = make_instrument(test_isin(7), SESSIONS, reverse_unadjusted, volume=1000, splits=[SplitEvent(event, 0.1)])
        b = make_instrument(test_isin(8), SESSIONS, gbp_unit_error, volume=1000)
        result = compute_snapshot([a, b], CUTOFF, CFG)
        for i in (0, 1):
            self.assertEqual(result.status[i, col(60)], Status.KURSSPRUNG_PRUEFEN)
            self.assertNotIn(i, result.rankings[60].native0.order.tolist())
        # Splitbereinigte Zusammenlegung (gleichmäßige Reihe) bleibt zulässig.
        adjusted = make_instrument(test_isin(9), SESSIONS, lambda k: 10.0 + 0.01 * k, volume=1000, splits=[SplitEvent(event, 0.1)])
        self.assertEqual(compute_snapshot([adjusted], CUTOFF, CFG).status[0, col(60)], Status.TREND_BEWERTBAR)

    def test_T35_reviewed_extreme_jump_and_unclear_error_get_different_status(self):
        jump_day = day(2026, 9, 21)
        price = lambda k, d=SESSIONS: 10.0 + 0.01 * k if d[k] < jump_day else 40.0 + 0.01 * k  # noqa: E731
        unclear = make_instrument(test_isin(10), SESSIONS, price, volume=1000)
        reviewed = make_instrument(test_isin(11), SESSIONS, price, volume=1000, reviewed_jumps={jump_day: "freigegeben"})
        result = compute_snapshot([unclear, reviewed], CUTOFF, CFG)
        self.assertEqual(result.status[0, col(30)], Status.KURSSPRUNG_PRUEFEN)
        self.assertIn(result.status[1, col(30)], (Status.TREND_BEWERTBAR, Status.NICHT_STEIGEND))
        self.assertTrue(result.wflags[1, col(30)] & (1 << WindowWarning.GEPRUEFTER_SPRUNG_IM_FENSTER))
        self.assertTrue(result.warnings[1] & (1 << InstrumentWarning.GEPRUEFTER_KURSSPRUNG))

    def test_jump_and_split_detectors(self):
        days = np.arange(10, dtype=np.int64)
        close = np.array([10, 10, 10, 31, 31, 31, 10, 10, 10, 10], dtype=float)
        self.assertEqual(detect_jumps(days, close, 3.0), [3, 6])
        adjusted = np.full(10, 10.0)
        self.assertEqual(detect_unadjusted_splits(days, adjusted, [SplitEvent(5, 2.0)]), [])
        unadjusted = np.array([10] * 5 + [5] * 5, dtype=float)
        self.assertEqual(detect_unadjusted_splits(days, unadjusted, [SplitEvent(5, 2.0)]), [5])

    def test_bars_on_non_session_days_are_discarded(self):
        weekend = day(2026, 10, 10)  # Samstag
        inst = make_instrument(test_isin(12), SESSIONS, lambda k: 20 + 0.1 * k, volume=1000)
        insert_at = int(np.searchsorted(inst.days, weekend))
        inst.days = np.insert(inst.days, insert_at, weekend)
        inst.close = np.insert(inst.close, insert_at, 999.0)
        inst.volume = np.insert(inst.volume, insert_at, 0.0)
        result = compute_snapshot([inst], CUTOFF, CFG)
        self.assertTrue(result.warnings[0] & (1 << InstrumentWarning.BARS_AN_NICHTHANDELSTAGEN))
        self.assertEqual(result.status[0, col(30)], Status.TREND_BEWERTBAR)


if __name__ == "__main__":
    unittest.main()


class ReviewFindingTests(unittest.TestCase):
    """Nachträge aus der unabhängigen Prüfung (Abschnitte 8, 9, 12, 34.6)."""

    def test_zero_volume_outlier_at_end_never_becomes_top_winner(self):
        flat = make_instrument(test_isin(1), SESSIONS, lambda k: 2.0, volume=500)
        n = len(flat.days)
        flat.close[-1] = 4.9  # +145 % am Stichtag – ohne Umsatz
        flat.volume[-1] = 0.0
        normal = make_instrument(test_isin(2), SESSIONS, lambda k: 100 + 0.1 * k, volume=1000)
        result = compute_snapshot([flat, normal], CUTOFF, CFG)
        self.assertTrue(np.all(result.status[0, :] == Status.KURSSPRUNG_PRUEFEN), "alle Fenster bis zur Prüfung zurückgehalten")
        self.assertTrue(result.warnings[0] & (1 << InstrumentWarning.NULLUMSATZ_AUSREISSER))
        for h in (1, 6, 30, 90):
            self.assertEqual(result.rankings[h].native0.order.tolist(), [1], f"h={h}: nur die geprüfte Aktie")
        self.assertEqual(result.overall_max["entries"][0]["idx"], 1)
        released = make_instrument(test_isin(1), SESSIONS, lambda k: 2.0, volume=500, reviewed_jumps={int(flat.days[-1]): "freigegeben"})
        released.close[-1] = 4.9
        released.volume[-1] = 0.0
        result = compute_snapshot([released, normal], CUTOFF, CFG)
        self.assertNotEqual(result.status[0, 0], Status.KURSSPRUNG_PRUEFEN, "nach dokumentierter Prüfung freigegeben")
        self.assertEqual(n, len(released.days))

    def test_zero_volume_dip_at_window_start_holds_only_that_window(self):
        prices = lambda k: 100.0 + 0.2 * k
        inst = make_instrument(test_isin(3), SESSIONS, prices, volume=1000)
        start_30 = int(np.searchsorted(inst.days, CUTOFF - 30, side="right")) - 1
        inst.close[start_30] = 60.0  # Taxe ohne Umsatz am Beginn des 30-Tage-Fensters
        inst.volume[start_30] = np.nan
        result = compute_snapshot([inst], CUTOFF, CFG)
        self.assertEqual(result.status[0, col(30)], Status.KURSSPRUNG_PRUEFEN)
        self.assertEqual(result.status[0, col(25)], Status.TREND_BEWERTBAR)

    def test_small_moves_without_volume_are_only_counted_for_coverage(self):
        inst = make_instrument(test_isin(4), SESSIONS, lambda k: 100.0 + 0.05 * k, volume=1000)
        inst.volume[-1] = 0.0  # ruhiger Tag ohne Umsatz, Kurs kaum verändert
        result = compute_snapshot([inst], CUTOFF, CFG)
        self.assertEqual(result.status[0, col(30)], Status.TREND_BEWERTBAR)

    def test_near_flat_series_do_not_abort_the_run(self):
        rng = np.random.default_rng(7)
        for base in (100.0, 1e5):
            for _ in range(300):
                steps = rng.uniform(3e-9, 1e-8) * rng.choice([-1.0, 1.0], size=40)
                prices = base * np.cumprod(1.0 + steps)
                calculate_price_metrics(prices)  # streng: darf mit zentrierten Residuen nicht mehr auslösen
        forced = calculate_price_metrics(np.linspace(10, 20, 30), r2_bound_tolerance=-1.0, strict=False)
        self.assertIsNone(forced.r2)
        self.assertFalse(forced.r2_defined)
        with self.assertRaises(ArithmeticError):
            calculate_price_metrics(np.linspace(10, 20, 30), r2_bound_tolerance=-1.0)

    def test_window_lengths_above_90_are_rejected_in_core(self):
        from traktien.analytics.windows import resolve_window

        with self.assertRaises(ValueError):
            resolve_window(np.array([CUTOFF]), SESSIONS, CUTOFF, 91)
        with self.assertRaises(ValueError):
            resolve_window(np.array([CUTOFF]), SESSIONS, CUTOFF, 0)
