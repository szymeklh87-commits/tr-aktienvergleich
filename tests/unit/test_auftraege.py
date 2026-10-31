"""Abgelegte Aufträge bleiben byte-gleich mit den Anlagen: Die Prüfsumme jeder Auftragsdatei steht in ihrer Soll-Ist-Datei und
muss zur Datei passen (Gesamtauftrag 31.10.2026, Abschnitt 1; Depot-Optimierer, Ablage). Kein Test schreibt die Aufträge um."""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"

# Auftrag → Datei, in der seine Prüfsumme festgehalten ist
AUFTRAEGE = {
    "13_AktienPilot.md": "13_AktienPilot_Umsetzungsstand.md",
    "17_Gesamtauftrag_Robo.md": "17_Gesamtauftrag_Robo_SollIst.md",
    "18_Depot_Optimierer.md": "18_Depot_Optimierer_SollIst.md",
    "19_Depot_Optimierer_Alle_Informationen.md": "18_Depot_Optimierer_SollIst.md",
}


class AuftragsablageTests(unittest.TestCase):
    def test_every_order_matches_its_recorded_checksum(self):
        for auftrag, beleg in AUFTRAEGE.items():
            with self.subTest(auftrag=auftrag):
                digest = hashlib.sha256((DOCS / auftrag).read_bytes()).hexdigest()
                text = (DOCS / beleg).read_text(encoding="utf-8")
                self.assertIn(f"`{digest}`", text, f"Prüfsumme von {auftrag} nicht in {beleg} – Auftrag verändert?")

    def test_new_orders_are_plain_utf8_with_lf(self):
        for auftrag in ("18_Depot_Optimierer.md", "19_Depot_Optimierer_Alle_Informationen.md"):
            raw = (DOCS / auftrag).read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), auftrag)
            self.assertNotIn(b"\r\n", raw, auftrag)
            raw.decode("utf-8")

    def test_table_row_states_sizes_of_the_stored_orders(self):
        text = (DOCS / "18_Depot_Optimierer_SollIst.md").read_text(encoding="utf-8")
        for auftrag in ("18_Depot_Optimierer.md", "19_Depot_Optimierer_Alle_Informationen.md"):
            raw = (DOCS / auftrag).read_bytes()
            row = next(line for line in text.splitlines() if line.startswith(f"| `docs/{auftrag}`"))
            zahlen = [int(x.replace(".", "")) for x in re.findall(r"\| ([\d.]+) ", row)]
            self.assertEqual(zahlen[:3], [len(raw), len(raw.decode("utf-8")), raw.count(b"\n")], auftrag)


if __name__ == "__main__":
    unittest.main()
