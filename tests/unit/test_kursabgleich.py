"""Kursabgleich mit den Kursarchiven der Börsen (ab 1.20.0): Quellen lesen, Auswahlregel, Übernahme, Nachweis.

Alle Werte sind synthetisch; die Formate der Quellen folgen den echten Dateien (Notierungsarchiv der GPW mit Spalten wie
„Kurs zamknięcia“ und „Wolumen obrotu (w szt.)“, NOCP-Historie von Nasdaq, Tageskerzen von TMX).
"""

from __future__ import annotations

import unittest
from collections import Counter

import numpy as np

from traktien.analytics import kursabgleich as ka
from traktien.analytics.quality import SplitEvent
from traktien.jobs import kursabgleich_lauf as lauf
from traktien.providers import boersen
from traktien.providers.boersen import OfficialBar

GPW_HTML = """<html><body><table class="table">
<tr><th>Nazwa</th><th>Kod ISIN</th><th>Waluta</th><th>Kurs otwarcia</th><th>Kurs max</th><th>Kurs min</th><th>Kurs zamknięcia</th>
<th>Zmiana kursu %</th><th>Wolumen obrotu (w szt.)</th><th>Liczba transakcji</th><th>Wartość obrotu (w tys.)</th>
<th>Liczba otwartych pozycji</th><th>Wartość nominalna</th></tr>
<tr><td>ALFA</td><td>PLALFA000016</td><td>PLN</td><td>12,10</td><td>12,50</td><td>12,00</td><td>12,34</td><td>1,98</td><td>1&nbsp;250</td><td>17</td><td>15,40</td><td>0</td><td>0,10</td></tr>
<tr><td>BETA</td><td>PLBETA000013</td><td>PLN</td><td>0,00</td><td>0,00</td><td>0,00</td><td>4,560</td><td>0,00</td><td>0</td><td>0</td><td>0,00</td><td>0</td><td>1,00</td></tr>
<tr><td>Kein Wert</td><td>KEINEISIN</td><td>PLN</td><td>1</td><td>1</td><td>1</td><td>1</td><td>0</td><td>1</td><td>1</td><td>1</td><td>0</td><td>1</td></tr>
</table></body></html>"""


def series(n=40, start=1000, base=10.0, step=0.1):
    days = np.arange(start, start + n, dtype=np.int64)
    close = np.round(base + step * np.arange(n), 2)
    return days, close


def official_from(days, close, volume=1000.0, decimals=2, skip=(), override=None):
    out = {}
    for k, d in enumerate(days.tolist()):
        if k in skip:
            continue
        c, v = float(close[k]), volume
        if override and k in override:
            c, v = override[k]
        out[int(d)] = OfficialBar(day=int(d), close=c, volume=v, decimals=decimals)
    return out


