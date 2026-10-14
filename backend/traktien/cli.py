"""Kommandozeile: ``python -m traktien <befehl>``.

Befehle
  demo          DEMO-Lauf mit synthetischen Testdaten + Website-Zusammenbau
  run           Produktiver Lauf mit lokalem Zustandsverzeichnis
  ci            Produktiver Lauf in GitHub Actions (Zustand in Release-Assets)
  site          Website aus Zustandsverzeichnis zusammenbauen
  serve         Lokale Vorschau der gebauten Website
  restore-test  Sicherung wiederherstellen und prüfen
  verify-site   Alle veröffentlichten Dateien entschlüsseln und Schemata prüfen
"""

from __future__ import annotations

import argparse
import datetime as dt
import functools
import http.server
import json
import os
import shutil
import socketserver
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

from . import __version__
from .config import REPO_ROOT, load_method_config, load_pipeline_config, load_yaml
from .jobs.daily import EXIT_FAILED, EXIT_LOCKED, EXIT_OK, EXIT_RETRY, DailyRun, RunOptions, RunOutcome, build_status_file
from .jobs.sources import demo_sources, production_sources
from .jobs.state import GitHubReleaseStore, StateError, load_or_create_key, pack_database, sync_down, sync_up, unpack_database
from .jobs.summary import workflow_notice
from .providers.exchanges import load_exchange_table
from .publish.site import assemble_site, retained_snapshots
from .store.db import connect
from .util import crypto
from .util.jsonio import read_json
from .util.log import get_logger, setup_logging

LOG = get_logger("traktien")
DEFAULT_APP_DIST = REPO_ROOT / "app" / "dist"


def _reviews() -> list[dict]:
    data = load_yaml("pruefungen.yaml") or {}
    return list(data.get("kurssprung_entscheidungen") or [])


def _planned_start(cron: str | None, now: dt.datetime) -> dt.datetime | None:
    """Geplanter Start aus dem auslösenden Cron-Eintrag (Minute Stunde, Zeitzone Berlin)."""
    if not cron:
        return None
    parts = cron.split()
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    berlin = now.astimezone(ZoneInfo("Europe/Berlin"))
    planned = berlin.replace(hour=int(parts[1]), minute=int(parts[0]), second=0, microsecond=0)
    if planned > berlin + dt.timedelta(minutes=5):
        planned -= dt.timedelta(days=1)
    return planned.astimezone(dt.timezone.utc)


def _run_pipeline(state_dir: Path, mode: str, *, trigger: str, planned: dt.datetime | None, force: bool, key, on_checkpoint=None, identity_limit=None) -> tuple[RunOutcome, object]:
    method = load_method_config()
    pipeline = load_pipeline_config()
    table = load_exchange_table()
    sources = (
        demo_sources()
        if mode == "demo"
        else production_sources(
            table,
            _reviews(),
            price_provider=os.environ.get("KURS_ANBIETER", pipeline.get("anbieter.kurse", "yahoo")),
            universe_url=pipeline.get("universum.url"),
        )
    )
    conn = connect(state_dir / "state.sqlite")
    try:
        options = RunOptions(
            trigger=trigger,
            planned_start=planned,
            max_attempts=int(pipeline.get("zeitplan.max_versuche", 4)),
            force_publish=force,
            time_budget_s=float(pipeline.get("abruf.max_laufzeit_minuten", 300)) * 60,
            on_checkpoint=(lambda: on_checkpoint(conn)) if on_checkpoint else None,
            identity_limit=identity_limit,
        )
        outcome = DailyRun(conn, state_dir, sources, method, pipeline, table, key, options).execute()
    except BaseException:
        conn.close()
        raise
    LOG.info("Ergebnis: %s – %s", outcome.status, outcome.message)
    return outcome, conn


def _facts_sources(mode: str):
    """Quellen für Kennzahlen und Signale (ab 1.6)."""
    if mode == "demo":
        from .providers.demo import DemoExtraSources, DemoFactsProvider

        facts = DemoFactsProvider()
        return facts, DemoExtraSources(facts)
    from .providers.extra_sources import ExtraSources
    from .providers.yahoo import YahooProvider

    return YahooProvider(), ExtraSources()


