"""Ursachen der Kursunterschiede und Wirkung auf die Ranglisten (ab 1.18.1, ``tests/live/kurse_ursachen.py``) –
SYNTHETISCHE Kurse; der echte Abruf läuft im Workflow „App mit echten Daten prüfen“ (Option „Ursachen“)."""

from __future__ import annotations

import base64
import datetime as dt
import importlib.util
import sys
import types
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
        self.assertEqual(self.cause(nocp={self.D: 0.43}), "ungeklaert", "NOCP ein dritter Wert – kein Beleg")
        self.assertEqual(self.cause(nocp={self.D + 1: 0.41}), "ungeklaert", "NOCP nur an einem anderen Tag – kein Beleg")

    def test_stand_equal_to_the_official_close(self):
        """Stand = NOCP, Nasdaq-Historie nicht: Der Stand hat den offiziellen Schlusskurs (bis zum Abend des 24.10.2026
        als ungeklärt gezählt)."""
        self.assertEqual(self.cause(nocp={self.D: 0.42}), "stand_ist_nocp")

    def test_last_trade_needs_the_minute_price(self):
        self.assertEqual(self.cause(minute=0.42), "letzter_abschluss")
        self.assertEqual(self.cause(minute=0.41), "nasdaq_letzter_abschluss", "Nasdaq = letzter Abschluss, Stand nicht")
        self.assertEqual(self.cause(minute=0.43), "ungeklaert", "keine der beiden Quellen ist der letzte Abschluss")

    def test_less_than_one_price_step(self):
        """Stand zwischen zwei Kursstufen (Bruchteil eines Cents), Nasdaq zeigt eine Nachbarstufe."""
        self.assertEqual(self.cause(own=2.345, nasdaq_close=2.34, previous_own=2.30, previous_nasdaq=2.30), "rundung")
        self.assertEqual(self.cause(own=2.345, nasdaq_close=2.35, previous_own=2.30, previous_nasdaq=2.30), "rundung")
        self.assertEqual(self.cause(own=2.345, nasdaq_close=2.36, previous_own=2.30, previous_nasdaq=2.30), "ungeklaert", "1,5 Stufen")
        self.assertEqual(self.cause(own=2.35, nasdaq_close=2.34, previous_own=2.30, previous_nasdaq=2.30), "ungeklaert", "Stand auf der Kursstufe")
        self.assertEqual(self.cause(own=0.41235, nasdaq_close=0.4123), "rundung", "unter 1 $: Stufe 1/100 Cent")
        # Gleitkomma-Darstellung (float32) eines Kurses auf der Stufe gilt als auf der Stufe
        self.assertTrue(ursachen.on_grid(150.1199951171875, 0.01))
        self.assertTrue(ursachen.on_grid(0.4123000121116638, 0.0001))

    def test_no_trade_needs_zero_volume_and_the_previous_price(self):
        self.assertEqual(self.cause(own=0.40, yahoo_volume=0.0, previous_own=0.40, kind="nachbartag"), "kein_handel")
        self.assertEqual(self.cause(own=0.40, yahoo_volume=10.0, previous_own=0.40, kind="nachbartag"), "ungeklaert")
        self.assertEqual(self.cause(nasdaq_close=0.40, nasdaq_volume=0.0, previous_nasdaq=0.40), "kein_handel")

    def test_dividend_adjustment_and_split(self):
        self.assertEqual(self.cause(own=10.0, nasdaq_close=9.8, adjclose=9.8), "dividendenbereinigung")
        self.assertEqual(self.cause(kind="faktor"), "split")

    def test_equal_to_yahoo_alone_is_no_cause(self):
        self.assertEqual(self.cause(), "ungeklaert")


