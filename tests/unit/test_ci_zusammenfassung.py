"""Testergebnis als GitHub-Hinweise (``tests/ci_zusammenfassung.py``): Ergebnis je Test (ab 1.18).

Die Protokolle der Live-Prüfungen lassen sich aus dieser Umgebung nicht herunterladen; deshalb steht das Ergebnis jedes
Tests als Hinweis in der Laufübersicht. Ein übersprungener Test darf dabei nie als bestanden erscheinen.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests import ci_zusammenfassung as summary

# Ausgabe von ``python -m unittest -v``: Tests ohne Beschreibung in einer Zeile, mit Beschreibung in zwei Zeilen
OUTPUT = """test_1_open_and_unlock (live.test_app_live.LiveAppTest.test_1_open_and_unlock) ... ok
test_2b_report_1_30 (live.test_app_live.LiveAppTest.test_2b_report_1_30)
Ab 1.8.1: Bericht 1–30 – vier Tabellen, Matrix mit 30 Zeilen, Häufigkeit; nur Zählungen im Bericht. ... ok
test_2d_rotation_in_official_stand (live.test_app_live.LiveAppTest.test_2d_rotation_in_official_stand)
Ab 1.9.2: Im Zwischenstand führt der Knopf zum Stand mit Schlusskursen. ... skipped 'kein Zwischenstand aktiv – geprüft in test_2'
test_eodhd_history (live.test_sources_live.SourcesLiveTest.test_eodhd_history) ... skipped 'EODHD_API_KEY nicht gesetzt'
test_5_no_console_errors (live.test_app_live.LiveAppTest.test_5_no_console_errors) ... FAIL
test_6_install_and_first_start (live.test_app_live.LiveAppTest.test_6_install_and_first_start)
Installation wie auf dem Handy – soweit ohne Gerät möglich. ... ERROR

======================================================================
FAIL: test_5_no_console_errors (live.test_app_live.LiveAppTest.test_5_no_console_errors)
----------------------------------------------------------------------
AssertionError: 2 Konsolenfehler

----------------------------------------------------------------------
Ran 6 tests in 12.5s

