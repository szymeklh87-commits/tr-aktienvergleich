"""Aufmerksamkeit (eigene Berechnung, ab 1.25.0): Rang aus Umsatz und Kursbewegung, frühere Ränge mit derselben Rechnung,
„neu“ und Veränderungen; nur Aktien mit Mindestumsatz; Link statt Übernahme der onvista-Liste."""

from __future__ import annotations

import unittest

import numpy as np

from traktien.analytics import aufmerksamkeit as am


def stock(i: int, n: int = 60, *, spike_day: int | None = None, liquid: bool = True, seed: int = 0) -> am.StockAttention:
    rng = np.random.default_rng(seed + i)
    rvol = rng.uniform(0.8, 1.2, n)
    move = np.abs(rng.normal(0, 1, n))
    r1 = rng.normal(0, 0.01, n)
    if spike_day is not None:
        rvol[spike_day:] = 6.0
        move[spike_day] = 5.0
        r1[spike_day] = -0.08
    return am.StockAttention(isin=f"ZZ{i:010d}", days=np.arange(20000, 20000 + n), rvol=rvol, move=move, r1=r1, liquid=np.full(n, liquid))


class AttentionTests(unittest.TestCase):
    def test_spike_ranks_first_with_reasons_and_history(self):
        stocks = [stock(i) for i in range(40)] + [stock(40, spike_day=59)]
        out = am.compute(stocks)
        self.assertEqual(out["version"], "aufmerksamkeit-1")
        self.assertEqual(out["tag"], 20059)
        first = out["liste"][0]
        self.assertEqual((first["i"], first["rang"]), (40, 1))
        self.assertTrue(first["neu"] or first["vortag"] > 1)
        self.assertTrue(any("6,0-fach" in g for g in first["gruende"]))
        self.assertTrue(any(g.startswith("Kursbewegung −8,0") for g in first["gruende"]), first["gruende"])
        self.assertEqual(out["link_onvista"], am.ONVISTA_LINK)
        self.assertIn("kein Kaufsignal", out["hinweis"])

    def test_earlier_ranks_use_same_rule_and_illiquid_excluded(self):
        stocks = [stock(i) for i in range(40)] + [stock(40, spike_day=50), stock(41, liquid=False, spike_day=59)]
        out = am.compute(stocks)
        ids = [x["i"] for x in out["liste"]]
        self.assertNotIn(41, ids, "ohne Mindestumsatz nicht in der Rangliste")
        spike = next(x for x in out["liste"] if x["i"] == 40)
        self.assertIsNotNone(spike["vor7"])
        self.assertLessEqual(spike["vor7"], 3, "vor 7 Tagen (Tag 52) schon vorn: Umsatz seit Tag 50 hoch")
        self.assertEqual(out["tage_berechnet"], 31)
        self.assertIsNotNone(spike["vor30"], "Rang vor 30 Handelstagen aus denselben Daten")
        self.assertGreater(spike["vor30"], 3, "vor 30 Tagen (Tag 29) noch ohne erhöhten Umsatz")
        self.assertEqual(out["anzahl"], 41)

    def test_too_few_stocks(self):
        out = am.compute([stock(i) for i in range(5)])
        self.assertEqual(out["liste"], [])

    def test_percentile_ties(self):
        p = am._pct_rank(np.array([1.0, 1.0, 3.0]))
        self.assertEqual(p.tolist(), [0.25, 0.25, 1.0])


if __name__ == "__main__":
    unittest.main()