class Unexplained(unittest.TestCase):
    def test_reason_names_the_missing_source(self):
        self.assertEqual(ursachen.unexplained_reason("NYQ", None, 5), "nyse_gruppe_ohne_offiziellen_kurs")
        self.assertEqual(ursachen.unexplained_reason("ASE", None, 5), "nyse_gruppe_ohne_offiziellen_kurs")
        self.assertEqual(ursachen.unexplained_reason("NMS", None, 5), "nocp_fehlt_am_tag")
        self.assertEqual(ursachen.unexplained_reason("NMS", {4: 1.0}, 5), "nocp_fehlt_am_tag")
        self.assertEqual(ursachen.unexplained_reason("NCM", {5: 1.0}, 5), "nocp_dritter_wert")
        self.assertEqual(ursachen.unexplained_reason(None, None, 5), "boerse_unbekannt")

    def test_patterns_without_prices(self):
        self.assertEqual(ursachen.volume_bucket(1000.0, 1010.0), "gleich")
        self.assertEqual(ursachen.volume_bucket(500.0, 1000.0), "nasdaq_kleiner")
        self.assertEqual(ursachen.volume_bucket(1500.0, 1000.0), "nasdaq_groesser")
        self.assertEqual(ursachen.volume_bucket(None, 1000.0), "fehlt")
        self.assertEqual(ursachen.tick_bucket(10.01, 10.00), "1")
        self.assertEqual(ursachen.tick_bucket(10.02, 10.00), "2")
        self.assertEqual(ursachen.tick_bucket(10.07, 10.00), "3–10")
        self.assertEqual(ursachen.tick_bucket(10.50, 10.00), "über 10")
        self.assertEqual(ursachen.tick_bucket(0.4125, 0.4123), "2")


class Verdict(unittest.TestCase):
    def test_green_only_when_complete_and_every_deviation_has_evidence(self):
        self.assertEqual(ursachen.verdict({"abruf_fehlgeschlagen": 1, "ursachen": {}, "tage": {}}), "unvollstaendig")
        self.assertEqual(ursachen.verdict({"abruf_fehlgeschlagen": 0, "ursachen": {"ungeklaert": 1, "rundung": 5}, "tage": {"abweichend": 6}}), "ungeklaert")
        self.assertEqual(ursachen.verdict({"abruf_fehlgeschlagen": 0, "ursachen": {"rundung": 5}, "tage": {"abweichend": 5}}), "belegt")
        self.assertEqual(ursachen.verdict({"abruf_fehlgeschlagen": 0, "ursachen": {}, "tage": {"verglichen": 9}}), "keine_abweichungen")

    def test_transient_errors_are_retried_missing_data_is_not(self):
        for status in ("fehler_ConnectionError", "http_429", "http_503", "kein_json"):
            self.assertTrue(ursachen.transient(status), status)
        for status in ("ok", "http_404", "http_400"):
            self.assertFalse(ursachen.transient(status), status)


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
        effect, moves, changes = ursachen.ranking_effect(FakeStand(windows), {0: (days, nasdaq, {229})}, [True, True, False], 15, {0, 1})
        self.assertEqual(effect["ranglisten_insgesamt"], 90 * 2 * 11)
        self.assertGreater(effect["spitze_geaendert"], 0)
        self.assertGreater(moves[0]["platz1_vorher"], moves[0]["platz1_nachher"])
        self.assertGreater(moves[1]["platz1_nachher"], moves[1]["platz1_vorher"], "die zweite Aktie rückt auf Platz 1")
        # ab 1.18.2: jede Rangliste mit anderem Platz 1 einzeln – Zeitraum, Gruppe, Gewichtung, vorher und nachher
        self.assertEqual(len(changes), effect["spitze_geaendert"])
        reine_rendite = [c for c in changes if c["w"] == 0]
        self.assertTrue(reine_rendite)
        self.assertEqual({tuple(c["platz1"]) for c in reine_rendite}, {(0, 1)})
        self.assertEqual({c["gruppe"] for c in reine_rendite}, {"A", "B"})
        self.assertTrue(all(c["raus"] == [] and c["rein"] == [] for c in changes), "nur 3 Aktien: unter den ersten 10 dieselben")
        # kein abweichender Tag im Zeitraum (Start nach dem Tag): nichts neu gerechnet
        unchanged = {h: window(h, [0, 1, 2], [1.0, 0.8, 0.5], [0.99, 0.95, 0.9], [230, 230, 230], 3) for h in range(1, 91)}
        effect, _, changes = ursachen.ranking_effect(FakeStand(unchanged), {0: (days, nasdaq, {205})}, [True, True, False], 15, {0})
        self.assertEqual(effect.get("ranglisten_verglichen", 0), 0)
        self.assertEqual(changes, [])

    def test_compare_orders(self):
        self.assertEqual(ursachen.compare_orders([1, 2, 3], [1, 2, 3]), {"spitze": False, "top10_aktien": False, "top10_reihenfolge": False, "reihenfolge": False})
        self.assertEqual(ursachen.compare_orders([1, 2, 3], [2, 1, 3]), {"spitze": True, "top10_aktien": False, "top10_reihenfolge": True, "reihenfolge": True})


