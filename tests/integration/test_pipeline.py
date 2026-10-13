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
from traktien.providers.base import ListingCandidate, NoDataError, ProviderError, ProviderThrottled
from traktien.providers.demo import DemoVenueSource, build_demo_universe, demo_venue_offset_isin
from traktien.providers.exchanges import load_exchange_table
from traktien.publish.site import assemble_site
from traktien.store import repo
from traktien.store.db import connect
from traktien.util import crypto
from traktien.util.names import name_similarity

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
    """Wrapper um den DEMO-Anbieter: drosselt nach ``limit`` Abrufen dauerhaft. ``calls`` zählt die
    Tageskurse der Referenznotierungen, ``long_calls`` die Langabrufe der Umschichtungs-Regel (bis 3 Jahre)."""

    def __init__(self, inner, limit: int) -> None:
        self.inner = inner
        self.name = inner.name
        self.limit = limit
        self.calls = 0
        self.long_calls = 0

    def fetch_history(self, symbol, start, end, *, session_final=None):
        if is_venue_symbol(symbol):
            return self.inner.fetch_history(symbol, start, end, session_final=session_final)
        if end - start > 600:
            self.long_calls += 1
        else:
            self.calls += 1
        if self.calls + self.long_calls > self.limit:
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

    def __init__(self, inner, suffix: str | tuple[str, ...], day: int | None) -> None:
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
        self.assertEqual(throttled.prices.long_calls, 0, "bei Drosselung kein Langabruf im selben Lauf")
        events = [r["message"] for r in conn.execute("SELECT message FROM run_event WHERE step = 'umschichtung'")]
        self.assertTrue(any("Anbieter drosselt, Rest im nächsten Lauf" in m for m in events), events)
        resumed = ThrottlingProvider(base.prices, limit=10_000)
        second, conn = self.run_once(sources=dataclasses.replace(base, prices=resumed))
        self.assertEqual(second.status, "veroeffentlicht", second.message)
        self.assertEqual(second.cutoff_day, first.cutoff_day)
        self.assertLess(resumed.calls, 195 - 50)  # bereits geprüfte Historien werden nicht erneut geladen
        self.assertGreater(resumed.long_calls, 0)

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
        # XETR fehlt: 128 von 164 Aktien mit Stichtagskurs (78 % ≥ 75 %) → gekennzeichneter Teilstand
        self.assertEqual(final.status, "veroeffentlicht", final.message)
        rows = self.published(conn)
        self.assertEqual([r["completeness"] for r in rows], ["teilstand"])
        manifest = json.loads(crypto.unpack((self.dir / "snapshots" / rows[0]["id"] / "manifest.bin").read_bytes(), None, f"snapshots/{rows[0]['id']}/manifest.bin"))
        self.assertEqual(manifest["completeness"]["missing_markets"], ["XETR"])
        self.assertGreaterEqual(manifest["completeness"]["instrument_share"], 0.75)

    def test_last_scheduled_attempt_publishes_no_partial_snapshot_below_75_percent(self):
        base = demo_sources()
        codes = {e.calendar for e in self.table.exchanges.values() if e.key in ("US", "XETR", "XLON", "XHKG", "XASX", "XTKS")}
        D = determine_cutoff(codes, base.calendars, base.now).cutoff_day
        late = dataclasses.replace(base, prices=MissingCutoffProvider(base.prices, (".DE", ".L"), D))
        for _ in range(3):
            outcome, conn = self.run_once(sources=late, trigger="zeitplan")
            self.assertEqual(outcome.status, "wartet_auf_provider", outcome.message)
        final, conn = self.run_once(sources=late, trigger="zeitplan")
        # XETR und London fehlen: 97 von 164 Aktien (59 % < 75 %) → kein Teilstand, Lauf fehlgeschlagen
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
        self.assertEqual(venue["version"], "boersenplatz-v3")
        self.assertEqual((venue["schwankung_faktor"], venue["schwankung_sitzungen"], venue["schwelle_hoechstens"], venue["nur_mit_umsatz"]), (3.0, 20, 1.0, True))
        diag = venue["auswertung"]
        self.assertEqual(diag["feste_schwelle_auffaellig"], diag["davon_ohne_umsatz"] + diag["davon_in_schwankungsbreite"] + diag["davon_weiter_auffaellig"])
        self.assertLessEqual(diag["davon_weiter_auffaellig"], venue["anzahl"]["aktie_zeitraum"].get("abweichung", 0))
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

    def test_second_venue_errors_never_block_publication(self):
        """Der Abgleich ist nur ein Hinweis: Ein unerwarteter Fehler der Quelle oder ein nicht lesbarer
        Börsenkalender des zweiten Platzes verhindert die Veröffentlichung nicht und hinterlässt keine
        Kennzeichen (1.5.1)."""
        sources = demo_sources()
        bit = 1 << WindowWarning.BOERSENPLATZ_ABWEICHUNG

        class BrokenVenueSource:
            def lookup(self, isins, budget_s=None):
                raise RuntimeError("Quelle kaputt")

        outcome, conn = self.run_once(sources=dataclasses.replace(sources, venues=BrokenVenueSource()))
        self.assertEqual(outcome.status, "veroeffentlicht", outcome.message)
        load = self.load_snapshot(outcome.snapshot_id)
        manifest = load("manifest.bin")
        self.assertIn("Abgleich wegen eines Fehlers übersprungen (RuntimeError)", manifest["venue_check"]["hinweis"])
        self.assertTrue(manifest["venue_check"]["abgebrochen"])
        self.assertTrue(next(c for c in manifest["checks"] if c["name"] == "boersenplatz_kennzeichen")["passed"])
        self.assertEqual(load("instruments.bin")["venue"]["idx"], [])
        for h in (1, 30, 90):
            self.assertTrue(all(not (w & bit) for w in load(f"windows/{h}.full.bin")["m"]["wf"]), h)
        warnings = [r["message"] for r in conn.execute("SELECT message FROM run_event WHERE step = 'boersenplatz' AND level = 'WARN'")]
        self.assertTrue(any("Quelle kaputt" in m for m in warnings), warnings)

        class BrokenCalendar:
            """Börsenkalender, der für den zweiten Platz (DEMO: Frankfurt) nicht lesbar ist."""

            def __init__(self, inner):
                self.inner = inner

            def __getattr__(self, name):
                return getattr(self.inner, name)

            def sessions(self, code, start_day, end_day):
                if code == "XFRA":
                    raise ValueError("Kalender defekt")
                return self.inner.sessions(code, start_day, end_day)

        other = Path(tempfile.mkdtemp(prefix="pipeline-kalender-"))
        self.addCleanup(shutil.rmtree, other, True)
        conn2 = self.open(other / "state.sqlite")
        broken = dataclasses.replace(sources, calendars=BrokenCalendar(sources.calendars))
        second = DailyRun(conn2, other, broken, self.method, self.pipeline, self.table, None, RunOptions()).execute()
        self.assertEqual(second.status, "veroeffentlicht", second.message)
        root = other / "snapshots" / second.snapshot_id
        venue = json.loads(crypto.unpack((root / "instruments.bin").read_bytes(), None, f"snapshots/{second.snapshot_id}/instruments.bin"))["venue"]
        self.assertGreater(len(venue["idx"]), 0)
        self.assertEqual(set(venue["status"]), {"nicht_geprueft"})
        warnings = [r["message"] for r in conn2.execute("SELECT message FROM run_event WHERE step = 'boersenplatz' AND level = 'WARN'")]
        self.assertEqual(sum("Börsenkalender XFRA nicht lesbar" in m for m in warnings), 1, "eine Warnung je Kalender")

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


