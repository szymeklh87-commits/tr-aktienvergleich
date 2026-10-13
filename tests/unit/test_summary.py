"""Kurzbericht des täglichen Laufs (Hinweis in der GitHub-Laufübersicht)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from traktien.jobs.daily import RunOutcome
from traktien.jobs.summary import MAX_BYTES, report_lines, workflow_notice
from traktien.store import repo
from traktien.store.db import connect

VERSIONS = {"method": "m", "metrics": "k", "ranking": "r", "frequency": "f", "software": "s"}


class RunSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="summary-"))
        self.conn = connect(self.dir / "state.sqlite")
        repo.create_run(self.conn, "lauf-1", trigger="manuell", planned_start=None, attempt=1, versions=VERSIONS, data_mode="produktiv")
        self.outcome = RunOutcome(
            75,
            "wartet_auf_provider",
            "Daten für XETR noch unvollständig; nächster Versuch geplant",
            "lauf-1",
            details={
                "cutoff_day": 20738,
                "details": {
                    "market_threshold": 0.8,
                    "per_market": {
                        "XETR": {"expected": 900, "present": 3, "closed": 0},
                        "XNYS": {"expected": 2000, "present": 1995, "closed": 0},
                        "XTKS": {"expected": 0, "present": 0, "closed": 120},
                    },
                },
                "ohne_stichtag": {"XETR": ["SAP.DE (vorher 2026-10-09)", "ALV.DE (vorher 2026-10-09)"]},
            },
        )

    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_most_important_lines_come_first(self) -> None:
        repo.log_event(self.conn, "lauf-1", "kurse", "Kursabruf beendet: 2900 aktualisiert, davon 897 ohne Kurs am Stichtag; 0 Einzelfehler (isoliert)")
        repo.log_event(self.conn, "lauf-1", "revision", "SAP.DE: neuer Split gemeldet")  # Einzelmeldung: nicht im Bericht
        lines = report_lines(self.conn, self.outcome)
        self.assertEqual(lines[0], self.outcome.message)
        self.assertEqual(lines[1], "Stichtagskurse je Markt (nötig 80%): XETR 3/900 (0%) ✗, XNYS 1995/2000 (100%)")
        self.assertEqual(lines[2], "Ohne Stichtagskurs XETR, z. B.: SAP.DE (vorher 2026-10-09), ALV.DE (vorher 2026-10-09)")
        self.assertIn("Kursabruf beendet: 2900 aktualisiert, davon 897 ohne Kurs am Stichtag; 0 Einzelfehler (isoliert)", lines)
        self.assertFalse(any("Split" in line for line in lines))

    def test_warnings_are_counted_with_few_examples(self) -> None:
        for i in range(250):
            repo.log_event(self.conn, "lauf-1", "identitaet", f"US{i:010d}: Name passt nicht zur Notierung " + "x" * 400, "WARN")
        lines = report_lines(self.conn, self.outcome)
        warning = [line for line in lines if line.startswith("WARN identitaet")]
        self.assertEqual(len(warning), 1)
        self.assertIn("250×", warning[0])
        self.assertIn("(+247 weitere)", warning[0])
        self.assertLess(len(warning[0]), 700, "Beispiele werden gekürzt")

    def test_notice_fits_github_limit_and_is_escaped(self) -> None:
        for i in range(400):
            repo.log_event(self.conn, "lauf-1", "kurse", f"Meldung {i}: " + "y" * 150)
        notice = workflow_notice(self.conn, self.outcome)
        self.assertTrue(notice.startswith("::notice title=Lauf%3A wartet_auf_provider::"))
        self.assertNotIn("\n", notice)
        self.assertLess(len(notice.encode("utf-8")), MAX_BYTES + 400)
        self.assertIn("Stichtagskurse je Markt", notice)
        self.assertIn("weitere Zeilen im Protokoll", notice)


if __name__ == "__main__":
    unittest.main()
