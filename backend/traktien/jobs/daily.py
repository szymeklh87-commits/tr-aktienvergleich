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
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from .. import __version__
from ..analytics.codes import InstrumentWarning, Status
from ..analytics.engine import InstrumentData, SnapshotComputation, compute_snapshot
from ..analytics.fx import FxRates
from ..analytics.quality import SplitEvent
from ..config import MethodConfig, PipelineConfig
from ..providers.base import NoDataError, PriceHistory, ProviderError, ProviderThrottled
from ..providers.exchanges import ExchangeTable, unit_info
from ..providers.identity import resolve_identity, verify_against_prices
from ..providers.tr_universe import evaluate_new_universe
from ..publish.checks import run_checks
from ..publish.snapshot_writer import SCHEMA as API_SCHEMA, InstrumentMeta, SnapshotWriter, evidence_archive, snapshot_tar
from ..store import repo
from ..util import crypto
from ..util.jsonio import atomic_write_bytes, atomic_write_json, canonical_bytes, sha256_hex
from ..util.log import get_logger
from ..util.timeutil import day_to_iso, iso_utc, parse_iso_utc
from .cutoff import determine_cutoff, session_final_checker
from .sources import Sources

LOG = get_logger(__name__)
LOCK_NAME = "taeglicher-lauf"

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_LOCKED = 2
EXIT_RETRY = 75

