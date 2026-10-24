"""Unabhängige Referenzfälle der Rechnung (ab 1.17; Simons Auftrag vom 24.10.2026: „Sichere die aktuelle Berechnung
zusätzlich durch unabhängige Referenzfälle ab“).

Jeder Fall nennt seine Eingaben und das von Hand bzw. mit exakten Brüchen (``fractions.Fraction``) ermittelte
Ergebnis – unabhängig vom Rechenkern. Erst danach wird der Rechenkern (``traktien.analytics``) damit verglichen.
Die Fälle decken die Regeln aus docs/03_Methodik.md ab: Kursrendite, R² auf dem Preis gegen den Beobachtungsindex,
größter Rückgang, Kalenderzeiträume mit Wochenende, Feiertag und fehlendem Kurs, Perzentile mit Gleichstand,
Gewichtung, eigener Endtag bei fehlendem Schlusskurs und Ø Tagesumsatz. SYNTHETISCHE Zahlen.
"""

from __future__ import annotations

import datetime as dt
import math
import unittest
from fractions import Fraction

import numpy as np

from traktien.analytics.codes import Status
from traktien.analytics.metrics import calculate_price_metrics
from traktien.analytics.ranking import average_ranks_doubled, percentile_average_rank, weighted_score
from traktien.analytics.turnover import compute_turnover
from traktien.analytics.windows import resolve_window
from traktien.jobs.daily import own_cutoff_day
from traktien.util.timeutil import date_to_day


def d(day: int, month: int = 10) -> int:
    return date_to_day(dt.date(2026, month, day))


def exact_r2(prices: list[Fraction]) -> Fraction:
    """R² der Geraden durch (i, p_i) als exakter Bruch: (Σ(t−t̄)(p−p̄))² / (Σ(t−t̄)² · Σ(p−p̄)²)."""
    n = len(prices)
    t_mean = Fraction(n - 1, 2)
    p_mean = sum(prices, Fraction(0)) / n
    s_tp = sum((Fraction(i) - t_mean) * (p - p_mean) for i, p in enumerate(prices))
    s_tt = sum((Fraction(i) - t_mean) ** 2 for i in range(n))
    s_pp = sum((p - p_mean) ** 2 for p in prices)
    return s_tp * s_tp / (s_tt * s_pp)


# Sitzungen Oktober 2026 (Mo–Fr), Feiertag am Mittwoch, 21.10. (nur in den Fällen, die ihn brauchen)
WEEKDAYS = np.array([d(x) for x in (1, 2, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23)], dtype=np.int64)
WITH_HOLIDAY = WEEKDAYS[WEEKDAYS != d(21)]


class ReturnAndSteadinessReference(unittest.TestCase):
    def test_return_from_first_and_last_price(self):
        # Start 50, Ende 55: (55 − 50) / 50 = +10 %
        m = calculate_price_metrics(np.array([50.0, 52.0, 55.0]), min_obs_trend=2)
        self.assertAlmostEqual(m.r, 0.10, places=15)
        # Start 80, Ende 60: −25 %
        self.assertAlmostEqual(calculate_price_metrics(np.array([80.0, 70.0, 60.0]), min_obs_trend=2).r, -0.25, places=15)

    def test_r2_of_a_straight_line_is_one(self):
        prices = [10.0 + i for i in range(15)]
        m = calculate_price_metrics(np.array(prices))
        self.assertEqual(m.r2, 1.0)
        # Steigung 1 je Beobachtung, Mittel 17 → relative Steigung 100 · 1 / 17 %
        self.assertAlmostEqual(m.slope_pct, 100.0 / 17.0, places=12)

    def test_r2_matches_exact_fraction(self):
        prices = [Fraction(v) for v in (100, 103, 101, 106, 104, 108, 107, 111, 109, 114, 112, 115, 118, 116, 120)]
        expected = exact_r2(prices)
        m = calculate_price_metrics(np.array([float(p) for p in prices]))
        self.assertAlmostEqual(m.r2, float(expected), places=12)
        # gleichmäßiger Anstieg mit kleinen Rücksetzern: hoher, aber nicht perfekter Wert
        self.assertGreater(float(expected), 0.9)
        self.assertLess(float(expected), 1.0)

    def test_r2_is_about_steadiness_not_direction(self):
        # gleichmäßig fallend: R² ebenso hoch wie steigend – die Rendite zeigt die Richtung
        rising = calculate_price_metrics(np.array([10.0 + i for i in range(15)]))
        falling = calculate_price_metrics(np.array([24.0 - i for i in range(15)]))
        self.assertEqual(rising.r2, falling.r2)
        self.assertGreater(rising.r, 0)
        self.assertLess(falling.r, 0)

    def test_r2_needs_15_observations_and_a_moving_price(self):
        self.assertIsNone(calculate_price_metrics(np.array([10.0 + i for i in range(14)])).r2)
        self.assertIsNone(calculate_price_metrics(np.full(20, 12.5)).r2, "konstanter Kurs: R² nicht definiert")

    def test_largest_drop_and_up_days(self):
        # Höchststand 120, danach 90: Rückgang 25 %; Anstiege: 100→120, 90→110 = 2
        m = calculate_price_metrics(np.array([100.0, 120.0, 90.0, 110.0]), min_obs_trend=2)
        self.assertAlmostEqual(m.mdd, 0.25, places=15)
        self.assertEqual(m.ups, 2)


