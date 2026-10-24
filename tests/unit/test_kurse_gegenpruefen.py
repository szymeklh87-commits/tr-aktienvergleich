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

    def test_notice_names_the_source_and_contains_only_counts(self):
        report = {
            "stand": "2026-10-23_3f7ce5f3", "stichtag": "2026-10-23", "abgerufen_utc": "2026-10-24T18:00:00Z",
            "ausgewaehlt": 300, "davon_aus_den_ersten_10": 150, "abruf": {"ok": 298, "http_404": 2},
            "zaehler": {"tage_verglichen": 20000, "tag_gleich": 19990, "tag_klein": 10, "renditen_verglichen": 26000, "rendite_gleich": 26000},
            "aktien_mit": {"tag_klein": 3},
        }
        (line,) = gegen.annotations(report)
        self.assertTrue(line.startswith("::notice title=Kurse unabhängig gegengeprüft (Nasdaq)::Nachträglich bei Nasdaq abgerufen"))
        self.assertIn("beweist nicht, welche Kurse ein anderes Modell damals hatte", line)
        self.assertIn("20000 verglichen – gleich 19990", line)
        report["zaehler"]["tag_gross"] = 1
        self.assertTrue(gegen.annotations(report)[0].startswith("::warning"))


if __name__ == "__main__":
    unittest.main()
