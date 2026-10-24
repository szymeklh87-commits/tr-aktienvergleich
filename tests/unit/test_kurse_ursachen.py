"""Ursachen der Kursunterschiede und Wirkung auf die Ranglisten (ab 1.18.1, ``tests/live/kurse_ursachen.py``) –
SYNTHETISCHE Kurse; der echte Abruf läuft im Workflow „App mit echten Daten prüfen“ (Option „Ursachen“)."""

from __future__ import annotations

import base64
import datetime as dt
import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

LIVE = Path(__file__).resolve().parents[1] / "live"
sys.path.insert(0, str(LIVE))
SPEC = importlib.util.spec_from_file_location("kurse_ursachen", LIVE / "kurse_ursachen.py")
ursachen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ursachen)


def day(text: str) -> int:
    return (dt.date.fromisoformat(text) - dt.date(1970, 1, 1)).days


def stamp(text: str, hour: int, minute: int) -> int:
    """Zeitstempel einer Kerze in New York (Sommerzeit, −4 h) als UTC-Sekunden."""
    local = dt.datetime.fromisoformat(f"{text}T{hour:02d}:{minute:02d}:00")
    return int((local + dt.timedelta(hours=4)).replace(tzinfo=dt.timezone.utc).timestamp())


class Parsing(unittest.TestCase):
    def test_nasdaq_rows_with_volume(self):
        payload = {"data": {"tradesTable": {"rows": [{"date": "10/23/2026", "close": "$0.4123", "volume": "1,200"}, {"date": "10/22/2026", "close": "$0.41", "volume": "N/A"}]}}}
        self.assertEqual(ursachen.parse_nasdaq_rows(payload), {day("2026-10-23"): {"close": 0.4123, "volume": 1200.0}, day("2026-10-22"): {"close": 0.41, "volume": None}})

    def test_nocp_rows_found_without_fixed_structure(self):
        payload = {"data": {"symbol": "X", "nocp": {"nocpTable": [{"date": "10/23/2026", "price": "$1.23"}, {"date": "10/22/2026", "price": "$1.20"}], "nocpChart": [{"x": 1, "y": 2}]}}}
        rows, fields = ursachen.parse_nocp(payload)
        self.assertEqual(rows, {day("2026-10-23"): 1.23, day("2026-10-22"): 1.20})
        self.assertEqual(fields, ["date", "price"])
        self.assertEqual(ursachen.parse_nocp({"data": None}), ({}, []))

    def test_yahoo_daily_with_volume_adjclose_and_events(self):
        open_utc = stamp("2026-10-21", 9, 30)
        payload = {"chart": {"result": [{
            "meta": {"gmtoffset": -14400, "exchangeName": "NCM"},
            "timestamp": [open_utc, open_utc + 86400],
            "indicators": {"quote": [{"close": [0.5, 0.52], "volume": [0, 1000]}], "adjclose": [{"adjclose": [0.49, 0.52]}]},
            "events": {"dividends": {"1": {"date": open_utc, "amount": 0.01}}, "splits": {"2": {"date": open_utc + 86400, "numerator": 1, "denominator": 10}}},
        }]}}
        parsed = ursachen.parse_yahoo_daily(payload)
        self.assertEqual(parsed["exchange"], "NCM")
        self.assertEqual(parsed["days"][day("2026-10-21")], {"close": 0.5, "volume": 0.0, "adjclose": 0.49})
        self.assertEqual(parsed["dividends"], [day("2026-10-21")])
        self.assertEqual(parsed["splits"], [(day("2026-10-22"), 0.1)])

    def test_last_regular_minute_before_four_pm(self):
        times = [stamp("2026-10-23", 15, 58), stamp("2026-10-23", 15, 59), stamp("2026-10-23", 16, 0), stamp("2026-10-22", 15, 41)]
        payload = {"chart": {"result": [{"meta": {"gmtoffset": -14400}, "timestamp": times, "indicators": {"quote": [{"close": [1.01, 1.02, 1.05, 0.99]}]}}]}}
        self.assertEqual(ursachen.parse_yahoo_minutes(payload), {day("2026-10-23"): 1.02, day("2026-10-22"): 0.99})


