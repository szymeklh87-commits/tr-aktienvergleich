"""Android-Emulator mit echten Daten (ab 1.18, ``tests/live/android_echte_daten.py``): Auswahl des Tabs nach dem Neustart
und Urteil über den Neustart ohne Netz. Ohne Emulator – der echte Lauf ist der Job „android“ im Workflow „App mit echten
Daten prüfen“."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

LIVE = Path(__file__).resolve().parents[1] / "live"
sys.path.insert(0, str(LIVE))
SPEC = importlib.util.spec_from_file_location("android_echte_daten", LIVE / "android_echte_daten.py")
echt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(echt)

SITE = echt.SITE
GOOD = {
    "zustand": {
        "sperrbildschirm": False, "kursstand": True, "ladeanzeige": False, "hinweise": ["Offline – gespeicherter Stand"],
        "online": False, "service_worker": True, "seite": "#/", "geladen": "complete",
    },
    "rangliste_zeilen": 10,
}


def changed(**fields) -> dict:
    off = {"zustand": dict(GOOD["zustand"]), "rangliste_zeilen": GOOD["rangliste_zeilen"]}
    for name, value in fields.items():
        if name in off["zustand"]:
            off["zustand"][name] = value
        else:
            off[name] = value
    return off


class TabLabel(unittest.TestCase):
    def test_only_the_page_of_the_app_and_the_marker(self):
        self.assertEqual(echt.tab_label(SITE + "?offline=ab12cd34#/", "offline=ab12cd34"), "#/ (dieser Aufruf)")
        self.assertEqual(echt.tab_label(SITE + "?pruefung=0f0f0f0f#/hilfe", "offline=ab12cd34"), "#/hilfe")
        self.assertEqual(echt.tab_label(SITE), "#/")
        self.assertEqual(echt.tab_label("chrome-native://newtab/"), "andere Adresse")
        self.assertEqual(echt.tab_label("https://example.org/#/x"), "andere Adresse")


class OfflineVerdict(unittest.TestCase):
    def test_passes_only_with_every_requirement(self):
        self.assertEqual(echt.offline_verdict(GOOD), (True, []))

    def test_each_missing_requirement_is_named(self):
        cases = {
            "Seite nicht vom Service Worker gesteuert": changed(service_worker=False),
            "Browser meldete keine fehlende Verbindung": changed(online=True),
            "fragte erneut nach der Passphrase": changed(sperrbildschirm=True),
            "Startseite mit Kursstand nicht sichtbar": changed(kursstand=False),
            "kein Hinweis „Offline – gespeicherter Stand“": changed(hinweise=["Keine Internetverbindung"]),
            "Rangliste aus dem Speicher ohne Zeilen": changed(rangliste_zeilen=0),
        }
        for reason, off in cases.items():
            with self.subTest(reason):
                ok, reasons = echt.offline_verdict(off)
                self.assertFalse(ok)
                self.assertIn(reason, reasons)

    def test_a_timeout_without_state_fails_with_all_reasons(self):
        ok, reasons = echt.offline_verdict({"fehler": "TimeoutError: Locator.wait_for: Timeout 90000ms exceeded."})
        self.assertFalse(ok)
        self.assertEqual(reasons[0], "TimeoutError: Locator.wait_for: Timeout 90000ms exceeded.")
        self.assertIn("Rangliste aus dem Speicher ohne Zeilen", reasons)


if __name__ == "__main__":
    unittest.main()
