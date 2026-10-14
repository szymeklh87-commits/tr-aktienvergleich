"""Zwischenstand (ab 1.8) im Ablauf: vorläufige Kurse, eigener Stand, Status, Website, GitHub-Ablauf.

Alle Läufe verwenden die DEMO-Quellen (synthetische Kurse; „jetzt“ = 13.10.2026, 12:30 Uhr Berlin: Tokio,
Hongkong und Sydney haben den 13.10. beendet, Xetra und London handeln, New York öffnet erst um 15:30 Uhr).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from traktien import cli
from traktien.analytics.codes import Status
from traktien.config import load_method_config, load_pipeline_config
from traktien.jobs.daily import DailyRun, RunOptions, build_status_file
from traktien.jobs.intraday import IntradayRun
from traktien.jobs.sources import demo_sources
from traktien.providers.base import QuoteBatchResult
from traktien.providers.demo import DEMO_INTRADAY_NOW
from traktien.providers.exchanges import load_exchange_table
from traktien.publish.site import assemble_site
from traktien.store import repo
from traktien.store.db import connect
from traktien.util import crypto
from traktien.util.timeutil import UTC, date_to_day

D13 = date_to_day(dt.date(2026, 10, 13))


def intraday_sources(now: dt.datetime = DEMO_INTRADAY_NOW):
    sources = demo_sources()
    sources.now = now
    sources.prices.quote_now = now
    return sources


class IntradayPipelineTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="zwischenstand-"))
        self.pipeline = load_pipeline_config()
        self.method = load_method_config()
        self.table = load_exchange_table()
        self.conn = connect(self.dir / "state.sqlite")
        self.addCleanup(self.conn.close)
        outcome = DailyRun(self.conn, self.dir, demo_sources(), self.method, self.pipeline, self.table, None, RunOptions()).execute()
        self.assertEqual(outcome.status, "veroeffentlicht", outcome.message)
        self.official_id = outcome.snapshot_id

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_intraday(self, now: dt.datetime = DEMO_INTRADAY_NOW, sources=None):
        sources = sources or intraday_sources(now)
        return IntradayRun(self.conn, self.dir, sources, self.method, self.pipeline, self.table, None, RunOptions(trigger="zwischenstand")).execute()

    def read(self, snapshot_id: str, name: str) -> dict:
        path = self.dir / "snapshots" / snapshot_id / name
        return json.loads(crypto.unpack(path.read_bytes(), None, f"snapshots/{snapshot_id}/{name}"))

    def test_intraday_stand_uses_provisional_prices_and_never_stores_them(self):
        bars_before = self.conn.execute("SELECT COUNT(*) FROM daily_bar").fetchone()[0]
        outcome = self.run_intraday()
        self.assertEqual(outcome.status, "veroeffentlicht", outcome.message)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM daily_bar").fetchone()[0], bars_before, "vorläufige Kurse nie in der Kurshistorie")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM daily_bar WHERE session_day = ?", (D13,)).fetchone()[0], 0)
        row = repo.latest_intraday(self.conn, "demo")
        self.assertEqual((row["id"], int(row["cutoff_day"])), (outcome.snapshot_id, D13))
        self.assertTrue(row["id"].startswith("2026-10-13_z"))

        manifest = self.read(row["id"], "manifest.bin")
        self.assertEqual(manifest["art"], "zwischenstand")
        info = manifest["zwischenstand"]
        self.assertEqual(info["boersen_ohne_kurs"], ["XNYS"], "New York hat noch nicht geöffnet")
        self.assertEqual(set(info["boersen_mit_kurs"]), {"XASX", "XETR", "XHKG", "XLON", "XTKS"})
        self.assertIn("XNYS", info["oeffnung_utc"])
        self.assertGreater(info["davon_sitzung_beendet"], 0, "Asien hat den Tag beendet")
        self.assertLess(info["davon_sitzung_beendet"], info["aktien_mit_kurs"], "Europa handelt noch")
        self.assertIsNone(manifest["rotation"])
        self.assertTrue(manifest["provider"]["intraday"])

        instruments = self.read(row["id"], "instruments.bin")
        exchange = instruments["exchange_key"]
        us = next(i for i, key in enumerate(exchange) if key == "US" and instruments["level_status"][i] != Status.KEINE_KURSDATEN and instruments["has_series"][i])
        eu = next(i for i, key in enumerate(exchange) if key == "XETR" and instruments["has_series"][i] and instruments["last_close_day"][i] == D13)
        self.assertEqual(instruments["level_status"][us], int(Status.KURS_AM_STICHTAG_FEHLT), "US-Aktien ohne Kurs von heute fehlen in den Ranglisten")
        series = self.read(row["id"], f"series/{instruments['isin'][eu]}.bin")
        self.assertEqual(series["provisional"]["day"], D13)
        self.assertFalse(series["provisional"]["session_closed"])
        self.assertEqual(series["d"][-1], D13)

        status = json.loads((self.dir / "site_meta" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["latest_snapshot_id"], row["id"])
        self.assertEqual(status["latest_official_snapshot_id"], self.official_id)
        self.assertEqual(status["zwischenstand"]["snapshot_id"], row["id"])
        self.assertEqual(status["zwischenstand"]["stichtag"], "2026-10-13")
        self.assertEqual(status["last_run"]["trigger"], "zwischenstand")
        index = json.loads((self.dir / "site_meta" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual([s["snapshot_id"] for s in index["snapshots"]][:2], [row["id"], self.official_id])
        self.assertEqual(index["snapshots"][0]["art"], "zwischenstand")
        self.assertEqual(repo.attempts_for_cutoff(self.conn, D13, "demo"), 0, "Zwischenstände zählen nicht als Versuch des täglichen Laufs")

        app = Path(tempfile.mkdtemp(prefix="app-"))
        self.addCleanup(shutil.rmtree, app, True)
        (app / "index.html").write_text("<!doctype html>", encoding="utf-8")
        site = self.dir / "site"
        assemble_site(app_dist=app, state_dir=self.dir, out_dir=site, crypto_descriptor=crypto.crypto_descriptor(None), keep=5)
        self.assertTrue((site / "data" / "snapshots" / row["id"] / "manifest.bin").exists())
        self.assertTrue((site / "data" / "snapshots" / self.official_id / "manifest.bin").exists(), "offizieller Stand bleibt wählbar")
        with contextlib.redirect_stdout(io.StringIO()) as report:
            self.assertEqual(cli.main(["verify-site", "--site", str(site)]), 0)
        self.assertTrue(json.loads(report.getvalue())["ok"])

    def test_new_intraday_replaces_the_previous_one(self):
        first = self.run_intraday()
        later = self.run_intraday(DEMO_INTRADAY_NOW + dt.timedelta(hours=1, minutes=10))
        self.assertEqual(later.status, "veroeffentlicht", later.message)
        self.assertNotEqual(first.snapshot_id, later.snapshot_id)
        rows = self.conn.execute("SELECT id FROM zwischenstand").fetchall()
        self.assertEqual([r["id"] for r in rows], [later.snapshot_id], "immer nur ein Zwischenstand")
        self.assertFalse((self.dir / "archives" / f"site-{first.snapshot_id}.tar").exists())
        self.assertTrue((self.dir / "archives" / f"site-{later.snapshot_id}.tar").exists())

    def test_official_stand_of_the_same_day_replaces_the_intraday_in_the_app(self):
        outcome = self.run_intraday()
        summary = {"snapshot_id": "2026-10-13_aaaaaaaa", "cutoff_session_date": "2026-10-13", "completeness": "vollstaendig"}
        repo.insert_snapshot(
            self.conn, id="2026-10-13_aaaaaaaa", idempotency_key="test-offiziell-13", cutoff_day=D13, computed_at="2026-10-14T05:00:00Z",
            published_at="2026-10-14T05:00:00Z", completeness="vollstaendig", data_mode="demo", universe_id="u", run_id="r",
            supersedes=None, summary_json=json.dumps(summary), site_archive="site-2026-10-13_aaaaaaaa.tar", evidence_archive=None, status="veroeffentlicht",
        )
        self.assertIsNone(repo.current_intraday(self.conn, "demo"))
        status = build_status_file(self.conn, self.dir, "demo", self.pipeline, last_run_id=None, now=DEMO_INTRADAY_NOW + dt.timedelta(days=1))
        self.assertNotIn("zwischenstand", status)
        self.assertEqual(status["latest_snapshot_id"], "2026-10-13_aaaaaaaa")
        index = json.loads((self.dir / "site_meta" / "index.json").read_text(encoding="utf-8"))
        self.assertNotIn(outcome.snapshot_id, [s["snapshot_id"] for s in index["snapshots"]])

    def test_before_any_market_opened_there_is_nothing_new(self):
        outcome = self.run_intraday(dt.datetime(2026, 10, 12, 22, 30, tzinfo=UTC))  # 00:30 Uhr Berlin, vor Sydney und Tokio
        self.assertEqual(outcome.status, "keine_neuen_daten", outcome.message)
        self.assertIn("offizielle Stand ist aktuell", outcome.message)
        self.assertIsNone(repo.latest_intraday(self.conn, "demo"))

    def test_too_few_current_prices_publish_nothing(self):
        sources = intraday_sources()
        full = sources.prices.fetch_quotes

        def few(symbols, *, budget_s=900.0, progress=None):
            result = full(symbols, budget_s=budget_s)
            keep = dict(list(result.quotes.items())[:5])
            return QuoteBatchResult(quotes=keep, missing={}, requests=result.requests, endpoint="demo")

        sources.prices.fetch_quotes = few
        outcome = self.run_intraday(sources=sources)
        self.assertEqual(outcome.status, "keine_neuen_daten", outcome.message)
        self.assertIn("Noch zu wenige aktuelle Kurse", outcome.message)

    def test_cli_demo_with_intraday_builds_both_stands(self):
        site = self.dir / "demo-site"
        state = self.dir / "demo-state"
        with contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["demo", "--fresh", "--zwischenstand", "--state-dir", str(state), "--site", str(site), "--app-dist", str(self._stub())])
        self.assertEqual(code, 0)
        status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
        self.assertTrue(status["zwischenstand"]["snapshot_id"].startswith("2026-10-13_z"))
        self.assertEqual(len(status["retained_snapshot_ids"]), 2)

    def _stub(self) -> Path:
        stub = self.dir / "stub"
        stub.mkdir(exist_ok=True)
        (stub / "index.html").write_text("<!doctype html>", encoding="utf-8")
        return stub


class IntradayCiTests(unittest.TestCase):
    """``python -m traktien ci --zwischenstand`` gegen die nachgebildete GitHub-API (wie test_ci_flow)."""

    def setUp(self):
        from tests.integration.test_ci_flow import PASSPHRASE, TOKEN, FakeGitHub
        from traktien.jobs.state import GitHubReleaseStore
        from traktien.providers.http import HttpClient

        self.passphrase, self.token = PASSPHRASE, TOKEN
        self.tmp = Path(tempfile.mkdtemp(prefix="ci-zwischenstand-"))
        self.stub = self.tmp / "app"
        self.stub.mkdir()
        (self.stub / "index.html").write_text("<!doctype html>", encoding="utf-8")
        self.github = FakeGitHub("simon/tr-aktienvergleich")
        self.store = GitHubReleaseStore(repo="simon/tr-aktienvergleich", token=TOKEN, http=HttpClient(session=self.github, sleep=lambda _s: None))
        env = mock.patch.dict(os.environ, {"DATA_PASSPHRASE": PASSPHRASE, "GITHUB_TOKEN": TOKEN, "GITHUB_REPOSITORY": "simon/tr-aktienvergleich", "GITHUB_EVENT_NAME": "workflow_dispatch"})
        env.start()
        self.addCleanup(env.stop)
        self.now = [demo_sources().now]

        def sources(*args, **kwargs):
            s = demo_sources()
            s.now = self.now[0]
            s.prices.quote_now = self.now[0]
            return s

        for patch in (
            mock.patch.object(GitHubReleaseStore, "from_env", classmethod(lambda cls, tag="datenstand": self.store)),
            mock.patch.object(cli, "production_sources", sources),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_ci(self, name: str, *extra: str) -> tuple[int, dict, Path, str]:
        output = self.tmp / f"{name}.out"
        printed = io.StringIO()
        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}), contextlib.redirect_stdout(printed):
            code = cli.main(["ci", "--state-dir", str(self.tmp / name / "state"), "--site", str(self.tmp / name / "site"), "--app-dist", str(self.stub), *extra])
        values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines()) if output.exists() else {}
        return code, values, self.tmp / name / "site", printed.getvalue()

    def test_intraday_on_github_publishes_and_keeps_only_the_newest_archive(self):
        code, out, _, _ = self.run_ci("offiziell")
        self.assertEqual((code, out.get("status")), (0, "veroeffentlicht"))
        self.now[0] = DEMO_INTRADAY_NOW
        code, out, site, printed = self.run_ci("z1", "--zwischenstand")
        self.assertEqual((code, out.get("deploy"), out.get("status")), (0, "true", "veroeffentlicht"), printed)
        self.assertIn("::notice title=Zwischenstand::Stichtag 2026-10-13", printed)
        self.assertIn("ohne Kurs: XNYS", printed)
        self.assertNotIn(self.passphrase, printed)
        status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
        first = status["zwischenstand"]["snapshot_id"]
        self.assertIn(f"site-{first}.tar", self.github.names())
        self.assertTrue((site / "data" / "snapshots" / first / "manifest.bin").exists())
        self.now[0] = DEMO_INTRADAY_NOW + dt.timedelta(hours=2)
        code, out, site, printed = self.run_ci("z2", "--zwischenstand")
        self.assertEqual(code, 0, printed)
        second = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))["zwischenstand"]["snapshot_id"]
        self.assertNotEqual(first, second)
        names = self.github.names()
        self.assertIn(f"site-{second}.tar", names)
        self.assertNotIn(f"site-{first}.tar", names, "ältere Zwischenstände werden aus dem Release entfernt")

    def test_one_tap_update_computes_the_missing_official_stand_first_and_requests_facts(self):
        """Ab 1.9.1 ist „Zwischenstand“ die Voreinstellung eines Laufs von Hand: Fehlt der offizielle Stand des
        letzten Börsentags, entsteht er zuerst – dann meldet der Lauf ``kennzahlen=true`` (Kennzahlen-Job folgt)."""
        self.now[0] = dt.datetime(2026, 10, 12, 6, 0, tzinfo=dt.timezone.utc)  # Montag früh: Stichtag Freitag 09.10.
        code, out, _, printed = self.run_ci("frueh")
        self.assertEqual((code, out.get("status")), (0, "veroeffentlicht"), printed)
        self.now[0] = DEMO_INTRADAY_NOW  # Dienstag 12:30 Uhr: offizieller Stand 12.10. fehlt noch
        code, out, site, printed = self.run_ci("ein-tipp", "--zwischenstand")
        self.assertEqual(code, 0, printed)
        self.assertIn("Zuerst der tägliche Lauf", printed)
        self.assertEqual(out.get("kennzahlen"), "true", "neuer offizieller Stand → Kennzahlen und Signale danach")
        status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["last_price_session"], "2026-10-12")
        self.assertEqual(status["zwischenstand"]["stichtag"], "2026-10-13")
        intraday = status["zwischenstand"]["snapshot_id"]
        # Kennzahlen-Job danach (wie im Workflow, mit DEMO-Kennzahlen statt Netz): der Zwischenstand bleibt auf der Website
        from traktien.providers.demo import DemoExtraSources, DemoFactsProvider

        def demo_facts(mode):
            facts = DemoFactsProvider()
            return facts, DemoExtraSources(facts)

        with mock.patch.object(cli, "_facts_sources", demo_facts):
            code, out, site, printed = self.run_ci("kennzahlen", "--kennzahlen")
        self.assertEqual(code, 0, printed)
        status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["zwischenstand"]["snapshot_id"], intraday)
        self.assertEqual(status["latest_snapshot_id"], intraday)
        self.assertTrue((site / "data" / "snapshots" / intraday / "manifest.bin").exists())
        # Noch ein Tipp: offizieller Stand vorhanden → nur Zwischenstand, keine Kennzahlen
        self.now[0] = DEMO_INTRADAY_NOW + dt.timedelta(hours=1)
        code, out, _, printed = self.run_ci("zweiter-tipp", "--zwischenstand")
        self.assertEqual(code, 0, printed)
        self.assertNotIn("Zuerst der tägliche Lauf", printed)
        self.assertEqual(out.get("kennzahlen"), "false")

    def test_staged_update_publishes_the_leaders_first_and_then_all_stocks(self):
        """Gestaffelte Aktualisierung (ab 1.11): Stufe 1 holt nur die Kurse der Aktien, die sich im letzten Stand oben
        wiederholen, rechnet sofort und stellt den Stand bereit – ohne den Zustand zu sichern (der Job läuft parallel
        zu Stufe 2). Stufe 2 rechnet alle Aktien, sichert und ersetzt Stufe 1."""
        from traktien.config import PipelineConfig

        code, out, _, printed = self.run_ci("offiziell")
        self.assertEqual((code, out.get("status")), (0, "veroeffentlicht"), printed)
        released = self.github.names()
        database = self.github.data("state.sqlite.tra")
        raw = json.loads(json.dumps(load_pipeline_config().raw))
        raw.setdefault("zwischenstand", {})["stufe1_hoechstens"] = 40
        self.now[0] = DEMO_INTRADAY_NOW
        with mock.patch.object(cli, "load_pipeline_config", lambda *a, **k: PipelineConfig(raw)):
            code, out, site, printed = self.run_ci("stufe1", "--zwischenstand", "--stufe", "1")
        self.assertEqual((code, out.get("deploy"), out.get("status")), (0, "true", "veroeffentlicht"), printed)
        self.assertIn("::notice title=Stufe 1::Stichtag 2026-10-13", printed)
        self.assertIn("::notice title=Dauer Stufe 1::", printed)
        self.assertNotIn(self.passphrase, printed)
        self.assertEqual(self.github.names(), released, "Stufe 1 lädt nichts hoch")
        self.assertEqual(self.github.data("state.sqlite.tra"), database, "Stufe 1 sichert den Zustand nicht")
        status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
        first = status["zwischenstand"]
        self.assertEqual((first["stufe"]["nummer"], first["stufe"]["von"], first["stufe"]["aktien"]), (1, 2, 40))
        self.assertNotIn("reihenfolge", first["stufe"], "die Reihenfolge (ISINs) steht nicht im öffentlichen Status")
        self.assertLessEqual(first["aktien_mit_kurs"], 40)
        self.assertTrue((site / "data" / "snapshots" / first["snapshot_id"] / "manifest.bin").exists())
        # Stufe 2 (parallel gestartet, hier danach): alle Aktien, Zustand und Archiv gesichert
        code, out, site, printed = self.run_ci("stufe2", "--zwischenstand", "--gestaffelt")
        self.assertEqual((code, out.get("deploy"), out.get("status")), (0, "true", "veroeffentlicht"), printed)
        second = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))["zwischenstand"]
        self.assertEqual((second["stufe"]["nummer"], second["stufe"]["von"]), (2, 2))
        self.assertGreater(second["aktien_mit_kurs"], first["aktien_mit_kurs"])
        self.assertIn(f"site-{second['snapshot_id']}.tar", self.github.names())
        self.assertNotEqual(self.github.data("state.sqlite.tra"), database)

    def test_intraday_saves_in_a_background_process_and_waits_at_the_end(self):
        """Ab 1.12 (GitHub Actions): Sichern läuft als eigener Prozess weiter, während der Workflow die Website prüft
        und hochlädt; „sichern-warten“ am Ende des Jobs meldet Erfolg oder Fehler. Hier startet der Test den Prozess
        im selben Python (die nachgebildete GitHub-API gibt es nur hier)."""
        code, out, _, printed = self.run_ci("offiziell")
        self.assertEqual(code, 0, printed)
        self.now[0] = DEMO_INTRADAY_NOW
        spawned = {}

        def fake_spawn(state_dir, names, keep):
            spawned["args"] = (Path(state_dir), list(names), keep)

        with mock.patch.dict(os.environ, {"SICHERN_IM_HINTERGRUND": "true"}), mock.patch.object(cli, "_spawn_save", fake_spawn):
            code, out, site, printed = self.run_ci("z1", "--zwischenstand")
        self.assertEqual((code, out.get("deploy"), out.get("sichern")), (0, "true", "hintergrund"), printed)
        self.assertNotIn("auf Sichern warten", printed, "der Schritt wartet nicht mehr auf das Sichern")
        first = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))["zwischenstand"]["snapshot_id"]
        self.assertNotIn(f"site-{first}.tar", self.github.names(), "vor dem Sichern noch nicht im Release")
        state_dir, names, keep = spawned["args"]
        self.assertIn(f"site-{first}.tar", names)
        self.assertEqual(cli.main(["sichern", "--state-dir", str(state_dir), "--behalten", str(keep), "--archive", *names]), 0)
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.assertEqual(cli.main(["sichern-warten", "--state-dir", str(state_dir), "--timeout", "5"]), 0)
        self.assertIn("::notice title=Sichern::im Hintergrund", printed.getvalue())
        self.assertIn(f"site-{first}.tar", self.github.names())
        # Ohne Ergebnis meldet „sichern-warten“ einen Fehler (dann wird nicht bereitgestellt)
        (state_dir / cli.SAVE_RESULT).unlink()
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.assertEqual(cli.main(["sichern-warten", "--state-dir", str(state_dir), "--timeout", "1"]), cli.EXIT_FAILED)
        self.assertIn("::error::Sichern im Hintergrund ohne Ergebnis", printed.getvalue())

    def test_force_means_the_official_run_even_with_intraday_default(self):
        code, out, _, printed = self.run_ci("offiziell")
        self.assertEqual(code, 0, printed)
        self.now[0] = DEMO_INTRADAY_NOW
        code, out, site, printed = self.run_ci("erzwingen", "--zwischenstand", "--force")
        self.assertEqual(code, 0, printed)
        self.assertNotIn("::notice title=Zwischenstand::", printed, "„erzwingen“ rechnet den offiziellen Stand, keinen Zwischenstand")
        status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
        self.assertIsNone(status.get("zwischenstand"))


if __name__ == "__main__":
    unittest.main()