# Abrufstatus, die der nächste Versuch für denselben Stichtag erneut abruft
FETCH_RETRY_STATUSES = frozenset({"ohne_stichtag", "fehler"})


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
        # Je Markt einige Notierungen ohne Kurs am Stichtag (für den Kurzbericht des Laufs)
        self.cutoff_gaps: dict[str, list[str]] = {}
        self.versions = {
            "software": __version__,
            "method": method.method_version,
            "metrics": method.metrics_version,
            "ranking": method.ranking_version,
            "frequency": method.frequency_version,
            "turnover": method.turnover_version,
            "method_fingerprint": method.fingerprint(),
            "exchanges": table.version,
            "api_schema": API_SCHEMA,
        }

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
        if not available_codes:
            return self.finish("fehlgeschlagen", "Keine Referenznotierung mit verfügbarem Börsenkalender", EXIT_FAILED)
        cutoff = determine_cutoff(
            available_codes,
            self.sources.calendars,
            self.now(),
            grace_minutes=int(self.pipeline.get("stichtag.karenz_minuten_nach_schluss", 60)),
        )
        D = cutoff.cutoff_day
        self.attempt = repo.attempts_for_cutoff(self.conn, D, self.sources.data_mode) + 1
        repo.update_run(self.conn, self.run_id, cutoff_day=D)
        self.conn.execute("UPDATE run SET attempt = ? WHERE id = ?", (self.attempt, self.run_id))
        self.event("stichtag", f"Kursstichtag {day_to_iso(D)} (Börsen mit Sitzung: {', '.join(cutoff.markets_with_session)}); Versuch {self.attempt}")

        latest = repo.latest_for_cutoff(self.conn, D, self.sources.data_mode)
        if latest is not None and latest["completeness"] == "vollstaendig" and latest["universe_id"] == universe["id"] and not self.options.force_publish:
            return self.finish(
                "keine_neuen_daten",
                f"Kein neuer abgeschlossener Börsentag seit {day_to_iso(D)}; letzter Stand bleibt gültig",
                EXIT_OK,
                cutoff_day=D,
                snapshot_id=latest["id"],
            )

        throttled = self.step_fetch(members, refs, D)
        fx = self.step_fx(D)
        comp, metas, market_stats = self.step_compute(universe, members, D, fx)
        completeness = self.assess_completeness(market_stats)
        repo.update_run(self.conn, self.run_id, data_revision=comp.input_hash)

        status_partial = completeness["status"] != "vollstaendig"
        if (throttled or status_partial) and self.attempt < self.options.max_attempts and not self.options.force_publish:
            repo.update_run(self.conn, self.run_id, status="wartet_auf_provider")
            reason = "Anbieter drosselt" if throttled else f"Daten für {', '.join(completeness['missing_markets']) or 'einzelne Märkte'} noch unvollständig"
            return self.finish("wartet_auf_provider", f"{reason}; nächster Versuch geplant", EXIT_RETRY, cutoff_day=D, details=completeness)
        if completeness["share"] < float(self.pipeline.get("vollstaendigkeit.teilstand_mindestens", 0.90)) and not self.options.force_publish:
            return self.finish("fehlgeschlagen", f"Nur {completeness['share']:.0%} der erwarteten Märkte geliefert – kein Teilstand veröffentlicht", EXIT_FAILED, cutoff_day=D, details=completeness)

        repo.update_run(self.conn, self.run_id, status="teilweise_berechnet" if status_partial else "vollstaendig_berechnet")
        return self.publish(universe, comp, metas, completeness, D)

    # ---------------------------------------------------------- Universum

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
        previous_members = {k: v["name"] for k, v in repo.universe_members(self.conn, previous["id"]).items()} if previous else None
        if previous is not None and previous["sha256"] == meta["sha256"]:
            repo.insert_universe(self.conn, meta, parsed.entries, "akzeptiert", "unverändert bestätigt", previous["id"], 0, 0)
            self.event("universum", f"TR-Liste unverändert ({len(parsed.entries)} ISINs), bestätigt am {meta['retrieved_at']}")
            return dict(repo.universe_by_id(self.conn, meta["id"]))
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
        fetched = errors = without_cutoff = 0
        now = self.now()
        for isin, listing in todo:
            if self.elapsed() > budget:
                self.event("kurse", "Zeitbudget erreicht – Rest wird im nächsten Versuch fortgesetzt", "WARN")
                return True
            code = listing["calendar_code"]
            if not code or not self.sources.calendars.available(code):
                repo.mark_fetched(self.conn, target, listing["id"], "kein_kalender")
                continue
            final = session_final_checker(self.sources.calendars, code, now, int(self.pipeline.get("stichtag.karenz_minuten_nach_schluss", 60)))
            revision = int(listing["data_revision"])
            _, last_day, count = repo.bar_range(self.conn, listing["id"], revision)
            need_full = count == 0
            if not need_full and listing["last_full_fetch_at"]:
                age = (now - parse_iso_utc(listing["last_full_fetch_at"])).days
                if age >= full_refresh_days and full_refreshes < full_refresh_quota:
                    need_full = True
                    full_refreshes += 1
            start_day = D - initial_days if need_full else int(last_day) - overlap
            try:
                history = self.sources.prices.fetch_history(listing["provider_symbol"], start_day, D + 3, session_final=final)
            except ProviderThrottled:
                self.event("kurse", f"Anbieter drosselt bei {listing['provider_symbol']} – Checkpoint gesetzt", "WARN")
                self.checkpoint(force=True)
                return True
            except NoDataError as exc:
                repo.update_listing_fetch(self.conn, listing["id"], status="keine_daten", error=str(exc))
                repo.mark_fetched(self.conn, target, listing["id"], "keine_daten")
                continue
            except (ProviderError, ConnectionError, ValueError) as exc:
                errors += 1
                repo.update_listing_fetch(self.conn, listing["id"], status="fehler", error=str(exc)[:300])
                repo.mark_fetched(self.conn, target, listing["id"], "fehler")
                continue

            ok, why = self.verify_listing(isin, listing, history)
            if not ok:
                repo.mark_identity_unclear(self.conn, isin, why)
                repo.mark_fetched(self.conn, target, listing["id"], "identitaet_unklar")
                self.event("identitaet", f"{isin}: {why}", "WARN")
                continue
            self.store_history(listing, history, need_full, revision)
            if D in history.days or self.sources.calendars.session_close_utc(code, D) is None:
                repo.mark_fetched(self.conn, target, listing["id"], "ok")
            else:
                repo.mark_fetched(self.conn, target, listing["id"], "ohne_stichtag")
                without_cutoff += 1
            fetched += 1
            if fetched % 100 == 0:
                self.checkpoint()
        self.event("kurse", f"Kursabruf beendet: {fetched} aktualisiert, davon {without_cutoff} ohne Kurs am Stichtag; {errors} Einzelfehler (isoliert)")
        self.checkpoint(force=True)
        return False

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
        revised = False
        if not full and revision > 0:
            existing = repo.load_bars(self.conn, listing_id, revision, int(history.days[0]) if len(history) else None)
            overlap = np.intersect1d(existing["days"], history.days)
            if len(overlap):
                old = existing["close"][np.searchsorted(existing["days"], overlap)]
                new = history.close[np.searchsorted(history.days, overlap)]
                changed = np.abs(new / old - 1.0) > 1e-6
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
        repo.prune_fx_rates(self.conn, D - 400)
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

    # ---------------------------------------------------------- Berechnung

    def step_compute(self, universe: dict, members: dict, D: int, fx: FxRates | None = None) -> tuple[SnapshotComputation, list[InstrumentMeta], dict]:
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
        comp = compute_snapshot(inputs, D, self.method, fx=fx)
        return comp, metas, market_stats

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
            "share": share,
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
        key_material = {
            "cutoff": D,
            "universe_sha256": universe["sha256"],
            "input": comp.input_hash,
            "instrument_meta": sha256_hex(canonical_bytes(shown_meta)),
            "versions": self.versions,
            "data_mode": self.sources.data_mode,
            "completeness": completeness["status"],
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
        }
        checks = run_checks(comp, self.method)
        manifest_base["checks"] = checks
        if not all(c["passed"] for c in checks):
            failed = [c["name"] for c in checks if not c["passed"]]
            return self.finish("fehlgeschlagen", f"Konsistenzprüfung fehlgeschlagen: {', '.join(failed)}", EXIT_FAILED, cutoff_day=D)
        repo.update_run(self.conn, self.run_id, status="geprueft")

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

    def apply_retention(self) -> None:
        keep_bars = max(200, int(self.pipeline.get("aufbewahrung.kurs_historie_tage", 250)))
        newest = self.conn.execute("SELECT MAX(session_day) FROM daily_bar").fetchone()[0]
        if newest:
            repo.prune_old_bars(self.conn, int(newest) - keep_bars)

    # --------------------------------------------------------------- Status

    def write_status(self, status: str, message: str) -> None:
        build_status_file(self.conn, self.state_dir, self.sources.data_mode, self.pipeline, last_run_id=self.run_id, now=self.now())


