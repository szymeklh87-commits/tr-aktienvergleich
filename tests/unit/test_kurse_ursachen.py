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
from unittest import mock
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

    def cause(self, own=0.42, nasdaq_close=0.41, nasdaq_volume=1000.0, yahoo_volume=1000.0, adjclose=None, nocp=None, minute=None, previous_own=0.40, previous_nasdaq=0.40, kind="gross",
              splits=None, dividends=None, nasdaq_dividends=None, cutoff=None):
        nasdaq = {self.D: {"close": nasdaq_close, "volume": nasdaq_volume}}
        yahoo = {"days": {self.D: {"close": own, "volume": yahoo_volume, "adjclose": adjclose}}, "splits": splits or [], "dividends": dividends or []}
        minutes = {self.D: minute} if minute is not None else {}
        return ursachen.day_cause(self.D, own, nasdaq, yahoo, nocp, minutes, previous_own, previous_nasdaq, kind, nasdaq_dividends, cutoff)[0]

    def test_nasdaq_equal_to_the_official_close_is_a_finding_not_a_cause(self):
        """Auftrag vom 25.10.2026, 03:47 Uhr: „‚Yahoo weicht vom offiziellen Schlusskurs ab‘ beschreibt zunächst einen Befund.
        Eine Ursache gilt erst als belegt, wenn nachgewiesen ist, wodurch der Unterschied entsteht.“ Bis 1.18.2 zählte
        Nasdaq-Historie = NOCP und Stand nicht als belegte Ursache – seit dem 25.10.2026 ist das der Befund „abweichung_vom_nocp“,
        die Ursache bleibt offen."""
        self.assertEqual(self.cause(nocp={self.D: 0.41}), "abweichung_vom_nocp")
        self.assertIn("abweichung_vom_nocp", ursachen.OPEN)
        self.assertNotIn("abweichung_vom_nocp", ursachen.EVIDENCE)
        self.assertEqual(self.cause(nocp={self.D: 0.43}), "ungeklaert", "NOCP ein dritter Wert – kein Beleg")
        self.assertEqual(self.cause(nocp={self.D + 1: 0.41}), "ungeklaert", "NOCP nur an einem anderen Tag – kein Beleg")
        # Stand = letzte Minutenkerze vor 16:00 Uhr: seit dem 25.10.2026, 09:20 Uhr nur eine plausible Erklärung („Gleicher Kurs wie eine
        # Minutenkerze beweist allein keine ausgelassene Schlussauktion“) – die Ursache bleibt ungeklärt
        self.assertEqual(self.cause(nocp={self.D: 0.41}, minute=0.42), "letzter_abschluss")
        self.assertIn("letzter_abschluss", ursachen.PLAUSIBLE)
        self.assertNotIn("letzter_abschluss", ursachen.EVIDENCE)
        self.assertEqual(ursachen.evidence_class("letzter_abschluss"), "plausibel")
        self.assertEqual(ursachen.evidence_class("abweichung_vom_nocp"), "ohne_erklaerung")
        self.assertEqual(ursachen.unexplained_reason("NMS", {self.D: 0.41}, self.D, "abweichung_vom_nocp"), "nocp_anders")
        self.assertEqual(ursachen.unexplained_reason("NMS", {self.D: 0.41}, self.D, "letzter_abschluss", 0.41), "nocp_anders", "Nasdaq = NOCP: Befund, auch mit plausibler Erklärung")
        self.assertEqual(ursachen.unexplained_reason("NMS", None, self.D, "letzter_abschluss", 0.41, nocp_unsecured=True), "nocp_nicht_abgesichert")

    def test_nasdaq_equal_to_the_last_trade_explains_nothing_when_it_is_the_official_close(self):
        """Lauf 40158331688: An 12 Tagen war die Nasdaq-Historie zugleich der offizielle Schlusskurs (NOCP) und der letzte
        Abschluss vor 16:00 Uhr – „Nasdaq = letzter Abschluss“ erklärt dann nicht, warum der Stand abweicht: Befund, keine
        belegte Ursache. Ohne NOCP (NYSE-Gruppe) bleibt es belegt: der Nasdaq-Historie fehlt die Schlussauktion."""
        self.assertEqual(self.cause(nocp={self.D: 0.41}, minute=0.41), "abweichung_vom_nocp")
        self.assertEqual(self.cause(minute=0.41), "nasdaq_letzter_abschluss")
        self.assertEqual(self.cause(nocp={self.D: 0.40}, minute=0.41), "nasdaq_letzter_abschluss", "NOCP ein anderer Kurs: der Nasdaq-Historie fehlt die Schlussauktion")

    def test_cause_of_a_deviation_from_the_official_close(self):
        """Variante (b), jeder Tag mit Stand ≠ NOCP: belegt nur mit Kursstufe oder Stand = letzter Abschluss vor 16:00 Uhr."""
        self.assertEqual(ursachen.nocp_day_cause(self.D, 2.345, 2.34, {}), "rundung")
        self.assertEqual(ursachen.nocp_day_cause(self.D, 10.12, 10.00, {self.D: 10.12}), "letzter_abschluss")
        self.assertEqual(ursachen.nocp_day_cause(self.D, 10.12, 10.00, {self.D: 10.00}), "ungeklaert", "NOCP = letzter Abschluss, Stand ein anderer Kurs: kein Beleg für den Stand")
        self.assertEqual(ursachen.nocp_day_cause(self.D, 10.12, 10.00, {}), "ungeklaert")

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

    def test_dividend_adjustment_and_split_need_a_reported_event(self):
        """Seit dem 25.10.2026, 09:20 Uhr (Punkt 2): belegt nur mit gemeldetem Ereignis. Vergleichskurs = dividendenbereinigter Kurs:
        belegt mit einer Dividende nach dem Tag (Yahoo oder Nasdaq), sonst nur plausibel. Faktor zwischen den Kursen: belegt, wenn ein
        Split passenden Verhältnisses nach dem Tag (bis zum Kursstand) gemeldet ist und der bereinigte Kurs gleicht, sonst plausibel."""
        self.assertEqual(self.cause(own=10.0, nasdaq_close=9.8, adjclose=9.8), "dividende_ohne_ereignis")
        self.assertEqual(self.cause(own=10.0, nasdaq_close=9.8, adjclose=9.8, dividends=[self.D + 3]), "dividendenbereinigung")
        self.assertEqual(self.cause(own=10.0, nasdaq_close=9.8, adjclose=9.8, nasdaq_dividends=[self.D + 3], cutoff=self.D + 10), "dividendenbereinigung")
        self.assertEqual(self.cause(own=10.0, nasdaq_close=9.8, adjclose=9.8, dividends=[self.D - 3]), "dividende_ohne_ereignis", "Dividende vor dem Tag erklärt nichts")
        self.assertEqual(self.cause(own=10.0, nasdaq_close=9.8, adjclose=9.8, dividends=[self.D + 30], cutoff=self.D + 10), "dividende_ohne_ereignis", "nach dem Kursstand")
        # Stand splitbereinigt (10), Quelle unbereinigt (20): Split 2:1 nach dem Tag gemeldet → belegt
        self.assertEqual(self.cause(own=10.0, nasdaq_close=20.0, kind="faktor", splits=[(self.D + 5, 2.0)], cutoff=self.D + 10), "split")
        self.assertEqual(self.cause(own=10.0, nasdaq_close=20.0, kind="faktor"), "split_ohne_ereignis")
        self.assertEqual(self.cause(own=10.0, nasdaq_close=20.0, kind="faktor", splits=[(self.D - 5, 2.0)], cutoff=self.D + 10), "split_ohne_ereignis", "Split vor dem Tag")
        self.assertEqual(self.cause(own=10.0, nasdaq_close=30.0, kind="faktor", splits=[(self.D + 5, 2.0)], cutoff=self.D + 10), "split_ohne_ereignis", "anderes Verhältnis")
        self.assertEqual(ursachen.evidence_class("split"), "belegt")
        self.assertEqual(ursachen.evidence_class("split_ohne_ereignis"), "plausibel")
        for cause in ("rundung", "kein_handel", "nasdaq_letzter_abschluss", "dividende_ohne_ereignis"):
            self.assertEqual(ursachen.evidence_class(cause), "plausibel", cause)

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
    def test_green_only_when_complete_secured_and_every_deviation_has_evidence(self):
        """Grün nur, wenn jede Aktie abgesichert verglichen ist und jede Abweichung eine belegte Ursache hat – eine plausible Erklärung
        (Kursstufe, Minutenkerze, Umsatz 0) reicht seit dem 25.10.2026, 09:20 Uhr nicht."""
        cats = lambda **c: {"kategorien": {"nasdaq_historie": c}}  # noqa: E731
        self.assertEqual(ursachen.verdict({"abruf_fehlgeschlagen": 1}), "unvollstaendig")
        self.assertEqual(ursachen.verdict({"nicht_abgesichert": 2, **cats(abweichung=0)}), "unvollstaendig", "nicht abgesichert = nicht geprüft")
        self.assertEqual(ursachen.verdict(cats(abweichung=6, belegt=1, ohne_erklaerung=5)), "ungeklaert")
        self.assertEqual(ursachen.verdict(cats(abweichung=5, plausibel=5)), "ungeklaert", "plausibel ist nicht belegt")
        self.assertEqual(ursachen.verdict(cats(abweichung=5, belegt=5)), "belegt")
        self.assertEqual(ursachen.verdict(cats(abweichung=3, stand_ist_nocp=3)), "belegt", "Stand = NOCP: abweichend nur die Vergleichsquelle")
        self.assertEqual(ursachen.verdict(cats(uebereinstimmung=9)), "keine_abweichungen")
        self.assertEqual(ursachen.open_days({"kategorien": {"a": {"abweichung": 4, "plausibel": 1, "ohne_erklaerung": 2}, "b": {"abweichung": 1, "belegt": 1}}}), (5, 3, 1))

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

    def test_order_of_the_first_ten_and_whether_the_trigger_is_needed(self):
        """Seit dem 25.10.2026 (Auftrag 25.10.2026, Punkt 1 und 4): in der gemeinsamen Rechnung auch jede Rangliste, deren erste 10 bei
        gleichen Aktien anders geordnet sind (Plätze vorher/nachher), und je neuem Platz 1, ob er auch ohne die Auslöser –
        nur mit den übrigen ersetzten Kursen – wechseln würde."""
        days = np.arange(200, 230, dtype=np.int64)
        own = np.linspace(1.0, 2.0, 30)
        nasdaq = own.copy()
        nasdaq[-1] = 1.6  # Aktie 0: Rendite 1,0 → 0,6 (hinter Aktie 1)
        other = np.linspace(1.0, 1.55, 30)  # Aktie 2: Rendite 0,5 → 0,55, bleibt Dritte
        windows = {h: window(h, [0, 1, 2], [1.0, 0.8, 0.5], [0.99, 0.95, 0.9], [200, 200, 200], 3) for h in range(1, 91)}
        subs = {0: (days, nasdaq, {229}), 2: (days, other, {229})}
        effects = ursachen.ranking_effects(FakeStand(windows), {"x": subs, "y": {2: (days, other, {229})}}, [True, True, False], 15, set(), attribute={"x"}, order_details={"x", "y"})
        _, _, changes = effects["x"]
        top = [c for c in changes if c["w"] == 0 and c["gruppe"] == "A"]
        self.assertEqual(len(top), 90)
        for c in top:
            self.assertEqual(c["platz1"], [0, 1])
            self.assertEqual(c["reihenfolge"], {"plaetze": [1, 2], "vorher": [0, 1], "nachher": [1, 0]})
            self.assertEqual(c["ersetzt"], [0, 2], "Aktien mit ersetzten Kursen unter den ersten 10")
            if not c.get("nicht_untersucht"):
                self.assertEqual(c["ausloeser"], [0])
                self.assertEqual(c["ohne_ausloeser"], 0, "nur mit den Kursen von Aktie 2 bleibt Aktie 0 vorn: Auslöser nötig")
        # nur Aktie 2 ersetzt: in der reinen Rendite (0/100) bleibt die Reihenfolge – dort keine Zeile
        self.assertEqual([c for c in effects["y"][2] if c["w"] == 0], [])

    def test_triggers_are_the_smallest_set_that_changes_place_one(self):
        """Lauf 40158331688: Die Suche hatte Aktien unter die Auslöser gesetzt, die sie nur unterwegs hinzunahm – sie nahm die
        ersetzten Aktien nach der Größe ihrer Änderung hinzu, bis Platz 1 wechselte. Seit dem 25.10.2026 die kleinste Menge:
        jede Aktie, die allein reicht; sonst schrittweise hinzunehmen und nicht nötige wieder weglassen. Hier ändern zwei
        Aktien ihre Rendite stärker als die dritte, die allein den Wechsel auslöst – Auslöser ist nur die dritte."""
        days = np.arange(200, 230, dtype=np.int64)
        third = np.linspace(1.0, 1.7, 30) * (1 + 0.01 * np.sin(np.arange(30)))
        third[0], third[-1] = 1.0, 1.7
        r_third, r2_third, _ = ursachen.window_values(days, third, 200, 15)
        noisy = lambda end: np.concatenate(([1.0], np.linspace(1.0, end, 30)[1:-1] * (1 + 0.04 * np.sin(np.arange(1, 29) * 1.7)), [end]))  # noqa: E731
        big3, big4 = noisy(1.45), noisy(1.5)
        for series, expected in ((big3, 0.45), (big4, 0.5)):
            r, r2, st = ursachen.window_values(days, series, 200, 15)
            self.assertAlmostEqual(r, expected)
            self.assertEqual(st, 18)
            self.assertLess(r2, r2_third - 0.01, "R² bleibt unter dem der ersten drei")
        r = [0.6, 0.9, 0.5, 0.1, 0.2]
        r2 = [(1 + r2_third) / 2, r2_third - 0.01, r2_third, 0.5, 0.6]
        windows = {h: window(h, [0, 1, 2, 3, 4], r, r2, [200] * 5, 5) for h in range(1, 91)}
        subs = {2: (days, third, {229}), 3: (days, big3, {229}), 4: (days, big4, {229})}
        _, _, changes = ursachen.ranking_effect(FakeStand(windows), subs, [True] * 5, 15, set())
        studied = [c for c in changes if c["w"] == 50 and c["gruppe"] == "A" and not c.get("nicht_untersucht")]
        self.assertTrue(studied)
        for c in studied:
            self.assertEqual(c["platz1"], [0, 1])
            self.assertEqual(c["ausloeser"], [2], "nur die Aktie, die allein reicht – nicht die zwei mit größerer Änderung")
            self.assertEqual(c["allein"], [2])
            self.assertEqual(c["ohne_ausloeser"], 0, "mit den Kursen der beiden anderen allein bleibt Aktie 0 vorn")

    def test_new_leader_through_a_third_stock_with_score_and_position(self):
        """Lauf 40160248028: Platz 1 wechselte, obwohl Rendite und R² beider Spitzenreiter gleich blieben – der Score hängt von
        den Perzentilen in der Vergleichsmenge ab. Seit dem 25.10.2026 nennt die Zeile den Score wie in der App vorher/nachher
        und die Lage des Auslösers gegenüber den Werten beider Spitzenreiter. Hier (Gewichtung 40/60, vier Aktien): Aktie 2
        steigt mit ihrer Rendite von unter beiden auf zwischen beide – Aktie 0 verliert einen Rang der Rendite, Aktie 1 nicht."""
        members = np.array([0, 1, 2, 3], dtype=np.int64)
        status = np.array([18, 18, 18, 18], dtype=np.uint8)
        r_of, r2_of = {0: 0.6, 1: 0.9, 2: 0.5, 3: 0.1}, {0: 0.95, 1: 0.80, 2: 0.85, 3: 0.40}
        r_new = {**r_of, 2: 0.7}
        before = ursachen.lists_of(ursachen.nachrechnen.rank_group(members, status, r_of, r2_of))["40"]
        after = ursachen.lists_of(ursachen.nachrechnen.rank_group(members, status, r_new, r2_of))["40"]
        self.assertEqual((before[0], after[0]), (0, 1))
        c = ursachen.leader_change(members, "40", before, after[0], [2], (status, r_of, r2_of), (status.copy(), r_new, dict(r2_of)), {i: 200 for i in range(4)})
        self.assertEqual(c["ausloeser"], [2])
        self.assertEqual(c["rendite"], {0: (0.6, 0.6), 1: (0.9, 0.9)}, "Werte beider Spitzenreiter unverändert")
        self.assertEqual(c["vergleichsmenge"], (4, 4))
        s0, s1 = c["score"][0], c["score"][1]  # je (vorher, nachher)
        # Perzentil = 100 · (Rang − 1) / (M − 1): Aktie 0 Rendite Rang 3 → 2, R² Rang 4; Aktie 1 Rendite Rang 4, R² Rang 2
        self.assertAlmostEqual(s0[0]["p_rendite"], 200 / 3)
        self.assertAlmostEqual(s0[1]["p_rendite"], 100 / 3)
        self.assertAlmostEqual(s0[0]["p_r2"], 100.0)
        self.assertAlmostEqual(s0[0]["score"], 80.0)
        self.assertAlmostEqual(s0[1]["score"], 60.0)
        self.assertAlmostEqual(s1[0]["score"], 0.4 * 100 / 3 + 60.0)
        self.assertAlmostEqual(s1[1]["score"], 0.4 * 100 / 3 + 60.0, msg="Aktie 1 unverändert")
        values = c["ausloeser_werte"][2]
        self.assertEqual(values["lage_rendite"], ("unter_beiden", "zwischen"))
        self.assertEqual(values["lage_r2"], ("zwischen", "zwischen"))
        self.assertEqual(values["in_vergleichsmenge"], (True, True))
        # Text: Score und Lage in der Zeile, Buchstaben statt Nummern
        letters = ursachen.Lettering([0, 1, 2, 3], lambda i: "verglichen", {}, {})
        row = letters.changes([{"h": 30, "gruppe": "A", "w": 40, "platz1": [0, 1], "raus": [], "rein": [], "ersetzt": [2], **c}], {2: {229: (1.5, "stand_ist_letzter_abschluss")}})[0]
        line = ursachen._leader_line(row, "gemeinsam b", 1, 1)
        self.assertIn("A: Rendite +60.00 % → +60.00 %, R² 0.95 → 0.95, Score 80.000 → 60.000 (Perzentil der Rendite 66.667 → 33.333, des R² 100.000 → 100.000)", line)
        self.assertIn("B: Rendite +90.00 % → +90.00 %, R² 0.8 → 0.8, Score 73.333 → 73.333", line)
        self.assertIn("Vergleichsmenge (4 → 4 Aktien)", line)
        self.assertIn("auslösend C (Rendite +50.00 % → +70.00 %, gegenüber A und B: unter beiden → zwischen beiden; R² 0.85 → 0.85: zwischen beiden → zwischen beiden)", line)

    def test_compare_orders(self):
        self.assertEqual(ursachen.compare_orders([1, 2, 3], [1, 2, 3]), {"spitze": False, "top10_aktien": False, "top10_reihenfolge": False, "reihenfolge": False})
        self.assertEqual(ursachen.compare_orders([1, 2, 3], [2, 1, 3]), {"spitze": True, "top10_aktien": False, "top10_reihenfolge": True, "reihenfolge": True})


