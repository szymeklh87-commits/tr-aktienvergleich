"""T37, T41–T47, T52, T55, T56, T59, T60: täglicher Lauf, Wiederanlauf, Veröffentlichung.

Alle Läufe verwenden die DEMO-Quelle mit synthetischen Testaktien (keine echten Kurse).
"""

from __future__ import annotations

import base64
import dataclasses
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from traktien.config import CANONICAL_WEIGHTS, load_method_config, load_pipeline_config
from traktien.jobs.cutoff import determine_cutoff
from traktien.jobs.daily import EXIT_LOCKED, EXIT_OK, EXIT_RETRY, DailyRun, RunOptions
from traktien.jobs.summary import report_lines
from traktien.jobs.sources import DemoUniverseSource, demo_sources
from traktien.jobs.state import load_or_create_key, pack_database, unpack_database
from traktien.analytics.codes import WindowWarning
from traktien.providers.base import NoDataError, ProviderError, ProviderThrottled
from traktien.providers.demo import DemoVenueSource, demo_venue_offset_isin
from traktien.providers.exchanges import load_exchange_table
from traktien.publish.site import assemble_site
from traktien.store import repo
from traktien.store.db import connect
from traktien.util import crypto

APP_STUB = None


def app_stub() -> Path:
    global APP_STUB
    if APP_STUB is None:
        APP_STUB = Path(tempfile.mkdtemp(prefix="app-stub-"))
        (APP_STUB / "index.html").write_text("<!doctype html><title>Stub</title>", encoding="utf-8")
    return APP_STUB


def is_venue_symbol(symbol: str) -> bool:
    """DEMO-Notierungen am zweiten Börsenplatz (Frankfurt, „.F“) – Abrufe des Börsenplatz-Abgleichs."""
    return symbol.endswith(".F")


class ThrottlingProvider:
    """Wrapper um den DEMO-Anbieter: drosselt nach ``limit`` Abrufen dauerhaft (zählt nur Referenzkurse)."""

    def __init__(self, inner, limit: int) -> None:
        self.inner = inner
        self.name = inner.name
        self.limit = limit
        self.calls = 0

    def fetch_history(self, symbol, start, end, *, session_final=None):
        if is_venue_symbol(symbol):
            return self.inner.fetch_history(symbol, start, end, session_final=session_final)
        self.calls += 1
        if self.calls > self.limit:
            raise ProviderThrottled("Testdrosselung")
        return self.inner.fetch_history(symbol, start, end, session_final=session_final)


def without_days(history, keep: np.ndarray):
    """Kopie einer PriceHistory nur mit den Tagen, für die ``keep`` wahr ist."""
    n = len(history.days)
    changes = {}
    for f in dataclasses.fields(history):
        value = getattr(history, f.name)
        if isinstance(value, np.ndarray) and len(value) == n:
            changes[f.name] = value[keep]
        elif isinstance(value, list) and len(value) == n and f.name == "bar_times_utc":
            changes[f.name] = [v for v, k in zip(value, keep) if k]
    return dataclasses.replace(history, **changes)


class MissingCutoffProvider:
    """Wrapper: für Symbole mit ``suffix`` fehlt der Kurs am Tag ``day`` (wie Yahoo mit leerem Schlusskurs)."""

    def __init__(self, inner, suffix: str, day: int | None) -> None:
        self.inner = inner
        self.name = inner.name
        self.suffix = suffix
        self.day = day
        self.calls: list[str] = []

    def fetch_history(self, symbol, start, end, *, session_final=None):
        if not is_venue_symbol(symbol):
            self.calls.append(symbol)
        history = self.inner.fetch_history(symbol, start, end, session_final=session_final)
        if self.day is None or not symbol.endswith(self.suffix):
            return history
        return without_days(history, history.days != self.day)


class FailingProvider:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.name = inner.name

    def fetch_history(self, symbol, start, end, *, session_final=None):
        raise ProviderError("Testausfall")


class VenueFaultProvider:
    """Wrapper: zweiter Börsenplatz ohne Kurse für ``missing`` und Drosselung ab ``throttle``."""

    def __init__(self, inner, *, missing: set[str], throttle: str | None) -> None:
        self.inner = inner
        self.name = inner.name
        self.missing = missing
        self.throttle = throttle
        self.throttled = False
        self.venue_calls: list[str] = []

    def fetch_history(self, symbol, start, end, *, session_final=None):
        if symbol.endswith(".F"):
            self.venue_calls.append(symbol)
            if symbol == self.throttle or self.throttled:
                self.throttled = True
                raise ProviderThrottled("Testdrosselung")
            if symbol in self.missing:
                raise NoDataError(f"{symbol}: keine Daten")
        return self.inner.fetch_history(symbol, start, end, session_final=session_final)


