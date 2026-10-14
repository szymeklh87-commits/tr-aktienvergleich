"""Signale je Aktie (signale-v1): Rechenregeln, Ampeln, Texte, Kalibrierung – mit SYNTHETISCHEN Kursen."""

from __future__ import annotations

import math
import unittest

import numpy as np

from traktien.analytics import signals as sg


def series(n=140, drift=0.002, noise=0.01, seed=1, start=100.0, volume=200_000.0, last_volume=None):
    rng = np.random.default_rng(seed)
    returns = drift + noise * rng.standard_normal(n)
    close = start * np.exp(np.cumsum(returns))
    vol = np.full(n, volume)
    if last_volume is not None:
        vol[-1] = last_volume
    days = np.arange(20000, 20000 + n)
    return days, close, vol


def stock(isin="X1", n=140, drift=0.002, noise=0.01, facts=None, unit_to_eur=1.0, **kw):
    days, close, vol = series(n=n, drift=drift, noise=noise, **kw)
    return sg.StockInput(
        isin=isin, days=days, open=close * 0.999, high=close * 1.01, low=close * 0.99, close=close, volume=vol,
        unit_to_eur=unit_to_eur, facts=facts, now_ts=float(days[-1]) * 86400 + 3600,
    )


def facts(target_factor=1.3, analysts=12, buy=(5, 5, 2, 0, 0), old=(3, 4, 5, 0, 0), close=None, sector="Technology", fpe=18.0):
    def row(month, counts):
        keys = ("stark_kaufen", "kaufen", "halten", "verkaufen", "stark_verkaufen")
        return {"monat": month, **dict(zip(keys, counts))}

    return {
        "analysten": {"anzahl": analysts, "ziel_mittel": close * target_factor, "ziel_tief": close * 0.9, "ziel_hoch": close * 1.8, "kurs": close,
                      "empfehlung_mittel": 1.8, "empfehlung": "buy", "kaufen_anteil": (buy[0] + buy[1]) / sum(buy)},
        "empfehlungen": [row("0m", buy), row("-1m", buy), row("-2m", old), row("-3m", old)],
        "urteile": [],
        "bewertung": {"kgv_erwartet": fpe, "peg": 0.9},
        "wachstum": {"gewinn_naechstes_jahr": 0.25, "umsatz_naechstes_jahr": 0.12},
        "finanzen": {"eigenkapitalrendite": 0.22, "nettomarge": 0.18, "verschuldung": 0.4, "free_cashflow_positiv": True},
        "risiko": {"hoch_52w": close * 1.02},
        "branche": {"sektor": sector},
    }


class TechnicalTests(unittest.TestCase):
    def test_rising_stock_with_volume_spike_scores_high_and_falling_low(self):
        up = sg.tech_series(None, None, None, *series(drift=0.004, noise=0.006, last_volume=600_000.0)[1:])
        comps = sg.short_component_series(up)
        self.assertAlmostEqual(comps["volumen"][-1], 50 + 25 * math.log2(3.0), places=4)
        self.assertGreater(comps["schwung"][-1], 70)
        self.assertGreater(comps["trendlage"][-1], 99)
        down = sg.tech_series(None, None, None, *series(drift=-0.004, noise=0.006, seed=2)[1:])
        dcomps = sg.short_component_series(down)
        self.assertLess(dcomps["schwung"][-1], 30)
        self.assertLess(dcomps["trendlage"][-1], 1)

    def test_rsi_streak_and_breakout(self):
        close = np.array([10.0] * 20 + [10.0 + 0.1 * k for k in range(1, 11)])
        ts = sg.tech_series(None, None, None, close, np.full(len(close), 1000.0))
        self.assertEqual(int(ts.streak[-1]), 10)
        self.assertEqual(float(ts.rsi[-1]), 100.0)
        comps = sg.short_component_series(ts)
        self.assertEqual(comps["ausbruch"][-1], 100.0)
        self.assertLess(comps["rsi"][-1], 50, "RSI 100 = überhitzt, wenige Punkte")

    def test_zero_or_missing_volume_is_unknown_not_low(self):
        days, close, vol = series()
        vol[:] = 0.0
        ts = sg.tech_series(None, None, None, close, vol)
        self.assertTrue(np.isnan(ts.rvol[-1]))
        self.assertTrue(np.isnan(sg.short_component_series(ts)["volumen"][-1]))

    def test_technical_score_needs_four_signals(self):
        comps = {k: np.array([np.nan, 60.0]) for k in sg.SHORT_WEIGHTS}
        comps["volumen"] = np.array([np.nan, np.nan])
        comps["rsi"] = np.array([np.nan, np.nan])
        score = sg.technical_score_series(comps)
        self.assertTrue(np.isnan(score[0]))
        self.assertAlmostEqual(score[1], 60.0)


