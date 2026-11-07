"""Kurzbericht des täglichen Laufs (Hinweis in der GitHub-Laufübersicht)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from traktien.jobs.daily import RunOutcome
from traktien.jobs.summary import MAX_BYTES, identifiers, public_text, report_lines, workflow_notice
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
        self.assertIn("Kursabruf beendet: 2900 aktualisiert, davon 897 ohne Kurs am Stichtag; 0 Einzelfehler (isoliert)", lines)
        # ab 1.21.0 ohne Kürzel (Befund F19): nur der letzte Kurstag davor mit Anzahl
        self.assertEqual(lines[-1], "Ohne Stichtagskurs, Beispiele je Börse: XETR vorher 2026-10-09 2×")
        self.assertFalse(any("SAP" in line or "ALV" in line for line in lines))
        self.assertFalse(any("Split" in line for line in lines))

    def test_counts_stay_ahead_of_examples_when_many_markets_lack_the_cutoff_close(self) -> None:
        gaps = {f"X{k:03d}": [f"S{k}.XX (vorher 2026-10-09)", f"T{k}.XX (vorher 2026-10-09)", f"U{k}.XX (vorher 2026-10-09)"] for k in range(30)}
        outcome = RunOutcome(75, "wartet_auf_provider", "Daten für viele Börsen unvollständig", "lauf-1", details=dict(self.outcome.details, ohne_stichtag=gaps))
        self.conn.execute("UPDATE run SET cutoff_day = 20738 WHERE id = 'lauf-1'")
        repo.log_event(self.conn, "lauf-1", "kurse", "Kursabruf beendet: 3916 aktualisiert")
        notice = workflow_notice(self.conn, outcome)
        self.assertIn("Kursabruf beendet", notice)
        self.assertLess(notice.index("Kursabruf beendet"), notice.index("Ohne Stichtagskurs"))
        examples = [line for line in report_lines(self.conn, outcome) if line.startswith("Ohne Stichtagskurs")]
        self.assertEqual(len(examples), 1, "Beispiele in einer Zeile")
        self.assertLessEqual(len(examples[0]), 1200)

    def test_listings_without_data_are_grouped_by_exchange_with_error_kinds(self) -> None:
        self.conn.execute("UPDATE run SET cutoff_day = 20738 WHERE id = 'lauf-1'")
        now = "2026-10-13T08:00:00Z"
        self.conn.execute(
            "INSERT INTO instrument(id, isin, identity_status, created_at, updated_at) VALUES (1, 'CA0000000001', 'verifiziert', ?, ?)", (now, now)
        )
        rows = [("ABC.TO", "XTSE", "keine_daten", "ABC.TO: Symbol unbekannt (404)"), ("DEF.TO", "XTSE", "keine_daten", "DEF.TO: Symbol unbekannt (404)"),
                ("GHI.TO", "XTSE", "keine_daten", None), ("VOD.L", "XLON", "keine_daten", "VOD.L: keine gültigen Tageskurse im Zeitraum"),
                ("SAP.DE", "XETR", "fehler", "SAP.DE: HTTP 500"), ("AAPL", "US", "ok", None)]
        for k, (symbol, exchange, status, error) in enumerate(rows, start=1):
            self.conn.execute(
                "INSERT INTO listing(id, instrument_id, provider, provider_symbol, exchange_key, is_reference, last_error, created_at, updated_at) "
                "VALUES (?, 1, 'yahoo', ?, ?, 0, ?, ?, ?)",
                (k, symbol, exchange, error, now, now),
            )
            repo.mark_fetched(self.conn, "20738:produktiv", k, status)
        repo.log_event(self.conn, "lauf-1", "kurse", "Anbieter drosselt bei VOD.L – Checkpoint gesetzt", "WARN")
        repo.log_event(self.conn, "lauf-1", "pruefung", "ABC.TO: Währungswechsel CAD → USD – zurückgehalten", "WARN")
        lines = report_lines(self.conn, self.outcome)
        missing = next(line for line in lines if line.startswith("Keine Kursdaten je Börse"))
        # ab 1.21.0 (Befund F19): Fehlerarten mit Anzahl statt Kürzeln als Beispiel
        self.assertEqual(missing, "Keine Kursdaten je Börse: XTSE 3 (Symbol unbekannt (404) 2, ohne Meldung 1), XLON 1 (keine gültigen Tageskurse im Zeitraum 1)")
        errors = next(line for line in lines if line.startswith("Abruffehler je Börse"))
        self.assertEqual(errors, "Abruffehler je Börse: XETR 1 (HTTP 500 1)")
        self.assertLess(lines.index(missing), lines.index(errors))
        self.assertIn("WARN kurse: 1× – Anbieter drosselt bei [Kürzel] – Checkpoint gesetzt", lines)
        self.assertIn("WARN pruefung: 1× – [Kürzel]: Währungswechsel CAD → USD – zurückgehalten", lines)
        notice = workflow_notice(self.conn, self.outcome)
        for symbol in ("ABC.TO", "DEF.TO", "GHI.TO", "VOD.L", "SAP.DE", "AAPL"):
            self.assertNotIn(symbol, notice)

    def test_public_text_masks_isins_and_symbols_but_keeps_counts_codes_and_currencies(self) -> None:
        now = "2026-10-13T08:00:00Z"
        self.conn.execute("INSERT INTO instrument(id, isin, identity_status, created_at, updated_at) VALUES (1, 'HK0000000001', 'verifiziert', ?, ?)", (now, now))
        for k, (symbol, ticker, exchange, currency) in enumerate((("2780.HK", "2780", "XHKG", "HKD"), ("BRK-B", "BRK-B", "US", "USD"), ("EUR.DE", "EUR", "XETR", "EUR")), start=1):
            self.conn.execute(
                "INSERT INTO listing(id, instrument_id, provider, provider_symbol, ticker, exchange_key, currency, is_reference, created_at, updated_at) "
                "VALUES (?, 1, 'yahoo', ?, ?, ?, ?, 0, ?, ?)",
                (k, symbol, ticker, exchange, currency, now, now),
            )
        known = identifiers(self.conn)
        self.assertIn("2780.HK", known)
        self.assertNotIn("2780", known, "reine Ziffern bleiben (Zählungen)")
        self.assertNotIn("EUR", known, "Währungen bleiben lesbar")
        self.assertNotIn("XHKG", known)
        text = public_text("Chart-Abruf: 2780 Abrufe; 2780.HK und BRK-B gedrosselt; US0378331005: Name passt nicht; XHKG 735/735; EUR → USD.", known)
        self.assertEqual(text, "Chart-Abruf: 2780 Abrufe; [Kürzel] und [Kürzel] gedrosselt; [ISIN]: Name passt nicht; XHKG 735/735; EUR → USD.")

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
