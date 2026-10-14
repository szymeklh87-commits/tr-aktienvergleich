"""Zwischenstand (ab 1.8): Wahl des Stichtags, begonnene Sitzungen, Umsatz ohne den laufenden Tag – SYNTHETISCHE Daten."""

from __future__ import annotations

import datetime as dt
import unittest

import numpy as np

from traktien.analytics.codes import RETURN_PUBLISHABLE, Status
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

    def test_own_cutoff_counts_with_the_previous_close(self):
        """Ab 1.13 (Simons Wahl 15:20 Uhr): Eine Aktie, deren Börse heute noch nicht geöffnet hat, zählt im
        Zwischenstand mit dem Schlusskurs des Handelstags davor – ihre Fenster enden dort. Ergebnis Zahl für Zahl
        wie eine Rechnung mit diesem Tag als Stichtag; ohne eigenen Stichtag fehlte sie („Kurs am Stichtag fehlt“)."""
        cfg = load_method_config()
        sessions = weekday_holiday_sessions(dt.date(2026, 5, 1), dt.date(2026, 10, 13), set())
        today, yesterday = int(sessions[-1]), int(sessions[-2])
        rng = np.random.default_rng(7)

        def series(seed_shift: float, n: int) -> dict:
            close = 20 * np.exp(np.cumsum(rng.normal(0.002 + seed_shift, 0.012, n)))
            return dict(sessions=sessions, days=sessions[:n], close=close, volume=np.full(n, 50_000.0), currency="USD", unit_factor=1.0)

        de = series(0.0, len(sessions))  # Kurs von heute (vorläufig)
        us = series(0.001, len(sessions) - 1)  # New York noch geschlossen: letzter Kurs gestern
        both = compute_snapshot(
            [
                InstrumentData(isin="DE0000000001", provisional_day=today, **de),
                InstrumentData(isin="US0000000001", cutoff_day=yesterday, **us),
            ],
            today,
            cfg,
        )
        alone = compute_snapshot([InstrumentData(isin="US0000000001", **us)], yesterday, cfg)
        for name in ("status", "r", "p0", "p1", "start_day", "n_obs", "n_exp", "r2", "m"):
            np.testing.assert_array_equal(getattr(both, name)[1], getattr(alone, name)[0], err_msg=name)
        self.assertEqual(int(both.end_day[0]), today)
        self.assertEqual(int(both.end_day[1]), yesterday)
        col = 29
        self.assertIn(int(both.status[1, col]), {int(x) for x in RETURN_PUBLISHABLE}, "US-Aktie in der Rangliste")
        self.assertIn(1, both.rankings[30].native0.order.tolist())
        ends = {e["idx"]: e["end_day"] for row in both.winners for e in row.entries}
        self.assertTrue(all(day == (yesterday if idx == 1 else today) for idx, day in ends.items()), "Spitzenreiter mit eigenem Endtag")
        # Ohne eigenen Stichtag fehlt sie – so war es bis 1.12
        without = compute_snapshot(
            [InstrumentData(isin="DE0000000001", provisional_day=today, **de), InstrumentData(isin="US0000000001", **us)], today, cfg
        )
        self.assertNotIn(int(without.status[1, col]), {int(x) for x in RETURN_PUBLISHABLE})
        self.assertNotEqual(without.input_hash, both.input_hash)
        # Ohne Überschreibung bleibt der Prüfwert wie bisher (offizieller Stand unverändert)
        plain = compute_snapshot([InstrumentData(isin="US0000000001", **us)], yesterday, cfg)
        self.assertEqual(plain.input_hash, alone.input_hash)


