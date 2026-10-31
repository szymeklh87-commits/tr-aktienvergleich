"""Bericht je Spielgelddepot (Abschnitte 14, 21, 22): Formeln, nicht definierte Kennzahlen, Vergleich, Bootstrap, Steuern,
Ausführungen mit FIFO-Losen. Alle Erwartungswerte von Hand nachgerechnet."""

from __future__ import annotations

import datetime as dt
import math
import unittest

import numpy as np

from traktien.aktienpilot import bericht as ber
from traktien.aktienpilot.buchhaltung import Event, replay
from traktien.aktienpilot.config import ReleaseConfig, TaxConfig
from traktien.util.timeutil import date_to_day

D0 = date_to_day(dt.date(2026, 3, 2))  # Montag


def tage(n: int, start: int = D0) -> list[int]:
    """n Werktage ab ``start``."""
    out, d = [], start
    while len(out) < n:
        if dt.date.fromordinal(dt.date(1970, 1, 1).toordinal() + d).weekday() < 5:
            out.append(d)
        d += 1
    return out


def werte_aus(rets: list[float], start: float = 10_000.0, days: list[int] | None = None, guthaben: float = 0.0) -> list[dict]:
    days = days or tage(len(rets) + 1)
    v = start
    out = [{"tag": days[0], "gesamt_eur": v, "guthaben_eur": guthaben}]
    for d, r in zip(days[1:], rets):
        v *= 1.0 + r
        out.append({"tag": d, "gesamt_eur": v, "guthaben_eur": guthaben})
    return out


SEQ = [0]


def ev(tag: int, typ: str, isin: str | None = None, stueck: float | None = None, betrag: float = 0.0, gebuehr: float = 0.0, owner: str = "s1") -> Event:
    SEQ[0] += 1
    return Event(f"e{SEQ[0]}", "t", SEQ[0], "2026-03-02T22:00:00Z", tag, typ, isin=isin, stueck=stueck, kurs=None if stueck is None else abs(betrag) / stueck,
                 waehrung="EUR", fx_eur=1.0, fx_quelle=None, betrag_eur=betrag, gebuehren_eur=gebuehr, nutzlast={"zuordnung": owner})


def bericht(werte, *, events=(), fluesse=None, zins=None, vergleiche=(), historisch=False, synthetisch=False, regeln=(), offen=(), depot="f-test",
            fondsart=lambda isin: "Aktie"):
    book = replay("t", list(events))
    return ber.berechnen(depot_id=depot, werte=werte, fluesse=fluesse or {}, book=book, events=list(events), startkapital=10_000.0, historisch=historisch,
                         synthetisch=synthetisch, regeln=list(regeln), vergleiche=list(vergleiche), zins_kurs=zins, zins_quelle=None if zins is None else "Geldmarkt-ETF",
                         fondsart=fondsart, steuer_cfg=TaxConfig(), freigabe_cfg=ReleaseConfig(), offen=list(offen), datenstand="s-1", ap_version="t")


class RenditeTests(unittest.TestCase):
    def test_flows_are_removed_and_incomplete_days_are_no_measurement_points(self) -> None:
        d = tage(3)
        werte = [{"tag": d[0], "gesamt_eur": 100.0}, {"tag": d[1], "gesamt_eur": 60.0, "vollstaendig": False}, {"tag": d[2], "gesamt_eur": 115.0}]
        days, rets, skipped = ber.renditen(werte, {d[2]: 5.0})
        self.assertEqual((days, skipped), ([d[0], d[2]], 1))
        self.assertAlmostEqual(float(rets[0]), (115.0 - 5.0) / 100.0 - 1.0)
        self.assertAlmostEqual(ber.zeitgewichtet(werte, {d[2]: 5.0}), 0.10)
        self.assertIsNone(ber.renditen([{"tag": d[0], "gesamt_eur": 0.0}, {"tag": d[1], "gesamt_eur": 1.0}], {}))

    def test_drawdown_on_return_index_ignores_deposits(self) -> None:
        d = tage(4)
        werte = [{"tag": d[0], "gesamt_eur": 100.0}, {"tag": d[1], "gesamt_eur": 80.0}, {"tag": d[2], "gesamt_eur": 1080.0}, {"tag": d[3], "gesamt_eur": 1100.0}]
        # Einzahlung 1.000 am dritten Tag: Index 1 → 0,8 → 1,0 → 1,0185…; Rückgang 20 %, nicht 0 %
        self.assertAlmostEqual(ber.max_rueckgang(werte, {d[2]: 1000.0}), 0.20)


