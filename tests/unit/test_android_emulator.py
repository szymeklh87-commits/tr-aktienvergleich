"""Urteil zur Systemschrift im Android-Emulator (ab 1.18.1, ``tests/live/android_emulator.py``) – ohne Emulator.

Anlass: Im Emulator (Chrome 124) wirkte die Systemschrift 130 % nicht auf die App, auch nicht nach einem Neustart von Chrome.
Eine Kontrollseite mit langem Absatz wurde größer (16 → 20,8 px), mit und ohne ``text-size-adjust: 100%`` (Lauf vom
24.10.2026, 22:11 Uhr). Ob die App das verhindert oder dieses Chrome nur längere Textblöcke vergrößert, entscheiden ein
langer Absatz mitten in der App und eine Kontrollseite mit kurzen Texten in Karten."""

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
SMALL = {"schrift": 16.0, "zeile": 18.8}
BIG = {"schrift": 20.8, "zeile": 24.2}


def measured(long_plain: dict, long_adjusted: dict, short: dict, inside: dict) -> dict:
    return {"ohne_text_size_adjust": long_plain, "mit_text_size_adjust": long_adjusted, "kurze_texte": short, "langer_absatz_in_der_app": inside}


BEFORE = measured(SMALL, SMALL, SMALL, SMALL)


class FontScaleVerdict(unittest.TestCase):
    def test_effect_on_the_app_is_checked_directly(self):
        bigger_font = dict(SAME, schrift_px=20.8)
        self.assertEqual(emulator.font_scale_verdict(NORMAL, bigger_font, None, None)[0], "wirkt")
        page_zoom = dict(SAME, breite=296)
        self.assertEqual(emulator.font_scale_verdict(NORMAL, page_zoom, None, None)[0], "wirkt", "als Seitenzoom: weniger CSS-Pixel")

    def test_long_paragraph_grows_on_the_control_page_but_not_in_the_app_is_an_app_error(self):
        result, text = emulator.font_scale_verdict(NORMAL, SAME, BEFORE, measured(BIG, BIG, SMALL, SMALL))
        self.assertEqual(result, "app_blockiert")
        self.assertIn("FEHLER der App", text)

    def test_only_long_text_blocks_grow_in_this_chrome(self):
        """Wie im Lauf vom 24.10.2026: langer Absatz wächst überall, kurze Texte nirgends – kein Fehler der App."""
        result, text = emulator.font_scale_verdict(NORMAL, SAME, BEFORE, measured(BIG, BIG, SMALL, BIG))
        self.assertEqual(result, "nur_lange_texte")
        self.assertIn("die App verhindert nichts, folgt der Systemschrift hier aber nicht", text)
        self.assertIn("kurze Texte in Karten: Schrift 16.0 → 16.0 px", text)

    def test_short_texts_grow_on_the_control_page_but_not_in_the_app_is_an_app_error(self):
        result, text = emulator.font_scale_verdict(NORMAL, SAME, BEFORE, measured(BIG, BIG, BIG, BIG))
        self.assertEqual(result, "app_blockiert")
        self.assertIn("nicht aber auf die Texte der App", text)

    def test_opt_in_is_not_testable_in_an_older_chrome(self):
        """Ab 1.18.2 setzt die App <meta name="text-scale" content="scale">; Chrome 124 (Emulator) kennt das noch nicht – die
        Wirkung ist dort nicht prüfbar (kein Fehler der App, aber auch nicht bestanden). Ab Chrome 146 wäre es ein Fehler."""
        after = measured(BIG, BIG, BIG, BIG)
        result, text = emulator.font_scale_verdict(NORMAL, SAME, BEFORE, after, opt_in=True, chrome=124)
        self.assertEqual(result, "nicht_pruefbar")
        self.assertIn("erst ab Version 146", text)
        self.assertIn("hier Chrome 124: nicht prüfbar", text)
        self.assertEqual(emulator.font_scale_verdict(NORMAL, SAME, BEFORE, after, opt_in=True, chrome=146)[0], "app_blockiert")
        self.assertEqual(emulator.font_scale_verdict(NORMAL, SAME, BEFORE, after, opt_in=False, chrome=124)[0], "app_blockiert")
        self.assertEqual(emulator.font_scale_verdict(NORMAL, dict(SAME, schrift_px=20.8), BEFORE, after, opt_in=True, chrome=124)[0], "wirkt")

    def test_unclear_without_the_measurement_in_the_app(self):
        after = measured(BIG, BIG, SMALL, None)
        before = dict(BEFORE, langer_absatz_in_der_app=None)
        self.assertEqual(emulator.font_scale_verdict(NORMAL, SAME, before, after)[0], "unklar")

    def test_nothing_scales_in_this_chrome(self):
        result, text = emulator.font_scale_verdict(NORMAL, SAME, BEFORE, BEFORE)
        self.assertEqual(result, "chrome_ohne_wirkung")
        self.assertIn("Verhalten dieses Chrome, nicht der App", text)
        self.assertIn("nur in der Desktop-Emulation", text)

    def test_without_measurements_nothing_is_claimed(self):
        result, text = emulator.font_scale_verdict(NORMAL, SAME, None, None)
        self.assertEqual(result, "ohne_kontrolle")
        self.assertIn("nicht geprüft", text)

    def test_control_pages(self):
        self.assertNotIn("text-size-adjust", emulator.control_html(False))
        self.assertIn("text-size-adjust:100%", emulator.control_html(True))
        self.assertIn("width=device-width", emulator.control_html(True))
        short = emulator.control_html(False, short=True)
        self.assertEqual(short.count("class='karte'"), 20)
        self.assertNotIn(emulator.CONTROL_TEXT, short)


if __name__ == "__main__":
    unittest.main()
