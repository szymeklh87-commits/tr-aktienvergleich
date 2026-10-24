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