def _facts_and_signals(conn, state_dir: Path, key, pipeline, *, mode: str, run_id: str | None, budget_s: float | None = None,
                       new_snapshot: bool = False, now: dt.datetime | None = None) -> list[str]:
    """Kennzahlen abrufen (Zeitbudget) und – wenn sich etwas geändert hat – einen neuen Signal-Stand schreiben.
    Fehler hier lassen den Lauf und den Kurs-Datenstand unberührt. Rückgabe: Meldungen für den Kurzbericht."""
    from .jobs.facts import FactsJob, FactsSettings, SignalsJob
    from .store import repo as _repo

    messages: list[str] = []
    now = now or dt.datetime.now(tz=dt.timezone.utc)

    def event(step: str, message: str, level: str = "INFO") -> None:
        LOG.log(20 if level == "INFO" else 30, "[%s] %s", step, message)
        if run_id:
            _repo.log_event(conn, run_id, step, message, level)

    fetched = 0
    try:
        settings = FactsSettings.from_pipeline(pipeline)
        if budget_s is not None:
            settings.budget_s = settings.budget_initial_s = budget_s
        provider, extra = _facts_sources(mode)
        report = FactsJob(conn, provider=provider, extra=extra, settings=settings, now=now, event=event).run()
        fetched = report.fetched + sum(v for k, v in report.extras.items() if k != "fehler")
        event("kennzahlen", report.message())
        messages.append(report.message())
    except Exception as exc:  # Kennzahlen sind eine Ergänzung – nie ein Grund für einen roten Lauf
        event("kennzahlen", f"Kennzahlen übersprungen ({type(exc).__name__}: {exc})", "WARN")
        messages.append(f"Kennzahlen übersprungen ({type(exc).__name__})")
    try:
        from .analytics.signals import VERSION as SIGNAL_VERSION

        latest = _repo.signal_stands(conn, 1)
        published = _repo.published_snapshots(conn, mode)
        stale = not latest or (published and latest[0]["snapshot_id"] != published[0]["id"])
        # neue Rechenregeln (z. B. Gesamtwertung ab signale-v2): sofort einen neuen Stand rechnen
        outdated = bool(latest) and json.loads(latest[0]["summary_json"] or "{}").get("version") != SIGNAL_VERSION
        if fetched or new_snapshot or stale or outdated:
            summary = SignalsJob(conn, state_dir, None if mode == "demo" and key is None else key, load_exchange_table(), now=now, data_mode=mode, event=event).run()
            if summary:
                messages.append(
                    f"Signal-Stand {summary['id']}: {summary['aktien']} Aktien, {summary['mit_kursziel']} mit Kursziel; Gesamtwertung stark {summary['gesamt_stark']}, "
                    f"mittel {summary['gesamt_mittel']}; beide grün {summary['beide_gruen']}, kurzfristig grün {summary['kurz_gruen']}, langfristig grün {summary['lang_gruen']}"
                )
        else:
            messages.append("Signale unverändert (keine neuen Kennzahlen, kein neuer Datenstand)")
    except Exception as exc:  # siehe oben
        event("signale", f"Signal-Stand nicht erstellt ({type(exc).__name__}: {exc})", "WARN")
        messages.append(f"Signal-Stand nicht erstellt ({type(exc).__name__})")
    return messages


def _signal_archive(conn) -> list[str]:
    from .store import repo as _repo

    latest = _repo.signal_stands(conn, 1)
    return [latest[0]["archive"]] if latest else []


def cmd_demo(args) -> int:
    state_dir = Path(args.state_dir)
    if args.fresh and state_dir.exists():
        shutil.rmtree(state_dir)
    key = None
    descriptor = crypto.crypto_descriptor(None)
    if args.passphrase:
        key, descriptor = load_or_create_key(state_dir, args.passphrase, allow_new=True)
    outcome, conn = _run_pipeline(state_dir, "demo", trigger="manuell", planned=None, force=False, key=key)
    code, status = outcome.exit_code, outcome.status
    if code != EXIT_LOCKED:
        from .providers.demo import DEMO_NOW

        for line in _facts_and_signals(conn, state_dir, key, load_pipeline_config(), mode="demo", run_id=outcome.run_id, new_snapshot=status == "veroeffentlicht", now=DEMO_NOW):
            LOG.info("%s", line)
        build_status_file(conn, state_dir, "demo", load_pipeline_config(), last_run_id=outcome.run_id, now=DEMO_NOW, keep_next=True)
        if getattr(args, "zwischenstand", False):
            intraday = _run_intraday(conn, state_dir, "demo", key)
            LOG.info("Zwischenstand: %s – %s", intraday.status, intraday.message)
    conn.close()
    if args.site:
        keep = int(load_pipeline_config().get("aufbewahrung.site_snapshots", 5))
        result = assemble_site(app_dist=Path(args.app_dist), state_dir=state_dir, out_dir=Path(args.site), crypto_descriptor=descriptor, keep=keep)
        LOG.info("Website gebaut: %s (Snapshots: %s)", args.site, ", ".join(result["snapshots"]))
    print(json.dumps({"status": status, "exit_code": code}, ensure_ascii=False))
    return 0 if code in (EXIT_OK,) else code


