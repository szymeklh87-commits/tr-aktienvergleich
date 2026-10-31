"""Spielgeld-Robo in der echten DEMO-Pipeline (Abschnitte 29.5, 29.8, 32.3) – SYNTHETISCHE Daten.

Prüft: der tägliche DEMO-Lauf führt alle Spielgelddepots einmal je Stichtag (Wiederholung bucht nichts doppelt), legt einen
verschlüsselten Stand in die Website und schreibt öffentlich nur Kennung, Zeit und Schema; die historische Simulation legt
gekennzeichnete Depots ``h-…`` an, archiviert die vorige und gibt öffentlich nur Zahlen aus; kein Echtgeld-Modus im Zustand.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from traktien.util import crypto

REPO = Path(__file__).resolve().parents[2]
PASSPHRASE = "Demo-Testschluessel-2026!"


def _env() -> dict:
    return dict(os.environ, PYTHONPATH=str(REPO / "backend"), LOG_LEVEL="WARNING")


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "traktien", *args], check=True, cwd=REPO, env=_env(), capture_output=True, text=True, timeout=900)


class SpielgeldPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cls.state, cls.site, cls.app = base / "state", base / "site", base / "app"
        cls.app.mkdir()
        (cls.app / "index.html").write_text("<!doctype html><title>Test</title>", encoding="utf-8")
        _cli("demo", "--fresh", "--state-dir", str(cls.state), "--site", str(cls.site), "--app-dist", str(cls.app), "--passphrase", PASSPHRASE)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _db(self) -> sqlite3.Connection:
        return sqlite3.connect(self.state / "state.sqlite")

    def _status(self) -> dict:
        return json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))

    def test_1_taeglicher_lauf_und_veroeffentlichung(self):
        conn = self._db()
        depots = conn.execute("SELECT id, modus, status FROM ap_depot").fetchall()
        self.assertGreaterEqual(len(depots), 10)
        self.assertTrue(all(m == "DEMO" for _, m, _ in depots))
        runs = conn.execute("SELECT depot_id, COUNT(*) FROM ap_tageslauf GROUP BY depot_id").fetchall()
        self.assertEqual(len(runs), len(depots))
        self.assertTrue(all(n == 1 for _, n in runs))
        status = self._status()
        info = status.get("spielgeld")
        self.assertIsNotNone(info)
        self.assertEqual(set(info), {"id", "erstellt_utc", "schema"})
        blob = (self.site / "data" / "pilot" / info["id"] / "pilot.bin").read_bytes()
        self.assertTrue(blob.startswith(b"TRA1"))
        descriptor = json.loads((self.state / "crypto.json").read_text(encoding="utf-8"))
        key = crypto.verify_descriptor(descriptor, PASSPHRASE)
        payload = json.loads(crypto.unpack(blob, key, f"pilot/{info['id']}/pilot.bin"))
        self.assertEqual(payload["schema"], "tr-spielgeld/1")
        self.assertEqual(payload["modus"], "DEMO")
        self.assertIn("Keine echten Orders", payload["hinweis"])
        # öffentliche Statusdatei ohne Depotinhalte (keine ISINs, keine Depotnamen)
        text = json.dumps(status, ensure_ascii=False)
        self.assertIsNone(re.search(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b", text))
        self.assertNotIn("Pilotdepot", text)
        conn.close()

    def test_2_historische_simulation(self):
        before = json.loads((self.state / "site_meta" / "pilot.json").read_text(encoding="utf-8"))["id"]
        out = _cli("spielgeld-simulation", "--demo", "--passphrase", PASSPHRASE, "--state-dir", str(self.state), "--tage", "6",
                   "--site", str(self.site), "--app-dist", str(self.app))
        summary = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertEqual(summary["tage"], 6)
        self.assertEqual(summary["schritte"], 6 * summary["depots"])
        self.assertEqual(summary["rechnungen"], 6)
        # öffentliche Ausgabe nur Zahlen: keine ISINs, keine Namen
        self.assertIsNone(re.search(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b", out.stdout))
        self.assertNotIn("kennzahlen", summary)
        conn = self._db()
        hist = conn.execute("SELECT id, name, test_id, status FROM ap_depot WHERE id LIKE 'h-%'").fetchall()
        self.assertEqual(len(hist), summary["depots"])
        self.assertTrue(all("(historische Simulation)" in name and test.startswith("historisch-") and st == "aktiv" for _, name, test, st in hist))
        # zweite Simulation: die erste bleibt archiviert erhalten, nichts gelöscht
        _cli("spielgeld-simulation", "--demo", "--passphrase", PASSPHRASE, "--state-dir", str(self.state), "--tage", "3")
        rows = conn.execute("SELECT status, COUNT(*) FROM ap_depot WHERE id LIKE 'h-%' GROUP BY status").fetchall()
        self.assertEqual(dict(rows), {"aktiv": summary["depots"], "archiviert": summary["depots"]})
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ap_depot WHERE modus NOT IN ('PAPER', 'SIGNAL', 'DEMO')").fetchone()[0], 0)
        after = json.loads((self.state / "site_meta" / "pilot.json").read_text(encoding="utf-8"))["id"]
        self.assertNotEqual(before, after)
        self.assertEqual(sorted(p.name for p in (self.state / "pilot").iterdir()), [after])
        conn.close()


if __name__ == "__main__":
    unittest.main()