class Causes(unittest.TestCase):
    D = day("2026-10-23")

    def cause(self, own=0.42, nasdaq_close=0.41, nasdaq_volume=1000.0, yahoo_volume=1000.0, adjclose=None, nocp=None, minute=None, previous_own=0.40, previous_nasdaq=0.40, kind="gross"):
        nasdaq = {self.D: {"close": nasdaq_close, "volume": nasdaq_volume}}
        yahoo = {"days": {self.D: {"close": own, "volume": yahoo_volume, "adjclose": adjclose}}}
        minutes = {self.D: minute} if minute is not None else {}
        return ursachen.day_cause(self.D, own, nasdaq, yahoo, nocp, minutes, previous_own, previous_nasdaq, kind)[0]

    def test_official_close_needs_nasdaq_equal_to_nocp(self):
        self.assertEqual(self.cause(nocp={self.D: 0.41}), "offizieller_schlusskurs")
        self.assertEqual(self.cause(nocp={self.D: 0.43}), "ungeklaert", "Nasdaq nicht der NOCP – kein Beleg")
        self.assertEqual(self.cause(nocp={self.D: 0.42}), "ungeklaert", "Stand = NOCP: Yahoo hätte den offiziellen Kurs")

    def test_last_trade_needs_the_minute_price(self):
        self.assertEqual(self.cause(minute=0.42), "letzter_abschluss")
        self.assertEqual(self.cause(minute=0.41), "ungeklaert")

    def test_no_trade_needs_zero_volume_and_the_previous_price(self):
        self.assertEqual(self.cause(own=0.40, yahoo_volume=0.0, previous_own=0.40, kind="nachbartag"), "kein_handel")
        self.assertEqual(self.cause(own=0.40, yahoo_volume=10.0, previous_own=0.40, kind="nachbartag"), "ungeklaert")
        self.assertEqual(self.cause(nasdaq_close=0.40, nasdaq_volume=0.0, previous_nasdaq=0.40), "kein_handel")

    def test_dividend_adjustment_and_split(self):
        self.assertEqual(self.cause(own=10.0, nasdaq_close=9.8, adjclose=9.8), "dividendenbereinigung")
        self.assertEqual(self.cause(kind="faktor"), "split")

    def test_equal_to_yahoo_alone_is_no_cause(self):
        self.assertEqual(self.cause(), "ungeklaert")


class WindowValues(unittest.TestCase):
    def test_return_r2_and_trend_status_like_the_recheck(self):
        days = np.arange(100, 120, dtype=np.int64)
        rising = np.linspace(1.0, 2.0, 20)
        r, r2, status = ursachen.window_values(days, rising, 100, 15)
        self.assertAlmostEqual(r, 1.0)
        self.assertAlmostEqual(r2, 1.0)
        self.assertEqual(status, 18)
        self.assertEqual(ursachen.window_values(days, rising[::-1].copy(), 100, 15)[2], 16)
        self.assertEqual(ursachen.window_values(days, rising, 110, 15)[1:], (None, 15))


class FakeStand:
    def __init__(self, windows: dict):
        self.windows = windows

    def get(self, relative: str):
        return self.windows[int(relative.split("/")[1].split(".")[0])]

    def drop(self, relative: str) -> None:
        pass


def window(h: int, idx: list[int], r: list[float], r2: list[float], start: list[int], n: int) -> dict:
    status = np.zeros(n, dtype=np.uint8)
    status[idx] = 18
    return {"m": {"idx": idx, "r": r, "r2": r2, "start": start}, "status_b64": base64.b64encode(status.tobytes()).decode("ascii")}