def cmd_run(args) -> int:
    state_dir = Path(args.state_dir)
    passphrase = os.environ.get("DATA_PASSPHRASE")
    key, _ = load_or_create_key(state_dir, passphrase, allow_new=True)
    outcome, conn = _run_pipeline(state_dir, "produktiv", trigger=args.trigger, planned=None, force=args.force, key=key)
    conn.close()
    return outcome.exit_code


def cmd_ci(args) -> int:
    """Kompletter GitHub-Ablauf; schreibt Ausgaben für die nächsten Workflow-Schritte."""
    state_dir = Path(args.state_dir)
    passphrase = os.environ.get("DATA_PASSPHRASE")
    pipeline = load_pipeline_config()
    if not passphrase and os.environ.get("UNVERSCHLUESSELT_ERLAUBT", "").lower() != "true":
        print("::error::Secret DATA_PASSPHRASE fehlt. Ohne Passphrase wären Kursdaten öffentlich lesbar. Siehe docs/02_Einrichtung_und_Betrieb.md")
        return EXIT_FAILED
    store = GitHubReleaseStore.from_env(tag=pipeline.get("github.release_tag", "datenstand"))
    if args.reset_state:
        LOG.warning("Zustand wird bewusst neu aufgebaut (Eingabe zustand_neu_aufbauen)")
        assets = store.assets()
        for name in ("state.sqlite.tra", "state.sqlite.tra.neu", "crypto.json"):
            if name in assets:
                store.delete(assets[name])
    sync_down(store, state_dir, passphrase)
    if args.nur_website:
        return _ci_site_only(store, state_dir, passphrase, pipeline, args)
    if args.kennzahlen:
        return _ci_facts_only(store, state_dir, passphrase, pipeline, args)
    if args.zwischenstand:
        return _ci_intraday(store, state_dir, passphrase, pipeline, args)
    key, descriptor = load_or_create_key(state_dir, passphrase, allow_new=True)
    # GitHub-Concurrency (Gruppe „taeglicher-lauf“) lässt nie zwei Läufe gleichzeitig zu. Eine Sperre
    # in der heruntergeladenen Sicherung stammt deshalb aus einem beendeten oder abgebrochenen Lauf.
    if (state_dir / "state.sqlite").exists():
        from .store import repo as _repo

        lock_conn = connect(state_dir / "state.sqlite")
        try:
            cleared = _repo.clear_orphaned_locks(lock_conn, "Lauf ohne Abschluss beendet (Sperre beim nächsten Lauf freigegeben)")
        finally:
            lock_conn.close()
        if cleared:
            LOG.warning("Verwaiste Sperre freigegeben: %s", ", ".join(cleared))

    def upload_checkpoint(conn) -> None:
        try:
            sync_up(store, state_dir, conn, key, keep_archives=int(pipeline.get("aufbewahrung.archiv_snapshots", 60)))
        except Exception as exc:  # Checkpoint-Upload darf den Lauf nicht abbrechen
            LOG.warning("Checkpoint-Upload fehlgeschlagen: %s", exc)

    now = dt.datetime.now(tz=dt.timezone.utc)
    planned = _planned_start(os.environ.get("AUSLOESENDER_ZEITPLAN"), now)
    trigger = "zeitplan" if os.environ.get("GITHUB_EVENT_NAME") == "schedule" else "manuell"
    outcome, conn = _run_pipeline(state_dir, "produktiv", trigger=trigger, planned=planned, force=args.force, key=key, on_checkpoint=upload_checkpoint)
    code, status = outcome.exit_code, outcome.status
    keep = int(pipeline.get("aufbewahrung.site_snapshots", 5))
    try:
        # Kurzbericht (Ergebnis, Stichtag, Abruf, Stichtagskurse je Markt) in der Laufübersicht
        try:
            print(workflow_notice(conn, outcome))
        except Exception as exc:  # Bericht ist Beiwerk und darf den Lauf nicht abbrechen
            LOG.warning("Kurzbericht nicht erstellt: %s", exc)
        if code == EXIT_LOCKED:
            _write_output("deploy", "false")
            return 0
        # Kennzahlen und Signale (ab 1.6) laufen im eigenen Job „kennzahlen“ nach der Bereitstellung
        sync_up(store, state_dir, conn, key, keep_archives=int(pipeline.get("aufbewahrung.archiv_snapshots", 60)))
        index_path = state_dir / "site_meta" / "index.json"
        if index_path.exists():
            wanted = [s["snapshot_id"] for s in retained_snapshots(read_json(index_path), keep)]
            sync_down(store, state_dir, passphrase, wanted_snapshots=wanted, wanted_archives=_signal_archive(conn))
        else:
            build_status_file(conn, state_dir, "produktiv", pipeline, last_run_id=None, now=now)
    finally:
        conn.close()
    assemble_site(app_dist=Path(args.app_dist), state_dir=state_dir, out_dir=Path(args.site), crypto_descriptor=descriptor, keep=keep)
    _write_output("deploy", "true")
    _write_output("status", status)
    if code == EXIT_RETRY:
        _write_output("retry", "true")
        print(f"::notice::Daten noch unvollständig – nächster geplanter Versuch übernimmt ({status})")
        return 0
    if code == EXIT_FAILED:
        print(f"::warning::Lauf fehlgeschlagen ({status}); letzter guter Stand bleibt veröffentlicht")
        return 0 if args.soft_fail else EXIT_FAILED
    return 0


