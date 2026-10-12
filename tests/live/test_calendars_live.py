"""Börsenkalender-Anbindung (exchange_calendars) gegen bekannte Feiertage und Schlusszeiten.

Benötigt das Paket ``exchange_calendars`` (in GitHub Actions über backend/requirements.txt
installiert). Kein Netzwerkzugriff nötig. In einer Umgebung ohne das Paket übersprungen.
"""

from __future__ import annotations

import datetime as dt
import unittest

from traktien.jobs.cutoff import determine_cutoff
from traktien.providers.exchanges import load_exchange_table
from traktien.util.timeutil import date_to_day

try:
    from traktien.providers.calendars import ExchangeCalendarsProvider

    PROVIDER = ExchangeCalendarsProvider()
except ImportError:  # pragma: no cover - Umgebung ohne exchange_calendars
    PROVIDER = None

UTC = dt.timezone.utc


def day(text: str) -> int:
    return date_to_day(dt.date.fromisoformat(text))


@unittest.skipIf(PROVIDER is None, "exchange_calendars nicht installiert")
class ExchangeCalendarsLiveTest(unittest.TestCase):
    def test_every_configured_calendar_exists(self) -> None:
        table = load_exchange_table()
        missing = sorted({e.calendar for e in table.exchanges.values() if not PROVIDER.available(e.calendar)})
        self.assertEqual(missing, [], "Kalender in config/boersen.yaml ohne exchange_calendars-Entsprechung")

    def test_known_holidays_are_not_sessions(self) -> None:
        cases = {
            "XETR": ["2026-12-24", "2026-12-25", "2026-12-31"],
            "XNYS": ["2026-11-26", "2026-12-25"],
            "XTKS": ["2026-10-12"],
            "XLON": ["2026-12-25", "2026-12-28"],
            "XHKG": ["2026-12-25"],
        }
        for code, dates in cases.items():
            for text in dates:
                self.assertIsNone(PROVIDER.session_close_utc(code, day(text)), f"{code} {text} sollte geschlossen sein")
        for code in cases:
            sessions = PROVIDER.sessions(code, day("2026-09-01"), day("2026-10-31"))
            self.assertGreater(len(sessions), 35, code)
            self.assertTrue(all(b > a for a, b in zip(sessions, sessions[1:])), "aufsteigend und eindeutig")

    def test_close_times_in_utc(self) -> None:
        self.assertEqual(PROVIDER.session_close_utc("XETR", day("2026-10-12")), dt.datetime(2026, 10, 12, 15, 30, tzinfo=UTC))
        self.assertEqual(PROVIDER.session_close_utc("XETR", day("2026-11-09")), dt.datetime(2026, 11, 9, 16, 30, tzinfo=UTC))
        self.assertEqual(PROVIDER.session_close_utc("XNYS", day("2026-10-12")), dt.datetime(2026, 10, 12, 20, 0, tzinfo=UTC))
        self.assertEqual(PROVIDER.session_close_utc("XNYS", day("2026-11-27")), dt.datetime(2026, 11, 27, 18, 0, tzinfo=UTC), "verkürzter Handel nach Thanksgiving")

    def test_cutoff_at_six_berlin_is_previous_trading_day(self) -> None:
        codes = {"XETR", "XNYS", "XLON", "XTKS", "XHKG", "XASX"}
        # Dienstag, 13.10.2026, 06:00 Berlin = 04:00 UTC: Tokio handelt bereits, Montag ist überall abgeschlossen.
        result = determine_cutoff(codes, PROVIDER, dt.datetime(2026, 10, 13, 4, 0, tzinfo=UTC))
        self.assertEqual(result.cutoff_day, day("2026-10-12"))
        self.assertNotIn("XTKS", result.markets_with_session, "Tokio hatte am 12.10.2026 Feiertag")
        self.assertIn("XTKS", result.markets_closed)
        # Samstag früh: Stichtag ist der Freitag
        result = determine_cutoff(codes, PROVIDER, dt.datetime(2026, 10, 17, 4, 0, tzinfo=UTC))
        self.assertEqual(result.cutoff_day, day("2026-10-16"))


if __name__ == "__main__":
    unittest.main()
