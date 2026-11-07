"""Daytrading vorbereiten (ab 1.22, Befund F22): Tageswerte, Kriterium orb-1, Rückrechnung mit Kosten – synthetische Kerzen."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from traktien.analytics import intraday_scan as ids

ROOT = Path(__file__).resolve().parents[2]
T0 = 1_793_871_000  # ein Handelstag, 09:00 Uhr


def day(prices: list[tuple[float, float, float, float, float]], start: int = T0) -> list[ids.Bar]:
    return [ids.Bar(start + 60 * i, o, h, l, c, v) for i, (o, h, l, c, v) in enumerate(prices)]


def quiet_day(n: int = 120, price: float = 100.0, volume: float = 1000.0) -> list[ids.Bar]:
    return day([(price, price + 0.2, price - 0.2, price, volume) for _ in range(n)])


def breakout_day(n: int = 120) -> list[ids.Bar]:
    """15 Minuten Spanne 99,5–100,5 mit hohem Umsatz seit Handelsbeginn, danach Ausbruch und Anstieg bis 104."""
    bars = [(100.0, 100.5, 99.5, 100.0, 2500.0) for _ in range(15)]
    bars += [(100.4, 101.2, 100.3, 101.0, 6000.0)]  # Ausbruch
    price = 101.0
    for _ in range(n - 16):
        price += 0.05
        bars.append((price - 0.05, price + 0.05, price - 0.1, price, 2500.0))
    return day(bars)


class IntradayScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.c = ids.Criteria()
        self.history = [ids.day_values(quiet_day(), self.c).cum_volume for _ in range(5)]

    def test_day_values_vwap_range_and_move(self):
        values = ids.day_values(breakout_day(), self.c)
        self.assertEqual((values.range_high, values.range_low), (100.5, 99.5))
        self.assertAlmostEqual(values.vwap[0], (100.5 + 99.5 + 100.0) / 3)
        self.assertGreater(values.move_pct[-1], 3.5)
        self.assertEqual(values.cum_volume[14], 37_500)

    def test_breakout_with_volume_gives_a_signal_and_quiet_day_none(self):
        signal = ids.first_signal(breakout_day(), self.c, self.history)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.minute, 15)
        self.assertEqual(signal.entry, 101.0)
        self.assertEqual(signal.stop, 99.5)
        self.assertAlmostEqual(signal.target, 101.0 + 2 * 1.5)
        self.assertGreaterEqual(signal.relative_volume, 2.0)
        self.assertIsNone(ids.first_signal(quiet_day(), self.c, self.history))
        self.assertIsNone(ids.first_signal(breakout_day(), self.c, []), "ohne Vergleichstage kein relativer Umsatz – kein Signal")

    def test_no_look_ahead_signal_depends_only_on_bars_until_then(self):
        full = breakout_day()
        cut = full[:16]
        self.assertEqual(ids.first_signal(full, self.c, self.history).minute, ids.first_signal(cut, self.c, self.history).minute)

    def test_trade_with_costs_and_backtest_summary(self):
        signal = ids.first_signal(breakout_day(), self.c, self.history)
        trade = ids.simulate(breakout_day(), signal, self.c)
        self.assertEqual(trade.outcome, "ziel")
        shares = 1000 // 101.0
        expected = shares * (104.0 * 0.999 - 101.0 * 1.001) - 2.0
        self.assertAlmostEqual(trade.net_eur, round(expected, 2), places=2)
        result = ids.backtest([quiet_day() for _ in range(5)] + [breakout_day(), quiet_day()], self.c, history_days=5)
        summary = result.summary()
        self.assertEqual((summary["tage"], summary["signale"], summary["trades"]), (7, 1, 1))
        self.assertFalse(summary["freigegeben"], "nie von selbst freigegeben")
        self.assertEqual(summary["ausgaenge"]["ziel"], 1)

    def test_stop_before_target_in_the_same_bar(self):
        bars = breakout_day()[:16] + day([(101.0, 104.0, 99.0, 100.0, 3000.0)], start=T0 + 16 * 60)
        signal = ids.first_signal(bars, self.c, self.history)
        self.assertEqual(ids.simulate(bars, signal, self.c).outcome, "stop", "vorsichtig: Stop zählt zuerst")

    def test_criteria_validation_and_shipped_configuration_is_switched_off(self):
        with self.assertRaises(ValueError):
            ids.Criteria.from_mapping({"spanne_minuten": 0})
        with self.assertRaises(ValueError):
            ids.Criteria.from_mapping({"chance_risiko": 50})
        config = yaml.safe_load((ROOT / "config" / "daytrading.yaml").read_text(encoding="utf-8"))
        self.assertIs(config["aktiv"], False, "keine Liste ohne Prüfung und Freigabe")
        self.assertEqual(config["quelle"], "keine")
        criteria = ids.Criteria.from_mapping(config["kriterium"])
        self.assertEqual(criteria.spanne_minuten, 15)
        self.assertGreaterEqual(config["freigabe"]["min_trades"], 50)


if __name__ == "__main__":
    unittest.main()
