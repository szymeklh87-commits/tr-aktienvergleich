"""Eingabe aus der App für einen auf GitHub gestarteten Lauf (ab 1.22, ``traktien.util.eingabe``)."""

from __future__ import annotations

import base64
import os
import unittest

from traktien.util.eingabe import EingabeFehler, KENNUNG_RE, eingabe_zeile, split_eingabe

KENNUNG = "kt3x9a0b-0123456789abcdef"
TEXT = base64.b64encode(os.urandom(120)).decode("ascii")


class EingabeTests(unittest.TestCase):
    def test_line_from_the_app_is_split_into_id_and_ciphertext(self):
        self.assertTrue(KENNUNG_RE.match(KENNUNG))
        self.assertEqual(split_eingabe(eingabe_zeile(KENNUNG, TEXT)), (KENNUNG, TEXT))

    def test_spaces_and_line_breaks_from_pasting_on_a_phone_are_removed(self):
        line = eingabe_zeile(KENNUNG, TEXT)
        pasted = "  " + line[:10] + "\n" + line[10:50] + " \r\n " + line[50:] + "\n"
        self.assertEqual(split_eingabe(pasted), (KENNUNG, TEXT))

    def test_broken_or_foreign_lines_are_rejected_with_a_code(self):
        line = eingabe_zeile(KENNUNG, TEXT)
        cases = {
            "": "eingabe_leer",
            "   \n": "eingabe_leer",
            TEXT: "kennung_ungueltig",  # nur der verschlüsselte Teil
            "kX.abcd": "kennung_ungueltig",
            f"{KENNUNG}.": "eingabe_unvollstaendig",
            line[:-3]: "eingabe_unvollstaendig",  # abgeschnitten
            f"{KENNUNG}.ab$cd==": "eingabe_unvollstaendig",
            f"{KENNUNG}.{TEXT}; rm -rf /": "eingabe_unvollstaendig",
            "github_pat_" + "A" * 40: "kennung_ungueltig",
        }
        for text, code in cases.items():
            with self.subTest(text=text[:20]):
                with self.assertRaises(EingabeFehler) as ctx:
                    split_eingabe(text)
                self.assertEqual(ctx.exception.code, code)
                self.assertNotIn(TEXT[:16], ctx.exception.text, "nie Inhalt in der Meldung")

    def test_length_limit_of_github_inputs(self):
        with self.assertRaises(EingabeFehler) as ctx:
            split_eingabe(eingabe_zeile(KENNUNG, "A" * 70_000))
        self.assertEqual(ctx.exception.code, "eingabe_zu_lang")
        with self.assertRaises(EingabeFehler):
            eingabe_zeile("falsch", TEXT)


if __name__ == "__main__":
    unittest.main()
