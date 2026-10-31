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
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from . import __version__
from .config import REPO_ROOT, load_method_config, load_pipeline_config, load_yaml
from .jobs.daily import EXIT_FAILED, EXIT_LOCKED, EXIT_OK, EXIT_RETRY, DailyRun, RunOptions, RunOutcome, build_status_file
from .jobs.sources import demo_sources, production_sources
from .jobs.state import GitHubReleaseStore, StateError, load_or_create_key, pack_database, sync_down, sync_up, unpack_database
from .jobs.summary import workflow_notice
from .providers.exchanges import load_exchange_table
from .publish.site import SITE_SNAPSHOTS_DEFAULT, assemble_site, retained_snapshots
from .store.db import connect
from .util import crypto
from .util.jsonio import read_json
from .util.log import get_logger, setup_logging

LOG = get_logger("traktien")
DEFAULT_APP_DIST = REPO_ROOT / "app" / "dist"


def _reviews() -> list[dict]:
    data = load_yaml("pruefungen.yaml") or {}
    return list(data.get("kurssprung_entscheidungen") or [])


def run_trigger(event: str | None, actor: str | None) -> str:
    """Auslöser eines Laufs für Status und App: „zeitplan“ (GitHub-Zeitplan), „nachtlauf“ (ab 1.17: vom Workflow
    „Nachtlauf“ gestartet – GitHub meldet dann den Bot als Auslöser) oder „manuell“ (Knopf „Run workflow“, eigener
    externer Auslöser mit dem eigenen Token)."""
    if event == "schedule":
        return "zeitplan"
    if event == "workflow_dispatch" and actor == "github-actions[bot]":
        return "nachtlauf"
    return "manuell"


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
        demo_sources(kursabgleich=True)
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
        keep = int(load_pipeline_config().get("aufbewahrung.site_snapshots", SITE_SNAPSHOTS_DEFAULT))
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
    STOPWATCH.reset()
    if args.reset_state:
        LOG.warning("Zustand wird bewusst neu aufgebaut (Eingabe zustand_neu_aufbauen)")
        assets = store.assets()
        for name in ("state.sqlite.tra", "state.sqlite.tra.neu", "crypto.json"):
            if name in assets:
                store.delete(assets[name])
    STOPWATCH.start("Zustand laden")
    sync_down(store, state_dir, passphrase)
    STOPWATCH.stop()
    if args.nur_website:
        return _ci_site_only(store, state_dir, passphrase, pipeline, args)
    if args.kennzahlen:
        return _ci_facts_only(store, state_dir, passphrase, pipeline, args)
    # Ab 1.9.1 ist „Zwischenstand“ die Voreinstellung eines von Hand gestarteten Laufs („alles aktualisieren“).
    # „erzwingen“ und „zustand_neu_aufbauen“ meinen immer den offiziellen Lauf.
    if args.zwischenstand and not args.force and not args.reset_state:
        if getattr(args, "stufe", None) == 1:
            return _ci_stage_one(store, state_dir, passphrase, pipeline, args)
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
    trigger = run_trigger(os.environ.get("GITHUB_EVENT_NAME"), os.environ.get("GITHUB_ACTOR"))
    outcome, conn = _run_pipeline(state_dir, "produktiv", trigger=trigger, planned=planned, force=args.force, key=key, on_checkpoint=upload_checkpoint)
    code, status = outcome.exit_code, outcome.status
    keep = int(pipeline.get("aufbewahrung.site_snapshots", SITE_SNAPSHOTS_DEFAULT))
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
    keep = int(pipeline.get("aufbewahrung.site_snapshots", SITE_SNAPSHOTS_DEFAULT))
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
        build_status_file(conn, state_dir, mode, pipeline, last_run_id=last["id"] if last else None, now=dt.datetime.now(tz=dt.timezone.utc), keep_next=True)
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
    keep = int(pipeline.get("aufbewahrung.site_snapshots", SITE_SNAPSHOTS_DEFAULT))
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
        # Datenmodus des veröffentlichten Stands (im Betrieb „produktiv“) – sonst fehlten Stände und Zwischenstand im Status
        mode_row = conn.execute("SELECT data_mode FROM snapshot_manifest WHERE status = 'veroeffentlicht' ORDER BY cutoff_day DESC, published_at DESC LIMIT 1").fetchone()
        data_mode = mode_row["data_mode"] if mode_row and mode_row["data_mode"] else "produktiv"
        build_status_file(conn, state_dir, data_mode, pipeline, last_run_id=last["id"] if last else None, now=dt.datetime.now(tz=dt.timezone.utc), keep_next=True)
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

        sources = demo_sources(kursabgleich=True)
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


def _run_intraday(conn, state_dir: Path, mode: str, key, *, stage: dict | None = None, only: list[str] | None = None) -> RunOutcome:
    """Zwischenstand (ab 1.8) mit der offenen Datenbankverbindung. ``stage``/``only`` (ab 1.10): Stufe der
    gestaffelten Aktualisierung und – in Stufe 1 – die zuerst zu aktualisierenden Aktien (ISINs)."""
    from .jobs.intraday import IntradayRun

    pipeline = load_pipeline_config()
    sources, table = _sources_for(mode, pipeline)
    run = IntradayRun(conn, state_dir, sources, load_method_config(), pipeline, table, key, RunOptions(trigger="zwischenstand"))
    run.stage = stage
    run.only_isins = set(only) if only is not None else None
    return run.execute()


