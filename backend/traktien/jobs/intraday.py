"""Zwischenstand (ab 1.8): alle Ranglisten mit aktuellen Kursen während des Handelstags neu rechnen.

Ablauf
1. Ist der offizielle Datenstand nicht auf dem neuesten abgeschlossenen Börsentag, rechnet zuerst der
   normale tägliche Lauf (sonst fehlten Schlusskurse zwischen dem offiziellen Stand und heute).
2. Aktuelle Kurse aller Referenznotierungen in Sammelabfragen (Yahoo „spark“, 20 Werte je Abruf) –
   verzögert, je nach Börse bis etwa 15–20 Minuten.
3. Stichtag des Zwischenstands T: der neueste Tag nach dem offiziellen Stand, an dem genug Aktien
   schon gehandelt wurden (Mindestanteil der Aktien, deren Börse an T eine Sitzung hat).
4. Je Aktie mit Kurs an T wird dieser Kurs als vorläufige letzte Beobachtung angehängt – nur im
   Speicher, nie in die gespeicherte Kurshistorie. Aktien ohne Kurs an T (Börse noch nicht geöffnet,
   heute geschlossen, kein Handel) fehlen in den Ranglisten des Zwischenstands mit dem Status
   „Kurs am Stichtag fehlt“ bzw. „Markt am Stichtag geschlossen“ – wie im offiziellen Lauf.
5. Rechenkern, Prüfungen und Dateien wie im offiziellen Lauf, ohne Abgleich mit einem zweiten
   Börsenplatz und ohne Umschichtungs-Regel (die rechnet mit Wochenschlusskursen). Der Ø Tagesumsatz
   (Gruppe B) zählt den laufenden Tag nicht mit.

Es gibt immer höchstens einen Zwischenstand. Sobald ein offizieller Stand mit gleichem oder späterem
Stichtag veröffentlicht ist, verschwindet er aus der App.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..analytics.codes import WindowWarning
from ..analytics.fx import FxRates
from ..analytics.venues import VenueCheck
from ..publish.checks import run_checks
from ..publish.snapshot_writer import SnapshotWriter, snapshot_tar
from ..providers.base import LiveQuote
from ..store import repo
from ..util.jsonio import atomic_write_bytes, canonical_bytes, sha256_hex
from ..util.timeutil import day_to_iso, iso_utc
from .daily import EXIT_FAILED, EXIT_LOCKED, EXIT_OK, LOCK_NAME, DailyRun, RunOutcome, _license_note

KIND = "zwischenstand"


@dataclass
class ProvisionalBar:
    """Vorläufiger Kurs einer Notierung am Stichtag des Zwischenstands (in der Kurseinheit der Tageskurse)."""

    day: int
    close: float
    volume: float
    time_utc: str
    session_closed: bool
    high: float = float("nan")
    low: float = float("nan")

    def value(self, key: str):
        return {
            "days": self.day,
            "open": float("nan"),
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "close_raw": self.close,
            "volume": self.volume,
            "quality": 0,
        }[key]


@dataclass
class DayChoice:
    """Gewählter Stichtag mit Zählung je Kandidat (für Bericht und Manifest)."""

    day: int | None
    candidates: list[dict]


def started_sessions(calendars, codes: set[str], now: dt.datetime, after_day: int) -> dict[str, list[int]]:
    """Je Kalender die Sitzungstage nach ``after_day``, deren Handel bis ``now`` schon begonnen hat."""
    out: dict[str, list[int]] = {}
    today = int(now.timestamp() // 86400)
    for code in sorted(codes):
        opener = getattr(calendars, "session_open_utc", None)
        days = [int(d) for d in calendars.sessions(code, after_day + 1, today + 1).tolist()]
        started = []
        for day in days:
            opening = opener(code, day) if opener is not None else None
            if opening is None:
                close = calendars.session_close_utc(code, day)
                opening = close - dt.timedelta(hours=8) if close is not None else None
            if opening is not None and opening <= now:
                started.append(day)
        if started:
            out[code] = started
    return out


def choose_day(
    listings: dict[str, dict],
    quotes: dict[str, LiveQuote],
    started: dict[str, list[int]],
    stored_last: dict[str, int],
    calendars,
    *,
    min_share: float,
) -> DayChoice:
    """Neuester Tag, an dem mindestens ``min_share`` der Aktien mit Sitzung an diesem Tag einen Kurs haben.

    Gezählt wird nur ein Kurs, dessen Handelstag genau dieser Tag ist und vor dem die gespeicherte
    Historie lückenlos bis zur vorherigen Sitzung reicht (sonst fehlte ein Schlusskurs dazwischen)."""
    days = sorted({d for values in started.values() for d in values}, reverse=True)
    report = []
    for day in days:
        expected = present = 0
        for isin, listing in listings.items():
            code = listing["calendar_code"]
            if day not in started.get(code, []):
                continue
            expected += 1
            quote = quotes.get(listing["provider_symbol"])
            if quote is None or quote.session_day != day:
                continue
            previous = calendars.sessions(code, day - 20, day - 1)
            if len(previous) and stored_last.get(isin, -1) < int(previous[-1]):
                continue
            present += 1
        share = present / expected if expected else 0.0
        report.append({"tag": day_to_iso(day), "erwartet": expected, "mit_kurs": present, "anteil": round(share, 4)})
        if expected and share >= min_share:
            return DayChoice(day, report)
    return DayChoice(None, report)


class IntradayRun(DailyRun):
    """Zwischenstand: gleiche Bausteine wie der tägliche Lauf, mit vorläufigen Kursen als letzter Beobachtung."""

    # Gestaffelte Aktualisierung (ab 1.10): Stufe 1 holt zuerst nur die Kurse der wichtigsten Aktien (``only_isins``),
    # Stufe 2 alle. ``stage`` steht im Datenstand (z. B. {"nummer": 1, "von": 2, …}).
    stage: dict | None = None
    only_isins: set[str] | None = None

    def execute(self) -> RunOutcome:  # type: ignore[override]
        repo.create_run(
            self.conn,
            self.run_id,
            trigger=KIND,
            planned_start=None,
            attempt=1,
            versions=self.versions,
            data_mode=self.sources.data_mode,
            started_at=iso_utc(self.now()),
        )
        acquired, other = repo.acquire_lock(self.conn, LOCK_NAME, self.run_id)
        if not acquired:
            repo.update_run(self.conn, self.run_id, status="abgebrochen", status_detail=f"Anderer Lauf aktiv: {other}", finished_at=iso_utc(self.now()))
            return RunOutcome(EXIT_LOCKED, "abgebrochen", f"Anderer Lauf aktiv ({other})", self.run_id)
        try:
            return self._intraday()
        except Exception as exc:  # gute Stände bleiben erhalten
            import traceback

            detail = f"{type(exc).__name__}: {exc}"
            self.event("fehler", detail + "\n" + traceback.format_exc(limit=6), level="ERROR")
            return self.finish("fehlgeschlagen", detail, EXIT_FAILED)

    def write_status(self, status: str, message: str) -> None:
        """Wie im täglichen Lauf, aber der nächste offizielle Kursstand bleibt der zuletzt berechnete."""
        from .daily import build_status_file

        build_status_file(self.conn, self.state_dir, self.sources.data_mode, self.pipeline, last_run_id=self.run_id, now=self.now(), keep_next=True)

    # ------------------------------------------------------------------ Ablauf

    def _intraday(self) -> RunOutcome:
        # Dauer je Abschnitt in Sekunden (ab 1.10, für die Laufübersicht: wo steckt die Zeit?)
        self.timings: dict[str, float] = {}
        mode = self.sources.data_mode
        universe = repo.latest_universe(self.conn, data_mode=mode)
        if universe is None:
            return self.finish("fehlgeschlagen", "Noch kein TR-Universum – zuerst den täglichen Lauf starten", EXIT_FAILED)
        universe = dict(universe)
        official = repo.published_snapshots(self.conn, mode, limit=1)
        if not official:
            return self.finish("fehlgeschlagen", "Noch kein offizieller Datenstand – zuerst den täglichen Lauf starten", EXIT_FAILED)
        official_day = int(official[0]["cutoff_day"])
        members = repo.universe_members(self.conn, universe["id"])
        refs = repo.reference_listings(self.conn)
        rows = repo.instruments(self.conn, members)
        listings: dict[str, dict] = {}
        for isin in sorted(members):
            listing = refs.get(isin)
            row = rows.get(isin)
            if listing is None or row is None or row["identity_status"] != "verifiziert":
                continue
            code = listing["calendar_code"]
            if not code or not self.sources.calendars.available(code) or not listing["provider_symbol"]:
                continue
            listings[isin] = dict(listing)
        if self.only_isins is not None:
            # Stufe 1: Tagwahl und Anteile nur über die zuerst aktualisierten Aktien
            listings = {isin: listing for isin, listing in listings.items() if isin in self.only_isins}
        codes = {listing["calendar_code"] for listing in listings.values()}
        now = self.now()
        started = started_sessions(self.sources.calendars, codes, now, official_day)
        if not started:
            return self.finish(
                "keine_neuen_daten",
                f"Seit dem offiziellen Stand vom {day_to_iso(official_day)} hat noch keine Börse neu gehandelt – der offizielle Stand ist aktuell",
                EXIT_OK,
                cutoff_day=official_day,
            )
        wanted = [listing["provider_symbol"] for isin, listing in listings.items() if listing["calendar_code"] in started and (self.only_isins is None or isin in self.only_isins)]
        if self.only_isins is not None:
            # Stufe 1: wichtigste zuerst (Reihenfolge der Prioritätenliste), nur Aktien offener Börsen
            order = {isin: k for k, isin in enumerate(self.stage.get("reihenfolge", []) if self.stage else [])}
            symbol_rank = {listing["provider_symbol"]: order.get(isin, len(order)) for isin, listing in listings.items()}
            wanted.sort(key=lambda s: symbol_rank.get(s, len(order)))
        fetch = getattr(self.sources.prices, "fetch_quotes", None)
        if fetch is None:
            return self.finish("fehlgeschlagen", f"Der Kursanbieter {self.sources.price_provider_name} liefert keine aktuellen Kurse", EXIT_FAILED)
        budget = float(self.pipeline.get("zwischenstand.max_sekunden_kurse", 900))
        began = time.monotonic()
        result = fetch(wanted, budget_s=budget)
        seconds = time.monotonic() - began
        self.timings["kurse"] = seconds
        self.event(
            "kurse",
            f"Aktuelle Kurse: {len(result.quotes)} von {len(wanted)} Notierungen in {result.requests} Sammelabfragen ({seconds:.0f} s)"
            + ("; Anbieter drosselt" if result.throttled else ""),
        )
        if not result.quotes:
            return self.finish("fehlgeschlagen", "Keine aktuellen Kurse erhalten – später erneut versuchen", EXIT_FAILED, cutoff_day=official_day)
        stored_last = {isin: last for isin, last in self._stored_last(listings).items()}
        choice = choose_day(
            listings,
            result.quotes,
            started,
            stored_last,
            self.sources.calendars,
            min_share=float(self.pipeline.get("zwischenstand.mindestanteil_aktien", 0.2)),
        )
        if choice.day is None:
            return self.finish(
                "keine_neuen_daten",
                "Noch zu wenige aktuelle Kurse für einen Zwischenstand: " + "; ".join(f"{c['tag']} {c['mit_kurs']} von {c['erwartet']}" for c in choice.candidates),
                EXIT_OK,
                cutoff_day=official_day,
            )
        T = int(choice.day)
        provisional, skipped = self._provisional_bars(listings, result.quotes, T, now)
        repo.update_run(self.conn, self.run_id, cutoff_day=T, universe_id=universe["id"])
        self.event(
            "stichtag",
            f"Zwischenstand für {day_to_iso(T)}: {len(provisional)} Aktien mit aktuellem Kurs"
            + (f"; nicht verwendet: {', '.join(f'{k} {v}' for k, v in sorted(skipped.items()))}" if skipped else ""),
        )
        fx = self._stored_fx(T)
        began = time.monotonic()
        comp, metas, market_stats = self.step_compute(universe, members, T, fx, provisional=provisional)
        self.timings["rechnen"] = time.monotonic() - began
        completeness = self.assess_completeness(market_stats)
        return self._publish_intraday(universe, comp, metas, completeness, T, official[0], result, choice, provisional, now)

    def _stored_last(self, listings: dict[str, dict]) -> dict[str, int]:
        out: dict[str, int] = {}
        for isin, listing in listings.items():
            row = self.conn.execute(
                "SELECT MAX(session_day) FROM daily_bar WHERE listing_id = ? AND revision = ?", (int(listing["id"]), int(listing["data_revision"]))
            ).fetchone()
            if row and row[0] is not None:
                out[isin] = int(row[0])
        return out

    def _provisional_bars(self, listings: dict[str, dict], quotes: dict[str, LiveQuote], T: int, now: dt.datetime) -> tuple[dict[str, ProvisionalBar], dict[str, int]]:
        """Vorläufige Kurse am Stichtag T je ISIN; ``skipped`` zählt Gründe für nicht verwendete Kurse."""
        bars: dict[str, ProvisionalBar] = {}
        skipped: dict[str, int] = {}
        grace = dt.timedelta(minutes=int(self.pipeline.get("stichtag.karenz_minuten_nach_schluss", 60)))

        def skip(reason: str) -> None:
            skipped[reason] = skipped.get(reason, 0) + 1

        for isin, listing in listings.items():
            quote = quotes.get(listing["provider_symbol"])
            if quote is None or quote.session_day != T:
                continue
            unit = listing["price_unit"]
            if quote.currency and unit and quote.currency != unit:
                skip("andere Kurseinheit")
                continue
            if not (quote.price > 0 and np.isfinite(quote.price)):
                skip("ungültiger Kurs")
                continue
            close_at = self.sources.calendars.session_close_utc(listing["calendar_code"], T)
            bars[isin] = ProvisionalBar(
                day=T,
                close=float(quote.price),
                volume=float(quote.volume) if np.isfinite(quote.volume) and quote.volume >= 0 else float("nan"),
                time_utc=iso_utc(quote.time_utc),
                session_closed=bool(close_at is not None and close_at + grace <= now),
            )
        return bars, skipped

    def _opening(self, code: str, day: int) -> dt.datetime | None:
        opener = getattr(self.sources.calendars, "session_open_utc", None)
        return opener(code, day) if opener is not None else None

    def _stored_fx(self, day: int) -> FxRates | None:
        rows = repo.fx_rates_since(self.conn, day - 150)
        if not rows:
            return None
        return FxRates.from_rows(
            [(int(r["day"]), r["currency"], float(r["per_eur"])) for r in rows],
            source=rows[-1]["source"],
            url=None,
            fetched_at=max(r["fetched_at"] for r in rows),
            max_age_days=self.method.fx_max_age_days,
        )

    # ------------------------------------------------------------ Veröffentlichung

    def _publish_intraday(self, universe, comp, metas, completeness, T: int, official, result, choice: DayChoice, provisional: dict, now: dt.datetime) -> RunOutcome:
        times = sorted(bar.time_utc for bar in provisional.values())
        quotes_until = times[-1] if times else None
        computed_at = iso_utc(now)
        stamp = now.astimezone(dt.timezone.utc).strftime("%H%M")
        key = sha256_hex(canonical_bytes({"cutoff": T, "input": comp.input_hash, "versions": self.versions, "kind": KIND, "at": computed_at}))
        snapshot_id = f"{day_to_iso(T)}_z{stamp}{key[:6]}"
        closed = sum(1 for bar in provisional.values() if bar.session_closed)
        intraday_info = {
            "stichtag": day_to_iso(T),
            "kurse_bis_utc": quotes_until,
            "kurse_ab_utc": times[0] if times else None,
            "abgerufen_utc": computed_at,
            "aktien_mit_kurs": len(provisional),
            "davon_sitzung_beendet": closed,
            "abrufe": result.requests,
            "gedrosselt": result.throttled,
            "offizieller_stand": official["id"],
            "offizieller_stichtag": day_to_iso(int(official["cutoff_day"])),
            "tagwahl": choice.candidates,
            "boersen_mit_kurs": completeness.get("delivered_markets", []),
            "boersen_ohne_kurs": completeness.get("missing_markets", []),
            # Sitzungsbeginn der Börsen ohne Kurs (z. B. New York): liegt er nach dem Abruf, öffnet die Börse noch
            "oeffnung_utc": {
                code: (iso_utc(opening) if (opening := self._opening(code, T)) is not None else None)
                for code in completeness.get("missing_markets", [])
            },
            # Gestaffelte Aktualisierung (ab 1.10): Stufe 1 = zuerst die wichtigsten Aktien, Stufe 2 = alle
            "stufe": None if self.stage is None else {k: v for k, v in self.stage.items() if k != "reihenfolge"},
            "beschreibung": (
                "Vorläufiger Stand mit aktuellen Kursen (verzögert, je nach Börse bis etwa 15–20 Minuten). Der letzte Kurs jeder "
                "Aktie ist der zuletzt gemeldete des Tages, kein Schlusskurs – bis zum Börsenschluss ändert er sich noch. Aktien "
                "von Börsen, die heute noch nicht oder nicht gehandelt haben, fehlen in den Ranglisten. Ø Tagesumsatz ohne den "
                "laufenden Tag; kein Abgleich mit einem zweiten Börsenplatz, keine Umschichtungs-Regel."
            ),
        }
        manifest_base = {
            "data_mode": self.sources.data_mode,
            "art": KIND,
            "zwischenstand": intraday_info,
            "cutoff_session_date": day_to_iso(T),
            "cutoff_day": T,
            "computed_at_utc": computed_at,
            "published_at_utc": computed_at,
            "run_id": self.run_id,
            "attempt": 1,
            "completeness": completeness,
            "idempotency_key": key,
            "supersedes": None,
            "versions": dict(self.versions, data_revision=comp.input_hash, calendar=self.sources.calendars.version()),
            "method": self.method.as_dict(),
            "calendar_convention": "kalendertage",
            "currency_basis": "Kursrendite in jeweiliger Notierungswährung; splitbereinigt; ohne Dividenden, Kosten, Steuern und EUR-Wechselkurseffekt. Letzter Kurs vorläufig (Zwischenstand).",
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
                "intraday": True,
            },
            "flags": {"report_publishable": True, "model_validated": False, "forecast_eligible": False, "original_run_on_time": None},
            "kursmeldung": {"am_stichtag": 0, "aktien": sum(1 for m in metas if m.quote_days), "beschreibung": "Im Zwischenstand ist der letzte Kurs jeder Aktie ein vorläufiger Kurs des laufenden Tages."},
        }
        comp.wflags &= np.uint16(~(1 << WindowWarning.BOERSENPLATZ_ABWEICHUNG) & 0xFFFF)
        comp.venue = VenueCheck(version=self.method.venue_version, settings=self.method.venue_settings(), aborted=True)
        comp.venue.note = "Im Zwischenstand nicht geprüft – der Abgleich mit einem zweiten Börsenplatz läuft nur im offiziellen Stand"
        comp.rotation = None
        checks = run_checks(comp, self.method)
        manifest_base["checks"] = checks
        if not all(c["passed"] for c in checks):
            failed = [c["name"] for c in checks if not c["passed"]]
            return self.finish("fehlgeschlagen", f"Konsistenzprüfung fehlgeschlagen: {', '.join(failed)}", EXIT_FAILED, cutoff_day=T)
        snapshots_dir = self.state_dir / "snapshots"
        began = time.monotonic()
        writer = SnapshotWriter(comp, metas, self.method, snapshot_id=snapshot_id, key=self.key)
        manifest = writer.write(snapshots_dir, manifest_base)
        self.timings["schreiben"] = time.monotonic() - began
        began = time.monotonic()
        archive_name = f"site-{snapshot_id}.tar"
        atomic_write_bytes(self.state_dir / "archives" / archive_name, snapshot_tar(snapshots_dir / snapshot_id))
        self.timings["archiv"] = time.monotonic() - began
        summary = {
            "snapshot_id": snapshot_id,
            "art": KIND,
            "cutoff_session_date": day_to_iso(T),
            "computed_at_utc": computed_at,
            "kurse_bis_utc": quotes_until,
            "completeness": completeness["status"],
            "data_mode": self.sources.data_mode,
            "universe_count": comp.n_instruments,
            "return_eligible_30": manifest["coverage"]["per_window"][29]["return_eligible"],
            "trend_eligible_30": manifest["coverage"]["per_window"][29]["trend_eligible"],
            "aktien_mit_kurs": len(provisional),
            "offizieller_stand": official["id"],
            "stufe": intraday_info["stufe"],
            "supersedes": None,
            "versions": manifest_base["versions"],
        }
        removed = repo.insert_intraday(
            self.conn,
            id=snapshot_id,
            cutoff_day=T,
            created_at=computed_at,
            quotes_until=quotes_until,
            data_mode=self.sources.data_mode,
            run_id=self.run_id,
            official_id=official["id"],
            summary_json=json.dumps(summary, ensure_ascii=False),
            site_archive=archive_name,
        )
        for name in removed:
            (self.state_dir / "archives" / name).unlink(missing_ok=True)
        until = quotes_until[11:16] if quotes_until else "?"
        return self.finish(
            "veroeffentlicht",
            f"Zwischenstand {snapshot_id} veröffentlicht: {len(provisional)} Aktien mit Kurs vom {day_to_iso(T)} (bis {until} UTC)",
            EXIT_OK,
            cutoff_day=T,
            snapshot_id=snapshot_id,
            details=completeness | {"zwischenstand": intraday_info, "zeiten": dict(self.timings)},
        )
