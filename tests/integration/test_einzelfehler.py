"""Fehlerisolierung je Notierung im täglichen Lauf (ab 1.20.4).

Seit dem 03.11.2026 (16:58 Uhr) endete der offizielle Tageslauf bei jedem Versuch mit „NoDataError: … keine gültigen
Tageskurse im Zeitraum“ (17 rote Läufe bis 07.11.): Für eine Notierung meldete der Kursanbieter korrigierte frühere Kurse,
das Neueinlesen der ganzen Kursreihe – der zweite Kursabruf dieser Notierung im selben Lauf – lieferte keine gültigen
Tageskurse, und die Ausnahme beendete den ganzen Lauf. Weil die Notierung im Checkpoint offen blieb, scheiterte jeder weitere
Versuch an derselben Stelle. Diese Tests stellen das mit der DEMO-Quelle nach (synthetische Testaktien, keine echten Kurse)
und prüfen: Quarantäne statt Abbruch, unveränderte Kursreihe, kein Platz in den Ranglisten, automatisches Neueinlesen und
Aufheben der Quarantäne, Rückrollen nur der betroffenen Notierung, Checkpoint bei Drosselung, kontrollierte Wiederholungen,
Anbieterfehler in jeder Abrufphase und einen sichtbaren Abbruch, wenn sich Einzelfehler zu einem Systemfehler häufen.
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
import unittest
from unittest import mock

from traktien.analytics.codes import InstrumentWarning
from traktien.jobs.daily import EXIT_FAILED, EXIT_OK, EXIT_RETRY, FETCH_RETRY_STATUSES, QUARANTINE_PREFIX, CorrectionUnavailable, DailyRun, RunOptions
from traktien.jobs.sources import demo_sources
from traktien.providers.base import NoDataError, ProviderError, ProviderThrottled
from traktien.store import repo
from traktien.util import crypto

from tests.integration.test_pipeline import MissingCutoffProvider, PipelineTestCase, is_venue_symbol

KORREKTUR_BIT = 1 << InstrumentWarning.KORREKTUR_AUSSTEHEND
FENSTER = (1, 7, 30, 90)


class CorrectionGapProvider:
    """Wrapper um den DEMO-Anbieter: Für ``symbol`` liefert er korrigierte frühere Kurse (Schlusskurse vor dem letzten
    gelieferten Tag um ``factor`` verändert), die ganze Kursreihe beim Neueinlesen (Zeitraum über 100 Tage) aber nicht:
    ``NoDataError`` wie Yahoo („keine gültigen Tageskurse im Zeitraum“) oder – mit ``throttle`` – eine Drosselung."""

    def __init__(self, inner, symbol: str, *, factor: float = 1.03, throttle: bool = False) -> None:
        self.inner = inner
        self.name = inner.name
        self.symbol = symbol
        self.factor = factor
        self.throttle = throttle
        self.refetches = 0
        self.calls: list[str] = []

    def fetch_history(self, symbol, start, end, *, session_final=None):
        self.calls.append(symbol)
        history = self.inner.fetch_history(symbol, start, end, session_final=session_final)
        if symbol != self.symbol:
            return history
        if end - start > 100:
            self.refetches += 1
            if self.throttle:
                raise ProviderThrottled("Testdrosselung beim Neueinlesen")
            raise NoDataError(f"{symbol}: keine gültigen Tageskurse im Zeitraum")
        close = history.close.copy()
        close[history.days < history.days[-1]] *= self.factor
        return dataclasses.replace(history, close=close)


class PhaseFaultProvider:
    """Wrapper: genau ein Anbieterfehler (HTTP 502) beim ersten Abruf der Phase ``phase`` – Tageskurse („kurse“), zweiter
    Börsenplatz („boersenplatz“) oder Langhistorie der Umschichtungs-Regel („langhistorie“)."""

    def __init__(self, inner, phase: str) -> None:
        self.inner = inner
        self.name = inner.name
        self.phase = phase
        self.hit: str | None = None

    @staticmethod
    def phase_of(symbol, start, end) -> str:
        if is_venue_symbol(symbol):
            return "boersenplatz"
        return "langhistorie" if end - start > 600 else "kurse"

    def fetch_history(self, symbol, start, end, *, session_final=None):
        if self.hit is None and self.phase_of(symbol, start, end) == self.phase:
            self.hit = symbol
            raise ProviderError(f"{symbol}: HTTP 502 (Test)")
        return self.inner.fetch_history(symbol, start, end, session_final=session_final)


class ListingIsolationTests(PipelineTestCase):
    def load(self, sid):
        root = self.dir / "snapshots" / sid
        return lambda rel: json.loads(crypto.unpack((root / rel).read_bytes(), None, f"snapshots/{sid}/{rel}"))

    def leader(self, sid, h=30):
        """Symbol und ISIN von Platz 1 in Ranking 1 (Fenster ``h``) – eine Aktie, die sicher in den Ranglisten steht."""
        load = self.load(sid)
        instruments = load("instruments.bin")
        top = load(f"windows/{h}.full.bin")["orders"]["v0"][0]
        return instruments["symbol"][top], instruments["isin"][top]

    def listing(self, conn, symbol):
        return conn.execute("SELECT * FROM listing WHERE provider_symbol = ? AND is_reference = 1", (symbol,)).fetchone()

    def bars(self, conn, row):
        return repo.load_bars(conn, row["id"], int(row["data_revision"]))

    def ranked(self, sid, isin) -> dict[int, bool]:
        load = self.load(sid)
        instruments = load("instruments.bin")
        idx = instruments["isin"].index(isin)
        return {h: idx in load(f"windows/{h}.full.bin")["orders"]["v0"] for h in FENSTER}

    def warnings(self, sid, isin) -> int:
        instruments = self.load(sid)("instruments.bin")
        return int(instruments["warnings"][instruments["isin"].index(isin)])

    def events(self, conn, run_id, step=None):
        sql, params = "SELECT level, step, message FROM run_event WHERE run_id = ?", [run_id]
        if step:
            sql += " AND step = ?"
            params.append(step)
        return conn.execute(sql + " ORDER BY id", params).fetchall()

    def test_failed_second_fetch_quarantines_listing_and_run_still_publishes(self):
        """Regression seit 03.11.2026: Korrigierte frühere Kurse gemeldet, Neueinlesen ohne gültige Tageskurse – mit 1.20.3
        „fehlgeschlagen“ (Gegenprobe mit dem Code von main). Jetzt: Quarantäne, Kursreihe unverändert, aus allen Ranglisten
        zurückgehalten, Lauf veröffentlicht."""
        base = demo_sources()
        first, conn = self.run_once(sources=base)
        self.assertEqual(first.status, "veroeffentlicht", first.message)
        symbol, isin = self.leader(first.snapshot_id)
        self.assertEqual(self.ranked(first.snapshot_id, isin), {h: True for h in FENSTER})
        before = self.listing(conn, symbol)
        stored = self.bars(conn, before)

        conn.execute("DELETE FROM fetch_checkpoint")  # alle Notierungen erneut abrufen (zweiter Lauf zum selben Stichtag)
        gap = CorrectionGapProvider(base.prices, symbol)
        second, conn = self.run_once(sources=dataclasses.replace(base, prices=gap), force_publish=True)
        self.assertEqual((second.status, second.exit_code), ("veroeffentlicht", EXIT_OK), second.message)
        self.assertEqual(gap.refetches, 1, "keine sinnlose Wiederholung, wenn der Anbieter keine Tageskurse liefert")

        row = self.listing(conn, symbol)
        self.assertEqual(row["hold_all"], 1)
        self.assertTrue(row["hold_reason"].startswith(QUARANTINE_PREFIX), row["hold_reason"])
        self.assertIn("keine gültigen Tageskurse", row["hold_reason"])
        self.assertEqual(row["last_fetch_status"], "quarantaene")
        self.assertEqual(int(row["data_revision"]), int(before["data_revision"]), "keine neue Revision aus halben Daten")
        after = self.bars(conn, row)
        for column in ("days", "close", "volume"):
            self.assertEqual(after[column].tolist(), stored[column].tolist(), f"gespeicherte Kursreihe unverändert ({column})")
        checkpoint = repo.fetched(conn, f"{second.cutoff_day}:demo")
        self.assertEqual(checkpoint[row["id"]], "quarantaene")
        self.assertNotIn("fehler", checkpoint.values(), "keine weiteren Fehler")
        self.assertGreater(sum(1 for s in checkpoint.values() if s == "ok"), 100, "alle anderen Notierungen normal gespeichert")

        self.assertEqual(self.ranked(second.snapshot_id, isin), {h: False for h in FENSTER}, "in Quarantäne in keiner Rangliste")
        self.assertTrue(self.warnings(second.snapshot_id, isin) & KORREKTUR_BIT)
        manifest = self.load(second.snapshot_id)("manifest.bin")
        self.assertEqual(manifest["codes"]["instrument_warnings"][str(int(InstrumentWarning.KORREKTUR_AUSSTEHEND))]["key"], "korrektur_ausstehend")
        warned = [e for e in self.events(conn, second.run_id, "quarantaene") if e["level"] == "WARN"]
        self.assertEqual(len(warned), 1)
        summary = [e["message"] for e in self.events(conn, second.run_id, "kurse") if e["message"].startswith("Kursabruf beendet")]
        self.assertEqual(len(summary), 1)
        self.assertIn("; 0 Einzelfehler (isoliert)", summary[0])
        self.assertIn("Quarantäne (Kurskorrektur ausstehend): 1 neu, 0 aufgehoben", summary[0])

        # Nächster Versuch: Die Notierung in Quarantäne wird von selbst erneut abgerufen – ganze Kursreihe, neue Revision,
        # Quarantäne aufgehoben, wieder in den Ranglisten. Erneut geladen werden nur Notierungen mit offenem Abrufstatus.
        reopened = {
            r["provider_symbol"]
            for r in conn.execute(
                "SELECT l.provider_symbol FROM fetch_checkpoint f JOIN listing l ON l.id = f.listing_id WHERE f.target_key = ? AND f.status IN "
                f"({', '.join('?' for _ in FETCH_RETRY_STATUSES)})",
                (f"{second.cutoff_day}:demo", *sorted(FETCH_RETRY_STATUSES)),
            )
        }
        self.assertIn(symbol, reopened)
        counting = MissingCutoffProvider(base.prices, (), None)
        third, conn = self.run_once(sources=dataclasses.replace(base, prices=counting), force_publish=True)
        self.assertEqual(third.exit_code, EXIT_OK, third.message)
        self.assertEqual(set(counting.calls), reopened, "nur Notierungen mit offenem Abrufstatus werden erneut geladen")
        self.assertEqual(counting.calls.count(symbol), 1)
        row = self.listing(conn, symbol)
        self.assertEqual((row["hold_all"], row["hold_reason"], row["last_fetch_status"]), (0, None, "ok"))
        self.assertGreater(int(row["data_revision"]), int(before["data_revision"]))
        self.assertEqual(repo.fetched(conn, f"{third.cutoff_day}:demo")[row["id"]], "ok")
        released = [e["message"] for e in self.events(conn, third.run_id, "quarantaene")]
        self.assertEqual(len(released), 1)
        self.assertIn("Quarantäne aufgehoben", released[0])
        self.assertEqual(self.ranked(third.snapshot_id, isin), {h: True for h in FENSTER})
        self.assertFalse(self.warnings(third.snapshot_id, isin) & KORREKTUR_BIT)

    def test_throttling_during_second_fetch_sets_checkpoint_and_retries_listing(self):
        """Drosselt der Anbieter beim Neueinlesen, ist das kein Datenfehler: Checkpoint, Lauf wartet, die Notierung bleibt
        unverändert und offen – der nächste Versuch lädt sie erneut."""
        base = demo_sources()
        late = dataclasses.replace(base, prices=MissingCutoffProvider(base.prices, ".DE", base_cutoff(self, base)))
        first, conn = self.run_once(sources=late, trigger="manuell")
        self.assertEqual(first.status, "wartet_auf_provider", first.message)
        D = first.cutoff_day
        open_before = {i for i, s in repo.fetched(conn, f"{D}:demo").items() if s == "ohne_stichtag"}
        de = [r for r in conn.execute("SELECT * FROM listing WHERE is_reference = 1 AND provider_symbol LIKE '%.DE' ORDER BY provider_symbol")]
        target = de[len(de) // 2]
        self.assertIn(target["id"], open_before)
        stored = self.bars(conn, target)

        gap = CorrectionGapProvider(base.prices, target["provider_symbol"], throttle=True)
        second, conn = self.run_once(sources=dataclasses.replace(base, prices=gap), trigger="manuell")
        self.assertEqual((second.status, second.exit_code), ("wartet_auf_provider", EXIT_RETRY), second.message)
        self.assertEqual(gap.refetches, 1)
        row = self.listing(conn, target["provider_symbol"])
        self.assertEqual(row["hold_all"], 0, "Drosselung ist keine Quarantäne")
        self.assertEqual(int(row["data_revision"]), int(target["data_revision"]))
        self.assertEqual(self.bars(conn, row)["days"].tolist(), stored["days"].tolist(), "nichts gespeichert, alles zurückgerollt")
        checkpoint = repo.fetched(conn, f"{D}:demo")
        self.assertEqual(checkpoint[row["id"]], "ohne_stichtag", "bleibt für den nächsten Versuch offen")
        drossel = [e["message"] for e in self.events(conn, second.run_id, "kurse") if e["level"] == "WARN"]
        self.assertTrue(any("Anbieter drosselt beim Neueinlesen" in m for m in drossel), drossel)

        third, conn = self.run_once(sources=base, trigger="manuell")
        self.assertEqual(third.status, "veroeffentlicht", third.message)
        self.assertEqual(repo.fetched(conn, f"{D}:demo")[row["id"]], "ok")

    def test_store_error_rolls_back_only_that_listing_and_next_attempt_loads_it(self):
        """Ein unerwarteter Fehler nach ersten Schreibvorgängen: nur diese Notierung zurückgerollt (keine halbe Revision),
        Status „fehler“, alle anderen gespeichert, Lauf veröffentlicht; der nächste Versuch lädt die Notierung erneut."""
        base = demo_sources()
        original = DailyRun.store_history
        chosen: dict = {}

        def broken(run, listing, history, full, revision):
            if not chosen and listing["provider_symbol"].endswith(".L"):
                chosen["symbol"] = listing["provider_symbol"]
            if listing["provider_symbol"] == chosen.get("symbol"):
                original(run, listing, history, full, revision)  # schreibt Revision und Kurse …
                raise RuntimeError("Testfehler nach dem Schreiben")  # … und scheitert danach
            return original(run, listing, history, full, revision)

        with mock.patch.object(DailyRun, "store_history", broken):
            first, conn = self.run_once(sources=base)
        self.assertEqual((first.status, first.exit_code), ("veroeffentlicht", EXIT_OK), first.message)
        row = self.listing(conn, chosen["symbol"])
        self.assertEqual(row["last_fetch_status"], "fehler")
        self.assertIn("RuntimeError: Testfehler nach dem Schreiben", row["last_error"])
        self.assertEqual(int(row["data_revision"]), 0, "Revision zurückgerollt")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM daily_bar WHERE listing_id = ?", (row["id"],)).fetchone()[0], 0, "keine Kurse gespeichert")
        checkpoint = repo.fetched(conn, f"{first.cutoff_day}:demo")
        self.assertEqual(checkpoint[row["id"]], "fehler")
        self.assertEqual(sum(1 for s in checkpoint.values() if s == "fehler"), 1)
        summary = [e["message"] for e in self.events(conn, first.run_id, "kurse") if e["message"].startswith("Kursabruf beendet")]
        self.assertIn("; 1 Einzelfehler (isoliert)", summary[0])
        warned = [e["message"] for e in self.events(conn, first.run_id, "kurse") if e["level"] == "WARN"]
        self.assertTrue(any("nur diese Notierung zurückgerollt" in m and "daily.py:" in m for m in warned), warned)

        second, conn = self.run_once(sources=base, force_publish=True)
        self.assertEqual(second.exit_code, EXIT_OK, second.message)
        row = self.listing(conn, chosen["symbol"])
        self.assertEqual(row["last_fetch_status"], "ok")
        self.assertGreater(len(self.bars(conn, row)["days"]), 100)
        self.assertEqual(repo.fetched(conn, f"{second.cutoff_day}:demo")[row["id"]], "ok")

    def test_provider_error_in_any_fetch_phase_never_stops_the_run(self):
        """Ein Anbieterfehler trifft nur die eine Notierung – in jeder Abrufphase des Tageslaufs (das Neueinlesen nach einer
        Kurskorrektur prüfen die Tests oben)."""
        for phase in ("kurse", "boersenplatz", "langhistorie"):
            with self.subTest(phase=phase):
                self.tearDown()
                self.setUp()
                base = demo_sources()
                fault = PhaseFaultProvider(base.prices, phase)
                outcome, conn = self.run_once(sources=dataclasses.replace(base, prices=fault))
                self.assertIsNotNone(fault.hit, f"Phase {phase} im DEMO-Lauf nicht erreicht")
                self.assertEqual((outcome.status, outcome.exit_code), ("veroeffentlicht", EXIT_OK), outcome.message)
                if phase == "kurse":
                    row = self.listing(conn, fault.hit)
                    self.assertEqual(repo.fetched(conn, f"{outcome.cutoff_day}:demo")[row["id"]], "fehler")

    def test_broken_database_is_no_single_listing_error(self):
        """Hat SQLite die Transaktion selbst schon zurückgesetzt (z. B. Datenträger voll), ist das kein Einzelfall: Der
        ursprüngliche Fehler beendet den Lauf, statt als Einzelfehler einer Notierung durchzugehen."""
        original = DailyRun.store_history
        hit: list[str] = []

        def disk_full(run, listing, history, full, revision):
            if not hit:
                hit.append(listing["provider_symbol"])
                run.conn.execute("ROLLBACK")  # wie SQLite bei SQLITE_FULL: ganze Transaktion samt Sicherungspunkt weg
                raise sqlite3.OperationalError("database or disk is full")
            return original(run, listing, history, full, revision)

        with mock.patch.object(DailyRun, "store_history", disk_full):
            outcome, conn = self.run_once()
        self.assertEqual((outcome.status, outcome.exit_code), ("fehlgeschlagen", EXIT_FAILED))
        self.assertIn("database or disk is full", outcome.message)
        self.assertEqual(self.published(conn), [])

    def test_many_errors_are_a_system_error_and_fail_the_run_visibly(self):
        """Mehr Einzelfehler als ``abruf.einzelfehler_max``: kein Einzelfall – der Lauf bricht sichtbar ab und
        veröffentlicht nichts (statt still Tausende Notierungen zu überspringen)."""
        self.pipeline.raw.setdefault("abruf", {})["einzelfehler_max"] = 3

        def always(run, listing, history, full, revision):
            raise OSError("Datenträger voll (Test)")

        with mock.patch.object(DailyRun, "store_history", always):
            outcome, conn = self.run_once()
        self.assertEqual((outcome.status, outcome.exit_code), ("fehlgeschlagen", EXIT_FAILED))
        self.assertIn("Mehr als 3 Einzelfehler", outcome.message)
        self.assertEqual(self.published(conn), [])
        D = conn.execute("SELECT cutoff_day FROM run WHERE id = ?", (outcome.run_id,)).fetchone()[0]
        self.assertEqual(sum(1 for s in repo.fetched(conn, f"{D}:demo").values() if s == "fehler"), 4, "drei Einzelfehler erlaubt, der vierte bricht ab")


def base_cutoff(case: PipelineTestCase, base) -> int:
    from traktien.jobs.cutoff import determine_cutoff

    codes = {e.calendar for e in case.table.exchanges.values() if e.key in ("US", "XETR", "XLON", "XHKG", "XASX", "XTKS")}
    return determine_cutoff(codes, base.calendars, base.now).cutoff_day


class RefetchRetryTests(PipelineTestCase):
    """Kontrollierte Wiederholungen beim Neueinlesen: vorübergehende Fehler bis ``abruf.korrektur_wiederholungen`` Mal,
    keine Tageskurse sofort Quarantäne, Drosselung unverändert an den Aufrufer."""

    class Flaky:
        name = "test"

        def __init__(self, errors):
            self.errors = list(errors)
            self.calls = 0

        def fetch_history(self, symbol, start, end, *, session_final=None):
            self.calls += 1
            if self.errors:
                raise self.errors.pop(0)
            return "kursreihe"

    def run_with(self, provider):
        self.pipeline.raw.setdefault("abruf", {}).update({"korrektur_wiederholungen": 2, "korrektur_pause_sekunden": 0})
        conn = self.open(self.dir / "state.sqlite")
        return DailyRun(conn, self.dir, dataclasses.replace(demo_sources(), prices=provider), self.method, self.pipeline, self.table, None, RunOptions())

    def test_transient_errors_are_retried(self):
        flaky = self.Flaky([ProviderError("HTTP 502"), ConnectionError("getrennt")])
        self.assertEqual(self.run_with(flaky).refetch_corrected("X", 1, 500), "kursreihe")
        self.assertEqual(flaky.calls, 3)

    def test_persistent_errors_end_in_quarantine_after_the_retries(self):
        flaky = self.Flaky([ProviderError("HTTP 502")] * 5)
        with self.assertRaises(CorrectionUnavailable) as caught:
            self.run_with(flaky).refetch_corrected("X", 1, 500)
        self.assertEqual(flaky.calls, 3)
        self.assertIn("nach 3 Versuchen", str(caught.exception))

    def test_no_data_goes_to_quarantine_at_once_and_throttling_is_passed_on(self):
        flaky = self.Flaky([NoDataError("X: keine gültigen Tageskurse im Zeitraum")])
        with self.assertRaises(CorrectionUnavailable):
            self.run_with(flaky).refetch_corrected("X", 1, 500)
        self.assertEqual(flaky.calls, 1)
        throttled = self.Flaky([ProviderThrottled("429")])
        with self.assertRaises(ProviderThrottled):
            self.run_with(throttled).refetch_corrected("X", 1, 500)
        self.assertEqual(throttled.calls, 1)


if __name__ == "__main__":
    unittest.main()