class Fetching(unittest.TestCase):
    def test_error_name_keeps_the_kind_without_the_address(self):
        """Lauf vom 24.10.2026, 23:09 Uhr: 121 × „ConnectionError“ – ab jetzt mit der Art dahinter, ohne Adresse und Kürzel."""
        self.assertEqual(ursachen.error_name(ConnectionError("Anfrage an api.nasdaq.com endgültig fehlgeschlagen: Timeout")), "ConnectionError_Timeout")
        self.assertEqual(ursachen.error_name(ConnectionError("Anfrage an api.nasdaq.com endgültig fehlgeschlagen: ConnectionError")), "ConnectionError")
        self.assertEqual(ursachen.error_name(ValueError("https://api.nasdaq.com/api/quote/ABCD/historical: kaputt ab hier")), "ValueError")

    def test_slow_down_doubles_the_nasdaq_interval_up_to_the_cap(self):
        http = types.SimpleNamespace(min_interval={"api.nasdaq.com": 1.0, "query2.finance.yahoo.com": 0.3})
        self.assertEqual(ursachen.slow_down(http), 2.0)
        self.assertEqual(ursachen.slow_down(http), ursachen.MAX_INTERVAL_S)
        self.assertEqual(ursachen.slow_down(http), ursachen.MAX_INTERVAL_S)
        self.assertEqual(http.min_interval["query2.finance.yahoo.com"], 0.3, "Yahoo bleibt unverändert")
        self.assertIsNone(ursachen.slow_down(object()), "ohne Drossel nichts zu ändern")
        self.assertIsNone(ursachen.nasdaq_requests(object()))
        self.assertEqual(ursachen.nasdaq_requests(types.SimpleNamespace(stats=types.SimpleNamespace(by_host={"api.nasdaq.com": 431}))), 431)


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
        # ungeklärte Tage: Fehler mit dem Grund im Titel – ein fehlerfrei gelaufenes Skript ist kein Beleg
        self.assertTrue(lines[0].startswith("::error title=Kursursachen: NICHT VOLLSTÄNDIG BELEGT – 300 von 600 abweichenden Tagen ungeklärt::"), lines[0][:120])
        for line in lines:
            self.assertNotIn(",", line.split("::", 2)[1])
        self.assertLessEqual(len(lines), 10)
        report["ursachen"] = {"offizieller_schlusskurs": 600}
        report["aktien"] = [s for s in report["aktien"] if s["aktie"] == "B"]
        self.assertTrue(ursachen.annotations(report)[0].startswith("::notice title=Kursursachen: jede Abweichung belegt (600 Tage)::"))
        report["abruf_fehlgeschlagen"] = 3
        self.assertTrue(ursachen.annotations(report)[0].startswith("::error title=Kursursachen: UNVOLLSTÄNDIG – 3 Aktien ohne Antwort einer Quelle::"))

    def test_changed_rankings_are_listed_with_letters_and_rows_never_cut_silently(self):
        """Ab 1.18.2: welche Ranglisten sich ändern (Zeitraum, Gruppe, Gewichtung, Buchstaben), Abruf je Gruppe, Aktien unter
        den ersten 10 mit nur anderem offiziellem Schlusskurs – und höchstens 10 Hinweise, Weggelassenes ausdrücklich gezählt."""
        stock = {"aktie": "A", "boerse": "Nasdaq", "kursbereich": "1–10 $", "top10": 725, "platz1": 240, "abweichend": 3, "groesste_abweichung_pct": 0.12,
                 "ursachen": {"offizieller_schlusskurs": 3}, "nocp_abrufbar": True, "nocp_tage_ungleich": 3, "minutenkurse_tage": 30, "ereignisse": {},
                 "rangwirkung": {"unter_ersten_10_vorher": 725, "unter_ersten_10_nachher": 725}, "rangwirkung_nocp": {"unter_ersten_10_vorher": 725, "unter_ersten_10_nachher": 724, "platz1_vorher": 240, "platz1_nachher": 238}}
        report = {
            "stand": "2026-10-23_3f7ce5f3", "stichtag": "2026-10-23", "abgerufen_utc": "2026-10-24T22:00:00Z", "ausgewaehlt": 404, "davon_aus_den_ersten_20": 254,
            "abruf": {"nasdaq_ok": 283, "fehlgeschlagen_nasdaq_fehler_ConnectionError": 121}, "abruf_fehlgeschlagen": 121,
            "abruf_je_gruppe": {"erste_10_mit_kursen": 147, "zufall_ohne_antwort": 121}, "sperrpausen": 2, "nasdaq_anfragen_bis_zur_ersten_sperre": 431, "nasdaq_anfragen": 650, "nasdaq_abstand_s": 3.0,
            "nocp_abruf": {}, "tage": {"verglichen": 100, "abweichend": 3}, "nur_eine_quelle": {}, "ursachen": {"offizieller_schlusskurs": 3},
            "aktien_mit_ereignis_im_zeitraum": {}, "ranglisten": {"ranglisten_verglichen": 1640, "ranglisten_insgesamt": 1980},
            "ranglisten_offizieller_schlusskurs": {"ranglisten_verglichen": 1640, "ranglisten_insgesamt": 1980, "spitze_geaendert": 1, "top10_aktien_geaendert": 1},
            "aenderungen_nasdaq": [],
            "aenderungen_offizieller_schlusskurs": [{"h": 30, "gruppe": "A", "w": 60, "platz1": ["A", "Z2"], "raus": ["A"], "rein": ["Z3"]}],
            "weitere_buchstaben": [{"aktie": "Z2", "abgefragt": True, "boerse": "Nasdaq", "kursbereich": "über 100 $", "top10": 3, "abweichend": 0, "nocp_ungleich": 0},
                                   {"aktie": "Z3", "abgefragt": False, "top10": 0}],
            "aktien": [stock],
            "aktien_nur_nocp": [{"aktie": "B", "boerse": "Nasdaq", "kursbereich": "10–100 $", "top10": 9, "platz1": 0, "nocp_tage_ungleich": 4, "groesste_abweichung_nocp_pct": 0.3,
                                 "rangwirkung_nocp": {"unter_ersten_10_vorher": 9, "unter_ersten_10_nachher": 9, "platz_geaendert": 2}}],
        }
        text = "\n".join(ursachen.annotations(report)).replace("%0A", "\n").replace("%25", "%")
        self.assertIn("je Gruppe: erste_10_mit_kursen 147, zufall_ohne_antwort 121", text)
        self.assertIn("Sperrpausen 2 (erste nach 431 Anfragen an Nasdaq), Anfragen an Nasdaq 650, Abstand zuletzt 3.0 s", text)
        self.assertIn("Platz 1 anders – (a): keine | (b): 1 – 30 Tage Gruppe A 60/40: A → Z2", text)
        self.assertIn("Andere Aktien unter den ersten 10 – (a): keine | (b): 1 – 30 Tage Gruppe A 60/40: raus A rein Z3", text)
        self.assertIn("Z2 (Nasdaq, über 100 $; unter den ersten 10 in 3 Ranglisten; abweichend von der Nasdaq-Historie an 0 Tagen)", text)
        self.assertIn("Z3 (nicht abgefragt oder ohne Nasdaq-Kurse – Kurse in beiden Varianten unverändert)", text)
        self.assertIn("Ursachen: Nasdaq = NOCP 3", text)
        self.assertIn("(b) unter den ersten 10 725 → 724, Platz 1 240 → 238, anderer Platz 0", text)
        self.assertIn("Aktie B (Nasdaq, 10–100 $; unter den ersten 10 in 9 Ranglisten, Platz 1 in 0): Stand wie Nasdaq-Historie, aber ungleich NOCP an 4 Tagen (größte 0.3 %)", text)
        self.assertIn("„Nasdaq = NOCP“ = Yahoo nicht der offizielle Schlusskurs der Heimatbörse (Nasdaq-Kurs = NOCP)", text)
        # sehr viele Zeilen: höchstens 10 Hinweise, das Weggelassene wird gezählt – nichts still abgeschnitten
        report["aktien"] = [dict(stock, aktie=f"Z{k}") for k in range(30, 30 + ursachen.MAX_ROWS)]
        report["aktien_nur_nocp"] = [dict(report["aktien_nur_nocp"][0], aktie=f"Z{k}") for k in range(100, 160)]
        lines = ursachen.annotations(report)
        self.assertLessEqual(len(lines), 10)
        self.assertIn("Nicht gezeigt:", lines[-1])
        shown = sum(line.count("Aktie Z") for line in lines)
        dropped = int(lines[-1].split("Nicht gezeigt: ")[1].split(" ")[0])
        self.assertEqual(shown + dropped, ursachen.MAX_ROWS + 60, "jede Zeile gezeigt oder gezählt")
        for line in lines:
            self.assertNotIn(",", line.split("::", 2)[1])


if __name__ == "__main__":
    unittest.main()
