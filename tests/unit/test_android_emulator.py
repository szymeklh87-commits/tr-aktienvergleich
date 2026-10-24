"""Urteil zur Systemschrift im Android-Emulator (ab 1.18.1, ``tests/live/android_emulator.py``) – ohne Emulator.

Anlass: Im Emulator (Chrome 124) wirkte die Systemschrift 130 % nicht auf die App, auch nicht nach einem Neustart von Chrome.
Ob das an Chrome liegt oder an der App (``text-size-adjust: 100%``), entscheidet eine Kontrollseite ohne und mit der Angabe."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

LIVE = Path(__file__).resolve().parents[1] / "live"
SPEC = importlib.util.spec_from_file_location("android_emulator", LIVE / "android_emulator.py")
emulator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(emulator)

NORMAL = {"breite": 384, "schrift_px": 16.0, "textzeile_px": 57.5}
SAME = {"breite": 384, "schrift_px": 16.0, "textzeile_px": 58.2}
SMALL = {"schrift": 16.0, "zeile": 18.0}
BIG = {"schrift": 20.8, "zeile": 23.0}


def control(plain: dict, adjusted: dict) -> dict:
    return {"ohne_text_size_adjust": plain, "mit_text_size_adjust": adjusted}


class FontScaleVerdict(unittest.TestCase):
    def test_effect_on_the_app_is_checked_directly(self):
        bigger_font = dict(SAME, schrift_px=20.8)
        self.assertEqual(emulator.font_scale_verdict(NORMAL, bigger_font, None, None)[0], "wirkt")
        page_zoom = dict(SAME, breite=296)
        self.assertEqual(emulator.font_scale_verdict(NORMAL, page_zoom, None, None)[0], "wirkt", "als Seitenzoom: weniger CSS-Pixel")

    def test_control_page_scales_but_the_app_does_not_is_an_app_error(self):
        result, text = emulator.font_scale_verdict(NORMAL, SAME, control(SMALL, SMALL), control(BIG, SMALL))
        self.assertEqual(result, "app_blockiert")
        self.assertIn("FEHLER der App", text)
        self.assertIn("mit text-size-adjust 100 % nicht", text)

    def test_nothing_scales_in_this_chrome(self):
        result, text = emulator.font_scale_verdict(NORMAL, SAME, control(SMALL, SMALL), control(SMALL, SMALL))
        self.assertEqual(result, "chrome_ohne_wirkung")
        self.assertIn("Verhalten dieses Chrome, nicht der App", text)
        self.assertIn("nur in der Desktop-Emulation", text)

    def test_without_measurements_nothing_is_claimed(self):
        result, text = emulator.font_scale_verdict(NORMAL, SAME, None, None)
        self.assertEqual(result, "ohne_kontrolle")
        self.assertIn("nicht geprüft", text)

    def test_control_page_without_and_with_text_size_adjust(self):
        self.assertNotIn("text-size-adjust", emulator.control_html(False))
        self.assertIn("text-size-adjust:100%", emulator.control_html(True))
        self.assertIn("width=device-width", emulator.control_html(True))


if __name__ == "__main__":
    unittest.main()
