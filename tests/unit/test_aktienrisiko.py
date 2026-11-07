"""Risiko je Aktie (ab 1.24.0, ``risiko-1``): Stufen, Gründe, fehlende Daten nie „niedrig“."""

from __future__ import annotations

import math
import unittest

from traktien.analytics import aktienrisiko as ar

DAY = 0.25 / math.sqrt(252.0)  # Tagesschwankung für 25 % pro Jahr


def facts(**fin):
    base = {"verschuldung": 0.4, "liquiditaet": 1.8, "nettomarge": 0.12, "free_cashflow_positiv": True}
    base.update(fin)
    return {"finanzen": base, "wachstum": {}, "risiko": {}, "branche": {"sektor": "Technology"}}


class RiskTests(unittest.TestCase):
    def test_calm_solid_company_is_low(self):
        r = ar.assess({"schwankung": 0.2 / math.sqrt(252.0), "kurs": 98.0, "hoch250": 100.0}, facts(), 5e9)
        self.assertEqual(r.level, "niedrig")
        self.assertTrue(r.complete)
        self.assertIn("geringe Kursschwankung (20 % pro Jahr)", r.reasons)

    def test_volatile_indebted_small_cap_is_high_with_main_reasons(self):
        r = ar.assess({"schwankung": 0.8 / math.sqrt(252.0), "kurs": 40.0, "hoch250": 100.0}, facts(verschuldung=3.0, liquiditaet=0.4), 40e6)
        self.assertEqual(r.level, "hoch")
        self.assertEqual(len(r.reasons), 3)
        self.assertTrue(r.reasons[0].startswith(("sehr hohe Kursschwankung", "60 % unter", "Schulden", "kurzfristige", "sehr kleiner")))
        self.assertGreaterEqual(r.points, 8)

    def test_medium_band(self):
        r = ar.assess({"schwankung": 0.45 / math.sqrt(252.0), "kurs": 65.0, "hoch250": 100.0}, facts(), 5e9)
        self.assertEqual((r.level, r.points), ("mittel", 2))

    def test_missing_fundamentals_never_low_and_flagged(self):
        r = ar.assess({"schwankung": DAY, "kurs": 99.0, "hoch250": 100.0}, None, None)
        self.assertEqual(r.level, "mittel")
        self.assertFalse(r.complete)
        self.assertIn("Bilanzkennzahlen fehlen – Bewertung unvollständig", r.reasons)

    def test_no_series_or_held_prices_not_assessable(self):
        self.assertEqual(ar.assess({}, facts(), 5e9).level, "unbekannt")
        held = ar.assess({"schwankung": DAY}, facts(), 5e9, data_issue="Kurse zurückgehalten (Währungswechsel)")
        self.assertEqual(held.level, "unbekannt")

    def test_banks_skip_leverage_and_news_counts(self):
        bank = facts(verschuldung=8.0)
        bank["branche"]["sektor"] = "Financial Services"
        r = ar.assess({"schwankung": 0.2 / math.sqrt(252.0), "kurs": 99.0, "hoch250": 100.0}, bank, 5e9)
        self.assertEqual(r.level, "niedrig", "Verschuldung von Banken ist kein Risikomerkmal dieser Regel")
        news = ar.assess({"schwankung": 0.4 / math.sqrt(252.0), "kurs": 99.0, "hoch250": 100.0}, facts(), 5e9, news_positive=0, news_negative=3)
        self.assertEqual(news.level, "mittel")
        self.assertIn("überwiegend negative Schlagzeilen (3 negativ, 0 positiv)", news.reasons)

    def test_confirmed_critical_event_is_always_high(self):
        r = ar.assess({"schwankung": 0.2 / math.sqrt(252.0), "kurs": 98.0, "hoch250": 100.0}, facts(), 5e9, critical_event="Insolvenz (06.11.2026)")
        self.assertEqual(r.level, "hoch", "ab risiko-2: belegtes kritisches Ereignis")
        self.assertEqual(r.reasons[0], "Kaufwarnung: Insolvenz (06.11.2026)")
        self.assertEqual(ar.VERSION, "risiko-2")


if __name__ == "__main__":
    unittest.main()