class GroupComparisonPipelineTests(PipelineTestCase):
    """Gruppenvergleich A/B (ab 1.4): Gruppe B in allen Dateien, Vergleichsmengen, Kalenderstarts."""

    def load_snapshot(self, sid):
        root = self.dir / "snapshots" / sid
        return lambda rel: json.loads(crypto.unpack((root / rel).read_bytes(), None, f"snapshots/{sid}/{rel}"))

    def test_group_b_in_windows_overview_frequency_and_series(self):
        from traktien.analytics.windows import expected_start_sessions  # noqa: F401  (Regel der Kalenderstarts)

        outcome, conn = self.run_once()
        self.assertEqual(outcome.status, "veroeffentlicht", outcome.message)
        load = self.load_snapshot(outcome.snapshot_id)
        manifest = load("manifest.bin")
        check = next(c for c in manifest["checks"] if c["name"] == "gruppe_b_eigene_vergleichsmenge")
        self.assertTrue(check["passed"], check)
        instruments = load("instruments.bin")
        liquid = instruments["turnover"]["liquid"]
        self.assertEqual(len(instruments["calendar"]), len(instruments["isin"]))
        overview = load("overview.bin")
        frequency = load("frequency.bin")
        self.assertEqual(set(frequency["starts"]), {c for c in instruments["calendar"] if c})
        for h in (1, 3, 19, 20, 21, 30, 60, 90):
            full = load(f"windows/{h}.full.bin")
            head = load(f"windows/{h}.bin")
            members = full["m"]["idx"]
            pos = {idx: k for k, idx in enumerate(members)}
            u_set = set(full["orders"]["u"]["0"])
            for w in CANONICAL_WEIGHTS:
                order_b = full["orders"]["ul"][str(w)]
                self.assertEqual(len(order_b), full["counts"]["UL"])
                self.assertTrue(all(liquid[i] for i in order_b), "Gruppe B nur Aktien aus L")
                self.assertEqual(set(order_b), {i for i in u_set if liquid[i]}, "Vergleichsmenge U ∩ L")
                self.assertEqual(head["orders"]["ul"][str(w)], order_b[:50])
                row = overview["ul"][str(w)][h - 1]
                if order_b:
                    self.assertEqual(row["idx"], order_b[0])
                    self.assertEqual(row["M"], len(order_b))
                else:
                    self.assertIn(row["empty"], ("zu_wenig_tagesdaten", "kein_aufwaertskandidat", "keine_aktie_mit_umsatz"))
                occ = frequency["occ"]["ul"][str(w)]
                top = [i for hh, i in zip(occ["h"], occ["idx"]) if hh == h]
                self.assertEqual(top, order_b[:10])
            for w in (0, 100):  # Teilmenge ändert die Reihenfolge nicht
                self.assertEqual(full["orders"]["ul"][str(w)], [i for i in full["orders"]["u"][str(w)] if liquid[i]])
            self.assertEqual(overview["v0l"][h - 1].get("idx"), (full["orders"]["v0l"] or [None])[0])
            for idx in members:
                k = pos[idx]
                in_vl = liquid[idx]
                in_ul = idx in set(full["orders"]["ul"]["60"])
                self.assertEqual(full["m"]["a_rvl"][k] is not None, in_vl)
                self.assertEqual(full["m"]["a_gul"][k] is not None, in_ul)
                self.assertEqual(full["m"]["a_rul"][k] is not None, in_ul)
        # Rangmatrix der Kursreihen: Spalten ul0 … ul100 = Platz in Gruppe B
        isin = next(instruments["isin"][i] for i in full["orders"]["ul"]["60"][:1])
        series = load(f"series/{isin}.bin")
        self.assertEqual(series["rank_columns"][-11:], [f"ul{w}" for w in CANONICAL_WEIGHTS])
        ranks = np.frombuffer(base64.b64decode(series["ranks_b64"]), dtype="<u2").reshape(90, len(series["rank_columns"]))
        column = series["rank_columns"].index("ul60")
        self.assertEqual(int(ranks[89, column]), full["orders"]["ul"]["60"].index(instruments["isin"].index(isin)) + 1)
        self.assertIsNotNone(frequency["server_reference_b"])
        self.assertTrue(frequency["universe"]["ul"].startswith("Gleichmäßig gestiegene Aktien mit Ø Tagesumsatz"))