class CalendarWindowReference(unittest.TestCase):
    def test_one_day_ends_today_and_starts_yesterday(self):
        w = resolve_window(WEEKDAYS, WEEKDAYS, d(23), 1)
        self.assertTrue(w.ok)
        self.assertEqual((w.start_session, w.n_obs, w.n_expected), (d(22), 2, 2))

    def test_weekend_start_falls_back_to_friday(self):
        # Stichtag Montag 19.10., 2 Kalendertage → Ziel Samstag 17.10. → letzte Sitzung davor: Freitag 16.10.
        cutoff = d(19)
        obs = WEEKDAYS[WEEKDAYS <= cutoff]
        w = resolve_window(obs, WEEKDAYS, cutoff, 2)
        self.assertEqual((w.start_session, w.n_obs), (d(16), 2))

    def test_holiday_in_the_window_counts_as_no_session(self):
        # 7 Tage bis Freitag 23.10. → Start Freitag 16.10.; Feiertag 21.10. ist keine Sitzung (5 statt 6 erwartete Kurse)
        obs = WITH_HOLIDAY
        w = resolve_window(obs, WITH_HOLIDAY, d(23), 7)
        self.assertEqual((w.start_session, w.n_obs, w.n_expected), (d(16), 5, 5))

    def test_missing_start_price_is_not_replaced_by_an_older_one(self):
        obs = WEEKDAYS[WEEKDAYS != d(16)]
        w = resolve_window(obs, WEEKDAYS, d(23), 7)
        self.assertEqual(w.status, Status.STARTKURS_FEHLT)

    def test_missing_price_on_the_cutoff_and_closed_market(self):
        self.assertEqual(resolve_window(WEEKDAYS[:-1], WEEKDAYS, d(23), 5).status, Status.KURS_AM_STICHTAG_FEHLT)
        self.assertEqual(resolve_window(WITH_HOLIDAY[WITH_HOLIDAY <= d(20)], WITH_HOLIDAY, d(21), 1).status, Status.MARKT_AM_STICHTAG_GESCHLOSSEN)

    def test_own_end_day_with_last_close_at_most_one_missed_session(self):
        # Kurs am Stichtag 23.10. fehlt, letzter Kurs 22.10., Börse hatte seitdem 1 Sitzung → eigener Endtag 22.10.
        days = WEEKDAYS[WEEKDAYS <= d(22)]
        close = np.linspace(10, 12, len(days))
        self.assertEqual(own_cutoff_day(days, close, WEEKDAYS, d(23), 1), d(22))
        # letzter Kurs 21.10., seitdem 2 Sitzungen → zu alt, die Aktie fehlt
        days2 = WEEKDAYS[WEEKDAYS <= d(21)]
        self.assertIsNone(own_cutoff_day(days2, np.linspace(10, 12, len(days2)), WEEKDAYS, d(23), 1))
        # Kurs am Stichtag vorhanden → kein eigener Endtag
        self.assertIsNone(own_cutoff_day(WEEKDAYS, np.linspace(10, 12, len(WEEKDAYS)), WEEKDAYS, d(23), 1))