class CountingVenueSource:
    def __init__(self, inner, *, without: set[str] = frozenset()) -> None:
        self.inner = inner
        self.without = without
        self.asked: list[str] = []

    def lookup(self, isins, budget_s):
        self.asked += list(isins)
        found = self.inner.lookup(isins, budget_s)
        return {isin: ([c for c in found[isin] if c.exchange_key != "XFRA"] if isin in self.without else found[isin]) for isin in found}


class PipelineTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="pipeline-"))
        self.method = load_method_config()
        self.pipeline = load_pipeline_config()
        self.table = load_exchange_table()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def open(self, path):
        conn = connect(path)
        self.addCleanup(conn.close)
        return conn

    def run_once(self, sources=None, key=None, **options):
        sources = sources or demo_sources()
        conn = self.open(self.dir / "state.sqlite")
        outcome = DailyRun(conn, self.dir, sources, self.method, self.pipeline, self.table, key, RunOptions(**options)).execute()
        return outcome, conn

    def published(self, conn):
        return repo.published_snapshots(conn, "demo")


class DailyRunTests(PipelineTestCase):
    def test_T41_T60_headless_run_publishes_flagged_demo_snapshot(self):
        outcome, conn = self.run_once()
        self.assertEqual(outcome.exit_code, EXIT_OK, outcome.message)
        self.assertEqual(outcome.status, "veroeffentlicht")
        rows = self.published(conn)
        self.assertEqual(len(rows), 1)
        snapshot_dir = self.dir / "snapshots" / rows[0]["id"]
        manifest = json.loads(crypto.unpack((snapshot_dir / "manifest.bin").read_bytes(), None, f"snapshots/{rows[0]['id']}/manifest.bin"))
        self.assertEqual(manifest["data_mode"], "demo")
        self.assertTrue(all(c["passed"] for c in manifest["checks"]))
        self.assertEqual(manifest["flags"]["model_validated"], False)
        self.assertEqual(manifest["flags"]["forecast_eligible"], False)
        status = json.loads((self.dir / "site_meta" / "status.json").read_text())
        self.assertEqual(status["app_mode"], "demo")
        self.assertEqual(status["latest_snapshot_id"], rows[0]["id"])

    def test_idempotent_rerun_creates_no_second_snapshot(self):
        first, conn = self.run_once()
        second, conn = self.run_once()
        self.assertEqual(second.status, "keine_neuen_daten")
        self.assertEqual(len(self.published(conn)), 1)

    def test_T42_parallel_trigger_does_not_start_second_run(self):
        conn = self.open(self.dir / "state.sqlite")
        repo.acquire_lock(conn, "taeglicher-lauf", "fremder-lauf")
        outcome, _ = self.run_once()
        self.assertEqual(outcome.exit_code, EXIT_LOCKED)
        self.assertEqual(self.published(conn), [])

    def test_T42_orphaned_lock_from_restored_backup_is_released_and_logged(self):
        conn = self.open(self.dir / "state.sqlite")
        repo.create_run(conn, "alter-lauf", trigger="zeitplan", planned_start=None, attempt=1, versions=self.versions(), data_mode="demo")
        repo.acquire_lock(conn, "taeglicher-lauf", "alter-lauf")
        cleared = repo.clear_orphaned_locks(conn, "Test: Lauf ohne Abschluss")
        self.assertEqual(cleared, ["alter-lauf"])
        self.assertIsNone(conn.execute("SELECT * FROM run_lock").fetchone())
        row = conn.execute("SELECT status FROM run WHERE id = 'alter-lauf'").fetchone()
        self.assertEqual(row["status"], "abgebrochen", "nie als erfolgreicher Lauf ausgewiesen")
        outcome, _ = self.run_once()
        self.assertEqual(outcome.exit_code, EXIT_OK, outcome.message)

    def versions(self):
        return {"method": "m", "metrics": "k", "ranking": "r", "frequency": "f", "software": "s"}

    def test_T43_T44_throttling_checkpoint_and_resume_same_cutoff(self):
        base = demo_sources()
        throttled = dataclasses.replace(base, prices=ThrottlingProvider(base.prices, limit=60))
        first, conn = self.run_once(sources=throttled)
        self.assertEqual(first.exit_code, EXIT_RETRY)
        self.assertEqual(first.status, "wartet_auf_provider")
        done = repo.fetched(conn, f"{first.cutoff_day}:demo")
        self.assertEqual(len(done), 60)
        resumed = ThrottlingProvider(base.prices, limit=10_000)
        second, conn = self.run_once(sources=dataclasses.replace(base, prices=resumed))
        self.assertEqual(second.status, "veroeffentlicht", second.message)
        self.assertEqual(second.cutoff_day, first.cutoff_day)
        self.assertLess(resumed.calls, 195 - 50)  # bereits geprüfte Historien werden nicht erneut geladen

    def test_missing_cutoff_close_is_fetched_again_in_next_attempt(self):
        """Fehlt bei einem Markt der Schlusskurs des Stichtags (Anbieter liefert ihn verspätet), holt
        der nächste Versuch genau diese Notierungen erneut und veröffentlicht dann vollständig."""
        base = demo_sources()
        codes = {e.calendar for e in self.table.exchanges.values() if e.key in ("US", "XETR", "XLON", "XHKG", "XASX", "XTKS")}
        D = determine_cutoff(codes, base.calendars, base.now).cutoff_day
        late = MissingCutoffProvider(base.prices, ".DE", D)
        first, conn = self.run_once(sources=dataclasses.replace(base, prices=late))
        self.assertEqual(first.exit_code, EXIT_RETRY, first.message)
        self.assertEqual(first.cutoff_day, D)
        self.assertIn("XETR", first.message)
        statuses = repo.fetched(conn, f"{D}:demo")
        retried = {lid for lid, s in statuses.items() if s in ("ohne_stichtag", "fehler")}
        self.assertTrue(any(s == "ohne_stichtag" for s in statuses.values()))
        examples = first.details["ohne_stichtag"]["XETR"]
        self.assertTrue(0 < len(examples) <= 3 and all(".DE (" in e for e in examples), examples)
        report = "\n".join(report_lines(conn, first))
        self.assertIn("Ohne Stichtagskurs, Beispiele je Börse: XETR ", report)
        self.assertIn("Stichtagskurse je Markt", report)

        complete = MissingCutoffProvider(base.prices, ".DE", None)
        second, conn = self.run_once(sources=dataclasses.replace(base, prices=complete))
        self.assertEqual(second.status, "veroeffentlicht", second.message)
        self.assertEqual(second.cutoff_day, D)
        # Nur die Notierungen ohne Stichtagskurs (und Einzelfehler) werden erneut abgerufen
        self.assertEqual(len(complete.calls), len(retried))
        self.assertTrue({s for s in late.calls if s.endswith(".DE")} <= set(complete.calls), complete.calls)
        self.assertLess(len(complete.calls), len(late.calls) // 2, "Notierungen mit Stichtagskurs werden nicht erneut geladen")
        # Alle XETR-Notierungen haben jetzt ihren Stichtagskurs; offen bleiben höchstens DEMO-Werte,
        # denen der Kurs auch in den Ausgangsdaten fehlt (z. B. ausgesetzter Handel)
        remaining = [s for s in repo.fetched(conn, f"{D}:demo").values() if s == "ohne_stichtag"]
        self.assertLessEqual(len(remaining), len([c for c in complete.calls if not c.endswith(".DE")]))

    def test_manual_runs_keep_waiting_only_last_scheduled_attempt_decides(self):
        """„Jetzt aktualisieren“ beliebig oft: Von Hand gestartete Läufe warten bei fehlenden Kursen nur
        weiter; über Teilstand oder Fehlschlag entscheidet allein der vierte geplante Versuch."""
        base = demo_sources()
        codes = {e.calendar for e in self.table.exchanges.values() if e.key in ("US", "XETR", "XLON", "XHKG", "XASX", "XTKS")}
        D = determine_cutoff(codes, base.calendars, base.now).cutoff_day
        late = dataclasses.replace(base, prices=MissingCutoffProvider(base.prices, ".DE", D))
        for _ in range(5):
            outcome, conn = self.run_once(sources=late, trigger="manuell")
            self.assertEqual((outcome.status, outcome.exit_code), ("wartet_auf_provider", EXIT_RETRY), outcome.message)
        for _ in range(3):
            outcome, conn = self.run_once(sources=late, trigger="zeitplan")
            self.assertEqual(outcome.status, "wartet_auf_provider", outcome.message)
        final, conn = self.run_once(sources=late, trigger="zeitplan")
        # XETR fehlt: 4 von 5 Börsen geliefert (80 % < 90 %) → kein Teilstand, Lauf fehlgeschlagen
        self.assertEqual(final.status, "fehlgeschlagen", final.message)
        self.assertIn("kein Teilstand", final.message)
        self.assertEqual(self.published(conn), [])

    def test_T44_provider_outage_keeps_last_good_result(self):
        first, conn = self.run_once()
        self.assertEqual(first.status, "veroeffentlicht")
        base = demo_sources()
        conn.execute("DELETE FROM fetch_checkpoint")
        outage = dataclasses.replace(base, prices=FailingProvider(base.prices))
        second, conn = self.run_once(sources=outage, force_publish=True)
        self.assertIn(second.status, ("keine_neuen_daten", "veroeffentlicht"))
        rows = self.published(conn)
        self.assertTrue((self.dir / "snapshots" / rows[-1]["id"] / "manifest.bin").exists())

    def test_T45_broken_universe_parse_keeps_previous_list(self):
        self.run_once()
        conn = self.open(self.dir / "state.sqlite")
        before = repo.latest_universe(conn, data_mode="demo")

        class Truncated(DemoUniverseSource):
            def fetch(self):
                meta, result = super().fetch()
                result.entries = result.entries[: len(result.entries) // 3]
                meta = dict(meta, id="Dkaputt000000000", sha256="0" * 64)
                return meta, result

        sources = dataclasses.replace(demo_sources(), universe=Truncated())
        outcome, conn = self.run_once(sources=sources, force_publish=True)
        held = repo.universe_by_id(conn, "Dkaputt000000000")
        self.assertEqual(held["status"], "zur_pruefung")
        self.assertEqual(repo.latest_universe(conn, data_mode="demo")["id"], before["id"])
        self.assertEqual(len(repo.universe_members(conn, before["id"])), 198)

    def test_T46_unfinished_files_are_never_visible(self):
        from traktien.publish import snapshot_writer

        original = snapshot_writer.SnapshotWriter.frequency_payload

        def broken(self):
            raise RuntimeError("Absturz mitten im Schreiben")

        snapshot_writer.SnapshotWriter.frequency_payload = broken
        try:
            outcome, conn = self.run_once()
        finally:
            snapshot_writer.SnapshotWriter.frequency_payload = original
        self.assertEqual(outcome.status, "fehlgeschlagen")
        self.assertEqual(self.published(conn), [])
        visible = [p for p in (self.dir / "snapshots").iterdir() if not p.name.startswith(".tmp-")] if (self.dir / "snapshots").exists() else []
        self.assertEqual(visible, [])

    def test_T47_overview_windows_series_and_frequency_agree(self):
        outcome, conn = self.run_once()
        sid = outcome.snapshot_id
        root = self.dir / "snapshots" / sid

        def load(rel):
            return json.loads(crypto.unpack((root / rel).read_bytes(), None, f"snapshots/{sid}/{rel}"))

        overview = load("overview.bin")
        frequency = load("frequency.bin")
        instruments = load("instruments.bin")
        for h in (1, 7, 30, 90):
            head = load(f"windows/{h}.bin")
            full = load(f"windows/{h}.full.bin")
            self.assertEqual(head["orders"]["v0"], full["orders"]["v0"][:50])
            for w in CANONICAL_WEIGHTS:
                self.assertEqual(head["orders"]["u"][str(w)], full["orders"]["u"][str(w)][:50])
                row = overview["u"][str(w)][h - 1]
                if full["orders"]["u"][str(w)]:
                    self.assertEqual(row["idx"], full["orders"]["u"][str(w)][0])
            winner = overview["winners"][h - 1]
            if full["orders"]["v0"]:
                self.assertEqual(winner["entries"][0]["idx"], full["orders"]["v0"][0])
                top = full["orders"]["v0"][0]
                series = load(f"series/{instruments['isin'][top]}.bin")
                columns = series["rank_columns"]
                ranks = np.frombuffer(base64.b64decode(series["ranks_b64"]), dtype="<u2").reshape(90, len(columns))
                self.assertEqual(int(ranks[h - 1, columns.index("v0")]), 1)
            # Ranking 2: Kopf = Anfang der vollständigen Liste, Sieger = Platz 1, gleiche Renditen wie Ranking 1
            self.assertEqual(head["orders"]["v0l"], full["orders"]["v0l"][:50])
            self.assertEqual(full["orders"]["v0l"], [i for i in full["orders"]["v0"] if instruments["turnover"]["liquid"][i]])
            self.assertEqual(full["counts"]["L"], len(full["orders"]["v0l"]))
            winner_l = overview["winners_l"][h - 1]
            if full["orders"]["v0l"]:
                top_l = full["orders"]["v0l"][0]
                self.assertEqual(winner_l["entries"][0]["idx"], top_l)
                pos = full["m"]["idx"].index(top_l)
                self.assertEqual(winner_l["entries"][0]["r"], full["m"]["r"][pos])
                self.assertEqual(winner_l["entries"][0]["p0"], full["m"]["p0"][pos])
                self.assertEqual(winner_l["entries"][0]["p1"], full["m"]["p1"][pos])
                series = load(f"series/{instruments['isin'][top_l]}.bin")
                columns = series["rank_columns"]
                ranks = np.frombuffer(base64.b64decode(series["ranks_b64"]), dtype="<u2").reshape(90, len(columns))
                self.assertEqual(int(ranks[h - 1, columns.index("v0l")]), 1)
            else:
                self.assertEqual(winner_l["entries"], [])
            occ = frequency["occ"]["v0"]
            first = [i for i, hh in enumerate(occ["h"]) if hh == h and occ["rank"][i] == 1]
            if full["orders"]["v0"]:
                self.assertEqual(occ["idx"][first[0]], full["orders"]["v0"][0])

    def load_snapshot(self, sid):
        root = self.dir / "snapshots" / sid
        return lambda rel: json.loads(crypto.unpack((root / rel).read_bytes(), None, f"snapshots/{sid}/{rel}"))

    def test_second_venue_flags_deviations_without_changing_returns_or_ranks(self):
        outcome, conn = self.run_once()
        self.assertEqual(outcome.status, "veroeffentlicht", outcome.message)
        load = self.load_snapshot(outcome.snapshot_id)
        manifest = load("manifest.bin")
        instruments = load("instruments.bin")
        check = next(c for c in manifest["checks"] if c["name"] == "boersenplatz_kennzeichen")
        self.assertTrue(check["passed"], check)
        venue = manifest["venue_check"]
        self.assertEqual(venue["version"], "boersenplatz-v1")
        self.assertGreater(venue["anzahl"]["kandidaten"], 0)
        self.assertEqual(venue["anzahl"]["aktien"].get("geprueft"), venue["anzahl"]["kandidaten"])
        bit = 1 << WindowWarning.BOERSENPLATZ_ABWEICHUNG
        offset = instruments["isin"].index(demo_venue_offset_isin())
        impulse = next(i for i, name in enumerate(instruments["name"]) if "Impulstag" in name)
        self.assertIn(offset, instruments["venue"]["idx"], "Testaktie mit abweichenden Vergleichskursen gehört zu den ersten Plätzen")
        self.assertIn(impulse, instruments["venue"]["idx"])
        k = instruments["venue"]["idx"].index(impulse)
        self.assertTrue(instruments["venue"]["level_flag"][k], "Impulstag: Endkurs am zweiten Platz 37,5 % tiefer")
        self.assertEqual(instruments["venue"]["symbol"][k], "S194.F")
        candidates = set(instruments["venue"]["idx"])
        for h in (1, 10, 24, 25, 30, 90):
            full = load(f"windows/{h}.full.bin")
            head = load(f"windows/{h}.bin")
            xv = full["xv"]
            self.assertTrue(set(xv["idx"]) <= candidates)
            for key in ("status", "r", "dev", "d0", "d1", "p0", "p1"):
                self.assertEqual(len(xv[key]), len(xv["idx"]))
            for j, idx in enumerate(xv["idx"]):
                wf = full["m"]["wf"][full["m"]["idx"].index(idx)]
                self.assertEqual(bool(wf & bit), xv["status"][j] == "abweichung", (h, idx))
            for j, idx in enumerate(head["xv"]["idx"]):  # Kopfdatei: dieselben Werte
                self.assertEqual(head["xv"]["status"][j], xv["status"][xv["idx"].index(idx)])
            if offset in xv["idx"]:
                expected = "abweichung" if h >= 25 else "ok"
                self.assertEqual(xv["status"][xv["idx"].index(offset)], expected, h)
            if impulse in xv["idx"]:
                self.assertEqual(xv["status"][xv["idx"].index(impulse)], "abweichung")
            self.assertTrue(all(not (w & bit) for i, w in zip(full["m"]["idx"], full["m"]["wf"]) if i not in candidates))
        events = [r["message"] for r in conn.execute("SELECT message FROM run_event WHERE step = 'boersenplatz'")]
        self.assertTrue(any(m.startswith("Börsenplatz-Abgleich:") for m in events), events)
        self.assertTrue(any(line.startswith("Börsenplatz-Abgleich:") for line in report_lines(conn, outcome)))

        # Ohne Abgleich: identische Renditen und Reihenfolgen – der Abgleich ist nur ein Hinweis
        other = Path(tempfile.mkdtemp(prefix="pipeline-ohne-"))
        self.addCleanup(shutil.rmtree, other, True)
        conn2 = self.open(other / "state.sqlite")
        plain = DailyRun(conn2, other, dataclasses.replace(demo_sources(), venues=None), self.method, self.pipeline, self.table, None, RunOptions()).execute()
        root2 = other / "snapshots" / plain.snapshot_id
        load2 = lambda rel: json.loads(crypto.unpack((root2 / rel).read_bytes(), None, f"snapshots/{plain.snapshot_id}/{rel}"))
        self.assertEqual(load2("instruments.bin")["venue"]["idx"], [])
        self.assertIn("nicht eingerichtet", load2("manifest.bin")["venue_check"]["hinweis"])
        for h in (1, 30, 90):
            a, b = load(f"windows/{h}.full.bin"), load2(f"windows/{h}.full.bin")
            self.assertEqual(a["orders"], b["orders"])
            self.assertEqual(a["m"]["r"], b["m"]["r"])
            self.assertEqual([w & ~bit for w in a["m"]["wf"]], b["m"]["wf"])

    def test_second_venue_missing_failed_or_throttled_is_marked_and_choice_is_reused(self):
        sources = demo_sources()
        recorder = VenueFaultProvider(sources.prices, missing=set(), throttle=None)
        first, conn = self.run_once(sources=dataclasses.replace(sources, prices=recorder))
        instruments = self.load_snapshot(first.snapshot_id)("instruments.bin")
        checked = instruments["venue"]["idx"]
        self.assertGreaterEqual(len(checked), 6)
        by_symbol = {instruments["venue"]["symbol"][k]: instruments["isin"][i] for k, i in enumerate(checked)}
        isins = [by_symbol[symbol] for symbol in recorder.venue_calls]  # Abrufreihenfolge = beste Plätze zuerst
        self.assertEqual(len(isins), len(checked))
        symbols = {isin: symbol for symbol, isin in by_symbol.items()}
        # Zweiter Lauf: gespeicherte Wahl wird wiederverwendet; Rollen: [1] ohne Kurse, letzte gedrosselt
        source = CountingVenueSource(DemoVenueSource())
        provider = VenueFaultProvider(sources.prices, missing={symbols[isins[1]]}, throttle=symbols[isins[-1]])
        again = dataclasses.replace(sources, venues=source, prices=provider)
        conn.execute("UPDATE venue_listing SET checked_at = '2020-01-01T00:00:00Z' WHERE isin = ?", (isins[0],))
        conn.execute("DELETE FROM venue_listing WHERE isin = ?", (isins[2],))
        source.without = {isins[2]}
        conn.execute("DELETE FROM snapshot_manifest")  # gleiche Eingaben sollen erneut veröffentlicht werden
        second = DailyRun(conn, self.dir, again, self.method, self.pipeline, self.table, None, RunOptions(force_publish=True)).execute()
        self.assertEqual(second.status, "veroeffentlicht", second.message)
        self.assertEqual(sorted(source.asked), sorted([isins[0], isins[2]]), "nur veraltete oder fehlende Wahl wird neu gesucht")
        venue = self.load_snapshot(second.snapshot_id)("instruments.bin")["venue"]
        status = {instruments["isin"][i]: st for i, st in zip(venue["idx"], venue["status"])}
        self.assertEqual(status[isins[2]], "kein_vergleichsplatz")
        self.assertEqual(status[isins[1]], "abruf_fehlgeschlagen")
        self.assertEqual(status[isins[-1]], "nicht_geprueft")
        self.assertEqual(status[isins[0]], "geprueft")
        self.assertEqual(provider.venue_calls[-1], symbols[isins[-1]])
        self.assertNotIn(symbols[isins[2]], provider.venue_calls, "ohne zweiten Börsenplatz kein Abruf")

    def test_second_venue_statuses_without_reuse(self):
        sources = demo_sources()
        probe, _ = self.run_once(sources=sources)
        instruments = self.load_snapshot(probe.snapshot_id)("instruments.bin")
        checked = instruments["venue"]["idx"]
        isins = [instruments["isin"][i] for i in checked]
        symbols = {isin: instruments["venue"]["symbol"][k] for k, isin in enumerate(isins)}
        # Frischer Zustand: alle Fehlerarten in einem Lauf
        fresh = Path(tempfile.mkdtemp(prefix="pipeline-platz-"))
        self.addCleanup(shutil.rmtree, fresh, True)
        conn = self.open(fresh / "state.sqlite")
        order = sorted(checked, key=lambda i: instruments["isin"][i])  # Reihenfolge egal; Rollen festlegen
        without, missing = instruments["isin"][order[0]], instruments["isin"][order[1]]
        provider = VenueFaultProvider(sources.prices, missing={symbols[missing]}, throttle=None)
        source = CountingVenueSource(DemoVenueSource(), without={without})
        run = DailyRun(conn, fresh, dataclasses.replace(sources, venues=source, prices=provider), self.method, self.pipeline, self.table, None, RunOptions())
        outcome = run.execute()
        self.assertEqual(outcome.status, "veroeffentlicht", outcome.message)
        root = fresh / "snapshots" / outcome.snapshot_id
        load = lambda rel: json.loads(crypto.unpack((root / rel).read_bytes(), None, f"snapshots/{outcome.snapshot_id}/{rel}"))
        venue = load("instruments.bin")["venue"]
        status = dict(zip(venue["idx"], venue["status"]))
        self.assertEqual(status[order[0]], "kein_vergleichsplatz")
        self.assertEqual(status[order[1]], "abruf_fehlgeschlagen")
        manifest = load("manifest.bin")
        self.assertTrue(next(c for c in manifest["checks"] if c["name"] == "boersenplatz_kennzeichen")["passed"])
        for h in (5, 60):
            xv = load(f"windows/{h}.full.bin")["xv"]
            self.assertNotIn(order[0], xv["idx"])
            self.assertNotIn(order[1], xv["idx"])

        # Drosselung mitten im Abgleich: Rest „nicht geprüft“, Veröffentlichung trotzdem
        fresh2 = Path(tempfile.mkdtemp(prefix="pipeline-platz2-"))
        self.addCleanup(shutil.rmtree, fresh2, True)
        conn2 = self.open(fresh2 / "state.sqlite")
        throttling = VenueFaultProvider(sources.prices, missing=set(), throttle=symbols[isins[len(isins) // 2]])
        outcome2 = DailyRun(conn2, fresh2, dataclasses.replace(sources, prices=throttling), self.method, self.pipeline, self.table, None, RunOptions()).execute()
        self.assertEqual(outcome2.status, "veroeffentlicht", outcome2.message)
        root2 = fresh2 / "snapshots" / outcome2.snapshot_id
        manifest2 = json.loads(crypto.unpack((root2 / "manifest.bin").read_bytes(), None, f"snapshots/{outcome2.snapshot_id}/manifest.bin"))
        counts = manifest2["venue_check"]["anzahl"]["aktien"]
        self.assertGreater(counts.get("nicht_geprueft", 0), 0)
        self.assertIn("drosselt", manifest2["venue_check"]["hinweis"])
        warnings = [r["message"] for r in conn2.execute("SELECT message FROM run_event WHERE step = 'boersenplatz' AND level = 'WARN'")]
        self.assertTrue(warnings)

    def test_T37_ticker_change_keeps_name_isin_and_one_ranking_entry(self):
        first, conn = self.run_once()
        self.assertEqual(first.status, "veroeffentlicht", first.message)

        def load(sid, rel):
            return json.loads(crypto.unpack((self.dir / "snapshots" / sid / rel).read_bytes(), None, f"snapshots/{sid}/{rel}"))

        inst1 = load(first.snapshot_id, "instruments.bin")
        full1 = load(first.snapshot_id, "windows/30.full.bin")
        idx = full1["orders"]["v0"][0]
        isin, name, old_symbol, old_ticker = inst1["isin"][idx], inst1["name"][idx], inst1["symbol"][idx], inst1["ticker"][idx]
        new_symbol, new_ticker = f"N{old_symbol}", f"N{old_ticker}"

        base = demo_sources()

        class TickerChanged(type(base.identity)):
            def lookup(self, isins, budget_s):
                found = super().lookup(isins, budget_s)
                if isin in found:
                    found[isin] = [dataclasses.replace(c, provider_symbol=new_symbol, ticker=new_ticker) for c in found[isin]]
                return found

        prices = base.prices
        prices.instruments[new_symbol] = prices.instruments.pop(old_symbol)  # Anbieter führt die Aktie nur noch unter dem neuen Symbol
        conn.execute("UPDATE instrument SET identity_checked_at = '2000-01-01T00:00:00Z' WHERE isin = ?", (isin,))
        second, conn = self.run_once(sources=dataclasses.replace(base, identity=TickerChanged(), prices=prices), force_publish=True)
        self.assertEqual(second.status, "veroeffentlicht", second.message)
        self.assertNotEqual(second.snapshot_id, first.snapshot_id)

        inst2 = load(second.snapshot_id, "instruments.bin")
        self.assertEqual(inst2["isin"].count(isin), 1, "eine ISIN, ein Eintrag")
        idx2 = inst2["isin"].index(isin)
        self.assertEqual(inst2["name"][idx2], name, "Name bleibt beim Tickerwechsel erhalten")
        self.assertEqual((inst2["symbol"][idx2], inst2["ticker"][idx2]), (new_symbol, new_ticker))
        self.assertIn(old_ticker, inst2["aliases"][idx2], "alter Ticker bleibt suchbar")
        full2 = load(second.snapshot_id, "windows/30.full.bin")
        self.assertEqual(full2["orders"]["v0"].count(idx2), 1)
        pos1 = full1["m"]["idx"].index(idx)
        pos2 = full2["m"]["idx"].index(idx2)
        self.assertEqual(full2["m"]["r"][pos2], full1["m"]["r"][pos1], "dieselbe Kursreihe, dieselbe Rendite")
        self.assertEqual(full2["orders"]["v0"][0], idx2, "Rangplatz unverändert")

    def test_T59_site_without_snapshots_shows_setup_state(self):
        site = self.dir / "site"
        assemble_site(app_dist=app_stub(), state_dir=self.dir, out_dir=site, crypto_descriptor=crypto.crypto_descriptor(None))
        status = json.loads((site / "data" / "status.json").read_text())
        index = json.loads((site / "data" / "snapshots" / "index.json").read_text())
        self.assertIsNone(status["latest_snapshot_id"])
        self.assertEqual(index["snapshots"], [])


class SecurityAndBackupTests(PipelineTestCase):
    def test_T52_no_secrets_in_published_files_state_or_logs(self):
        secret = "Sehr-Geheime-Passphrase-123"
        os.environ["OPENFIGI_API_KEY"] = "figi-key-should-not-leak"
        try:
            key, descriptor = load_or_create_key(self.dir, secret, allow_new=True)
            outcome, conn = self.run_once(key=key)
            self.assertEqual(outcome.status, "veroeffentlicht")
            site = self.dir / "site"
            assemble_site(app_dist=app_stub(), state_dir=self.dir, out_dir=site, crypto_descriptor=descriptor)
            blob = pack_database(conn, self.dir, key).read_bytes()
            haystacks = [p.read_bytes() for p in site.rglob("*") if p.is_file()] + [blob]
            haystacks += [p.read_bytes() for p in (self.dir / "archives").iterdir()]
            events = "\n".join(r[0] for r in conn.execute("SELECT message FROM run_event")).encode()
            haystacks.append(events)
            for data in haystacks:
                self.assertNotIn(secret.encode(), data)
                self.assertNotIn(b"figi-key-should-not-leak", data)
            # Verschlüsselte Dateien sind ohne Schlüssel nicht lesbar
            manifest = next(site.rglob("manifest.bin"))
            with self.assertRaises(crypto.ContainerError):
                crypto.unpack(manifest.read_bytes(), None, "x")
        finally:
            del os.environ["OPENFIGI_API_KEY"]

    def test_T55_backup_restores_in_clean_environment(self):
        outcome, conn = self.run_once()
        key = crypto.derive_key("backup-test", crypto.new_salt(), 1000)
        blob = pack_database(conn, self.dir, key).read_bytes()
        clean = Path(tempfile.mkdtemp(prefix="restore-"))
        try:
            unpack_database(blob, key, clean / "state.sqlite")
            restored = self.open(clean / "state.sqlite")
            for table in ("instrument", "listing", "daily_bar", "snapshot_manifest", "run"):
                a = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                b = restored.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                self.assertEqual(a, b, table)
            with self.assertRaises(crypto.ContainerError):
                unpack_database(blob, crypto.derive_key("falsch", key.salt, 1000), clean / "x.sqlite")
        finally:
            shutil.rmtree(clean, ignore_errors=True)

    def test_status_names_next_possible_cutoff(self):
        outcome, conn = self.run_once()
        status = json.loads((self.dir / "site_meta" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["naechster_kursstand"]["datum"], "2026-10-13")
        self.assertEqual(status["naechster_kursstand"]["ab_utc"], "2026-10-13T21:00:00Z")
        self.assertIn("XNYS", status["naechster_kursstand"]["boersen"])

    def test_T56_status_exposes_last_check_for_heartbeat(self):
        outcome, conn = self.run_once()
        status = json.loads((self.dir / "site_meta" / "status.json").read_text())
        self.assertEqual(status["last_run"]["status"], "veroeffentlicht")
        self.assertIsNotNone(status["last_successful_check_utc"])
        self.assertEqual(status["heartbeat_max_age_hours"], 30)
        self.assertEqual(status["schedule"]["uhrzeit"], "06:00")

    def test_passphrase_mismatch_is_detected(self):
        load_or_create_key(self.dir, "eins", allow_new=True)
        from traktien.jobs.state import StateError

        with self.assertRaises(StateError):
            load_or_create_key(self.dir, "zwei", allow_new=True)


if __name__ == "__main__":
    unittest.main()