class EvaluateTests(unittest.TestCase):
    def batch(self, items):
        return {r.isin: r for r in sg.compute_all(items).results}

    def universe(self, extra):
        """Genug Vergleichsaktien für Perzentile (≥ 20 Werte je Kennzahl)."""
        items = list(extra)
        for k in range(30):
            item = stock(isin=f"V{k}", drift=0.001 * (k % 5 - 2), seed=100 + k)
            item.facts = facts(close=float(item.close[-1]), target_factor=1.0 + 0.02 * (k % 7), fpe=10.0 + k, analysts=5)
            items.append(item)
        return items

    def test_strong_stock_gets_two_green_lights_with_reasons(self):
        item = stock(isin="GUT", drift=0.004, noise=0.006, last_volume=500_000.0)
        item.facts = facts(close=float(item.close[-1]), target_factor=1.30, fpe=12.0)
        result = self.batch(self.universe([item]))["GUT"]
        self.assertEqual(result.short_light, "gruen", result.short)
        self.assertEqual(result.long_light, "gruen", (result.long, result.upside))
        self.assertTrue(result.both_green)
        self.assertAlmostEqual(result.upside, 0.30, places=4)
        target = next(c for c in result.components if c.key == "kursziel")
        self.assertIn("+30 %", target.text)
        self.assertIn("12 Analysten", target.text)
        self.assertIn("83 % Kaufen", target.text)
        self.assertEqual(target.tone, 1)

    def test_target_below_price_is_red_long_term(self):
        item = stock(isin="ZIEL", drift=0.003)
        item.facts = facts(close=float(item.close[-1]), target_factor=0.85)
        result = self.batch(self.universe([item]))["ZIEL"]
        self.assertEqual(result.long_light, "rot")
        self.assertEqual(result.long_reason, "Kursziel unter dem aktuellen Kurs")

    def test_few_analysts_count_less(self):
        one = stock(isin="EINS", drift=0.001)
        one.facts = facts(close=float(one.close[-1]), target_factor=2.6, analysts=1)
        many = stock(isin="VIELE", drift=0.001)
        many.facts = facts(close=float(many.close[-1]), target_factor=2.6, analysts=20)
        results = self.batch(self.universe([one, many]))
        p_one = next(c.points for c in results["EINS"].components if c.key == "kursziel")
        p_many = next(c.points for c in results["VIELE"].components if c.key == "kursziel")
        self.assertLess(p_one, p_many)
        self.assertNotEqual(results["EINS"].long_light, "gruen", "1 Analyst reicht nicht für Grün")

    def test_pence_targets_are_scaled_and_foreign_units_rejected(self):
        item = stock(isin="GBP", drift=0.002)
        close = float(item.close[-1])
        item.facts = facts(close=close / 100.0, target_factor=1.2)  # Kursziel in GBP, Kurse in GBp
        result = self.batch(self.universe([item]))["GBP"]
        self.assertAlmostEqual(result.upside, 0.2, places=3)
        odd = stock(isin="ODD", drift=0.002)
        odd.facts = facts(close=float(odd.close[-1]) * 7.0, target_factor=1.2)  # keine erkennbare Einheit
        self.assertIsNone(self.batch(self.universe([odd]))["ODD"].upside)

    def test_illiquid_stock_is_grey_short_term(self):
        item = stock(isin="DUENN", drift=0.004, volume=50.0)
        result = self.batch(self.universe([item]))["DUENN"]
        self.assertEqual(result.short_light, "grau")
        self.assertIn("Umsatz", result.short_reason)
        self.assertIsNone(result.probability)

    def test_without_facts_long_term_is_grey_and_nothing_is_invented(self):
        item = stock(isin="NACKT", n=60)
        result = self.batch([item])["NACKT"]
        self.assertEqual(result.long_light, "grau")
        self.assertIsNone(result.upside)
        self.assertTrue(all(c.points is None for c in result.components if c.key in ("kursziel", "bewertung", "wachstum")))

    def test_news_and_community_feed_short_term(self):
        item = stock(isin="NEWS", drift=0.002)
        now = item.now_ts
        item.news = [{"titel": "Company beats estimates, record profit", "zeit": now - 3600, "tendenz": 1},
                     {"titel": "Analyst upgrades stock", "zeit": now - 7200, "tendenz": 1}]
        item.community = {"bullish": 18, "bearish": 2, "beitraege": 30, "je_tag": 12.0}
        result = self.batch(self.universe([item]))["NEWS"]
        news = next(c for c in result.components if c.key == "nachrichten")
        comm = next(c for c in result.components if c.key == "community")
        self.assertGreater(news.points, 70)
        self.assertIn("2 positiv", news.text)
        self.assertGreater(comm.points, 70)
        self.assertIn("90 % bullish", comm.text)


class CalibrationTests(unittest.TestCase):
    def test_counts_hit_rates_and_base_rate(self):
        hist = []
        for k in range(40):
            days, close, vol = series(n=150, drift=0.002 if k % 2 else -0.001, seed=k)
            ts = sg.tech_series(None, None, None, close, vol)
            tech = sg.technical_score_series(sg.short_component_series(ts))
            hist.append((days, close, tech, True))
        cal = sg.calibrate(hist)
        self.assertGreater(cal.samples, 3000)
        self.assertEqual(sum(cal.n), cal.samples)
        self.assertTrue(0 <= cal.base_up5 <= 1)
        self.assertEqual(cal.stocks, 40)
        self.assertEqual(cal.bucket(65.0), 4)
        self.assertEqual(cal.bucket(100.0), len(cal.edges) - 2)
        self.assertIsNone(cal.bucket(None))

    def test_illiquid_stocks_are_not_counted(self):
        days, close, vol = series()
        ts = sg.tech_series(None, None, None, close, vol)
        tech = sg.technical_score_series(sg.short_component_series(ts))
        self.assertEqual(sg.calibrate([(days, close, tech, False)]).samples, 0)


class FormatTests(unittest.TestCase):
    def test_german_formats(self):
        self.assertEqual(sg.pct_de(0.1234), "+12,3 %")
        self.assertEqual(sg.pct_de(-0.05, 0), "−5 %")
        self.assertEqual(sg.num_de(2.25, 1), "2,2")
        self.assertEqual(sg.pct_de(None), "–")


if __name__ == "__main__":
    unittest.main()
