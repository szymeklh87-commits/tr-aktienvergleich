"""Rückblick der Signalregel (ab 1.24.0): Status je Tag wie die Signalregel, keine Zukunftsdaten, Ausführung mit Limit, Stop
und Ziel, unabhängige Fälle, Kennzahlen – SYNTHETISCHE Kurse."""

from __future__ import annotations

import math
import unittest

import numpy as np

from traktien.analytics import rueckblick as rb
from traktien.analytics import signals as sg
from traktien.analytics import tradeplan as tp


def history(close, *, open_=None, high=None, low=None, volume=None, days=None, unit_to_eur=1.0, usd_per_eur=1.1, isin="ZZ0000000001") -> rb.StockHistory:
    close = np.asarray(close, dtype=np.float64)
    n = len(close)
    open_ = np.asarray(open_ if open_ is not None else close, dtype=np.float64)
    high = np.asarray(high if high is not None else np.maximum(open_, close) * 1.005, dtype=np.float64)
    low = np.asarray(low if low is not None else np.minimum(open_, close) * 0.995, dtype=np.float64)
    volume = np.asarray(volume if volume is not None else np.full(n, 1e6), dtype=np.float64)
    ts = sg.tech_series(open_, high, low, close, volume)
    return rb.StockHistory(isin=isin, days=np.asarray(days if days is not None else np.arange(20000, 20000 + n)), open=open_, high=high, low=low,
                           close=ts.close, sma20=ts.sma20, sma50=ts.sma50, high20=ts.high20, rsi=ts.rsi, atr_pct=ts.atr_pct, gap=ts.gap,
                           rvol=ts.rvol, r20=ts.r20, turnover_local=ts.turnover, unit_to_eur=unit_to_eur, usd_per_eur=usd_per_eur, currency="EUR")


def universe(n_days=160, extra=None, seed=3) -> list[rb.StockHistory]:
    """25 Vergleichsaktien (Zufallspfade) plus ``extra`` – genug Werte je Tag für das Stärke-Perzentil."""
    rng = np.random.default_rng(seed)
    out = []
    for k in range(25):
        path = 30.0 * np.exp(np.cumsum(rng.normal(0.0, 0.015, n_days)))
        out.append(history(path, isin=f"ZZ{k + 100:010d}"))
    return out + (extra or [])


def trending(n_days=160, *, drift=0.004, swing=0.002) -> np.ndarray:
    """Steigender Kurs (über den Linien, nahe am Hoch); ``swing`` = Schwankung um den Trend."""
    k = np.arange(n_days)
    return 20.0 * np.exp(drift * k) * (1.0 + swing * np.sin(k / (2.0 if swing < 0.005 else 1.5)))


