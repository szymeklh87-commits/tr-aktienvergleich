"""Kurse unabhängig gegenprüfen (ab 1.18, ``tests/live/kurse_gegenpruefen.py``): Auswertung der Nasdaq-Antwort und der
Vergleich mit dem Stand. SYNTHETISCHE Kurse – der echte Abruf läuft im Workflow „App mit echten Daten prüfen“."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import unittest
from pathlib import Path

LIVE = Path(__file__).resolve().parents[1] / "live"
sys.path.insert(0, str(LIVE))
SPEC = importlib.util.spec_from_file_location("kurse_gegenpruefen", LIVE / "kurse_gegenpruefen.py")
gegen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gegen)


def day(text: str) -> int:
    return (dt.date.fromisoformat(text) - dt.date(1970, 1, 1)).days


class NasdaqAnswer(unittest.TestCase):
    def test_rows_become_closes_per_day(self):
        payload = {"data": {"tradesTable": {"rows": [
            {"date": "10/23/2026", "close": "$1,234.56", "volume": "1,000"},
            {"date": "10/22/2026", "close": "$0.5123", "volume": "5"},
            {"date": "10/21/2026", "close": "N/A"},
        ]}}}
        self.assertEqual(gegen.parse_nasdaq(payload), {day("2026-10-23"): 1234.56, day("2026-10-22"): 0.5123})
        self.assertEqual(gegen.parse_nasdaq({"data": None}), {})
        self.assertEqual(gegen.day_of("01/02/2026"), day("2026-01-02"))


class YahooAnswer(unittest.TestCase):
    def test_days_from_the_timestamp_in_exchange_time_and_only_bars_with_a_close(self):
        # Tageskerzen beginnen um 9:30 Uhr New York = 13:30 UTC (Sommerzeit, gmtoffset −4 h)
        open_utc = lambda text: int(dt.datetime.fromisoformat(text + "T13:30:00+00:00").timestamp())  # noqa: E731
        payload = {"chart": {"result": [{
            "meta": {"gmtoffset": -14400, "regularMarketPrice": 99.0},
            "timestamp": [open_utc("2026-10-21"), open_utc("2026-10-22"), open_utc("2026-10-23")],
            "indicators": {"quote": [{"close": [262.2399902, None, 0.5123]}]},
        }], "error": None}}
        self.assertEqual(gegen.parse_yahoo(payload), {day("2026-10-21"): 262.2399902, day("2026-10-23"): 0.5123},
                         "ohne Schlusskurs kein Tag – auch nicht aus regularMarketPrice")
        self.assertEqual(gegen.parse_yahoo({"chart": {"result": None, "error": {"code": "Not Found"}}}), {})
        self.assertEqual(gegen.parse_yahoo({}), {})

    def test_same_as_yahoo_allows_only_the_float_digits_of_yahoo(self):
        self.assertTrue(gegen.same_as_yahoo(262.2399902, 262.2399902))
        self.assertTrue(gegen.same_as_yahoo(262.24, 262.2399902))
        self.assertFalse(gegen.same_as_yahoo(262.25, 262.2399902))
        self.assertFalse(gegen.same_as_yahoo(0.5124, 0.5123), "unter 1 $ zählt schon 1/100 Cent")


class Classification(unittest.TestCase):
    def test_same_close_within_the_rounding_of_nasdaq(self):
        self.assertEqual(gegen.classify(262.2399902, 262.24, []), "gleich")
        self.assertEqual(gegen.classify(0.51234, 0.5123, []), "gleich")
        self.assertEqual(gegen.classify(262.26, 262.24, []), "klein")

    def test_factor_neighbour_small_big(self):
        self.assertEqual(gegen.classify(50.0, 100.0, []), "faktor", "Split 2:1 nach dem Abruf")
        self.assertEqual(gegen.classify(10.0, 1.0, []), "faktor", "Zusammenlegung 1:10")
        self.assertEqual(gegen.classify(101.5, 100.0, [101.5, 99.0]), "nachbartag")
        self.assertEqual(gegen.classify(100.4, 100.0, []), "klein")
        self.assertEqual(gegen.classify(107.0, 100.0, []), "gross")

    def test_return_tolerance_follows_the_rounding_of_both_prices(self):
        self.assertTrue(gegen.return_matches(0.1, 10.00, 11.00))
        self.assertTrue(gegen.return_matches(11.004 / 10.0 - 1, 10.00, 11.00), "Abweichung kleiner als ein halber Cent")
        self.assertFalse(gegen.return_matches(11.02 / 10.0 - 1, 10.00, 11.00))


class StockComparison(unittest.TestCase):
    def test_days_missing_days_and_returns(self):
        cutoff = day("2026-10-23")
        d = [day("2026-10-19"), day("2026-10-20"), day("2026-10-21"), day("2026-10-23")]
        series = {
            "d": d + [day("2026-10-22")],
            "c": [10.0, 10.5, 11.0, 12.0, None],  # 22.10. als Leerzeile (fehlender Kurstag)
            "gaps": [day("2026-10-22")],
            "window_start": [day("2026-10-21"), day("2026-10-20"), day("2026-10-19")],
        }
        fresh = {day("2026-10-19"): 10.0, day("2026-10-20"): 10.5, day("2026-10-21"): 11.0, day("2026-10-22"): 11.4, day("2026-10-23"): 12.0}
        returns = {1: 12.0 / 11.0 - 1, 2: 12.0 / 10.5 - 1, 3: 12.0 / 10.0 - 1 + 0.01}
        counts = gegen.compare_stock(series, fresh, returns, cutoff)
        self.assertEqual(counts["tage_verglichen"], 4)
        self.assertEqual(counts["tag_gleich"], 4)
        self.assertEqual((counts["nur_bei_nasdaq"], counts["nur_bei_nasdaq_als_fehlender_tag_gezaehlt"]), (1, 1))
        self.assertEqual((counts["renditen_verglichen"], counts["rendite_gleich"], counts["rendite_abweichend"]), (3, 2, 1))
        # Stichtagskurs fehlte im Stand (eigener Endtag 21.10.), Nasdaq hat ihn
        short = {"d": d[:3], "c": [10.0, 10.5, 11.0], "gaps": [], "window_start": []}
        counts = gegen.compare_stock(short, fresh, {}, cutoff)
        self.assertEqual(counts["nur_bei_nasdaq_nach_letztem_kurs_des_stands"], 2)

    def test_pattern_of_a_constant_shift_before_an_event(self):
        """Muster ohne Kurse: Stand/Nasdaq vor einem Tag konstant 5 % höher, danach gleich – typisch für eine Anpassung, die
        nur ein Anbieter vorgenommen hat (z. B. nach einer Kapitalmaßnahme)."""
        cutoff = day("2026-10-23")
        days = [day("2026-10-19"), day("2026-10-20"), day("2026-10-21"), day("2026-10-22"), day("2026-10-23")]
        fresh = dict(zip(days, [20.0, 20.2, 20.4, 20.6, 20.8]))
        own = [20.0 * 1.05, 20.2 * 1.05, 20.4, 20.6, 20.8]
        series = {"d": days, "c": own, "gaps": [], "window_start": [days[3], days[2], days[1], days[0]]}
        returns = {h: 20.8 / own[4 - h] - 1 for h in (1, 2, 3, 4)}
        diag: dict = {}
        counts = gegen.compare_stock(series, fresh, returns, cutoff, diag)
        self.assertEqual((counts["tag_gross"], counts["rendite_abweichend"]), (2, 2))
        self.assertEqual(diag["verhaeltnis"], [1.05, 1.05, 1.05])
        self.assertTrue(diag["konstant"])
        self.assertEqual((diag["erste_abweichung_tage_vor_stichtag"], diag["letzte_abweichung_tage_vor_stichtag"], diag["danach_gleich"]), (4, 3, 3))
        self.assertEqual(diag["kursbereich"], "10–100 $")
        self.assertAlmostEqual(diag["groesste_renditeabweichung_pp"], round(100 * (20.8 / 20.0 - 20.8 / 21.0), 2), places=2)

    def test_cause_of_each_deviation_from_the_counter_check_at_yahoo(self):
        """Ursachen (Modulbeschreibung, Punkt 4): Kurs = heutiger Yahoo-Kurs → wie Yahoo; Tag in ``quote_days`` und Yahoo
        inzwischen anders → vorläufig aus der Kursmeldung; Yahoo anders ohne Markierung → unerklärt; Yahoo ohne Kurs."""
        cutoff = day("2026-10-23")
        days = [day("2026-10-19"), day("2026-10-20"), day("2026-10-21"), day("2026-10-22"), day("2026-10-23")]
        nasdaq = dict(zip(days, [0.50, 0.51, 0.52, 0.53, 0.54]))
        own = [0.51, 0.51, 0.53, 0.55, 0.56]  # 19., 21., 22. und 23. weichen ab
        yahoo = {days[0]: 0.51, days[1]: 0.51, days[2]: 0.5299, days[4]: 0.55}  # 22. fehlt bei Yahoo
        series = {"d": days, "c": own, "gaps": [], "window_start": [days[3], days[2], days[1], days[0]], "quote_days": [days[4]]}
        returns = {h: own[4] / own[4 - h] - 1 for h in (1, 2, 3, 4)}
        diag: dict = {}
        counts = gegen.compare_stock(series, nasdaq, returns, cutoff, diag, yahoo)
        self.assertEqual(counts["abweichung_wie_yahoo"], 1)  # 19.
        self.assertEqual(counts["abweichung_unerklaert"], 1)  # 21.: Yahoo 0,5299, Stand 0,53
        self.assertEqual(counts["abweichung_ohne_yahoo_kurs"], 1)  # 22.
        self.assertEqual(counts["abweichung_kursmeldung"], 1)  # 23.: vorläufig, Yahoo heute 0,55
        self.assertEqual(diag["ursachen"], {"wie_yahoo": 1, "unerklaert": 1, "ohne_yahoo_kurs": 1, "kursmeldung": 1})
        # Stand gegen Yahoo über alle Tage: 19. und 20. gleich, 21. und 23. anders (23. davon vorläufig), 22. fehlt
        self.assertEqual((counts["yahoo_tage_verglichen"], counts["yahoo_gleich"], counts["yahoo_abweichend"]), (4, 2, 2))
        self.assertEqual((counts["yahoo_abweichend_kursmeldung"], counts["nicht_bei_yahoo"]), (1, 1))
        # Renditen enden am 23. (vorläufig) – Start 22. ohne Yahoo-Kurs, 21. unerklärt, 20. gleich, 19. wie Yahoo
        self.assertEqual(counts["rendite_abweichend"], 4)
        self.assertEqual(diag["renditen_ursachen"], {"ohne_yahoo_kurs": 1, "unerklaert": 1, "kursmeldung": 2})

    def test_returns_of_yahoo_are_a_provider_difference_only_if_both_ends_are_yahoo(self):
        self.assertEqual(gegen.return_cause({"wie_yahoo"}), "wie_yahoo")
        self.assertEqual(gegen.return_cause({"wie_yahoo", "kursmeldung"}), "kursmeldung")
        self.assertEqual(gegen.return_cause({"kursmeldung", "unerklaert"}), "unerklaert")
        self.assertEqual(gegen.return_cause({"wie_yahoo", "ohne_yahoo_kurs"}), "ohne_yahoo_kurs")

    def test_without_yahoo_every_deviation_stays_unexplained(self):
        cutoff = day("2026-10-23")
        days = [day("2026-10-22"), day("2026-10-23")]
        series = {"d": days, "c": [10.0, 10.2], "gaps": [], "window_start": [days[0]]}
        counts = gegen.compare_stock(series, {days[0]: 10.0, days[1]: 10.0}, {1: 0.02}, cutoff, {}, None)
        self.assertEqual((counts["abweichung_ohne_yahoo_kurs"], counts["rendite_abweichend_ohne_yahoo_kurs"]), (1, 1))
        self.assertNotIn("yahoo_tage_verglichen", counts)


def report_with(**zaehler) -> dict:
    base = {"tage_verglichen": 20000, "tag_gleich": 20000, "renditen_verglichen": 26000, "rendite_gleich": 26000,
            "yahoo_tage_verglichen": 20000, "yahoo_gleich": 20000}
    base.update(zaehler)
    return {
        "stand": "2026-10-23_3f7ce5f3", "stichtag": "2026-10-23", "abgerufen_utc": "2026-10-24T18:00:00Z",
        "ausgewaehlt": 300, "davon_aus_den_ersten_10": 150, "abruf": {"ok": 298, "http_404": 2}, "yahoo_abruf": {"ok": 298},
        "zaehler": base, "aktien_mit": {},
    }


class Verdict(unittest.TestCase):
    def test_all_equal_passes(self):
        self.assertEqual(gegen.verdict(report_with()), ("bestanden", []))

    def test_provider_differences_pass_only_with_evidence_for_every_deviation(self):
        report = report_with(tag_gleich=19800, tag_gross=50, tag_klein=150, abweichung_wie_yahoo=190, abweichung_kursmeldung=10,
                             rendite_gleich=25900, rendite_abweichend=100, rendite_abweichend_wie_yahoo=100)
        result, reasons = gegen.verdict(report)
        self.assertEqual(result, "bestanden_mit_anbieterunterschieden")
        self.assertIn("wie Yahoo 190 Kurstage und 100 Renditen", reasons[0])

    def test_a_single_unexplained_deviation_fails(self):
        for name in ("abweichung_unerklaert", "abweichung_ohne_yahoo_kurs", "rendite_abweichend_unerklaert", "rendite_abweichend_ohne_yahoo_kurs"):
            with self.subTest(name):
                result, reasons = gegen.verdict(report_with(tag_klein=1, abweichung_wie_yahoo=0, **{name: 1}))
                self.assertEqual(result, "nicht_bestanden")
                self.assertTrue(any("Abweichungen" in r for r in reasons))

    def test_sources_reachable_only_in_part_fail(self):
        report = report_with()
        report["yahoo_abruf"] = {"ok": 200, "http_429": 98}
        self.assertEqual(gegen.verdict(report)[0], "nicht_bestanden")
        report = report_with()
        report["abruf"] = {"ok": 100, "keine_kurse": 200}
        self.assertEqual(gegen.verdict(report)[0], "nicht_bestanden")


class Annotations(unittest.TestCase):
    def test_notice_names_the_sources_and_contains_only_counts(self):
        (line,) = gegen.annotations(report_with())
        self.assertTrue(line.startswith("::notice title=Kurse unabhängig gegengeprüft (Nasdaq): bestanden::Nachträglich bei Nasdaq abgerufen"))
        self.assertIn("zur Gegenprobe bei Yahoo (Quelle der App)", line)
        self.assertIn("beweist nicht, welche Kurse ein anderes Modell damals hatte", line)
        self.assertIn("20000 verglichen – gleich 20000", line)
        self.assertIn("Urteil: BESTANDEN", line)

    def test_levels_follow_the_verdict(self):
        explained = report_with(tag_gleich=19999, tag_gross=1, abweichung_wie_yahoo=1)
        self.assertTrue(gegen.annotations(explained)[0].startswith("::warning title=Kurse unabhängig gegengeprüft (Nasdaq): bestanden, Anbieter unterscheiden sich::"))
        failed = report_with(tag_gleich=19999, tag_gross=1, abweichung_unerklaert=1)
        first = gegen.annotations(failed)[0]
        self.assertTrue(first.startswith("::error title=Kurse unabhängig gegengeprüft (Nasdaq): NICHT bestanden::"))
        self.assertIn("unerklärt: 1 Kurstage, 0 Renditen", first)

    def test_long_pattern_lists_are_split_and_never_cut(self):
        report = report_with(tag_gleich=19000, tag_klein=1000, abweichung_wie_yahoo=1000)
        pattern = {"unter_den_ersten_10": True, "kursbereich": "unter 1 $", "tage": 69, "abweichend": 66, "gross": 53, "klein": 9, "cent": 49,
                   "ursachen": {"wie_yahoo": 66}, "verhaeltnis": [0.9607, 0.9997, 1.0375], "konstant": False, "erste_abweichung_tage_vor_stichtag": 95,
                   "letzte_abweichung_tage_vor_stichtag": 0, "danach_gleich": 0, "renditen_abweichend": 59, "groesste_renditeabweichung_pp": 4.72,
                   "renditen_ursachen": {"wie_yahoo": 59}}
        report["muster"] = [dict(pattern) for _ in range(20)]
        report["aktien_mit_abweichung"] = 31
        lines = gegen.annotations(report)
        pattern_notes = [line for line in lines if "Muster der Abweichungen" in line]
        self.assertGreater(len(pattern_notes), 1)
        self.assertLessEqual(len(lines), 10, "GitHub zeigt je Schritt höchstens 10 Hinweise einer Art")
        for line in lines:
            self.assertLessEqual(len(line.split("::", 2)[2].replace("%0A", "\n").encode("utf-8")), gegen.MAX_ANNOTATION_BYTES + 10)
        numbers = [int(m) for line in pattern_notes for m in __import__("re").findall(r"Muster (\d+) \(", line)]
        self.assertEqual(numbers, list(range(1, 21)), "jedes Muster genau einmal, in Reihenfolge")
        self.assertIn("(1/", pattern_notes[0])
        self.assertIn("20 von 31 Aktien", pattern_notes[0])

    def test_chunked_keeps_every_line_whole(self):
        lines = [f"Zeile {k} " + "ä" * 400 for k in range(30)]
        parts = gegen.chunked(lines, 2000)
        self.assertEqual([line for part in parts for line in part], lines)
        for part in parts:
            self.assertLessEqual(sum(len(line.encode("utf-8")) + 3 for line in part), 2000)


if __name__ == "__main__":
    unittest.main()