def _ci_site_only(store, state_dir: Path, passphrase: str | None, pipeline, args) -> int:
    """Nur die Website neu zusammensetzen und bereitstellen, z. B. nach einer App-Änderung.

    Kein Abruf, keine Berechnung und keine Änderung an der Sicherung: Status, Index und die
    aufbewahrten Datenstände kommen unverändert aus dem Release „datenstand“.

    Zusammen mit ``--reset-state`` (neue Passphrase): Die alte Sicherung ist dann schon gelöscht;
    angelegt und gesichert werden nur neue Schlüsselparameter und eine leere Datenbank. So prüft
    die App die neue Passphrase nach wenigen Minuten – Zuordnung und Kurse lädt der nächste
    normale Lauf."""
    keep = int(pipeline.get("aufbewahrung.site_snapshots", 5))
    if args.reset_state:
        # Lokale Reste (nur bei Läufen außerhalb von GitHub möglich) gehören zum alten Schlüssel
        for leftover in ("state.sqlite", "state.sqlite-wal", "state.sqlite-shm", "crypto.json"):
            (state_dir / leftover).unlink(missing_ok=True)
        key, descriptor = load_or_create_key(state_dir, passphrase, allow_new=True)
        conn = connect(state_dir / "state.sqlite")  # leere Datenbank mit aktuellem Schema
        try:
            sync_up(store, state_dir, conn, key, keep_archives=int(pipeline.get("aufbewahrung.archiv_snapshots", 60)))
        finally:
            conn.close()
        print("::notice title=Neuer Schlüssel::Zustand neu angelegt; Zuordnung und Kurse lädt der nächste normale Lauf")
    elif not (state_dir / "state.sqlite").exists() or not (state_dir / "crypto.json").exists():
        print("::error::Noch kein gespeicherter Zustand im Release – zuerst einen normalen Lauf starten")
        return EXIT_FAILED
    else:
        _, descriptor = load_or_create_key(state_dir, passphrase, allow_new=False)
    conn = connect(state_dir / "state.sqlite")
    try:
        last = conn.execute("SELECT id, status, data_mode FROM run ORDER BY started_at DESC, rowid DESC LIMIT 1").fetchone()
        mode = last["data_mode"] if last else "produktiv"
        build_status_file(conn, state_dir, mode, pipeline, last_run_id=last["id"] if last else None, now=dt.datetime.now(tz=dt.timezone.utc))
    finally:
        conn.close()
    wanted = [s["snapshot_id"] for s in retained_snapshots(read_json(state_dir / "site_meta" / "index.json"), keep)]
    conn = connect(state_dir / "state.sqlite")
    try:
        archives = _signal_archive(conn)
    finally:
        conn.close()
    if wanted or archives:
        sync_down(store, state_dir, passphrase, wanted_snapshots=wanted, wanted_archives=archives)
    assemble_site(app_dist=Path(args.app_dist), state_dir=state_dir, out_dir=Path(args.site), crypto_descriptor=descriptor, keep=keep)
    _write_output("deploy", "true")
    _write_output("status", last["status"] if last else "kein_lauf")
    try:
        app_version = read_json(Path(args.app_dist) / "version.json").get("version", "?")
    except (OSError, ValueError):
        app_version = "?"
    if args.reset_state:
        print(f"::notice title=Nur Website::App {app_version} mit neuem Schlüssel bereitgestellt; noch kein Datenstand")
    else:
        print(f"::notice title=Nur Website::App {app_version} neu zusammengesetzt; Datenstand unverändert ({len(wanted)} veröffentlichte Stände)")
    return 0


