"""Zwischenstand (ab 1.8): Wahl des Stichtags, begonnene Sitzungen, Umsatz ohne den laufenden Tag – SYNTHETISCHE Daten."""

from __future__ import annotations

import datetime as dt
import unittest

import numpy as np

from traktien.analytics.codes import RETURN_PUBLISHABLE
from traktien.analytics.engine import InstrumentData, compute_snapshot
from traktien.config import load_method_config
from traktien.jobs.intraday import ProvisionalBar, choose_day, started_sessions
from traktien.jobs.state import is_intraday_archive
from traktien.providers.base import LiveQuote
from traktien.providers.calendars import StaticCalendarProvider, weekday_holiday_sessions
from traktien.util.timeutil import UTC, date_to_day

D13 = date_to_day(dt.date(2026, 10, 13))
D12 = date_to_day(dt.date(2026, 10, 12))
D9 = date_to_day(dt.date(2026, 10, 9))


def calendars() -> StaticCalendarProvider:
    sessions = {code: weekday_holiday_sessions(dt.date(2026, 6, 1), dt.date(2026, 12, 31), set()) for code in ("XETR", "XNYS", "XTKS")}
    closes = {"XETR": ("Europe/Berlin", dt.time(17, 30)), "XNYS": ("America/New_York", dt.time(16, 0)), "XTKS": ("Asia/Tokyo", dt.time(15, 30))}
    opens = {"XETR": dt.time(9, 0), "XNYS": dt.time(9, 30), "XTKS": dt.time(9, 0)}
    return StaticCalendarProvider(sessions, closes, opens=opens)


def quote(symbol: str, day: int, price: float = 10.0) -> LiveQuote:
    return LiveQuote(symbol, price, dt.datetime(2026, 10, 13, 10, 15, tzinfo=UTC), day, 1000.0, price, "EUR", "Europe/Berlin")


class StartedSessionTests(unittest.TestCase):
    def test_only_sessions_that_have_opened_count(self):
        cal = calendars()
        noon_berlin = dt.datetime(2026, 10, 13, 10, 30, tzinfo=UTC)  # 12:30 Uhr Berlin
        started = started_sessions(cal, {"XETR", "XNYS", "XTKS"}, noon_berlin, D12)
        self.assertEqual(started, {"XETR": [D13], "XTKS": [D13]}, "New York öffnet erst um 15:30 Uhr Berlin")
        evening = dt.datetime(2026, 10, 13, 14, 0, tzinfo=UTC)  # 16:00 Uhr Berlin
        self.assertIn("XNYS", started_sessions(cal, {"XNYS"}, evening, D12))
        self.assertEqual(started_sessions(cal, {"XETR"}, noon_berlin, D13), {}, "nichts nach dem offiziellen Stand begonnen")

    def test_opening_times_of_the_static_calendar(self):
        cal = calendars()
        self.assertEqual(cal.session_open_utc("XETR", D13), dt.datetime(2026, 10, 13, 7, 0, tzinfo=UTC))
        self.assertEqual(cal.session_open_utc("XNYS", D13), dt.datetime(2026, 10, 13, 13, 30, tzinfo=UTC))
        self.assertIsNone(cal.session_open_utc("XETR", date_to_day(dt.date(2026, 10, 17))), "Samstag")


