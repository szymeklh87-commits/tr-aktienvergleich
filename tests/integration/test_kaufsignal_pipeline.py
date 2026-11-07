"""Kaufsignal nach Signalregel 1 im Signal-Stand (ab 1.21.0): Spalten, Einzelansicht, Liste der Kaufkandidaten.

DEMO-Quellen (synthetische Kurse und Kennzahlen). Geprüft wird die Veröffentlichung und die innere Stimmigkeit jedes
Plans – die Rechenregeln selbst prüft tests/unit/test_tradeplan.py von Hand nachgerechnet.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from traktien.analytics import ai_review as ai
from traktien.analytics import tradeplan as tp
from traktien.cli import _facts_and_signals
from traktien.config import PipelineConfig, load_method_config, load_pipeline_config
from traktien.jobs.daily import DailyRun, RunOptions
from traktien.jobs.facts import SignalsJob, build_inputs
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
        cls.env = mock.patch.dict(os.environ)
        cls.env.start()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        outcome = DailyRun(cls.conn, cls.dir, demo_sources(), load_method_config(), cls.pipeline, cls.table, None, RunOptions()).execute()
        assert outcome.status == "veroeffentlicht", outcome.message
        cls.notes = _facts_and_signals(cls.conn, cls.dir, None, cls.pipeline, mode="demo", run_id=outcome.run_id, new_snapshot=True, now=DEMO_NOW)
        cls.stand = repo.signal_stands(cls.conn)[0]
        root = cls.dir / "signale" / cls.stand["id"]
        cls.root = root
        cls.main = json.loads(crypto.unpack((root / "signale.bin").read_bytes(), None, f"signale/{cls.stand['id']}/signale.bin"))

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.conn.close()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def detail(self, isin: str, stand_id: str | None = None) -> dict:
        stand_id = stand_id or self.stand["id"]
        root = self.dir / "signale" / stand_id
        return json.loads(crypto.unpack((root / "details" / f"{isin}.bin").read_bytes(), None, f"signale/{stand_id}/details/{isin}.bin"))

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

    def test_demo_never_asks_the_paid_ai(self):
        ki = self.main["ki"]
        self.assertEqual((ki["gefragt"], ki["beantwortet"], ki["hinweis"]), (0, 0, "DEMO – keine Abfrage"))
        self.assertEqual(ki["isin"], [])
        self.assertIsNone(self.detail(self.main["isin"][self.main["listen"]["handel"][0]])["ki"])

    def test_shipped_configuration_never_asks_even_with_a_key(self):
        """Ab 1.22: technisch fertig, aber ohne Kostenfreigabe ausgeschaltet – mit Schlüssel und Testöffner wird trotzdem nichts gefragt."""
        self.assertIs(self.pipeline.get("ki.aktiv"), False)
        asked = []
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-NICHT-ECHT-43"}):
            summary = SignalsJob(self.conn, self.dir, None, self.table, now=DEMO_NOW + dt.timedelta(minutes=9), data_mode="demo", pipeline=self.pipeline,
                                 ai_opener=lambda request, timeout: asked.append(request) or b"{}").run()
        main = json.loads(crypto.unpack((self.dir / "signale" / summary["id"] / "signale.bin").read_bytes(), None, f"signale/{summary['id']}/signale.bin"))
        self.assertEqual(asked, [])
        self.assertEqual((main["ki"]["gefragt"], main["ki"]["hinweis"], main["ki"]["eingerichtet"]), (0, "abgeschaltet bis zur Kostenfreigabe", True))

    def test_ai_review_for_the_front_candidates_with_key(self):
        """Mit Schlüssel (hier ein Testöffner statt der Schnittstelle): Auswertung für die ersten zehn Kandidaten der Liste,
        im Protokoll nur Zahlen, der Schlüssel nirgends im Datenstand."""
        key = "sk-test-NICHT-ECHT-42"
        asked = []

        def opener(request, timeout):
            body = json.loads(request.data)
            asked.append(json.loads(body["messages"][0]["content"].split("\n", 1)[1])["isin"])
            text = json.dumps({"einordnung": "Einordnung aus dem Test – lang genug für die Prüfung.", "risiken": ["Testrisiko"], "zu_spaet": None,
                               "nachrichtenlage": "keine"})
            return json.dumps({"content": [{"type": "text", "text": text}], "usage": {"input_tokens": 900, "output_tokens": 90}}).encode("utf-8")

        events = []
        # ab 1.22 ist die KI in config/pipeline.yaml ausgeschaltet (ohne Kostenfreigabe) – hier eingeschaltet, um den Weg zu prüfen
        switched_on = PipelineConfig({**self.pipeline.raw, "ki": {**(self.pipeline.raw.get("ki") or {}), "aktiv": True}})
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": key}):
            summary = SignalsJob(self.conn, self.dir, None, self.table, now=DEMO_NOW + dt.timedelta(minutes=7), data_mode="demo", pipeline=switched_on,
                                 ai_opener=opener, event=lambda step, message, level="INFO": events.append((step, message, level))).run()
        stand_id = summary["id"]
        main = json.loads(crypto.unpack((self.dir / "signale" / stand_id / "signale.bin").read_bytes(), None, f"signale/{stand_id}/signale.bin"))
        front = [main["isin"][k] for k in main["listen"]["handel"][:10]]
        self.assertTrue(front, "DEMO hat Kaufkandidaten")
        self.assertEqual(asked, front, "dieselbe Reihenfolge wie die Liste der App")
        self.assertEqual(sorted(main["ki"]["isin"]), sorted(front))
        self.assertEqual((main["ki"]["gefragt"], main["ki"]["beantwortet"], main["ki"]["eingabe_token"]), (len(front), len(front), 900 * len(front)))
        self.assertTrue(main["ki"]["eingerichtet"])
        review = self.detail(front[0], stand_id)["ki"]
        self.assertEqual((review["risiken"], review["nachrichtenlage"], review["version"]), (["Testrisiko"], "keine", ai.VERSION))
        others = [i for i in main["isin"] if i not in front]
        self.assertIsNone(self.detail(others[0], stand_id)["ki"])
        self.assertEqual(summary["ki"]["beantwortet"], len(front))
        self.assertNotIn("isin", summary["ki"], "öffentliche Zusammenfassung ohne ISINs")
        logged = " ".join(message for _, message, _ in events)
        self.assertIn(f"{len(front)} von {len(front)} Aktien", logged)
        self.assertNotIn(key, logged)
        for isin in front:
            self.assertNotIn(isin, logged)
        for path in (self.dir / "signale" / stand_id).rglob("*"):
            if path.is_file():
                self.assertNotIn(key.encode(), path.read_bytes())
        self.assertNotIn(key, (self.dir / "site_meta" / "signale.json").read_text(encoding="utf-8"))

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
