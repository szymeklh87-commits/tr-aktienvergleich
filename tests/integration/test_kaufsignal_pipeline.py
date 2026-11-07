"""Kaufsignal nach Signalregel 1 im Signal-Stand (ab 1.21.0): Spalten, Einzelansicht, Liste der Kaufkandidaten.

DEMO-Quellen (synthetische Kurse und Kennzahlen). Geprüft wird die Veröffentlichung und die innere Stimmigkeit jedes
Plans – die Rechenregeln selbst prüft tests/unit/test_tradeplan.py von Hand nachgerechnet.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from traktien.analytics import tradeplan as tp
from traktien.cli import _facts_and_signals
from traktien.config import load_method_config, load_pipeline_config
from traktien.jobs.daily import DailyRun, RunOptions
from traktien.jobs.facts import build_inputs
from traktien.jobs.sources import demo_sources
from traktien.providers.demo import DEMO_NOW
from traktien.providers.exchanges import load_exchange_table
from traktien.store import repo
from traktien.store.db import connect
from traktien.util import crypto


class BuySignalPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp(prefix="kaufsignal-"))
        cls.pipeline = load_pipeline_config()
        cls.table = load_exchange_table()
        cls.conn = connect(cls.dir / "state.sqlite")
        outcome = DailyRun(cls.conn, cls.dir, demo_sources(), load_method_config(), cls.pipeline, cls.table, None, RunOptions()).execute()
        assert outcome.status == "veroeffentlicht", outcome.message
        cls.notes = _facts_and_signals(cls.conn, cls.dir, None, cls.pipeline, mode="demo", run_id=outcome.run_id, new_snapshot=True, now=DEMO_NOW)
        cls.stand = repo.signal_stands(cls.conn)[0]
        root = cls.dir / "signale" / cls.stand["id"]
        cls.root = root
        cls.main = json.loads(crypto.unpack((root / "signale.bin").read_bytes(), None, f"signale/{cls.stand['id']}/signale.bin"))

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def detail(self, isin: str) -> dict:
        return json.loads(crypto.unpack((self.root / "details" / f"{isin}.bin").read_bytes(), None, f"signale/{self.stand['id']}/details/{isin}.bin"))

    def test_columns_rules_and_counts(self):
        handel = self.main["handel"]
        n = len(self.main["isin"])
        for column in ("status", "grund", "einstieg", "stop", "ziel", "ziel_basis", "crv", "zu_spaet"):
            self.assertEqual(len(handel[column]), n, column)
        self.assertEqual(handel["regeln"]["version"], tp.RULE_VERSION)
        self.assertTrue(set(handel["status"]) <= set(tp.STATUS_ORDER))
        self.assertEqual(sum(handel["anzahl"].values()), n)
        self.assertEqual(handel["anzahl"]["kaufsignal"], handel["status"].count("kaufsignal"))
        self.assertGreater(handel["anzahl"]["kein_kauf"], 0, "die Regel ist streng: viele DEMO-Aktien ohne Signal")

    def test_every_plan_is_consistent(self):
        h = self.main["handel"]
        for k, status in enumerate(h["status"]):
            with self.subTest(isin=self.main["isin"][k], status=status):
                if status == "kein_kauf":
                    self.assertIsNone(h["einstieg"][k])
                    self.assertFalse(h["zu_spaet"][k])
                    continue
                entry, stop, target, crv = h["einstieg"][k], h["stop"][k], h["ziel"][k], h["crv"][k]
                self.assertLess(stop, entry)
                kurs = self.main["kurs"][k]
                self.assertGreaterEqual(entry, kurs, "Einstiegslimit nie unter dem Schlusskurs")
                self.assertAlmostEqual(crv, round((target - entry) / (entry - stop), 2), places=2)
                if status == "kaufsignal":
                    self.assertGreaterEqual(crv, tp.MIN_CRV)
                    self.assertGreater(target, entry)
                    self.assertFalse(h["zu_spaet"][k])
                    self.assertEqual(h["grund"][k], "alle Bedingungen erfüllt")

    def test_candidate_list_orders_buy_signals_first_then_by_total(self):
        order = self.main["listen"]["handel"]
        statuses = [self.main["handel"]["status"][k] for k in order]
        self.assertNotIn("kein_kauf", statuses)
        self.assertEqual(statuses, sorted(statuses, key=lambda s: tp.STATUS_ORDER[s]))
        for status in ("kaufsignal", "beobachten"):
            totals = [self.main["gesamt"][k] or 0 for k in order if self.main["handel"]["status"][k] == status]
            self.assertEqual(totals, sorted(totals, reverse=True), status)

    def test_detail_carries_the_full_plan_with_all_checks(self):
        h = self.main["handel"]
        picks = [k for k, s in enumerate(h["status"]) if s != "kein_kauf"][:3] + [h["status"].index("kein_kauf")]
        for k in picks:
            detail = self.detail(self.main["isin"][k])
            plan = detail["handel"]
            self.assertEqual(plan["status"], h["status"][k])
            self.assertEqual(plan["grund"], h["grund"][k])
            groups = {c["gruppe"] for c in plan["pruefungen"]}
            self.assertTrue({"basis", "ausgangslage"} <= groups)
            for check in plan["pruefungen"]:
                self.assertTrue(check["regel"] and check["label"], check)

    def test_held_prices_never_give_a_buy_signal(self):
        """Zurückgehaltene Kurse (z. B. Währungswechsel) – kein Kaufsignal; die Quarantäne fällt schon vorher heraus."""
        listing = self.conn.execute("SELECT * FROM listing WHERE is_reference = 1 AND last_fetch_status = 'ok' ORDER BY id LIMIT 1").fetchone()
        repo.set_listing_hold(self.conn, listing["id"], True, "Notierungswährung geändert: EUR → USD")
        try:
            inputs, _ = build_inputs(self.conn, cutoff_day=self.stand["cutoff_day"], table=self.table, now=DEMO_NOW)
            held = [item for item in inputs if item.data_issue]
            self.assertEqual(len(held), 1)
            self.assertIn("Währungswechsel" if "Währungswechsel" in held[0].data_issue else "zurückgehalten", held[0].data_issue)
            from traktien.analytics import signals as sg
            result = next(r for r in sg.compute_all(inputs).results if r.isin == held[0].isin)
            self.assertEqual(result.plan.status, "kein_kauf")
            self.assertTrue(result.plan.reason.startswith("Kursdaten geprüft"))
        finally:
            repo.set_listing_hold(self.conn, listing["id"], False, None)


if __name__ == "__main__":
    unittest.main()