def _ci_facts_only(store, state_dir: Path, passphrase: str | None, pipeline, args) -> int:
    """Nur Kennzahlen, Kursziele und Signale aktualisieren (ohne Kursabruf und ohne neue Ranglisten).

    Gedacht für „jederzeit aktualisieren“: dauert je nach Budget 10–45 Minuten; der Kurs-Datenstand
    bleibt unverändert, die App zeigt danach den neuen Signal-Stand."""
    keep = int(pipeline.get("aufbewahrung.site_snapshots", 5))
    if not (state_dir / "state.sqlite").exists() or not (state_dir / "crypto.json").exists():
        print("::error::Noch kein gespeicherter Zustand im Release – zuerst einen normalen Lauf starten")
        return EXIT_FAILED
    key, descriptor = load_or_create_key(state_dir, passphrase, allow_new=False)
    conn = connect(state_dir / "state.sqlite")
    try:
        # Nach dem täglichen Lauf: übliches Budget (bei der Erstbefüllung länger); von Hand gestartet: mehr Zeit
        daily = os.environ.get("KENNZAHLEN_TAEGLICH", "").lower() == "true"
        budget = None if daily else float(pipeline.get("kennzahlen.max_sekunden_manuell", 2400))
        published = conn.execute("SELECT id FROM snapshot_manifest WHERE status = 'veroeffentlicht' ORDER BY cutoff_day DESC, published_at DESC LIMIT 1").fetchone()
        stands = conn.execute("SELECT snapshot_id FROM signal_stand ORDER BY created_at DESC LIMIT 1").fetchone()
        new_snapshot = published is not None and (stands is None or stands["snapshot_id"] != published["id"])
        notes = _facts_and_signals(conn, state_dir, key, pipeline, mode="produktiv", run_id=None, budget_s=budget, new_snapshot=new_snapshot)
        print("::notice title=Kennzahlen und Signale::" + " | ".join(notes).replace("%", "%25"))
        last = conn.execute("SELECT id, status FROM run ORDER BY started_at DESC, rowid DESC LIMIT 1").fetchone()
        build_status_file(conn, state_dir, "produktiv", pipeline, last_run_id=last["id"] if last else None, now=dt.datetime.now(tz=dt.timezone.utc), keep_next=True)
        sync_up(store, state_dir, conn, key, keep_archives=int(pipeline.get("aufbewahrung.archiv_snapshots", 60)))
        archives = _signal_archive(conn)
    finally:
        conn.close()
    wanted = [s["snapshot_id"] for s in retained_snapshots(read_json(state_dir / "site_meta" / "index.json"), keep)]
    sync_down(store, state_dir, passphrase, wanted_snapshots=wanted, wanted_archives=archives)
    assemble_site(app_dist=Path(args.app_dist), state_dir=state_dir, out_dir=Path(args.site), crypto_descriptor=descriptor, keep=keep)
    _write_output("deploy", "true")
    _write_output("status", "kennzahlen")
    return 0


def _sources_for(mode: str, pipeline):
    table = load_exchange_table()
    if mode == "demo":
        from .providers.demo import DEMO_INTRADAY_NOW

        sources = demo_sources()
        sources.now = DEMO_INTRADAY_NOW
        sources.prices.quote_now = DEMO_INTRADAY_NOW
        return sources, table
    return (
        production_sources(
            table,
            _reviews(),
            price_provider=os.environ.get("KURS_ANBIETER", pipeline.get("anbieter.kurse", "yahoo")),
            universe_url=pipeline.get("universum.url"),
        ),
        table,
    )


def _run_intraday(conn, state_dir: Path, mode: str, key) -> RunOutcome:
    """Zwischenstand (ab 1.8) mit der offenen Datenbankverbindung."""
    from .jobs.intraday import IntradayRun

    pipeline = load_pipeline_config()
    sources, table = _sources_for(mode, pipeline)
    return IntradayRun(conn, state_dir, sources, load_method_config(), pipeline, table, key, RunOptions(trigger="zwischenstand")).execute()


def _official_due(conn, mode: str, pipeline) -> tuple[bool, str]:
    """Fehlt der offizielle Stand für den neuesten abgeschlossenen Börsentag? Dann rechnet der Zwischenstand
    zuerst den täglichen Lauf (sonst fehlten Schlusskurse zwischen offiziellem Stand und heute)."""
    from .jobs.cutoff import determine_cutoff
    from .store import repo as _repo
    from .util.timeutil import day_to_iso

    sources, _ = _sources_for(mode, pipeline)
    refs = _repo.reference_listings(conn)
    codes = {row["calendar_code"] for row in refs.values() if row["calendar_code"] and sources.calendars.available(row["calendar_code"])}
    if not codes:
        return True, "noch keine Zuordnung"
    now = sources.now if sources.data_mode == "demo" else dt.datetime.now(tz=dt.timezone.utc)
    cutoff = determine_cutoff(codes, sources.calendars, now, grace_minutes=int(pipeline.get("stichtag.karenz_minuten_nach_schluss", 60)))
    latest = _repo.published_snapshots(conn, sources.data_mode, limit=1)
    if latest and int(latest[0]["cutoff_day"]) >= cutoff.cutoff_day:
        return False, f"offizieller Stand {day_to_iso(int(latest[0]['cutoff_day']))} ist aktuell"
    return True, f"offizieller Stand für {day_to_iso(cutoff.cutoff_day)} fehlt noch"