class TriggerSearch(unittest.TestCase):
    """Auftrag vom 25.10.2026, 09:20 Uhr, Punkt 5: „Prüfe, ob das Verfahren tatsächlich die kleinste Auslösermenge findet. Schrittweises
    Hinzufügen und Entfernen garantiert das allgemein nicht. Verwende eine nachweislich geeignete Suche oder benenne Ergebnis und
    Suchgrenzen korrekt.“"""

    def test_fast_doubled_ranks_equal_the_independent_ones(self):
        rng = np.random.default_rng(7)
        for n in (1, 2, 5, 50, 400):
            values = np.round(rng.normal(size=n), 1)  # viele Gleichstände
            if n > 3:
                values[0] = np.nan
            self.assertEqual(ursachen.doubled_ranks_fast(values).tolist(), ursachen.nachrechnen.doubled_ranks(values).tolist(), n)
        self.assertEqual(ursachen.doubled_ranks_fast(np.array([])).tolist(), [])

    def test_fast_leader_equals_the_independent_ranking_for_random_subsets(self):
        """Platz 1 je Teilmenge vektorisiert gerechnet – gleich dem Platz 1 aus ``nachrechnen.rank_group`` für 0/100, 100/0 und gemischte
        Gewichtungen, auch wenn Aktien in die Vergleichsmenge U eintreten oder aus ihr fallen und bei Gleichständen."""
        rng = np.random.default_rng(11)
        n = 60
        members = np.arange(n, dtype=np.int64)
        for trial in range(25):
            status = np.where(rng.random(n) < 0.8, 18, 16).astype(np.uint8)
            r_of = {i: float(np.round(rng.normal(0.1, 0.2), 2)) for i in range(n)}
            r2_of = {i: (float(np.round(rng.random(), 2)) if status[i] == 18 else None) for i in range(n)}
            status_new = status.copy()
            r_new, r2_new = dict(r_of), dict(r2_of)
            touched = [int(x) for x in rng.choice(n, size=12, replace=False)]
            for j in touched:
                status_new[j] = 18 if rng.random() < 0.7 else 16
                r_new[j] = float(np.round(r_of[j] + rng.normal(0, 0.1), 2))
                r2_new[j] = float(np.round(rng.random(), 2)) if status_new[j] == 18 else None
            for w in ("0", "40", "50", "100"):
                fast = ursachen.LeaderSearch(members, w, (status, r_of, r2_of), (status_new, r_new, r2_new))
                for size in (0, 1, 3, 12):
                    subset = touched[:size]
                    st, r, r2 = status.copy(), dict(r_of), dict(r2_of)
                    for j in subset:
                        st[j], r[j], r2[j] = status_new[j], r_new[j], r2_new[j]
                    expected = ursachen.lists_of(ursachen.nachrechnen.rank_group(members, st, r, r2))[w]
                    self.assertEqual(fast.leader(subset), int(expected[0]) if len(expected) else None, (trial, w, size))
                    self.assertEqual(fast.leader_full(subset), int(expected[0]) if len(expected) else None, (trial, w, size, "vollständig"))
                if w in ("40", "50"):
                    self.assertTrue(fast.incremental, "gewichtete Rangliste: berichtigte Ränge statt vollständiger Neurechnung")

    def test_exact_search_finds_a_smaller_set_than_adding_and_removing(self):
        """Gegenbeispiel: Platz 1 wechselt mit {4, 5} oder mit {1, 2, 3}. Schrittweises Hinzufügen (Reihenfolge 1, 2, 3, 4, 5) und
        Weglassen ergibt {1, 2, 3} – irreduzibel, aber nicht die kleinste. Die Suche nach Größe findet {4, 5} und weist nach, dass
        keine einzelne Aktie reicht."""
        def leader_of(subset):
            s = set(subset)
            return "neu" if {4, 5} <= s or {1, 2, 3} <= s else "alt"

        exact = ursachen.minimal_triggers(leader_of, [1, 2, 3, 4, 5], "neu", budget=1000, order_key=lambda j: j)
        self.assertEqual((exact["verfahren"], exact["nachgewiesen"], exact["groesse"], exact["mengen"]), ("exakt", True, 2, [[4, 5]]))
        self.assertEqual(exact["geprueft_bis"], 2)
        # Budget nur für die einzelnen Aktien: irreduzible Menge mit benannter Grenze – ausdrücklich nicht „kleinste“
        bounded = ursachen.minimal_triggers(leader_of, [1, 2, 3, 4, 5], "neu", budget=5, order_key=lambda j: j)
        self.assertEqual((bounded["verfahren"], bounded["nachgewiesen"], bounded["mengen"], bounded["geprueft_bis"], bounded["mindestens"]),
                         ("irreduzibel", False, [[1, 2, 3]], 1, 2))
        # jede einzelne Aktie, die allein reicht, ist eine kleinste Menge (Größe 1, nachgewiesen)
        singles = ursachen.minimal_triggers(lambda s: "neu" if 3 in s or 5 in s else "alt", [1, 2, 3, 4, 5], "neu", budget=10)
        self.assertEqual((singles["groesse"], singles["mengen"], singles["nachgewiesen"]), (1, [[3], [5]], True))

    def test_leader_change_cross_checks_each_trigger_alone_and_without(self):
        """Gegenprobe wie für Z31 im Lauf 40162120622: der Auslöser allein ergibt den neuen Platz 1, alle übrigen ersetzten Kurse ohne
        ihn lassen den bisherigen Spitzenreiter vorn."""
        members = np.array([0, 1, 2, 3], dtype=np.int64)
        status = np.array([18, 18, 18, 18], dtype=np.uint8)
        r_of, r2_of = {0: 0.6, 1: 0.9, 2: 0.5, 3: 0.1}, {0: 0.95, 1: 0.80, 2: 0.85, 3: 0.40}
        r_new = {**r_of, 2: 0.7, 3: 0.05}
        before = ursachen.lists_of(ursachen.nachrechnen.rank_group(members, status, r_of, r2_of))["40"]
        after = ursachen.lists_of(ursachen.nachrechnen.rank_group(members, status, r_new, r2_of))["40"]
        c = ursachen.leader_change(members, "40", before, after[0], [2, 3], (status, r_of, r2_of), (status.copy(), r_new, dict(r2_of)), {i: 200 for i in range(4)})
        self.assertEqual(c["ausloeser"], [2])
        self.assertEqual((c["suche"]["verfahren"], c["suche"]["nachgewiesen"], c["suche"]["groesse"], c["suche"]["schnell"]), ("exakt", True, 1, True))
        # Gegenprobe mit der unabhängigen Rechnung (nachrechnen.rank_group), nicht mit der schnellen Rechnung der Suche – seit dem
        # 25.10.2026, 11:45 Uhr; dazu jede einzelne ersetzte Aktie unabhängig: allein reicht nur C
        self.assertEqual(c["gegenprobe"], [{"aktie": 2, "allein": after[0], "ohne": before[0], "wie_suche": True}])
        self.assertEqual(c["einzeln_unabhaengig"], {"geprueft": 2, "allein": [2], "wie_suche": True})
        letters = ursachen.Lettering([0, 1, 2, 3], lambda i: "verglichen", {}, {})
        row = letters.changes([{"h": 30, "gruppe": "A", "w": 40, "platz1": [before[0], after[0]], "raus": [], "rein": [], "ersetzt": [2, 3], **c}], {2: {229: (1.5, "ungeklaert")}})[0]
        line = ursachen._leader_line(row, "(b)", 1, 1)
        self.assertIn("kleinste Auslösermenge 1 Aktie – nachweislich", line)
        self.assertIn("Gegenprobe C mit der unabhängigen Rechnung: allein → Platz 1 B (wie mit allen); alle übrigen ersetzten Kurse ohne C → Platz 1 A "
                      "(bisheriger Spitzenreiter: ohne diese Aktie kein Wechsel)", line)
        self.assertIn("jede der 2 ersetzten Aktien einzeln auch mit der unabhängigen Rechnung: allein ausreichend C – wie die Suche", line)
        self.assertNotIn("ABWEICHEND", line)
        # weicht die schnelle Rechnung der Suche von der unabhängigen ab, steht das am Wechsel – nie still übernommen
        row_off = dict(row, gegenprobe=[dict(row["gegenprobe"][0], wie_suche=False)], einzeln_unabhaengig=dict(row["einzeln_unabhaengig"], allein=["C", "D"], wie_suche=False))
        line_off = ursachen._leader_line(row_off, "(b)", 1, 1)
        self.assertIn("– ABWEICHEND von der schnellen Rechnung der Suche", line_off)
        self.assertIn("allein ausreichend C D – ABWEICHEND von der Suche", line_off)

    def test_independent_cross_check_uses_the_independent_ranking(self):
        """Die Gegenprobe rechnet mit ``nachrechnen.rank_group`` – auch wenn die schnelle Rechnung der Suche gültig ist: eine
        verfälschte schnelle Rechnung (nur für einzelne Teilmengen) fällt in der Gegenprobe auf."""
        members = np.array([0, 1, 2, 3], dtype=np.int64)
        status = np.array([18, 18, 18, 18], dtype=np.uint8)
        r_of, r2_of = {0: 0.6, 1: 0.9, 2: 0.5, 3: 0.1}, {0: 0.95, 1: 0.80, 2: 0.85, 3: 0.40}
        r_new = {**r_of, 2: 0.7, 3: 0.05}
        before = ursachen.lists_of(ursachen.nachrechnen.rank_group(members, status, r_of, r2_of))["40"]
        after = ursachen.lists_of(ursachen.nachrechnen.rank_group(members, status, r_new, r2_of))["40"]
        real = ursachen.LeaderSearch.leader

        def skewed(self, subset):  # leere und volle Menge richtig, Aktie 3 allein fälschlich mit neuem Platz 1
            return after[0] if list(subset) == [3] else real(self, subset)

        with mock.patch.object(ursachen.LeaderSearch, "leader", skewed):
            c = ursachen.leader_change(members, "40", before, after[0], [2, 3], (status, r_of, r2_of), (status.copy(), r_new, dict(r2_of)), {i: 200 for i in range(4)})
        self.assertTrue(c["suche"]["schnell"])
        self.assertEqual(sorted(c["allein"]), [2, 3], "die verfälschte Suche hält auch 3 für ausreichend")
        self.assertEqual(c["einzeln_unabhaengig"], {"geprueft": 2, "allein": [2], "wie_suche": False})
        # beide Gegenproben weichen von der Suche ab: ohne 2 bleibt nur 3 – unabhängig der bisherige Platz 1, laut Suche der neue
        self.assertEqual([(g["aktie"], g["allein"] == after[0], g["ohne"] == before[0], g["wie_suche"]) for g in c["gegenprobe"]],
                         [(2, True, True, False), (3, False, False, False)])