class RankingReference(unittest.TestCase):
    def test_percentiles_with_a_tie(self):
        # Werte 3, 1, 2, 2 → Ränge 4, 1, 2,5, 2,5 → P = 100 · (Rang − 1) / 3 = 100, 0, 50, 50
        values = np.array([3.0, 1.0, 2.0, 2.0])
        self.assertEqual(average_ranks_doubled(values).tolist(), [8, 2, 5, 5])
        self.assertEqual(percentile_average_rank(values).tolist(), [100.0, 0.0, 50.0, 50.0])

    def test_help_example_three_stocks_at_60_40(self):
        # Hilfe „So liest du eine Rangliste“: A +12 %, R² 0,95 · B +25 %, R² 0,40 · C +5 %, R² 0,80
        r = percentile_average_rank(np.array([0.12, 0.25, 0.05]))
        g = percentile_average_rank(np.array([0.95, 0.40, 0.80]))
        self.assertEqual(r.tolist(), [50.0, 100.0, 0.0])
        self.assertEqual(g.tolist(), [100.0, 0.0, 50.0])
        scores = weighted_score(60, g, r)
        self.assertEqual([round(x, 9) for x in scores.tolist()], [80.0, 40.0, 30.0])
        # nur Kursrendite: B vorn; nur Gleichmäßigkeit: A vorn
        self.assertEqual(int(np.argmax(weighted_score(0, g, r))), 1)
        self.assertEqual(int(np.argmax(weighted_score(100, g, r))), 0)

    def test_weighting_formula(self):
        # Score(60/40) = 0,6 · 50 + 0,4 · 90 = 66; 50/50 = 70
        self.assertAlmostEqual(float(weighted_score(60, np.array([50.0]), np.array([90.0]))[0]), 66.0, places=12)
        self.assertAlmostEqual(float(weighted_score(50, np.array([50.0]), np.array([90.0]))[0]), 70.0, places=12)
        with self.assertRaises(ValueError):
            weighted_score(65, np.array([50.0]), np.array([90.0]))


class TurnoverReference(unittest.TestCase):
    def sessions(self):
        start = date_to_day(dt.date(2026, 9, 1))
        days = [start + k for k in range(60) if dt.date.fromordinal(dt.date(1970, 1, 1).toordinal() + start + k).weekday() < 5]
        return np.array(days, dtype=np.int64)

    def test_average_over_20_sessions_in_main_currency(self):
        sessions = self.sessions()
        cutoff = int(sessions[-1])
        last20 = sessions[-20:]
        close = np.full(len(last20), 250.0)  # 250 Pence = 2,50 GBP
        volume = np.array([1000.0] * 10 + [3000.0] * 10)
        # 2,50 GBP × (1000 bzw. 3000) → Ø (2500 + 7500) / 2 = 5000 GBP
        result = compute_turnover(last20, close, volume, sessions, cutoff, split_days=np.array([], dtype=np.int64), currency="GBP", unit_factor=0.01, fx=None)
        self.assertAlmostEqual(result.avg_local, 5000.0, places=9)
        # ohne Wechselkurs keine Angabe in USD – die Aktie fehlt dann in Gruppe B, nicht in Gruppe A
        self.assertEqual(result.status, "wechselkurs_fehlt")
        self.assertIsNone(result.avg_usd)
        self.assertEqual((result.sessions, result.with_data, result.positive), (20, 20, 20))

    def test_missing_volume_does_not_count_as_zero_and_split_blocks(self):
        sessions = self.sessions()
        cutoff = int(sessions[-1])
        last20 = sessions[-20:]
        close = np.full(20, 10.0)
        volume = np.full(20, 100.0)
        volume[0] = np.nan  # nicht gemeldet: zählt nicht (kein Nullersatz)
        result = compute_turnover(last20, close, volume, sessions, cutoff, split_days=np.array([], dtype=np.int64), currency="USD", unit_factor=1.0, fx=None)
        self.assertEqual((result.with_data, result.positive), (19, 19))
        self.assertAlmostEqual(result.avg_usd, 1000.0, places=9)
        blocked = compute_turnover(last20, close, volume, sessions, cutoff, split_days=np.array([int(last20[5])]), currency="USD", unit_factor=1.0, fx=None)
        self.assertEqual(blocked.status, "kapitalmassnahme")
        too_few = volume.copy()
        too_few[:5] = 0.0  # gemeldete 0 zählt mit 0, aber nur 15 Tage mit Umsatz < 16
        self.assertEqual(compute_turnover(last20, close, too_few, sessions, cutoff, split_days=np.array([], dtype=np.int64), currency="USD", unit_factor=1.0, fx=None).status, "zu_wenig_umsatztage")


if __name__ == "__main__":
    unittest.main()