def _ci_intraday(store, state_dir: Path, passphrase: str | None, pipeline, args) -> int:
    """Zwischenstand auf GitHub: bei Bedarf zuerst der tägliche Lauf, dann aktuelle Kurse, Ranglisten, Website."""
    keep = int(pipeline.get("aufbewahrung.site_snapshots", 5))
    if not (state_dir / "state.sqlite").exists() or not (state_dir / "crypto.json").exists():
        print("::error::Noch kein gespeicherter Zustand im Release – zuerst einen normalen Lauf starten")
        return EXIT_FAILED
    key, descriptor = load_or_create_key(state_dir, passphrase, allow_new=False)
    from .store import repo as _repo

    conn = connect(state_dir / "state.sqlite")
    try:
        cleared = _repo.clear_orphaned_locks(conn, "Lauf ohne Abschluss beendet (Sperre beim nächsten Lauf freigegeben)")
        if cleared:
            LOG.warning("Verwaiste Sperre freigegeben: %s", ", ".join(cleared))
        due, why = _official_due(conn, "produktiv", pipeline)
    finally:
        conn.close()

    def upload_checkpoint(conn) -> None:
        try:
            sync_up(store, state_dir, conn, key, keep_archives=int(pipeline.get("aufbewahrung.archiv_snapshots", 60)))
        except Exception as exc:  # Checkpoint-Upload darf den Lauf nicht abbrechen
            LOG.warning("Checkpoint-Upload fehlgeschlagen: %s", exc)

    if due:
        print(f"::notice title=Zwischenstand::Zuerst der tägliche Lauf – {why}")
        outcome, conn = _run_pipeline(state_dir, "produktiv", trigger="manuell", planned=None, force=False, key=key, on_checkpoint=upload_checkpoint)
        try:
            print(workflow_notice(conn, outcome))
        except Exception as exc:  # Bericht ist Beiwerk
            LOG.warning("Kurzbericht nicht erstellt: %s", exc)
        finally:
            conn.close()
    conn = connect(state_dir / "state.sqlite")
    try:
        outcome = _run_intraday(conn, state_dir, "produktiv", key)
        print(intraday_notice(outcome))
        sync_up(store, state_dir, conn, key, keep_archives=int(pipeline.get("aufbewahrung.archiv_snapshots", 60)))
        archives = _signal_archive(conn)
    finally:
        conn.close()
    wanted = [s["snapshot_id"] for s in retained_snapshots(read_json(state_dir / "site_meta" / "index.json"), keep)]
    sync_down(store, state_dir, passphrase, wanted_snapshots=wanted, wanted_archives=archives)
    assemble_site(app_dist=Path(args.app_dist), state_dir=state_dir, out_dir=Path(args.site), crypto_descriptor=descriptor, keep=keep)
    _write_output("deploy", "true")
    _write_output("status", outcome.status)
    if outcome.exit_code == EXIT_FAILED:
        print(f"::warning::Zwischenstand nicht erstellt ({outcome.message}); der bisherige Stand bleibt sichtbar")
        return 0 if args.soft_fail else EXIT_FAILED
    return 0


def intraday_notice(outcome: RunOutcome) -> str:
    """Kurzbericht des Zwischenstands für die Laufübersicht – nur Zahlen, Börsencodes und Uhrzeiten, keine Kurse."""
    info = (outcome.details or {}).get("details", {}).get("zwischenstand") if isinstance((outcome.details or {}).get("details"), dict) else None
    if outcome.status != "veroeffentlicht" or not info:
        return f"::notice title=Zwischenstand::{outcome.status}: {outcome.message}".replace("%", "%25")
    parts = [
        f"Stichtag {info['stichtag']}",
        f"{info['aktien_mit_kurs']} Aktien mit aktuellem Kurs (bis {str(info.get('kurse_bis_utc') or '?')[11:16]} UTC, davon {info['davon_sitzung_beendet']} nach Börsenschluss)",
        f"{info['abrufe']} Sammelabfragen" + (", gedrosselt" if info.get("gedrosselt") else ""),
        "Börsen mit Kurs: " + (", ".join(info.get("boersen_mit_kurs") or []) or "–"),
        "ohne Kurs: " + (", ".join(info.get("boersen_ohne_kurs") or []) or "–"),
        "Tagwahl: " + "; ".join(f"{c['tag']} {c['mit_kurs']}/{c['erwartet']}" for c in info.get("tagwahl") or []),
    ]
    return ("::notice title=Zwischenstand::" + " | ".join(parts)).replace("%", "%25")


