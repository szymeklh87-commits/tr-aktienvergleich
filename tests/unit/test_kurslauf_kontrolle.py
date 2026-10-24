"""Kontrolle des Kurslaufs (ab 1.17.1, ``ops/kurslauf_kontrolle.py``): liest die Laufübersicht richtig und urteilt nur nach
den festen Kriterien. SYNTHETISCHE Laufdaten im Format der echten Notizen."""

from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location("kurslauf_kontrolle", Path(__file__).resolve().parents[2] / "ops" / "kurslauf_kontrolle.py")
kontrolle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kontrolle)

FULL = (
    "Snapshot 2026-10-26_abcdef12 (vollständig) veröffentlicht\n"
    "Stichtagskurse je Markt (nötig 80%): XNYS 3610/3618 (100%)\n"
    "Kursstichtag 2026-10-26 (Börsen mit Sitzung: XNYS, XETR)\n"
    "Kursabruf: 11145 Notierungen offen (davon 0 erneut: ohne Stichtagskurs oder Fehler), 0 bereits erledigt (Checkpoint)\n"
    "Chart-Abruf: 11145 Abrufe in 1395 s (8.0 je Sekunde; 4 gleichzeitig über 2 Hosts, Abstand 0.25 s je Host)\n"
    "Kursabruf beendet: 11145 aktualisiert, davon 49 ohne Kurs am Stichtag; 0 Einzelfehler (isoliert)"
)


def notice(text: str, status: str = "veroeffentlicht") -> dict:
    return {"annotation_level": "notice", "title": f"Lauf: {status}", "message": text}


def fake_api(run: dict, notices: list[dict], kennzahlen: str = "success"):
    jobs = {
        "jobs": [
            {"id": 1, "name": "berechnen", "conclusion": "success", "started_at": "2026-10-26T23:40:00Z", "completed_at": "2026-10-27T00:12:00Z"},
            {"id": 2, "name": "kennzahlen", "conclusion": kennzahlen},
            {"id": 3, "name": "signale-bereitstellen", "conclusion": "success" if kennzahlen == "success" else "skipped"},
        ]
    }

    def api(path: str):
        if path.endswith("/jobs?per_page=50"):
            return jobs
        if "/check-runs/1/annotations" in path:
            return notices
        return run

    return api


class RunReportParsing(unittest.TestCase):
    def test_full_run_values(self):
        report = kontrolle.run_report([notice(FULL)])
        self.assertEqual(report["status"], "veroeffentlicht")
        self.assertEqual((report["stand"], report["vollstaendigkeit"], report["stichtag"]), ("2026-10-26", "vollständig", "2026-10-26"))
        self.assertEqual((report["offen"], report["erneut"], report["checkpoint"]), (11145, 0, 0))
        self.assertEqual((report["abrufe"], report["abruf_sekunden"], report["je_sekunde"]), (11145, 1395, 8.0))
        self.assertTrue(report["gleichzeitig"])
        self.assertFalse(report["rueckfall_drosselung"])

    def test_throttled_fallback_is_recognised(self):
        text = FULL.replace(
            "Abstand 0.25 s je Host)",
            "Abstand 0.25 s je Host); Drosselung (HTTP 429) nach 5000 Abrufen – danach 6145 einzeln mit dem bisherigen Abstand",
        )
        report = kontrolle.run_report([notice(text)])
        self.assertTrue(report["rueckfall_drosselung"])


class Verdict(unittest.TestCase):
    def evaluate(self, run: dict, notices: list[dict], **kwargs) -> dict:
        with mock.patch.object(kontrolle, "api", fake_api(run, notices, **kwargs)), mock.patch.dict(os.environ, {"GITHUB_ACTIONS": ""}):
            return kontrolle.evaluate(42)

    def test_night_run_with_full_parallel_fetch_passes(self):
        run = {"event": "workflow_dispatch", "triggering_actor": {"login": "github-actions[bot]"}, "created_at": "2026-10-26T23:38:00Z"}
        result = self.evaluate(run, [notice(FULL)])
        self.assertEqual(result["ausloeser"], "nachtlauf")
        self.assertTrue(result["bestanden"], result["kriterien"])
        self.assertIn("61 min nach 22:37 UTC", result["kriterien"][0]["ist"])

    def test_manual_or_partial_runs_do_not_pass(self):
        manual = {"event": "workflow_dispatch", "triggering_actor": {"login": "szymeklh87-commits"}, "created_at": "2026-10-24T11:41:08Z"}
        self.assertFalse(self.evaluate(manual, [notice(FULL)])["bestanden"])
        scheduled = {"event": "schedule", "triggering_actor": {"login": "szymeklh87-commits"}, "created_at": "2026-10-27T09:10:00Z"}
        small = FULL.replace("11145 Notierungen offen", "51 Notierungen offen").replace("Chart-Abruf: 11145 Abrufe", "Chart-Abruf: 51 Abrufe")
        self.assertFalse(self.evaluate(scheduled, [notice(small)])["bestanden"], "nur Nachzügler aus dem Checkpoint")
        self.assertFalse(self.evaluate(scheduled, [notice(FULL, status="wartet_auf_provider")])["bestanden"])
        self.assertFalse(self.evaluate(scheduled, [notice(FULL)], kennzahlen="failure")["bestanden"])
        self.assertTrue(self.evaluate(scheduled, [notice(FULL)])["bestanden"])


if __name__ == "__main__":
    unittest.main()
