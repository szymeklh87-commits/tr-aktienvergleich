"""Täglicher Lauf (Abschnitte 16 und 17).

Zustände: laeuft → (wartet_auf_provider) → vollstaendig_berechnet/teilweise_berechnet →
geprueft → veroeffentlicht; außerdem keine_neuen_daten, fehlgeschlagen, abgebrochen.
„Teilweise berechnet“ bedeutet nicht automatisch „teilweise veröffentlicht“: ein
Teilstand wird nur veröffentlicht, wenn er in sich konsistent ist und sein Nenner
bekannt ist, und er wird als Teilstand gekennzeichnet.

Rückgabecodes der CLI: 0 = veröffentlicht oder nichts Neues, 75 = später erneut
versuchen (Anbieterdaten fehlen noch), 2 = anderer Lauf aktiv, 1 = Fehler.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .. import __version__
from ..analytics.codes import RETURN_PUBLISHABLE, InstrumentWarning, Status, WindowWarning
from ..analytics.engine import InstrumentData, SnapshotComputation, compute_snapshot
from ..analytics.fx import FxRates
from ..analytics.venues import AltSeries, InstrumentVenue, VenueCheck, candidate_indices, choose_venue, compare_instrument, robust_daily_noise
from ..analytics import rotation as rot
from ..analytics.weekly import aggregate_weeks, fridays, rolling_week_ends
from ..analytics.quality import SplitEvent
from ..config import MethodConfig, PipelineConfig
from ..providers.base import HistoryFetchStats, HistoryJob, NoDataError, PriceHistory, ProviderError, ProviderThrottled, fetch_histories_sequential
from ..providers.exchanges import ExchangeTable, unit_info
from ..providers.identity import alternative_symbols, plausible_alternative, resolve_identity, verify_against_prices
from ..providers.tr_universe import evaluate_new_universe
from ..publish.checks import run_checks
from ..publish.snapshot_writer import SCHEMA as API_SCHEMA, InstrumentMeta, SnapshotWriter, evidence_archive, snapshot_tar
from ..store import repo
from ..util import crypto
from ..util.jsonio import atomic_write_bytes, atomic_write_json, canonical_bytes, sha256_hex
from ..util.log import get_logger
from ..util.timeutil import day_to_iso, iso_utc, parse_iso_utc
from ..analytics import kursabgleich as kursregel
from .cutoff import NextCutoff, determine_cutoff, next_cutoff, session_final_checker
from .kursabgleich_lauf import Kursabgleich, Settings as KursabgleichSettings, build_report
from .sources import Sources

LOG = get_logger(__name__)
LOCK_NAME = "taeglicher-lauf"
# Ab 1.17: nächster möglicher Kursstand des letzten Laufs (Datenbank-Tabelle kv), damit status.json ihn auch nach
# Schritten auf einem frischen Rechner nennt (Kennzahlen, „Nur die Website“)
NEXT_CUTOFF_KV = "naechster_kursstand"

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_LOCKED = 2
EXIT_RETRY = 75

# Abrufstatus, die der nächste Versuch für denselben Stichtag erneut abruft
FETCH_RETRY_STATUSES = frozenset({"ohne_stichtag", "fehler", "identitaet_unklar"})


@dataclass
class SymbolSearchBudget:
    """Suche nach anderen Kürzeln für Notierungen ohne Kursdaten: Kontingent je Lauf."""

    max_listings: int
    max_seconds: float
    tried: int = 0
    found_spelling: int = 0
    found_search: int = 0
    seconds: float = 0.0
    exhausted_logged: bool = False

    def available(self) -> bool:
        return self.tried < self.max_listings and self.seconds < self.max_seconds


@dataclass
class RunOptions:
    trigger: str = "manuell"
    planned_start: dt.datetime | None = None
    max_attempts: int = 4
    force_publish: bool = False
    time_budget_s: float = 5 * 3600
    checkpoint_every_s: float = 900
    on_checkpoint: Callable[[], None] | None = None
    identity_limit: int | None = None


@dataclass
class RunOutcome:
    exit_code: int
    status: str
    message: str
    run_id: str
    snapshot_id: str | None = None
    cutoff_day: int | None = None
    details: dict = field(default_factory=dict)


def stored_universe_content(stored: dict[str, dict]) -> dict[str, tuple[str, bool]]:
    """Inhalt einer gespeicherten TR-Liste: je ISIN Name und Gültigkeit (die Seitenzahl im PDF zählt nicht)."""
    return {isin: (row["name"], bool(row["valid"])) for isin, row in stored.items()}


def same_universe_content(entries, stored: dict[str, dict]) -> bool:
    """Gleicher Inhalt wie die gespeicherte Liste: dieselben ISINs mit denselben Namen und derselben Gültigkeit. Bei
    doppelten Einträgen gilt – wie beim Speichern – der Inhalt je ISIN."""
    if not entries or not stored:
        return False
    return {e.isin: (e.name, bool(e.valid)) for e in entries} == stored_universe_content(stored)


def own_cutoff_day(days: np.ndarray, close: np.ndarray, sessions: np.ndarray, D: int, max_missed: int) -> int | None:
    """Eigener Stichtag einer Aktie ohne Schlusskurs am Stichtag ``D`` (ab tr-methode-1.9.0, Simons Wunsch vom 14.10.2026:
    „Alle Aktien sollen bewertet werden“): der Tag ihres letzten gültigen Schlusskurses an einer Börsensitzung, wenn die
    Börse seitdem höchstens ``max_missed`` Sitzungen hatte (1 = nur ``D`` selbst; Feiertage zählen nicht). ``None``, wenn
    der Kurs am Stichtag vorliegt (Ende am gemeinsamen Stichtag) oder der letzte Kurs veraltet ist (Aktie fehlt wie bisher)."""
    days = np.asarray(days, dtype=np.int64)
    close = np.asarray(close, dtype=np.float64)
    sessions = np.asarray(sessions, dtype=np.int64)
    valid = (days <= D) & np.isfinite(close) & (close > 0) & np.isin(days, sessions)
    if not valid.any():
        return None
    last = int(days[valid].max())
    if last >= D:
        return None
    missed = int(np.count_nonzero((sessions > last) & (sessions <= D)))
    return last if missed <= max_missed else None


class DailyRun:
    def __init__(
        self,
        conn,
        state_dir: Path,
        sources: Sources,
        method: MethodConfig,
        pipeline: PipelineConfig,
        table: ExchangeTable,
        key: crypto.KeyMaterial | None,
        options: RunOptions,
    ) -> None:
        self.conn = conn
        self.state_dir = Path(state_dir)
        self.sources = sources
        self.method = method
        self.pipeline = pipeline
        self.table = table
        self.key = key
        self.options = options
        self.run_id = f"{iso_utc(sources.now).replace(':', '').replace('-', '')}-{uuid.uuid4().hex[:8]}"
        self.started_monotonic = time.monotonic()
        self.last_checkpoint = time.monotonic()
        self.attempt = 1
        # Schlusskurse aus der Kursmeldung (Tageskerze beim Anbieter noch unvollständig): neu am Stichtag
        # übernommen bzw. in diesem Lauf durch die nachgelieferte Tageskerze ersetzt
        self.quote_closes = 0
        self.quote_replaced = 0
        # Je Markt einige Notierungen ohne Kurs am Stichtag (für den Kurzbericht des Laufs)
        self.cutoff_gaps: dict[str, list[str]] = {}
        # Zwischenstand (ab 1.13): Aktien je noch geschlossener Börse, die mit dem letzten Schlusskurs zählen
        self.closing_counts: dict[str, int] = {}
        self.versions = {
            "software": __version__,
            "method": method.method_version,
            "metrics": method.metrics_version,
            "ranking": method.ranking_version,
            "frequency": method.frequency_version,
            "groups": method.groups_version,
            "reference_model": method.reference_model,
            "turnover": method.turnover_version,
            "rotation": method.rotation.version,
            "method_fingerprint": method.fingerprint(),
            "exchanges": table.version,
            "api_schema": API_SCHEMA,
        }
        # Kursabgleich mit den Kursarchiven der Börsen (ab 1.20.0): nur mit angebundener Quelle der Börsen
        self.kursabgleich: Kursabgleich | None = None
        exchanges = getattr(sources, "exchanges", None)
        settings = KursabgleichSettings.from_pipeline(pipeline)
        if exchanges is not None and settings.enabled:
            self.kursabgleich = Kursabgleich(conn, exchanges, sources.calendars, settings, event=self.event)
            self.versions["kursabgleich"] = kursregel.RULE_VERSION

    # -------------------------------------------------------------- Hilfen

    def now(self) -> dt.datetime:
        if self.sources.data_mode == "demo":
            return self.sources.now
        return dt.datetime.now(tz=dt.timezone.utc)

    def elapsed(self) -> float:
        return time.monotonic() - self.started_monotonic

    def event(self, step: str, message: str, level: str = "INFO") -> None:
        LOG.log(20 if level == "INFO" else 30, "[%s] %s", step, message)
        repo.log_event(self.conn, self.run_id, step, message, level)

    def checkpoint(self, force: bool = False) -> None:
        repo.heartbeat(self.conn, LOCK_NAME, self.run_id)
        if self.options.on_checkpoint and (force or time.monotonic() - self.last_checkpoint >= self.options.checkpoint_every_s):
            self.options.on_checkpoint()
            self.last_checkpoint = time.monotonic()

    def finish(self, status: str, message: str, exit_code: int, **extra) -> RunOutcome:
        repo.update_run(self.conn, self.run_id, status=status, status_detail=message, finished_at=iso_utc(self.now()), **{k: v for k, v in extra.items() if k in ("snapshot_id", "cutoff_day", "data_revision", "universe_id")})
        repo.release_lock(self.conn, LOCK_NAME, self.run_id)
        self.event("ende", f"{status}: {message}")
        self.write_status(status, message)
        details = dict(extra)
        if self.cutoff_gaps:
            details.setdefault("ohne_stichtag", self.cutoff_gaps)
        return RunOutcome(exit_code, status, message, self.run_id, extra.get("snapshot_id"), extra.get("cutoff_day"), details)

    # -------------------------------------------------------------- Ablauf

    def execute(self) -> RunOutcome:
        repo.create_run(
            self.conn,
            self.run_id,
            trigger=self.options.trigger,
            planned_start=iso_utc(self.options.planned_start) if self.options.planned_start else None,
            attempt=1,
            versions=self.versions,
            data_mode=self.sources.data_mode,
            started_at=iso_utc(self.now()),
        )
        acquired, other = repo.acquire_lock(self.conn, LOCK_NAME, self.run_id)
        if not acquired:
            repo.update_run(self.conn, self.run_id, status="abgebrochen", status_detail=f"Anderer Lauf aktiv: {other}", finished_at=iso_utc(self.now()))
            return RunOutcome(EXIT_LOCKED, "abgebrochen", f"Anderer Lauf aktiv ({other}) – kein zweiter Vollabruf", self.run_id)
        try:
            return self._execute()
        except Exception as exc:  # Lauf endet kontrolliert, gutes Ergebnis bleibt erhalten
            detail = f"{type(exc).__name__}: {exc}"
            self.event("fehler", detail + "\n" + traceback.format_exc(limit=6), level="ERROR")
            return self.finish("fehlgeschlagen", detail, EXIT_FAILED)

    def _execute(self) -> RunOutcome:
        repo.sync_review_decisions(self.conn, self.sources.review_decisions)
        universe = self.step_universe()
        if universe is None:
            return self.finish("fehlgeschlagen", "Kein akzeptiertes TR-Universum verfügbar", EXIT_FAILED)
        repo.update_run(self.conn, self.run_id, universe_id=universe["id"])
        members = repo.universe_members(self.conn, universe["id"])
        repo.ensure_instruments(self.conn, members)

        self.step_identity(members)
        refs = repo.reference_listings(self.conn)
        codes = {row["calendar_code"] for isin, row in refs.items() if isin in members and row["calendar_code"]}
        available_codes = {c for c in codes if self.sources.calendars.available(c)}
        broken = getattr(self.sources.calendars, "broken", None) or {}
        if broken:
            self.event(
                "kalender",
                "Börsenkalender nicht ladbar: " + ", ".join(f"{code} ({why})" for code, why in sorted(broken.items()))
                + " – Aktien dieser Börsen fehlen in diesem Lauf (Bibliotheksversionen prüfen)",
                "WARN",
            )
        if not available_codes:
            return self.finish("fehlgeschlagen", "Keine Referenznotierung mit verfügbarem Börsenkalender", EXIT_FAILED)
        cutoff = determine_cutoff(
            available_codes,
            self.sources.calendars,
            self.now(),
            grace_minutes=int(self.pipeline.get("stichtag.karenz_minuten_nach_schluss", 60)),
        )
        D = cutoff.cutoff_day
        self.next_cutoff = next_cutoff(
            available_codes, self.sources.calendars, D, grace_minutes=int(self.pipeline.get("stichtag.karenz_minuten_nach_schluss", 60))
        )
        self.attempt = repo.attempts_for_cutoff(self.conn, D, self.sources.data_mode) + 1
        # Über Teilstand oder Fehlschlag entscheidet nur der letzte geplante Versuch eines Stichtags.
        # Von Hand gestartete Läufe („Jetzt aktualisieren“) warten bei fehlenden Kursen nur weiter –
        # sie sollen nicht die Wiederholungen des Zeitplans aufbrauchen und keinen roten Lauf erzeugen.
        scheduled_attempt = repo.attempts_for_cutoff(self.conn, D, self.sources.data_mode, trigger="zeitplan") + 1
        final_attempt = self.options.trigger == "zeitplan" and scheduled_attempt >= self.options.max_attempts
        repo.update_run(self.conn, self.run_id, cutoff_day=D)
        self.conn.execute("UPDATE run SET attempt = ? WHERE id = ?", (self.attempt, self.run_id))
        self.event("stichtag", f"Kursstichtag {day_to_iso(D)} (Börsen mit Sitzung: {', '.join(cutoff.markets_with_session)}); Versuch {self.attempt}")

        latest = repo.latest_for_cutoff(self.conn, D, self.sources.data_mode)
        if latest is not None and latest["completeness"] == "vollstaendig" and self.same_universe(latest["universe_id"], universe["id"]) and not self.options.force_publish:
            return self.finish(
                "keine_neuen_daten",
                f"Kein neuer abgeschlossener Börsentag seit {day_to_iso(D)}; letzter Stand bleibt gültig",
                EXIT_OK,
                cutoff_day=D,
                snapshot_id=latest["id"],
            )

        throttled = self.step_fetch(members, refs, D)
        fx = self.step_fx(D)
        comp, metas, market_stats = self.step_kursabgleich(universe, members, D, fx)
        # Drosselt der Kursanbieter schon beim Tagesabruf, wartet auch der Langabruf auf den nächsten Lauf
        self.step_long_history(comp, metas, D, fetch=not throttled)
        completeness = self.assess_completeness(market_stats)
        repo.update_run(self.conn, self.run_id, data_revision=comp.input_hash)

        status_partial = completeness["status"] != "vollstaendig"
        if (throttled or status_partial) and not final_attempt and not self.options.force_publish:
            repo.update_run(self.conn, self.run_id, status="wartet_auf_provider")
            reason = "Anbieter drosselt" if throttled else f"Daten für {', '.join(completeness['missing_markets']) or 'einzelne Märkte'} noch unvollständig"
            return self.finish("wartet_auf_provider", f"{reason}; nächster Versuch geplant", EXIT_RETRY, cutoff_day=D, details=completeness)
        # Teilstand (letzter geplanter Versuch): nur, wenn genug Aktien einen Schlusskurs am Stichtag haben –
        # gezählt über Aktien, nicht über Börsen (Tallinn mit 15 Aktien wiegt nicht so viel wie Hongkong mit 735)
        minimum = float(self.pipeline.get("vollstaendigkeit.teilstand_mindestens_aktien", 0.75))
        if completeness["instrument_share"] < minimum and not self.options.force_publish:
            return self.finish(
                "fehlgeschlagen",
                f"Nur {completeness['instrument_share']:.0%} der erwarteten Aktien mit Schlusskurs am Stichtag (nötig {minimum:.0%}) – kein Teilstand veröffentlicht",
                EXIT_FAILED,
                cutoff_day=D,
                details=completeness,
            )

        repo.update_run(self.conn, self.run_id, status="teilweise_berechnet" if status_partial else "vollstaendig_berechnet")
        return self.publish(universe, comp, metas, completeness, D)

    # ---------------------------------------------------------- Universum

    def same_universe(self, stand_universe: str | None, current: str) -> bool:
        """Gehört der vorhandene Stand zur selben TR-Liste? Ab 1.17.1 auch dann, wenn er mit einer anderen Dateifassung
        desselben Inhalts gerechnet wurde (dieselben ISINs, Namen und Gültigkeit) – dann bleibt er gültig."""
        if stand_universe == current:
            return True
        if stand_universe is None:
            return False
        stored = repo.universe_members(self.conn, stand_universe)
        return bool(stored) and stored_universe_content(stored) == stored_universe_content(repo.universe_members(self.conn, current))

    def step_universe(self) -> dict | None:
        previous = repo.latest_universe(self.conn, data_mode=self.sources.data_mode)
        try:
            meta, parsed = self.sources.universe.fetch()
        except Exception as exc:
            if previous is None:
                self.event("universum", f"TR-Liste nicht abrufbar und keine frühere Liste: {exc}", "ERROR")
                return None
            self.event("universum", f"TR-Liste nicht abrufbar ({exc}); letzte akzeptierte Liste vom {previous['retrieved_at']} bleibt aktiv", "WARN")
            return dict(previous)
        stored = repo.universe_members(self.conn, previous["id"]) if previous else None
        previous_members = {k: v["name"] for k, v in stored.items()} if stored is not None else None
        if previous is not None and previous["sha256"] == meta["sha256"]:
            repo.insert_universe(self.conn, meta, parsed.entries, "akzeptiert", "unverändert bestätigt", previous["id"], 0, 0)
            self.event("universum", f"TR-Liste unverändert ({len(parsed.entries)} ISINs), bestätigt am {meta['retrieved_at']}")
            return dict(repo.universe_by_id(self.conn, meta["id"]))
        if previous is not None and stored is not None and same_universe_content(parsed.entries, stored):
            # Ab 1.17.1: Trade Republic liefert dieselbe Liste in mehreren Dateifassungen (andere Bytes, gleicher Inhalt).
            # Bis 1.17.0 galt jede Fassung als neue Liste – der Lauf rechnete denselben Stichtag dann erneut und
            # veröffentlichte ihn ein zweites Mal (gesehen am 23. und 24.10.2026). Jetzt bleibt die bisherige Liste gültig.
            repo.confirm_universe(self.conn, previous["id"], meta)
            self.event("universum", f"TR-Liste inhaltlich unverändert (andere Datei, dieselben {len(stored)} ISINs und Namen) – bisherige Liste bleibt gültig")
            return dict(repo.universe_by_id(self.conn, previous["id"]))
        min_entries = int(self.pipeline.get("universum.min_eintraege", 1000)) if self.sources.data_mode == "produktiv" else 10
        decision = evaluate_new_universe(
            parsed,
            previous_members,
            min_entries=min_entries,
            max_change_share=float(self.pipeline.get("universum.max_aenderung_ohne_pruefung", 0.10)),
        )
        approved = set(self.pipeline.get("universum.freigegebene_versionen", []) or [])
        accepted = decision.accepted or meta["id"] in approved
        reason = decision.reason if decision.accepted else (f"manuell freigegeben ({decision.reason})" if accepted else decision.reason)
        status = "akzeptiert" if accepted else "zur_pruefung"
        if repo.universe_by_id(self.conn, meta["id"]) is not None:
            repo.set_universe_status(self.conn, meta["id"], status, reason)
        else:
            repo.insert_universe(self.conn, meta, parsed.entries, status, reason, previous["id"] if previous else None, len(decision.added), len(decision.removed))
        if accepted:
            repo.record_universe_changes(self.conn, meta["id"], decision.added, decision.removed, decision.renamed)
            self.event("universum", f"Neue TR-Liste akzeptiert: {parsed.count} ISINs (+{len(decision.added)} / −{len(decision.removed)}), Abschnitte: {', '.join(parsed.sections)}")
            return dict(repo.universe_by_id(self.conn, meta["id"]))
        self.event("universum", f"Neue TR-Liste {meta['id']} zur Prüfung zurückgehalten: {reason}", "WARN")
        if previous is None:
            return None
        return dict(previous)

    # ---------------------------------------------------------- Identität

    def step_identity(self, members: dict) -> None:
        max_age = int(self.pipeline.get("abruf.identitaet_pruefung_alle_tage", 45))
        limit = self.options.identity_limit or int(self.pipeline.get("abruf.identitaet_max_pro_lauf", 4000))
        due = repo.identity_due(self.conn, list(members), max_age)[:limit]
        if not due:
            return
        self.event("identitaet", f"Identitätsprüfung für {len(due)} ISINs")
        budget = float(self.pipeline.get("abruf.identitaet_max_sekunden", 3600))
        block = 200
        for start in range(0, len(due), block):
            if self.elapsed() > budget:
                self.event("identitaet", "Zeitbudget für Identitätsprüfung erreicht – Rest im nächsten Lauf", "WARN")
                break
            batch = due[start : start + block]
            found = self.sources.identity.lookup(batch, budget_s=max(60.0, budget - self.elapsed()))
            for isin in batch:
                if isin not in found:
                    continue  # nicht abgefragt (Drosselung/Budget): bleibt offen
                result = resolve_identity(isin, members.get(isin, {}).get("name", ""), found[isin], self.table, self.method.excluded_security_types)
                repo.save_identity(self.conn, result, self.table, self.sources.price_provider_name)
            self.checkpoint()

    # ---------------------------------------------------------- Kursabruf

    def step_fetch(self, members: dict, refs: dict, D: int) -> bool:
        target = f"{D}:{self.sources.data_mode}"
        repo.clear_old_checkpoints(self.conn, target)
        done = repo.fetched(self.conn, target)
        initial_days = int(self.pipeline.get("abruf.erstimport_kalendertage", 200))
        overlap = int(self.pipeline.get("abruf.inkrementell_ueberlappung_tage", 10))
        full_refresh_days = int(self.pipeline.get("abruf.vollabgleich_alle_tage", 30))
        full_refresh_quota = int(self.pipeline.get("abruf.vollabgleich_max_pro_lauf", 800))
        budget = self.options.time_budget_s
        # Erledigt ist eine Notierung für diesen Stichtag erst mit Kurs am Stichtag (oder ohne Sitzung an
        # diesem Tag). Fehlte der Stichtagskurs oder schlug der Abruf fehl, holt der nächste Versuch sie
        # erneut – Anbieter liefern Schlusskurse teils verspätet nach.
        retry = {listing_id for listing_id, status in done.items() if status in FETCH_RETRY_STATUSES}
        todo = [(isin, refs[isin]) for isin in sorted(members) if isin in refs and (refs[isin]["id"] not in done or refs[isin]["id"] in retry)]
        self.event("kurse", f"Kursabruf: {len(todo)} Notierungen offen (davon {len(retry)} erneut: ohne Stichtagskurs oder Fehler), {len(done) - len(retry)} bereits erledigt (Checkpoint)")
        full_refreshes = 0
        # ab 1.6: Historien kürzer als der Erstimport (früher 200 Tage) mit einem vollen Abruf verlängern – kostet
        # nichts extra (ein Abruf wie der tägliche), wird aber je Notierung höchstens alle 7 Tage versucht
        extend_quota = int(self.pipeline.get("abruf.historie_verlaengern_max_pro_lauf", 4000))
        extended = 0
        fetched = errors = without_cutoff = 0
        now = self.now()
        symbols = SymbolSearchBudget(
            max_listings=int(self.pipeline.get("abruf.kuerzel_alternativen_max_pro_lauf", 300)),
            max_seconds=float(self.pipeline.get("abruf.kuerzel_alternativen_max_sekunden", 900)),
        )
        # Ab 1.17 wird vorab je Notierung entschieden, ob ein voller Abruf fällig ist (gleiche Regeln und Kontingente
        # wie bisher) – der Sammelabruf übernimmt nur Notierungen ohne fälligen Vollabruf.
        plans: dict[int, tuple[int | None, int | None, int, bool]] = {}
        for isin, listing in todo:
            code = listing["calendar_code"]
            if not code or not self.sources.calendars.available(code):
                continue
            revision = int(listing["data_revision"])
            first_day, last_day, count = repo.bar_range(self.conn, listing["id"], revision)
            need_full = count == 0
            if not need_full and listing["last_full_fetch_at"]:
                age = (now - parse_iso_utc(listing["last_full_fetch_at"])).days
                if age >= full_refresh_days and full_refreshes < full_refresh_quota:
                    need_full = True
                    full_refreshes += 1
                elif first_day is not None and int(first_day) > D - initial_days + 30 and age >= 7 and extended < extend_quota:
                    need_full = True
                    extended += 1
            plans[listing["id"]] = (first_day, last_day, count, need_full)
        batch_note = ""
        if self.batch_fetch_enabled():
            todo, throttled, batch_counts = self.step_fetch_batch(todo, plans, target, D, now)
            fetched += batch_counts["uebernommen"]
            without_cutoff += batch_counts["ohne_stichtag"]
            batch_note = f"; davon {batch_counts['uebernommen']} aus dem Sammelabruf"
            if throttled:
                self.event("kurse", "Anbieter drosselt beim Sammelabruf – Checkpoint gesetzt, Rest im nächsten Versuch", "WARN")
                self.checkpoint(force=True)
                return True
        # Ab 1.17: Die Chart-Abrufe laufen (je nach abruf.chart_gleichzeitig) gleichzeitig voraus; ausgewertet, geprüft
        # und gespeichert wird weiter Notierung für Notierung in diesem Thread – in derselben Reihenfolge wie bisher.
        grace = int(self.pipeline.get("stichtag.karenz_minuten_nach_schluss", 60))
        finals: dict[str, Callable[[int], bool]] = {}
        queued: list[tuple[str, Any, int, bool]] = []
        jobs: list[HistoryJob] = []
        for isin, listing in todo:
            code = listing["calendar_code"]
            if not code or not self.sources.calendars.available(code):
                repo.mark_fetched(self.conn, target, listing["id"], "kein_kalender")
                continue
            if code not in finals:
                finals[code] = session_final_checker(self.sources.calendars, code, now, grace)
            revision = int(listing["data_revision"])
            first_day, last_day, count, need_full = plans[listing["id"]]
            start_day = D - initial_days if need_full else int(last_day) - overlap
            queued.append((isin, listing, revision, need_full))
            jobs.append(HistoryJob(listing["provider_symbol"], start_day, D + 3, finals[code]))
        fetch_stats = HistoryFetchStats()
        parallel = getattr(self.sources.prices, "fetch_histories", None)
        if callable(parallel):
            outcomes = parallel(
                jobs,
                workers=int(self.pipeline.get("abruf.chart_gleichzeitig", 1)),
                interval_s=float(self.pipeline.get("abruf.chart_abstand_sekunden", 0.25)),
                stats=fetch_stats,
            )
        else:
            outcomes = fetch_histories_sequential(self.sources.prices, jobs, fetch_stats)
        self.fetch_stats = fetch_stats
        try:
            for k, outcome in outcomes:
                isin, listing, revision, need_full = queued[k]
                final = jobs[k].session_final
                code = listing["calendar_code"]
                if self.elapsed() > budget:
                    self.event("kurse", "Zeitbudget erreicht – Rest wird im nächsten Versuch fortgesetzt", "WARN")
                    return True
                no_data: str | None = None
                if isinstance(outcome, ProviderThrottled):
                    self.event("kurse", f"Anbieter drosselt bei {listing['provider_symbol']} – Checkpoint gesetzt", "WARN")
                    self.checkpoint(force=True)
                    return True
                if isinstance(outcome, NoDataError):
                    no_data = str(outcome)
                elif isinstance(outcome, BaseException):
                    errors += 1
                    repo.update_listing_fetch(self.conn, listing["id"], status="fehler", error=str(outcome)[:300])
                    repo.mark_fetched(self.conn, target, listing["id"], "fehler")
                    continue
                else:
                    history = outcome
                if not self._store_fetched(isin, listing, history if no_data is None else None, no_data, need_full, revision, final, D, target, symbols, initial_days):
                    return True
                if self._last_store_counted:
                    fetched += 1
                    without_cutoff += self._last_store_without_cutoff
                    if fetched % 100 == 0:
                        self.checkpoint()
        finally:
            closer = getattr(outcomes, "close", None)
            if callable(closer):
                closer()
            if fetch_stats.requests:
                self.event("kurse", self.fetch_stats_text(fetch_stats))
        self.event("kurse", f"Kursabruf beendet: {fetched} aktualisiert{batch_note}, davon {without_cutoff} ohne Kurs am Stichtag; {errors} Einzelfehler (isoliert)"
                   + (f"; Historie auf {initial_days} Tage verlängert: {extended}" if extended else ""))
        if self.quote_closes or self.quote_replaced:
            self.event(
                "kurse",
                f"Schlusskurs aus der Kursmeldung (Tageskerze beim Anbieter noch ohne Schlusskurs): {self.quote_closes} Notierungen am Stichtag; "
                f"{self.quote_replaced} frühere durch die nachgelieferte Tageskerze ersetzt",
            )
        if symbols.tried:
            found = symbols.found_spelling + symbols.found_search
            self.event(
                "kurse",
                f"Andere Kürzel für Notierungen ohne Kursdaten: {symbols.tried} geprüft, {found} gefunden "
                f"({symbols.found_spelling} andere Schreibweise, {symbols.found_search} Suche nach ISIN)",
            )
        self.checkpoint(force=True)
        return False

    @staticmethod
    def fetch_stats_text(stats: HistoryFetchStats) -> str:
        """Protokollzeile zum Chart-Abruf (nur Zahlen): Dauer, Tempo, gleichzeitig oder einzeln, Drosselung."""
        how = (
            f"{stats.workers} gleichzeitig über {stats.hosts} Hosts, Abstand {stats.interval_s:.2f} s je Host"
            if stats.workers > 1
            else "nacheinander"
        )
        text = f"Chart-Abruf: {stats.requests} Abrufe in {stats.seconds:.0f} s ({stats.per_second:.1f} je Sekunde; {how})"
        if stats.throttled_after is not None:
            text += f"; Drosselung (HTTP 429) nach {stats.throttled_after} Abrufen – danach {stats.careful} einzeln mit dem bisherigen Abstand"
        elif stats.http_429:
            text += f"; {stats.http_429} × HTTP 429 mit Wiederholung"
        return text

    def _store_fetched(self, isin: str, listing, history, no_data: str | None, need_full: bool, revision: int, final, D: int, target: str, symbols, initial_days: int) -> bool:
        """Eine abgerufene Notierung prüfen und speichern (wie bis 1.16 im Abruf-Loop). ``False``: Lauf unterbrechen
        (Drosselung bei der Suche nach einem anderen Kürzel – Checkpoint ist gesetzt)."""
        self._last_store_counted = False
        self._last_store_without_cutoff = 0
        code = listing["calendar_code"]
        if no_data is not None:
            # Kennt der Anbieter das Kürzel nicht, eine andere Schreibweise derselben Notierung versuchen
            try:
                found = self.symbol_alternative(isin, listing, D - initial_days, D + 3, final, symbols)
            except ProviderThrottled:
                self.event("kurse", f"Anbieter drosselt bei der Suche nach einem anderen Kürzel für {listing['provider_symbol']} – Checkpoint gesetzt", "WARN")
                self.checkpoint(force=True)
                return False
            if found is None:
                repo.update_listing_fetch(self.conn, listing["id"], status="keine_daten", error=no_data)
                repo.mark_fetched(self.conn, target, listing["id"], "keine_daten")
                return True
            listing, history = found
            need_full = True  # neue Kursreihe: als eigene Revision speichern, nie mit alten Kursen mischen
        else:
            ok, why = self.verify_listing(isin, listing, history)
            if not ok:
                repo.mark_identity_unclear(self.conn, isin, why)
                repo.mark_fetched(self.conn, target, listing["id"], "identitaet_unklar")
                self.event("identitaet", f"{isin}: {why}", "WARN")
                return True
        self.store_history(listing, history, need_full, revision)
        if D in history.close_from_quote:
            self.quote_closes += 1
        if D in history.days or self.sources.calendars.session_close_utc(code, D) is None:
            repo.mark_fetched(self.conn, target, listing["id"], "ok")
        else:
            repo.mark_fetched(self.conn, target, listing["id"], "ohne_stichtag")
            self._last_store_without_cutoff = 1
        self._last_store_counted = True
        return True

    # ------------------------------------------------- Sammelabruf (ab 1.17)

    def batch_fetch_enabled(self) -> bool:
        """Sammelabruf der Tageskurse: abschaltbar über ``abruf.sammelabruf`` und nur mit einem Anbieter, der ihn kann."""
        if not bool(self.pipeline.get("abruf.sammelabruf", True)):
            return False
        return callable(getattr(self.sources.prices, "fetch_recent", None))

    def step_fetch_batch(self, todo: list, plans: dict, target: str, D: int, now: dt.datetime) -> tuple[list, bool, dict]:
        """Ergänzt Notierungen mit gespeicherter Kursreihe aus Sammelabfragen (siehe ``jobs/increment.py``).

        Übernommen wird eine Notierung nur, wenn die Planung eindeutig ist und danach der Kurs am Stichtag vorliegt
        (oder ihre Börse am Stichtag keine Sitzung hatte). Alles andere – auch eine Sitzung am Stichtag, die in den
        Sammeldaten fehlt – geht unverändert an den Chart-Abruf. Rückgabe: Notierungen für den Chart-Abruf,
        ob der Anbieter drosselt, Zählungen."""
        from collections import Counter

        from ..providers.yahoo import QUOTE_FIELDS_BAR
        from .increment import ACTION_NEW, ACTION_SINGLE, StoredTail, plan_increment, session_days

        grace = int(self.pipeline.get("stichtag.karenz_minuten_nach_schluss", 60))
        counts = {"uebernommen": 0, "ohne_stichtag": 0, "neu": 0, "aktuell": 0, "einzeln": 0}
        candidates: list = []
        rest: list = []
        for isin, listing in todo:
            plan = plans.get(listing["id"])
            if plan is None:
                rest.append((isin, listing))  # ohne Börsenkalender: der Chart-Weg vermerkt das wie bisher
                continue
            _, last_day, count, need_full = plan
            confirmed = listing["provider_type"] is not None and listing["provider_name"] is not None
            if need_full or count == 0 or last_day is None or not confirmed:
                rest.append((isin, listing))
                continue
            candidates.append((isin, listing))
        if not candidates:
            return rest, False, counts
        started = time.monotonic()
        budget = float(self.pipeline.get("abruf.sammelabruf_max_sekunden", 900))
        recent = self.sources.prices.fetch_recent([listing["provider_symbol"] for _, listing in candidates], budget_s=budget)
        finals: dict[str, Callable[[int], bool]] = {}

        def final_for(code: str):
            if code not in finals:
                finals[code] = session_final_checker(self.sources.calendars, code, now, grace)
            return finals[code]

        # Kursmeldungen (Eröffnung, Hoch, Tief, Umsatz) nur für Notierungen mit neuer abgeschlossener Sitzung
        need_quote = []
        for _, listing in candidates:
            bars = recent.bars.get(listing["provider_symbol"])
            if bars is None:
                continue
            last_day = int(plans[listing["id"]][1])
            days = session_days(bars.timestamps, bars.exchange_tz or listing["exchange_tz"])
            final = final_for(listing["calendar_code"])
            if any(int(day) > last_day and final(int(day)) for day in days.tolist()):
                need_quote.append(listing["provider_symbol"])
        quotes: dict = {}
        quote_requests = 0
        throttled = recent.throttled
        if need_quote and not throttled:
            fetched_quotes = self.sources.prices.fetch_quotes(need_quote, budget_s=budget, fields=QUOTE_FIELDS_BAR, spark_fallback=False)
            quotes = fetched_quotes.quotes
            quote_requests = fetched_quotes.quote_requests or fetched_quotes.requests
            throttled = throttled or fetched_quotes.throttled
        reasons: Counter = Counter()
        sources_used: Counter = Counter()
        for isin, listing in candidates:
            symbol = listing["provider_symbol"]
            bars = recent.bars.get(symbol)
            if bars is None:
                if not (throttled and recent.missing.get(symbol) == "Kursanbieter drosselt"):
                    reasons["keine_sammeldaten"] += 1
                    rest.append((isin, listing))
                # gedrosselt: bleibt offen und kommt im nächsten Versuch wieder
                continue
            if bars.currency and listing["price_unit"] and bars.currency != listing["price_unit"]:
                reasons["waehrung"] += 1  # Währungswechsel prüft und hält der Chart-Weg zurück
                rest.append((isin, listing))
                continue
            revision = int(listing["data_revision"])
            stored = repo.load_bars(self.conn, listing["id"], revision, D - 60)
            tail = StoredTail(stored["days"], stored["close"], stored["quality"], stored["volume"])
            code = listing["calendar_code"]
            plan = plan_increment(tail, bars, quotes.get(symbol), tz_name=listing["exchange_tz"], session_final=final_for(code), symbol=symbol, fetched_at=now)
            if plan.action == ACTION_SINGLE:
                reasons[plan.reason] += 1
                rest.append((isin, listing))
                continue
            days_after = set(int(d) for d in tail.days.tolist())
            if plan.action == ACTION_NEW and plan.new_day is not None:
                days_after.add(int(plan.new_day))
            if D not in days_after and self.sources.calendars.session_close_utc(code, D) is not None:
                reasons["stichtag_fehlt"] += 1  # Sitzung am Stichtag, aber kein Kurs in den Sammeldaten: Chart-Weg
                rest.append((isin, listing))
                continue
            if plan.action == ACTION_NEW and plan.history is not None:
                repo.store_bars(self.conn, listing["id"], revision, plan.history)
                for key, value in plan.sources.items():
                    sources_used[f"{key}:{value}"] += 1
                counts["neu"] += 1
            else:
                counts["aktuell"] += 1
            repo.update_listing_fetch(self.conn, listing["id"], status="ok")
            repo.mark_fetched(self.conn, target, listing["id"], "ok")
            counts["uebernommen"] += 1
            if counts["uebernommen"] % 500 == 0:
                self.checkpoint()
        counts["einzeln"] = sum(reasons.values())
        seconds = time.monotonic() - started
        self.batch_stats = {
            "notierungen": len(candidates),
            "sekunden": round(seconds, 1),
            "spark_abrufe": recent.requests,
            "quote_abrufe": quote_requests,
            "neu": counts["neu"],
            "aktuell": counts["aktuell"],
            "einzeln": counts["einzeln"],
            "gruende": dict(reasons.most_common()),
            "herkunft": dict(sources_used),
            "gedrosselt": bool(throttled),
        }
        why = ", ".join(f"{name} {n}" for name, n in reasons.most_common(6)) or "keine"
        self.event(
            "kurse",
            f"Sammelabruf: {len(candidates)} Notierungen mit gespeicherter Kursreihe in {seconds:.0f} s ({recent.requests} Spark-Abrufe, "
            f"{quote_requests} Kursabfragen): {counts['neu']} neue Tageskerzen, {counts['aktuell']} ohne neue Sitzung, "
            f"{counts['einzeln']} einzeln über den Chart-Abruf ({why})",
        )
        self.checkpoint(force=True)
        return rest, bool(throttled), counts

    def symbol_alternative(self, isin: str, listing, start_day: int, end_day: int, final, budget: SymbolSearchBudget) -> tuple[dict, PriceHistory] | None:
        """Andere Schreibweise derselben Notierung, wenn der Kursanbieter das Kürzel nicht kennt.

        Versucht werden andere Schreibweisen (z. B. „ADDT-B.ST“ statt „ADDTB.ST“) und Treffer der Suche
        nach der ISIN – nur an derselben Börse. Jeder Treffer muss die Plausibilitätsprüfung bestehen
        (Instrumenttyp, Zeitzone, Börsencode, Währung, Name). Ein Versuch je Notierung und Wiederholfrist;
        gefundene Kürzel ersetzen das alte und bleiben auch nach der nächsten Identitätsprüfung erhalten.
        """
        exchange = self.table.exchanges.get(listing["exchange_key"] or "")
        if exchange is None:
            return None
        old = listing["provider_symbol"]
        search = self.sources.symbol_search
        if search is None and not self.table.symbol_variants(exchange, old):
            return None  # nichts zu versuchen
        retry_days = int(self.pipeline.get("abruf.kuerzel_alternativen_wiederholen_tage", 30))
        if not repo.symbol_alternative_due(self.conn, listing["id"], self.now(), retry_days):
            return None
        if not budget.available():
            if not budget.exhausted_logged:
                budget.exhausted_logged = True
                self.event("kuerzel", "Kontingent für die Suche nach anderen Kürzeln erreicht – weitere Notierungen in den nächsten Läufen")
            return None
        budget.tried += 1
        started = time.monotonic()
        try:
            hits = []
            if search is not None:
                try:
                    hits = search.search(isin, self.table)
                except ProviderThrottled:
                    raise
                except (ProviderError, ConnectionError, ValueError) as exc:
                    LOG.info("Suche nach %s: %s", isin, exc)
            candidates = alternative_symbols(self.table, exchange.key, old, hits)[:3]
            alias_rows = repo.aliases(self.conn, [isin]).get(isin, [])
            names = {
                "tr": next((alias for alias, kind in alias_rows if kind == "tr_name"), ""),
                "quelle": next((alias for alias, kind in alias_rows if kind == "name"), ""),
                "alle": [alias for alias, kind in alias_rows if kind in ("tr_name", "name")],
            }
            for symbol, how in candidates:
                try:
                    history = self.sources.prices.fetch_history(symbol, start_day, end_day, session_final=final)
                except ProviderThrottled:
                    raise
                except (ProviderError, ConnectionError, ValueError):
                    continue  # unbekannt oder ohne Kurse: nächster Kandidat
                ok, why = self.verify_alternative(listing, symbol, history, names)
                if not ok:
                    self.event("kuerzel", f"{isin}: Kürzel {symbol} verworfen – {why}")
                    continue
                if not repo.update_listing_symbol(self.conn, listing["id"], symbol):
                    self.event("kuerzel", f"{isin}: Kürzel {symbol} gehört bereits zu einer anderen Notierung – nicht übernommen")
                    continue
                repo.record_symbol_alternative(self.conn, listing["id"], old, symbol)
                repo.add_alias(self.conn, isin, symbol, "symbol", self.sources.price_provider_name)
                if how == "schreibweise":
                    budget.found_spelling += 1
                else:
                    budget.found_search += 1
                label = "andere Schreibweise" if how == "schreibweise" else "Suche nach ISIN"
                self.event("kuerzel", f"{isin}: Kürzel {old} → {symbol} ({label}, {exchange.name})")
                updated = dict(listing)
                updated["provider_symbol"] = symbol
                return updated, history
            repo.record_symbol_alternative(self.conn, listing["id"], old, None)
            return None
        finally:
            budget.seconds += time.monotonic() - started

    def verify_alternative(self, listing, symbol: str, history: PriceHistory, names: dict) -> tuple[bool, str]:
        """Plausibilitätsprüfung für ein anderes Kürzel (immer vollständig, auch bei bestätigter Notierung).

        ``names``: TR-Name („tr“), Name laut Identitätsquelle („quelle“) und alle bekannten Namen („alle“).
        """
        if self.sources.data_mode != "demo":
            from ..providers.base import ListingCandidate
            from ..providers.identity import IdentityResult

            reference = ListingCandidate(
                source="gespeichert",
                exchange_key=listing["exchange_key"],
                provider_symbol=symbol,
                ticker=listing["ticker"],
                exch_code=None,
                name=names["quelle"] or None,
            )
            result = IdentityResult("", "verifiziert", "unklar", reference, "", [reference], {"tr": names["tr"]})
            ok, why = verify_against_prices(
                result,
                provider_exchange_code=history.exchange_name,
                provider_tz=history.exchange_tz,
                provider_type=history.instrument_type,
                provider_name=history.long_name or history.short_name,
                table=self.table,
            )
            if not ok:
                return False, why
        return plausible_alternative(history.long_name or history.short_name, history.currency, listing["price_unit"] or listing["currency"], names["alle"])

    def verify_listing(self, isin: str, listing, history: PriceHistory) -> tuple[bool, str]:
        if self.sources.data_mode == "demo":
            return True, "DEMO"
        if listing["provider_type"] is not None and listing["provider_name"] is not None:
            return True, "bereits bestätigt"
        from ..providers.identity import IdentityResult
        from ..providers.base import ListingCandidate

        names = {"tr": next((a for a, k in repo.aliases(self.conn, [isin]).get(isin, []) if k == "tr_name"), "")}
        reference = ListingCandidate(
            source="gespeichert",
            exchange_key=listing["exchange_key"],
            provider_symbol=listing["provider_symbol"],
            ticker=listing["ticker"],
            exch_code=None,
            name=next((a for a, k in repo.aliases(self.conn, [isin]).get(isin, []) if k == "name"), None),
        )
        result = IdentityResult(isin, "verifiziert", "unklar", reference, "", [reference], names)
        return verify_against_prices(
            result,
            provider_exchange_code=history.exchange_name,
            provider_tz=history.exchange_tz,
            provider_type=history.instrument_type,
            provider_name=history.long_name or history.short_name,
            table=self.table,
        )

    def store_history(self, listing, history: PriceHistory, full: bool, revision: int) -> None:
        listing_id = listing["id"]
        stored_currency = listing["price_unit"]
        if history.currency and listing["last_fetch_status"] == "ok" and stored_currency and stored_currency != history.currency:
            repo.set_listing_hold(self.conn, listing_id, True, f"Notierungswährung geändert: {stored_currency} → {history.currency}")
            self.event("pruefung", f"{listing['provider_symbol']}: Währungswechsel {stored_currency} → {history.currency} – zurückgehalten", "WARN")
        new_splits = repo.store_corporate_actions(self.conn, listing_id, history)
        if new_splits:
            repo.mark_long_history_refresh(self.conn, listing_id)  # ältere Wochenkurse neu laden
        revised = False
        if not full and revision > 0:
            existing = repo.load_bars(self.conn, listing_id, revision, int(history.days[0]) if len(history) else None)
            overlap = np.intersect1d(existing["days"], history.days)
            if len(overlap):
                pos = np.searchsorted(existing["days"], overlap)
                old = existing["close"][pos]
                new = history.close[np.searchsorted(history.days, overlap)]
                # Schlusskurse aus der Kursmeldung sind vorläufig: ihr Ersatz durch die Tageskerze ist keine Korrektur
                provisional = (existing["quality"][pos] & repo.QUALITY_CLOSE_FROM_QUOTE) != 0
                provisional |= np.isin(overlap, np.asarray(history.close_from_quote, dtype=np.int64))
                changed = (np.abs(new / old - 1.0) > 1e-6) & ~provisional
                replaced = provisional & ~np.isin(overlap, np.asarray(history.close_from_quote, dtype=np.int64))
                self.quote_replaced += int(replaced.sum())
                if changed.any() or new_splits:
                    revised = True
        if revised:
            reason = "neuer Split gemeldet" if new_splits else "Anbieter hat zurückliegende Kurse korrigiert"
            self.event("revision", f"{listing['provider_symbol']}: {reason} – Historie wird neu eingelesen")
            start = int(history.days[0]) - int(self.pipeline.get("abruf.erstimport_kalendertage", 200))
            history = self.sources.prices.fetch_history(listing["provider_symbol"], start, int(history.days[-1]) + 1)
            full = True
        if full:
            revision = repo.new_revision(self.conn, listing_id, "Vollabruf" if not revised else "Korrektur")
            repo.store_bars(self.conn, listing_id, revision, history)
            repo.finalize_revision(self.conn, listing_id, revision)
            repo.prune_old_revisions(self.conn, listing_id, revision)
        else:
            repo.store_bars(self.conn, listing_id, revision, history)
        repo.update_listing_fetch(self.conn, listing_id, status="ok", full=full, meta=history)

    # ------------------------------------------------------- Wechselkurse

    def step_fx(self, D: int) -> FxRates | None:
        """EZB-Referenzkurse abrufen und sichern; bei Ausfall die gespeicherten Kurse verwenden.

        Ein Abruf je Lauf (90 Tage). Ohne ausreichend aktuelle Kurse bleibt der Umsatz anderer
        Währungen unbestimmt – die Aktien fehlen dann in Ranking 2, nicht in Ranking 1.
        """
        source = self.sources.fx
        if source is None:
            return None
        label = getattr(source, "name", "Referenzkurse")
        url = getattr(source, "url", None)
        fetched_at: str | None = None
        try:
            fetched = source.fetch()
            repo.store_fx_rates(self.conn, fetched.rows, source=fetched.source, fetched_at=fetched.fetched_at)
            label, url, fetched_at = fetched.source, fetched.url, fetched.fetched_at
            latest = max(day for day, _, _ in fetched.rows)
            currencies = len({currency for _, currency, _ in fetched.rows})
            self.event("wechselkurse", f"{currencies} Währungen je EUR bis {day_to_iso(latest)} ({fetched.source})")
        except Exception as exc:  # Ausfall der Quelle darf den Lauf nicht stoppen
            self.event("wechselkurse", f"Referenzkurse nicht abrufbar ({type(exc).__name__}: {exc}) – gespeicherte Kurse werden verwendet", "WARN")
        self.ensure_fx_history(source, D)
        repo.prune_fx_rates(self.conn, D - self.long_days() - 60)
        rows = repo.fx_rates_since(self.conn, D - 150)
        if not rows:
            self.event("wechselkurse", "Keine Referenzkurse vorhanden – Umsatz in USD nur für USD-Notierungen bestimmbar", "WARN")
            return None
        if fetched_at is None:
            fetched_at = max(row["fetched_at"] for row in rows)
            label = rows[-1]["source"]
        return FxRates.from_rows(
            [(int(row["day"]), row["currency"], float(row["per_eur"])) for row in rows],
            source=label,
            url=url,
            fetched_at=fetched_at,
            max_age_days=self.method.fx_max_age_days,
        )

    def long_days(self) -> int:
        return int(self.method.rotation.history_years) * 365 + 120

    def ensure_fx_history(self, source, D: int) -> None:
        """EZB-Kurshistorie für die Rückschau der Umschichtungs-Regel (einmalig bzw. wenn ältere Kurse fehlen)."""
        fetch_history = getattr(source, "fetch_history", None)
        if fetch_history is None:
            return
        first = self.conn.execute("SELECT MIN(day) FROM fx_rate").fetchone()[0]
        wanted = D - self.long_days()
        if first is not None and int(first) <= wanted + 30:
            return
        try:
            fetched = fetch_history(wanted - 30)
            repo.store_fx_rates(self.conn, fetched.rows, source=fetched.source, fetched_at=fetched.fetched_at)
            self.event("wechselkurse", f"EZB-Kurshistorie ab {day_to_iso(wanted - 30)} geladen ({len(fetched.rows)} Kurse)")
        except Exception as exc:  # die Regel rechnet dann mit kürzerer Rückschau
            self.event("wechselkurse", f"EZB-Kurshistorie nicht abrufbar ({type(exc).__name__}: {exc}) – Rückblick-Test kürzer", "WARN")

    def long_fx(self, D: int) -> FxRates | None:
        rows = repo.fx_rates_since(self.conn, D - self.long_days() - 60)
        if not rows:
            return None
        return FxRates.from_rows(
            [(int(row["day"]), row["currency"], float(row["per_eur"])) for row in rows],
            source=rows[-1]["source"],
            url=None,
            fetched_at=max(row["fetched_at"] for row in rows),
            max_age_days=self.method.fx_max_age_days,
        )

    # ---------------------------------------------------------- Berechnung

    def step_compute(
        self,
        universe: dict,
        members: dict,
        D: int,
        fx: FxRates | None = None,
        provisional: dict | None = None,
    ) -> tuple[SnapshotComputation, list[InstrumentMeta], dict]:
        """Rechenkern-Eingaben aus der Datenbank und Berechnung. ``provisional`` (Zwischenstand, ab 1.8): je
        ISIN ein vorläufiger Kurs des Tages ``D`` (``ProvisionalBar``), der als letzte Beobachtung angehängt
        wird – nur im Speicher, nie in die gespeicherte Kurshistorie. Aktien ohne Kurs an ``D`` (Börse noch nicht
        geöffnet, Feiertag, Kurs nicht geliefert) zählen mit ihrem letzten Schlusskurs (eigener Stichtag je Aktie,
        Zwischenstand ab 1.13, alle Stände ab tr-methode-1.9.0), siehe ``own_cutoff_day``."""
        loading_started = time.monotonic()
        # Mehrere Durchgänge je Lauf (Kursabgleich, ab 1.20.0): Zähler je Durchgang neu
        self.closing_counts = {}
        self.cutoff_gaps = {}
        ka_run = self.kursabgleich
        if ka_run is not None:
            ka_run.reset_pass()
            if not ka_run.official:
                ka_run.load(D)
        refs = repo.reference_listings(self.conn)
        rows = repo.instruments(self.conn, members)
        alias_map = repo.aliases(self.conn, members)
        reviews = repo.review_map(self.conn)
        start_day = D - 150
        universe_age = (self.now() - parse_iso_utc(universe["retrieved_at"])).days if universe.get("retrieved_at") else 0
        identity_max_age = int(self.pipeline.get("abruf.identitaet_pruefung_alle_tage", 45))
        inputs: list[InstrumentData] = []
        metas: list[InstrumentMeta] = []
        market_stats: dict[str, dict] = {}
        for isin in sorted(members):
            info = members[isin]
            row = rows.get(isin)
            listing = refs.get(isin)
            alias_list = alias_map.get(isin, [])
            # Frühere Namen, Ticker und Symbole bleiben suchbar (Tickerwechsel, Umbenennung); die ISIN bleibt der Schlüssel.
            current = {listing["ticker"], listing["provider_symbol"]} if listing is not None else set()
            names = [a for a, kind in alias_list if kind in ("name", "tr_name", "ticker", "symbol") and a not in current]
            display = (listing["provider_name"] if listing is not None and listing["provider_name"] else None) or (row["full_name"] if row else None) or info["name"]
            warnings = int(row["warnings"]) if row else 0
            if universe_age > 14:
                warnings |= 1 << InstrumentWarning.TR_NACHWEIS_ALT
            if row is not None and row["identity_checked_at"]:
                if (self.now() - parse_iso_utc(row["identity_checked_at"])).days > identity_max_age * 2:
                    warnings |= 1 << InstrumentWarning.IDENTITAET_ALT
            meta = InstrumentMeta(
                isin=isin,
                name=display,
                tr_name=info["name"],
                aliases=sorted({n for n in names if n and n != display}),
                instrument_type=row["instrument_type"] if row else "unklar",
                identity_status=row["identity_status"] if row else "offen",
                identity_reason=row["identity_reason"] if row else None,
            )
            pre = 0
            if not info["valid"] or (row is not None and row["identity_status"] == "isin_ungueltig"):
                pre = Status.ISIN_UNGUELTIG
            elif row is None or row["identity_status"] == "offen":
                pre = Status.IDENTITAET_OFFEN
            elif row["identity_status"] == "kein_aktieninstrument":
                pre = Status.KEIN_AKTIENINSTRUMENT
            elif row["identity_status"] != "verifiziert" or listing is None:
                pre = Status.IDENTITAET_UNKLAR
            if pre:
                inputs.append(InstrumentData(isin=isin, pre_status=int(pre), warnings=warnings))
                metas.append(meta)
                continue
            exchange = self.table.exchanges.get(listing["exchange_key"])
            unit = listing["price_unit"] or (exchange.currency if exchange else None)
            base_currency, unit_to_base = unit_info(unit)
            if unit and base_currency != unit:
                warnings |= 1 << InstrumentWarning.WAEHRUNGS_UNTEREINHEIT
            meta.ticker = listing["ticker"]
            meta.symbol = listing["provider_symbol"]
            meta.exchange_key = listing["exchange_key"]
            meta.exchange_name = listing["exchange_name"]
            meta.mic = listing["mic"]
            meta.tz = listing["exchange_tz"]
            meta.calendar = listing["calendar_code"]
            meta.currency = base_currency
            meta.price_unit = unit
            meta.unit_factor = float(listing["unit_factor"] or 1.0)
            meta.provider = listing["provider"]
            meta.data_revision = int(listing["data_revision"])
            meta.fetched_at = listing["last_fetch_at"]
            code = listing["calendar_code"]
            if not code or not self.sources.calendars.available(code):
                inputs.append(InstrumentData(isin=isin, pre_status=int(Status.KALENDER_FEHLT), warnings=warnings))
                metas.append(meta)
                continue
            sessions = self.sources.calendars.sessions(code, start_day - 30, D)
            bars = repo.load_bars(self.conn, listing["id"], int(listing["data_revision"]), start_day - 30)
            splits = repo.splits_for(self.conn, listing["id"])
            if ka_run is not None and len(bars["days"]):
                # Kursabgleich (ab 1.20.0): Kurse der Börse nach der Auswahlregel – vor dem vorläufigen Kurs des Zwischenstands
                known_names = [n for n in (listing["provider_name"], row["full_name"] if row else None, info["name"], *names) if n]
                bars, check, check_source = ka_run.overlay(isin, listing, known_names, bars, splits, D)
                if check is not None:
                    meta.exchange_check = {"quelle": check_source, "status": check.status, "grund": check.reason}
                    meta.corrections = [
                        {"d": int(c.day), "grund": c.reason, "alt": c.old, "neu": c.new, "boerse_roh": c.official_raw, "quelle": check_source}
                        for c in check.corrections
                    ]
                    if check.adopted and any(c.reason in kursregel.PRICE_REASONS for c in check.corrections):
                        warnings |= 1 << InstrumentWarning.KURS_DER_BOERSE
            if ka_run is not None and ka_run.active and ka_run.us_check.get(int(listing["id"])) == "nicht_gelistet":
                # Zuordnung (ab 1.20.0): laut Wertpapierliste von Nasdaq Trader nicht an einer US-Börse notiert – OTC-Handel
                meta.exchange_key = "OTC"
                meta.exchange_name = "USA OTC-Markt (laut Wertpapierliste von Nasdaq Trader nicht börsennotiert)"
                warnings |= 1 << InstrumentWarning.OTC_NOTIERUNG
            bar = (provisional or {}).get(isin)
            own_cutoff = None
            if bar is None:
                own_cutoff = own_cutoff_day(bars["days"], bars["close"], sessions, D, self.method.last_close_max_missed_sessions)
                if own_cutoff is not None:
                    self.closing_counts[code] = self.closing_counts.get(code, 0) + 1
            if bar is not None:
                keep = bars["days"] < bar.day  # ein vorläufiger Kurs ersetzt nie einen gespeicherten Schlusskurs
                if not np.any(bars["days"] == bar.day):
                    bars = {k: np.append(v[keep], bar.value(k)) for k, v in bars.items()}
                    meta.provisional_day = int(bar.day)
                    meta.provisional_time = bar.time_utc
                    meta.provisional_final = bool(bar.session_closed)
            quote_days = bars["days"][(bars["quality"] & repo.QUALITY_CLOSE_FROM_QUOTE) != 0]
            if len(quote_days):
                warnings |= 1 << InstrumentWarning.SCHLUSSKURS_AUS_KURSMELDUNG
                meta.quote_days = [int(d) for d in quote_days.tolist()]
            if splits:
                meta.events = [{"type": "split", "day": s.day, "factor": s.factor} for s in splits if s.day >= start_day - 30]
                if self.sources.price_provider_name == "yahoo":
                    warnings |= 1 << InstrumentWarning.ROHKURS_REKONSTRUIERT
            meta.sessions = sessions
            meta.ohlc = bars
            inputs.append(
                InstrumentData(
                    isin=isin,
                    sessions=sessions,
                    days=bars["days"],
                    close=bars["close"],
                    volume=bars["volume"],
                    splits=splits,
                    reviewed_jumps=reviews.get(isin, {}),
                    hold_all=bool(listing["hold_all"]),
                    warnings=warnings,
                    currency=base_currency,
                    unit_factor=unit_to_base,
                    provisional_day=meta.provisional_day,
                    cutoff_day=own_cutoff,
                )
            )
            metas.append(meta)
            stats = market_stats.setdefault(code, {"expected": 0, "present": 0, "closed": 0})
            market_open_at_cutoff = len(sessions) > 0 and int(sessions[-1]) == D
            if not market_open_at_cutoff:
                stats["closed"] += 1
            elif len(bars["days"]):
                stats["expected"] += 1
                if bool(np.any(bars["days"] == D)):
                    stats["present"] += 1
                elif len(self.cutoff_gaps.setdefault(code, [])) < 3:
                    before = bars["days"][bars["days"] < D]
                    previous = f"vorher {day_to_iso(int(before.max()))}" if len(before) else "kein früherer Kurs"
                    self.cutoff_gaps[code].append(f"{listing['provider_symbol']} ({previous})")
        self.event("berechnung", f"Berechne {len(inputs)} Instrumente × {len(self.method.windows())} Fenster")
        timings = getattr(self, "timings", None)
        if isinstance(timings, dict):  # Zwischenstand (ab 1.12): Laden aus der Datenbank getrennt vom Rechnen messen
            timings["daten_laden"] = time.monotonic() - loading_started
        comp = compute_snapshot(inputs, D, self.method, fx=fx)
        return comp, metas, market_stats

    def step_kursabgleich(
        self,
        universe: dict,
        members: dict,
        D: int,
        fx: FxRates | None = None,
    ) -> tuple[SnapshotComputation, list[InstrumentMeta], dict]:
        """Kursabgleich mit den Kursarchiven der Börsen (ab 1.20.0, ``jobs/kursabgleich_lauf.py``): Durchgang 0 allein mit
        der Hauptquelle (für die Gegenüberstellung), Abruf der Börsenkurse (alle Aktien an XWAR, Spitzenplätze an XTSE, XTSX,
        XNAS), Durchgang 1 mit der Auswahlregel; neue Spitzenplätze mit eigener Quelle führen zu weiteren Durchgängen."""
        ka_run = self.kursabgleich
        if ka_run is None:
            return self.step_compute(universe, members, D, fx)
        from .kursabgleich_lauf import ranking_lists

        started = time.monotonic()
        deadline = started + ka_run.settings.budget_s
        ka_run.load(D)
        ka_run.active = False
        comp0, _, _ = self.step_compute(universe, members, D, fx)
        before = ranking_lists(comp0)
        refs = repo.reference_listings(self.conn)
        if self.sources.data_mode != "demo":
            ka_run.check_us_listings(refs, members, getattr(ka_run.sources, "http", None))
        ka_run.fetch_day_files(refs, members, D, deadline)
        ka_run.fetch_symbols(ka_run.top_listings(comp0, refs), D, deadline)
        del comp0
        self.checkpoint()
        ka_run.active = True
        comp, metas, market_stats = self.step_compute(universe, members, D, fx)
        ka_run.passes = 1
        while ka_run.passes < ka_run.settings.max_passes and time.monotonic() < deadline:
            new = ka_run.top_listings(comp, refs)
            if not new:
                break
            ka_run.fetched_new = False
            ka_run.fetch_symbols(new, D, deadline)
            if not ka_run.fetched_new:
                break
            comp, metas, market_stats = self.step_compute(universe, members, D, fx)
            ka_run.passes += 1
        ka_run.timings["gesamt"] = time.monotonic() - started
        report = build_report(ka_run, before, comp, metas, D)
        comp.kursabgleich = report
        summary = report["summary"]
        ranks = summary["ranglisten"]
        # Kurzbericht (öffentlich): nur Zählwerte – keine Namen, Kürzel, ISINs oder Kurse
        self.event(
            "kursabgleich",
            f"Kursabgleich {summary['regel']}: {summary['aktien_mit_kurskorrektur']} Aktien mit Kurs der Börse; Platz 1 anders in "
            f"{ranks.get('platz1_anders', 0)} von {ranks.get('ranglisten', 0)} Ranglisten, erste 10 anders in {ranks.get('erste10_andere_aktien', 0)}; "
            f"{ka_run.passes} Durchgänge",
        )
        for source, counts in summary["quellen"].items():
            status = ", ".join(f"{k.split(':', 1)[1]} {v}" for k, v in sorted(counts.items()) if k.startswith("status:"))
            fixes = ", ".join(f"{k.split(':', 1)[1]} {v}" for k, v in sorted(counts.items()) if k.startswith("korrektur:"))
            self.event("kursabgleich", f"{source}: {counts.get('notierungen', 0)} Notierungen ({status}); Korrekturen: {fixes or 'keine'}")
        fetched = ", ".join(f"{k} {v}" for k, v in sorted(ka_run.stats.items()) if not k.startswith("us_zuordnung"))
        if fetched:
            self.event("kursabgleich", f"Abrufe: {fetched}")
        us = summary.get("us_zuordnung") or {}
        if us.get("liste") == "ok":
            self.event("kursabgleich", "US-Zuordnung (Nasdaq Trader): " + ", ".join(f"{k} {v}" for k, v in sorted(us.items()) if k != "liste"))
        return comp, metas, market_stats

    def last_close_info(self) -> dict:
        """Manifest (ab tr-methode-1.9.0): Aktien ohne Kurs am Stichtag, die mit ihrem letzten Schlusskurs zählen."""
        return {
            "aktien": int(sum(self.closing_counts.values())),
            "je_kalender": dict(sorted(self.closing_counts.items())),
            "max_verpasste_sitzungen": int(self.method.last_close_max_missed_sessions),
            "beschreibung": (
                "Aktien ohne Kurs am Stichtag – Feiertag ihrer Börse, Kurs nicht geliefert oder (im Zwischenstand) Börse noch nicht "
                "geöffnet – zählen mit ihrem letzten Schlusskurs; ihre Zeiträume enden an diesem Tag. Ist der letzte Kurs älter als "
                "eine verpasste Börsensitzung, gilt er als veraltet und die Aktie fehlt."
            ),
        }

    def assess_completeness(self, market_stats: dict) -> dict:
        threshold = float(self.pipeline.get("vollstaendigkeit.markt_geliefert_ab", 0.80))
        delivered, missing, expected_total, present_total = [], [], 0, 0
        for code, stats in sorted(market_stats.items()):
            if stats["expected"] == 0:
                continue
            expected_total += stats["expected"]
            present_total += stats["present"]
            share = stats["present"] / stats["expected"]
            (delivered if share >= threshold else missing).append(code)
        markets = len(delivered) + len(missing)
        share = (len(delivered) / markets) if markets else 0.0
        return {
            "status": "vollstaendig" if markets and not missing else "teilstand",
            "share": share,  # Anteil gelieferter Börsen
            "instrument_share": (present_total / expected_total) if expected_total else 0.0,  # Anteil Aktien mit Stichtagskurs
            "delivered_markets": delivered,
            "missing_markets": missing,
            "expected_instruments_at_cutoff": expected_total,
            "present_instruments_at_cutoff": present_total,
            "market_threshold": threshold,
            "per_market": market_stats,
        }

    # ----------------------------------------------------- Veröffentlichung

    def publish(self, universe: dict, comp: SnapshotComputation, metas: list[InstrumentMeta], completeness: dict, D: int) -> RunOutcome:
        # Angezeigte Stammdaten (Name, Ticker, Börse, Identität) gehören zum veröffentlichten Ergebnis:
        # Ein Tickerwechsel oder eine geklärte Identität am selben Stichtag ergibt eine neue Revision.
        shown_meta = [
            [m.isin, m.name, m.tr_name, m.aliases, m.ticker, m.symbol, m.exchange_key, m.exchange_name, m.mic, m.currency, m.price_unit, m.instrument_type, m.identity_status, m.identity_reason]
            for m in metas
        ]
        history = repo.long_history_rows(self.conn).values()
        key_material = {
            "cutoff": D,
            "universe_sha256": universe["sha256"],
            "input": comp.input_hash,
            "instrument_meta": sha256_hex(canonical_bytes(shown_meta)),
            "versions": self.versions,
            "data_mode": self.sources.data_mode,
            "completeness": completeness["status"],
            # Umschichtungs-Regel: mehr geladene Langhistorie ergibt einen neuen Rückblick
            "long_history": sorted((int(r["listing_id"]), r["status"], r["fetched_at"] or "") for r in history),
        }
        idem = sha256_hex(canonical_bytes(key_material))
        existing = repo.snapshot_by_key(self.conn, idem)
        if existing is not None:
            return self.finish("keine_neuen_daten", f"Gleicher Datenstand wie Snapshot {existing['id']} – nichts Neues zu veröffentlichen", EXIT_OK, cutoff_day=D, snapshot_id=existing["id"])
        snapshot_id = f"{day_to_iso(D)}_{idem[:8]}"
        previous_same_day = repo.latest_for_cutoff(self.conn, D, self.sources.data_mode)
        computed_at = iso_utc(self.now())
        planned = self.options.planned_start
        on_time = None
        if planned is not None:
            on_time = (self.now() - planned).total_seconds() <= 3600 and self.attempt == 1
        manifest_base = {
            "data_mode": self.sources.data_mode,
            "cutoff_session_date": day_to_iso(D),
            "cutoff_day": D,
            "computed_at_utc": computed_at,
            "published_at_utc": computed_at,
            "run_id": self.run_id,
            "attempt": self.attempt,
            "completeness": completeness,
            "idempotency_key": idem,
            "supersedes": previous_same_day["id"] if previous_same_day is not None else None,
            "versions": dict(self.versions, data_revision=comp.input_hash, calendar=self.sources.calendars.version()),
            "method": self.method.as_dict(),
            "letzter_schlusskurs": self.last_close_info(),
            "calendar_convention": "kalendertage",
            "currency_basis": "Kursrendite in jeweiliger Notierungswährung; splitbereinigt; ohne Dividenden, Kosten, Steuern und EUR-Wechselkurseffekt.",
            "universe": {
                "universe_snapshot_id": universe["id"],
                "source_url": universe["source_url"],
                "retrieved_at_utc": universe["retrieved_at"],
                "http_last_modified": universe.get("http_last_modified"),
                "pdf_creation_date": universe.get("pdf_creation_date"),
                "sha256": universe["sha256"],
                "parser_version": universe["parser_version"],
                "isin_count": universe["isin_count"],
                "nachweis": "TR-Listung laut offizieller Liste; keine Zusage individueller sofortiger Kaufbarkeit",
            },
            "provider": {
                "prices": self.sources.price_provider_name,
                "calendars": self.sources.calendars.version(),
                "license_note": _license_note(self.sources.price_provider_name),
                "live_data": False,
                "intraday": False,
            },
            "flags": {
                "report_publishable": True,
                "model_validated": False,
                "forecast_eligible": False,
                "original_run_on_time": on_time,
            },
            # Schlusskurse aus der letzten Kursmeldung, weil die Tageskerze beim Anbieter noch unvollständig war
            "kursmeldung": {
                "am_stichtag": sum(1 for m in metas if D in m.quote_days),
                "aktien": sum(1 for m in metas if m.quote_days),
                "beschreibung": "Fehlte beim Kursanbieter nach Börsenschluss noch der Schlusskurs der Tageskerze, gilt der letzte gemeldete Kurs dieser Sitzung (gekennzeichnet). Sobald die Tageskerze nachgeliefert wird, ersetzt sie ihn automatisch.",
            },
        }
        try:
            comp.venue = self.step_venues(comp, metas, D)
        except Exception as exc:  # nur ein Hinweis: ein Fehler im Abgleich darf die Veröffentlichung nicht verhindern
            comp.wflags &= np.uint16(~(1 << WindowWarning.BOERSENPLATZ_ABWEICHUNG) & 0xFFFF)
            comp.venue = VenueCheck(version=self.method.venue_version, settings=self.method.venue_settings(), aborted=True)
            comp.venue.note = f"Abgleich wegen eines Fehlers übersprungen ({type(exc).__name__}); Ranglisten unverändert"
            self.event("boersenplatz", f"{comp.venue.note}: {exc}", "WARN")
        comp.rotation = self.step_rotation(comp, metas, D)
        checks = run_checks(comp, self.method)
        manifest_base["checks"] = checks
        if not all(c["passed"] for c in checks):
            failed = [c["name"] for c in checks if not c["passed"]]
            return self.finish("fehlgeschlagen", f"Konsistenzprüfung fehlgeschlagen: {', '.join(failed)}", EXIT_FAILED, cutoff_day=D)
        repo.update_run(self.conn, self.run_id, status="geprueft")
        if self.kursabgleich is not None and comp.kursabgleich is not None:
            stored = self.kursabgleich.store_corrections(self.run_id)
            repo.prune_exchange_bars(self.conn, D - self.kursabgleich.settings.range_days - 60)
            self.event("kursabgleich", f"Nachweis gespeichert: {stored} Korrekturen (Tabelle kurskorrektur)")

        snapshots_dir = self.state_dir / "snapshots"
        writer = SnapshotWriter(comp, metas, self.method, snapshot_id=snapshot_id, key=self.key)
        manifest = writer.write(snapshots_dir, manifest_base)
        archives = self.state_dir / "archives"
        site_name = f"site-{snapshot_id}.tar"
        evidence_name = f"evidence-{snapshot_id}.tra"
        atomic_write_bytes(archives / site_name, snapshot_tar(snapshots_dir / snapshot_id))
        evidence = evidence_archive(comp, manifest)
        atomic_write_bytes(archives / evidence_name, crypto.pack(evidence, self.key, f"archive/{evidence_name}"))
        summary = {
            "snapshot_id": snapshot_id,
            "cutoff_session_date": day_to_iso(D),
            "computed_at_utc": computed_at,
            "completeness": completeness["status"],
            "data_mode": self.sources.data_mode,
            "universe_count": comp.n_instruments,
            "return_eligible_30": manifest["coverage"]["per_window"][29]["return_eligible"],
            "trend_eligible_30": manifest["coverage"]["per_window"][29]["trend_eligible"],
            "supersedes": manifest_base["supersedes"],
            "versions": manifest_base["versions"],
        }
        repo.insert_snapshot(
            self.conn,
            id=snapshot_id,
            idempotency_key=idem,
            cutoff_day=D,
            computed_at=computed_at,
            published_at=computed_at,
            completeness=completeness["status"],
            data_mode=self.sources.data_mode,
            universe_id=universe["id"],
            run_id=self.run_id,
            supersedes=manifest_base["supersedes"],
            summary_json=json.dumps(summary, ensure_ascii=False),
            site_archive=site_name,
            evidence_archive=evidence_name,
            status="veroeffentlicht",
        )
        self.apply_retention()
        self.step_aktienpilot(comp, metas, D, snapshot_id)
        label = "Teilstand" if completeness["status"] != "vollstaendig" else "vollständig"
        return self.finish(
            "veroeffentlicht",
            f"Snapshot {snapshot_id} ({label}) veröffentlicht",
            EXIT_OK,
            cutoff_day=D,
            snapshot_id=snapshot_id,
            data_revision=comp.input_hash,
            details=completeness,
        )

    # ------------------------------------------------- Spielgeld-Robo (AktienPilot)

    def step_aktienpilot(self, comp: SnapshotComputation, metas: list[InstrumentMeta], D: int, snapshot_id: str) -> dict | None:
        """Spielgelddepots mit demselben Rechenstand weiterführen (Abschnitt 29.5). Ein Fehler hier verhindert nie die
        Veröffentlichung der Ranglisten; im Protokoll stehen nur Zahlen, keine Depotinhalte."""
        try:
            from ..aktienpilot import tageslauf
            from ..aktienpilot.config import load_aktienpilot_config

            cfg = load_aktienpilot_config()
            if not cfg.aktiv:
                return None
            summary = tageslauf.ausfuehren(
                self.conn, cfg=cfg, method=self.method, comp=comp, metas=metas, D=D, fx=comp.fx, calendars=self.sources.calendars,
                provider=self.sources.prices, run_id=self.run_id, now=self.now(), key=self.key, snapshot_id=snapshot_id,
                data_mode=self.sources.data_mode, log=lambda text: self.event("spielgeld", text),
            )
            return summary
        except Exception as exc:  # nur ein Hinweis: die Ranglisten sind bereits veröffentlicht
            self.event("spielgeld", f"Spielgeld-Robo übersprungen ({type(exc).__name__}: {str(exc)[:200]})", "WARN")
            return None

    # ------------------------------------------------- Zweiter Börsenplatz

    def step_venues(self, comp: SnapshotComputation, metas: list[InstrumentMeta], D: int) -> VenueCheck | None:
        """Abgleich der vorderen Plätze beider Rendite-Ranglisten mit einem zweiten Börsenplatz.

        Nur ein Hinweis: setzt das Fensterkennzeichen „Kursabweichung zwischen Börsenplätzen“, ändert
        aber weder Rendite noch Rang. Läuft erst, wenn feststeht, dass veröffentlicht wird. Zeitbudget
        und Anbieterlimits beenden den Schritt vorzeitig; nicht geprüfte Aktien sind so gekennzeichnet.
        """
        settings = self.method.venue_settings()
        check = VenueCheck(version=self.method.venue_version, settings=settings)
        source = self.sources.venues
        if source is None or settings.top_n == 0 or settings.max_instruments == 0:
            check.note = "Abgleich mit einem zweiten Börsenplatz ist in dieser Umgebung nicht eingerichtet"
            self.event("boersenplatz", check.note)
            return check
        indices, total = candidate_indices(comp.rankings, comp.windows, settings.top_n, settings.max_instruments)
        check.candidates = total
        if total > len(indices):
            check.note = f"Obergrenze erreicht: {len(indices)} von {total} Aktien geprüft (beste Plätze zuerst)"
        if not indices:
            return check
        started = time.monotonic()
        budget = min(
            float(self.pipeline.get("abruf.boersenplatz_max_sekunden", 900)),
            max(60.0, self.options.time_budget_s + 900.0 - self.elapsed()),
        )

        def remaining() -> float:
            return budget - (time.monotonic() - started)

        # 1. Zweiten Börsenplatz wählen (gespeichert; nach einiger Zeit neu geprüft)
        isins = [comp.isins[i] for i in indices]
        position = {isin: i for i, isin in zip(indices, isins)}
        max_age = int(self.pipeline.get("abruf.boersenplatz_pruefung_alle_tage", 45))
        stored = repo.venue_listings(self.conn, isins)
        now = self.now()
        due = [isin for isin in isins if isin not in stored or (now - parse_iso_utc(stored[isin]["checked_at"])).days >= max_age]
        for start in range(0, len(due), 100):
            if remaining() <= 0:
                break
            batch = due[start : start + 100]
            try:
                found = source.lookup(batch, budget_s=max(10.0, remaining()))
            except ProviderThrottled:
                self.event("boersenplatz", "Identitätsquelle drosselt – übrige Aktien im nächsten Lauf", "WARN")
                break
            except (ProviderError, ConnectionError, ValueError) as exc:
                self.event("boersenplatz", f"Suche nach zweitem Börsenplatz fehlgeschlagen: {exc}", "WARN")
                break
            for isin in batch:
                if isin not in found:
                    continue  # nicht abgefragt (Drosselung/Budget): bleibt offen
                meta = metas[position[isin]]
                choice = choose_venue(
                    found[isin], reference_symbol=meta.symbol, reference_exchange=meta.exchange_key, table=self.table, preferred=settings.preferred
                )
                repo.save_venue_listing(
                    self.conn,
                    isin,
                    symbol=choice.provider_symbol if choice else None,
                    exchange_key=choice.exchange_key if choice else None,
                    source=choice.source if choice else None,
                )
        stored = repo.venue_listings(self.conn, isins)

        # 2. Schlusskurse am zweiten Börsenplatz laden und vergleichen
        publishable = np.isin(comp.status, [int(x) for x in RETURN_PUBLISHABLE])
        grace = int(self.pipeline.get("stichtag.karenz_minuten_nach_schluss", 60))
        bit = np.uint16(1 << WindowWarning.BOERSENPLATZ_ABWEICHUNG)
        stopped: str | None = None
        broken_calendars: set[str] = set()
        for idx in indices:
            isin = comp.isins[idx]
            meta = metas[idx]
            row = stored.get(isin)
            if row is None:  # Suche nicht abgeschlossen (Zeitbudget, Drosselung)
                check.results[idx] = InstrumentVenue("nicht_geprueft")
                continue
            exchange = self.table.exchanges.get(row["exchange_key"] or "")
            if row["status"] != "gefunden" or exchange is None:
                check.results[idx] = InstrumentVenue("kein_vergleichsplatz")
                continue
            if stopped is None and remaining() <= 0:
                stopped = "Zeitbudget für den Börsenplatz-Abgleich erreicht"
            if stopped is not None:
                check.results[idx] = InstrumentVenue("nicht_geprueft", symbol=row["provider_symbol"], exchange_key=exchange.key, exchange_name=exchange.name)
                continue
            cols = [col for col in range(len(comp.windows)) if publishable[idx, col]]
            if not cols:
                continue
            first = int(min(comp.start_day[idx, col] for col in cols)) - settings.max_gap_days - 3
            final = None
            alt_sessions = None  # ohne Kalender des Vergleichsplatzes: Regel von boersenplatz-v1
            if self.sources.calendars.available(exchange.calendar):
                final = session_final_checker(self.sources.calendars, exchange.calendar, now, grace)
                try:
                    alt_sessions = self.sources.calendars.sessions(exchange.calendar, first, D)
                except Exception as exc:  # ohne Kalender kein Vergleich nach v2 – lieber „nicht geprüft“ als eine andere Regel
                    if exchange.calendar not in broken_calendars:
                        broken_calendars.add(exchange.calendar)
                        self.event("boersenplatz", f"Börsenkalender {exchange.calendar} nicht lesbar ({exc}) – Aktien mit diesem zweiten Börsenplatz nicht geprüft", "WARN")
                    check.results[idx] = InstrumentVenue("nicht_geprueft", symbol=row["provider_symbol"], exchange_key=exchange.key, exchange_name=exchange.name)
                    continue
            try:
                history = self.sources.prices.fetch_history(row["provider_symbol"], first, D, session_final=final)
            except ProviderThrottled:
                stopped = "Kursanbieter drosselt beim Börsenplatz-Abgleich"
                check.results[idx] = InstrumentVenue("nicht_geprueft")
                continue
            except (NoDataError, ProviderError, ConnectionError, ValueError):
                check.results[idx] = InstrumentVenue(
                    "abruf_fehlgeschlagen", symbol=row["provider_symbol"], exchange_key=exchange.key, exchange_name=exchange.name
                )
                continue
            unit = history.price_unit or history.currency or exchange.currency
            base, factor = unit_info(unit)
            alt = AltSeries(
                symbol=row["provider_symbol"],
                exchange_key=exchange.key,
                exchange_name=exchange.name,
                currency=base,
                price_unit=unit,
                unit_factor=factor,
                days=history.days,
                close=history.close,
                volume=history.volume,
            )
            observed = comp.observed.get(idx)
            noise = robust_daily_noise(observed.close, settings.noise_sessions) if observed is not None else None
            result = compare_instrument(
                cols=cols,
                start_days=comp.start_day[idx],
                r_ref=comp.r[idx],
                p1_ref=float(comp.p1[idx, cols[0]]),
                cutoff_day=D,
                ref_currency=meta.currency,
                ref_unit_factor=unit_info(meta.price_unit)[1],
                alt=alt,
                fx=comp.fx,
                settings=settings,
                alt_sessions=alt_sessions,
                ref_noise=noise,
            )
            check.results[idx] = result
            for col, pair in result.pairs.items():
                if pair.status == "abweichung":
                    comp.wflags[idx, col] |= bit
            self.checkpoint()
        if stopped is not None:
            self.event("boersenplatz", f"{stopped} – übrige Aktien als „nicht geprüft“ gekennzeichnet", "WARN")
            check.note = "; ".join(x for x in (check.note, stopped) if x)
        counts = check.counts()
        by_status = counts["aktien"]
        pairs = counts["aktie_zeitraum"]
        self.event(
            "boersenplatz",
            # Wichtigste Zahlen vorn: der Kurzbericht in GitHub kürzt Zeilen nach 160 Zeichen
            f"Börsenplatz-Abgleich: {by_status.get('geprueft', 0)} von {total} Aktien geprüft, {counts['auffaellige_aktien']} auffällig; "
            f"Zeiträume: {pairs.get('abweichung', 0)} auffällig, {pairs.get('ok', 0)} unauffällig, {pairs.get('keine_kurse', 0)} ohne Vergleichskurse; "
            f"ohne zweiten Börsenplatz {by_status.get('kein_vergleichsplatz', 0)}, Kurse nicht abrufbar {by_status.get('abruf_fehlgeschlagen', 0)}, "
            f"nicht geprüft {by_status.get('nicht_geprueft', 0)} (erste {settings.top_n} Plätze beider Rendite-Ranglisten)",
        )
        diag = check.diagnostics()
        if diag["feste_schwelle_auffaellig"] or diag["schwelle_median"] is not None:
            pct = lambda x: "–" if x is None else f"{x * 100:.0f} %"  # noqa: E731
            self.event(
                "boersenplatz",
                f"Börsenplatz-Abgleich, Auswertung: nach fester 10-%-Regel {diag['feste_schwelle_auffaellig']} Zeiträume ({diag['feste_schwelle_aktien']} Aktien) auffällig – "
                f"davon {diag['davon_ohne_umsatz']} ohne Umsatz am Vergleichsplatz, {diag['davon_in_schwankungsbreite']} innerhalb der üblichen Schwankung, "
                f"{diag['davon_weiter_auffaellig']} weiter auffällig; Schwelle Wertentwicklung Median {pct(diag['schwelle_median'])}, höchstens {pct(diag['schwelle_max'])}, "
                f"über 10 % bei {diag['schwelle_erhoeht_aktien']} Aktien",
            )
        return check

    # ------------------------------------------------- Umschichtungs-Regel

    def step_long_history(self, comp: SnapshotComputation, metas: list[InstrumentMeta], D: int, *, fetch: bool = True) -> None:
        """Wochenwerte für den Rückblick-Test der Umschichtungs-Regel pflegen.

        1. Aufnahme: Aktien mit Ø Tagesumsatz ab der Vorauswahlschwelle (heute) bekommen eine
           Langhistorie; einmal aufgenommen, bleiben sie (sonst fehlten früher liquide Aktien).
        2. Langabruf (bis 3 Jahre) für neu aufgenommene oder nach einem Split neu zu ladende Aktien,
           begrenzt je Lauf; Rest im nächsten Lauf.
        3. Jüngere Wochen in jedem Lauf aus den geprüften Tageskursen neu verdichten.
        """
        cfg = self.method.rotation
        refs = repo.reference_listings(self.conn)
        position = {isin: i for i, isin in enumerate(comp.isins)}
        pool = []
        for i, result in enumerate(comp.turnover or []):
            listing = refs.get(comp.isins[i])
            if listing is not None and result.determined and result.avg_usd >= cfg.pool_min_turnover_usd:
                pool.append(int(listing["id"]))
        added = repo.ensure_long_history(self.conn, pool)
        rows = repo.long_history_rows(self.conn)
        by_id = {int(listing["id"]): (isin, listing) for isin, listing in refs.items()}
        # Langabruf
        limit = int(self.pipeline.get("abruf.langhistorie_max_pro_lauf", 2500))
        budget = float(self.pipeline.get("abruf.langhistorie_max_sekunden", 900))
        started = time.monotonic()
        loaded = failed = 0
        stop_reason = None
        first_day = D - self.long_days()
        due = repo.long_history_due(self.conn, limit) if fetch else []
        if not fetch and repo.long_history_due(self.conn, 1):
            stop_reason = "Anbieter drosselt"
        for listing_id in due:
            if time.monotonic() - started > budget:
                stop_reason = "Zeitbudget erreicht"
                break
            if listing_id not in by_id:
                continue
            isin, listing = by_id[listing_id]
            code = listing["calendar_code"]
            if not code or not self.sources.calendars.available(code):
                repo.set_long_history(self.conn, listing_id, "keine_daten", error="kein Börsenkalender")
                continue
            try:
                history = self.sources.prices.fetch_history(listing["provider_symbol"], first_day, D)
            except ProviderThrottled:
                stop_reason = "Anbieter drosselt"
                break
            except NoDataError as exc:
                repo.set_long_history(self.conn, listing_id, "keine_daten", error=str(exc)[:200])
                failed += 1
                continue
            except (ProviderError, ConnectionError, ValueError) as exc:
                repo.set_long_history(self.conn, listing_id, rows.get(listing_id, {"status": "offen"})["status"] if listing_id in rows else "offen", error=str(exc)[:200])
                failed += 1
                continue
            sessions = self.sources.calendars.sessions(code, first_day, D)
            keep = np.isin(history.days, sessions) & (history.days <= D)
            weeks = fridays(int(first_day), D)
            agg = aggregate_weeks(history.days[keep], history.close[keep], history.volume[keep], weeks, sessions=sessions)
            repo.store_week_bars(self.conn, listing_id, agg)
            first_week = next((int(w) for w, c in zip(agg.week_ends.tolist(), agg.close.tolist()) if c == c), None)
            repo.set_long_history(self.conn, listing_id, "ok", first_week=first_week)
            loaded += 1
            self.checkpoint()
        # jüngere Wochen aus den geprüften Tageskursen
        refreshed = 0
        for listing_id in repo.long_history_rows(self.conn):
            if listing_id not in by_id:
                continue
            isin, _ = by_id[listing_id]
            i = position.get(isin)
            obs = comp.observed.get(i) if i is not None else None
            meta = metas[i] if i is not None else None
            if obs is None or meta is None or meta.sessions is None or not len(obs.days):
                continue
            weeks = fridays(int(obs.days[0]), D)
            if not len(weeks):
                continue
            agg = aggregate_weeks(obs.days, obs.close, obs.volume, weeks, sessions=meta.sessions)
            # die erste Woche ist meist nur teilweise in den Tageskursen enthalten → nicht überschreiben
            repo.store_week_bars(self.conn, listing_id, _drop_first_week(agg))
            refreshed += 1
        repo.prune_week_bars(self.conn, D - self.long_days() - 14)
        status = repo.long_history_rows(self.conn)
        done = sum(1 for r in status.values() if r["status"] == "ok")
        open_ = sum(1 for r in status.values() if r["status"] in ("offen", "erneut"))
        message = (
            f"Wochenwerte für die Umschichtungs-Regel: {len(status)} Aktien in der Vorauswahl (+{added} neu), "
            f"Langhistorie {done} geladen, {open_} offen; in diesem Lauf {loaded} geladen, {failed} ohne Daten, {refreshed} aktualisiert"
        )
        self.event("umschichtung", message + (f" – {stop_reason}, Rest im nächsten Lauf" if stop_reason else ""))

    def step_rotation(self, comp: SnapshotComputation, metas: list[InstrumentMeta], D: int):
        """Rückblick-Test aller Varianten und Tagesvorschlag (nur bei Veröffentlichung)."""
        cfg = self.method.rotation
        refs = repo.reference_listings(self.conn)
        position = {isin: i for i, isin in enumerate(comp.isins)}
        listing_ids = list(repo.long_history_rows(self.conn))
        id_to_isin = {int(listing["id"]): isin for isin, listing in refs.items()}
        members = [(lid, id_to_isin[lid]) for lid in listing_ids if lid in id_to_isin and id_to_isin[lid] in position]
        members.sort(key=lambda item: item[1])
        fx = self.long_fx(D) or comp.fx
        rule = rot.UniverseRule(
            min_turnover_usd=cfg.min_turnover_usd,
            turnover_weeks=cfg.turnover_weeks,
            min_positive_share=cfg.min_positive_share,
            min_coverage=cfg.min_coverage,
            max_jump=float(np.log(cfg.max_jump_factor)),
        )
        costs = rot.CostModel(fee=cfg.fee_eur, spread=cfg.spread, tax_rate=cfg.tax_rate, allowance=cfg.allowance_eur)
        grid = fridays(D - self.long_days(), D)
        outcome = RotationOutcome(config=cfg, rule=rule, costs=costs, day=D)
        history = repo.long_history_rows(self.conn).values()
        outcome.history = {
            "aktien": len(history),
            "geladen": sum(1 for r in history if r["status"] == "ok"),
            "offen": sum(1 for r in history if r["status"] in ("offen", "erneut")),
            "ohne_daten": sum(1 for r in history if r["status"] == "keine_daten"),
        }
        if not members or not len(grid) or fx is None:
            outcome.note = "Noch keine Wochenwerte oder Wechselkurse – die Regel rechnet, sobald Daten vorliegen"
            self.event("umschichtung", outcome.note)
            return outcome
        rows_by_listing = repo.week_bars_since(self.conn, [lid for lid, _ in members], int(grid[0]))
        rate_cache: dict[tuple[str | None, str], tuple[np.ndarray, np.ndarray]] = {}

        def unit_rates(currency: str | None, which: str, weeks: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            """EUR und USD je Währungseinheit an jedem Wochenende (NaN = kein ausreichend aktueller Kurs)."""
            key = (currency, which)
            if key not in rate_cache:
                eur = np.full(len(weeks), np.nan)
                usd = np.full(len(weeks), np.nan)
                if currency:
                    for k, week_end in enumerate(weeks.tolist()):
                        e = fx.eur_per_unit(currency, int(week_end))
                        u = fx.usd_per_unit(currency, int(week_end))
                        eur[k] = e if e is not None else np.nan
                        usd[k] = u[0] if u is not None else np.nan
                rate_cache[key] = (eur, usd)
            return rate_cache[key]

        panel = _empty_panel(len(members), grid)
        column = {int(w): k for k, w in enumerate(grid.tolist())}
        now_weeks = rolling_week_ends(D, max(cfg.lookback_weeks) + cfg.turnover_weeks + 1)
        now = _empty_panel(len(members), now_weeks)
        for r, (listing_id, isin) in enumerate(members):
            i = position[isin]
            meta = metas[i]
            panel.idx[r] = now.idx[r] = i
            panel.isins.append(isin)
            now.isins.append(isin)
            for row in rows_by_listing.get(listing_id, []):
                k = column.get(int(row["week_end"]))
                if k is None:
                    continue
                panel.close[r, k] = row["close"] if row["close"] is not None else np.nan
                panel.turnover[r, k] = row["turnover"]
                panel.with_data[r, k] = row["with_data"]
                panel.positive[r, k] = row["positive"]
                panel.observed[r, k] = row["observed"]
                panel.sessions[r, k] = row["sessions"]
                panel.jump[r, k] = row["jump"]
                panel.first_close[r, k] = row["first_close"] if row["first_close"] is not None else np.nan
                panel.first_day[r, k] = row["first_day"] if row["first_day"] is not None else -1
            obs = comp.observed.get(i)
            if obs is not None and meta.sessions is not None:
                agg = aggregate_weeks(obs.days, obs.close, obs.volume, now_weeks, sessions=meta.sessions)
                now.close[r], now.turnover[r], now.with_data[r] = agg.close, agg.turnover, agg.with_data
                now.positive[r], now.observed[r], now.sessions[r], now.jump[r] = agg.positive, agg.observed, agg.sessions, agg.jump
                now.first_close[r], now.first_day[r] = agg.first_close, agg.first_day
            currency, factor = meta.currency, unit_info(meta.price_unit)[1]
            for target, weeks, which in ((panel, grid, "raster"), (now, now_weeks, "jetzt")):
                eur, usd = unit_rates(currency, which, weeks)
                target.unit_eur[r] = eur * factor
                target.unit_usd[r] = usd * factor
        outcome.pool = len(members)
        outcome.grid = grid
        outcome.first_week_with_data = next((int(grid[k]) for k in range(len(grid)) if np.isfinite(panel.close[:, k]).any()), None)
        for holdings in cfg.holdings:
            for rhythm in cfg.rhythms:
                for lookback in cfg.lookback_weeks:
                    for capital in cfg.capitals:
                        variant = rot.RuleVariant(holdings=holdings, rhythm=rhythm, lookback_weeks=lookback, capital=capital, keep_rank_factor=cfg.keep_rank_factor, band=cfg.band)
                        result = rot.backtest(panel, variant, costs, rule)
                        outcome.results[variant.key] = result
                        outcome.previews[variant.key] = rot.preview(now, result, variant, rule, D)
        outcome.panel_idx = panel.idx.copy()
        default = rot.RuleVariant(cfg.default_holdings, cfg.default_rhythm, cfg.default_lookback_weeks, cfg.default_capital, cfg.keep_rank_factor, cfg.band)
        outcome.default_key = default.key
        main = outcome.results.get(default.key)
        stats = main.stats() if main is not None else {}
        if stats:
            self.event(
                "umschichtung",
                f"Umschichtungs-Regel ({default.holdings} Aktien, {default.rhythm}, {default.lookback_weeks} Wochen): Rückblick "
                f"{day_to_iso(stats['start_day'])}–{day_to_iso(stats['end_day'])}, {len(members)} Aktien mit Wochenwerten, "
                f"{stats['umschichtungen']} Umschichtungen, {stats['orders']} Orders",
            )
        else:
            self.event("umschichtung", f"Umschichtungs-Regel: noch zu wenig Wochenwerte für einen Rückblick ({len(members)} Aktien)")
        return outcome

    def apply_retention(self) -> None:
        keep_bars = max(200, int(self.pipeline.get("aufbewahrung.kurs_historie_tage", 430)))
        newest = self.conn.execute("SELECT MAX(session_day) FROM daily_bar").fetchone()[0]
        if newest:
            repo.prune_old_bars(self.conn, int(newest) - keep_bars)

    # --------------------------------------------------------------- Status

    def write_status(self, status: str, message: str) -> None:
        build_status_file(
            self.conn,
            self.state_dir,
            self.sources.data_mode,
            self.pipeline,
            last_run_id=self.run_id,
            now=self.now(),
            next_cutoff=getattr(self, "next_cutoff", None),
            # Bricht ein Lauf vor dem Stichtag ab, bleibt der zuletzt bekannte nächste Kursstand stehen (ab 1.17)
            keep_next=True,
        )


def _license_note(provider: str) -> str:
    if provider == "yahoo":
        return ("Kursdaten: Yahoo Finance (inoffizielle Schnittstelle, keine Lizenz für einen Massendatenfeed; "
                "nur private Auswertung). Kursquelle ist nicht der TR-Ausführungsplatz.")
    if provider == "eodhd":
        return "Kursdaten: EODHD (lizenzierter Datenvertrag des Nutzers). Kursquelle ist nicht der TR-Ausführungsplatz."
    return "DEMO – synthetische Testdaten, keine echten Kurse."


def build_status_file(
    conn,
    state_dir: Path,
    data_mode: str,
    pipeline: PipelineConfig,
    *,
    last_run_id: str | None,
    now: dt.datetime,
    next_cutoff: NextCutoff | None = None,
    keep_next: bool = False,
) -> dict:
    """Schreibt ``site_meta/status.json``, ``site_meta/index.json`` und (ab 1.6) ``site_meta/signale.json``
    aus der Datenbank. ``keep_next``: den zuletzt berechneten nächsten Kursstand übernehmen (für Schritte
    nach dem eigentlichen Lauf, die ihn nicht selbst bestimmen)."""
    previous_next = None
    if keep_next and next_cutoff is None:
        try:
            previous_next = json.loads((Path(state_dir) / "site_meta" / "status.json").read_text(encoding="utf-8")).get("naechster_kursstand")
        except (OSError, ValueError):
            previous_next = None
        if previous_next is None:
            # Ab 1.17: Auf einem frischen Rechner (Job „Kennzahlen“, „Nur die Website“) fehlt die Datei – dann gilt der
            # beim letzten Lauf in der Datenbank vermerkte nächste Kursstand (bis 1.16 fehlte er danach in status.json).
            try:
                previous_next = json.loads(repo.kv_get(conn, NEXT_CUTOFF_KV) or "null")
            except ValueError:
                previous_next = None
    last_run = conn.execute("SELECT * FROM run WHERE id = ?", (last_run_id,)).fetchone() if last_run_id else None
    published = repo.published_snapshots(conn, data_mode)
    if next_cutoff is not None:
        current_next = {"datum": day_to_iso(next_cutoff.day), "ab_utc": iso_utc(next_cutoff.ready_utc), "boersen": next_cutoff.markets}
        repo.kv_set(conn, NEXT_CUTOFF_KV, json.dumps(current_next, ensure_ascii=False))
    else:
        current_next = previous_next if isinstance(previous_next, dict) else None
        # Ein übernommener Wert, der nicht mehr nach dem veröffentlichten Stand liegt, ist überholt
        if current_next is not None and published and str(current_next.get("datum") or "") <= day_to_iso(published[0]["cutoff_day"]):
            current_next = None
    complete = [r for r in published if r["completeness"] == "vollstaendig"]
    # Zwischenstand (ab 1.8): nur, solange er neuer ist als der neueste offizielle Stand
    intraday = repo.current_intraday(conn, data_mode)
    intraday_summary = json.loads(intraday["summary_json"]) if intraday is not None else None
    last_success = conn.execute(
        "SELECT finished_at FROM run WHERE status IN ('veroeffentlicht', 'keine_neuen_daten') AND data_mode = ? ORDER BY finished_at DESC LIMIT 1",
        (data_mode,),
    ).fetchone()
    schedule = pipeline.get("zeitplan", {}) or {}
    status = {
        "schema": "tr-status/1",
        "generated_at_utc": iso_utc(now),
        "app_mode": data_mode,
        "latest_snapshot_id": published[0]["id"] if published else None,
        "latest_complete_snapshot_id": complete[0]["id"] if complete else None,
        "last_price_session": day_to_iso(published[0]["cutoff_day"]) if published else None,
        "last_successful_check_utc": last_success[0] if last_success else None,
        "last_run": None
        if last_run is None
        else {
            "run_id": last_run["id"],
            "trigger": last_run["trigger"],
            "planned_start_utc": last_run["planned_start"],
            "started_at_utc": last_run["started_at"],
            "finished_at_utc": last_run["finished_at"],
            "status": last_run["status"],
            "message": last_run["status_detail"],
            "cutoff_session_date": day_to_iso(last_run["cutoff_day"]) if last_run["cutoff_day"] is not None else None,
            "attempt": last_run["attempt"],
        },
        "schedule": {
            "uhrzeit": schedule.get("uhrzeit", "07:00"),
            "zeitzone": schedule.get("zeitzone", "Europe/Berlin"),
            "wiederholungen_minuten": schedule.get("wiederholungen_minuten", [15, 45, 120]),
            # Ab 1.17: Nachtlauf (UTC, Wochentage 1 = Montag … 7 = Sonntag); fehlt, wenn keiner eingerichtet ist
            "nachtlauf_utc": schedule.get("nachtlauf_utc"),
            "nachtlauf_wochentage": schedule.get("nachtlauf_wochentage"),
        },
        "heartbeat_max_age_hours": int(pipeline.get("betrieb.heartbeat_max_stunden", 30)),
        "software_version": __version__,
        # Ab wann ein Lauf neue Schlusskurse bringen kann (gleiche Regel wie der Kursstichtag)
        "naechster_kursstand": current_next,
        "latest_official_snapshot_id": published[0]["id"] if published else None,
    }
    snapshots = [json.loads(r["summary_json"]) | {"published_at_utc": r["published_at"]} for r in published]
    if intraday is not None and intraday_summary is not None:
        status["zwischenstand"] = {
            "snapshot_id": intraday["id"],
            "stichtag": day_to_iso(int(intraday["cutoff_day"])),
            "kurse_bis_utc": intraday["quotes_until"],
            "erstellt_utc": intraday["created_at"],
            "aktien_mit_kurs": intraday_summary.get("aktien_mit_kurs"),
            "offizieller_stand": intraday["official_id"],
            # Gestaffelte Aktualisierung (ab 1.10): Stufe 1 = zuerst die wichtigsten Aktien, Stufe 2 = alle
            "stufe": intraday_summary.get("stufe"),
        }
        status["latest_snapshot_id"] = intraday["id"]
        snapshots = [intraday_summary | {"published_at_utc": intraday["created_at"]}] + snapshots
    index = {
        "schema": "tr-snapshot-index/1",
        "snapshots": snapshots,
    }
    meta_dir = Path(state_dir) / "site_meta"
    atomic_write_json(meta_dir / "status.json", status)
    atomic_write_json(meta_dir / "index.json", index)
    stands = repo.signal_stands(conn, 1)
    if stands:
        summary = json.loads(stands[0]["summary_json"])
        summary.pop("kandidaten", None)
        atomic_write_json(meta_dir / "signale.json", summary)
    _pilot_export(conn, Path(state_dir), data_mode)
    return status


def _pilot_export(conn, state_dir: Path, data_mode: str) -> None:
    """Neuesten Spielgeld-Stand (bereits verschlüsselt) als Datei für die Website ablegen – im Betrieb nur, wenn die
    Veröffentlichung in ``config/aktienpilot.yaml`` eingeschaltet ist (Abschnitt 0: Anzeige erst nach Freigabe); im DEMO immer
    (synthetische Daten zum Prüfen). ``site_meta/pilot.json`` enthält nur Kennung, Zeit und Schema."""
    from ..aktienpilot import stand as pilot_stand
    from ..aktienpilot.config import load_aktienpilot_config

    meta = state_dir / "site_meta" / "pilot.json"
    try:
        cfg = load_aktienpilot_config()
    except Exception:  # Konfiguration fehlerhaft: nichts veröffentlichen
        cfg = None
    latest = pilot_stand.neuester(conn)
    if cfg is None or latest is None or not (cfg.veroeffentlichen or data_mode == "demo"):
        if meta.exists():
            meta.unlink()
        return
    stand_id, created, blob = latest
    target = state_dir / "pilot" / stand_id / "pilot.bin"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)
    for old in (state_dir / "pilot").iterdir():  # nur der neueste Stand liegt als Datei bereit (ältere bleiben in ap_stand)
        if old.is_dir() and old.name != stand_id:
            shutil.rmtree(old, ignore_errors=True)
    atomic_write_json(meta, {"id": stand_id, "erstellt_utc": created, "schema": pilot_stand.SCHEMA})


def _drop_first_week(agg):
    """Wochenwerte ohne die erste Woche (in den Tageskursen meist unvollständig)."""
    return agg.select(slice(1, None))


def _empty_panel(n: int, weeks: np.ndarray) -> rot.WeeklyPanel:
    w = len(weeks)
    return rot.WeeklyPanel(
        idx=np.zeros(n, dtype=np.int64),
        week_ends=np.asarray(weeks, dtype=np.int64),
        close=np.full((n, w), np.nan),
        turnover=np.zeros((n, w)),
        with_data=np.zeros((n, w), dtype=np.int32),
        positive=np.zeros((n, w), dtype=np.int32),
        observed=np.zeros((n, w), dtype=np.int32),
        sessions=np.zeros((n, w), dtype=np.int32),
        jump=np.zeros((n, w)),
        unit_eur=np.full((n, w), np.nan),
        unit_usd=np.full((n, w), np.nan),
        first_close=np.full((n, w), np.nan),
        first_day=np.full((n, w), -1, dtype=np.int64),
        isins=[],
    )


@dataclass
class RotationOutcome:
    """Ergebnis der Umschichtungs-Regel für einen Datenstand (alle Varianten)."""

    config: object
    rule: object
    costs: object
    day: int
    pool: int = 0
    grid: np.ndarray | None = None
    first_week_with_data: int | None = None
    default_key: str | None = None
    results: dict = field(default_factory=dict)
    previews: dict = field(default_factory=dict)
    panel_idx: np.ndarray | None = None
    note: str | None = None
    history: dict = field(default_factory=dict)  # Langhistorie: aktien, geladen, offen, ohne_daten