def _write_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def cmd_site(args) -> int:
    state_dir = Path(args.state_dir)
    passphrase = os.environ.get("DATA_PASSPHRASE") if not args.demo else None
    key, descriptor = load_or_create_key(state_dir, passphrase, allow_new=False) if passphrase else (None, crypto.crypto_descriptor(None))
    if (state_dir / "crypto.json").exists() and not passphrase:
        descriptor = read_json(state_dir / "crypto.json")
    keep = int(load_pipeline_config().get("aufbewahrung.site_snapshots", 5))
    result = assemble_site(app_dist=Path(args.app_dist), state_dir=state_dir, out_dir=Path(args.site), crypto_descriptor=descriptor, keep=keep)
    print(json.dumps(result["snapshots"]))
    return 0


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".webmanifest": "application/manifest+json",
        ".bin": "application/octet-stream",
        ".js": "text/javascript",
        ".json": "application/json",
        ".svg": "image/svg+xml",
    }

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args) -> None:  # leise
        pass


def cmd_serve(args) -> int:
    handler = functools.partial(_Handler, directory=str(Path(args.site).resolve()))
    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Lokale Vorschau: http://127.0.0.1:{args.port}/  (nur dieser Rechner, keine dauerhafte Bereitstellung)")
        server.serve_forever()
    return 0


def cmd_restore_test(args) -> int:
    """Sichert die Datenbank, stellt sie in einer sauberen Umgebung wieder her und vergleicht.

    Mit ``--aus-release`` wird zuerst die echte Sicherung aus den GitHub-Release-Assets geladen
    (monatlicher Wiederherstellungstest im Workflow „Sicherung prüfen“).
    """
    state_dir = Path(args.state_dir)
    passphrase = os.environ.get("DATA_PASSPHRASE")
    if getattr(args, "aus_release", False):
        store = GitHubReleaseStore.from_env(tag=load_pipeline_config().get("github.release_tag", "datenstand"))
        info = sync_down(store, state_dir, passphrase)
        if not info["database"]:
            print(json.dumps({"wiederherstellung_ok": False, "grund": "Keine Datenbanksicherung im Release gefunden"}, ensure_ascii=False))
            return EXIT_FAILED
    key = None
    if passphrase and (state_dir / "crypto.json").exists():
        key = crypto.verify_descriptor(read_json(state_dir / "crypto.json"), passphrase)
    conn = connect(state_dir / "state.sqlite")
    try:
        blob_path = pack_database(conn, state_dir, key)
        with tempfile.TemporaryDirectory() as clean:
            target = Path(clean) / "restored.sqlite"
            unpack_database(blob_path.read_bytes(), key, target)
            restored = connect(target)
            try:
                report = {}
                for table in ("instrument", "listing", "daily_bar", "run", "snapshot_manifest", "universe_member"):
                    a = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608 - feste Tabellennamen
                    b = restored.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
                    report[table] = {"original": a, "wiederhergestellt": b, "gleich": a == b}
            finally:
                restored.close()
    finally:
        conn.close()
    ok = all(v["gleich"] for v in report.values())
    print(json.dumps({"wiederherstellung_ok": ok, "tabellen": report}, ensure_ascii=False, indent=2))
    return 0 if ok else EXIT_FAILED