class SourceParsingTests(unittest.TestCase):
    def test_gpw_archive_rows_with_ohlc_volume_and_decimals(self):
        status, bars, info = boersen.parse_gpw_html(GPW_HTML, 20000)
        self.assertEqual(status, "ok")
        self.assertEqual(set(bars), {"PLALFA000016", "PLBETA000013"})
        a = bars["PLALFA000016"]
        self.assertEqual((a.open, a.high, a.low, a.close, a.volume, a.trades, a.decimals), (12.1, 12.5, 12.0, 12.34, 1250.0, 17.0, 2))
        b = bars["PLBETA000013"]
        # Tag ohne Umsatz: Eröffnung, Hoch und Tief 0,00 gelten als nicht vorhanden, der Schlusskurs bleibt
        self.assertEqual((b.open, b.high, b.low, b.close, b.volume, b.decimals), (None, None, None, 4.56, 0.0, 3))
        self.assertEqual(info["PLALFA000016"], {"name": "ALFA", "currency": "PLN"})

    def test_header_map_does_not_take_nominal_value_as_low(self):
        header = ["Nazwa", "Kod ISIN", "Waluta", "Kurs otwarcia", "Kurs max", "Kurs min", "Kurs zamknięcia", "Zmiana kursu %",
                  "Wolumen obrotu (w szt.)", "Liczba transakcji", "Wartość obrotu (w tys.)", "Liczba otwartych pozycji", "Wartość nominalna"]
        cols = boersen._header_map(header)
        self.assertEqual(cols["low"], 5)
        self.assertEqual(cols["close"], 6)
        self.assertEqual(cols["volume"], 8)

    def test_newconnect_table_with_numbers(self):
        table = [["Statystyka"], ["Nazwa", "ISIN", "Kurs otwarcia", "Kurs maksymalny", "Kurs minimalny", "Kurs zamknięcia", "Wolumen"],
                 ["GAMMA", "PLGAMMA00019", 1.5, 1.6, 1.4, 1.55, 300]]
        status, bars, _ = boersen.parse_table(table, 20001)
        self.assertEqual(status, "ok")
        g = bars["PLGAMMA00019"]
        self.assertEqual((g.open, g.high, g.low, g.close, g.volume, g.decimals), (1.5, 1.6, 1.4, 1.55, 300.0, 2))

    def test_decimals(self):
        self.assertEqual(boersen.decimals_of_text("1 234,560"), 3)
        self.assertEqual(boersen.decimals_of_text("$0.4550"), 4)
        self.assertEqual(boersen.decimals_of_text("12"), 0)
        self.assertEqual(boersen.decimals_of_number(12.340000152587890625), 2)
        self.assertEqual(boersen.decimals_of_number(0.455), 3)

    def test_nocp_history_any_field_names(self):
        payload = {"data": {"nocp": {"nocpTable": [{"date": "10/29/2026", "price": "$1.2345"}, {"date": "10/30/2026", "price": "$1.25"}]}}}
        bars = boersen.parse_nocp(payload)
        self.assertEqual(len(bars), 2)
        day = boersen.day_of(__import__("datetime").date(2026, 10, 29))
        self.assertEqual((bars[day].close, bars[day].decimals), (1.2345, 4))

    def test_tmx_symbols_and_exchange(self):
        self.assertEqual(boersen.tmx_symbol("ABC-A.TO"), "ABC.A")
        self.assertEqual(boersen.tmx_symbol("XYZ.V"), "XYZ")
        self.assertEqual(boersen.tmx_symbol("REIT-UN.TO"), "REIT.UN")
        self.assertTrue(boersen.tmx_exchange_matches("XTSX", "TSX Venture Exchange"))
        self.assertFalse(boersen.tmx_exchange_matches("XTSE", "TSX Venture Exchange"))
        self.assertTrue(boersen.tmx_exchange_matches("XTSE", "Toronto Stock Exchange"))

    def test_tmx_rows(self):
        items = [{"dateTime": "2026-10-29T00:00:00", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05, "volume": 1000},
                 {"dateTime": "2026-10-30", "close": 0, "volume": 0}]
        rows = boersen.tmx_rows(items, "dateTime", {"close": "close", "open": "open", "high": "high", "low": "low", "volume": "volume"}, 0, 99999)
        self.assertEqual(len(rows), 1)
        self.assertEqual(next(iter(rows.values())).close, 1.05)

    def test_cse_daily_market_summary(self):
        text = ("CSE Daily Market Summary\n\nStock\tSymbol\tVol(00s)\tHigh\tLow\tClose\tChange\t52W Hi\t52W Lo\n"
                "Alpha Metals Inc.\tALM\t245\t0.5100\t0.4300\t0.4700\t+0.0400\t1.2400\t0.2400\n"
                "Beta Holdings Corp.\tBET.U\t10\t1.0000\t1.0000\t1.0000\t0.0000\t1.2\t0.5\n\n"
                "Stock\tSymbol\tBid\tAsk\t52W Hi\t52W Lo\nGamma Gold Ltd.\tGAM\t0.0100\t0.0150\t0.05\t0.01\n")
        status, bars, info = boersen.parse_cse_summary(text, 20300)
        self.assertEqual(status, "ok")
        self.assertEqual(set(bars), {"ALM", "BET.U"})
        a = bars["ALM"]
        self.assertEqual((a.close, a.high, a.low, a.volume, a.decimals), (0.47, 0.51, 0.43, 24500.0, 4))
        self.assertEqual(info["BET.U"]["currency"], "USD")
        self.assertTrue(info["GAM"]["ohne_abschluss"])
        self.assertEqual(boersen.cse_symbol("ABC-U.CN"), "ABC.U")
        filled = boersen.fill_no_trade_days({20300: a}, [20299, 20301])
        self.assertNotIn(20299, filled)  # vor dem ersten Abschluss bleibt der Tag leer
        self.assertEqual((filled[20301].close, filled[20301].volume), (0.47, 0.0))

    def test_sources_per_exchange(self):
        self.assertEqual(boersen.sources_for("XWAR"), ("gpw", "newconnect"))
        self.assertEqual(boersen.sources_for("XTSX"), ("tmx",))
        self.assertEqual(boersen.sources_for("XNAS"), ("nasdaq_nocp",))
        self.assertEqual(boersen.sources_for("XCNQ"), ("cse",))
        self.assertEqual(boersen.sources_for("XNYS"), ())
        # Sammelschlüssel „US“: Nasdaq-Notierung laut Börse beim Kursanbieter (Yahoo „NMS“ usw.)
        self.assertEqual(boersen.sources_for("US", "NMS"), ("nasdaq_nocp",))
        self.assertEqual(boersen.sources_for("US", "NYQ"), ())
        self.assertEqual(boersen.us_venue("US", "PCX"), "ARCX")
        self.assertEqual(boersen.us_venue("US", "PNK"), "OTC")
        self.assertIsNone(boersen.us_venue("US", None))
        self.assertIsNone(boersen.us_venue("XETR", "GER"))