class StockDays(unittest.TestCase):
    def test_each_stock_day_counted_once_official_close_first(self):
        """Auftrag Punkt 2: „Zähle überlappende Fälle verschiedener Vergleiche nicht als unabhängige Fälle zusammen.“ Maßgeblich ist der
        abgesicherte NOCP, sonst die Nasdaq-Historie; Stand = NOCP bei abweichender Nasdaq-Historie ist eine Übereinstimmung."""
        own = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0, 6: 1.0}
        a = {1: "gleich", 2: "ohne_erklaerung", 3: "plausibel", 4: "stand_ist_nocp", 5: "gleich"}
        b = {2: "ohne_erklaerung", 3: "gleich", 4: "gleich", 5: "plausibel"}
        out = ursachen.consolidate_days(own, a, b)
        self.assertEqual((out["uebereinstimmung"], out["ohne_erklaerung"], out["plausibel"], out["ohne_vergleich"], out["verglichen"]), (3, 1, 1, 1, 5))
        self.assertEqual((out["abweichend_in_beiden"], out["abweichend_nur_nasdaq_historie"], out["abweichend_nur_nocp"]), (1, 2, 1))
        report = {"je_aktie_und_tag": dict(out), "je_aktie_und_tag_zusatz": {"belegt": 2, "plausibel": 1}}
        self.assertEqual({k: ursachen.unique_days(report)[k] for k in ("abweichend", "ungeklaert", "plausibel")}, {"abweichend": 5, "ungeklaert": 3, "plausibel": 2})