class ChooseDayTests(unittest.TestCase):
    def listings(self, n_eur: int, n_us: int) -> dict[str, dict]:
        out = {}
        for k in range(n_eur):
            out[f"DE{k:010d}"] = {"calendar_code": "XETR", "provider_symbol": f"E{k}.DE"}
        for k in range(n_us):
            out[f"US{k:010d}"] = {"calendar_code": "XNYS", "provider_symbol": f"U{k}"}
        return out

    def test_today_when_enough_stocks_have_traded(self):
        listings = self.listings(30, 70)
        quotes = {l["provider_symbol"]: quote(l["provider_symbol"], D13 if l["calendar_code"] == "XETR" else D12) for l in listings.values()}
        stored = {isin: D12 for isin in listings}
        started = {"XETR": [D13]}
        choice = choose_day(listings, quotes, started, stored, calendars(), min_share=0.2)
        self.assertEqual(choice.day, D13)
        self.assertEqual(choice.candidates[0]["erwartet"], 30, "nur Aktien, deren Börse heute schon begonnen hat")
        self.assertEqual(choice.candidates[0]["mit_kurs"], 30)

    def test_too_few_quotes_or_gap_in_history(self):
        listings = self.listings(30, 0)
        quotes = {l["provider_symbol"]: quote(l["provider_symbol"], D13) for k, l in enumerate(listings.values()) if k < 5}
        stored = {isin: D12 for isin in listings}
        choice = choose_day(listings, quotes, {"XETR": [D13]}, stored, calendars(), min_share=0.2)
        self.assertIsNone(choice.day, "5 von 30 Aktien reichen nicht")
        all_quotes = {l["provider_symbol"]: quote(l["provider_symbol"], D13) for l in listings.values()}
        behind = {isin: D9 for isin in listings}  # Schlusskurs vom 12.10. fehlt in der gespeicherten Historie
        choice = choose_day(listings, all_quotes, {"XETR": [D13]}, behind, calendars(), min_share=0.2)
        self.assertIsNone(choice.day, "ohne den Schlusskurs der Vorsitzung kein Zwischenstand – zuerst der tägliche Lauf")
        self.assertEqual(choice.candidates[0]["mit_kurs"], 0)


class EngineTests(unittest.TestCase):
    def test_provisional_day_counts_for_return_but_not_for_turnover(self):
        cfg = load_method_config()
        sessions = weekday_holiday_sessions(dt.date(2026, 5, 1), dt.date(2026, 10, 13), set())
        n = len(sessions)
        rng = np.random.default_rng(3)
        close = 50 * np.exp(np.cumsum(rng.normal(0.001, 0.01, n)))
        volume = np.full(n, 100_000.0)
        volume[-1] = 2_000.0  # laufender Tag: erst ein Teil des Umsatzes
        base = dict(sessions=sessions, days=sessions, close=close, volume=volume, currency="USD", unit_factor=1.0)
        provisional = compute_snapshot([InstrumentData(isin="US0000000001", provisional_day=int(sessions[-1]), **base)], int(sessions[-1]), cfg)
        final = compute_snapshot([InstrumentData(isin="US0000000001", **base)], int(sessions[-1]), cfg)
        t_prov, t_final = provisional.turnover[0], final.turnover[0]
        self.assertEqual(t_prov.last_day, int(sessions[-2]), "Ø Tagesumsatz ohne den laufenden Tag")
        self.assertEqual(t_final.last_day, int(sessions[-1]))
        self.assertGreater(t_prov.avg_usd, t_final.avg_usd)
        col = 29
        self.assertEqual(provisional.r[0, col], final.r[0, col], "Rendite mit dem vorläufigen Kurs wie mit einem Schlusskurs")
        self.assertIn(int(provisional.status[0, col]), {int(x) for x in RETURN_PUBLISHABLE}, "Kursrendite veröffentlicht")
        self.assertNotEqual(provisional.input_hash, final.input_hash, "vorläufig ist ein anderer Datenstand")


class SmallTests(unittest.TestCase):
    def test_provisional_bar_fills_every_bar_column(self):
        bar = ProvisionalBar(day=D13, close=12.5, volume=300.0, time_utc="2026-10-13T10:15:00Z", session_closed=False)
        self.assertEqual(bar.value("days"), D13)
        self.assertEqual(bar.value("close"), 12.5)
        self.assertTrue(np.isnan(bar.value("open")))
        self.assertEqual(bar.value("quality"), 0)

    def test_intraday_archive_names(self):
        self.assertTrue(is_intraday_archive("site-2026-10-13_z1030ab12cd.tar"))
        self.assertFalse(is_intraday_archive("site-2026-10-12_c3806c24.tar"))
        self.assertFalse(is_intraday_archive("signale-20261014T061500Z.tar"))


if __name__ == "__main__":
    unittest.main()