def _ci_stage_one(store, state_dir: Path, passphrase: str | None, pipeline, args) -> int:
    """Gestaffelte Aktualisierung, Stufe 1 (ab 1.11): zuerst nur die Kurse der wichtigsten Aktien – der sich
    wiederholenden Spitzenreiter des letzten Stands –, sofort rechnen und als Zwischenstand bereitstellen.

    Stufe 1 liest den gespeicherten Zustand nur: nichts wird hochgeladen. Parallel rechnet der Job „berechnen“
    alle Aktien (Stufe 2), sichert den Zustand und ersetzt Stufe 1 auf der Website."""
    from .jobs.priority import priority_isins
    from .store import repo as _repo

    keep = int(pipeline.get("aufbewahrung.site_snapshots", SITE_SNAPSHOTS_DEFAULT))
    if not (state_dir / "state.sqlite").exists() or not (state_dir / "crypto.json").exists():
        print("::notice title=Stufe 1::Noch kein gespeicherter Zustand – nur Stufe 2 läuft")
        _write_output("deploy", "false")
        return 0
    key, descriptor = load_or_create_key(state_dir, passphrase, allow_new=False)
    data_mode = _sources_for("produktiv", pipeline)[0].data_mode  # in Tests mit DEMO-Quellen „demo“
    conn = connect(state_dir / "state.sqlite")
    try:
        intraday = _repo.current_intraday(conn, data_mode)
        official = _repo.published_snapshots(conn, data_mode, limit=1)
        latest_id = intraday["id"] if intraday is not None else (official[0]["id"] if official else None)
        if latest_id is None:
            print("::notice title=Stufe 1::Noch kein veröffentlichter Stand – nur Stufe 2 läuft")
            _write_output("deploy", "false")
            return 0
        STOPWATCH.start("Reihenfolge bestimmen")
        sync_down(store, state_dir, passphrase, wanted_snapshots=[latest_id], include_database=False)
        archive = state_dir / "archives" / f"site-{latest_id}.tar"
        order = (
            priority_isins(
                archive,
                latest_id,
                key,
                top_n=int(pipeline.get("zwischenstand.stufe1_platz_bis", 25)),
                limit=int(pipeline.get("zwischenstand.stufe1_hoechstens", 1500)),
            )
            if archive.exists()
            else []
        )
        STOPWATCH.stop()
        if not order:
            print("::notice title=Stufe 1::Keine Reihenfolge aus dem letzten Stand – nur Stufe 2 läuft")
            _write_output("deploy", "false")
            return 0
        stage = {
            "nummer": 1,
            "von": 2,
            "aktien": len(order),
            "grundlage": latest_id,
            "beschreibung": "Zuerst die Aktien, die sich in den oberen Rängen wiederholen; alle übrigen folgen in Stufe 2.",
            "reihenfolge": order,
        }
        STOPWATCH.start("Vorbereitung")
        outcome = _run_intraday(conn, state_dir, "produktiv", key, stage=stage, only=order)
        STOPWATCH.stop()
        _split_intraday_time(outcome)
        print(intraday_notice(outcome).replace("title=Zwischenstand", "title=Stufe 1", 1))
        archives = _signal_archive(conn)
    finally:
        conn.close()
    if outcome.status != "veroeffentlicht":
        print(f"::notice title=Stufe 1::{outcome.status} – Stufe 2 rechnet alle Aktien")
        _write_output("deploy", "false")
        return 0
    STOPWATCH.start("ältere Stände laden")
    wanted = [s["snapshot_id"] for s in retained_snapshots(read_json(state_dir / "site_meta" / "index.json"), keep)]
    sync_down(store, state_dir, passphrase, wanted_snapshots=wanted, wanted_archives=archives, include_database=False)
    STOPWATCH.start("Website zusammenstellen")
    assemble_site(app_dist=Path(args.app_dist), state_dir=state_dir, out_dir=Path(args.site), crypto_descriptor=descriptor, keep=keep)
    print(STOPWATCH.notice(title="Dauer Stufe 1"))
    _write_output("deploy", "true")
    _write_output("status", outcome.status)
    return 0