class RotationPipelineTests(PipelineTestCase):
    """Umschichtungs-Regel im täglichen Lauf: Dateien, Regeleinhaltung, Langhistorie in Etappen."""

    def load_snapshot(self, sid):
        root = self.dir / "snapshots" / sid
        return lambda rel: json.loads(crypto.unpack((root / rel).read_bytes(), None, f"snapshots/{sid}/{rel}"))

    def test_rule_files_are_complete_consistent_and_match_the_series(self):
        from traktien.analytics.weekly import friday_of

        outcome, conn = self.run_once()
        self.assertEqual(outcome.status, "veroeffentlicht", outcome.message)
        load = self.load_snapshot(outcome.snapshot_id)
        manifest = load("manifest.bin")
        instruments = load("instruments.bin")
        check = next(c for c in manifest["checks"] if c["name"] == "umschichtung_regel_eingehalten")
        self.assertTrue(check["passed"], check)
        index = load("rotation/index.bin")
        cfg = self.method.rotation
        self.assertEqual(index["schema"], "tr-rotation/1")
        self.assertEqual(index["version"], "rotation-v1")
        self.assertEqual(index["standard"], "n5-monatlich-w13-k10000")
        self.assertEqual(len(index["varianten"]), len(cfg.holdings) * len(cfg.rhythms) * len(cfg.lookback_weeks) * len(cfg.capitals))
        self.assertEqual(index["langhistorie"]["offen"], 0)
        self.assertEqual(index["langhistorie"]["geladen"], index["vorauswahl"])
        self.assertEqual(manifest["rotation"]["standard"], index["standard"])
        n_instruments = len(instruments["isin"])
        usd = instruments["turnover"]["usd"]
        for info in index["varianten"]:
            self.assertEqual(info["status"], "ok", info["key"])
            variant = load(f"rotation/{info['key']}.bin")
            self.assertEqual(variant["kennzahlen"], info["kennzahlen"])
            days = variant["verlauf"]["tage"]
            self.assertTrue(all(friday_of(d) == d for d in days), "Bewertung zu Freitagsschlusskursen")
            for key in ("depot", "ohne_kosten", "vergleich"):
                self.assertEqual(len(variant["verlauf"][key]), len(days))
            self.assertEqual(variant["verlauf"]["depot"][0], info["kapital"], "am ersten Entscheidungstag noch alles Bargeld")
            orders = variant["orders"]
            decided = set(variant["umschichtungen"])
            for k, decision in enumerate(orders["tag"]):
                self.assertIn(decision, decided)
                self.assertGreater(orders["ausfuehrung"][k], decision, "ausgeführt erst am nächsten Handelstag")
                self.assertLessEqual(orders["ausfuehrung"][k], decision + 7)
                self.assertTrue(0 <= orders["idx"][k] < n_instruments)
                self.assertGreaterEqual(usd[orders["idx"][k]] or 0, cfg.pool_min_turnover_usd, "nur Aktien der Vorauswahl")
                if orders["aktion"][k] == "kauf":
                    self.assertLessEqual(orders["platz"][k], info["aktien"])
            preview = variant["vorschlag"]
            self.assertLessEqual(len(preview["bestand"]["idx"]), info["aktien"])
            self.assertLessEqual(sum(preview["bestand"]["anteil"]), 1.0 + 1e-6)
            trend = preview["rangliste"]["trend"]
            self.assertEqual(trend, sorted(trend, reverse=True))
            self.assertEqual(preview["rangliste"]["platz"], list(range(1, len(trend) + 1)))
            self.assertEqual(info["beschlossen_am"], preview["beschlossen_am"])
        # Tagesvorschlag der Standardvariante (nicht beschlossen): Trend = Kursrendite über 91 Tage aus der Kursreihe
        default = load(f"rotation/{index['standard']}.bin")["vorschlag"]
        self.assertIsNone(default["beschlossen_am"])
        D = manifest["cutoff_day"]
        for idx, value in zip(default["rangliste"]["idx"], default["rangliste"]["trend"]):
            series = load(f"series/{instruments['isin'][idx]}.bin")
            d, c = series["d"], series["c"]
            then = max(k for k, day_ in enumerate(d) if day_ <= D - 91)
            self.assertGreaterEqual(d[then], D - 98)
            expected = c[d.index(D)] / c[then] - 1.0
            self.assertAlmostEqual(value, expected, delta=abs(expected) * 6e-6 + 1e-9)  # sechs signifikante Stellen
        events = [r["message"] for r in conn.execute("SELECT message FROM run_event WHERE step = 'umschichtung'")]
        self.assertTrue(any(m.startswith("Wochenwerte für die Umschichtungs-Regel") for m in events), events)
        self.assertTrue(any(line.startswith("Umschichtungs-Regel (5 Aktien") for line in report_lines(conn, outcome)))

    def test_long_history_is_loaded_in_stages_stored_weekly_and_refreshed_after_splits(self):
        from traktien.config import PipelineConfig

        raw = json.loads(json.dumps(self.pipeline.raw))
        raw["abruf"]["langhistorie_max_pro_lauf"] = 30
        self.pipeline = PipelineConfig(raw)
        first, conn = self.run_once()
        self.assertEqual(first.status, "veroeffentlicht", first.message)
        rows = repo.long_history_rows(conn)
        loaded = [lid for lid, r in rows.items() if r["status"] == "ok"]
        waiting = [lid for lid, r in rows.items() if r["status"] == "offen"]
        self.assertEqual(len(loaded), 30)
        self.assertGreater(len(waiting), 0)
        index = self.load_snapshot(first.snapshot_id)("rotation/index.bin")
        self.assertEqual(index["langhistorie"], {"aktien": len(rows), "geladen": 30, "offen": len(waiting), "ohne_daten": 0})
        D = determine_cutoff_day(conn)
        long_weeks = repo.week_bars_since(conn, loaded[:1], 0)[loaded[0]]
        short_weeks = repo.week_bars_since(conn, waiting[:1], 0)[waiting[0]]
        self.assertLess(long_weeks[0]["week_end"], short_weeks[0]["week_end"], "Langabruf reicht weiter zurück als die Tageskurse")
        self.assertGreaterEqual(short_weeks[0]["week_end"], D - 200)
        for row in long_weeks[1:]:
            self.assertEqual((row["week_end"] + 3) % 7, 4, "Schlüssel ist der Freitag")
            if row["close"] is not None:
                self.assertIsNotNone(row["first_close"])
                self.assertTrue(row["week_end"] - 7 < row["first_day"] <= row["week_end"])
        # Nach einem Split werden die Wochenwerte zuerst neu geladen (sonst unbereinigt)
        repo.mark_long_history_refresh(conn, loaded[0])
        self.assertEqual(repo.long_history_due(conn, 1), [loaded[0]])
        second, conn = self.run_once(force_publish=True)
        self.assertEqual(second.status, "veroeffentlicht", second.message)
        rows = repo.long_history_rows(conn)
        self.assertEqual(rows[loaded[0]]["status"], "ok")
        self.assertEqual(sum(1 for r in rows.values() if r["status"] == "ok"), min(len(rows), 59))
        again = self.load_snapshot(second.snapshot_id)("rotation/index.bin")
        self.assertEqual(again["langhistorie"]["geladen"], min(len(rows), 59))


