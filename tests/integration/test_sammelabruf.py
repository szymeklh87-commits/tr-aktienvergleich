"""Sammelabruf der Tageskurse (ab 1.17) im ganzen Lauf: gleiche Tageskerzen und gleiche Rechnung wie der Einzelabruf.

Zwei DEMO-Läufe je Zustand: zuerst mit Kursen bis Freitag, 09.10.2026 (alles neu, Chart-Weg), dann mit Kursen bis
Montag, 12.10.2026. Im zweiten Lauf ergänzt einmal der Sammelabruf die neue Sitzung und einmal – Sammelabruf
abgeschaltet – wie bis 1.16 der Einzelabruf je Notierung. Beide Zustände müssen danach dieselben Tageskerzen und
dieselbe Rechengrundlage (Prüfsumme der Eingangsdaten) haben. SYNTHETISCHE Daten.
"""

from __future__ import annotations

import copy
import dataclasses
import datetime as dt
import math
import shutil
import tempfile
import unittest
from pathlib import Path

from traktien.config import PipelineConfig, load_method_config, load_pipeline_config
from traktien.jobs.daily import DailyRun, RunOptions
from traktien.jobs.sources import demo_sources
from traktien.providers.demo import DEMO_NOW
from traktien.providers.exchanges import load_exchange_table
from traktien.store.db import connect
from traktien.util.timeutil import UTC, date_to_day

FIRST_END = date_to_day(dt.date(2026, 10, 9))
SECOND_DAY = date_to_day(dt.date(2026, 10, 12))


class SammelabrufTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.method = load_method_config()
        cls.base_pipeline = load_pipeline_config()
        cls.table = load_exchange_table()
        cls.folders = {}
        cls.results = {}
        for batch in (True, False):
            folder = Path(tempfile.mkdtemp(prefix=f"sammelabruf-{'an' if batch else 'aus'}-"))
            cls.folders[batch] = folder
            cls.results[batch] = cls._two_runs(folder, batch)

    @classmethod
    def tearDownClass(cls):
        for batch, (conn, *_rest) in cls.results.items():
            conn.close()
            shutil.rmtree(cls.folders[batch], ignore_errors=True)

    @classmethod
    def _two_runs(cls, folder: Path, batch: bool):
        sources = demo_sources()
        provider = sources.prices
        provider.quote_now = DEMO_NOW  # Kursmeldung der abgeschlossenen Sitzung (vor Börsenbeginn am Dienstag)
        pipeline = PipelineConfig(copy.deepcopy(cls.base_pipeline.raw))
        pipeline.raw.setdefault("abruf", {})["sammelabruf"] = batch
        conn = connect(folder / "state.sqlite")
        provider.data_end = FIRST_END
        first = DailyRun(
            conn, folder, dataclasses.replace(sources, now=dt.datetime(2026, 10, 10, 4, 5, tzinfo=UTC)), cls.method, pipeline, cls.table, None, RunOptions()
        ).execute()
        provider.data_end = None
        second = DailyRun(conn, folder, sources, cls.method, pipeline, cls.table, None, RunOptions()).execute()
        events = [row[0] for row in conn.execute("SELECT message FROM run_event WHERE step = 'kurse' ORDER BY rowid")]
        return conn, first, second, events

    def bars(self, batch: bool) -> dict:
        conn = self.results[batch][0]
        rows = conn.execute(
            """SELECT l.provider_symbol, b.open, b.high, b.low, b.close_split, b.close_raw, b.volume, b.quality
               FROM daily_bar b JOIN listing l ON l.id = b.listing_id AND b.revision = l.data_revision
               WHERE b.session_day = ? ORDER BY l.provider_symbol""",
            (SECOND_DAY,),
        ).fetchall()
        return {row[0]: tuple(row[1:]) for row in rows}

    def test_both_paths_publish_both_days(self):
        for batch in (True, False):
            _, first, second, _ = self.results[batch]
            with self.subTest(sammelabruf=batch):
                self.assertEqual(first.status, "veroeffentlicht", first.message)
                self.assertEqual(second.status, "veroeffentlicht", second.message)
                self.assertEqual((first.cutoff_day, second.cutoff_day), (FIRST_END, SECOND_DAY))

    def test_batch_path_was_used_for_the_new_session(self):
        events = self.results[True][3]
        batch_lines = [line for line in events if line.startswith("Sammelabruf:")]
        self.assertEqual(len(batch_lines), 1, events)
        self.assertRegex(batch_lines[0], r"Sammelabruf: \d+ Notierungen mit gespeicherter Kursreihe")
        new = int(batch_lines[0].split("): ")[1].split(" neue Tageskerzen")[0])
        self.assertGreaterEqual(new, 90, batch_lines[0])
        # Börsen, die am Dienstagmorgen schon wieder handeln (Hongkong), bleiben beim Chart-Abruf: ihre Meldung gehört zu „heute“
        self.assertIn("meldung_fehlt", batch_lines[0])
        self.assertFalse(any(line.startswith("Sammelabruf:") for line in self.results[False][3]), "abgeschaltet heißt abgeschaltet")

    def test_same_bars_for_the_new_session(self):
        batch, single = self.bars(True), self.bars(False)
        self.assertEqual(set(batch), set(single))
        self.assertGreater(len(batch), 100)

        def same(a, b):
            if a is None or b is None:
                return a is None and b is None
            return math.isclose(a, b, rel_tol=0, abs_tol=0) or (math.isnan(a) and math.isnan(b))

        differing = [symbol for symbol in batch if not all(same(x, y) for x, y in zip(batch[symbol], single[symbol]))]
        self.assertEqual(differing, [])

    def test_same_computation_input(self):
        hashes = {}
        for batch in (True, False):
            conn, _, second, _ = self.results[batch]
            hashes[batch] = conn.execute("SELECT data_revision FROM run WHERE id = ?", (second.run_id,)).fetchone()[0]
        self.assertTrue(hashes[True])
        self.assertEqual(hashes[True], hashes[False])


if __name__ == "__main__":
    unittest.main()
