"""T03, T21–T25, T27, T28: Kalenderfenster und Stichtagslogik (synthetische Kalender)."""

from __future__ import annotations

import datetime as dt
import unittest

import numpy as np

from traktien.analytics.codes import Status
from traktien.analytics.engine import compute_snapshot
from traktien.analytics.windows import expected_start_sessions, resolve_window
from traktien.config import MethodConfig, parse_window_days
from tests.helpers import day, make_instrument, test_isin, weekday_sessions

CFG = MethodConfig()


class WindowParsingTests(unittest.TestCase):
    def test_T21_exactly_ninety_windows_and_invalid_rejected(self):
        self.assertEqual(list(CFG.windows()), list(range(1, 91)))
        self.assertEqual(len(CFG.windows()), 90)
        for bad in (0, 91, -1, 1.5, "1.5", "abc", True, None, "0", "91"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                parse_window_days(bad)
        for good, expected in ((1, 1), (90, 90), ("30", 30), (45.0, 45)):
            self.assertEqual(parse_window_days(good), expected)


class ResolveWindowTests(unittest.TestCase):
    def setUp(self):
        # Synthetischer Kalender Mo–Fr, Juli–Oktober 2026, Feiertag am 2026-08-17 (Montag).
        self.sessions = weekday_sessions(dt.date(2026, 6, 1), dt.date(2026, 10, 12), [dt.date(2026, 8, 17)])
        self.cutoff = day(2026, 10, 12)  # Montag

    def test_T22_weekend_target_start_uses_last_real_session_before(self):
        # h = 1: B = Sonntag 11.10. → letzte Sitzung Freitag 09.10.
        rw = resolve_window(self.sessions, self.sessions, self.cutoff, 1)
        self.assertTrue(rw.ok)
        self.assertEqual(rw.start_session, day(2026, 10, 9))
        self.assertEqual(rw.n_obs, 2)
        self.assertEqual(rw.n_expected, 2)
        # h = 2 und h = 3 enden ebenfalls am Freitag: gleiche Endpunkte sind korrekt.
        for h in (2, 3):
            self.assertEqual(resolve_window(self.sessions, self.sessions, self.cutoff, h).start_session, day(2026, 10, 9))
        self.assertEqual(resolve_window(self.sessions, self.sessions, self.cutoff, 4).start_session, day(2026, 10, 8))

    def test_T23_missing_expected_start_close_is_not_hidden(self):
        start = day(2026, 9, 11)  # Freitag; Ziel für h = 31 ist 11.09.
        obs = self.sessions[self.sessions != start]
        rw = resolve_window(obs, self.sessions, self.cutoff, 31)
        self.assertEqual(rw.status, Status.STARTKURS_FEHLT)
        self.assertEqual(rw.start_session, start)

    def test_T03_missing_end_close_gives_missing_value_with_reason(self):
        obs = self.sessions[self.sessions != self.cutoff]
        rw = resolve_window(obs, self.sessions, self.cutoff, 30)
        self.assertEqual(rw.status, Status.KURS_AM_STICHTAG_FEHLT)

    def test_T27_market_holiday_differs_from_missing_provider_data(self):
        holiday_sessions = self.sessions[self.sessions != self.cutoff]
        obs = holiday_sessions
        rw = resolve_window(obs, holiday_sessions, self.cutoff, 30)
        self.assertEqual(rw.status, Status.MARKT_AM_STICHTAG_GESCHLOSSEN)
        rw_missing = resolve_window(obs, self.sessions, self.cutoff, 30)
        self.assertEqual(rw_missing.status, Status.KURS_AM_STICHTAG_FEHLT)

    def test_history_too_short(self):
        obs = self.sessions[self.sessions >= day(2026, 9, 1)]
        self.assertEqual(resolve_window(obs, self.sessions, self.cutoff, 60).status, Status.HISTORIE_ZU_KURZ)
        self.assertTrue(resolve_window(obs, self.sessions, self.cutoff, 30).ok)

    def test_no_start_session_within_seven_days(self):
        # Langer Börsenstillstand: keine Sitzungen 2026-09-01 … 2026-09-14.
        gap = self.sessions[(self.sessions < day(2026, 9, 1)) | (self.sessions > day(2026, 9, 14))]
        rw = resolve_window(gap, gap, self.cutoff, 30)  # B = 12.09.
        self.assertEqual(rw.status, Status.KEINE_STARTSITZUNG)

    def test_expected_start_sessions_helper(self):
        starts = expected_start_sessions(self.sessions, self.cutoff, range(1, 91))
        self.assertEqual(len(starts), 90)
        self.assertEqual(starts[0], day(2026, 10, 9))


class CalendarDifferenceTests(unittest.TestCase):
    def test_T25_different_national_holidays_are_handled_per_market(self):
        start, end = dt.date(2026, 6, 1), dt.date(2026, 10, 12)
        us = weekday_sessions(start, end, [dt.date(2026, 7, 3), dt.date(2026, 9, 7)])  # US: 3.7. (Ersatz), Labor Day
        de = weekday_sessions(start, end, [dt.date(2026, 10, 3)])  # Samstag – kein Effekt
        cutoff = day(2026, 10, 12)
        rw_us = resolve_window(us, us, cutoff, 38)  # B = 04.09. Freitag
        rw_de = resolve_window(de, de, cutoff, 38)
        self.assertEqual(rw_us.start_session, day(2026, 9, 4))
        self.assertEqual(rw_de.start_session, day(2026, 9, 4))
        self.assertEqual(rw_de.n_expected - rw_us.n_expected, 1)  # Labor Day fehlt nur in den USA
        # Sommerzeitwechsel ändern Sitzungsdaten nicht: es wird mit Kalenderdaten gerechnet.
        self.assertEqual(rw_us.n_obs, rw_us.n_expected)


class StrictCutoffTests(unittest.TestCase):
    def test_T28_older_end_date_never_enters_strict_ranking(self):
        sessions = weekday_sessions(dt.date(2026, 6, 1), dt.date(2026, 10, 12))
        cutoff = day(2026, 10, 12)
        fresh = make_instrument(test_isin(1), sessions, lambda k: 100 + k, volume=1000)
        stale_days = sessions[sessions < cutoff]
        stale = make_instrument(test_isin(2), stale_days, lambda k: 50 + k, volume=1000)
        stale.sessions = sessions
        result = compute_snapshot([fresh, stale], cutoff, CFG)
        col = 29  # h = 30
        self.assertEqual(result.status[1, col], Status.KURS_AM_STICHTAG_FEHLT)
        self.assertNotIn(1, result.rankings[30].native0.order.tolist())
        self.assertEqual(result.rankings[30].native0.order.tolist(), [0])

    def test_T24_thirty_calendar_days_with_fewer_than_15_observations_has_no_trend(self):
        # Börse mit nur drei Sitzungen pro Woche (synthetisch): 30 Kalendertage < 15 Beobachtungen.
        all_days = weekday_sessions(dt.date(2026, 6, 1), dt.date(2026, 10, 12))
        sessions = np.array([d for d in all_days if (d - 4) % 7 in (0, 2, 4)], dtype=np.int64)
        cutoff = int(sessions[-1])
        inst = make_instrument(test_isin(3), sessions, lambda k: 10 + 0.1 * k, volume=500)
        result = compute_snapshot([inst], cutoff, CFG)
        col = 29
        self.assertLess(int(result.n_obs[0, col]), 15)
        self.assertEqual(result.status[0, col], Status.ZU_WENIG_TAGESDATEN_TREND)
        self.assertTrue(np.isnan(result.r2[0, col]))
        self.assertTrue(np.isfinite(result.r[0, col]))
        self.assertEqual(result.rankings[30].trend[60].size, 0)
        self.assertEqual(result.rankings[30].native0.size, 1)


if __name__ == "__main__":
    unittest.main()