class RuleTests(unittest.TestCase):
    def test_deviation_zero_volume_and_missing_days(self):
        days, close = series()
        main = close.copy()
        main[5] = 11.5  # Tag ohne Umsatz an der Börse: Hauptquelle mit anderem Wert
        main[10] = round(close[10] * 1.05, 2)  # Tag mit Umsatz: Hauptquelle weicht ab
        volume = np.full(len(days), 1000.0)
        off = official_from(days, close, skip=(20,), override={5: (float(close[4]), 0.0)})
        res = ka.reconcile("gpw", ka.ListingInput(days=days, close=main, volume=volume), off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual(res.status, "uebernommen")
        self.assertEqual(res.counts["ohne_umsatz"], 1)
        self.assertEqual(res.counts["abweichend"], 1)
        self.assertEqual(res.counts["nur_hauptquelle"], 1)
        reasons = Counter(c.reason for c in res.corrections)
        self.assertEqual(reasons, Counter({"tag_ohne_umsatz": 1, "amtlicher_schlusskurs": 1}))
        zero = next(c for c in res.corrections if c.reason == "tag_ohne_umsatz")
        self.assertEqual((zero.old, zero.new, zero.old_volume, zero.new_volume), (11.5, float(close[4]), 1000.0, 0.0))

    def test_rounding_is_not_a_deviation_but_one_tick_is(self):
        days, close = series()
        main = close + 0.004  # Hauptquelle mit drei Stellen, Börse mit zwei: Rundung
        off = official_from(days, close, decimals=2)
        res = ka.reconcile("gpw", ka.ListingInput(days=days, close=main, volume=np.full(len(days), 5.0)), off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual(res.counts["rundung"], len(days))
        self.assertEqual(res.status, "uebernommen")
        # ab 1.1 im Nachweis: jeder Tag, an dem sich nur die Nachkommastellen ändern – keine Kurskorrektur im engeren Sinn
        self.assertEqual(Counter(c.reason for c in res.corrections), Counter({"nachkommastellen": len(days)}))
        self.assertFalse(any(c.reason in ka.PRICE_REASONS for c in res.corrections))
        main2 = close.copy()
        main2[3] += 0.01  # ein Kursschritt: Abweichung
        res2 = ka.reconcile("gpw", ka.ListingInput(days=days, close=main2, volume=np.full(len(days), 5.0)), off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual(res2.counts["abweichend"], 1)

    def test_coarser_rounding_of_the_main_source(self):
        days, close = series()
        exact = close + 0.0049  # Börse mit vier Stellen
        main = np.round(exact, 2)  # Hauptquelle rundet auf zwei Stellen
        off = official_from(days, exact, decimals=4)
        res = ka.reconcile("tmx", ka.ListingInput(days=days, close=main, volume=np.full(len(days), 5.0)), off, first_day=int(days[0]), last_day=int(days[-1]), basis="unbereinigt")
        self.assertEqual(res.counts["abweichend"], 0)

    def test_one_tick_on_a_coarse_looking_value_is_not_rounding(self):
        """Eine Reihe mit drei Stellen (0,165 … ) rundet nicht auf zwei: 0,18 statt 0,175 ist ein anderer Kurs (ein Kursschritt)."""
        days = np.arange(1000, 1030, dtype=np.int64)
        close = np.round(0.15 + 0.005 * np.arange(30), 3)
        main = close.copy()
        k = int(np.nonzero(np.isclose(close, 0.175))[0][0])
        main[k] = 0.18
        off = official_from(days, close, decimals=3)
        res = ka.reconcile("tmx", ka.ListingInput(days=days, close=main, volume=np.full(30, 1000.0)), off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual(res.counts["abweichend"], 1)
        self.assertEqual(res.counts["rundung"], 0)

    def test_missing_trading_day_is_added(self):
        days, close = series()
        keep = np.ones(len(days), dtype=bool)
        keep[7] = False
        off = official_from(days, close)
        inp = ka.ListingInput(days=days[keep], close=close[keep], volume=np.full(int(keep.sum()), 1000.0))
        res = ka.reconcile("gpw", inp, off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual(res.counts["nur_boerse"], 1)
        bars = {"days": days[keep], "close": close[keep].copy(), "close_raw": close[keep].copy(), "open": close[keep].copy(), "high": close[keep] + 0.1,
                "low": close[keep] - 0.1, "volume": np.full(int(keep.sum()), 1000.0), "quality": np.zeros(int(keep.sum()), dtype=np.int64)}
        out = ka.apply(bars, res, off, [])
        self.assertEqual(len(out["days"]), len(days))
        k = int(np.nonzero(out["days"] == days[7])[0][0])
        self.assertEqual(out["close"][k], float(close[7]))
        self.assertTrue(int(out["quality"][k]) & ka.QUALITY_EXCHANGE_ADDED)
        self.assertTrue(all(int(q) & ka.QUALITY_EXCHANGE_CLOSE for q in out["quality"]))

    def test_unadjusted_exchange_prices_against_split_basis(self):
        days, close = series()
        split = SplitEvent(day=int(days[15]), factor=2.0)
        raw = close.copy()
        raw[days < split.day] *= 2
        off = official_from(days, raw)
        inp = ka.ListingInput(days=days, close=close, volume=np.full(len(days), 9.0), close_raw=raw, splits=[split])
        res = ka.reconcile("gpw", inp, off, first_day=int(days[0]), last_day=int(days[-1]), basis="unbereinigt")
        self.assertEqual(res.status, "bestaetigt")
        self.assertEqual(res.counts["gleich"], len(days))
        # TMX: Basis unbekannt – an einem Split im Zeitraum eindeutig ermittelt
        res_raw = ka.reconcile("tmx", inp, off, first_day=int(days[0]), last_day=int(days[-1]), basis="unbekannt")
        self.assertEqual(res_raw.basis, "unbereinigt")
        res_adj = ka.reconcile("tmx", inp, official_from(days, close), first_day=int(days[0]), last_day=int(days[-1]), basis="unbekannt")
        self.assertEqual(res_adj.basis, "bereinigt")
        self.assertEqual(res_adj.status, "bestaetigt")

    def test_not_comparable_cases_adopt_nothing(self):
        days, close = series()
        inp = ka.ListingInput(days=days, close=close, volume=np.full(len(days), 1.0))
        cases = {
            "identitaet": dict(identity_ok=False),
            "waehrung": dict(currency_ok=False),
        }
        for reason, kwargs in cases.items():
            res = ka.reconcile("tmx", inp, official_from(days, close), first_day=int(days[0]), last_day=int(days[-1]), **kwargs)
            self.assertEqual((res.status, res.reason), ("nicht_vergleichbar", reason))
            self.assertFalse(res.adopted)
        hundred = ka.reconcile("gpw", inp, official_from(days, close * 100), first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual((hundred.status, hundred.reason), ("nicht_vergleichbar", "gleichbleibender_faktor"))
        rng = np.random.default_rng(1)
        other = official_from(days, close * (1 + rng.uniform(0.02, 0.2, len(days))) )
        res = ka.reconcile("gpw", inp, other, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual((res.status, res.reason), ("nicht_vergleichbar", "zu_wenig_gleiche_tage"))

    def test_coverage_guard_prevents_source_switch_inside_the_period(self):
        days, close = series()
        main = close.copy()
        main[30] *= 1.03
        off = official_from(days, close, skip=tuple(range(0, 10)))  # Börse erst ab Tag 10: nur 75 % abgedeckt
        res = ka.reconcile("tmx", ka.ListingInput(days=days, close=main, volume=np.full(len(days), 1.0)), off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual(res.status, "abdeckung_unvollstaendig")
        self.assertFalse(res.adopted)
        self.assertEqual(res.corrections, [])
        self.assertEqual(res.counts["abweichend"], 1)  # eingeordnet, aber nicht übernommen

    def test_volume_status_follows_the_exchange(self):
        days, close = series()
        volume = np.full(len(days), 100.0)
        volume[4] = 0.0  # Hauptquelle ohne Umsatz, Börse mit Umsatz
        res = ka.reconcile("gpw", ka.ListingInput(days=days, close=close, volume=volume), official_from(days, close, volume=50.0), first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual([(c.reason, c.old_volume, c.new_volume) for c in res.corrections], [("umsatz_laut_boerse", 0.0, 50.0)])

    # ---------------------------------------------------------------- Regel 1.1 (Befunde des Prüflaufs vom 31.10.2026)

    def test_no_trade_day_after_a_split_keeps_the_basis_of_the_last_trade(self):
        """Zusammenlegung 1:5 am Tag 20, an dem die Börse keinen Abschluss hat: Sie trägt den letzten Schlusskurs (Basis vor dem
        Split) fort. 1.0 setzte diesen Wert ohne Umrechnung ein – ein künstlicher Sprung um Faktor 5 (Prüflauf: CSE-Aktien)."""
        days, close = series(40, base=1.0, step=0.01)  # Basis der App (bereinigt)
        split = SplitEvent(day=int(days[20]), factor=0.2)
        raw = close.copy()
        raw[days < split.day] *= 0.2  # wie gehandelt: vor der Zusammenlegung ein Fünftel
        override = {20: (float(round(raw[19], 4)), 0.0)}  # Tag ohne Umsatz: letzter Schlusskurs (alte Basis)
        off = official_from(days, np.round(raw, 4), decimals=4, override=override)
        main = close.copy()
        main[20] = close[19]  # Hauptquelle: Vortageskurs in Basis der App
        inp = ka.ListingInput(days=days, close=main, volume=np.full(40, 1000.0), splits=[split])
        res = ka.reconcile("cse", inp, off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertTrue(res.adopted)
        day20 = next(r for r in res.days if r.day == int(days[20]))
        self.assertEqual(day20.code, "gleich")
        self.assertAlmostEqual(day20.official, float(close[19]), places=6)
        self.assertFalse([c for c in res.corrections if c.reason in ka.PRICE_REASONS])
        bars = {"days": days, "close": main.copy(), "close_raw": main * np.where(days < split.day, 0.2, 1.0), "open": main.copy(),
                "high": main + 0.01, "low": main - 0.01, "volume": np.full(40, 1000.0), "quality": np.zeros(40, dtype=np.int64)}
        out = ka.apply(bars, res, off, [split])
        self.assertLess(float(np.max(np.abs(np.diff(np.log(out["close"]))))), np.log(1.1))
        k = 20
        self.assertEqual((out["open"][k], out["high"][k], out["low"][k]), (out["close"][k],) * 3)  # kein Abschluss: keine Spanne

    def test_main_source_without_split_adjustment_is_converted_also_on_days_without_exchange_price(self):
        """Die Hauptquelle meldet vor einer Zusammenlegung 1:50 die unbereinigten Kurse, obwohl der Split bekannt ist (Prüflauf:
        Nasdaq-Aktie, Sprung um Faktor 42 am Split-Tag). Die Börse belegt es; umgerechnet werden auch Tage ohne Kurs der Börse."""
        days, close = series(60, base=5.0, step=0.01)
        split = SplitEvent(day=int(days[40]), factor=0.02)
        raw = close.copy()
        raw[days < split.day] *= 0.02
        raw = np.round(raw, 4)
        main = close.copy()
        main[days < split.day] = raw[days < split.day]  # Hauptquelle: unbereinigt vor dem Split
        main[12] = close[12]  # an einem Tag doch bereinigt
        off = official_from(days, raw, decimals=4, skip=(37,))  # Tag 37: kein Kurs der Börse
        inp = ka.ListingInput(days=days, close=main, volume=np.full(60, 1000.0), splits=[split])
        res = ka.reconcile("nasdaq_nocp", inp, off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertTrue(res.main_unadjusted)
        self.assertEqual(res.status, "uebernommen")
        reasons = Counter(c.reason for c in res.corrections)
        self.assertEqual(reasons["split_nicht_angewendet"], 39)  # 40 Tage vor dem Split ohne Tag 12 (dort schon bereinigt)
        own = next(c for c in res.corrections if c.day == int(days[37]))
        self.assertEqual(own.reason, "split_nicht_angewendet")
        self.assertAlmostEqual(own.new, float(raw[37]) / 0.02, places=6)
        bars = {"days": days, "close": main.copy(), "close_raw": main * np.where(days < split.day, 0.02, 1.0), "open": main.copy(),
                "high": main.copy(), "low": main.copy(), "volume": np.full(60, 1000.0), "quality": np.zeros(60, dtype=np.int64)}
        out = ka.apply(bars, res, off, [split])
        self.assertLess(float(np.max(np.abs(np.diff(np.log(out["close"]))))), np.log(1.1))  # kein Sprung am Split mehr
        self.assertTrue(int(out["quality"][37]) & ka.QUALITY_SPLIT_FIXED)
        self.assertAlmostEqual(out["close_raw"][37], float(raw[37]), places=8)

    def test_basis_break_at_the_edge_is_not_adopted_but_a_temporary_scaling_is(self):
        """Am Anfang des Zeitraums 30 Handelstage im Verhältnis 0,525 bei sich bewegenden Kursen, danach gleich: Eine Quelle hat
        eine Kapitalmaßnahme berücksichtigt, die die Splitdaten nicht kennen – nicht entscheidbar (Prüflauf: CSE-Aktie). Derselbe
        Faktor sechs Tage mitten im Zeitraum, davor und danach gleich, ist ein Fehler der Hauptquelle und wird korrigiert."""
        days, close = series(80, base=2.0, step=0.01)
        main = close.copy()
        main[:30] = np.round(close[:30] * 0.525, 4)
        off = official_from(days, close)
        res = ka.reconcile("cse", ka.ListingInput(days=days, close=main, volume=np.full(80, 10.0)), off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual((res.status, res.reason), ("nicht_vergleichbar", "basis_bruch"))
        self.assertAlmostEqual(res.factor, 0.525, places=2)
        self.assertEqual(res.corrections, [])
        middle = close.copy()
        middle[40:46] = np.round(close[40:46] * 0.525, 4)
        res2 = ka.reconcile("cse", ka.ListingInput(days=days, close=middle, volume=np.full(80, 10.0)), off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual(res2.status, "uebernommen")
        self.assertEqual(Counter(c.reason for c in res2.corrections), Counter({"amtlicher_schlusskurs": 6}))
        # kleine gleichbleibende Unterschiede am Rand (ein Kursschritt) sind kein Bruch der Basis
        tick = close.copy()
        tick[:8] = close[:8] + 0.01
        res3 = ka.reconcile("cse", ka.ListingInput(days=days, close=tick, volume=np.full(80, 10.0)), off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual(res3.status, "uebernommen")

    def test_jump_next_to_a_split_blocks_the_adoption(self):
        """Die Splitdaten nennen den Split drei Handelstage zu spät: An diesen Tagen stünde der Kurs der Börse in falscher Basis –
        die Übernahme erzeugte zwei Sprünge um Faktor 2 neben dem Split. Nichts wird übernommen."""
        days, close = series(60, base=10.0, step=0.02)
        actual = int(days[30])
        recorded = SplitEvent(day=int(days[33]), factor=2.0)
        raw = close.copy()
        raw[days < actual] *= 2.0  # wie gehandelt: 2:1-Split am Tag 30
        off = official_from(days, raw)
        inp = ka.ListingInput(days=days, close=close, volume=np.full(60, 100.0), splits=[recorded])
        res = ka.reconcile("gpw", inp, off, first_day=int(days[0]), last_day=int(days[-1]))
        self.assertEqual((res.status, res.reason), ("nicht_vergleichbar", "sprung_am_split"))
        self.assertTrue(res.jumps)
        self.assertEqual(res.corrections, [])

    def test_apply_keeps_ohlc_consistent(self):
        days, close = series(10)
        main = close.copy()
        main[2] = 20.0
        off = official_from(days, close)
        res = ka.reconcile("nasdaq_nocp", ka.ListingInput(days=days, close=main, volume=np.full(10, 3.0)), off, first_day=int(days[0]), last_day=int(days[-1]))
        bars = {"days": days, "close": main.copy(), "close_raw": main.copy(), "open": main.copy(), "high": main + 0.5, "low": main - 0.5,
                "volume": np.full(10, 3.0), "quality": np.zeros(10, dtype=np.int64)}
        out = ka.apply(bars, res, off, [])
        self.assertEqual(out["close"][2], float(close[2]))
        self.assertTrue(np.all(out["high"] >= out["close"]) and np.all(out["low"] <= out["close"]))
        self.assertEqual(bars["close"][2], 20.0)  # Eingabe unverändert


class RunHelperTests(unittest.TestCase):
    def test_source_is_switched_off_after_failures_in_a_row(self):
        run = lauf.Kursabgleich(conn=None, sources=None, calendars=None)
        for k in range(lauf.MAX_FAILURES - 1):
            self.assertFalse(run._failed("nasdaq_nocp", "fehler_Timeout"))
        self.assertFalse(run._failed("nasdaq_nocp", "ok"))  # ein Erfolg setzt die Zählung zurück
        for k in range(lauf.MAX_FAILURES - 1):
            run._failed("nasdaq_nocp", "http_503")
        self.assertTrue(run._failed("nasdaq_nocp", "fehler_ConnectionError"))
        self.assertTrue(run._disabled("nasdaq_nocp"))
        self.assertFalse(run._disabled("tmx"))
        self.assertFalse(run._failed("gpw", "ohne_zeilen"))  # keine Daten für den Tag ist kein Fehler der Quelle

    def test_nasdaq_traded_list(self):
        text = "Nasdaq Traded|Symbol|Security Name|Listing Exchange|Market Category|ETF|Round Lot Size|Test Issue|Financial Status|CQS Symbol|NASDAQ Symbol|NextShares\n" \
               "Y|AAPL|Apple Inc. - Common Stock|Q|Q|N|100|N|N||AAPL|N\n" \
               "Y|BRK.B|Berkshire Hathaway Inc. Class B|N| |N|100|N||BRK.B|BRK-B|N\n" \
               "Y|ZZZT|Test|Q|Q|N|100|Y|N||ZZZT|N\n" \
               "File Creation Time: 1030202617:00|||||||||||"
        listing = lauf.parse_nasdaq_traded(text)
        self.assertEqual(listing["AAPL"], "nasdaq")
        self.assertEqual(listing["BRK-B"], "nyse")
        self.assertNotIn("ZZZT", listing)

    def test_name_score_ignores_share_class_description(self):
        self.assertGreaterEqual(lauf.name_score("Alpha Mining Corp. Class A Subordinate Voting Shares", ["Alpha Mining Corp"]), lauf.NAME_CONFIRMED)
        self.assertLess(lauf.name_score("Beta Energy Ltd.", ["Alpha Mining Corp"]), lauf.NAME_CONFIRMED)

    def test_compare_rankings(self):
        before = {(1, "A", 0): [1, 2, 3], (1, "A", 10): [4, 5, 6], (2, "B", 0): [7, 8, 9]}
        after = {(1, "A", 0): [2, 1, 3], (1, "A", 10): [4, 6, 5], (2, "B", 0): [7, 8, 10]}
        rows, counts = lauf.compare_rankings(before, after, corrected={2})
        self.assertEqual(counts["platz1_anders"], 1)
        self.assertEqual(counts["erste10_andere_aktien"], 1)
        self.assertEqual(counts["erste10_andere_reihenfolge"], 2)  # gleiche Aktien, andere Reihenfolge (auch mit neuem Platz 1)
        lead = next(r for r in rows if r["platz1_anders"])
        self.assertEqual(lead["ausloeser"], [2])


if __name__ == "__main__":
    unittest.main()
