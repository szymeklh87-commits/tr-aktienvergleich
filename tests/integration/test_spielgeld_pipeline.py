"""Spielgeld-Robo in der echten DEMO-Pipeline (Abschnitte 29.5, 29.8, 32.3) – SYNTHETISCHE Daten.

Prüft: der tägliche DEMO-Lauf führt alle Spielgelddepots einmal je Stichtag (Wiederholung bucht nichts doppelt), legt einen
verschlüsselten Stand in die Website und schreibt öffentlich nur Kennung, Zeit und Schema; die historische Simulation legt
gekennzeichnete Depots ``h-…`` an, archiviert die vorige und gibt öffentlich nur Zahlen aus; kein Echtgeld-Modus im Zustand.
"""

from __future__ import annotations

import base64
import datetime as dt
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

    def test_3_eingang_aus_der_app_im_naechsten_taeglichen_lauf(self):
        """Eine eigene Regel aus der App (verschlüsselt im Eingangsordner) wird im nächsten täglichen Lauf genau einmal
        übernommen: eigenes Forschungsdepot e-…, im selben Lauf weitergeführt, im App-Stand mit Eingangsstatus."""
        from traktien.aktienpilot import eingang as ein
        from traktien.aktienpilot import vorlagen
        from traktien.aktienpilot.config import load_aktienpilot_config
        from traktien.jobs.kursaktualisierung import neue_kennung
        from traktien.providers.demo import DEMO_NOW

        descriptor = json.loads((self.state / "crypto.json").read_text(encoding="utf-8"))
        key = crypto.verify_descriptor(descriptor, PASSPHRASE)
        regel = json.loads(json.dumps(vorlagen.alle(load_aktienpilot_config())["lineal"]))
        regel.update(id="r-app-test", version=1, name="App-Test Lineal")
        when = DEMO_NOW - dt.timedelta(hours=2)
        kennung = neue_kennung(when)
        folder = self.state / "spielgeld-eingang" / "eingang"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{kennung}.bin").write_bytes(base64.b64decode(ein.baue(kennung, "regel_testen", {"regel": regel}, key, erstellt=when)))
        # neuer Lauf auf neuem Zustand mit demselben Schlüssel (der DEMO-Stichtag ist fest)
        (self.state / "state.sqlite").unlink()
        _cli("demo", "--state-dir", str(self.state), "--site", str(self.site), "--app-dist", str(self.app), "--passphrase", PASSPHRASE)
        conn = self._db()
        row = conn.execute("SELECT status, typ FROM ap_eingang WHERE id = ?", (kennung,)).fetchone()
        self.assertEqual(tuple(row), ("verarbeitet", "regel_testen"))
        depot = conn.execute("SELECT id, art, modus, status FROM ap_depot WHERE id LIKE 'e-%'").fetchall()
        self.assertEqual([tuple(r) for r in depot], [("e-app-test-v1", "forschung", "DEMO", "aktiv")])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ap_tageslauf WHERE depot_id = 'e-app-test-v1'").fetchone()[0], 1, "im selben Lauf weitergeführt")
        conn.close()
        status = self._status()
        sid = status["spielgeld"]["id"]
        payload = json.loads(crypto.unpack((self.site / "data" / "pilot" / sid / "pilot.bin").read_bytes(), key, f"pilot/{sid}/pilot.bin"))
        self.assertIn("e-app-test-v1", [d["id"] for d in payload["depots"]])
        self.assertEqual(payload["eingaenge"][0]["kennung"], kennung)
        self.assertEqual(payload["eingaenge"][0]["status"], "verarbeitet")
        self.assertIn("r-app-test@1", payload["regeln"])


if __name__ == "__main__":
    unittest.main()
