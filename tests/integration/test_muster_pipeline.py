"""Musterbereiche (Abschnitt 26) in der echten DEMO-Pipeline – SYNTHETISCHE Daten.

Prüft: der tägliche DEMO-Lauf erkennt Vor-Ausbruch, Volumensprung und Seitwärtsbasis aus denselben Tageskerzen wie Rangliste und
Spielgeld-Robo (einmal geladen), legt einen verschlüsselten Stand in die Website und schreibt öffentlich nur Kennung, Zeit und
Schema; das Journal enthält jede Zustandsänderung genau einmal; das Protokoll enthält nur Zahlen.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.integration.test_spielgeld_pipeline import PASSPHRASE, _cli
from traktien.util import crypto


class MusterPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cls.state, cls.site, cls.app = base / "state", base / "site", base / "app"
        cls.app.mkdir()
        (cls.app / "index.html").write_text("<!doctype html><title>Test</title>", encoding="utf-8")
        cls.out = _cli("demo", "--fresh", "--state-dir", str(cls.state), "--site", str(cls.site), "--app-dist", str(cls.app), "--passphrase", PASSPHRASE)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_published_encrypted_with_public_status_only(self):
        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        info = status.get("muster")
        self.assertIsNotNone(info, "status.json nennt den Musterstand")
        self.assertEqual(set(info), {"id", "erstellt_utc", "schema"})
        blob = (self.site / "data" / "muster" / info["id"] / "muster.bin").read_bytes()
        self.assertTrue(blob.startswith(b"TRA1"))
        key = crypto.verify_descriptor(json.loads((self.state / "crypto.json").read_text(encoding="utf-8")), PASSPHRASE)
        payload = json.loads(crypto.unpack(blob, key, f"muster/{info['id']}/muster.bin"))
        self.assertEqual((payload["schema"], payload["id"], payload["modus"]), ("tr-muster/1", info["id"], "DEMO"))
        self.assertEqual(set(payload["module"]), {"A", "B", "C"})
        for m, mod in payload["module"].items():
            self.assertEqual(mod["geprueft"] + sum(len(v) for v in mod["nicht_pruefbar"].values()), payload["universum"], f"{m}: jede Aktie geprüft oder mit Grund")
            self.assertLessEqual(len(mod["top"]), 10)
        self.assertEqual(payload["module"]["B"]["intraday"]["status"], "nicht prüfbar")
        self.assertIn("Keine Gewinnwahrscheinlichkeit", payload["auswertung"]["hinweis"])
        self.assertTrue(payload["journal"], "Journal der Zustandswechsel")
        # öffentlich keine ISINs
        self.assertIsNone(re.search(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b", json.dumps(status)))

    def test_journal_once_and_log_only_numbers(self):
        conn = sqlite3.connect(self.state / "state.sqlite")
        try:
            n, distinct = conn.execute("SELECT COUNT(*), COUNT(DISTINCT id || zustand || tag) FROM muster_ereignis").fetchone()
            self.assertGreater(n, 0)
            self.assertEqual(n, distinct)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM muster_stand").fetchone()[0], 1)
            # Protokoll des Laufs (öffentlich als Hinweise): nur Zahlen, Kerzen einmal für Robo und Musterbereiche geladen
            lines = [r[0] for r in conn.execute("SELECT message FROM run_event WHERE step = 'muster' ORDER BY at")]
        finally:
            conn.close()
        self.assertTrue(any(l.startswith("Musterbereiche:") for l in lines), lines)
        self.assertEqual(sum("für Robo und Musterbereiche" in l for l in lines), 1, "Tageskerzen genau einmal geladen")
        for l in lines:
            self.assertIsNone(re.search(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b", l), l)


if __name__ == "__main__":
    unittest.main()
