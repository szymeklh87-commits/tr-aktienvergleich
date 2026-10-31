"""Strategielabor (Gesamtauftrag vom 31.10.2026, Abschnitte 12, 13, 15) über den Befehl ``spielgeld-labor`` auf dem echten
DEMO-Zustand – SYNTHETISCHE Daten.

Prüft: Der Befehl rechnet alle Varianten über den gemeinsamen Motor, legt das Ergebnis mit Prüfsumme im Zustand ab und baut
einen neuen verschlüsselten Spielgeld-Stand, der das Ergebnis enthält; das öffentliche Protokoll enthält nur Zahlen; die
Depots des Labors werden nicht als Spielgelddepots gespeichert (nur ihre Auswertung); Vorwärtsdepots entstehen erst im
nächsten täglichen Lauf.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.integration.test_spielgeld_pipeline import PASSPHRASE, _cli
from traktien.util import crypto


class LaborPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cls.state, cls.site, cls.app = base / "state", base / "site", base / "app"
        cls.app.mkdir()
        (cls.app / "index.html").write_text("<!doctype html><title>Test</title>", encoding="utf-8")
        _cli("demo", "--fresh", "--state-dir", str(cls.state), "--site", str(cls.site), "--app-dist", str(cls.app), "--passphrase", PASSPHRASE)
        conn = sqlite3.connect(cls.state / "state.sqlite")
        cls.depots_vorher = conn.execute("SELECT COUNT(*) FROM ap_depot").fetchone()[0]
        conn.close()
        cls.step_summary = base / "step-summary.md"
        with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(cls.step_summary)}):
            cls.out = _cli("spielgeld-labor", "--demo", "--passphrase", PASSPHRASE, "--state-dir", str(cls.state), "--tage", "40", "--site", str(cls.site),
                           "--app-dist", str(cls.app))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_public_output_only_numbers(self):
        line = self.out.stdout.strip().splitlines()[-1]
        summary = json.loads(line)
        self.assertEqual(summary["varianten"], 28)
        self.assertEqual(sum(summary["zaehlung"].values()), 28)
        self.assertGreater(summary["depots"], 28 * 3)
        conn = sqlite3.connect(self.state / "state.sqlite")
        forschung = conn.execute("SELECT COUNT(*) FROM ap_depot WHERE art = 'forschung' AND status != 'archiviert' AND id LIKE 'demo-f-%'").fetchone()[0]
        conn.close()
        self.assertGreaterEqual(forschung, 2)
        self.assertEqual(summary["laufende"], forschung, "alle laufenden Vorlagen historisch mitgerechnet")
        self.assertIsNone(re.search(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b", self.out.stdout + self.out.stderr), "keine ISIN im Protokoll")
        self.assertNotIn("lab-", line, "keine Kennung im öffentlichen Protokoll")
        # Zusammenfassung des Workflow-Laufs (öffentlich sichtbar): nur Zählungen und Zeiten
        text = self.step_summary.read_text(encoding="utf-8")
        self.assertRegex(text, rf"^Strategielabor: 28 Varianten und {summary['laufende']} laufende Strategien, \d+ Handelstage, \d+ Aktien; verworfen \d+")
        self.assertIsNone(re.search(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b", text))
        self.assertNotIn("lab-", text)
        self.assertNotIn("Vorlage", text)

    def test_result_in_state_and_encrypted_stand(self):
        conn = sqlite3.connect(self.state / "state.sqlite")
        try:
            rows = conn.execute("SELECT id, modus, version FROM ap_labor").fetchall()
            depots = conn.execute("SELECT COUNT(*) FROM ap_depot").fetchone()[0]
            lab_depots = conn.execute("SELECT COUNT(*) FROM ap_depot WHERE id LIKE '%lab-%' OR id LIKE 'demo-l-%'").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1:], ("DEMO", "labor-1"))
        self.assertEqual(depots, self.depots_vorher, "Labordepots werden nicht gespeichert, nur ausgewertet")
        self.assertEqual(lab_depots, 0, "Vorwärtsdepots erst im nächsten täglichen Lauf")
        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        rel = f"pilot/{status['spielgeld']['id']}/pilot.bin"
        key = crypto.verify_descriptor(json.loads((self.state / "crypto.json").read_text(encoding="utf-8")), PASSPHRASE)
        stand = json.loads(crypto.unpack((self.site / "data" / rel).read_bytes(), key, rel))
        lab = stand["labor"]
        self.assertEqual((lab["schema"], lab["id"], lab["modus"]), ("tr-labor/1", rows[0][0], "DEMO"))
        self.assertEqual([z["art"] for z in lab["zeitraeume"][:3]], ["entwicklung", "validierung", "test"])
        self.assertTrue(lab["walk_forward"]["faltungen"], "mindestens eine Walk-forward-Faltung")
        for v in lab["varianten"]:
            self.assertEqual("test" in v, v["status"] in ("validiert", "vorwaerts"), v["id"])
            self.assertEqual("regel" in v, v["status"] in ("validiert", "vorwaerts"), v["id"])
        self.assertTrue(set(lab["uebernahme"]["vorwaerts"]) <= {v["id"] for v in lab["varianten"] if v["status"] == "vorwaerts"})
        # laufende Strategien: über Entwicklung, Validierung und Test nachgerechnet, nur berichtet (Abschnitte 14, 17)
        self.assertTrue(lab["laufende"])
        for x in lab["laufende"]:
            self.assertEqual(x["quelle"], "vorlage")
            self.assertTrue(x["depot"].startswith("demo-f-"))
            self.assertEqual({"entwicklung", "validierung", "test"} <= set(x), True)
        self.assertTrue(any("laufende Strategien" in h for h in lab["hinweise"]))
        sp = lab["signalpruefung"]
        self.assertEqual(sp["horizonte"], [5, 20])
        self.assertEqual(len(sp["ergebnisse"]), 5 * 2)
        self.assertTrue(any(x["tage"] > 0 for x in sp["ergebnisse"]), "Folgekurse für einen Teil der Tage")
        self.assertIn("keine Gewinnwahrscheinlichkeit", sp["hinweis"])


if __name__ == "__main__":
    unittest.main()