class KennzahlTests(unittest.TestCase):
    def test_formulas_match_hand_calculation(self) -> None:
        rets = [0.01, -0.02, 0.015, 0.005, -0.01] * 6  # 30 Tagesrenditen
        werte = werte_aus(rets, guthaben=2_500.0)
        zins_tag = 0.0001
        prices = {werte[0]["tag"]: 100.0}
        p = 100.0
        for w in werte[1:]:
            p *= 1 + zins_tag
            prices[w["tag"]] = p
        b = bericht(werte, zins=lambda day: prices.get(day))
        k = b["kennzahlen"]
        r = np.asarray(rets)
        self.assertAlmostEqual(k["rendite_pct"], round(100 * (np.prod(1 + r) - 1), 2))
        self.assertAlmostEqual(k["volatilitaet_pct"], round(100 * np.std(r, ddof=1) * math.sqrt(252), 2))
        ex = r - zins_tag
        self.assertAlmostEqual(k["sharpe"], round(ex.mean() / ex.std(ddof=1) * math.sqrt(252), 2))
        self.assertAlmostEqual(k["sortino"], round(ex.mean() / math.sqrt(np.mean(np.minimum(ex, 0) ** 2)) * math.sqrt(252), 2))
        idx = np.concatenate([[1.0], np.cumprod(1 + r)])
        self.assertAlmostEqual(k["max_rueckgang_pct"], round(100 * float(np.max(1 - idx / np.maximum.accumulate(idx))), 2))
        self.assertAlmostEqual(k["kapitalbindung_pct"], round(100 * np.mean([(w["gesamt_eur"] - 2_500.0) / w["gesamt_eur"] for w in werte]), 1))
        self.assertIsNone(k["cagr_pct"])
        self.assertIn("unter einem Jahr", b["nicht_definiert"]["cagr_pct"])
        self.assertEqual(b["zeitraum"]["renditetage"], 30)
        self.assertEqual(b["rueckgang"]["pct"][0], 0.0)
        self.assertEqual(len(b["rueckgang"]["tag"]), 31)

    def test_cagr_from_one_year(self) -> None:
        d = [D0, D0 + 400]
        b = bericht([{"tag": d[0], "gesamt_eur": 10_000.0}, {"tag": d[1], "gesamt_eur": 12_100.0}])
        self.assertAlmostEqual(b["kennzahlen"]["cagr_pct"], round(100 * (1.21 ** (365.25 / 400) - 1), 2))

    def test_undefined_values_have_reasons_never_zero(self) -> None:
        b = bericht(werte_aus([0.01] * 5))
        k, nd = b["kennzahlen"], b["nicht_definiert"]
        for key in ("volatilitaet_pct", "sharpe", "sortino", "trefferquote_pct", "profitfaktor", "gewinn_mittel_eur", "verlust_mittel_eur"):
            self.assertIsNone(k[key], key)
            self.assertTrue(nd[key], key)
        self.assertIn("risikofreier Zins nicht verfügbar", nd["sharpe"])
        self.assertEqual(b["bootstrap"]["grund"], "zu wenige Tagesrenditen (5 < 20)")
        self.assertIn("zu kurz", b["haelften"]["grund"])
        self.assertEqual(bericht([{"tag": D0, "gesamt_eur": 10_000.0}])["grund"], "noch keine zwei vollständigen Bewertungstage")

    def test_idle_depot_has_no_sharpe_and_missing_rate_prices_are_reported(self) -> None:
        werte = werte_aus([0.0] * 25)
        b = bericht(werte, zins=lambda day: 100.0 + (day - D0) * 0.01)
        self.assertIsNone(b["kennzahlen"]["sharpe"])
        self.assertEqual(b["nicht_definiert"]["sharpe"], "Depotwert ohne Schwankung (nichts investiert)")
        self.assertEqual(b["kennzahlen"]["max_rueckgang_pct"], 0.0)
        b = bericht(werte_aus([0.01, -0.01] * 12), zins=lambda day: None if day == D0 else 100.0)
        self.assertIn("fehlt an 1 von 25 Bewertungstagen", b["nicht_definiert"]["sharpe"])