class StatusTests(unittest.TestCase):
    def test_last_day_status_matches_the_live_signal_rule(self):
        """Ohne Nachrichten, Termine und Analystenziele ergibt die Rechnung je Tag am letzten Tag denselben Status wie die
        Signalregel des Signal-Stands (gleiche Merkmale) – für „beobachten“ (zu spät) und für ein Kaufsignal."""
        for close, want in ((trending(), "beobachten"), (trending(drift=0.002, swing=0.015), "kaufsignal")):
            with self.subTest(want=want):
                self._compare(close, want)

    def _compare(self, close, want):
        vol = np.full(len(close), 1e6)
        vol[-1] = 2e6  # Umsatz der letzten Sitzung über dem Durchschnitt
        stock = history(close, volume=vol, isin="ZZ0000000001")
        hists = universe(extra=[stock])
        pct = rb.strength_percentiles(hists)[-1]
        status, entry, stop, target = rb.statuses(stock, pct)
        t = len(close) - 1
        plan = tp.plan_trade(tp.PlanInput(
            close=float(close[t]), day=int(stock.days[t]), atr_share=float(stock.atr_pct[t]), sma20=float(stock.sma20[t]), sma50=float(stock.sma50[t]),
            high20=float(stock.high20[t]), rsi=float(stock.rsi[t]), gap=float(stock.gap[t]), rvol=float(stock.rvol[t]), strength_pctile=float(pct[t]),
            turnover_usd=float(stock.turnover_local[t] * 1.0 * 1.1),
        ))
        name = rb.STATUS[int(status[t])]
        self.assertEqual(name, plan.status)
        self.assertEqual(name, want, "Testdaten erzeugen den erwarteten Fall")
        if plan.status in ("kaufsignal", "beobachten"):
            self.assertAlmostEqual(float(entry[t]), plan.entry, places=6)
            self.assertAlmostEqual(float(stop[t]), plan.stop, places=6)
            self.assertAlmostEqual(float(target[t]), plan.target, places=6)

    def test_no_future_data(self):
        """Werden alle Kursreihen nach Tag t0 abgeschnitten, bleiben Status und Planwerte bis t0 unverändert."""
        close = trending(200)
        full = universe(200, extra=[history(close)])
        t0 = 150
        cut = []
        for h in full:
            cut.append(rb.StockHistory(**{name: (getattr(h, name)[: t0 + 1] if isinstance(getattr(h, name), np.ndarray) else getattr(h, name))
                                          for name in h.__dataclass_fields__}))
        # Kennzahlen der abgeschnittenen Reihen neu aus den Kursen (nicht abgeschnittene Kennzahlen weiterreichen)
        cut = [history(h.close, open_=h.open, high=h.high, low=h.low, volume=None, days=h.days, isin=h.isin) for h in cut]
        full = [history(h.close, open_=h.open, high=h.high, low=h.low, volume=None, days=h.days, isin=h.isin) for h in full]
        p_full = rb.strength_percentiles(full)
        p_cut = rb.strength_percentiles(cut)
        for hf, hc, pf, pc in zip(full, cut, p_full, p_cut):
            sf = rb.statuses(hf, pf)
            sc = rb.statuses(hc, pc)
            np.testing.assert_array_equal(sf[0][: t0 + 1], sc[0])
            for a, b in zip(sf[1:], sc[1:]):
                np.testing.assert_allclose(a[: t0 + 1], b, equal_nan=True)

    def test_turnover_below_10_million_usd_is_never_a_signal(self):
        close = trending()
        vol = np.full(len(close), 1e6)
        vol[-1] = 2e6
        rich = history(close, volume=vol)
        poor = history(close, volume=vol / 100.0, isin="ZZ0000000002")  # rund 0,3 Mio. USD am Tag
        hists = universe(extra=[rich, poor])
        pct = rb.strength_percentiles(hists)
        st_poor = rb.statuses(poor, pct[-1])[0]
        self.assertFalse((st_poor >= 2).any(), "unter 10 Mio. USD nie Ausgangslage erfüllt")
        self.assertTrue((rb.statuses(rich, pct[-2])[0] >= 2).any(), "Gegenprobe: mit Umsatz wird die Ausgangslage erreicht")