class SymbolAlternativePipelineTests(PipelineTestCase):
    """1.4.1: Kennt der Kursanbieter ein Kürzel nicht, wird ein anderes Kürzel derselben Börse gesucht."""

    def load(self, sid, rel):
        return json.loads(crypto.unpack((self.dir / "snapshots" / sid / rel).read_bytes(), None, f"snapshots/{sid}/{rel}"))

    def test_unknown_symbol_is_replaced_only_by_a_plausible_same_exchange_alternative(self):
        xetra = [i for i in build_demo_universe() if i.exchange_key == "XETR" and i.pattern == "steady_strong"]
        good, bad = xetra[0], xetra[1]
        other = next(i for i in xetra[2:] if name_similarity(i.name, bad.name) < 0.25)  # fremde Aktie an derselben Börse
        wrong = {good.isin: good.symbol.replace(".DE", "X.DE"), bad.isin: bad.symbol.replace(".DE", "X.DE")}
        base = demo_sources()

        class WrongSymbols(type(base.identity)):
            def lookup(self, isins, budget_s):
                found = super().lookup(isins, budget_s)
                for isin, symbol in wrong.items():
                    if isin in found:
                        found[isin] = [dataclasses.replace(c, provider_symbol=symbol, ticker=symbol.split(".")[0]) for c in found[isin]]
                return found

        class FakeSearch:
            def __init__(self):
                self.queries: list[str] = []

            def search(self, query, table):
                self.queries.append(query)
                if query == good.isin:
                    return [
                        ListingCandidate("yahoo_search", "XFRA", "ANDERSWO.F", "ANDERSWO", "FRA", good.name, "Common Stock"),
                        ListingCandidate("yahoo_search", "XETR", good.symbol, good.symbol.split(".")[0], "GER", good.name, "Common Stock"),
                    ]
                if query == bad.isin:
                    return [ListingCandidate("yahoo_search", "XETR", other.symbol, other.symbol.split(".")[0], "GER", bad.name, "Common Stock")]
                return []

        class Recording:
            def __init__(self, inner):
                self.inner = inner
                self.name = inner.name
                self.symbols: list[str] = []

            def fetch_history(self, symbol, start, end, *, session_final=None):
                self.symbols.append(symbol)
                return self.inner.fetch_history(symbol, start, end, session_final=session_final)

        search, prices = FakeSearch(), Recording(base.prices)
        sources = dataclasses.replace(base, identity=WrongSymbols(), prices=prices, symbol_search=search)
        outcome, conn = self.run_once(sources=sources)
        self.assertEqual(outcome.status, "veroeffentlicht", outcome.message)

        def listing(isin):
            return conn.execute(
                "SELECT l.*, s.old_symbol, s.found FROM listing l JOIN instrument i ON i.id = l.instrument_id "
                "LEFT JOIN symbol_alternative s ON s.listing_id = l.id WHERE i.isin = ? AND l.is_reference = 1",
                (isin,),
            ).fetchone()

        fixed = listing(good.isin)
        self.assertEqual((fixed["provider_symbol"], fixed["last_fetch_status"]), (good.symbol, "ok"))
        self.assertEqual((fixed["old_symbol"], fixed["found"]), (wrong[good.isin], good.symbol))
        kept = listing(bad.isin)
        self.assertEqual((kept["provider_symbol"], kept["last_fetch_status"]), (wrong[bad.isin], "keine_daten"), "fremde Aktie nicht übernommen")
        self.assertEqual((kept["old_symbol"], kept["found"]), (wrong[bad.isin], None))
        self.assertNotIn("ANDERSWO.F", prices.symbols, "Treffer an einer anderen Börse wird nicht einmal abgerufen")
        self.assertIn(good.isin, search.queries)
        self.assertIn(bad.isin, search.queries)
        no_data = {r["isin"] for r in conn.execute("SELECT i.isin FROM listing l JOIN instrument i ON i.id = l.instrument_id WHERE l.is_reference = 1 AND l.last_fetch_status = 'keine_daten'")}
        self.assertEqual(set(search.queries), no_data | {good.isin}, "gesucht wird nur für Notierungen ohne Kursdaten")

        events = [r["message"] for r in conn.execute("SELECT message FROM run_event WHERE run_id = ?", (outcome.run_id,))]
        self.assertTrue(any(m.startswith(f"{good.isin}: Kürzel {wrong[good.isin]} → {good.symbol} (Suche nach ISIN") for m in events), events)
        self.assertTrue(any(m.startswith(f"{bad.isin}: Kürzel {other.symbol} verworfen – Name") for m in events), events)
        summary = next(m for m in events if m.startswith("Andere Kürzel"))
        self.assertIn(f"{len(set(search.queries))} geprüft, 1 gefunden (0 andere Schreibweise, 1 Suche nach ISIN)", summary)

        instruments = self.load(outcome.snapshot_id, "instruments.bin")
        idx = instruments["isin"].index(good.isin)
        self.assertEqual(instruments["symbol"][idx], good.symbol)
        window = self.load(outcome.snapshot_id, "windows/30.full.bin")
        self.assertIn(idx, window["m"]["idx"], "Aktie hat mit dem gefundenen Kürzel eine Kursrendite")

        # Die nächste Identitätsprüfung liefert wieder das alte Kürzel – die Korrektur bleibt bestehen
        conn.execute("UPDATE instrument SET identity_checked_at = '2000-01-01T00:00:00Z' WHERE isin = ?", (good.isin,))
        search.queries.clear()
        second, conn = self.run_once(sources=sources, force_publish=True)
        self.assertIn(second.status, ("veroeffentlicht", "keine_neuen_daten"), second.message)
        rows = conn.execute(
            "SELECT l.provider_symbol, l.is_reference FROM listing l JOIN instrument i ON i.id = l.instrument_id WHERE i.isin = ?", (good.isin,)
        ).fetchall()
        self.assertEqual([(r["provider_symbol"], r["is_reference"]) for r in rows], [(good.symbol, 1)])
        self.assertNotIn(good.isin, search.queries)


def determine_cutoff_day(conn) -> int:
    return int(conn.execute("SELECT MAX(cutoff_day) FROM run").fetchone()[0])


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
        self.assertEqual(status["schedule"]["uhrzeit"], "07:00")

    def test_passphrase_mismatch_is_detected(self):
        load_or_create_key(self.dir, "eins", allow_new=True)
        from traktien.jobs.state import StateError

        with self.assertRaises(StateError):
            load_or_create_key(self.dir, "zwei", allow_new=True)


if __name__ == "__main__":
    unittest.main()