def _stage_of(args) -> dict | None:
    """Gestaffelte Aktualisierung (ab 1.10): der volle Lauf ist Stufe 2, wenn parallel eine Stufe 1 läuft."""
    return {"nummer": 2, "von": 2} if getattr(args, "gestaffelt", False) else None


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
    keep = int(pipeline.get("aufbewahrung.site_snapshots", SITE_SNAPSHOTS_DEFAULT))
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
        prep_ids, prep_signals = _site_prep_targets(conn, pipeline, keep)
    finally:
        conn.close()
    # Ältere Stände und Signal-Stand laden und entpacken, während Kurse abgerufen und gerechnet wird (ab 1.12)
    prep = _SitePrep(state_dir, passphrase, prep_ids, prep_signals, tag=pipeline.get("github.release_tag", "datenstand"))
    prep.start()

    def upload_checkpoint(conn) -> None:
        try:
            sync_up(store, state_dir, conn, key, keep_archives=int(pipeline.get("aufbewahrung.archiv_snapshots", 60)))
        except Exception as exc:  # Checkpoint-Upload darf den Lauf nicht abbrechen
            LOG.warning("Checkpoint-Upload fehlgeschlagen: %s", exc)

    official_new = False
    if due:
        print(f"::notice title=Zwischenstand::Zuerst der tägliche Lauf – {why}")
        STOPWATCH.start("offizieller Lauf")
        outcome, conn = _run_pipeline(state_dir, "produktiv", trigger="manuell", planned=None, force=False, key=key, on_checkpoint=upload_checkpoint)
        official_new = outcome.status == "veroeffentlicht" and outcome.snapshot_id is not None
        try:
            print(workflow_notice(conn, outcome))
        except Exception as exc:  # Bericht ist Beiwerk
            LOG.warning("Kurzbericht nicht erstellt: %s", exc)
        finally:
            conn.close()
    conn = connect(state_dir / "state.sqlite")
    try:
        STOPWATCH.start("Vorbereitung")
        outcome = _run_intraday(conn, state_dir, "produktiv", key, stage=_stage_of(args))
        STOPWATCH.stop()
        _split_intraday_time(outcome)
        print(intraday_notice(outcome))
        archives = _signal_archive(conn)
        conn.commit()
    finally:
        conn.close()
    # Sichern (Datenbank packen und hochladen) läuft parallel zum Zusammenstellen der Website (ab 1.10). In GitHub
    # Actions ab 1.12 als eigener Prozess, der weiterläuft, während der Workflow die Website prüft und hochlädt;
    # gewartet wird erst am Ende des Jobs („sichern-warten“) – bereitgestellt wird nur nach erfolgreichem Sichern.
    began = time.monotonic()
    keep_archives = int(pipeline.get("aufbewahrung.archiv_snapshots", 60))
    saver: _BackgroundSave | None = None
    if _save_in_background_process():
        _spawn_save(state_dir, _archive_names(state_dir), keep_archives)
        _write_output("sichern", "hintergrund")
    else:
        saver = _BackgroundSave(state_dir, key, keep_archives=keep_archives)
        saver.start()
    STOPWATCH.start("Vorbereitung abwarten")
    prep.finish()
    STOPWATCH.start("ältere Stände laden")
    wanted = [s["snapshot_id"] for s in retained_snapshots(read_json(state_dir / "site_meta" / "index.json"), keep)]
    # Nur Archive laden: die Datenbank ist lokal die neueste und wird gerade im Hintergrund gesichert
    sync_down(
        GitHubReleaseStore.from_env(tag=pipeline.get("github.release_tag", "datenstand")),
        state_dir,
        passphrase,
        wanted_snapshots=wanted,
        wanted_archives=archives,
        include_database=False,
    )
    STOPWATCH.start("Website zusammenstellen")
    assemble_site(app_dist=Path(args.app_dist), state_dir=state_dir, out_dir=Path(args.site), crypto_descriptor=descriptor, keep=keep)
    if saver is not None:
        STOPWATCH.start("auf Sichern warten")
        saver.finish()
        STOPWATCH.stop()
        STOPWATCH.add("(Sichern parallel)", time.monotonic() - began)
    print(STOPWATCH.notice())
    print(_site_size_notice(Path(args.site)))
    _write_output("deploy", "true")
    _write_output("status", outcome.status)
    # Neuer offizieller Stand in diesem Lauf: danach wie beim täglichen Lauf Kennzahlen und Signale (Job „kennzahlen“)
    _write_output("kennzahlen", "true" if official_new else "false")
    if outcome.exit_code == EXIT_FAILED:
        print(f"::warning::Zwischenstand nicht erstellt ({outcome.message}); der bisherige Stand bleibt sichtbar")
        return 0 if args.soft_fail else EXIT_FAILED
    return 0


def _site_size_notice(site: Path) -> str:
    """Größe der Website für die Laufübersicht (ab 1.12): Dateien und MB je Bereich – nur Zählungen."""
    parts: dict[str, list[int]] = {}
    for root, _dirs, files in os.walk(site):
        rel = Path(root).relative_to(site).parts
        area = "Stände" if rel[:2] == ("data", "snapshots") else "Signale" if rel[:2] == ("data", "signale") else "App"
        entry = parts.setdefault(area, [0, 0])
        for name in files:
            try:
                entry[1] += os.stat(os.path.join(root, name)).st_size
            except OSError:
                continue
            entry[0] += 1
    total = sum(v[1] for v in parts.values())
    text = " | ".join(f"{area} {count} Dateien, {size / 1e6:.1f} MB" for area, (count, size) in sorted(parts.items()))
    return f"::notice title=Website::{text} | zusammen {total / 1e6:.1f} MB".replace("%", "%25")


def _split_intraday_time(outcome: RunOutcome) -> None:
    """Die Zeit des Zwischenstands in Kursabruf, Rechnen, Schreiben und Übriges aufteilen (Laufübersicht)."""
    details = (outcome.details or {}).get("details")
    times = details.get("zeiten") if isinstance(details, dict) else None
    if not times or not STOPWATCH.parts or STOPWATCH.parts[-1][0] != "Vorbereitung":
        return
    _, total = STOPWATCH.parts.pop()
    known = 0.0
    if "daten_laden" in times and "rechnen" in times:  # ab 1.12: Laden aus der Datenbank getrennt vom Rechnen
        times = dict(times, rechnen=max(0.0, float(times["rechnen"]) - float(times["daten_laden"])))
    for key, name in (("kurse", "Kurse abrufen"), ("daten_laden", "Kursreihen laden"), ("rechnen", "Rechnen"), ("schreiben", "Dateien schreiben"), ("archiv", "Archiv")):
        if key in times:
            STOPWATCH.add(name, float(times[key]))
            known += float(times[key])
    STOPWATCH.add("Übriges", max(0.0, total - known))