def _license_note(provider: str) -> str:
    if provider == "yahoo":
        return ("Kursdaten: Yahoo Finance (inoffizielle Schnittstelle, keine Lizenz für einen Massendatenfeed; "
                "nur private Auswertung). Kursquelle ist nicht der TR-Ausführungsplatz.")
    if provider == "eodhd":
        return "Kursdaten: EODHD (lizenzierter Datenvertrag des Nutzers). Kursquelle ist nicht der TR-Ausführungsplatz."
    return "DEMO – synthetische Testdaten, keine echten Kurse."


def build_status_file(conn, state_dir: Path, data_mode: str, pipeline: PipelineConfig, *, last_run_id: str | None, now: dt.datetime) -> dict:
    """Schreibt ``site_meta/status.json`` und ``site_meta/index.json`` aus der Datenbank."""
    last_run = conn.execute("SELECT * FROM run WHERE id = ?", (last_run_id,)).fetchone() if last_run_id else None
    published = repo.published_snapshots(conn, data_mode)
    complete = [r for r in published if r["completeness"] == "vollstaendig"]
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
            "uhrzeit": schedule.get("uhrzeit", "06:00"),
            "zeitzone": schedule.get("zeitzone", "Europe/Berlin"),
            "wiederholungen_minuten": schedule.get("wiederholungen_minuten", [15, 45, 120]),
        },
        "heartbeat_max_age_hours": int(pipeline.get("betrieb.heartbeat_max_stunden", 30)),
        "software_version": __version__,
    }
    index = {
        "schema": "tr-snapshot-index/1",
        "snapshots": [json.loads(r["summary_json"]) | {"published_at_utc": r["published_at"]} for r in published],
    }
    meta_dir = Path(state_dir) / "site_meta"
    atomic_write_json(meta_dir / "status.json", status)
    atomic_write_json(meta_dir / "index.json", index)
    return status