class TradeTests(unittest.TestCase):
    def test_hit_rate_profit_factor_and_core_trades_excluded(self) -> None:
        d = tage(8)
        events = [ev(d[0], "einzahlung", betrag=10_000.0, owner="pilot"),
                  ev(d[1], "kauf", "AAA", 10, -1_001.0, 1.0), ev(d[2], "verkauf", "AAA", 10, 1_199.0, 1.0),   # +198
                  ev(d[1], "kauf", "BBB", 10, -1_001.0, 1.0), ev(d[3], "verkauf", "BBB", 10, 900.0, 1.0),     # −101
                  ev(d[1], "kauf", "CCC", 10, -1_001.0, 1.0), ev(d[4], "verkauf", "CCC", 5, 600.0, 1.0),      # +99,5
                  ev(d[1], "kauf", "ETF", 10, -1_001.0, 1.0, owner="kern"), ev(d[5], "verkauf", "ETF", 10, 500.0, 1.0, owner="kern")]
        b = bericht(werte_aus([0.0] * 7, days=d), events=events)
        k = b["kennzahlen"]
        self.assertEqual((k["trades"], k["trades_unbekannt"]), (3, 0))
        self.assertAlmostEqual(k["trefferquote_pct"], round(100 * 2 / 3, 1))
        self.assertAlmostEqual(k["profitfaktor"], round((198.0 + 99.5) / 101.0, 2))
        self.assertAlmostEqual(k["gewinn_mittel_eur"], round((198.0 + 99.5) / 2, 2))
        self.assertAlmostEqual(k["verlust_mittel_eur"], -101.0)
        self.assertEqual(k["ausfuehrungen"], 8)
        self.assertEqual(k["kosten_eur"], 8.0)
        # nur Gewinne: Profitfaktor nicht definiert (kein erfundener Wert)
        b = bericht(werte_aus([0.0] * 7, days=d), events=events[:3])
        self.assertIsNone(b["kennzahlen"]["profitfaktor"])
        self.assertEqual(b["nicht_definiert"]["profitfaktor"], "kein Verlusttrade – Profitfaktor nicht definiert")

    def test_executions_list_fifo_lots_of_each_sale(self) -> None:
        d = tage(5)
        events = [ev(d[0], "kauf", "AAA", 10, -1_000.0), ev(d[1], "kauf", "AAA", 10, -1_200.0), ev(d[2], "verkauf", "AAA", 15, 1_950.0)]
        rows = ber.ausfuehrungen(events, replay("t", events))
        self.assertEqual([r["art"] for r in rows], ["kauf", "kauf", "verkauf"])
        sale = rows[2]
        self.assertEqual(sale["lose"], [{"kauf": ber._datum(d[0]), "stueck": 10.0, "kosten_eur": 1000.0},
                                        {"kauf": ber._datum(d[1]), "stueck": 5.0, "kosten_eur": 600.0}])
        self.assertAlmostEqual(sale["ergebnis_eur"], 350.0)
        self.assertIsNone(rows[0]["lose"])


class MonatTests(unittest.TestCase):
    def test_monthly_returns_chain_daily_returns_and_flag_partial_months(self) -> None:
        start = date_to_day(dt.date(2026, 3, 30))  # Montag
        days = tage(30, start)
        rets = [0.01] * 29
        b = bericht(werte_aus(rets, days=days))
        monate = {m["monat"]: m for m in b["monate"]}
        self.assertEqual(list(monate), ["2026-03", "2026-04", "2026-05"])
        self.assertAlmostEqual(monate["2026-04"]["rendite_pct"], round(100 * (1.01 ** 22 - 1), 2))
        self.assertTrue(monate["2026-03"]["angebrochen"])
        self.assertFalse(monate["2026-04"]["angebrochen"])
        self.assertTrue(monate["2026-05"]["angebrochen"])