class LastCloseRuleTests(unittest.TestCase):
    """tr-methode-1.9.0 (Simons Wunsch vom 14.10.2026: „Alle Aktien sollen bewertet werden“): Ohne Schlusskurs am Stichtag
    zählt der letzte Schlusskurs – höchstens eine verpasste Börsensitzung, Feiertage zählen nicht."""

    def setUp(self):
        self.sessions = weekday_holiday_sessions(dt.date(2026, 9, 1), dt.date(2026, 10, 13), set())
        self.D = date_to_day(dt.date(2026, 10, 13))

    def bars(self, last: dt.date):
        days = self.sessions[self.sessions <= date_to_day(last)]
        return days, np.linspace(10, 12, len(days))

    def test_close_on_the_cutoff_day_needs_no_own_cutoff(self):
        from traktien.jobs.daily import own_cutoff_day

        days, close = self.bars(dt.date(2026, 10, 13))
        self.assertIsNone(own_cutoff_day(days, close, self.sessions, self.D, 1))

    def test_missing_close_today_counts_with_yesterday(self):
        from traktien.jobs.daily import own_cutoff_day

        days, close = self.bars(dt.date(2026, 10, 12))
        self.assertEqual(own_cutoff_day(days, close, self.sessions, self.D, 1), D12, "„dann nimm von gestern“")
        self.assertIsNone(own_cutoff_day(days, close, self.sessions, self.D, 0), "Regel abschaltbar")

    def test_two_missed_sessions_are_stale(self):
        from traktien.jobs.daily import own_cutoff_day

        days, close = self.bars(dt.date(2026, 10, 9))  # Freitag: Montag und Dienstag ohne Kurs
        self.assertIsNone(own_cutoff_day(days, close, self.sessions, self.D, 1))

    def test_holiday_of_the_exchange_counts_with_the_last_session(self):
        from traktien.jobs.daily import own_cutoff_day

        holiday = weekday_holiday_sessions(dt.date(2026, 9, 1), dt.date(2026, 10, 13), {dt.date(2026, 10, 12), dt.date(2026, 10, 13)})
        days = holiday[holiday <= D9]
        close = np.linspace(10, 12, len(days))
        self.assertEqual(own_cutoff_day(days, close, holiday, self.D, 1), D9, "Montag und Dienstag Feiertag: keine verpasste Sitzung")

    def test_invalid_closes_and_bars_outside_sessions_do_not_count(self):
        from traktien.jobs.daily import own_cutoff_day

        days, close = self.bars(dt.date(2026, 10, 12))
        close = close.copy()
        close[-1] = np.nan  # 12.10. ungültig → letzter gültiger Kurs am 9.10., zwei verpasste Sitzungen
        self.assertIsNone(own_cutoff_day(days, close, self.sessions, self.D, 1))
        saturday = date_to_day(dt.date(2026, 10, 10))
        days2 = np.append(self.sessions[self.sessions <= D9], saturday)
        close2 = np.linspace(10, 12, len(days2))
        self.assertIsNone(own_cutoff_day(days2, close2, self.sessions, self.D, 1), "Kurs am Samstag ist keine Sitzung")
        self.assertIsNone(own_cutoff_day(np.array([], dtype=np.int64), np.array([]), self.sessions, self.D, 1))

    def test_method_comparison_shows_the_newly_rated_pairs(self):
        """Methodenvergleich 1.8.0 → 1.9.0: Aktien mit eigenem Stichtag zählen nach den alten Regeln als „Kurs am Stichtag
        fehlt“ (Börse offen) bzw. „Markt am Stichtag geschlossen“ (Feiertag) – so sieht man, was die Regel hinzunimmt."""
        cfg = load_method_config()
        self.assertEqual((cfg.method_version, cfg.previous_method_version, cfg.last_close_max_missed_sessions), ("tr-methode-1.9.0", "tr-methode-1.8.0", 1))
        sessions = weekday_holiday_sessions(dt.date(2026, 5, 1), dt.date(2026, 10, 13), set())
        holiday = weekday_holiday_sessions(dt.date(2026, 5, 1), dt.date(2026, 10, 13), {dt.date(2026, 10, 13)})
        rng = np.random.default_rng(5)

        def inst(isin, cal, upto):
            days = cal[cal <= upto]
            close = 30 * np.exp(np.cumsum(rng.normal(0.002, 0.01, len(days))))
            return InstrumentData(isin=isin, sessions=cal, days=days, close=close, volume=np.full(len(days), 1e5), currency="USD", unit_factor=1.0)

        today = int(sessions[-1])
        full = inst("DE0000000001", sessions, today)
        missing = inst("DE0000000002", sessions, int(sessions[-2]))
        missing.cutoff_day = int(sessions[-2])
        closed = inst("JP0000000003", holiday, int(holiday[-1]))
        closed.cutoff_day = int(holiday[-1])
        comp = compute_snapshot([full, missing, closed], today, cfg)
        col = 29
        for i in (0, 1, 2):
            self.assertIn(int(comp.status[i, col]), {int(x) for x in RETURN_PUBLISHABLE}, f"Aktie {i} bewertet")
        self.assertEqual(int(comp.previous_status[1, col]), int(Status.KURS_AM_STICHTAG_FEHLT))
        self.assertEqual(int(comp.previous_status[2, col]), int(Status.MARKT_AM_STICHTAG_GESCHLOSSEN))
        self.assertEqual(int(comp.previous_status[0, col]), int(comp.status[0, col]), "unverändert für Aktien mit Kurs am Stichtag")
        cmp = comp.method_comparison
        self.assertEqual((cmp["vorher"], cmp["jetzt"]), ("tr-methode-1.8.0", "tr-methode-1.9.0"))
        self.assertEqual(cmp["paare"]["nicht_mehr_bewertet"], 0)
        added = cmp["paare"]["hinzugekommen_aus_status"]
        self.assertEqual(set(added), {str(int(Status.KURS_AM_STICHTAG_FEHLT)), str(int(Status.MARKT_AM_STICHTAG_GESCHLOSSEN))})
        self.assertEqual(sum(added.values()), cmp["paare"]["neu_bewertet"])


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
