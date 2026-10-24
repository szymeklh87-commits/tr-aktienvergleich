"""Live-Prüfung der App in weiteren Browsern (ab 1.18.1): Format des S25+ je Browser und Kennzeichnung im Ergebnis.
Ohne Browser und ohne Passphrase – der echte Lauf ist der Job „browser“ im Workflow „App mit echten Daten prüfen“."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

LIVE = Path(__file__).resolve().parents[1] / "live"
sys.path.insert(0, str(LIVE))

import app_bericht_hinweis  # noqa: E402
import test_app_live  # noqa: E402


class DeviceOptions(unittest.TestCase):
    def test_s25_format_in_every_browser_and_no_mobile_mode_in_firefox(self):
        chromium = test_app_live.device_options("chromium")
        self.assertEqual(chromium, test_app_live.S25)
        self.assertTrue(test_app_live.device_options("webkit")["is_mobile"])
        firefox = test_app_live.device_options("firefox")
        self.assertNotIn("is_mobile", firefox)
        self.assertEqual((firefox["viewport"], firefox["device_scale_factor"], firefox["has_touch"]), ({"width": 384, "height": 832}, 2.8125, True))
        self.assertIn("is_mobile", test_app_live.S25, "die Vorlage selbst bleibt unverändert")
        with self.assertRaises(ValueError):
            test_app_live.device_options("edge")


class ReportTitle(unittest.TestCase):
    def report(self, browser: str | None) -> dict:
        out = {"adresse": "https://beispiel/", "ansichten": {"Start": {"route": "/", "elemente": 1, "sekunden": 0.1}}, "konsolenfehler": [], "fehler": [], "fehlgeschlagene_abrufe": []}
        if browser:
            out["browser"] = browser
        return out

    def test_other_browsers_are_named_in_title_and_summary(self):
        (first,) = app_bericht_hinweis.lines(self.report("firefox 142.0"))
        self.assertTrue(first.startswith("::notice title=App mit echten Daten (Firefox)%3A alles in Ordnung::"))
        self.assertIn("Browser: firefox 142.0 im Format des S25+ (Playwright; kein Gerät)", first)

    def test_chromium_title_stays_as_before(self):
        (first,) = app_bericht_hinweis.lines(self.report("chromium 141.0"))
        self.assertTrue(first.startswith("::notice title=App mit echten Daten%3A alles in Ordnung::"))
        (old,) = app_bericht_hinweis.lines(self.report(None))
        self.assertTrue(old.startswith("::notice title=App mit echten Daten%3A alles in Ordnung::"))
        self.assertNotIn("Browser:", old)


if __name__ == "__main__":
    unittest.main()
