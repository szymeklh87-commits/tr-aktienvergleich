"""Ursachen der Kursunterschiede und Wirkung auf die Ranglisten (ab 1.18.1, ``tests/live/kurse_ursachen.py``) –
SYNTHETISCHE Kurse; der echte Abruf läuft im Workflow „App mit echten Daten prüfen“ (Option „Ursachen“)."""

from __future__ import annotations

import base64
import datetime as dt
import importlib.util
import re
import sys
import types
import unittest
from collections import Counter
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


class NocpNote(unittest.TestCase):
    def test_position_of_the_nasdaq_history_on_a_day_with_a_different_official_close(self):
        """Lauf vom 25.10.2026, 00:30 Uhr: „Nasdaq ein dritter Kurs“ fasste zusammen, ob die Nasdaq-Historie dem Stand gleicht
        (beide führen denselben anderen Schlusskurs als den offiziellen) oder ein dritter Kurs ist – jetzt getrennt."""
        self.assertEqual(ursachen.nocp_note(1.25, 1.20, 1.20), "nasdaq_gleich_nocp")
        self.assertEqual(ursachen.nocp_note(1.25, 1.25, 1.20), "nasdaq_gleich_stand")
        self.assertEqual(ursachen.nocp_note(1.2500, 1.2549, 1.20), "nasdaq_gleich_stand", "innerhalb der Rundung gleich")
        self.assertEqual(ursachen.nocp_note(1.25, 1.30, 1.20), "drei_kurse")
        self.assertEqual(ursachen.nocp_note(1.25, None, 1.20), "nasdaq_ohne_tag")


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
        # Auslöser: die bisherige Spitzenreiterin selbst – allein ausreichend; der neue Spitzenreiter stand vorher auf Platz 2.
        # Gesucht wird für höchstens MAX_ATTRIBUTIONS neue Plätze 1 je Variante, die übrigen sind ausdrücklich „nicht untersucht“
        leaders = [c for c in changes if c.get("platz1")]
        studied = [c for c in leaders if not c.get("nicht_untersucht")]
        self.assertEqual(len(studied), min(len(leaders), ursachen.MAX_ATTRIBUTIONS))
        self.assertTrue(all(c["ausloeser"] is None for c in leaders if c.get("nicht_untersucht")))
        for c in [c for c in reine_rendite if not c.get("nicht_untersucht")]:
            self.assertEqual((c["ausloeser"], c["allein"], c["platz_des_neuen_vorher"]), ([0], [0], 2))
            self.assertAlmostEqual(c["rendite"][0][1], 0.6)
            self.assertEqual(c["rendite"][1], (0.8, 0.8))
            self.assertEqual(c["start"], {0: 200, 1: 200})
        # kein abweichender Tag im Zeitraum (Start nach dem Tag): nichts neu gerechnet
        unchanged = {h: window(h, [0, 1, 2], [1.0, 0.8, 0.5], [0.99, 0.95, 0.9], [230, 230, 230], 3) for h in range(1, 91)}
        effect, _, changes = ursachen.ranking_effect(FakeStand(unchanged), {0: (days, nasdaq, {205})}, [True, True, False], 15, {0})
        self.assertEqual(effect.get("ranglisten_verglichen", 0), 0)
        self.assertEqual(changes, [])

    def test_a_third_stock_can_trigger_the_new_leader_through_the_ranks(self):
        """Gewichtete Rangliste: der Score kommt aus den Rängen von R² und Rendite in der Gruppe. Zieht eine dritte Aktie mit
        ihrer Rendite an der Spitzenreiterin vorbei, kostet sie diese einen Rang – Platz 1 wechselt, obwohl sich die Kurse der
        beiden Spitzenreiter nicht ändern. Die Suche nach den Auslösern findet die dritte Aktie – sie reicht allein aus."""
        days = np.arange(200, 230, dtype=np.int64)
        third = np.linspace(1.0, 1.7, 30) * (1 + 0.01 * np.sin(np.arange(30)))
        third[0], third[-1] = 1.0, 1.7
        r_third, r2_third, status = ursachen.window_values(days, third, 200, 15)
        self.assertEqual((round(r_third, 6), status), (0.7, 18))
        # 0: höchstes R², mittlere Rendite (vorn); 1: höchste Rendite; 2: Rendite 0.5 → 0.7 mit den ersetzten Kursen
        r = [0.6, 0.9, 0.5, 0.1, 0.2]
        r2 = [(1 + r2_third) / 2, r2_third - 0.01, r2_third, 0.5, 0.6]
        windows = {h: window(h, [0, 1, 2, 3, 4], r, r2, [200] * 5, 5) for h in range(1, 91)}
        _, _, changes = ursachen.ranking_effect(FakeStand(windows), {2: (days, third, {229})}, [True] * 5, 15, set())
        weighted = [c for c in changes if c["w"] == 50 and c["gruppe"] == "A"]
        self.assertEqual(len(weighted), 90)
        self.assertTrue([c for c in weighted if not c.get("nicht_untersucht")])
        for c in [c for c in weighted if not c.get("nicht_untersucht")]:
            self.assertEqual((c["platz1"], c["ausloeser"], c["allein"], c["platz_des_neuen_vorher"]), ([0, 1], [2], [2], 2))
            self.assertEqual(c["rendite"][0], (0.6, 0.6), "die bisherige Spitzenreiterin behält ihre Rendite")
        # reine Rendite: die dritte Aktie bleibt hinter Aktie 1 – dort kein neuer Platz 1
        self.assertFalse([c for c in changes if c["w"] == 0 and c.get("platz1")])

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