class SimulationTests(unittest.TestCase):
    def _flat(self, n=30, price=100.0):
        c = np.full(n, price)
        return history(c, open_=c.copy(), high=c * 1.001, low=c * 0.999)

    def test_limit_buy_target_and_holding(self):
        h = self._flat()
        t = 5
        h.open[t + 1] = 100.0
        h.low[t + 1], h.high[t + 1], h.close[t + 1] = 99.5, 101.0, 100.5
        h.open[t + 2], h.low[t + 2], h.high[t + 2], h.close[t + 2] = 101.0, 100.8, 104.5, 104.0  # Ziel 104 erreicht
        out = rb.simulate(h, t, entry=100.2, stop=98.0, target=104.0, cost=0.002)
        self.assertTrue(out.filled)
        self.assertAlmostEqual(out.plan[1], 100.5 / 100.0 - 1 - 0.002)
        for k in (5, 10, 20):
            self.assertAlmostEqual(out.plan[k], 104.0 / 100.0 - 1 - 0.002, msg=f"{k} Tage: Ziel am zweiten Tag")
        self.assertAlmostEqual(out.hold[1], 100.5 / 100.0 - 1 - 0.002)
        self.assertAlmostEqual(out.hold[5], 100.0 / 100.0 - 1 - 0.002)

    def test_stop_first_when_both_in_one_day_and_gap_down(self):
        h = self._flat()
        t = 3
        h.open[t + 1], h.low[t + 1], h.high[t + 1], h.close[t + 1] = 100.0, 99.9, 100.3, 100.1
        h.open[t + 2], h.low[t + 2], h.high[t + 2], h.close[t + 2] = 100.0, 97.0, 105.0, 101.0  # Stop und Ziel am selben Tag
        out = rb.simulate(h, t, entry=100.2, stop=98.0, target=104.0, cost=0.0)
        self.assertAlmostEqual(out.plan[5], 98.0 / 100.0 - 1, msg="vorsichtig: Stop zuerst")
        h2 = self._flat()
        h2.open[t + 1], h2.low[t + 1], h2.high[t + 1], h2.close[t + 1] = 100.0, 99.9, 100.3, 100.1
        h2.open[t + 2], h2.low[t + 2], h2.high[t + 2], h2.close[t + 2] = 95.0, 94.0, 96.0, 95.5  # Eröffnung unter dem Stop
        out2 = rb.simulate(h2, t, entry=100.2, stop=98.0, target=104.0, cost=0.0)
        self.assertAlmostEqual(out2.plan[5], 95.0 / 100.0 - 1, msg="Kurslücke: Verkauf zur Eröffnung")
        self.assertLessEqual(out2.plan_drawdown[5], 94.0 / 100.0 - 1 + 1e-12)

    def test_not_filled_above_the_limit(self):
        h = self._flat()
        t = 4
        h.open[t + 1], h.low[t + 1], h.high[t + 1] = 101.0, 100.5, 102.0
        out = rb.simulate(h, t, entry=100.2, stop=98.0, target=104.0, cost=0.0)
        self.assertFalse(out.filled)
        self.assertEqual(out.plan, {})

    def test_horizon_beyond_data_is_missing(self):
        h = self._flat(n=12)
        out = rb.simulate(h, 5, entry=None, stop=None, target=None, cost=0.0)
        self.assertTrue(out.filled)
        self.assertIsNotNone(out.hold[5])
        self.assertIsNone(out.hold[10])
        self.assertIsNone(out.hold[252])


class AggregateTests(unittest.TestCase):
    def test_episodes_count_once(self):
        status = np.array([0, 1, 3, 3, 3, 1, 3, 2, 2, 3], dtype=np.int8)
        self.assertEqual(rb.episode_starts(status, 3).tolist(), [2, 6, 9])
        self.assertEqual(rb.episode_starts(status, 2).tolist(), [7])

    def test_stats(self):
        s = rb.stats([0.02, -0.01, 0.03, None, float("nan")])
        self.assertEqual(s["n"], 3)
        self.assertFalse(s["belegt"])
        self.assertAlmostEqual(s["mittel"], 0.04 / 3, places=5)
        self.assertAlmostEqual(s["treffer"], 2 / 3, places=4)
        self.assertAlmostEqual(s["verlust_mittel"], -0.01, places=5)
        self.assertEqual(rb.stats([])["n"], 0)
        self.assertTrue(rb.stats([0.01] * rb.MIN_CASES)["belegt"])

    def test_compute_payload_shape_and_independent_cases(self):
        close = trending(220)
        vol = np.full(len(close), 1e6)
        vol[60::15] = 3e6  # wiederholt hoher Umsatz: mehrere Signalfolgen
        stock = history(close, volume=vol)
        result = rb.compute(universe(220, extra=[stock]), costs=None, cutoff_day=int(stock.days[-1]))
        p = result.payload
        self.assertEqual(p["version"], rb.VERSION)
        self.assertEqual(p["regel"], tp.RULE_VERSION)
        self.assertEqual(set(p["status"]), {"kaufsignal", "beobachten", "vergleich"})
        kauf = p["status"]["kaufsignal"]
        self.assertEqual(set(kauf["plan"]), {"1", "5", "10", "20"})
        self.assertEqual(set(kauf["halten"]), {str(h) for h in rb.HOLD_HORIZONS})
        self.assertLessEqual(kauf["ausgefuehrt"], kauf["faelle"])
        status = result.statuses[stock.isin]
        self.assertEqual(kauf["faelle"] >= len(rb.episode_starts(status, 3)) - 1, True)
        own = result.per_stock[stock.isin]
        self.assertLessEqual(own["n"], len(rb.episode_starts(status, 3)))
        for name in ("kaufsignal", "vergleich"):
            for key, s in p["status"][name]["halten"].items():
                if s["n"]:
                    self.assertTrue(0.0 <= s["treffer"] <= 1.0)
                    self.assertTrue(math.isfinite(s["mittel"]))


if __name__ == "__main__":
    unittest.main()
