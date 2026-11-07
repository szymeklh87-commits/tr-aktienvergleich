"""Signalregel 1 (ab 1.21.0): Kaufsignal, Einstiegslimit, Stop, Kursziel und CRV – von Hand nachgerechnet."""

from __future__ import annotations

import dataclasses
import unittest

from traktien.analytics import tradeplan as tp

GUT = tp.PlanInput(
    close=100.0, day=20400, atr_share=0.02, sma20=96.0, sma50=90.0, high20=101.0, rsi=64.0, gap=0.004, rvol=1.4,
    strength_pctile=85.0, turnover_usd=25_000_000.0, analyst_target=130.0, analysts=8, news_positive=1, news_negative=0,
)


def plan(**changes) -> tp.TradePlan:
    return tp.plan_trade(dataclasses.replace(GUT, **changes))


class TradePlanTests(unittest.TestCase):
    def test_all_conditions_give_a_buy_signal_with_hand_checked_levels(self):
        p = plan()
        self.assertEqual(p.status, "kaufsignal")
        # ATR = 2 % von 100 = 2,00 · Einstieg = 100 + 0,25 × 2 = 100,50 · Stop = 100,50 − 2 × 2 = 96,50 · Risiko 4,00
        # Ziel = 100,50 + 2 × 4,00 = 108,50 (Ø Kursziel 130 liegt darüber, gilt nicht) · CRV = 8,00 / 4,00 = 2
        self.assertEqual((p.entry, p.stop, p.target, p.target_basis, p.crv), (100.5, 96.5, 108.5, "2R", 2.0))
        self.assertAlmostEqual(p.risk_share, 4.0 / 100.5)
        self.assertFalse(p.late)
        self.assertTrue(all(c.ok for c in p.checks), [c.as_dict() for c in p.checks if not c.ok])

    def test_prices_round_to_the_tick_and_never_in_favour_of_the_signal(self):
        p = plan(close=12.34, atr_share=0.031, sma20=12.0, sma50=11.5, high20=12.40, analyst_target=None, analysts=0)
        atr = 0.031 * 12.34  # 0,38254
        self.assertEqual(p.entry, 12.44)  # 12,34 + 0,0956 = 12,4356 → aufgerundet 12,44
        self.assertEqual(p.stop, 11.67)   # 12,44 − 0,76508 = 11,67492 → abgerundet 11,67
        self.assertEqual(p.target, 13.98)  # 12,44 + 2 × 0,77 = 13,98
        self.assertEqual(p.crv, 2.0)
        self.assertLess(p.entry - 12.34, 0.25 * atr + 0.01)
        penny = plan(close=0.4567, atr_share=0.05, sma20=0.44, sma50=0.40, high20=0.46, analyst_target=None, analysts=0)
        self.assertEqual(penny.entry, 0.4625)  # 0,4567 + 0,0057088 = 0,4624088 → 0,4625 (Kursschritt 0,0001 unter 1)

    def test_analyst_target_below_two_r_caps_the_target_and_the_crv(self):
        p = plan(analyst_target=105.0)
        self.assertEqual((p.status, p.target, p.target_basis, p.crv), ("beobachten", 105.0, "analysten", 1.12))
        self.assertIn("unter 2 : 1", p.reason)
        few = plan(analyst_target=105.0, analysts=2)
        self.assertEqual((few.status, few.target_basis), ("kaufsignal", "2R"), "unter 3 Analysten zählt das Kursziel nicht")
        below = plan(analyst_target=95.0)
        self.assertEqual(below.status, "beobachten")
        self.assertEqual(below.reason, "Kursziel der Analysten liegt unter dem Einstieg")

    def test_late_entries_are_watch_not_buy(self):
        for changes, word in (({"sma20": 92.0}, "Abstand zur 20-Tage-Linie"), ({"rsi": 79.0}, "RSI"), ({"gap": 0.05}, "Kurslücke")):
            with self.subTest(changes=changes):
                p = plan(**changes)
                self.assertEqual(p.status, "beobachten")
                self.assertTrue(p.late)
                self.assertIn("Einstieg zu spät", p.reason)
                self.assertIn(word, p.reason)
                self.assertIsNotNone(p.entry, "Plan bleibt sichtbar, damit der Rücksetzer beobachtet werden kann")

    def test_events_turn_a_signal_into_watch(self):
        p = plan(earnings_day=20402)
        self.assertEqual((p.status, p.reason), ("beobachten", "Geschäftszahlen: in 2 Tagen"))
        self.assertEqual(plan(earnings_day=20404).status, "kaufsignal", "vier Tage Abstand reichen")
        self.assertEqual(plan(earnings_day=20390).status, "kaufsignal", "vergangener Termin zählt nicht")
        news = plan(news_positive=0, news_negative=2)
        self.assertEqual((news.status, news.reason), ("beobachten", "Schlagzeilen (3 Tage): 0 positiv, 2 negativ"))

    def test_minimum_turnover_is_10_million_usd_from_signal_rule_2(self):
        """Ab 1.23.0 (Signalregel 2): Ø Tagesumsatz mindestens 10 Mio. USD – genau an der Schwelle erfüllt, knapp darunter kein Kauf."""
        self.assertEqual(tp.RULE_VERSION, "signalregel-2")
        self.assertEqual(tp.RULES["mindestumsatz_usd"], 10_000_000.0)
        self.assertEqual(plan(turnover_usd=10_000_000.0).status, "kaufsignal")
        below = plan(turnover_usd=9_990_000.0)
        self.assertEqual(below.status, "kein_kauf")
        check = next(c for c in below.checks if c.key == "umsatz")
        self.assertIs(check.ok, False)
        self.assertEqual((check.value, check.rule), ("10,0 Mio. USD", "mindestens 10 Mio. USD pro Handelstag (Ø 20 Sitzungen)"))

    def test_setup_or_basis_failures_are_no_buy_with_the_first_reason(self):
        cases = (
            ({"data_issue": "Kurse zurückgehalten (Währungswechsel)"}, "Kursdaten geprüft"),
            ({"turnover_usd": 9_999_999.0}, "Ø Tagesumsatz"),  # ab Signalregel 2: Mindestumsatz 10 Mio. USD
            ({"turnover_usd": None}, "Ø Tagesumsatz: unbekannt"),
            ({"sma20": 101.0}, "Trend"),
            ({"sma50": 97.0}, "Trend"),
            ({"strength_pctile": 69.9}, "Relative Stärke"),
            ({"high20": 103.5}, "Nähe zum 20-Tage-Hoch"),
            ({"rvol": 0.9}, "Umsatz der letzten Sitzung"),
            ({"tradable": False}, "Bei Trade Republic gelistet"),
        )
        for changes, word in cases:
            with self.subTest(changes=changes):
                p = plan(**changes)
                self.assertEqual(p.status, "kein_kauf")
                self.assertTrue(p.reason.startswith(word), p.reason)
                self.assertIsNone(p.entry)

    def test_missing_data_never_gives_a_signal(self):
        for key in ("close", "atr_share", "sma20", "sma50", "high20", "strength_pctile", "rvol"):
            with self.subTest(key=key):
                p = plan(**{key: None})
                self.assertEqual(p.status, "kein_kauf", p.reason)
        unknown_rsi = plan(rsi=None)
        self.assertEqual(unknown_rsi.status, "beobachten")
        self.assertFalse(unknown_rsi.late)
        self.assertEqual(unknown_rsi.reason, "RSI (14) unbekannt")

    def test_boundaries_are_inclusive_as_documented(self):
        self.assertEqual(plan(high20=100.0 / 0.97).status, "kaufsignal", "genau 3 % unter dem Hoch")
        self.assertEqual(plan(rsi=75.0).status, "kaufsignal")
        self.assertEqual(plan(strength_pctile=70.0).status, "kaufsignal")
        self.assertEqual(plan(sma20=94.0).status, "kaufsignal", "genau 3 ATR über der 20-Tage-Linie")
        self.assertEqual(plan(rvol=1.0).status, "kaufsignal")
        self.assertEqual(plan(gap=0.02).status, "kaufsignal", "Kurslücke genau 1 ATR")

    def test_serialised_plan_and_rules_are_complete(self):
        d = plan().as_dict()
        self.assertEqual(d["regel"], tp.RULE_VERSION)
        self.assertEqual({c["gruppe"] for c in d["pruefungen"]}, {"basis", "ausgangslage", "zeitpunkt", "ereignis", "risiko"})
        self.assertEqual(tp.RULES["min_crv"], 2.0)
        self.assertIn("Keine Anlageberatung", tp.RULES["beschreibung"])


if __name__ == "__main__":
    unittest.main()