class Reconciliation(unittest.TestCase):
    """Lauf 40181869022 (Auftrag Punkt 2, „Überprüfe die bisher als belegt gezählten 49, 56 und 2 Fälle“): Vergleiche, deren Zuordnung jetzt
    nicht ausreichend abgesichert ist, zählen weder als Bestätigung noch als Ursache – für den Abgleich mit den Läufen vor der Absicherung
    werden ihre Tage aber gezählt, mit der Einordnung, die sie in einem abgesicherten Vergleich bekämen."""

    def test_unsecured_days_are_counted_with_the_class_they_would_get(self):
        days = [day("2026-10-19") + k for k in range(5)]
        own = {d: 10.0 for d in days}
        own[days[2]] = 10.05  # = letzte Minutenkerze, Nasdaq anders
        own[days[4]] = 10.20  # ohne Erklärung
        nasdaq = {d: {"close": 10.0, "volume": 100.0} for d in days}
        nocp = {d: 10.0 for d in days}
        minutes = {days[2]: 10.05}
        out = ursachen.diagnose_unsecured(own, nasdaq, nocp, {"days": {}, "splits": []}, minutes, days[0], days[-1])
        n = out["nasdaq"]
        self.assertEqual((n["tage"], n["gleich"], n["abweichend"]), (5, 3, 2))
        self.assertEqual((n["ursache_letzter_abschluss"], n["ursache_abweichung_vom_nocp"]), (1, 1))
        b = out["nocp"]
        self.assertEqual((b["tage"], b["gleich"], b["abweichend"], b["ursache_letzter_abschluss"], b["ursache_befund_nasdaq_gleich_nocp"]), (5, 3, 2, 1, 1))
        self.assertEqual(ursachen.diagnose_unsecured(own, None, None, {}, {}, days[0], days[-1]), {})
        self.assertEqual(ursachen.deviating_days(own, nasdaq, None), 2)
        lines = ursachen._reconcile_lines(dict(n, aktien=1), dict(b, aktien=1))
        self.assertEqual(len(lines), 1)
        self.assertIn("nicht ausreichend abgesicherte Vergleiche, nur gezählt (weder Bestätigung noch Ursache noch Ersatzkurs)", lines[0])
        self.assertIn("Nasdaq-Historie 1 Aktien, 5 Tage verglichen, gleich 3, abweichend 2", lines[0])
        self.assertIn("Stand = letzte Minutenkerze (plausibel) 1", lines[0])
        self.assertIn("Befund: Nasdaq-Historie = NOCP 1", lines[0])
        self.assertEqual(ursachen._reconcile_lines({}, None), [])