def _ways_text(ways: dict | None) -> str:
    """„ (quote 40 → 5.300 Kurse, spark 22 → 171)“ – nur Zählungen (ab 1.12)."""
    if not ways:
        return ""
    parts = [f"{name} {w.get('abrufe', 0)} → {w.get('kurse', 0)} Kurse" for name, w in ways.items() if w.get("abrufe")]
    return f" ({', '.join(parts)})" if parts else ""


def intraday_notice(outcome: RunOutcome) -> str:
    """Kurzbericht des Zwischenstands für die Laufübersicht – nur Zahlen, Börsencodes und Uhrzeiten, keine Kurse."""
    info = (outcome.details or {}).get("details", {}).get("zwischenstand") if isinstance((outcome.details or {}).get("details"), dict) else None
    if outcome.status != "veroeffentlicht" or not info:
        return f"::notice title=Zwischenstand::{outcome.status}: {outcome.message}".replace("%", "%25")
    parts = [
        f"Stichtag {info['stichtag']}",
        f"{info['aktien_mit_kurs']} Aktien mit aktuellem Kurs (bis {str(info.get('kurse_bis_utc') or '?')[11:16]} UTC, davon {info['davon_sitzung_beendet']} nach Börsenschluss)",
        f"{info['abrufe']} Sammelabfragen" + _ways_text(info.get("wege")) + (", gedrosselt" if info.get("gedrosselt") else ""),
        "Börsen mit Kurs: " + (", ".join(info.get("boersen_mit_kurs") or []) or "–"),
        "ohne Kurs: " + (", ".join(info.get("boersen_ohne_kurs") or []) or "–"),
        "Tagwahl: " + "; ".join(f"{c['tag']} {c['mit_kurs']}/{c['erwartet']}" for c in info.get("tagwahl") or []),
    ]
    return ("::notice title=Zwischenstand::" + " | ".join(parts)).replace("%", "%25")


def _site_prep_targets(conn, pipeline, keep: int) -> tuple[list[str], list[str]]:
    """Welche älteren Stände und welcher Signal-Stand voraussichtlich auf die Website kommen (ab 1.12): die
    neuesten ``keep`` offiziellen Stände und der neueste vollständige – eine Obermenge dessen, was nach dem Lauf
    bleibt. Nur für das Laden im Voraus; entschieden wird beim Zusammenstellen."""
    from .store import repo as _repo

    data_mode = _sources_for("produktiv", pipeline)[0].data_mode
    published = _repo.published_snapshots(conn, data_mode)
    ids = [row["id"] for row in published[:keep]]
    complete = next((row["id"] for row in published if row["completeness"] == "vollstaendig"), None)
    if complete is not None and complete not in ids:
        ids.append(complete)
    return ids, _signal_archive(conn)


class _SitePrep:
    """Lädt ältere Stände und den Signal-Stand im Hintergrund und entpackt sie (ab 1.12), während Kurse abgerufen
    und Ranglisten gerechnet werden. Ein Fehler ist nicht schlimm: dann stellt der bisherige Weg die Website
    zusammen (Archive laden und entpacken)."""

    def __init__(self, state_dir: Path, passphrase: str | None, snapshot_ids: list[str], signal_archives: list[str], *, tag: str) -> None:
        import threading

        self.state_dir = Path(state_dir)
        self.passphrase = passphrase
        self.snapshot_ids = list(snapshot_ids)
        self.signal_archives = list(signal_archives)
        self.tag = tag
        self.result: dict | None = None
        self.error: BaseException | None = None
        self.thread = threading.Thread(target=self._run, name="website-vorbereiten", daemon=True)

    def _run(self) -> None:
        from .publish.site import prepare_site_cache

        try:
            store = GitHubReleaseStore.from_env(tag=self.tag)
            sync_down(store, self.state_dir, self.passphrase, wanted_snapshots=self.snapshot_ids, wanted_archives=self.signal_archives, include_database=False)
            self.result = prepare_site_cache(self.state_dir, self.snapshot_ids, self.signal_archives)
        except BaseException as exc:  # nie den Lauf gefährden
            self.error = exc

    def start(self) -> None:
        self.thread.start()

    def finish(self) -> None:
        self.thread.join()
        if self.error is not None:
            LOG.warning("Website im Voraus vorbereiten fehlgeschlagen (%s) – Zusammenstellen wie bisher", type(self.error).__name__)


def _archive_names(state_dir: Path) -> list[str]:
    """Archive, die jetzt da sind (danach lädt das Zusammenstellen weitere herunter – die sind schon gesichert)."""
    return sorted(p.name for p in (Path(state_dir) / "archives").glob("*") if not p.name.startswith("."))


_SPAWNED: list = []
SAVE_PID = ".sichern.pid"
SAVE_RESULT = ".sichern.json"
SAVE_LOG = ".sichern.log"


def _save_in_background_process() -> bool:
    """Ab 1.12 in GitHub Actions (Umgebungsvariable SICHERN_IM_HINTERGRUND): Sichern als eigener Prozess."""
    return os.environ.get("SICHERN_IM_HINTERGRUND", "").strip().lower() == "true"


def _spawn_save(state_dir: Path, names: list[str], keep_archives: int) -> None:
    """Startet ``traktien sichern`` als eigenen Prozess (läuft nach dem Ende dieses Schritts weiter)."""
    import subprocess

    state_dir = Path(state_dir)
    for name in (SAVE_RESULT, SAVE_PID):
        (state_dir / name).unlink(missing_ok=True)
    command = [sys.executable, "-m", "traktien", "sichern", "--state-dir", str(state_dir), "--behalten", str(keep_archives), "--archive", *names]
    with open(state_dir / SAVE_LOG, "ab") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, env=dict(os.environ))
    _SPAWNED.append(process)  # Verweis behalten: der Prozess läuft bewusst über das Ende dieses Schritts hinaus
    (state_dir / SAVE_PID).write_text(str(process.pid), encoding="utf-8")


