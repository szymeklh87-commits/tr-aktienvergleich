"""Offizieller Stand und Zwischenstand getrennt in status.json (ab 1.20.5, Befunde F02, F05, F07).

Vom 03. bis 07.11.2026 scheiterte der offizielle Tageslauf bei jedem Versuch, von Hand gestartete Zwischenstände liefen aber
durch. Bis 1.20.4 zählten sie als „letzte erfolgreiche Prüfung“ und waren der „letzte Lauf“ – die App zeigte weder den
Fehlschlag noch „Keine aktuelle Prüfung“, und der Zwischenstand rechnete ungeprüft mit den Schlusskursen der fehlenden Tage.
Alle Läufe mit DEMO-Daten (synthetische Kurse). Nachgestellt wie im Betrieb: offizieller Stand vom Freitag, 09.10.2026; der
Lauf für Montag, 12.10., lädt alle Kurse und scheitert danach; der Zwischenstand vom 13.10. rechnet mit den so gespeicherten,
aber nie offiziell geprüften Schlusskursen vom 12.10.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from traktien.config import load_method_config, load_pipeline_config
from traktien.jobs.daily import DailyRun, RunOptions, build_status_file
from traktien.jobs.intraday import IntradayRun
from traktien.jobs.sources import demo_sources
from traktien.providers.demo import DEMO_INTRADAY_NOW, DEMO_NOW
from traktien.providers.exchanges import load_exchange_table
from traktien.store import repo
from traktien.store.db import connect
from traktien.util import crypto
from traktien.util.timeutil import iso_utc

TAG = dt.timedelta(days=1)
FREITAG = DEMO_NOW - 3 * TAG  # Samstag, 10.10.2026, 04:05 UTC → offizieller Stand vom Freitag, 09.10.


class SeparatedStatusTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="stand-getrennt-"))
        self.pipeline = load_pipeline_config()
        self.method = load_method_config()
        self.table = load_exchange_table()
        self.conn = connect(self.dir / "state.sqlite")
        self.addCleanup(self.conn.close)
        first = self.official(FREITAG)
        self.assertEqual(first.status, "veroeffentlicht", first.message)
        self.assertEqual(self.status()["offiziell"]["kursstand"], "2026-10-09")
        self.first = first

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def official(self, now: dt.datetime, **options):
        sources = demo_sources()
        sources.now = now
        return DailyRun(self.conn, self.dir, sources, self.method, self.pipeline, self.table, None, RunOptions(**options)).execute()

    def intraday(self, now: dt.datetime):
        sources = demo_sources()
        sources.now = now
        sources.prices.quote_now = now
        return IntradayRun(self.conn, self.dir, sources, self.method, self.pipeline, self.table, None, RunOptions(trigger="zwischenstand")).execute()

    def status(self) -> dict:
        return json.loads((self.dir / "site_meta" / "status.json").read_text(encoding="utf-8"))

    def finished(self, run_id: str) -> str:
        return self.conn.execute("SELECT finished_at FROM run WHERE id = ?", (run_id,)).fetchone()[0]

    def failed_official(self, now: dt.datetime):
        """Offizieller Lauf, der alle Kurse lädt und speichert und danach scheitert (wie vom 03. bis 07.11.2026)."""
        with mock.patch.object(DailyRun, "step_fx", side_effect=RuntimeError("Testausfall nach dem Kursabruf")):
            outcome = self.official(now, force_publish=True)
        self.assertEqual(outcome.status, "fehlgeschlagen", outcome.message)
        return outcome

    def versions(self) -> dict:
        return DailyRun(self.conn, self.dir, demo_sources(), self.method, self.pipeline, self.table, None, RunOptions()).versions

    def test_failed_official_run_stays_visible_behind_a_successful_intraday(self):
        failed = self.failed_official(DEMO_NOW)  # Stichtag 12.10. – Kurse gespeichert, dann gescheitert
        status = self.status()
        official = status["offiziell"]
        self.assertEqual(official["snapshot_id"], self.first.snapshot_id)
        self.assertEqual(official["kursstand"], "2026-10-09")
        self.assertEqual(official["letzte_erfolgreiche_pruefung_utc"], self.finished(self.first.run_id))
        self.assertEqual(official["letzter_lauf"]["status"], "fehlgeschlagen")
        self.assertEqual(official["letzter_fehlschlag"]["run_id"], failed.run_id)
        self.assertIn("Testausfall nach dem Kursabruf", official["letzter_fehlschlag"]["message"])
        self.assertEqual(official["fehlschlaege_seit_erfolg"], 1)
        self.assertEqual(official["erster_fehlschlag_seit_erfolg_utc"], self.finished(failed.run_id))
        # Der nächste offizielle Stand ist der fehlende 12.10. – bis 1.20.4 stand hier schon der 13.10.
        self.assertEqual(status["naechster_kursstand"]["datum"], "2026-10-12")

        # Zwischenstand am 13.10. läuft durch: Er ist jetzt der letzte Lauf, verdeckt den Fehlschlag aber nicht mehr
        z = self.intraday(DEMO_INTRADAY_NOW)
        self.assertEqual(z.status, "veroeffentlicht", z.message)
        status = self.status()
        self.assertEqual((status["last_run"]["trigger"], status["last_run"]["status"]), ("zwischenstand", "veroeffentlicht"))
        self.assertEqual(status["last_successful_check_utc"], self.finished(self.first.run_id), "nur offizielle Läufe zählen")
        self.assertEqual(status["offiziell"]["letzter_fehlschlag"]["run_id"], failed.run_id)
        self.assertEqual(status["offiziell"]["fehlschlaege_seit_erfolg"], 1)
        self.assertEqual(status["naechster_kursstand"]["datum"], "2026-10-12")

        # Grundlage des Zwischenstands: Für den 12.10. gibt es keinen offiziellen Stand – „ungeprüft“
        intraday = status["zwischenstand"]
        self.assertEqual((intraday["stichtag"], intraday["offizieller_stichtag"]), ("2026-10-13", "2026-10-09"))
        self.assertIs(intraday["basis_geprueft"], False)
        self.assertIn("Für den 12.10.2026 gibt es keinen geprüften offiziellen Stand", intraday["basis_hinweis"])
        self.assertIn("vom 09.10.2026", intraday["basis_hinweis"])
        self.assertIn("Keine Kaufsignale", intraday["basis_hinweis"])
        manifest = json.loads(crypto.unpack((self.dir / "snapshots" / z.snapshot_id / "manifest.bin").read_bytes(), None, f"snapshots/{z.snapshot_id}/manifest.bin"))
        self.assertIs(manifest["zwischenstand"]["basis_geprueft"], False)
        self.assertEqual(manifest["zwischenstand"]["basis_luecke"], ["2026-10-12"])

    def test_intraday_on_the_newest_official_stand_is_checked(self):
        second = self.official(DEMO_NOW)  # offizieller Stand 12.10.
        self.assertEqual(second.status, "veroeffentlicht", second.message)
        z = self.intraday(DEMO_INTRADAY_NOW)  # Zwischenstand 13.10.
        self.assertEqual(z.status, "veroeffentlicht", z.message)
        intraday = self.status()["zwischenstand"]
        self.assertIs(intraday["basis_geprueft"], True)
        self.assertIsNone(intraday["basis_hinweis"])
        status = self.status()
        self.assertIsNone(status["offiziell"]["letzter_fehlschlag"])
        self.assertEqual(status["offiziell"]["fehlschlaege_seit_erfolg"], 0)
        self.assertEqual(status["last_successful_check_utc"], self.finished(second.run_id))
        self.assertEqual(status["naechster_kursstand"]["datum"], "2026-10-13")

    def test_success_after_failures_clears_them_and_double_start_is_no_failure(self):
        self.failed_official(DEMO_NOW)
        self.failed_official(DEMO_NOW + TAG)
        self.assertEqual(self.status()["offiziell"]["fehlschlaege_seit_erfolg"], 2)
        versions = self.versions()
        # Doppelstart-Schutz: ein zweiter Lauf gleichzeitig ist kein Fehlschlag
        at = iso_utc(DEMO_NOW + 3 * TAG)
        repo.create_run(self.conn, "doppelt", trigger="zeitplan", planned_start=None, attempt=1, versions=versions, data_mode="demo", started_at=at)
        repo.update_run(self.conn, "doppelt", status="abgebrochen", status_detail="Anderer Lauf aktiv: x", finished_at=at)
        status = build_status_file(self.conn, self.dir, "demo", self.pipeline, last_run_id="doppelt", now=DEMO_NOW + 3 * TAG, keep_next=True)
        self.assertEqual(status["offiziell"]["fehlschlaege_seit_erfolg"], 2)
        self.assertNotEqual(status["offiziell"]["letzter_lauf"]["run_id"], "doppelt")
        # Ein späterer erfolgreicher offizieller Lauf (hier: „keine neuen Daten“) beendet die Fehlerserie
        later = iso_utc(DEMO_NOW + 4 * TAG)
        repo.create_run(self.conn, "spaeter", trigger="zeitplan", planned_start=None, attempt=1, versions=versions, data_mode="demo", started_at=later)
        repo.update_run(self.conn, "spaeter", status="keine_neuen_daten", status_detail="Kein neuer abgeschlossener Börsentag", finished_at=later)
        status = build_status_file(self.conn, self.dir, "demo", self.pipeline, last_run_id="spaeter", now=DEMO_NOW + 4 * TAG, keep_next=True)
        self.assertIsNone(status["offiziell"]["letzter_fehlschlag"])
        self.assertEqual(status["offiziell"]["fehlschlaege_seit_erfolg"], 0)
        self.assertEqual(status["offiziell"]["letzte_erfolgreiche_pruefung_utc"], later)
        self.assertEqual(status["last_successful_check_utc"], later)


if __name__ == "__main__":
    unittest.main()