class Legend(unittest.TestCase):
    def test_gaps_name_exchange_range_places_and_reason(self):
        """Lauf 40181869022: ein neuer Platz 1 ohne Vergleichskurse erschien nur als „ausgewählt, aber ohne Vergleichskurse“ – jetzt mit
        Börse, Kursbereich, Plätzen, ungeprüften Tagen und Grund (bei nicht abgesicherten auch den nicht bestandenen Prüfungen)."""
        names = ursachen.Lettering([], lambda i: {1: "ohne_vergleichskurse", 2: "nicht_abgesichert"}[i], {}, {1: 12, 2: 3},
                                   gaps={1: {"boerse": "XWAR", "kursbereich": "unter 1 (Landeswährung)", "grund": "nicht_gefunden", "pruefungen": "", "tage_stand": 70},
                                         2: {"boerse": "XSTO", "kursbereich": "10–100 (Landeswährung)", "grund": "nicht_abgesichert", "pruefungen": "aktie,kursniveau", "tage_stand": 68,
                                             "befund": "ISIN bei OpenFIGI unbekannt (Prüfziffer der ISIN gültig, Land SE); Kursniveau Stand/Quelle im Median 1.200 (erlaubt 0.98 bis 1.02)"}},
                                   first_places={1: 3})
        names(1), names(2)
        first, second = (ursachen._legend(x) for x in names.legend)
        self.assertIn("ohne Vergleichskurse", first)
        self.assertIn("XWAR, unter 1 (Landeswährung); unter den ersten 10 in 12 Ranglisten, Platz 1 in 3; 70 Tage im Stand ungeprüft; Grund: bei CNBC unter keiner "
                      "Schreibweise des Kürzels gefunden", first)
        self.assertIn("nicht bestanden: Aktie und Gattung (ISIN → Kürzel laut OpenFIGI), Kursniveau; Befund: ISIN bei OpenFIGI unbekannt (Prüfziffer der ISIN gültig, "
                      "Land SE); Kursniveau Stand/Quelle im Median 1.200 (erlaubt 0.98 bis 1.02)", second)
        self.assertNotIn("Befund", first, "ohne Befund kein leerer Zusatz")
        self.assertEqual(ursachen.venue_label("PNK"), "OTC")
        self.assertEqual(ursachen.venue_label("NYQ"), "NYSE")
        self.assertEqual(ursachen.venue_label("NMS"), "Nasdaq")
        self.assertEqual(ursachen.venue_label(None), "andere")

    def test_unchecked_leaders_per_stock(self):
        lines = ursachen._unchecked_leader_lines({"platz1_ungeprueft": [{"h": 30, "gruppe": "A", "w": 10, "aktie": "Z33", "zustand": "ohne_vergleichskurse"},
                                                                       {"h": 31, "gruppe": "A", "w": 10, "aktie": "Z33", "zustand": "ohne_vergleichskurse"},
                                                                       {"h": 58, "gruppe": "B", "w": 90, "aktie": "Z64", "zustand": "nicht_abgesichert"}]})
        self.assertIn("3 Ranglisten, 2 Aktien", lines[0])
        self.assertEqual(lines[1], "Z33 (ohne Vergleichskurse): 2 – 30/A/10, 31/A/10")
        self.assertEqual(lines[2], "Z64 (nicht abgesichert): 1 – 58/B/90")
        self.assertEqual(ursachen._unchecked_leader_lines({}), [])


class ShortForm(unittest.TestCase):
    """Lauf 40181869022: im Job „gemeinsame Wirkung“ fehlten 42 von 86 Teilen der Hinweise (GitHub: höchstens 50 je Job) – die Hinweise
    stehen jetzt in Kurzform, die Zusammenfassung des Jobs behält die Langform."""

    def test_same_leader_in_a_combined_variant_is_written_short(self):
        b = leader_change(score={"A": [{"score": 99.0, "p_rendite": 99.0, "p_r2": 99.0}] * 2, "Z2": [{"score": 98.9, "p_rendite": 98.0, "p_r2": 99.5}] * 2},
                          vergleichsmenge=[2929, 2929])
        bc = dict(b, gleich_mit_teil=["b"], suche=dict(b["suche"], kandidaten=60, auswertungen=60))
        self.assertTrue(ursachen._same_leader(bc, b))
        self.assertFalse(ursachen._same_leader(dict(bc, platz1=["A", "Z9"]), b))
        line = ursachen._leader_short(bc, "gemeinsam bc", 1, 2, "b", 1, 2)
        self.assertEqual(line, "gemeinsam bc 1/2 – 12/A/30: bisher A, neu Z2 – Rendite, R², Score und Perzentile wie in (b) 1/2; kleinste Auslösermenge 1 – nachweislich "
                               "(60 ersetzte Aktien, 60 Auswertungen): A; Gegenprobe A (unabhängige Rechnung): allein → Z2, ohne → A; einzeln unabhängig 57 geprüft: "
                               "allein ausreichend A; ebenso mit (b) allein")

    def test_members_and_orders_in_one_line_per_variant(self):
        changes = {"b": [{"h": 31, "gruppe": "A", "w": 20, "raus": ["G"], "rein": ["E"], "ersetzt": ["E"]},
                         {"h": 24, "gruppe": "A", "w": 0, "raus": [], "rein": [], "ersetzt": ["Z31"],
                          "reihenfolge": {"plaetze": [5, 6, 7, 8], "vorher": ["Z", "Z32", "Z31", "Z27"], "nachher": ["Z32", "Z", "Z27", "Z31"]}}],
                   "bc": []}
        members = ursachen._member_rows_short(changes, ("b", "bc"))
        self.assertEqual(members, [ursachen.SHORT_FORM_NOTE, "gemeinsam b (1): 31/A/20 raus G rein E*"])
        orders = ursachen._order_rows_short(changes, ("b", "bc"))
        self.assertEqual(orders, [ursachen.SHORT_FORM_NOTE, "gemeinsam b (1): 24/A/0 Pl. 5–8: Z Z32 Z31* Z27 → Z32 Z Z27 Z31*"])
        self.assertEqual(ursachen._order_rows_short({"b": []}, ("b",)), [])
        self.assertEqual(ursachen._places_text([2, 3]), "2, 3")

    def test_source_per_stock_and_day_with_codes(self):
        sources = {"je_aktie": [{"aktie": "Z31", "quelle": ["nocp"], "tage": [["2026-07-20", "b", "nocp", 2.6, "nasdaq_gleich_stand"],
                                                                             ["2026-09-17", "b", "nocp", -0.01, "letzter_abschluss"]]}]}
        rows = ursachen._source_rows(sources, compact=True)
        self.assertIn("s = Nasdaq-Historie = Stand, NOCP anders", rows[0])
        self.assertEqual(rows[1], "Z31 (b) NOCP 2: 20.07 +2.60 s, 17.09 -0.01 m")
        self.assertEqual(ursachen._source_rows(sources)[0], "Aktie Z31 – (b) offizieller Schlusskurs NOCP, 2 Tage: 20.07.26 +2.60 % Nasdaq-Historie = Stand, NOCP anders, "
                                                            "17.09.26 -0.01 % Stand = letzte Minutenkerze (plausibel)")


class Interaction(unittest.TestCase):
    def test_changes_that_arise_only_together_or_cancel_out(self):
        """Auftrag Punkt 1: „Prüfe ausdrücklich, ob Änderungen erst gemeinsam entstehen oder sich gegenseitig aufheben.“"""
        stats, examples = Counter(), []
        before = [0, 1, 2, 3]
        # erst gemeinsam: P und Q allein lassen Platz 1, gemeinsam wechselt er
        ursachen.interaction_step(stats, examples, before, [0, 2, 1, 3], [0, 1, 3, 2], [1, 0, 2, 3], {"h": 1, "gruppe": "A", "w": 0}, 4)
        # aufgehoben: P allein wechselt Platz 1, gemeinsam nicht (Q gleicht aus)
        ursachen.interaction_step(stats, examples, before, [1, 0, 2, 3], before, before, {"h": 2, "gruppe": "A", "w": 0}, 4)
        # auch einzeln: P allein und gemeinsam derselbe neue Platz 1
        ursachen.interaction_step(stats, examples, before, [2, 0, 1, 3], before, [2, 0, 1, 3], {"h": 3, "gruppe": "B", "w": 50}, 4)
        self.assertEqual(stats["ranglisten"], 3)
        self.assertEqual((stats["spitze_erst_gemeinsam"], stats["spitze_aufgehoben"], stats["spitze_auch_einzeln"]), (1, 1, 1))
        self.assertEqual((stats["spitze_mit_p"], stats["spitze_mit_q"], stats["spitze_gemeinsam"]), (2, 0, 2))
        self.assertEqual([x["art"] for x in examples], ["erst_gemeinsam", "aufgehoben"])
        self.assertEqual(examples[0]["platz1"], [0, 0, 0, 1])
        # übrige Rangänderungen über die ganze Liste: im ersten Fall ändert sich die Lage von 0 und 1 erst gemeinsam
        self.assertGreater(stats["aktien_rang_erst_gemeinsam"], 0)
        self.assertGreater(stats["aktien_rang_aufgehoben"], 0)


