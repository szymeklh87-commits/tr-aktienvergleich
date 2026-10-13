"""Ø Tagesumsatz, indikative USD-Umrechnung und die zwei Rendite-Ranglisten (Erweiterung 1.1).

Abnahmeprüfungen der Erweiterung:
* Höchste Rendite bei niedrigem Umsatz → nur Ranking 1.
* Ausreichend gehandelte Aktie → in beiden Rankings.
* Fehlende Volumendaten → keine Aufnahme in Ranking 2.
* Wochenenden und Feiertage verschieben Start- und Umsatzsitzungen korrekt.
* Beide Rankings: derselbe Kursstichtag, dieselbe Renditeformel, dieselben Werte.

Alle Daten sind synthetisch (Test-ISINs mit Präfix ZZ).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import unittest

import numpy as np

from traktien.analytics.codes import InstrumentWarning, WindowWarning
from traktien.analytics.engine import compute_snapshot
from traktien.analytics.fx import FxRates
from traktien.analytics.metrics import takeover_pattern
from traktien.analytics.turnover import TURNOVER_STATUS, compute_turnover
from traktien.config import MethodConfig
from traktien.util.timeutil import date_to_day
from tests.helpers import day, make_instrument, test_isin, weekday_sessions

D = day(2026, 10, 12)  # Montag
HOLIDAY = dt.date(2026, 10, 9)  # synthetischer Feiertag (Freitag) im Testkalender
SESSIONS = weekday_sessions(dt.date(2026, 5, 1), dt.date(2026, 10, 12), holidays=[HOLIDAY])


def fx_rates(max_age: int = 5) -> FxRates:
    """Synthetische Referenzkurse je EUR für alle Kalendertage mit Werktag (wie EZB: ohne Wochenende)."""
    rows = []
    current = dt.date(2026, 4, 1)
    while current <= dt.date(2026, 10, 12):
        if current.weekday() < 5:
            d = date_to_day(current)
            rows += [(d, "USD", 1.10), (d, "GBP", 0.85), (d, "JPY", 160.0)]
        current += dt.timedelta(days=1)
    return FxRates.from_rows(rows, source="TEST", url=None, fetched_at=None, max_age_days=max_age)


def growth(total: float, n: int):
    """Preisfunktion: von 100 gleichmäßig auf 100 · (1 + total) über n Sitzungen."""
    rate = (1 + total) ** (1 / max(n - 1, 1))
    return lambda k: 100 * rate**k


class TurnoverDefinitionTests(unittest.TestCase):
    def series(self, n: int = 40, price: float = 50.0, volume: float = 300_000.0):
        days = SESSIONS[-n:]
        return days, np.full(n, price), np.full(n, volume)

    def test_mean_of_close_times_volume_over_last_20_sessions(self) -> None:
        days, close, volume = self.series()
        result = compute_turnover(days, close, volume, SESSIONS, D, split_days=np.empty(0), currency="USD", unit_factor=1.0, fx=fx_rates())
        self.assertEqual(result.status, "ok")
        self.assertEqual((result.sessions, result.with_data, result.positive), (20, 20, 20))
        self.assertEqual(result.avg_usd, 50.0 * 300_000.0)
        self.assertEqual(result.last_day, D)
        # Feiertag 09.10. und Wochenenden liegen nicht unter den 20 Sitzungen
        self.assertEqual(result.first_day, int(SESSIONS[-20]))
        self.assertNotIn(date_to_day(HOLIDAY), SESSIONS[-20:].tolist())

    def test_missing_sessions_are_not_counted_as_zero(self) -> None:
        days, close, volume = self.series()
        volume = volume.copy()
        volume[-3:] = np.nan  # Volumen an den letzten 3 Sitzungen nicht gemeldet
        keep = np.ones(len(days), dtype=bool)
        keep[-6] = False  # eine Sitzung ganz ohne Kerze
        result = compute_turnover(days[keep], close[keep], volume[keep], SESSIONS, D, split_days=np.empty(0), currency="USD", unit_factor=1.0, fx=None)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.with_data, 16)
        self.assertEqual(result.avg_usd, 50.0 * 300_000.0, "Mittelwert nur über Sitzungen mit Daten")

    def test_reported_zero_volume_counts_as_zero_but_needs_16_positive_sessions(self) -> None:
        days, close, volume = self.series()
        volume = volume.copy()
        volume[-4:] = 0.0  # 16 von 20 positiv: zulässig, Nullen zählen mit
        ok = compute_turnover(days, close, volume, SESSIONS, D, split_days=np.empty(0), currency="USD", unit_factor=1.0, fx=None)
        self.assertEqual(ok.status, "ok")
        self.assertEqual(ok.positive, 16)
        self.assertAlmostEqual(ok.avg_usd, 50.0 * 300_000.0 * 16 / 20)
        volume[-5] = 0.0  # nur noch 15 positiv
        low = compute_turnover(days, close, volume, SESSIONS, D, split_days=np.empty(0), currency="USD", unit_factor=1.0, fx=None)
        self.assertEqual(low.status, "zu_wenig_umsatztage")
        self.assertIsNone(low.avg_usd)

    def test_missing_volume_data_prevents_a_value(self) -> None:
        days, close, volume = self.series()
        result = compute_turnover(days, close, np.full(len(days), np.nan), SESSIONS, D, split_days=np.empty(0), currency="USD", unit_factor=1.0, fx=None)
        self.assertEqual(result.status, "daten_fehlen")
        self.assertEqual(result.with_data, 0)
        self.assertIsNone(result.avg_usd)

    def test_subunits_and_fx_conversion_per_session(self) -> None:
        days, close, volume = self.series(price=500.0, volume=2_000_000.0)  # 500 GBp = 5 GBP
        result = compute_turnover(days, close, volume, SESSIONS, D, split_days=np.empty(0), currency="GBP", unit_factor=0.01, fx=fx_rates())
        self.assertEqual(result.status, "ok")
        self.assertAlmostEqual(result.avg_local, 5.0 * 2_000_000.0)
        self.assertAlmostEqual(result.avg_usd, 5.0 * 2_000_000.0 * 1.10 / 0.85)
        self.assertEqual(result.fx_last_day, D)

    def test_eur_converted_with_ecb_cross_rate(self) -> None:
        days, close, volume = self.series(price=20.0, volume=500_000.0)  # 10 Mio. EUR
        result = compute_turnover(days, close, volume, SESSIONS, D, split_days=np.empty(0), currency="EUR", unit_factor=1.0, fx=fx_rates())
        self.assertAlmostEqual(result.avg_usd, 10_000_000.0 * 1.10)

    def test_missing_or_stale_fx_rate_prevents_usd_value(self) -> None:
        days, close, volume = self.series()
        missing = compute_turnover(days, close, volume, SESSIONS, D, split_days=np.empty(0), currency="TWD", unit_factor=1.0, fx=fx_rates())
        self.assertEqual(missing.status, "wechselkurs_fehlt")
        self.assertIsNotNone(missing.avg_local, "Landeswährung bleibt sichtbar")
        stale = FxRates.from_rows([(day(2026, 9, 1), "USD", 1.1), (day(2026, 9, 1), "GBP", 0.85)], source="TEST", url=None, fetched_at=None, max_age_days=5)
        old = compute_turnover(days, close, volume, SESSIONS, D, split_days=np.empty(0), currency="GBP", unit_factor=0.01, fx=stale)
        self.assertEqual(old.status, "wechselkurs_fehlt")
        no_fx = compute_turnover(days, close, volume, SESSIONS, D, split_days=np.empty(0), currency="EUR", unit_factor=1.0, fx=None)
        self.assertEqual(no_fx.status, "wechselkurs_fehlt")

    def test_weekend_session_uses_previous_ecb_rate(self) -> None:
        rates = fx_rates()
        saturday = day(2026, 10, 10)
        value, used = rates.usd_per_unit("GBP", saturday)
        self.assertEqual(used, day(2026, 10, 9))
        self.assertAlmostEqual(value, 1.10 / 0.85)

    def test_split_inside_the_20_sessions_is_not_distorting_the_value(self) -> None:
        days, close, volume = self.series()
        split_day = int(SESSIONS[-10])
        result = compute_turnover(days, close, volume, SESSIONS, D, split_days=np.array([split_day]), currency="USD", unit_factor=1.0, fx=None)
        self.assertEqual(result.status, "kapitalmassnahme")
        earlier = compute_turnover(days, close, volume, SESSIONS, D, split_days=np.array([int(SESSIONS[-30])]), currency="USD", unit_factor=1.0, fx=None)
        self.assertEqual(earlier.status, "ok")

    def test_too_few_calendar_sessions(self) -> None:
        days, close, volume = self.series(n=10)
        result = compute_turnover(days, close, volume, SESSIONS[-10:], D, split_days=np.empty(0), currency="USD", unit_factor=1.0, fx=None)
        self.assertEqual(result.status, "zu_wenige_sitzungen")

    def test_every_status_has_a_text(self) -> None:
        for key in ("ok", "keine_kurse", "kalender_fehlt", "zu_wenige_sitzungen", "daten_fehlen", "zu_wenig_umsatztage", "kapitalmassnahme", "waehrung_unbekannt", "wechselkurs_fehlt"):
            self.assertIn(key, TURNOVER_STATUS)
            self.assertTrue(TURNOVER_STATUS[key]["text"])


class TwoReturnRankingsTests(unittest.TestCase):
    """Ranking 1 (alle) und Ranking 2 (Ø Umsatz ≥ 10 Mio. USD) aus demselben Rechenlauf."""

    @classmethod
    def setUpClass(cls) -> None:
        cfg = MethodConfig()
        n = len(SESSIONS)
        start = n - 70
        cls.cfg = cfg
        cls.instruments = [
            # 0: höchste Rendite, aber nur rund 1.000 USD Umsatz je Tag
            make_instrument(test_isin(1), SESSIONS, growth(1.50, n - start), volume=10.0, start_index=start, currency="USD"),
            # 1: gute Rendite, 100 USD × 200.000 Stück = Ø 20 Mio. USD → beide Rankings
            make_instrument(test_isin(2), SESSIONS, growth(0.40, n - start), volume=200_000.0, start_index=start, currency="USD"),
            # 2: an den letzten 5 Sitzungen kein Volumen gemeldet (Ø 12 Mio. USD, aber nur 15 von 20 Sitzungen)
            make_instrument(test_isin(3), SESSIONS, growth(0.80, n - start), volume=60_000.0, start_index=start, currency="USD"),
            # 3: EUR-Aktie, Landeswährung unter, in USD über 10 Mio. (Kurs 100 × 95.000 = 9,5 Mio. EUR · 1,10)
            make_instrument(test_isin(4), SESSIONS, growth(0.0, n - start), volume=95_000.0, start_index=start, currency="EUR"),
            # 4: Währung ohne Referenzkurs → nur Ranking 1
            make_instrument(test_isin(5), SESSIONS, growth(0.30, n - start), volume=900_000.0, start_index=start, currency="TWD"),
            # 5: nie ein Volumen gemeldet → bestehende Qualitätsregel (80 % belegtes Volumen) schließt sie aus beiden aus
            make_instrument(test_isin(6), SESSIONS, growth(0.60, n - start), volume=None, start_index=start, currency="USD"),
        ]
        cls.instruments[2].volume[-5:] = np.nan
        cls.comp = compute_snapshot(cls.instruments, D, cfg, fx=fx_rates())

    def members(self, h: int, which: str) -> list[int]:
        window = self.comp.rankings[h]
        ranking = window.native0 if which == "alle" else window.native0_liquid
        return ranking.order.tolist()

    def test_low_turnover_top_return_only_in_ranking_1(self) -> None:
        for h in (1, 7, 30, 90):
            self.assertEqual(self.members(h, "alle")[0], 0, f"h={h}: höchste Rendite führt Ranking 1")
            self.assertNotIn(0, self.members(h, "umsatz"))
        self.assertTrue(self.comp.warnings[0] & (1 << InstrumentWarning.SEHR_NIEDRIGER_UMSATZ))

    def test_liquid_stock_appears_in_both(self) -> None:
        for h in (1, 7, 30, 90):
            self.assertIn(1, self.members(h, "alle"))
            self.assertIn(1, self.members(h, "umsatz"))
        self.assertTrue(self.comp.liquid[1])
        self.assertEqual(self.comp.turnover[1].status, "ok")

    def test_missing_volume_or_fx_prevents_ranking_2(self) -> None:
        self.assertEqual(self.comp.turnover[2].status, "daten_fehlen")
        self.assertEqual(self.comp.turnover[2].with_data, 15)
        self.assertEqual(self.comp.turnover[4].status, "wechselkurs_fehlt")
        for idx in (2, 4):
            self.assertFalse(self.comp.liquid[idx])
            self.assertTrue(self.comp.warnings[idx] & (1 << InstrumentWarning.UMSATZ_NICHT_BESTIMMBAR))
            self.assertIn(idx, self.members(90, "alle"), "Ranking 1 bleibt möglich")
            self.assertNotIn(idx, self.members(90, "umsatz"))

    def test_existing_quality_rules_still_apply_to_ranking_1(self) -> None:
        # Ohne jedes gemeldete Volumen greift die bestehende Regel „mindestens 80 % belegtes Volumen“
        self.assertEqual(self.comp.turnover[5].status, "daten_fehlen")
        for h in (7, 30, 90):
            self.assertNotIn(5, self.members(h, "alle"))
            self.assertNotIn(5, self.members(h, "umsatz"))

    def test_fx_conversion_decides_admission(self) -> None:
        t = self.comp.turnover[3]
        self.assertLess(t.avg_local, 10_000_000.0)
        self.assertGreaterEqual(t.avg_usd, 10_000_000.0)
        self.assertIn(3, self.members(30, "umsatz"))

    def test_same_cutoff_formula_and_order(self) -> None:
        comp = self.comp
        for h in comp.windows:
            col = h - 1
            alle = self.members(h, "alle")
            umsatz = self.members(h, "umsatz")
            # Ranking 2 ist Ranking 1 ohne die nicht aufgenommenen Aktien – keine andere Sortierung
            self.assertEqual(umsatz, [i for i in alle if comp.liquid[i]])
            for i in umsatz:
                expected = comp.p1[i, col] / comp.p0[i, col] - 1.0
                self.assertEqual(comp.r[i, col], expected)
        self.assertEqual(comp.winners[0].entries[0]["idx"], 0)
        self.assertEqual(comp.winners_liquid[0].entries[0]["idx"], 1)
        self.assertEqual(comp.winners_liquid[0].entries[0]["end_day"], D)
        self.assertEqual(comp.winners[0].entries[0]["end_day"], D)

    def test_weekend_and_holiday_move_start_dates(self) -> None:
        comp = self.comp
        # h=1: Ziel 11.10. (Sonntag) → letzte Sitzung davor ist Donnerstag 08.10., weil Freitag 09.10. Feiertag ist
        self.assertEqual(int(comp.start_day[1, 0]), day(2026, 10, 8))
        # h=3: Ziel 09.10. (Feiertag) → ebenfalls 08.10.; h=4: Ziel 08.10. → 08.10.
        self.assertEqual(int(comp.start_day[1, 2]), day(2026, 10, 8))
        self.assertEqual(int(comp.start_day[1, 3]), day(2026, 10, 8))
        # h=5: Ziel 07.10. → 07.10.
        self.assertEqual(int(comp.start_day[1, 4]), day(2026, 10, 7))
        # gleiche Startdaten in beiden Rankings (dieselbe Berechnung)
        self.assertEqual(comp.winners_liquid[0].entries[0]["start_day"], int(comp.start_day[1, 0]))


class TakeoverPatternTests(unittest.TestCase):
    def test_jump_then_flat_is_flagged(self) -> None:
        prices = np.array([10.0, 10.1, 10.0, 13.0, 13.02, 13.01, 13.03, 13.02])
        self.assertTrue(takeover_pattern(prices, jump_min=0.15, calm_max=0.01, calm_sessions=3))

    def test_jump_with_continued_volatility_is_not_flagged(self) -> None:
        prices = np.array([10.0, 10.1, 10.0, 13.0, 13.5, 12.8, 13.6, 13.0])
        self.assertFalse(takeover_pattern(prices, jump_min=0.15, calm_max=0.01, calm_sessions=3))

    def test_jump_too_close_to_window_end_is_not_flagged(self) -> None:
        prices = np.array([10.0, 10.1, 10.0, 10.05, 13.0, 13.01])
        self.assertFalse(takeover_pattern(prices, jump_min=0.15, calm_max=0.01, calm_sessions=3))

    def test_engine_sets_window_flag(self) -> None:
        n = len(SESSIONS)
        start = n - 30

        def price(k: int) -> float:
            base = 20.0 * (1.001**k)
            return base * 1.3 if k >= 25 else base  # Sprung 5 Sitzungen vor Ende, danach ruhig

        inst = make_instrument(test_isin(9), SESSIONS, price, volume=50_000.0, start_index=start, currency="USD")
        comp = compute_snapshot([inst], D, MethodConfig(), fx=fx_rates())
        self.assertTrue(int(comp.wflags[0, 9]) & (1 << WindowWarning.UEBERNAHMEMUSTER))


if __name__ == "__main__":
    unittest.main()