def cmd_verify_site(args) -> int:
    from .util.crypto import ContainerError, unpack

    site = Path(args.site)
    descriptor = read_json(site / "data" / "crypto.json")
    key = None
    if descriptor.get("enabled"):
        passphrase = os.environ.get("DATA_PASSPHRASE")
        if not passphrase:
            print("DATA_PASSPHRASE fehlt für verschlüsselte Website")
            return EXIT_FAILED
        key = crypto.verify_descriptor(descriptor, passphrase)
    errors = []
    count = 0
    # Kein Geheimnis darf in einer veröffentlichten Datei stehen – weder im Klartext noch entschlüsselt.
    secrets = [v.encode("utf-8") for v in (os.environ.get(n) for n in ("DATA_PASSPHRASE", "OPENFIGI_API_KEY", "EODHD_API_KEY", "GITHUB_TOKEN")) if v and len(v) >= 6]

    def leaked(data: bytes) -> bool:
        return any(secret in data for secret in secrets)

    published = sorted((site / "data" / "snapshots").rglob("*.bin")) + sorted((site / "data" / "signale").rglob("*.bin"))
    for path in published:
        rel = path.relative_to(site / "data").as_posix()
        try:
            plain = unpack(path.read_bytes(), key, rel)
            payload = json.loads(plain.decode("utf-8"))
            if "schema" not in payload:
                errors.append(f"{rel}: Schema fehlt")
            if leaked(plain):
                errors.append(f"{rel}: enthält ein Geheimnis")
            count += 1
        except (ContainerError, ValueError) as exc:
            errors.append(f"{rel}: {exc}")
    for path in sorted(site.rglob("*")):
        if path.is_file() and path.suffix != ".bin" and leaked(path.read_bytes()):
            errors.append(f"{path.relative_to(site).as_posix()}: enthält ein Geheimnis")
    print(json.dumps({"dateien": count, "geheimnisse_geprueft": len(secrets), "fehler": errors[:20], "ok": not errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    setup_logging(os.environ.get("LOG_LEVEL", "INFO"))
    parser = argparse.ArgumentParser(prog="traktien", description=f"TR-Aktienvergleich {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("demo", help="DEMO-Lauf mit synthetischen Testdaten")
    p.add_argument("--state-dir", default="build/demo-state")
    p.add_argument("--site", default="build/demo-site")
    p.add_argument("--app-dist", default=str(DEFAULT_APP_DIST))
    p.add_argument("--passphrase", default=None, help="optional: DEMO verschlüsselt veröffentlichen")
    p.add_argument("--fresh", action="store_true")
    p.add_argument("--zwischenstand", action="store_true", help="danach einen DEMO-Zwischenstand mit synthetischen aktuellen Kursen rechnen")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("run", help="Produktiver Lauf mit lokalem Zustand")
    p.add_argument("--state-dir", default="state")
    p.add_argument("--trigger", default="manuell")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("ci", help="Produktiver Lauf in GitHub Actions")
    p.add_argument("--state-dir", default="state")
    p.add_argument("--site", default="_site")
    p.add_argument("--app-dist", default=str(DEFAULT_APP_DIST))
    p.add_argument("--force", action="store_true", help="neu berechnen und veröffentlichen, auch ohne neuen Börsenschluss")
    p.add_argument("--reset-state", action="store_true", help="gespeicherten Zustand verwerfen und alles neu laden")
    p.add_argument(
        "--nur-website",
        action="store_true",
        help="nur die Website aus dem gespeicherten Stand neu zusammensetzen (z. B. nach einer App-Änderung) – ohne Abruf und Berechnung",
    )
    p.add_argument(
        "--kennzahlen",
        action="store_true",
        help="nur Kennzahlen, Kursziele und Signale aktualisieren – ohne Kursabruf und ohne neue Ranglisten",
    )
    p.add_argument(
        "--zwischenstand",
        action="store_true",
        help="Zwischenstand: alle Ranglisten mit aktuellen (verzögerten) Kursen des laufenden Handelstags neu rechnen – vorläufig gekennzeichnet",
    )
    p.add_argument(
        "--soft-fail",
        action="store_true",
        help="fehlgeschlagenen Lauf mit Code 0 beenden (nur für lokale Versuche; der Workflow nutzt es nicht, damit GitHub bei Fehlern benachrichtigt)",
    )
    p.set_defaults(func=cmd_ci)

    p = sub.add_parser("site", help="Website zusammenbauen")
    p.add_argument("--state-dir", default="state")
    p.add_argument("--site", default="_site")
    p.add_argument("--app-dist", default=str(DEFAULT_APP_DIST))
    p.add_argument("--demo", action="store_true")
    p.set_defaults(func=cmd_site)

    p = sub.add_parser("serve", help="Lokale Vorschau")
    p.add_argument("--site", default="build/demo-site")
    p.add_argument("--port", type=int, default=8080)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("restore-test", help="Sicherung/Wiederherstellung prüfen")
    p.add_argument("--state-dir", default="state")
    p.add_argument("--aus-release", action="store_true", help="Sicherung vorher aus den GitHub-Release-Assets laden")
    p.set_defaults(func=cmd_restore_test)

    p = sub.add_parser("verify-site", help="Veröffentlichte Dateien prüfen")
    p.add_argument("--site", default="_site")
    p.set_defaults(func=cmd_verify_site)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except StateError as exc:
        print(f"::error::{exc}")
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