FAILED (failures=1, errors=1, skipped=2)
"""


class PerTestResultTests(unittest.TestCase):
    def test_every_test_with_its_own_result(self):
        self.assertEqual(
            summary.results(OUTPUT),
            [
                ("LiveAppTest.test_1_open_and_unlock", "bestanden"),
                ("LiveAppTest.test_2b_report_1_30", "bestanden"),
                ("LiveAppTest.test_2d_rotation_in_official_stand", "übersprungen: kein Zwischenstand aktiv – geprüft in test_2"),
                ("SourcesLiveTest.test_eodhd_history", "übersprungen: EODHD_API_KEY nicht gesetzt"),
                ("LiveAppTest.test_5_no_console_errors", "fehlgeschlagen"),
                ("LiveAppTest.test_6_install_and_first_start", "Fehler"),
            ],
        )

    def test_notice_counts_skipped_tests_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app-ausgabe.txt"
            path.write_text(OUTPUT, encoding="utf-8")
            lines = summary.report(path, einzeln=True)
        each = next(line for line in lines if "je Test" in line)
        self.assertIn("6 Tests: bestanden 2, übersprungen 2, nicht bestanden 2", each)
        self.assertIn("LiveAppTest.test_2d_rotation_in_official_stand – übersprungen: kein Zwischenstand aktiv", each)
        self.assertNotIn("test_eodhd_history – bestanden", each)
        self.assertTrue(any(line.startswith("::error title=FAIL%3A test_5_no_console_errors") for line in lines))
        # ohne --einzeln bleibt die bisherige Zusammenfassung
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test-ausgabe.txt"
            path.write_text(OUTPUT, encoding="utf-8")
            self.assertFalse(any("je Test" in line for line in summary.report(path)))

    def test_head_glued_to_a_long_report_is_found(self):
        # Lauf „Datenquellen prüfen“ vom 24.10.2026: Der Bericht aus tearDownModule (gepufferte Ausgabe) endete ohne
        # Zeilenumbruch, der nächste Test stand dahinter – er fehlte in der Liste (14 statt 15 Tests)
        output = (
            "test_yahoo_quote_matches_daily_close (tests.live.test_sources_live.SourcesLiveTest.test_yahoo_quote_matches_daily_close)\n"
            "Ab 1.9: Kursmeldung gegen Tageskerze. ... ok\n"
            '{\n  "yahoo": {"status": 200}\n'
            "}test_close_times_in_utc (tests.live.test_calendars_live.ExchangeCalendarsLiveTest.test_close_times_in_utc) ... ok\n"
            "xtest_cutoff (tests.live.test_calendars_live.ExchangeCalendarsLiveTest.test_cutoff) ... skipped 'Grund'\n"
            "\n" + "-" * 70 + "\nRan 3 tests in 1.0s\n\nOK (skipped=1)\n"
        )
        self.assertEqual(
            summary.results(output),
            [
                ("SourcesLiveTest.test_yahoo_quote_matches_daily_close", "bestanden"),
                ("ExchangeCalendarsLiveTest.test_close_times_in_utc", "bestanden"),
                ("ExchangeCalendarsLiveTest.test_cutoff", "übersprungen: Grund"),
            ],
        )

    def test_real_unittest_run_with_buffered_output(self):
        """Echter Lauf wie im Workflow (``2>&1 | tee``, ohne PYTHONUNBUFFERED): langer Bericht am Ende eines Moduls."""
        import os
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "modul_a.py").write_text(
                "import json, unittest\n"
                "def tearDownModule():\n"
                "    print(json.dumps({f'k{i}': 'x' * 50 for i in range(400)}, indent=2))\n"
                "class A(unittest.TestCase):\n"
                "    def test_a1(self):\n"
                "        '''Mit Beschreibung.'''\n",
                encoding="utf-8",
            )
            Path(tmp, "modul_b.py").write_text(
                "import unittest\n"
                "class B(unittest.TestCase):\n"
                "    def test_b1(self): pass\n"
                "    @unittest.skip('ohne Schlüssel')\n"
                "    def test_b2(self): pass\n",
                encoding="utf-8",
            )
            env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
            run = subprocess.run(
                [sys.executable, "-m", "unittest", "modul_a", "modul_b", "-v"],
                cwd=tmp, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60, check=False,
            )
            path = Path(tmp) / "quellen-ausgabe.txt"
            path.write_text(run.stdout, encoding="utf-8")
            lines = summary.report(path, einzeln=True)
        self.assertIn("}test_b1 (modul_b.B.test_b1)", run.stdout, "Ausgabe wie im Workflow verklebt")
        self.assertEqual(
            summary.results(run.stdout),
            [("A.test_a1", "bestanden"), ("B.test_b1", "bestanden"), ("B.test_b2", "übersprungen: ohne Schlüssel")],
        )
        each = next(line for line in lines if "je Test" in line)
        self.assertIn("3 Tests: bestanden 2, übersprungen 1%0A", each)
        self.assertFalse(any(line.startswith("::warning") for line in lines))

    def test_unassigned_tests_are_named_and_never_counted_as_passed(self):
        # „Ran 3 tests“, aber nur zwei Ergebnisse lesbar (Kopfzeile zerstört): Warnung statt stiller Lücke
        output = (
            "test_a (paket.modul.A.test_a) ... ok\n"
            "kaputte Zeile ohne Testnamen ... ok\n"
            "test_c (paket.modul.A.test_c) ... skipped 'Grund'\n"
            "\n" + "-" * 70 + "\nRan 3 tests in 0.1s\n\nOK (skipped=1)\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app-ausgabe.txt"
            path.write_text(output, encoding="utf-8")
            lines = summary.report(path, einzeln=True)
        each = next(line for line in lines if "je Test" in line)
        self.assertIn("::3 Tests: bestanden 1, übersprungen 1, ohne Einzelergebnis 1%0A", each)
        warning = next(line for line in lines if line.startswith("::warning"))
        self.assertIn("Ergebnis je Test unvollständig", warning)
        self.assertIn("unittest meldet 3 Tests, einzeln zugeordnet 2", warning)

    def test_command_line_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quellen-ausgabe.txt"
            path.write_text(OUTPUT, encoding="utf-8")
            import contextlib
            import io

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                summary.main(["--einzeln", str(path)])
        self.assertIn("title=quellen-ausgabe%3A je Test::6 Tests", out.getvalue())


if __name__ == "__main__":
    unittest.main()