class RankingEffect(unittest.TestCase):
    def test_nasdaq_prices_change_place_one_only_where_they_differ(self):
        """Aktie 0 liegt mit dem Stand vorn; mit dem Nasdaq-Kurs am letzten Tag (−20 %) fällt sie zurück – in Zeiträumen,
        die den Tag enthalten. Ein Zeitraum ohne abweichenden Tag bleibt unverändert."""
        days = np.arange(200, 230, dtype=np.int64)
        own = np.linspace(1.0, 2.0, 30)
        nasdaq = own.copy()
        nasdaq[-1] = 1.6
        windows = {}
        for h in range(1, 91):
            windows[h] = window(h, [0, 1, 2], [1.0, 0.8, 0.5], [0.99, 0.95, 0.9], [200, 200, 200], 3)
        effect, moves = ursachen.ranking_effect(FakeStand(windows), {0: (days, nasdaq, {229})}, [True, True, False], 15, {0})
        self.assertEqual(effect["ranglisten_insgesamt"], 90 * 2 * 11)
        self.assertGreater(effect["spitze_geaendert"], 0)
        self.assertGreater(moves[0]["platz1_vorher"], moves[0]["platz1_nachher"])
        # kein abweichender Tag im Zeitraum (Start nach dem Tag): nichts neu gerechnet
        unchanged = {h: window(h, [0, 1, 2], [1.0, 0.8, 0.5], [0.99, 0.95, 0.9], [230, 230, 230], 3) for h in range(1, 91)}
        effect, _ = ursachen.ranking_effect(FakeStand(unchanged), {0: (days, nasdaq, {205})}, [True, True, False], 15, {0})
        self.assertEqual(effect.get("ranglisten_verglichen", 0), 0)

    def test_compare_orders(self):
        self.assertEqual(ursachen.compare_orders([1, 2, 3], [1, 2, 3]), {"spitze": False, "top10_aktien": False, "top10_reihenfolge": False, "reihenfolge": False})
        self.assertEqual(ursachen.compare_orders([1, 2, 3], [2, 1, 3]), {"spitze": True, "top10_aktien": False, "top10_reihenfolge": True, "reihenfolge": True})


class Annotations(unittest.TestCase):
    def test_only_counts_letters_and_ranges_and_titles_without_commas(self):
        report = {
            "stand": "2026-10-23_3f7ce5f3", "stichtag": "2026-10-23", "abgerufen_utc": "2026-10-24T20:00:00Z", "ausgewaehlt": 500,
            "davon_aus_den_ersten_20": 350, "abruf": {"nasdaq_ok": 450}, "nocp_abruf": {"ok": 10, "mit_kursen": 10}, "nocp_felder": ["date", "price"],
            "tage": {"verglichen": 30000, "abweichend": 600, "abweichend_mit_nocp": 300}, "nur_eine_quelle": {}, "ursachen": {"offizieller_schlusskurs": 300, "ungeklaert": 300},
            "aktien_mit_abweichung": 2, "aktien_mit_ereignis_im_zeitraum": {}, "ranglisten": {"ranglisten_verglichen": 100, "ranglisten_insgesamt": 1980, "spitze_geaendert": 2},
            "aktien": [
                {"aktie": "A", "boerse": "Nasdaq", "kursbereich": "unter 1 $", "top10": 37, "platz1": 3, "abweichend": 66, "groesste_abweichung_pct": 3.93,
                 "ursachen": {"offizieller_schlusskurs": 60, "ungeklaert": 6}, "nocp_abrufbar": True, "minutenkurse_tage": 5, "ereignisse": {}, "rangwirkung": {"unter_ersten_10_vorher": 37, "unter_ersten_10_nachher": 35}},
                {"aktie": "B", "boerse": "NYSE", "kursbereich": "10–100 $", "top10": 0, "platz1": 0, "abweichend": 1, "groesste_abweichung_pct": 0.05,
                 "ursachen": {"letzter_abschluss": 1}, "nocp_abrufbar": False, "minutenkurse_tage": 5, "ereignisse": {}, "rangwirkung": {}},
            ],
        }
        lines = ursachen.annotations(report)
        text = "\n".join(lines)
        self.assertIn("Ursache belegt für 300, ungeklärt 300", text)
        self.assertIn("Platz 1 anders 2", text)
        self.assertIn("Aktie A (Nasdaq, unter 1 $", text)
        self.assertIn("Weitere 1 Aktien", text)
        self.assertTrue(lines[0].startswith("::warning"))
        for line in lines:
            self.assertNotIn(",", line.split("::", 2)[1])
        self.assertLessEqual(len(lines), 10)


if __name__ == "__main__":
    unittest.main()
