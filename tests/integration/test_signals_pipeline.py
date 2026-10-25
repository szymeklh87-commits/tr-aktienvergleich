"""Kennzahlen, Kursziele und Signale (ab 1.6) im Ablauf: Abruf mit Zeitbudget, Signal-Stand, Website.

Alle Läufe verwenden die DEMO-Quellen (synthetische Kurse und Kennzahlen).
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from traktien.cli import _facts_and_signals
from traktien.config import load_method_config, load_pipeline_config
from traktien.jobs.daily import DailyRun, RunOptions, build_status_file
from traktien.jobs.facts import FactsJob, FactsSettings, SignalsJob, eligible_stocks
from traktien.jobs.sources import demo_sources
from traktien.providers.base import NoDataError, ProviderThrottled
from traktien.providers.demo import DEMO_NOW, DemoExtraSources, DemoFactsProvider
from traktien.providers.exchanges import load_exchange_table
from traktien.publish.site import assemble_site
from traktien.store import repo
from traktien.store.db import connect
from traktien.util import crypto


class CountingFacts(DemoFactsProvider):
    """DEMO-Kennzahlen mit Zähler; wirft ab ``throttle_after`` Abrufen ProviderThrottled."""

    def __init__(self, throttle_after: int | None = None) -> None:
        super().__init__()
        self.calls: list[str] = []
        self.throttle_after = throttle_after

    def fetch_facts(self, symbol: str) -> dict:
        if self.throttle_after is not None and len(self.calls) >= self.throttle_after:
            raise ProviderThrottled("Testdrosselung")
        self.calls.append(symbol)
        return super().fetch_facts(symbol)


class SignalsPipelineTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="signale-"))
        self.pipeline = load_pipeline_config()
        self.table = load_exchange_table()
        sources = demo_sources()
        self.conn = connect(self.dir / "state.sqlite")
        self.addCleanup(self.conn.close)
        outcome = DailyRun(self.conn, self.dir, sources, load_method_config(), self.pipeline, self.table, None, RunOptions()).execute()
        self.assertEqual(outcome.status, "veroeffentlicht", outcome.message)
        self.run_id = outcome.run_id

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def facts_job(self, provider, **settings) -> FactsJob:
        s = FactsSettings(**settings)
        return FactsJob(self.conn, provider=provider, extra=DemoExtraSources(provider), settings=s, now=DEMO_NOW)

    def test_first_run_fetches_all_eligible_then_only_due_ones(self):
        provider = CountingFacts()
        report = self.facts_job(provider).run()
        eligible = eligible_stocks(self.conn)
        self.assertEqual(report.fetched, len(eligible))
        self.assertEqual(report.never_left, 0)
        self.assertEqual(report.with_facts, len(eligible))
        history = repo.target_history_counts(self.conn)
        self.assertGreater(history["aktien"], 0, "Kursziele werden je Tag gespeichert")
        provider2 = CountingFacts()
        again = FactsJob(self.conn, provider=provider2, extra=None, settings=FactsSettings(), now=DEMO_NOW + dt.timedelta(hours=2)).run()
        self.assertEqual(again.fetched, 0, "nichts fällig: frisch abgerufen")
        later = FactsJob(self.conn, provider=CountingFacts(), extra=None, settings=FactsSettings(), now=DEMO_NOW + dt.timedelta(days=4)).run()
        self.assertGreater(later.fetched, 0, "nach 3 Tagen werden Aktien mit Analysten erneuert")
        self.assertLess(later.fetched, len(eligible), "Aktien ohne Analysten erst nach 14 Tagen")

    def test_message_counts_only_considered_stocks_against_their_own_base(self):
        """Täglicher Lauf vom 25.10.2026: „11025 von 11006 Aktien mit Kennzahlen“ – der erste Wert zählte alle gespeicherten
        Kennzahlen, auch von Aktien, die nicht mehr berücksichtigt sind. Zähler und Bezugsmenge sind jetzt dieselbe Menge."""
        self.facts_job(CountingFacts()).run()
        eligible = eligible_stocks(self.conn)
        repo.save_facts(self.conn, "XX0000000000", "ALT.XX", "ok", {"kennzahlen": {}}, at="2026-10-01T00:00:00Z")  # nicht mehr in der Liste
        report = FactsJob(self.conn, provider=CountingFacts(), extra=None, settings=FactsSettings(), now=DEMO_NOW + dt.timedelta(hours=1)).run()
        self.assertEqual((report.with_facts, report.eligible, report.stored_ok), (len(eligible), len(eligible), len(eligible) + 1))
        text = report.message()
        self.assertIn(f"Kennzahlen vorhanden für {len(eligible)} von {len(eligible)} berücksichtigten Aktien", text)
        self.assertIn(f"gespeichert für {len(eligible) + 1} Aktien, davon 1 derzeit nicht berücksichtigt", text)
        self.assertLessEqual(report.with_facts, report.eligible, "Zähler nie größer als die Bezugsmenge")

    def test_throttling_stops_and_keeps_what_was_fetched(self):
        report = self.facts_job(CountingFacts(throttle_after=20)).run()
        self.assertEqual(report.fetched, 20)
        self.assertIn("drosselt", report.stopped)
        self.assertEqual(report.extras, {}, "bei Drosselung keine Ergänzungen")
        self.assertGreater(report.never_left, 0)

    def test_errors_keep_previous_good_facts(self):
        self.facts_job(CountingFacts()).run()
        isin, row = next(iter(repo.facts_rows(self.conn).items()))

        class Broken(DemoFactsProvider):
            def fetch_facts(self, symbol):
                raise ConnectionError("weg")

        FactsJob(self.conn, provider=Broken(), extra=None, settings=FactsSettings(top_refresh_days=0, ok_age_days=0, empty_age_days=0), now=DEMO_NOW + dt.timedelta(days=1)).run()
        after = repo.facts_rows(self.conn)[isin]
        self.assertEqual(after["status"], "ok")
        self.assertEqual(after["payload"], row["payload"])
        self.assertEqual(after["fetched_at"], row["fetched_at"], "Abrufzeit bleibt die des letzten guten Abrufs")
        self.assertIn("weg", after["error"])

    def test_unknown_symbols_are_marked_and_retried_after_30_days(self):
        class Unknown(DemoFactsProvider):
            def fetch_facts(self, symbol):
                raise NoDataError("unbekannt")

        report = FactsJob(self.conn, provider=Unknown(), extra=None, settings=FactsSettings(), now=DEMO_NOW).run()
        self.assertEqual(report.empty, len(eligible_stocks(self.conn)))
        job = FactsJob(self.conn, provider=CountingFacts(), extra=None, settings=FactsSettings(), now=DEMO_NOW + dt.timedelta(days=10))
        order, never = job.plan(eligible_stocks(self.conn), repo.facts_rows(self.conn), [], {})
        self.assertEqual((order, never), ([], 0))
        job.now = DEMO_NOW + dt.timedelta(days=31)
        order, _ = job.plan(eligible_stocks(self.conn), repo.facts_rows(self.conn), [], {})
        self.assertEqual(len(order), len(eligible_stocks(self.conn)))

    def test_signal_stand_is_written_encrypted_and_published_with_the_site(self):
        key, descriptor = __import__("traktien.jobs.state", fromlist=["load_or_create_key"]).load_or_create_key(self.dir, "Test-Passphrase-123", allow_new=True)
        notes = _facts_and_signals(self.conn, self.dir, key, self.pipeline, mode="demo", run_id=self.run_id, new_snapshot=True, now=DEMO_NOW)
        self.assertTrue(any(n.startswith("Kennzahlen:") for n in notes), notes)
        self.assertTrue(any(n.startswith("Signal-Stand") for n in notes), notes)
        stands = repo.signal_stands(self.conn)
        self.assertEqual(len(stands), 1)
        stand = stands[0]
        build_status_file(self.conn, self.dir, "demo", self.pipeline, last_run_id=self.run_id, now=DEMO_NOW)
        app = Path(tempfile.mkdtemp(prefix="app-"))
        self.addCleanup(shutil.rmtree, app, True)
        (app / "index.html").write_text("<!doctype html>", encoding="utf-8")
        site = self.dir / "site"
        assemble_site(app_dist=app, state_dir=self.dir, out_dir=site, crypto_descriptor=descriptor, keep=3)
        status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["signale"]["id"], stand["id"])
        root = site / "data" / "signale" / stand["id"]
        with self.assertRaises(Exception):
            crypto.unpack((root / "signale.bin").read_bytes(), None, f"signale/{stand['id']}/signale.bin")
        main = json.loads(crypto.unpack((root / "signale.bin").read_bytes(), key, f"signale/{stand['id']}/signale.bin"))
        self.assertEqual(main["schema"], "tr-signale/1")
        self.assertEqual(len(main["isin"]), main["anzahl"]["aktien"])
        for column in ("kurz", "kurz_ampel", "lang", "lang_ampel", "potenzial", "analysten", "handelbar", "gesamt", "gesamt_stufe", "gesamt_steigt_20"):
            self.assertEqual(len(main[column]), len(main["isin"]), column)
        # Gesamtwertung (ab signale-v2): Teile, Steig-Konstanz je Zeitraum, eigene Trefferquote, Liste
        self.assertEqual(set(main["gesamt_teile"]), {"konstanz", "kursziel", "kurzfristig", "qualitaet"})
        self.assertEqual(main["regeln"]["konstanz_zeitraeume"], [30, 60, 90])
        self.assertEqual(main["kalibrierung_konstanz"]["horizonte"], [20, 60])
        for feature in ("steig_30", "tage_30", "steig_60", "tage_60", "steig_90", "tage_90", "r_30k"):
            self.assertEqual(len(main["merkmale"][feature]), len(main["isin"]), feature)
        ranked = main["listen"]["gesamt"]
        self.assertTrue(ranked, "Liste nach Gesamtwertung")
        totals = [main["gesamt"][k] for k in ranked]
        self.assertEqual(totals, sorted(totals, reverse=True))
        self.assertTrue(set(main["gesamt_stufe"]) <= {"stark", "mittel", "schwach", "ohne"})
        self.assertTrue(set(main["kurz_ampel"]) <= {"gruen", "gelb", "rot", "grau"})
        self.assertEqual(main["kalibrierung"]["faelle_gesamt"], sum(main["kalibrierung"]["faelle"]))
        self.assertIn("ampel_kurz", main["regeln"])
        # Liste „Beides stark“: grün/grün zuerst
        first = main["listen"]["beide"][0]
        if main["anzahl"]["beide_gruen"]:
            self.assertEqual((main["kurz_ampel"][first], main["lang_ampel"][first]), ("gruen", "gruen"))
        isin = main["isin"][first]
        detail = json.loads(crypto.unpack((root / "details" / f"{isin}.bin").read_bytes(), key, f"signale/{stand['id']}/details/{isin}.bin"))
        self.assertEqual(detail["isin"], isin)
        self.assertEqual({c["horizont"] for c in detail["komponenten"]}, {"kurz", "lang"})
        self.assertEqual([p["tage"] for p in detail["konstanz"]], [30, 60, 90])
        self.assertEqual(detail["gesamt"], main["gesamt"][first])
        self.assertEqual(status["signale"]["gesamt_stark"], main["anzahl"]["gesamt"]["stark"])
        self.assertEqual(len(detail["verlauf"]["d"]), len(detail["verlauf"]["c"]))
        self.assertGreater(len(detail["verlauf"]["d"]), 60)
        # Kein Geheimnis in den veröffentlichten Signal-Dateien
        for path in root.rglob("*.bin"):
            self.assertNotIn(b"Test-Passphrase-123", path.read_bytes())

    def test_no_new_stand_without_changes(self):
        from traktien.config import PipelineConfig

        raw = dict(self.pipeline.raw)
        raw["kennzahlen"] = dict(raw.get("kennzahlen") or {}, zusatz_max_sekunden=0)
        pipeline = PipelineConfig(raw)
        _facts_and_signals(self.conn, self.dir, None, pipeline, mode="demo", run_id=self.run_id, new_snapshot=True, now=DEMO_NOW)
        notes = _facts_and_signals(self.conn, self.dir, None, pipeline, mode="demo", run_id=self.run_id, new_snapshot=False, now=DEMO_NOW + dt.timedelta(minutes=5))
        self.assertIn("Signale unverändert (keine neuen Kennzahlen, kein neuer Datenstand)", notes)
        self.assertEqual(len(repo.signal_stands(self.conn)), 1)
        # Stand mit älteren Rechenregeln (signale-v1): neuer Stand ohne neue Kennzahlen
        stand = repo.signal_stands(self.conn, 1)[0]
        summary = json.loads(stand["summary_json"]) | {"version": "signale-v1"}
        self.conn.execute("UPDATE signal_stand SET summary_json = ? WHERE id = ?", (json.dumps(summary), stand["id"]))
        notes = _facts_and_signals(self.conn, self.dir, None, pipeline, mode="demo", run_id=self.run_id, new_snapshot=False, now=DEMO_NOW + dt.timedelta(minutes=10))
        self.assertEqual(len(repo.signal_stands(self.conn)), 2, notes)

    def test_signals_job_without_published_snapshot_does_nothing(self):
        empty = connect(self.dir / "leer.sqlite")
        self.addCleanup(empty.close)
        self.assertIsNone(SignalsJob(empty, self.dir, None, self.table, now=DEMO_NOW, data_mode="demo").run())


if __name__ == "__main__":
    unittest.main()
