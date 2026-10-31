"""Depot-Optimierer über die Befehle ``depot-optimierer`` und ``depot-bericht`` auf dem echten DEMO-Zustand – SYNTHETISCHE
Daten; dazu das Nachladen älterer Kerzen mit einem nachgebildeten Kursanbieter.

Prüft: Forschungsergebnis mit Prüfsumme im Zustand, Empfehlung und Prognosen unveränderlich gespeichert, verschlüsselter
Spielgeld-Stand mit dem Teil „optimierer“, öffentliche Ausgabe nur mit Zahlen, verschlüsselter Bericht; ältere Kerzen
ergänzen nur vor der ersten gespeicherten Kerze (geprüfte Kerzen bleiben unverändert)."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tests.integration.test_spielgeld_pipeline import PASSPHRASE, _cli
from traktien.util import crypto


class _Anbieter:
    """Nachgebildeter Kursanbieter: Tageskerzen an Werktagen im angefragten Zeitraum."""

    def __init__(self):
        self.abrufe = 0

    def fetch_history(self, symbol, start_day, end_day, **_):
        from traktien.providers.base import PriceHistory

        self.abrufe += 1
        days = np.array([d for d in range(int(start_day), int(end_day) + 1) if (d + 3) % 7 < 5], dtype=np.int64)
        close = 50.0 * np.exp(np.linspace(0, 0.1, len(days)))
        return PriceHistory(provider="test", symbol=symbol, days=days, open=close, high=close * 1.01, low=close * 0.99, close=close,
                            volume=np.full(len(days), 1000.0), close_raw=close, currency="EUR")


class OptimiererPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cls.state, cls.site, cls.app = base / "state", base / "site", base / "app"
        cls.app.mkdir()
        (cls.app / "index.html").write_text("<!doctype html><title>Test</title>", encoding="utf-8")
        _cli("demo", "--fresh", "--state-dir", str(cls.state), "--site", str(cls.site), "--app-dist", str(cls.app), "--passphrase", PASSPHRASE)
        shutil.copy(cls.state / "state.sqlite", base / "vorher.sqlite")
        cls.vorher = base / "vorher.sqlite"
        cls.out = _cli("depot-optimierer", "--demo", "--passphrase", PASSPHRASE, "--state-dir", str(cls.state), "--schritt", "1", "--site", str(cls.site),
                       "--app-dist", str(cls.app))
        cls.bericht = base / "bericht.html"
        cls.bericht_out = _cli("depot-bericht", "--demo", "--passphrase", PASSPHRASE, "--state-dir", str(cls.state), "--ziel", str(cls.bericht))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_public_output_only_numbers(self):
        line = self.out.stdout.strip().splitlines()[-1]
        summary = json.loads(line)
        self.assertEqual(summary["merkmale"], 92)
        self.assertGreater(summary["aktien_panel"], 50)
        self.assertEqual(set(summary["horizonte"]), {"w1", "w2", "w4", "w12", "w26", "w52"})
        self.assertIsNone(re.search(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b", self.out.stdout + self.out.stderr + self.bericht_out.stdout), "keine ISIN im Protokoll")
        self.assertNotIn("opt-", line, "keine Kennung im öffentlichen Protokoll")

    def test_result_recommendation_and_stand(self):
        conn = sqlite3.connect(self.state / "state.sqlite")
        try:
            rows = conn.execute("SELECT id, modus FROM ap_optimierer").fetchall()
            emp = conn.execute("SELECT COUNT(*), COUNT(DISTINCT variante) FROM ap_empfehlung").fetchone()
        finally:
            conn.close()
        self.assertEqual([r[1] for r in rows], ["DEMO"])
        self.assertEqual(emp, (7, 7), "sechs Varianten und die Rangliste – auch wenn keine belastbar ist")
        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        rel = f"pilot/{status['spielgeld']['id']}/pilot.bin"
        key = crypto.verify_descriptor(json.loads((self.state / "crypto.json").read_text(encoding="utf-8")), PASSPHRASE)
        stand = json.loads(crypto.unpack((self.site / "data" / rel).read_bytes(), key, rel))
        opt = stand["optimierer"]
        self.assertEqual(opt["modell"]["id"], rows[0][0])
        self.assertEqual(len(opt["modell"]["forschung"]["faktoren"]["zeilen"]), 92 * 6, "jede Prüfung dokumentiert")
        for h in opt["modell"]["forschung"]["horizonte"].values():
            md = h.get("endmodell")
            self.assertTrue(md is None or "knn" not in md, "keine Trainingsdaten in der App")
        self.assertEqual(set(opt["heute"]["varianten"]), {"rendite", "ausgewogen", "stabil", "kurz", "mittel", "lang", "rangliste"})
        self.assertIn("kontrolle", opt)
        inventar = opt["modell"]["inventar"]
        self.assertEqual(len(inventar), 76)
        self.assertTrue(all(x["verwendet"] or x["grund"] for x in inventar))

    def test_encrypted_report(self):
        html = self.bericht.read_text(encoding="utf-8")
        self.assertIn("crypto.subtle", html)
        blob = re.search(r'const BLOB = "([A-Za-z0-9+/=]+)"', html).group(1)
        import base64

        raw = base64.b64decode(blob)
        self.assertTrue(raw.startswith(b"TRA1") and raw[4] & 1, "verschlüsselt")
        key = crypto.verify_descriptor(json.loads((self.state / "crypto.json").read_text(encoding="utf-8")), PASSPHRASE)
        aad = json.loads(re.search(r"const AAD = (\"[^\"]+\");", html).group(1))
        daten = json.loads(crypto.unpack(raw, key, aad))
        self.assertEqual(daten["modus"], "DEMO")
        self.assertEqual(list(daten["horizonte"]), ["w1", "w2", "w4", "w12", "w26", "w52"])
        self.assertEqual(list(daten["empfehlung"]["varianten"]), ["rendite", "ausgewogen", "stabil", "kurz", "mittel", "lang"])

    def test_long_history_only_before_stored_bars(self):
        from traktien.aktienpilot import langhistorie
        from traktien.jobs.sources import demo_sources
        from traktien.store import repo
        from traktien.store.db import connect

        work = Path(self.tmp.name) / "arbeit.sqlite"
        shutil.copy(self.vorher, work)
        conn = connect(work)
        try:
            latest = repo.published_snapshots(conn, "demo")[0]
            D = int(latest["cutoff_day"])
            members = repo.universe_members(conn, latest["universe_id"])
            refs = repo.reference_listings(conn)
            isin = sorted(i for i in members if i in refs)[0]
            lid, rev = int(refs[isin]["id"]), int(refs[isin]["data_revision"])
            first_before, last_before, n_before = repo.bar_range(conn, lid, rev)
            alt = repo.load_bars(conn, lid, rev)
            anbieter = _Anbieter()
            z = langhistorie.ergaenzen(conn, anbieter, demo_sources().calendars, members=members, bis=D, jahre=1.5)
            first_after, last_after, n_after = repo.bar_range(conn, lid, rev)
            neu = repo.load_bars(conn, lid, rev)
        finally:
            conn.close()
        self.assertGreater(z["ergaenzt"], 0)
        self.assertEqual(z["fehler"], 0)
        self.assertEqual(anbieter.abrufe, z["abgerufen"])
        self.assertLess(first_after, first_before)
        self.assertEqual(last_after, last_before)
        keep = neu["days"] >= first_before
        np.testing.assert_array_equal(neu["days"][keep], alt["days"])
        np.testing.assert_array_equal(neu["close"][keep], alt["close"], "geprüfte Kerzen unverändert")
        self.assertGreaterEqual(z["jahre"]["ab_1"], z["ergaenzt"])


if __name__ == "__main__":
    unittest.main()