def cmd_save(args) -> int:
    """Datenbank und Archive sichern (eigener Prozess des Zwischenstands, ab 1.12); Ergebnis in ``.sichern.json``."""
    from .util.jsonio import atomic_write_json
    from .util.log import redact

    state_dir = Path(args.state_dir)
    started = time.monotonic()
    try:
        key, _ = load_or_create_key(state_dir, os.environ.get("DATA_PASSPHRASE"), allow_new=False)
        store = GitHubReleaseStore.from_env(tag=load_pipeline_config().get("github.release_tag", "datenstand"))
        conn = connect(state_dir / "state.sqlite")
        try:
            info = sync_up(store, state_dir, conn, key, keep_archives=args.behalten, archive_names=list(args.archive or []))
        finally:
            conn.close()
        result = {"status": "ok", "hochgeladen": len(info.get("uploaded", [])), "entfernt": len(info.get("removed", []))}
    except Exception as exc:  # Ergebnis für „sichern-warten“ festhalten
        result = {"status": "fehler", "meldung": f"{type(exc).__name__}: {redact(str(exc))[:300]}"}
    result["sekunden"] = round(time.monotonic() - started, 1)
    atomic_write_json(state_dir / SAVE_RESULT, result)
    return 0 if result["status"] == "ok" else EXIT_FAILED


def cmd_save_wait(args) -> int:
    """Auf das Sichern im Hintergrund warten (letzter Schritt des Jobs, ab 1.12)."""
    state_dir = Path(args.state_dir)
    pid_file = state_dir / SAVE_PID
    pid = int(pid_file.read_text(encoding="utf-8").strip()) if pid_file.exists() else None
    started = time.monotonic()
    while pid is not None and time.monotonic() - started < args.timeout:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        except PermissionError:  # pragma: no cover - fremder Prozess mit gleicher Nummer
            break
        try:
            done, _ = os.waitpid(pid, os.WNOHANG)  # eigenes Kind (in Tests): beenden lassen
            if done == pid:
                break
        except ChildProcessError:
            pass
        time.sleep(0.2)
    waited = time.monotonic() - started
    result_file = state_dir / SAVE_RESULT
    if not result_file.exists():
        print(f"::error::Sichern im Hintergrund ohne Ergebnis (nach {waited:.0f} s) – der Zustand ist nicht gesichert; siehe {SAVE_LOG}")
        return EXIT_FAILED
    result = read_json(result_file)
    if result.get("status") != "ok":
        print(f"::error::Sichern im Hintergrund fehlgeschlagen: {result.get('meldung')}")
        return EXIT_FAILED
    print(f"::notice title=Sichern::im Hintergrund in {result.get('sekunden')} s ({result.get('hochgeladen')} Dateien hochgeladen); am Ende gewartet {waited:.0f} s")
    return 0


class _BackgroundSave:
    """Sichert Datenbank und neue Archive in einem eigenen Thread (eigene Datenbankverbindung, eigener
    Release-Zugriff), während die Website zusammengestellt wird. Ein Fehler beim Sichern lässt den Lauf
    scheitern – wie bisher, nur später gemeldet."""

    def __init__(self, state_dir: Path, key, *, keep_archives: int) -> None:
        import threading

        self.state_dir = Path(state_dir)
        self.key = key
        self.keep_archives = keep_archives
        self.names = _archive_names(self.state_dir)
        self.error: BaseException | None = None
        self.thread = threading.Thread(target=self._run, name="sichern", daemon=True)

    def _run(self) -> None:
        try:
            store = GitHubReleaseStore.from_env(tag=load_pipeline_config().get("github.release_tag", "datenstand"))
            conn = connect(self.state_dir / "state.sqlite")
            try:
                sync_up(store, self.state_dir, conn, self.key, keep_archives=self.keep_archives, archive_names=self.names)
            finally:
                conn.close()
        except BaseException as exc:  # im Hauptthread erneut auslösen
            self.error = exc

    def start(self) -> None:
        self.thread.start()

    def finish(self) -> None:
        self.thread.join()
        if self.error is not None:
            raise self.error


class _Stopwatch:
    """Dauer je Abschnitt eines Laufs (ab 1.10) – nur Sekunden, für die Laufübersicht."""

    def __init__(self) -> None:
        self.parts: list[tuple[str, float]] = []
        self._label: str | None = None
        self._began = 0.0

    def start(self, label: str) -> None:
        self.stop()
        self._label, self._began = label, time.monotonic()

    def stop(self) -> None:
        if self._label is not None:
            self.parts.append((self._label, time.monotonic() - self._began))
            self._label = None

    def add(self, label: str, seconds: float) -> None:
        self.parts.append((label, seconds))

    def reset(self) -> None:
        """Neu beginnen (je Aufruf von ``ci`` – in Tests laufen mehrere Aufrufe im selben Prozess)."""
        self.parts.clear()
        self._label = None

    def notice(self, title: str = "Dauer") -> str:
        self.stop()
        total = sum(s for _, s in self.parts)
        text = " | ".join(f"{label} {seconds:.0f} s" for label, seconds in self.parts) + f" | zusammen {total:.0f} s"
        return f"::notice title={title}::{text}".replace("%", "%25")


