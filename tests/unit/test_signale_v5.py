"""Signal-Stand ``signale-v5`` (ab 1.25.0): Kaufwarnung aus belegten kritischen Meldungen macht das Risiko „hoch“,
Gerüchte nicht; Wahrscheinlichkeiten und Aufmerksamkeit in der Reihenfolge der Ergebnisse."""

from __future__ import annotations

import unittest

from tests.unit.test_signals import stock
from traktien.analytics import signals as sg


def with_news(item, title, *, hours_ago=2.0, related=True):
    item.news = [{"titel": title, "quelle": "Reuters", "zeit": int(item.now_ts - hours_ago * 3600), "link": "https://example.org/a", "bezug": related, "tendenz": -1}]
    return item


class SignalsV5Tests(unittest.TestCase):
    def test_confirmed_critical_event_sets_warning_and_high_risk(self):
        batch = sg.compute_all([with_news(stock("ZZ0000000001", n=160, seed=3), "Beispiel files for Chapter 11 bankruptcy protection")], with_backtest=False)
        r = batch.results[0]
        self.assertEqual(sg.VERSION, "signale-v5")
        self.assertIsNotNone(r.news_warning)
        self.assertEqual(r.news_warning.art, "insolvenz")
        self.assertEqual(r.news_light, "rot")
        self.assertEqual(r.risk.level, "hoch")
        self.assertTrue(any(reason.startswith("Kaufwarnung: Insolvenz") for reason in r.risk.reasons), r.risk.reasons)

    def test_rumor_and_unrelated_news_do_not_warn(self):
        rumor = sg.compute_all([with_news(stock("ZZ0000000002", n=160, seed=4), "Beispiel reportedly weighs bankruptcy filing")], with_backtest=False).results[0]
        self.assertIsNone(rumor.news_warning)
        self.assertEqual(rumor.events[0].status, "geruecht")
        unrelated = sg.compute_all([with_news(stock("ZZ0000000003", n=160, seed=5), "Beispiel files for Chapter 11", related=False)], with_backtest=False).results[0]
        self.assertIsNone(unrelated.news_warning)
        self.assertEqual(unrelated.events, [])

    def test_probability_and_attention_follow_result_order(self):
        items = [stock(f"ZZ{k:010d}", n=180, seed=10 + k, volume=4e6) for k in range(25)]
        for item in items:
            item.usd_per_eur = 1.1  # Ø Tagesumsatz rund 400 Mio. USD: alle mit Mindestumsatz
        batch = sg.compute_all(items)
        self.assertIsNotNone(batch.wahrscheinlichkeit)
        for h, column in batch.wahrscheinlichkeit.probabilities.items():
            self.assertEqual(len(column), len(batch.results), h)
        self.assertEqual(len(batch.wahrscheinlichkeit.reasons), len(batch.results))
        att = batch.aufmerksamkeit
        self.assertEqual(att["version"], "aufmerksamkeit-1")
        self.assertEqual(att["anzahl"], 25)
        self.assertEqual(len(att["liste"]), 25)
        self.assertTrue(all(0 <= item["i"] < len(batch.results) for item in att["liste"]))
        self.assertEqual(sorted(item["rang"] for item in att["liste"]), list(range(1, 26)))


if __name__ == "__main__":
    unittest.main()
