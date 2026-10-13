"""Abgleich mit einem zweiten Börsenplatz: Wahl des Platzes und Vergleich (reine Funktionen)."""

from __future__ import annotations

import unittest

import numpy as np

from traktien.analytics.fx import FxRates
from traktien.analytics.venues import AltSeries, VenueSettings, candidate_indices, choose_venue, compare_instrument
from traktien.providers.base import ListingCandidate
from traktien.providers.exchanges import load_exchange_table
from tests.helpers import day

TABLE = load_exchange_table()
SETTINGS = VenueSettings()
D = day(2026, 10, 12)  # Montag


def weekdays(first: int, last: int) -> np.ndarray:
    import datetime as dt

    from traktien.util.timeutil import day_to_date

    return np.array([d for d in range(first, last + 1) if day_to_date(d).weekday() < 5], dtype=np.int64)


def candidate(key: str, symbol: str) -> ListingCandidate:
    return ListingCandidate("openfigi", key, symbol, symbol.split(".")[0], key, "TEST", "Common Stock")


def fx_rates(usd_per_eur: float = 1.10, gbp_per_eur: float = 0.85, until: int = D) -> FxRates:
    rows = []
    for d in weekdays(D - 120, until).tolist():
        rows += [(d, "USD", usd_per_eur), (d, "GBP", gbp_per_eur)]
    return FxRates.from_rows(rows, source="EZB (Test)", url=None, fetched_at=None, max_age_days=5)


class ChooseVenueTests(unittest.TestCase):
    def test_prefers_xetra_then_frankfurt_and_skips_reference_and_same_symbol(self) -> None:
        found = [candidate("US", "AAPL"), candidate("XNYS", "AAPL"), candidate("XFRA", "APC.F"), candidate("XETR", "APC.DE"), candidate("XSWX", "AAPL.SW")]
        choice = choose_venue(found, reference_symbol="AAPL", reference_exchange="US", table=TABLE, preferred=SETTINGS.preferred)
        self.assertEqual((choice.exchange_key, choice.provider_symbol), ("XETR", "APC.DE"))
        without_xetra = [c for c in found if c.exchange_key != "XETR"]
        choice = choose_venue(without_xetra, reference_symbol="AAPL", reference_exchange="US", table=TABLE, preferred=SETTINGS.preferred)
        self.assertEqual(choice.exchange_key, "XFRA")

    def test_reference_on_xetra_uses_frankfurt(self) -> None:
        found = [candidate("XETR", "SAP.DE"), candidate("XFRA", "SAP.F"), candidate("XSWX", "SAP.SW")]
        choice = choose_venue(found, reference_symbol="SAP.DE", reference_exchange="XETR", table=TABLE, preferred=SETTINGS.preferred)
        self.assertEqual(choice.provider_symbol, "SAP.F")

    def test_otc_unknown_and_identical_listings_are_no_second_venue(self) -> None:
        found = [candidate("OTC", "NSRGF"), ListingCandidate("openfigi", None, "X.XX", "X", "ZZ"), candidate("US", "NSRGY")]
        self.assertIsNone(choose_venue(found, reference_symbol="NSRGY", reference_exchange="US", table=TABLE, preferred=SETTINGS.preferred))
        self.assertIsNone(choose_venue([], reference_symbol="A", reference_exchange="US", table=TABLE, preferred=SETTINGS.preferred))


class _Ranking:
    def __init__(self, order):
        self.order = np.array(order, dtype=np.int64)
        self.size = len(order)


class _Window:
    def __init__(self, first, second):
        self.native0 = _Ranking(first)
        self.native0_liquid = _Ranking(second) if second is not None else None


class CandidateTests(unittest.TestCase):
    def test_union_of_both_rankings_best_place_first_with_limit(self) -> None:
        rankings = {1: _Window([5, 3, 9], [3]), 2: _Window([7, 5, 3], None), 3: _Window([], [])}
        chosen, total = candidate_indices(rankings, (1, 2, 3), top_n=2, max_instruments=10)
        self.assertEqual(chosen, [3, 5, 7])  # Platz 1: 3 (Ranking 2), 5, 7; Platz 2: 3, 5
        self.assertEqual(total, 3)
        chosen, total = candidate_indices(rankings, (1, 2, 3), top_n=2, max_instruments=2)
        self.assertEqual((chosen, total), ([3, 5], 3))


class CompareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.days = weekdays(D - 100, D)
        self.ref_close = 100.0 * np.exp(np.linspace(0.0, 0.5, len(self.days)))  # USD, steigend

    def ref_window(self, h: int) -> tuple[int, float]:
        """Startsitzung (letzter Kurs ≤ Stichtag − h) und Rendite der Referenz."""
        k = int(np.searchsorted(self.days, D - h, side="right")) - 1
        return int(self.days[k]), float(self.ref_close[-1] / self.ref_close[k] - 1.0)

    def run_compare(self, alt_close, *, alt_days=None, currency="EUR", unit="EUR", factor=1.0, fx=None, windows=(1, 5, 30, 90), alt_sessions=None):
        cols = [h - 1 for h in windows]
        start = np.full(90, -1, dtype=np.int64)
        r = np.full(90, np.nan)
        for h in windows:
            start[h - 1], r[h - 1] = self.ref_window(h)
        alt = AltSeries("TST.DE", "XETR", "Xetra", currency, unit, factor, self.days if alt_days is None else alt_days, alt_close)
        return compare_instrument(
            cols=cols,
            start_days=start,
            r_ref=r,
            p1_ref=float(self.ref_close[-1]),
            cutoff_day=D,
            ref_currency="USD",
            ref_unit_factor=1.0,
            alt=alt,
            fx=fx_rates() if fx is None else fx,
            settings=SETTINGS,
            alt_sessions=alt_sessions,
        )

    def test_same_prices_in_other_currency_are_unremarkable(self) -> None:
        result = self.run_compare(self.ref_close / 1.10)  # EUR-Kurse, EZB 1,10 USD je EUR
        self.assertEqual(result.status, "geprueft")
        self.assertFalse(result.flagged)
        self.assertAlmostEqual(result.level, 0.0, places=12)
        for col, pair in result.pairs.items():
            self.assertEqual(pair.status, "ok")
            self.assertAlmostEqual(pair.dev, 0.0, places=12)
            self.assertAlmostEqual(pair.r_alt, self.ref_window(col + 1)[1], places=12)

    def test_return_deviation_above_threshold_is_flagged_only_where_it_occurs(self) -> None:
        alt = self.ref_close / 1.10
        alt = np.where(self.days <= D - 25, alt * 0.85, alt)  # früher 15 % tiefer
        result = self.run_compare(alt)
        self.assertEqual(result.pairs[0].status, "ok")
        self.assertEqual(result.pairs[4].status, "ok")
        self.assertEqual(result.pairs[29].status, "abweichung")
        self.assertAlmostEqual(result.pairs[29].dev, 1 / 0.85 - 1, places=9)
        self.assertEqual(result.pairs[89].status, "abweichung")
        self.assertFalse(result.level_flagged)

    def test_deviation_just_below_threshold_is_not_flagged(self) -> None:
        alt = self.ref_close / 1.10
        alt = np.where(self.days <= D - 25, alt / 1.099, alt)
        result = self.run_compare(alt)
        self.assertEqual(result.pairs[29].status, "ok")
        self.assertAlmostEqual(result.pairs[29].dev, 0.099, places=9)

    def test_end_price_deviation_flags_every_window(self) -> None:
        result = self.run_compare(self.ref_close / 1.10 * 0.8)
        self.assertTrue(result.level_flagged)
        self.assertAlmostEqual(result.level, -0.2, places=12)
        self.assertTrue(all(p.status == "abweichung" for p in result.pairs.values()))
        self.assertTrue(all(abs(p.dev) < 1e-12 for p in result.pairs.values()), "Wertentwicklung selbst gleich")

    def test_subunits_are_converted(self) -> None:
        pence = self.ref_close / 1.10 * 0.85 * 100  # GBp: 0,85 GBP je EUR
        result = self.run_compare(pence, currency="GBP", unit="GBp", factor=0.01)
        self.assertFalse(result.flagged)
        self.assertAlmostEqual(result.level, 0.0, places=12)

    def test_missing_alt_closes_are_not_replaced_by_older_ones(self) -> None:
        days = self.days[self.days <= D - 7]  # Vergleichsplatz ohne Kurse in der letzten Woche
        result = self.run_compare(self.ref_close[: len(days)] / 1.10, alt_days=days)
        self.assertTrue(all(p.status == "keine_kurse" for p in result.pairs.values()))
        self.assertIsNone(result.level)
        gap = np.isin(self.days, weekdays(D - 40, D - 25))  # Lücke um den Start des 30-Tage-Fensters
        result = self.run_compare(self.ref_close[~gap] / 1.10, alt_days=self.days[~gap])
        self.assertEqual(result.pairs[29].status, "keine_kurse")
        self.assertEqual(result.pairs[4].status, "ok")

    def test_weekend_start_uses_last_close_before(self) -> None:
        # Stichtag Montag: Fenster 2 Tage beginnt am Samstag → letzter Schlusskurs Freitag
        result = self.run_compare(self.ref_close / 1.10, windows=(2, 3))
        friday = D - 3
        self.assertEqual(result.pairs[1].d0, friday)
        self.assertEqual(result.pairs[2].d0, friday)
        self.assertEqual(result.pairs[1].d1, D)

    # --- boersenplatz-v2: Börsenkalender des Vergleichsplatzes (Lieferlücke ≠ Feiertag) ---------------

    def monday_jump(self) -> np.ndarray:
        """Referenz mit +30 % am Stichtag (Montag); Vergleichsplatz bis Freitag mit gleichen Kursen."""
        ref = self.ref_close.copy()
        ref[-1] = ref[-2] * 1.30
        self.ref_close = ref
        return ref / 1.10

    def test_provider_gap_on_a_session_day_is_not_bridged_with_the_friday_close(self) -> None:
        alt = self.monday_jump()
        friday_and_before = self.days < D  # Anbieter liefert für Montag keinen Schlusskurs (Yahoo, 12.10.2026)
        # v1 (ohne Kalender): Freitagskurs statt Montagskurs → Endkurs 23 % tiefer → jedes Fenster „auffällig“
        legacy = self.run_compare(alt[friday_and_before], alt_days=self.days[friday_and_before], windows=(5, 30, 90))
        self.assertTrue(legacy.level_flagged)
        self.assertTrue(all(p.status == "abweichung" for p in legacy.pairs.values()))
        # v2: Xetra hatte am Montag eine Sitzung → nur dieser Schlusskurs zählt; er fehlt → kein Vergleich
        result = self.run_compare(alt[friday_and_before], alt_days=self.days[friday_and_before], windows=(5, 30, 90), alt_sessions=self.days)
        self.assertFalse(result.flagged)
        self.assertIsNone(result.level)
        self.assertEqual({p.status for p in result.pairs.values()}, {"keine_kurse"})

    def test_holiday_at_the_second_venue_uses_its_last_session_before(self) -> None:
        alt = self.monday_jump()
        sessions = self.days[self.days < D]  # Vergleichsplatz am Montag geschlossen (Feiertag dort)
        result = self.run_compare(alt[self.days < D], alt_days=sessions, windows=(5, 30), alt_sessions=sessions)
        self.assertEqual(result.end_day, D - 3)
        self.assertEqual(result.pairs[4].d1, D - 3)
        self.assertTrue(result.level_flagged, "Freitag dort gegen Montag hier: Abweichung bleibt sichtbar wie bisher")

    def test_gap_at_a_start_session_drops_only_that_window(self) -> None:
        start_30, _ = self.ref_window(30)
        keep = self.days != start_30
        result = self.run_compare(self.ref_close[keep] / 1.10, alt_days=self.days[keep], alt_sessions=self.days)
        self.assertEqual(result.pairs[29].status, "keine_kurse")
        self.assertEqual(result.pairs[4].status, "ok")
        self.assertEqual(result.pairs[89].status, "ok")
        self.assertFalse(result.flagged)

    def test_closes_on_days_without_a_session_are_ignored(self) -> None:
        saturday = D - 2
        days = np.sort(np.append(self.days, saturday))
        alt = self.ref_close / 1.10
        alt = np.insert(alt, int(np.searchsorted(self.days, saturday)), 1.0)  # unplausibler Samstagskurs
        result = self.run_compare(alt, alt_days=days, windows=(2,), alt_sessions=self.days)
        self.assertEqual(result.pairs[1].d0, D - 3)
        self.assertEqual(result.pairs[1].status, "ok")

    def test_missing_fx_rate_gives_no_result(self) -> None:
        old_rates = fx_rates(until=D - 20)
        result = self.run_compare(self.ref_close / 1.10, fx=old_rates)
        self.assertTrue(all(p.status == "wechselkurs_fehlt" for p in result.pairs.values()))
        same_currency = self.run_compare(self.ref_close, currency="USD", unit="USD", fx=old_rates)
        self.assertFalse(same_currency.flagged, "gleiche Währung braucht keinen Wechselkurs")
        self.assertTrue(all(p.status == "ok" for p in same_currency.pairs.values()))


if __name__ == "__main__":
    unittest.main()