class VergleichTests(unittest.TestCase):
    def test_comparison_over_common_period_when_benchmark_starts_later(self) -> None:
        d = tage(6)
        own = werte_aus([0.10, 0.0, 0.10, 0.0, -0.05], days=d)
        bench = werte_aus([0.02, 0.0, 0.03], days=d[2:])
        b = bericht(own, vergleiche=[("v-welt", "Welt", bench, {})])
        v = b["vergleiche"][0]
        self.assertEqual((v["von"], v["bis"]), (ber._datum(d[2]), ber._datum(d[5])))
        self.assertAlmostEqual(v["eigen_pct"], round(100 * (1.10 * 0.95 - 1), 2))
        self.assertAlmostEqual(v["vergleich_pct"], round(100 * (1.02 * 1.03 - 1), 2))
        self.assertAlmostEqual(v["abstand_pp"], round(100 * (1.10 * 0.95 - 1.02 * 1.03), 2))
        hurdle = {h["id"]: h for h in b["huerden"]}["benchmark"]
        self.assertEqual((hurdle["wert"], hurdle["erfuellt"]), (v["abstand_pp"], False))  # 4,5 % gegen 5,06 %

    def test_hurdles_count_only_forward_paper(self) -> None:
        werte = werte_aus([0.001] * 40)
        fwd = {h["id"]: h for h in bericht(werte)["huerden"]}
        hist = {h["id"]: h for h in bericht(werte, historisch=True)["huerden"]}
        demo = {h["id"]: h for h in bericht(werte, synthetisch=True)["huerden"]}
        self.assertTrue(fwd["sitzungen"]["erfuellt"])
        self.assertFalse(fwd["trades"]["erfuellt"])
        self.assertIsNone(hist["sitzungen"]["erfuellt"])
        self.assertIn("historische Simulation", hist["sitzungen"]["grund"])
        self.assertIsNone(demo["trades"]["erfuellt"])
        self.assertIsNone(fwd["profitfaktor"]["erfuellt"])
        self.assertIsNone(fwd["benchmark"]["erfuellt"])


class BootstrapTests(unittest.TestCase):
    def test_reproducible_with_seed_from_depot_id(self) -> None:
        rng = np.random.default_rng(1)
        werte = werte_aus(list(rng.normal(0.0005, 0.01, 120)))
        a, b, c = bericht(werte, depot="f-a")["bootstrap"], bericht(werte, depot="f-a")["bootstrap"], bericht(werte, depot="f-b")["bootstrap"]
        self.assertEqual(a, b)
        self.assertNotEqual(a["startwert"], c["startwert"])
        self.assertEqual((a["pfade"], a["block"]), (1000, 5))
        self.assertLessEqual(a["rendite_pct"]["p5"], a["rendite_pct"]["p50"])
        self.assertLessEqual(a["rendite_pct"]["p50"], a["rendite_pct"]["p95"])
        self.assertGreaterEqual(a["max_rueckgang_pct"]["p5"], 0.0)


class WarnungTests(unittest.TestCase):
    def test_short_period_small_sample_many_conditions_and_half_drop(self) -> None:
        d = tage(50)
        events = [ev(d[1], "kauf", "AAA", 1, -101.0, 1.0), ev(d[2], "verkauf", "AAA", 1, 120.0, 1.0)]
        regel = {"id": "r-x", "version": 1, "filter": {"und": [{"kennzahl": {"id": "rsi"}, "op": "<", "wert": 30}] * 9}}
        rets = [0.004] * 25 + [-0.004] * 24
        b = bericht(werte_aus(rets, days=d), events=events, regeln=[regel])
        text = " ".join(b["warnungen"])
        self.assertIn("Kurzer Zeitraum (50 Bewertungstage)", text)
        self.assertIn("Kleine Stichprobe: 1 abgeschlossene Trades", text)
        self.assertIn("Viele Bedingungen und Sortierkriterien (9)", text)
        self.assertIn("zweite Hälfte", text)
        self.assertIn("nicht möglich", b["walk_forward"])
        self.assertEqual(b["reproduzierbar"]["regeln"], ["r-x@1"])


class SteuerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arten = {"FONDS": "Aktienfonds", "GELD": "sonstiger Fonds"}

    def _steuer(self, events, offen=(), ende=None, fonds=False):
        book = replay("t", events)
        return ber.steuern(book.realized, lambda i: self.arten.get(i, "Aktie"), TaxConfig(), list(offen), ende, fonds)

    def test_stock_losses_only_offset_stock_gains_and_fund_partial_exemption(self) -> None:
        y = date_to_day(dt.date(2026, 6, 1))
        events = [ev(y, "kauf", "AKT", 1, -1_000.0), ev(y + 1, "verkauf", "AKT", 1, 500.0),          # Aktie −500
                  ev(y, "kauf", "FONDS", 1, -1_000.0), ev(y + 2, "verkauf", "FONDS", 1, 4_000.0)]    # Fonds +3.000 → 70 % = 2.100
        j = self._steuer(events)["jahre"][0]
        self.assertEqual((j["aktien_verluste_eur"], j["fonds_ergebnis_eur"]), (-500.0, 2100.0))
        self.assertEqual(j["verlustvortrag_aktien_eur"], -500.0)  # nicht mit dem Fondsgewinn verrechnet
        self.assertEqual((j["pauschbetrag_genutzt_eur"], j["steuerpflichtig_eur"]), (1000.0, 1100.0))
        self.assertAlmostEqual(j["steuer_eur"], round(1100.0 * 0.25 * 1.055, 2))

    def test_general_losses_offset_stock_gains_and_carry_forward_to_next_year(self) -> None:
        y1 = date_to_day(dt.date(2026, 6, 1))
        y2 = date_to_day(dt.date(2027, 6, 1))
        events = [ev(y1, "kauf", "GELD", 1, -3_000.0), ev(y1 + 1, "verkauf", "GELD", 1, 1_000.0),    # allgemein −2.000
                  ev(y1, "kauf", "AKT", 1, -1_000.0), ev(y1 + 2, "verkauf", "AKT", 1, 2_500.0),      # Aktie +1.500
                  ev(y2, "kauf", "AKT", 1, -1_000.0), ev(y2 + 1, "verkauf", "AKT", 1, 3_000.0)]      # Aktie +2.000 im Folgejahr
        j1, j2 = self._steuer(events)["jahre"]
        self.assertEqual((j1["steuerpflichtig_eur"], j1["verlustvortrag_allgemein_eur"]), (0.0, -500.0))
        self.assertEqual((j2["steuerpflichtig_eur"], j2["pauschbetrag_genutzt_eur"]), (500.0, 1000.0))

    def test_assumed_sale_at_end_is_separate_and_vorabpauschale_is_flagged(self) -> None:
        y = date_to_day(dt.date(2026, 6, 1))
        events = [ev(y, "kauf", "AKT", 1, -1_000.0), ev(y + 1, "verkauf", "AKT", 1, 1_800.0)]  # +800, unter dem Pauschbetrag
        out = self._steuer(events, offen=[("AKT2", 1_200.0), ("AKT3", None)], ende=y + 5, fonds=True)
        self.assertEqual(out["jahre"][0]["steuer_eur"], 0.0)
        self.assertAlmostEqual(out["verkauf_am_ende"]["zusaetzliche_steuer_eur"], round((800.0 + 1_200.0 - 1_000.0) * 0.26375, 2))
        self.assertEqual(out["verkauf_am_ende"]["unbekannte_kosten"], 1)
        self.assertTrue(any("Vorabpauschale nicht berechnet: Basiszins für 2026" in h for h in out["hinweise"]))
        self.assertTrue(any("26,375 %" in h for h in out["hinweise"]))


if __name__ == "__main__":
    unittest.main()