def base_report(**extra) -> dict:
    report = {
        "stand": "2026-10-23_3f7ce5f3", "stichtag": "2026-10-23", "abgerufen_utc": "2026-10-24T20:00:00Z", "ausgewaehlt": 500,
        "davon_aus_den_ersten_20": 350, "abruf": {"nasdaq_ok": 450}, "nocp_abruf": {"ok": 10, "mit_kursen": 10}, "nocp_felder": ["date", "price"],
        "tage": {"verglichen": 30000, "abweichend": 600, "abweichend_mit_nocp": 300}, "nur_eine_quelle": {}, "ursachen": {"offizieller_schlusskurs": 300, "ungeklaert": 300},
        "ungeklaert_gruende": {"nyse_gruppe_ohne_offiziellen_kurs": 290, "nocp_dritter_wert": 10},
        "aktien_mit_abweichung": 2, "aktien_mit_ereignis_im_zeitraum": {}, "ranglisten": {"ranglisten_verglichen": 100, "ranglisten_insgesamt": 1980, "spitze_geaendert": 2},
        "aktien": [
            {"aktie": "A", "boerse": "Nasdaq", "kursbereich": "unter 1 $", "top10": 37, "platz1": 3, "abweichend": 66, "groesste_abweichung_pct": 3.93,
             "ursachen": {"offizieller_schlusskurs": 60, "ungeklaert": 6}, "nocp_abrufbar": True, "minutenkurse_tage": 5, "ereignisse": {}, "rangwirkung": {"unter_ersten_10_vorher": 37, "unter_ersten_10_nachher": 35}},
            {"aktie": "B", "boerse": "NYSE", "kursbereich": "10–100 $", "top10": 0, "platz1": 0, "abweichend": 1, "groesste_abweichung_pct": 0.05,
             "ursachen": {"letzter_abschluss": 1}, "nocp_abrufbar": False, "minutenkurse_tage": 5, "ereignisse": {}, "rangwirkung": {}},
        ],
    }
    report.update(extra)
    return report


def decoded(lines: list[str]) -> str:
    return "\n".join(lines).replace("%0A", "\n").replace("%2C", ",").replace("%25", "%")


def leader_change(**extra) -> dict:
    change = {"h": 12, "gruppe": "A", "w": 30, "platz1": ["A", "Z2"], "raus": [], "rein": [], "platz_des_neuen_vorher": 2,
              "rendite_pct": {"A": [45.1, 44.2], "Z2": [44.9, 44.9]}, "r2": {"A": [0.91, 0.905], "Z2": [0.93, 0.93]},
              "ausloeser": [{"aktie": "A", "tage": [{"tag": "2026-10-16", "abweichung_pct": 0.36, "ursache": "nasdaq_gleich_nocp"}], "weitere_tage": 0}],
              "allein_ausreichend": ["A"], "ersetzte_aktien_im_zeitraum": 57}
    change.update(extra)
    return change