class Transfer(unittest.TestCase):
    """Übergabe der Vergleichskurse an den Job „gemeinsame Wirkung“ (seit dem 25.10.2026): verschlüsselt mit dem Schlüssel des Stands,
    an Stand und Job gebunden, als Ausgabe des Jobs geschrieben – ohne Secrets im Schritt der Ausgabe."""

    def test_sealed_transfer_opens_only_for_the_same_stand_and_job(self):
        key = ursachen.crypto.derive_key("nur-fuer-den-test", b"0123456789abcdef", iterations=1000)
        data = {"format": ursachen.TRANSFER_FORMAT, "stand": "2026-10-23_3f7ce5f3", "auswahl": "erste10", "a": {"7": [[20748, 12.34, 0.5, "abweichung_vom_nocp"]]}}
        sealed = ursachen.seal(data, key, "2026-10-23_3f7ce5f3", "erste10")
        self.assertNotIn("12.34", sealed)
        self.assertNotIn("abweichung", sealed)
        self.assertEqual(ursachen.unseal(sealed, key, "2026-10-23_3f7ce5f3", "erste10"), data)
        for sid, leg in (("2026-10-23_3f7ce5f3", "zufall"), ("2026-10-26_00000000", "erste10")):
            with self.assertRaises(ursachen.crypto.ContainerError):
                ursachen.unseal(sealed, key, sid, leg)
        other = ursachen.crypto.derive_key("andere-passphrase", b"0123456789abcdef", iterations=1000)
        with self.assertRaises(ursachen.crypto.ContainerError):
            ursachen.unseal(sealed, other, "2026-10-23_3f7ce5f3", "erste10")

    def test_output_step_writes_the_sealed_transfer_for_the_next_job(self):
        import contextlib
        import io
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path, output = Path(tmp) / "uebergabe.txt", Path(tmp) / "github_output"
            path.write_text("plaetze11_20:QUJD", encoding="ascii")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ursachen.write_output(path, str(output)), 0)
            self.assertEqual(output.read_text(encoding="ascii"), "vergleich_plaetze11_20=QUJD\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ursachen.write_output(Path(tmp) / "fehlt.txt", str(output)), 0)
            self.assertIn("::warning title=Kursursachen: Übergabe::", out.getvalue())
            path.write_text("unbekannt:QUJD", encoding="ascii")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ursachen.write_output(path, str(output)), 1)

    def test_payload_has_a_checksum_over_the_replacement_prices(self):
        report = {"abgerufen_utc": "2026-10-25T05:00:00Z", "abdeckung_je_gruppe": {}, "kategorien": {}}
        repl = {"a": {3: {20748: 10.0}}, "b": {}, "c": {}}
        days = {"a": {3: {20748: (1.0, "ungeklaert")}}, "b": {}, "c": {}}
        one = ursachen.transfer_payload("s", "erste10", report, {3: "erste_10"}, {3}, {}, {}, {}, repl, days, {})
        repl["a"][3][20748] = 10.01
        two = ursachen.transfer_payload("s", "erste10", report, {3: "erste_10"}, {3}, {}, {}, {}, repl, days, {})
        self.assertEqual(len(one["pruefsumme"]), 16)
        self.assertNotEqual(one["pruefsumme"], two["pruefsumme"], "andere Kurse, andere Prüfsumme")
        self.assertEqual(one["a"], {"3": [[20748, 10.0, 1.0, "ungeklaert"]]})


class Fetching(unittest.TestCase):
    def test_error_name_keeps_the_kind_without_the_address(self):
        """Lauf vom 24.10.2026, 23:09 Uhr: 121 × „ConnectionError“ – ab jetzt mit der Art dahinter, ohne Adresse und Kürzel."""
        self.assertEqual(ursachen.error_name(ConnectionError("Anfrage an api.nasdaq.com endgültig fehlgeschlagen: Timeout")), "ConnectionError_Timeout")
        self.assertEqual(ursachen.error_name(ConnectionError("Anfrage an api.nasdaq.com endgültig fehlgeschlagen: ConnectionError")), "ConnectionError")
        self.assertEqual(ursachen.error_name(ValueError("https://api.nasdaq.com/api/quote/ABCD/historical: kaputt ab hier")), "ValueError")

    def test_class_shares_are_tried_in_other_spellings_at_nasdaq(self):
        """Lauf 40158331688: zwei Aktien mit Börse NYSE (Yahoo) ohne Kurse bei Nasdaq – Kürzel mit Aktiengattung. Seit dem
        25.10.2026 fragt das Skript nach „BRK.B“ auch „BRK/B“ und „BRK^B“; die erste Schreibweise mit Kursen gilt."""
        calls = []

        class Http:
            def get(self, url, headers=None):
                calls.append(url)
                if "BRK%2FB/historical" in url:
                    return types.SimpleNamespace(status_code=200, json=lambda: {"data": {"tradesTable": {"rows": [{"date": "10/23/2026", "close": "$1.00", "volume": "5"}]}}})
                if "api.nasdaq.com" in url:
                    return types.SimpleNamespace(status_code=200, json=lambda: {"data": None})
                return types.SimpleNamespace(status_code=200, json=lambda: {"chart": {"result": [{"meta": {"exchangeName": "NYQ", "gmtoffset": -14400}, "timestamp": [], "indicators": {"quote": [{}]}}]}})

        base = ursachen.fetch_base(Http(), "BRK-B", day("2026-06-01"), day("2026-10-23"))
        self.assertEqual(base["nasdaq_symbol"], "BRK%2FB")
        self.assertEqual(base.get("nasdaq_variante"), 1)
        self.assertEqual(list(base["nasdaq"]), [day("2026-10-23")])
        nasdaq_calls = [u for u in calls if "api.nasdaq.com" in u]
        self.assertEqual(len(nasdaq_calls), 2, "nach der Schreibweise mit Kursen keine weitere")
        # Lauf 40159274087: die zweite Schreibweise antwortete mit HTTP 404 – die dritte wird trotzdem versucht, und
        # „keine Kurse“ bleibt das Ergebnis (kein Abruffehler), wenn keine Schreibweise Kurse hat
        class Http404(Http):
            def get(self, url, headers=None):
                calls.append(url)
                if "%2F" in url:
                    return types.SimpleNamespace(status_code=404, json=lambda: None)
                if "%5E" in url and "/historical" in url:
                    return types.SimpleNamespace(status_code=200, json=lambda: {"data": {"tradesTable": {"rows": [{"date": "10/23/2026", "close": "$2.00", "volume": "5"}]}}})
                return Http.get(self, url, headers)

        calls.clear()
        base = ursachen.fetch_base(Http404(), "BRK-B", day("2026-06-01"), day("2026-10-23"))
        self.assertEqual((base["nasdaq_symbol"], base.get("nasdaq_variante"), base["nasdaq_status"]), ("BRK%5EB", 2, "ok"))
        self.assertEqual(base["nasdaq_varianten_status"], ["http_404"])

        class HttpNone(Http):
            def get(self, url, headers=None):
                calls.append(url)
                if "api.nasdaq.com" in url and "BRK.B" not in url:
                    return types.SimpleNamespace(status_code=404, json=lambda: None)
                return Http.get(self, url, headers) if "api.nasdaq.com" not in url else types.SimpleNamespace(status_code=200, json=lambda: {"data": None})

        base = ursachen.fetch_base(HttpNone(), "BRK-B", day("2026-06-01"), day("2026-10-23"))
        self.assertEqual((base["nasdaq"], base["nasdaq_status"]), ({}, "ok"), "keine Kurse – kein Abruffehler")
        self.assertIsNone(ursachen.base_failed(base))
        self.assertEqual(base["yahoo"]["exchange"], "NYQ", "Börse der Yahoo-Kurse trotzdem abgefragt")
        calls.clear()
        base = ursachen.fetch_base(Http(), "ABCDY", day("2026-06-01"), day("2026-10-23"))
        self.assertEqual(base["nasdaq"], {})
        self.assertEqual(len([u for u in calls if "api.nasdaq.com" in u]), 1, "ohne Aktiengattung nur eine Anfrage")
        self.assertEqual(base["yahoo"]["exchange"], "NYQ", "Börse der Yahoo-Kurse auch ohne Nasdaq-Kurse")

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
        "tage": {"verglichen": 30000, "abweichend": 600, "abweichend_mit_nocp": 300}, "nur_eine_quelle": {}, "ursachen": {"abweichung_vom_nocp": 300, "ungeklaert": 300},
        "kategorien": {
            "nasdaq_historie": {"uebereinstimmung": 29400, "abweichung": 600, "belegt": 0, "stand_ist_nocp": 0, "plausibel": 0, "ohne_erklaerung": 600, "ohne_vergleich_aktien": 38,
                                "ohne_vergleich_ohne_kurse": 36, "ohne_vergleich_tage": 4, "nicht_abgesichert_aktien": 2, "nicht_abgesichert_tage": 180},
            # Zahlen wie im Lauf 40184599190 (Summe der Teile = 227)
            "offizieller_schlusskurs": {"uebereinstimmung": 12232, "abweichung": 475, "belegt": 34, "plausibel": 21, "ohne_erklaerung": 420, "ohne_vergleich_aktien": 227,
                                        "ohne_vergleich_nicht_nasdaq_notiert": 180, "ohne_vergleich_nasdaq_ohne_nocp": 0, "ohne_vergleich_ohne_kurse": 38,
                                        "ohne_vergleich_nasdaq_nicht_abgesichert_ohne_nocp": 1, "nicht_abgesichert_aktien": 8, "nicht_abgesichert_tage": 496,
                                        "ohne_vergleich_tage": 12422},
            "zusatzquellen": {"uebereinstimmung": 0, "abweichung": 0, "belegt": 0, "plausibel": 0, "ohne_erklaerung": 0, "ohne_vergleich_aktien": 38, "ohne_vergleich_tage": 0},
        },
        "je_aktie_und_tag": {"verglichen": 30000, "uebereinstimmung": 29400, "ohne_erklaerung": 600, "abweichend_in_beiden": 300, "abweichend_nur_nasdaq_historie": 300},
        "nocp_ursachen": {"letzter_abschluss": 20, "rundung": 1, "befund_nasdaq_gleich_nocp": 300, "befund_nasdaq_gleich_stand": 100, "befund_drei_kurse": 20},
        "ungeklaert_gruende": {"nyse_gruppe_ohne_offiziellen_kurs": 290, "nocp_dritter_wert": 10},
        "aktien_mit_abweichung": 2, "aktien_mit_ereignis_im_zeitraum": {}, "ranglisten": {"ranglisten_verglichen": 100, "ranglisten_insgesamt": 1980, "spitze_geaendert": 2},
        "aktien": [
            {"aktie": "A", "boerse": "Nasdaq", "kursbereich": "unter 1 $", "top10": 37, "platz1": 3, "abweichend": 66, "groesste_abweichung_pct": 3.93,
             "ursachen": {"abweichung_vom_nocp": 60, "ungeklaert": 6}, "nocp_abrufbar": True, "minutenkurse_tage": 5, "ereignisse": {}, "rangwirkung": {"unter_ersten_10_vorher": 37, "unter_ersten_10_nachher": 35}},
            {"aktie": "B", "boerse": "NYSE", "kursbereich": "10–100 $", "top10": 0, "platz1": 0, "abweichend": 1, "groesste_abweichung_pct": 0.05,
             "ursachen": {"split": 1}, "nocp_abrufbar": False, "minutenkurse_tage": 5, "ereignisse": {}, "rangwirkung": {}},
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
              "allein_ausreichend": ["A"], "ersetzte_aktien_im_zeitraum": 57,
              "suche": {"verfahren": "exakt", "nachgewiesen": True, "groesse": 1, "geprueft_bis": 1, "auswertungen": 57, "kandidaten": 57, "schnell": True},
              "gegenprobe": [{"aktie": "A", "allein": "Z2", "ohne": "A", "wie_suche": True}], "weitere_mengen": [], "mengen_gleicher_groesse": 1,
              "einzeln_unabhaengig": {"geprueft": 57, "allein": ["A"], "wie_suche": True}}
    change.update(extra)
    return change