STOPWATCH = _Stopwatch()


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
    keep = int(load_pipeline_config().get("aufbewahrung.site_snapshots", SITE_SNAPSHOTS_DEFAULT))
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


def _verify_files(args) -> tuple[int, list[str]]:
    """Prüft veröffentlichte Dateien: entschlüsselbar, gültiges JSON mit Schema, kein Geheimnis im Klartext."""
    from .util.crypto import ContainerError, unpack

    data_dir, relative, key, secrets = args
    count, errors = 0, []
    for rel in relative:
        try:
            plain = unpack((Path(data_dir) / rel).read_bytes(), key, rel)
            # Schnellweg (ab 1.12): die Dateien beginnen mit dem Schema; sonst vollständig lesen wie bisher
            if not plain.startswith(b'{"schema":'):
                payload = json.loads(plain.decode("utf-8"))
                if not isinstance(payload, dict) or "schema" not in payload:
                    errors.append(f"{rel}: Schema fehlt")
            if any(secret in plain for secret in secrets):
                errors.append(f"{rel}: enthält ein Geheimnis")
            count += 1
        except (ContainerError, ValueError) as exc:
            errors.append(f"{rel}: {exc}")
    return count, errors


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
    # Entschlüsseln und Prüfen auf mehrere Prozesse verteilt (ab 1.10) – gleiche Prüfung je Datei
    from .analytics.engine import default_workers

    workers = default_workers()
    relative = [path.relative_to(site / "data").as_posix() for path in published]
    if workers > 1 and len(relative) > 2000:
        import multiprocessing
        from concurrent.futures import ProcessPoolExecutor

        size = max(200, len(relative) // (workers * 4) + 1)
        chunks = [relative[k : k + size] for k in range(0, len(relative), size)]
        context = multiprocessing.get_context("forkserver" if "forkserver" in multiprocessing.get_all_start_methods() else "spawn")
        try:
            with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
                results = list(pool.map(_verify_files, [(str(site / "data"), chunk, key, secrets) for chunk in chunks]))
        except (OSError, RuntimeError, ImportError, EOFError) as exc:  # ohne Hilfsprozesse: gleiche Prüfung in einem Prozess
            LOG.warning("Prüfung in mehreren Prozessen nicht möglich (%s) – prüfe in einem Prozess", type(exc).__name__)
            results = [_verify_files((str(site / "data"), relative, key, secrets))]
    else:
        results = [_verify_files((str(site / "data"), relative, key, secrets))]
    for done, found in results:
        count += done
        errors.extend(found)
    for path in sorted(site.rglob("*")):
        if path.is_file() and path.suffix != ".bin" and leaked(path.read_bytes()):
            errors.append(f"{path.relative_to(site).as_posix()}: enthält ein Geheimnis")
    print(json.dumps({"dateien": count, "geheimnisse_geprueft": len(secrets), "fehler": errors[:20], "ok": not errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else EXIT_FAILED


def cmd_kurse_aktualisieren(args) -> int:
    """Kursaktualisierung auf Wunsch der App (Workflow ``aktualisieren.yml``): Anfrage prüfen, nur diese Kurse abrufen,
    in Teilen liefern. Ausgabe nur Zählungen und Zeiten – nie ISINs, Namen, Symbole oder Kurse (öffentliches Protokoll)."""
    from .jobs import kursaktualisierung as ka

    started = time.monotonic()
    passphrase = os.environ.get("DATA_PASSPHRASE") or None
    key = None
    descriptor_path = Path(args.schluessel)
    if passphrase and descriptor_path.exists():
        try:
            key = crypto.verify_descriptor(read_json(descriptor_path), passphrase)
        except crypto.ContainerError:
            print("::error::Die Passphrase passt nicht zu den Schlüsselparametern (crypto.json)")
            return EXIT_FAILED
    if key is None and args.probe:
        # Probe ohne Datenschlüssel (Messung, DEMO): eigener Wegwerf-Schlüssel – nie der Schlüssel des Datenstands
        key = crypto.derive_key("DEMO-Kursaktualisierung" if args.demo else "Messung-Kursaktualisierung", b"demo-kursaktual." if args.demo else b"messung-kursakt.", 1000)
    key_seconds = time.monotonic() - started
    kennung, text = args.kennung, os.environ.get(args.anfrage_env, "")
    if args.probe:
        if key is None:
            print("::error::Probe braucht den Datenschlüssel (DATA_PASSPHRASE und crypto.json) oder --demo")
            return EXIT_FAILED
        values = ka.sample_values()[: max(1, min(args.probe, len(ka.sample_values())))]
        if args.demo:
            from .providers.demo import build_demo_universe

            values = [(i.isin, i.symbol) for i in build_demo_universe() if i.pattern not in ("no_data", "missing_cutoff")][: max(1, args.probe)]
        kennung = ka.neue_kennung()
        text = ka.build_anfrage(kennung, "auswahl", values, key, sichtbar=min(5, len(values)), kursverlauf=[values[0][0]])
    if args.demo:
        from .providers.demo import DemoProvider

        provider = DemoProvider()
    else:
        from .providers.yahoo import YahooProvider

        provider = YahooProvider()
    if args.kanal == "git":
        repository, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
        if not repository or not token:
            print("::error::Lieferkanal git braucht GITHUB_REPOSITORY und GITHUB_TOKEN")
            return EXIT_FAILED
        channel = ka.GitLieferkanal(repository, token, server=os.environ.get("GITHUB_SERVER_URL", "https://github.com"), branch=args.branch)
    else:
        channel = ka.OrdnerLieferkanal(Path(args.ordner))
    try:
        report = ka.fetch_and_deliver(kennung, text, provider, key, Path(args.arbeit), channel)
    finally:
        if hasattr(channel, "close"):
            channel.close()
    report.zeiten = {"Schlüssel": key_seconds, **report.zeiten, "Gesamt (Prozess)": time.monotonic() - started}
    line = report.zeile()
    print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::notice title=Kursaktualisierung::{line}")
    return EXIT_OK


def cmd_spielgeld_eingang(args) -> int:
    """Eingang aus der App prüfen (Workflow ``spielgeld-eingang.yml``) und – nur wenn angenommen – verschlüsselt auf den Branch
    „spielgeld-eingang“ legen; das Ergebnis für die App liegt immer verschlüsselt daneben. Wirksam wird ein Eingang erst im
    täglichen Lauf. Ausgabe nur Kennung, Art, Status und Code – nie Regelinhalte (öffentliches Protokoll)."""
    from .aktienpilot import eingang as ein
    from .aktienpilot import katalog as kat
    from .aktienpilot.config import load_aktienpilot_config
    from .jobs import kursaktualisierung as ka

    passphrase = os.environ.get("DATA_PASSPHRASE") or None
    key = None
    descriptor_path = Path(args.schluessel)
    if passphrase and descriptor_path.exists():
        try:
            key = crypto.verify_descriptor(read_json(descriptor_path), passphrase)
        except crypto.ContainerError:
            print("::error::Die Passphrase passt nicht zu den Schlüsselparametern (crypto.json)")
            return EXIT_FAILED
    kennung, text = args.kennung, os.environ.get(args.nutzlast_env, "")
    if not ein.KENNUNG_RE.match(kennung or ""):
        print("Spielgeld-Eingang: Kennung ungültig – nichts abgelegt")
        return EXIT_FAILED
    method = load_method_config()
    cfg = load_aktienpilot_config()
    eintraege = kat.katalog(method, cfg)
    work = Path(args.arbeit)
    files: list[Path] = []
    try:
        e, blob = ein.annehmen(text, kennung, key, eintraege, method, cfg=cfg)
        target = work / ein.ORDNER_EINGANG / f"{kennung}.bin"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        files.append(target)
        regel = f"{e.regel['id']}@{e.regel['version']}" if e.regel else None
        result = dict(angenommen=True, code="angenommen", text="Angenommen – wirksam mit dem nächsten täglichen Lauf", art=e.art, regel=regel)
    except ein.EingangFehler as exc:
        result = dict(angenommen=False, code=exc.code, text=exc.text, art=None, regel=None)
    if key is not None:
        files.append(ein.ergebnis_datei(work / ein.ORDNER_ERGEBNIS, kennung, key, **result))
    if args.kanal == "git":
        repository, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
        if not repository or not token:
            print("::error::Ablage auf dem Branch braucht GITHUB_REPOSITORY und GITHUB_TOKEN")
            return EXIT_FAILED
        channel = ka.GitLieferkanal(repository, token, server=os.environ.get("GITHUB_SERVER_URL", "https://github.com"), branch=args.branch,
                                    prune=ein.prune_names, titel="Spielgeld-Eingang")
    else:
        channel = ka.OrdnerLieferkanal(Path(args.ordner), prune=ein.prune_names)
    try:
        channel.deliver(files, base=work)  # eingang/<kennung>.bin (nur angenommen) und ergebnis/<kennung>.bin
    finally:
        if hasattr(channel, "close"):
            channel.close()
    line = f"Spielgeld-Eingang {kennung}: {'angenommen' if result['angenommen'] else 'abgelehnt'} ({result['code']}), Art {result['art'] or '–'}"
    print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")
    return EXIT_OK


def cmd_spielgeld_simulation(args) -> int:
    """Historische Simulation aller Spielgelddepots auf dem gespeicherten Zustand (Gesamtauftrag, Abschnitte 14, 29.8, 31.6).
    Ausgabe nur mit Zahlen (Tage, Depots, Buchungen, Laufzeiten) – keine Aktien, Kurse oder Depotinhalte."""
    from .aktienpilot import simulation
    from .aktienpilot.config import load_aktienpilot_config

    state_dir = Path(args.state_dir)
    mode = "demo" if args.demo else "produktiv"
    if args.demo:
        key, descriptor = (load_or_create_key(state_dir, args.passphrase, allow_new=False) if args.passphrase else (None, crypto.crypto_descriptor(None)))
        if (state_dir / "crypto.json").exists() and not args.passphrase:
            descriptor = read_json(state_dir / "crypto.json")
    else:
        passphrase = os.environ.get("DATA_PASSPHRASE")
        if not passphrase:
            print("::error::DATA_PASSPHRASE fehlt – der Spielgeld-Stand wird nur verschlüsselt abgelegt")
            return 2
        key, descriptor = load_or_create_key(state_dir, passphrase, allow_new=False)
    pipeline = load_pipeline_config()
    sources, _ = _sources_for(mode, pipeline)
    if args.demo:
        from .providers.demo import DEMO_NOW

        now = DEMO_NOW
    else:
        now = dt.datetime.now(dt.timezone.utc)
    conn = connect(state_dir / "state.sqlite")
    try:
        summary = simulation.historisch(conn, cfg=load_aktienpilot_config(), method=load_method_config(), mode=mode, tage=int(args.tage), now=now,
                                        calendars=sources.calendars, provider=sources.marktreihen or sources.prices, key=key, log=lambda text: LOG.info("%s", text))
        if args.site:
            last = conn.execute("SELECT id FROM run WHERE data_mode = ? ORDER BY rowid DESC LIMIT 1", (mode,)).fetchone()
            build_status_file(conn, state_dir, mode, pipeline, last_run_id=last[0] if last else None, now=now, keep_next=True)
    finally:
        conn.close()
    if args.site:
        keep = int(pipeline.get("aufbewahrung.site_snapshots", SITE_SNAPSHOTS_DEFAULT))
        assemble_site(app_dist=Path(args.app_dist), state_dir=state_dir, out_dir=Path(args.site), crypto_descriptor=descriptor, keep=keep)
    public = {k: summary[k] for k in ("tage", "depots", "archiviert", "aktien", "ausgelassen", "lineal_fenster", "ereignisse", "orders", "journal",
                                      "schritte", "rechnungen", "sekunden", "stand_bytes")}
    print(json.dumps(public, ensure_ascii=False))
    if args.bericht:
        Path(args.bericht).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


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
        "--stufe",
        type=int,
        choices=(1, 2),
        default=None,
        help="gestaffelte Aktualisierung (ab 1.11): 1 = zuerst die wichtigsten Aktien, nur lesen und bereitstellen; ohne Angabe alle Aktien",
    )
    p.add_argument(
        "--gestaffelt",
        action="store_true",
        help="dieser volle Zwischenstand ist Stufe 2 einer gestaffelten Aktualisierung (Stufe 1 läuft parallel)",
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

    p = sub.add_parser("sichern", help="(intern) Zustand und Archive sichern – eigener Prozess des Zwischenstands")
    p.add_argument("--state-dir", default="state")
    p.add_argument("--behalten", type=int, default=60)
    p.add_argument("--archive", nargs="*", default=[])
    p.set_defaults(func=cmd_save)

    p = sub.add_parser("sichern-warten", help="Auf das Sichern im Hintergrund warten (Ende des Jobs)")
    p.add_argument("--state-dir", default="state")
    p.add_argument("--timeout", type=float, default=900.0)
    p.set_defaults(func=cmd_save_wait)

    p = sub.add_parser("kurse-aktualisieren", help="Kurse einzelner Aktien auf Wunsch der App abrufen und liefern (ab 1.21)")
    p.add_argument("--kennung", required=True, help="Kennung der Anfrage (Zufallswert aus der App)")
    p.add_argument("--anfrage-env", default="ANFRAGE", help="Name der Umgebungsvariable mit der verschlüsselten Anfrage")
    p.add_argument("--schluessel", default="crypto.json", help="Schlüsselparameter (crypto.json aus dem Release „datenstand“)")
    p.add_argument("--kanal", choices=("git", "ordner"), default="git")
    p.add_argument("--ordner", default="build/kurse-aktuell", help="Zielordner für --kanal ordner")
    p.add_argument("--arbeit", default="_aktuell", help="Arbeitsordner für die Lieferdateien")
    p.add_argument("--demo", action="store_true", help="synthetische DEMO-Kurse statt Yahoo")
    p.add_argument("--probe", type=int, default=0, help="Messung ohne App: eigene Anfrage mit so vielen öffentlich bekannten Werten")
    p.add_argument("--branch", default="kurse-aktuell", help="Branch des Lieferkanals (Messung: eigener Branch)")
    p.set_defaults(func=cmd_kurse_aktualisieren)

    p = sub.add_parser("spielgeld-eingang", help="Spielgeld-Robo: Eingang aus der App prüfen und für den täglichen Lauf ablegen")
    p.add_argument("--kennung", required=True, help="Kennung des Eingangs (Zufallswert aus der App)")
    p.add_argument("--nutzlast-env", default="NUTZLAST", help="Name der Umgebungsvariable mit dem verschlüsselten Eingang")
    p.add_argument("--schluessel", default="crypto.json", help="Schlüsselparameter (crypto.json aus dem Release „datenstand“)")
    p.add_argument("--kanal", choices=("git", "ordner"), default="git")
    p.add_argument("--ordner", default="build/spielgeld-eingang", help="Zielordner für --kanal ordner (DEMO: <state>/spielgeld-eingang)")
    p.add_argument("--arbeit", default="_eingang", help="Arbeitsordner")
    p.add_argument("--branch", default="spielgeld-eingang")
    p.set_defaults(func=cmd_spielgeld_eingang)

    p = sub.add_parser("spielgeld-simulation", help="Spielgeld-Robo: historische Simulation aller Depots auf dem gespeicherten Zustand")
    p.add_argument("--state-dir", default="state")
    p.add_argument("--demo", action="store_true", help="DEMO-Zustand (synthetische Kurse)")
    p.add_argument("--passphrase", default=None, help="nur DEMO: verschlüsselt ablegen wie die DEMO-Website")
    p.add_argument("--tage", type=int, default=60, help="Handelstage bis zum neuesten Stand (2 bis 250)")
    p.add_argument("--site", default=None, help="danach die Website in diesen Ordner bauen")
    p.add_argument("--app-dist", default=str(DEFAULT_APP_DIST))
    p.add_argument("--bericht", default=None, help="vollständige Zusammenfassung als JSON (privat, nicht in öffentliche Protokolle)")
    p.set_defaults(func=cmd_spielgeld_simulation)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except StateError as exc:
        print(f"::error::{exc}")
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
