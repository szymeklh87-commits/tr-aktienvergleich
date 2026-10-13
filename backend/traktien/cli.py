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
        sync_up(store, state_dir, conn, key, keep_archives=int(pipeline.get("aufbewahrung.archiv_snapshots", 60)))
        index_path = state_dir / "site_meta" / "index.json"
        if index_path.exists():
            wanted = [s["snapshot_id"] for s in retained_snapshots(read_json(index_path), keep)]
            sync_down(store, state_dir, passphrase, wanted_snapshots=wanted)
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
    aufbewahrten Datenstände kommen unverändert aus dem Release „datenstand“."""
    if not (state_dir / "state.sqlite").exists() or not (state_dir / "crypto.json").exists():
        print("::error::Noch kein gespeicherter Zustand im Release – zuerst einen normalen Lauf starten")
        return EXIT_FAILED
    _, descriptor = load_or_create_key(state_dir, passphrase, allow_new=False)
    keep = int(pipeline.get("aufbewahrung.site_snapshots", 5))
    conn = connect(state_dir / "state.sqlite")
    try:
        last = conn.execute("SELECT id, status, data_mode FROM run ORDER BY started_at DESC, rowid DESC LIMIT 1").fetchone()
        mode = last["data_mode"] if last else "produktiv"
        build_status_file(conn, state_dir, mode, pipeline, last_run_id=last["id"] if last else None, now=dt.datetime.now(tz=dt.timezone.utc))
    finally:
        conn.close()
    wanted = [s["snapshot_id"] for s in retained_snapshots(read_json(state_dir / "site_meta" / "index.json"), keep)]
    if wanted:
        sync_down(store, state_dir, passphrase, wanted_snapshots=wanted)
    assemble_site(app_dist=Path(args.app_dist), state_dir=state_dir, out_dir=Path(args.site), crypto_descriptor=descriptor, keep=keep)
    _write_output("deploy", "true")
    _write_output("status", last["status"] if last else "kein_lauf")
    try:
        app_version = read_json(Path(args.app_dist) / "version.json").get("version", "?")
    except (OSError, ValueError):
        app_version = "?"
    print(f"::notice title=Nur Website::App {app_version} neu zusammengesetzt; Datenstand unverändert ({len(wanted)} veröffentlichte Stände)")
    return 0


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

    for path in sorted((site / "data" / "snapshots").rglob("*.bin")):
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