class Annotations(unittest.TestCase):
    def test_only_counts_letters_and_ranges_and_titles_without_commas(self):
        report = base_report()
        lines = ursachen.annotations(report)
        text = decoded(lines)
        # die Ergebnisarten getrennt (Auftrag 25.10.2026, 09:20 Uhr, Punkt 2): Übereinstimmung, Abweichung, belegt, plausibel, ohne Erklärung,
        # fehlende Prüfmöglichkeit, nicht abgesichert
        self.assertIn("Ergebnis gegen die Nasdaq-Historie (Tage, nur abgesicherte Vergleiche): bestätigte Übereinstimmung 29400; festgestellte Abweichung 600 – davon Ursache "
                      "belegt 0 (–), Stand = offizieller Schlusskurs 0 (abweichend nur die Nasdaq-Historie), ungeklärt mit plausibler Erklärung 0 (–), ungeklärt ohne Erklärung 600 "
                      "(Befund Stand ≠ NOCP bei Nasdaq-Historie = NOCP 300, ohne Befund 300); fehlende Prüfmöglichkeit: 38 Aktien ohne abgesicherte Nasdaq-Historie – ohne "
                      "Nasdaq-Kurse 36, Nasdaq-Kurse vorhanden, aber Zuordnung nicht ausreichend abgesichert 2 (deren 180 Tage nur gezählt: weder Ersatzkurs noch Bestätigung); "
                      "4 Tage nur im Stand", text)
        # Lauf 40184599190: „227 Aktien … ohne abgesicherten NOCP (nicht Nasdaq-notiert …)“ – darunter auch Aktien ohne Nasdaq-Kurse und nicht
        # abgesicherte; jetzt aufgeschlüsselt (die Teile ergeben die Summe)
        self.assertIn("fehlende Prüfmöglichkeit: 227 Aktien ohne abgesicherten NOCP – nicht Nasdaq-notiert 180 (offizieller Schlusskurs der NYSE-Gruppe in den geprüften "
                      "Quellen nur kostenpflichtig), Nasdaq-notiert ohne NOCP 0, ohne Nasdaq-Kurse 38, Nasdaq-Kurse nicht abgesichert und ohne NOCP 1, NOCP vorhanden, aber "
                      "Zuordnung nicht ausreichend abgesichert 8 (deren 496 Tage nur gezählt: weder Ersatzkurs noch Bestätigung); 12422 Tage ohne abgesicherten NOCP bei Aktien "
                      "mit abgesichertem Nasdaq-Vergleich", text)
        self.assertIn("Ergebnis gegen den offiziellen Schlusskurs NOCP (Tage, nur abgesicherte Vergleiche): bestätigte Übereinstimmung 12232; festgestellte Abweichung 475 – davon "
                      "Ursache belegt 34 (NOCP unbereinigt vor einem gemeldeten Split passenden Verhältnisses – nicht ersetzt), ungeklärt mit plausibler Erklärung 21 "
                      "(Stand = letzte Minutenkerze (plausibel) 20, Kursstufe (plausibel) 1), ungeklärt ohne Erklärung 420 (Befund: Stand, Nasdaq-Historie und NOCP verschieden 20, "
                      "Nasdaq-Historie = NOCP 300, Nasdaq-Historie = Stand, NOCP anders 100)", text)
        # je Aktie und Tag genau einmal: 300 Tage weichen in beiden Vergleichen ab – nicht 300 + 300 Fälle
        self.assertIn("ungeklärt ohne Erklärung 600; Überschneidung: in beiden Vergleichen abweichend 300, nur Nasdaq-Historie 300, nur NOCP 0", text)
        self.assertNotIn("Yahoo nicht der offizielle Schlusskurs der Heimatbörse", text, "ein Befund ist keine Ursache")
        # Prüfgrenze ist keine Ursache: ausdrücklich so benannt, mit den geprüften Quellen
        self.assertIn("Ungeklärte Tage gegen die Nasdaq-Historie – Prüfgrenze bzw. Befund (erklärt, warum kein Beleg möglich war, nicht die Abweichung): "
                      "Prüfgrenze: Heimatbörse der NYSE-Gruppe oder Cboe – offizieller Schlusskurs in den geprüften Quellen nicht frei verfügbar "
                      "(NYSE: nur im kostenpflichtigen Produkt „TAQ NYSE Closing Prices“) 290", text)
        self.assertNotIn("keine frei zugängliche Quelle", text)
        self.assertIn("Befund ohne Ursache: Nasdaq-notiert – Stand, Nasdaq-Historie und NOCP drei verschiedene Kurse 10", text)
        self.assertIn("Die ausgewählten US-Aktien sind keine Vollprüfung aller Aktien der App.", text)
        self.assertIn("Platz 1 anders 2", text)
        self.assertIn("Aktie A (Nasdaq, unter 1 $", text)
        self.assertIn("Weitere 1 Aktien", text)
        # ungeklärte Tage (Befund oder ohne Erklärung): Fehler mit dem Grund im Titel – ein fehlerfrei gelaufenes Skript ist kein Beleg
        self.assertTrue(lines[0].startswith("::error title=Kursursachen: NICHT VOLLSTÄNDIG BELEGT – 600 von 600 abweichenden Aktientagen ungeklärt (0 davon mit plausibler Erklärung)::"),
                        lines[0][:160])
        for line in lines:
            self.assertNotIn(",", line.split("::", 2)[1], "Komma im Titel schneidet ihn ab")
        # nur plausible Erklärungen: weiterhin nicht belegt
        report = base_report(kategorien={"nasdaq_historie": {"abweichung": 600, "plausibel": 600}}, je_aktie_und_tag={"plausibel": 600, "verglichen": 30000})
        self.assertTrue(ursachen.annotations(report)[0].startswith("::error title=Kursursachen: NICHT VOLLSTÄNDIG BELEGT – 600 von 600 abweichenden Aktientagen ungeklärt (600 davon mit plausibler"))
        report = base_report(kategorien={"nasdaq_historie": {"abweichung": 600, "belegt": 600}}, je_aktie_und_tag={"belegt": 600, "verglichen": 30000})
        report["aktien"] = [s for s in report["aktien"] if s["aktie"] == "B"]
        self.assertTrue(ursachen.annotations(report)[0].startswith("::notice title=Kursursachen: jede Abweichung belegt (600 Aktientage)::"))
        report["abruf_fehlgeschlagen"] = 3
        self.assertTrue(ursachen.annotations(report)[0].startswith(
            "::error title=Kursursachen: UNVOLLSTÄNDIG – 3 Aktien ohne Antwort einer Quelle%2C 0 ohne Vergleichskurse%2C 0 nicht abgesichert; 0 von 600 abweichenden Aktientagen ungeklärt"))

    def test_missing_comparison_prices_are_not_a_passed_check(self):
        """Auftrag vom 24.10.2026, 23:50 Uhr: „Fehlende Daten dürfen nicht als bestandene Prüfung zählen.“ Ohne
        Vergleichskurse ist die Prüfung unvollständig – auch wenn jede verglichene Abweichung belegt ist; ebenso seit dem 25.10.2026,
        09:20 Uhr ohne abgesicherte Zuordnung („Fehlende Angaben dürfen nicht automatisch als bestandene Prüfung gelten“)."""
        belegt = {"kategorien": {"nasdaq_historie": {"abweichung": 5, "belegt": 5}}}
        self.assertEqual(ursachen.verdict({"abruf_fehlgeschlagen": 0, "ohne_vergleichskurse": 2, **belegt}), "unvollstaendig")
        self.assertEqual(ursachen.verdict({"abruf_fehlgeschlagen": 0, "ohne_vergleichskurse": 0, "nicht_abgesichert": 1, **belegt}), "unvollstaendig")
        self.assertEqual(ursachen.verdict({"abruf_fehlgeschlagen": 0, "ohne_vergleichskurse": 0, **belegt}), "belegt")
        report = base_report(ohne_vergleichskurse=25, nicht_abgesichert=4)
        self.assertTrue(ursachen.annotations(report)[0].startswith("::error title=Kursursachen: UNVOLLSTÄNDIG – 0 Aktien ohne Antwort einer Quelle%2C 25 ohne Vergleichskurse%2C 4 nicht abgesichert"))

    def test_coverage_per_group_separates_compared_missing_prices_and_failed_fetch(self):
        groups = {
            "erste_10": {"verglichen": 151, "verglichen_nasdaq": 147, "verglichen_cnbc": 4, "nocp_mit_nocp": 70, "nocp_nicht_nasdaq_notiert": 77, "keine_vergleichskurse": 6,
                         "keine_vergleichskurse_nasdaq_ohne_kurse": 6},
            "erste_20": {"verglichen": 85, "nocp_mit_nocp": 40, "nocp_nicht_nasdaq_notiert": 45, "keine_vergleichskurse": 12, "keine_vergleichskurse_nasdaq_ohne_kurse": 12,
                         "nicht_abgesichert": 3, "nicht_abgesichert_nasdaq": 2, "nicht_abgesichert_zusatzquelle": 1},
            "zufall": {"verglichen": 26, "nocp_mit_nocp": 9, "nocp_nicht_nasdaq_notiert": 17, "keine_vergleichskurse": 3, "keine_vergleichskurse_nasdaq_ohne_kurse": 3, "abruf_fehlgeschlagen": 121},
        }
        text = decoded(ursachen.annotations(base_report(abdeckung_je_gruppe=groups)))
        self.assertIn("erste 10: 157 Aktien – abgesichert verglichen 151 (mit Nasdaq 147: mit NOCP 70, ohne NOCP: nicht Nasdaq-notiert 77; mit Zusatzquelle: CNBC 4); "
                      "nicht ausreichend abgesichert 0; keine Vergleichskurse 6 (weder Nasdaq noch eine Zusatzquelle 6); Abruf fehlgeschlagen 0", text)
        self.assertIn("Plätze 11–20: 100 Aktien – abgesichert verglichen 85", text)
        self.assertIn("nicht ausreichend abgesichert 3 (Nasdaq 2, Zusatzquelle 1)", text)
        self.assertIn("Zufallsstichprobe: 150 Aktien – abgesichert verglichen 26 (mit Nasdaq 26: mit NOCP 9, ohne NOCP: nicht Nasdaq-notiert 17); nicht ausreichend abgesichert 0; "
                      "keine Vergleichskurse 3 (weder Nasdaq noch eine Zusatzquelle 3); Abruf fehlgeschlagen 121", text)
        self.assertIn("erste 20 gesamt (erste 10 und Plätze 11–20): 257 Aktien – abgesichert verglichen 236", text)

    def test_each_new_leader_with_method_leaders_and_triggering_deviations(self):
        report = base_report(
            aenderungen_nasdaq=[],
            aenderungen_offizieller_schlusskurs=[
                leader_change(),
                leader_change(h=45, gruppe="B", w=0, ausloeser=[{"aktie": "A", "tage": [], "weitere_tage": 0}, {"aktie": "Z3", "tage": [], "weitere_tage": 0},
                                                           {"aktie": "Z4", "tage": [], "weitere_tage": 0}],
                              allein_ausreichend=[], platz_des_neuen_vorher=None,
                              suche={"verfahren": "irreduzibel", "nachgewiesen": False, "groesse": 3, "geprueft_bis": 2, "mindestens": 3, "auswertungen": 25000, "kandidaten": 300, "schnell": True},
                              gegenprobe=[], ohne_ausloeser="A"),
                leader_change(h=46, ausloeser=None, suche={"auswertungen": 0}, gegenprobe=[], nicht_untersucht="zeitbudget"),
            ],
            zuordnung=[{"aktie": "A", "fundstelle": {"h": 30, "gruppe": "A", "w": 60, "platz": 1}},
                       {"aktie": "Z2", "fundstelle": {"h": 12, "gruppe": "B", "w": 30, "platz": 73}},
                       {"aktie": "Z3", "fundstelle": None}],
            weitere_buchstaben=[{"aktie": "Z2", "abgefragt": True, "boerse": "Nasdaq", "kursbereich": "über 100 $", "top10": 0, "abweichend": 0, "nocp_ungleich": 2}],
        )
        text = decoded(ursachen.annotations(report))
        self.assertIn("(a) Nasdaq-Kurs: in keiner Rangliste ein anderer Platz 1", text)
        self.assertIn("(b) offizieller Schlusskurs 1/3 – 12 Tage, Gruppe A, Gewichtung 30/70 (Gleichmäßigkeit 30 % und Rendite 70 %): bisher A, neu Z2 (vorher Platz 2); "
                      "A: Rendite +45.10 % → +44.20 %, R² 0.91 → 0.905; Z2: Rendite +44.90 % → +44.90 %, R² 0.93 → 0.93; "
                      "kleinste Auslösermenge 1 Aktie – nachweislich: jede kleinere Teilmenge der 57 ersetzten Aktien geprüft, keine ergibt diesen Platz 1 (57 Auswertungen); "
                      "auslösend A: 2026-10-16 +0.360 % (Nasdaq-Historie = NOCP); allein ausreichend: A; "
                      "Gegenprobe A mit der unabhängigen Rechnung: allein → Platz 1 Z2 (wie mit allen); alle übrigen ersetzten Kurse ohne A → Platz 1 A (bisheriger "
                      "Spitzenreiter: ohne diese Aktie kein Wechsel); jede der 57 ersetzten Aktien einzeln auch mit der unabhängigen Rechnung: allein ausreichend A – wie die Suche", text)
        # die Suche nach Größe reicht nicht für alle Mengen: Ergebnis und Grenze ausdrücklich, nicht „kleinste“
        self.assertIn("(b) offizieller Schlusskurs 2/3 – 45 Tage, Gruppe B, Gewichtung 0/100 (nur Kursrendite): bisher A, neu Z2 (vorher nicht in dieser Rangliste)", text)
        self.assertIn("Auslösermenge mit 3 Aktien – irreduzibel, aber NICHT nachweislich die kleinste: Teilmengen bis 2 Aktien vollständig geprüft, die kleinste hat mindestens 3 "
                      "(25000 Auswertungen über 300 ersetzte Aktien)", text)
        self.assertIn("mit den übrigen 54 ersetzten Aktien, aber ohne die Auslösermenge: Platz 1 bleibt A (Auslöser nötig)", text)
        self.assertIn("Auslöser nicht untersucht (Zeitbudget der Suche (15 min) erschöpft) – 57 ersetzte Aktien im Zeitraum", text)
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