class Annotations(unittest.TestCase):
    def test_only_counts_letters_and_ranges_and_titles_without_commas(self):
        report = base_report()
        lines = ursachen.annotations(report)
        text = decoded(lines)
        self.assertIn("Ursache belegt für 300: Yahoo nicht der offizielle Schlusskurs der Heimatbörse (Nasdaq-Kurs = NOCP) 300; ungeklärt (Ursache offen) 300", text)
        # Prüfgrenze ist keine Ursache: ausdrücklich so benannt
        self.assertIn("Ungeklärte Tage – Prüfgrenze bzw. Befund (erklärt, warum kein Beleg möglich war, nicht die Abweichung): "
                      "Prüfgrenze: Heimatbörse der NYSE-Gruppe oder Cboe – offizieller Schlusskurs nicht frei abrufbar 290", text)
        self.assertIn("Befund ohne Ursache: Nasdaq-notiert – Stand, Nasdaq-Historie und NOCP drei verschiedene Kurse 10", text)
        self.assertIn("Platz 1 anders 2", text)
        self.assertIn("Aktie A (Nasdaq, unter 1 $", text)
        self.assertIn("Weitere 1 Aktien", text)
        # ungeklärte Tage: Fehler mit dem Grund im Titel – ein fehlerfrei gelaufenes Skript ist kein Beleg
        self.assertTrue(lines[0].startswith("::error title=Kursursachen: NICHT VOLLSTÄNDIG BELEGT – 300 von 600 abweichenden Tagen ungeklärt::"), lines[0][:120])
        for line in lines:
            self.assertNotIn(",", line.split("::", 2)[1], "Komma im Titel schneidet ihn ab")
        report["ursachen"] = {"offizieller_schlusskurs": 600}
        report["aktien"] = [s for s in report["aktien"] if s["aktie"] == "B"]
        self.assertTrue(ursachen.annotations(report)[0].startswith("::notice title=Kursursachen: jede Abweichung belegt (600 Tage)::"))
        report["abruf_fehlgeschlagen"] = 3
        self.assertTrue(ursachen.annotations(report)[0].startswith(
            "::error title=Kursursachen: UNVOLLSTÄNDIG – 3 Aktien ohne Antwort einer Quelle%2C 0 ohne Vergleichskurse; 0 von 600 abweichenden Tagen ungeklärt::"))

    def test_missing_comparison_prices_are_not_a_passed_check(self):
        """Auftrag vom 24.10.2026, 23:50 Uhr: „Fehlende Daten dürfen nicht als bestandene Prüfung zählen.“ Ohne
        Vergleichskurse ist die Prüfung unvollständig – auch wenn jede verglichene Abweichung belegt ist."""
        self.assertEqual(ursachen.verdict({"abruf_fehlgeschlagen": 0, "ohne_vergleichskurse": 2, "ursachen": {"rundung": 5}, "tage": {"abweichend": 5}}), "unvollstaendig")
        self.assertEqual(ursachen.verdict({"abruf_fehlgeschlagen": 0, "ohne_vergleichskurse": 0, "ursachen": {"rundung": 5}, "tage": {"abweichend": 5}}), "belegt")
        report = base_report(ursachen={"offizieller_schlusskurs": 600}, ohne_vergleichskurse=25)
        self.assertTrue(ursachen.annotations(report)[0].startswith("::error title=Kursursachen: UNVOLLSTÄNDIG – 0 Aktien ohne Antwort einer Quelle%2C 25 ohne Vergleichskurse"))

    def test_coverage_per_group_separates_compared_missing_prices_and_failed_fetch(self):
        groups = {
            "erste_10": {"verglichen": 147, "nocp_mit_nocp": 70, "nocp_nicht_nasdaq_notiert": 77, "keine_vergleichskurse": 10, "keine_vergleichskurse_nasdaq_ohne_kurse": 10},
            "erste_20": {"verglichen": 85, "nocp_mit_nocp": 40, "nocp_nicht_nasdaq_notiert": 45, "keine_vergleichskurse": 12, "keine_vergleichskurse_nasdaq_ohne_kurse": 12},
            "zufall": {"verglichen": 26, "nocp_mit_nocp": 9, "nocp_nicht_nasdaq_notiert": 17, "keine_vergleichskurse": 3, "keine_vergleichskurse_nasdaq_ohne_kurse": 3, "abruf_fehlgeschlagen": 121},
        }
        text = decoded(ursachen.annotations(base_report(abdeckung_je_gruppe=groups)))
        self.assertIn("erste 10: 157 Aktien – erfolgreich verglichen 147 (mit NOCP 70, ohne NOCP: nicht Nasdaq-notiert 77); keine Vergleichskurse 10 (Nasdaq ohne Kurse 10); Abruf fehlgeschlagen 0", text)
        self.assertIn("Plätze 11–20: 97 Aktien – erfolgreich verglichen 85", text)
        self.assertIn("Zufallsstichprobe: 150 Aktien – erfolgreich verglichen 26 (mit NOCP 9, ohne NOCP: nicht Nasdaq-notiert 17); keine Vergleichskurse 3 (Nasdaq ohne Kurse 3); Abruf fehlgeschlagen 121", text)
        self.assertIn("erste 20 gesamt (erste 10 und Plätze 11–20): 254 Aktien – erfolgreich verglichen 232", text)

    def test_each_new_leader_with_method_leaders_and_triggering_deviations(self):
        report = base_report(
            aenderungen_nasdaq=[],
            aenderungen_offizieller_schlusskurs=[leader_change(), leader_change(h=45, gruppe="B", w=0, ausloeser=None, allein_ausreichend=[], platz_des_neuen_vorher=None)],
            zuordnung=[{"aktie": "A", "fundstelle": {"h": 30, "gruppe": "A", "w": 60, "platz": 1}},
                       {"aktie": "Z2", "fundstelle": {"h": 12, "gruppe": "B", "w": 30, "platz": 73}},
                       {"aktie": "Z3", "fundstelle": None}],
            weitere_buchstaben=[{"aktie": "Z2", "abgefragt": True, "boerse": "Nasdaq", "kursbereich": "über 100 $", "top10": 0, "abweichend": 0, "nocp_ungleich": 2}],
        )
        text = decoded(ursachen.annotations(report))
        self.assertIn("(a) Nasdaq-Kurs: in keiner Rangliste ein anderer Platz 1", text)
        self.assertIn("(b) offizieller Schlusskurs 1/2 – 12 Tage, Gruppe A, Gewichtung 30/70 (Gleichmäßigkeit 30 % und Rendite 70 %): bisher A, neu Z2 (vorher Platz 2); "
                      "A: Rendite +45.10 % → +44.20 %, R² 0.91 → 0.905; Z2: Rendite +44.90 % → +44.90 %, R² 0.93 → 0.93; "
                      "auslösend A: 2026-10-16 +0.360 % (Nasdaq-Historie = NOCP); allein ausreichend: A", text)
        self.assertIn("(b) offizieller Schlusskurs 2/2 – 45 Tage, Gruppe B, Gewichtung 0/100 (nur Kursrendite): bisher A, neu Z2 (vorher nicht in dieser Rangliste)", text)
        self.assertIn("Auslöser nicht auf einzelne Aktien eingrenzbar – Platz 1 wechselt erst mit allen 57 ersetzten Aktien des Zeitraums", text)
        # eindeutige Zuordnung jedes Buchstabens – über einen Platz in einer Rangliste des Stands, ohne Namen
        self.assertIn("A = Rangliste 30 Tage, Gruppe A, 60/40, Platz 1 (in der App: #/ranking?h=30&w=60&p=native&n=10)", text)
        self.assertIn("Z2 = Rangliste 12 Tage, Gruppe B, 30/70, Platz 73 (in der App: #/ranking?h=12&w=30&p=native&n=alle&g=b&seite=2) – Nasdaq, über 100 $", text)
        self.assertIn("Z3 = in keiner Rangliste dieses Stands", text)

    def test_long_lines_are_split_without_losing_text(self):
        long_line = "; ".join(f"Rangliste {k} Tage Gruppe A 60/40: raus Z{k} rein Z{k + 1} – „Ä“ → ✓" for k in range(400))
        parts = ursachen.split_lines([long_line, "kurz"])
        self.assertGreater(len(parts), 2)
        self.assertEqual(parts[-1], "kurz")
        limit = ursachen.gegen.MAX_ANNOTATION_BYTES - 300
        self.assertTrue(all(len(x.encode("utf-8")) <= limit for x in parts))
        rebuilt = " ".join([parts[0]] + [x[2:] for x in parts[1:-1]])
        self.assertEqual(rebuilt.replace(" ", ""), long_line.replace(" ", ""), "kein Text verloren")
        word = "x" * 9000  # ein Stück ohne „; “ und ohne Leerzeichen
        pieces = ursachen.split_lines([word])
        self.assertEqual("".join([pieces[0]] + [x[2:] for x in pieces[1:]]), word)
        self.assertTrue(all(len(x.encode("utf-8")) <= limit for x in pieces))

    def test_more_than_fifty_parts_are_distributed_and_the_rest_is_counted(self):
        """GitHub zeigt je Schritt höchstens 10 Hinweise je Art und je Job 50: Verteilung auf den Prüfschritt und vier Schritte
        „Einzelheiten“; was trotzdem nicht passt, nennt der letzte Hinweis – und alles steht in der Zusammenfassung des Jobs."""
        stock = dict(base_report()["aktien"][0])
        rows = [dict(stock, aktie=f"Z{k}", top10=1) for k in range(30, 30 + 600)]
        report = base_report(aktien=rows, aenderungen_offizieller_schlusskurs=[leader_change(h=h) for h in range(1, 91)])
        plan = ursachen.annotation_plan(report)
        self.assertEqual(len(plan["schritte"]), ursachen.MAX_STEPS)
        total = sum(len(step) for step in plan["schritte"])
        self.assertLessEqual(total, ursachen.MAX_JOB_ANNOTATIONS)
        for n, step in enumerate(plan["schritte"]):
            levels = Counter(line.split(" ", 1)[0] for line in step)
            for level, count in levels.items():
                self.assertLessEqual(count, ursachen.MAX_PER_STEP + (0 if n == 0 else 1), (n, level))
            for line in step:
                self.assertLessEqual(len(line.encode("utf-8")), 4000, "kein Hinweis über der Grenze, an der GitHub kürzt")
        self.assertGreater(plan["nicht_ausgegeben"], 0)
        self.assertEqual(plan["ausgegeben"] + plan["nicht_ausgegeben"], plan["teile"], "jedes Teil ausgegeben oder gezählt")
        closing = [line for step in plan["schritte"] for line in step if "Vollständigkeit der Hinweise" in line]
        self.assertEqual(len(closing), 1)
        self.assertIn(f"Nicht als Hinweis: {plan['nicht_ausgegeben']} von {plan['teile']} Teilen", decoded(closing))
        self.assertIn("vollständig in der Zusammenfassung dieses Jobs", decoded(closing))
        summary = ursachen.summary_markdown(report)
        for k in range(30, 30 + 600):
            self.assertIn(f"Aktie Z{k} (", summary)
        self.assertEqual(len(re.findall(r"\(b\) offizieller Schlusskurs \d+/90 – ", summary)), 90, "jede Rangliste mit neuem Platz 1 in der Zusammenfassung")

    def test_everything_fits_and_the_last_note_says_so(self):
        plan = ursachen.annotation_plan(base_report())
        self.assertEqual(plan["nicht_ausgegeben"], 0)
        lines = [line for step in plan["schritte"] for line in step]
        self.assertIn(f"Alle {plan['teile']} Teile als Hinweis ausgegeben", decoded(lines))
        self.assertLessEqual(Counter(line.split(" ", 1)[0] for line in plan["schritte"][0])["::notice"], ursachen.MAX_PER_STEP, "Platz für „Dauer“")

    def test_continuation_steps_print_their_part_of_the_plan(self):
        import contextlib
        import io
        import json
        import tempfile

        plan = {"schritte": [["::notice title=a::1"], ["::notice title=b::2", "::notice title=c::3"], [], [], []], "teile": 3, "ausgegeben": 3, "nicht_ausgegeben": 0}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hinweise.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ursachen.main(["--hinweise", str(path), "--teil", "2"]), 0)
            self.assertEqual(out.getvalue().splitlines(), ["::notice title=b::2", "::notice title=c::3"])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ursachen.main(["--hinweise", str(Path(tmp) / "fehlt.json"), "--teil", "3"]), 0)
            self.assertFalse(out.getvalue().startswith("::"), "ohne Ergebnis des Prüfschritts kein Hinweis")


if __name__ == "__main__":
    unittest.main()
