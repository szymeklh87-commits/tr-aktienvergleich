"""Kompletter GitHub-Ablauf (`python -m traktien ci`) gegen eine nachgebildete GitHub-REST-API.

Prüft ohne Netz: Release anlegen, verschlüsselten Zustand und Archive hochladen, auf einem
frischen Runner wiederherstellen, Website zusammenbauen, Ausgaben für die Workflow-Schritte,
Freigabe verwaister Sperren aus einer Sicherung (T41–T46, T52, T55). Kursquelle: DEMO
(synthetische Testaktien) statt Yahoo.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from traktien import cli
from traktien.jobs.sources import demo_sources
from traktien.jobs.state import (
    GitHubReleaseStore,
    StateError,
    berlin_day,
    generation_day,
    generation_name,
    generations_to_keep,
    load_or_create_key,
    pack_database,
    sync_down,
    sync_up,
)
from traktien.providers.http import HttpClient
from traktien.store import repo
from traktien.store.db import connect
from traktien.util import crypto

PASSPHRASE = "CI-Ablauf-Test-Passphrase!"
TOKEN = "testtoken-nicht-echt-123456"


class _Response:
    def __init__(self, status: int, body: bytes | dict | list | None = None, headers: dict | None = None) -> None:
        self.status_code = status
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        self.content = body or b""
        self.headers = headers or {}
        self.url = ""


class FakeGitHub:
    """Minimaler Nachbau der benötigten GitHub-REST-Endpunkte für Releases und Assets."""

    def __init__(self, repo_name: str) -> None:
        self.repo = repo_name
        self.release: dict | None = None
        self.assets: dict[int, dict] = {}
        self.next_id = 100
        self.calls: list[tuple[str, str]] = []
        self.fail_upload: str | None = None  # Name, dessen Upload mit Verbindungsabbruch scheitert
        self.upload_502: int = 0  # so viele Uploads antworten mit „502 Bad Gateway“ (vorübergehender Fehler, ab 1.15)
        self.fail_rename = False
        # ab 1.22: Zeitpunkt des Uploads („created_at“), aus dem die Sicherung den Tag einer älteren Fassung liest
        self.now_iso = "2026-11-01T10:00:00Z"
        # Ab 1.10 sichert ein zweiter Thread parallel zum Zusammenstellen der Website. Wie beim echten Server ist
        # jede Anfrage für sich atomar.
        self._lock = threading.Lock()

    def data(self, name: str) -> bytes | None:
        with self._lock:
            return next((a["data"] for a in self.assets.values() if a["name"] == name), None)

    def request(self, method, url, params=None, json=None, data=None, headers=None, timeout=None):  # noqa: A002 - Signatur wie requests
        with self._lock:
            return self._request(method, url, params=params, json=json, data=data, headers=headers, timeout=timeout)

    def _request(self, method, url, params=None, json=None, data=None, headers=None, timeout=None):  # noqa: A002
        self.calls.append((method, url))
        if (headers or {}).get("Authorization") != f"Bearer {TOKEN}":
            return _Response(401, {"message": "Bad credentials"})
        base = f"https://api.github.com/repos/{self.repo}"
        uploads = f"https://uploads.github.com/repos/{self.repo}"
        if method == "POST" and url.startswith(uploads) and params and params.get("name") == self.fail_upload:
            raise ConnectionError("Verbindung während des Uploads abgebrochen (Test)")
        if method == "PATCH" and url.startswith(f"{base}/releases/assets/"):
            if self.fail_rename:
                return _Response(502, {"message": "Bad Gateway"})
            asset = self.assets.get(int(url.rsplit("/", 1)[1]))
            if asset is None:
                return _Response(404, {"message": "Not Found"})
            if any(a["name"] == json["name"] and a is not asset for a in self.assets.values()):
                return _Response(422, {"message": "already_exists"})
            asset["name"] = json["name"]
            return _Response(200, {"id": asset["id"], "name": asset["name"]})
        if method == "GET" and url == f"{base}/releases/tags/datenstand":
            return _Response(200, self.release) if self.release else _Response(404, {"message": "Not Found"})
        if method == "POST" and url == f"{base}/releases":
            self.release = {"id": 1, "tag_name": json["tag_name"], "prerelease": json.get("prerelease")}
            return _Response(201, self.release)
        if method == "GET" and url == f"{base}/releases/1/assets":
            items = [{"id": a["id"], "name": a["name"], "size": len(a["data"]), "created_at": a.get("created_at")} for a in self.assets.values()]
            page, per_page = int(params["page"]), int(params["per_page"])
            return _Response(200, items[(page - 1) * per_page : page * per_page])
        if method == "GET" and url.startswith(f"{base}/releases/assets/"):
            asset = self.assets.get(int(url.rsplit("/", 1)[1]))
            if asset is None or headers.get("Accept") != "application/octet-stream":
                return _Response(404, {"message": "Not Found"})
            return _Response(200, asset["data"])
        if method == "POST" and url == f"{uploads}/releases/1/assets":
            name = params["name"]
            if self.upload_502:
                self.upload_502 -= 1
                return _Response(502, {"message": "Bad Gateway"})
            if any(a["name"] == name for a in self.assets.values()):
                return _Response(422, {"message": "already_exists"})
            self.next_id += 1
            self.assets[self.next_id] = {"id": self.next_id, "name": name, "data": bytes(data), "created_at": self.now_iso}
            return _Response(201, {"id": self.next_id, "name": name})
        if method == "DELETE" and url.startswith(f"{base}/releases/assets/"):
            self.assets.pop(int(url.rsplit("/", 1)[1]), None)
            return _Response(204)
        return _Response(404, {"message": f"unbekannter Endpunkt {method} {url}"})

    def names(self) -> set[str]:
        with self._lock:
            return {a["name"] for a in self.assets.values()}


class CiFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ci-ablauf-"))
        self.stub = self.tmp / "app"
        self.stub.mkdir()
        (self.stub / "index.html").write_text("<!doctype html><title>Stub</title>", encoding="utf-8")
        self.github = FakeGitHub("simon/tr-aktienvergleich")
        self.store = GitHubReleaseStore(repo="simon/tr-aktienvergleich", token=TOKEN, http=HttpClient(session=self.github, sleep=lambda _s: None))
        self.env = mock.patch.dict(
            os.environ,
            {
                "DATA_PASSPHRASE": PASSPHRASE,
                "GITHUB_TOKEN": TOKEN,
                "GITHUB_REPOSITORY": "simon/tr-aktienvergleich",
                "GITHUB_EVENT_NAME": "schedule",
                "AUSLOESENDER_ZEITPLAN": "0 7 * * *",
            },
        )
        self.env.start()
        self.patches = [
            mock.patch.object(GitHubReleaseStore, "from_env", classmethod(lambda cls, tag="datenstand": self.store)),
            mock.patch.object(cli, "production_sources", lambda *args, **kwargs: demo_sources()),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self) -> None:
        for patch in self.patches:
            patch.stop()
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_ci(self, name: str, *extra: str) -> tuple[int, dict, Path]:
        output = self.tmp / f"{name}.out"
        # Ausgabe abfangen: Zeilen wie „::error::…“ würde GitHub sonst als echte Hinweise des
        # Prüflaufs anzeigen. Die Tests prüfen den Text stattdessen über self.stdout.
        self.stdout = io.StringIO()
        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}), contextlib.redirect_stdout(self.stdout):
            code = cli.main(["ci", "--state-dir", str(self.tmp / name / "state"), "--site", str(self.tmp / name / "site"), "--app-dist", str(self.stub), *extra])
        values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines()) if output.exists() else {}
        return code, values, self.tmp / name / "site"

    def test_full_github_cycle_on_fresh_runners(self) -> None:
        code, out, site = self.run_ci("lauf1")
        self.assertEqual(code, 0)
        self.assertEqual(out.get("deploy"), "true")
        self.assertEqual(out.get("status"), "veroeffentlicht")
        # Kurzbericht als Hinweis in der Laufübersicht – ohne Passphrase und Token
        printed = self.stdout.getvalue()
        self.assertIn("::notice title=Lauf%3A veroeffentlicht::", printed)
        self.assertIn("Kursstichtag", printed)
        self.assertIn("Stichtagskurse je Markt", printed)
        self.assertNotIn(PASSPHRASE, printed)
        self.assertNotIn(TOKEN, printed)
        names = self.github.names()
        self.assertTrue({"crypto.json", "state.sqlite.tra"} <= names, names)
        self.assertTrue(any(n.startswith("site-") and n.endswith(".tar") for n in names))
        self.assertTrue(any(n.startswith("evidence-") and n.endswith(".tra") for n in names))
        status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
        first_id = status["latest_snapshot_id"]
        self.assertTrue(first_id)
        self.assertTrue(json.loads((site / "data" / "crypto.json").read_text(encoding="utf-8"))["enabled"])
        self.assertTrue(self.github.release["prerelease"], "Datenstand-Release ist als Vorabversion markiert")

        # Nichts Geheimes in Assets oder Website
        for asset in self.github.assets.values():
            self.assertNotIn(PASSPHRASE.encode(), asset["data"])
            self.assertNotIn(TOKEN.encode(), asset["data"])
        with contextlib.redirect_stdout(io.StringIO()) as report:
            self.assertEqual(cli.main(["verify-site", "--site", str(site)]), 0)
        self.assertTrue(json.loads(report.getvalue())["ok"])

        # Zweiter Lauf auf frischem Runner: Zustand kommt aus der Sicherung, kein neuer Börsenschluss
        code, out, site2 = self.run_ci("lauf2")
        self.assertEqual(code, 0)
        self.assertEqual(out.get("status"), "keine_neuen_daten")
        index = json.loads((site2 / "data" / "snapshots" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual([s["snapshot_id"] for s in index["snapshots"]], [first_id], "letzter Stand bleibt veröffentlicht")
        self.assertTrue((site2 / "data" / "snapshots" / first_id / "manifest.bin").exists())

        # Verwaiste Sperre in der Sicherung (abgebrochener Runner) blockiert den nächsten Lauf nicht
        state2 = self.tmp / "lauf2" / "state"
        conn = connect(state2 / "state.sqlite")
        try:
            repo.create_run(conn, "haengender-lauf", trigger="zeitplan", planned_start=None, attempt=1, versions={"method": "m", "metrics": "k", "ranking": "r", "frequency": "f", "software": "s"}, data_mode="demo")
            repo.acquire_lock(conn, "taeglicher-lauf", "haengender-lauf")
            key, _ = load_or_create_key(state2, PASSPHRASE, allow_new=False)
            sync_up(self.store, state2, conn, key)
        finally:
            conn.close()
        code, out, _ = self.run_ci("lauf3")
        self.assertEqual(code, 0)
        self.assertEqual(out.get("deploy"), "true")
        conn = connect(self.tmp / "lauf3" / "state" / "state.sqlite")
        try:
            row = conn.execute("SELECT status FROM run WHERE id = 'haengender-lauf'").fetchone()
            self.assertEqual(row["status"], "abgebrochen")
        finally:
            conn.close()

    def test_website_only_redeploys_without_touching_the_backup(self) -> None:
        # Ohne gespeicherten Zustand gibt es nichts neu zu veröffentlichen
        code, out, site = self.run_ci("leer", "--nur-website")
        self.assertNotEqual(code, 0)
        self.assertIn("zuerst einen normalen Lauf starten", self.stdout.getvalue())
        self.assertEqual(out, {})
        self.assertEqual(self.github.names(), set(), "nichts hochgeladen")

        code, out, _ = self.run_ci("lauf1")
        self.assertEqual(out.get("status"), "veroeffentlicht")
        first = json.loads((self.tmp / "lauf1" / "site" / "data" / "status.json").read_text(encoding="utf-8"))["latest_snapshot_id"]
        before = {name: bytes(asset["data"]) for name, asset in self.github.assets.items()}

        # Neue App-Hülle auf einem frischen Runner bereitstellen: kein Abruf, Sicherung unverändert
        (self.stub / "neu.txt").write_text("neue App-Version", encoding="utf-8")
        code, out, site = self.run_ci("web", "--nur-website")
        self.assertEqual(code, 0, self.stdout.getvalue())
        self.assertEqual(out.get("deploy"), "true")
        self.assertEqual(out.get("status"), "veroeffentlicht")
        self.assertIn("::notice title=Nur Website::", self.stdout.getvalue())
        self.assertEqual({name: bytes(asset["data"]) for name, asset in self.github.assets.items()}, before)
        self.assertEqual((site / "neu.txt").read_text(encoding="utf-8"), "neue App-Version")
        status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["latest_snapshot_id"], first)
        self.assertTrue((site / "data" / "snapshots" / first / "manifest.bin").exists())
        with contextlib.redirect_stdout(io.StringIO()) as report:
            self.assertEqual(cli.main(["verify-site", "--site", str(site)]), 0)
        self.assertTrue(json.loads(report.getvalue())["ok"])

    def test_new_passphrase_with_website_only_resets_key_in_minutes(self) -> None:
        code, out, _ = self.run_ci("lauf1")
        self.assertEqual(out.get("status"), "veroeffentlicht")
        old_descriptor = json.loads(self.github.data("crypto.json"))
        neu = "Neue-Passphrase-fuer-Test-2026"
        with mock.patch.dict(os.environ, {"DATA_PASSPHRASE": neu}):
            # Ohne Neuaufbau passt die neue Passphrase nicht zur Sicherung
            code, out, _ = self.run_ci("ohne_neuaufbau")
            self.assertNotEqual(code, 0)
            self.assertIn("Passphrase passt nicht", self.stdout.getvalue())
            self.assertEqual(out, {})
            code, out, site = self.run_ci("schluessel", "--reset-state", "--nur-website")
            self.assertEqual(code, 0, self.stdout.getvalue())
            self.assertEqual(out.get("deploy"), "true")
            self.assertEqual(out.get("status"), "kein_lauf")
            self.assertIn("::notice title=Neuer Schlüssel::", self.stdout.getvalue())
            new_descriptor = json.loads(self.github.data("crypto.json"))
            self.assertNotEqual(new_descriptor["salt_b64"], old_descriptor["salt_b64"])
            site_descriptor = json.loads((site / "data" / "crypto.json").read_text(encoding="utf-8"))
            crypto.verify_descriptor(site_descriptor, neu)  # die App prüft die neue Passphrase
            with self.assertRaises(crypto.ContainerError):
                crypto.verify_descriptor(site_descriptor, PASSPHRASE)
            status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
            self.assertIsNone(status["latest_snapshot_id"])
            self.assertIsNone(status["last_run"])
            # Der nächste normale Lauf arbeitet mit dem neuen Schlüssel weiter
            code, out, _ = self.run_ci("lauf2")
            self.assertEqual(code, 0, self.stdout.getvalue())
            self.assertEqual(out.get("status"), "veroeffentlicht")
        for asset in self.github.assets.values():
            self.assertNotIn(neu.encode(), bytes(asset["data"]))

    def test_missing_passphrase_stops_before_anything_is_published(self) -> None:
        with mock.patch.dict(os.environ, {"DATA_PASSPHRASE": ""}):
            code, out, site = self.run_ci("ohne")
        self.assertNotEqual(code, 0)
        self.assertIn("::error::Secret DATA_PASSPHRASE fehlt", self.stdout.getvalue())
        self.assertEqual(out, {})
        self.assertFalse(site.exists())
        self.assertEqual(self.github.names(), set())


class ReleaseReplaceTests(unittest.TestCase):
    """T55/T44: Die Sicherung im Release ist nie für einen Moment weg – auch nicht bei Abbrüchen."""

    def setUp(self) -> None:
        self.github = FakeGitHub("simon/tr-aktienvergleich")
        self.store = GitHubReleaseStore(repo="simon/tr-aktienvergleich", token=TOKEN, http=HttpClient(session=self.github, sleep=lambda _s: None))

    def test_failed_upload_keeps_previous_backup(self) -> None:
        self.store.replace("state.sqlite.tra", b"alt")
        self.github.fail_upload = "state.sqlite.tra.neu"
        with self.assertRaises(StateError):
            self.store.replace("state.sqlite.tra", b"neu")
        self.assertEqual(self.github.data("state.sqlite.tra"), b"alt")
        uploads = [c for c in self.github.calls if c[0] == "POST" and c[1].startswith("https://uploads.github.com")]
        self.assertEqual(len(uploads), 1 + GitHubReleaseStore.UPLOAD_ATTEMPTS, "erste Sicherung und vier Versuche für die neue")

    def test_transient_upload_error_is_retried(self) -> None:
        """Ab 1.15 (Lauf vom 14.10.2026, 17:18 Uhr: „Upload state.sqlite.tra.neu: HTTP 502“): vorübergehende Fehler des
        Upload-Servers werden wiederholt; die Sicherung gelingt, ohne Lücke."""
        self.store.replace("state.sqlite.tra", b"alt")
        self.github.upload_502 = 2
        self.store.replace("state.sqlite.tra", b"neu")
        self.assertEqual(self.github.data("state.sqlite.tra"), b"neu")
        self.assertEqual(self.github.names(), {"state.sqlite.tra"})

    def test_client_error_on_upload_is_not_retried(self) -> None:
        self.store.upload("a.bin", b"1")
        self.github.calls.clear()
        with self.assertRaises(StateError):
            self.store.upload("a.bin", b"2", existing={})  # 422 „already_exists“: Wiederholen hilft nicht
        uploads = [c for c in self.github.calls if c[0] == "POST" and c[1].startswith("https://uploads.github.com")]
        self.assertEqual(len(uploads), 1)
        self.assertEqual(self.github.data("a.bin"), b"1")

    def test_interrupted_rename_leaves_newest_copy_and_is_repaired(self) -> None:
        self.store.replace("state.sqlite.tra", b"alt")
        self.github.fail_rename = True
        with self.assertRaises(Exception):
            self.store.replace("state.sqlite.tra", b"neu")
        self.assertEqual(self.github.names(), {"state.sqlite.tra.neu"}, "nur noch der vollständige Zwischenstand")
        self.github.fail_rename = False
        self.store.replace("state.sqlite.tra", b"neuer")
        self.assertEqual(self.github.names(), {"state.sqlite.tra"})
        self.assertEqual(self.github.data("state.sqlite.tra"), b"neuer")

    def test_sync_down_uses_pending_copy_when_main_copy_is_missing(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="rueckfall-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        conn = connect(tmp / "quelle" / "state.sqlite")
        try:
            repo.create_run(conn, "lauf-a", trigger="manuell", planned_start=None, attempt=1, versions={"method": "m", "metrics": "k", "ranking": "r", "frequency": "f", "software": "s"}, data_mode="demo")
            key, _ = load_or_create_key(tmp / "quelle", PASSPHRASE, allow_new=True)
            sync_up(self.store, tmp / "quelle", conn, key)
        finally:
            conn.close()
        main = next(a for a in self.github.assets.values() if a["name"] == "state.sqlite.tra")
        main["name"] = "state.sqlite.tra.neu"  # Zustand nach Abbruch zwischen Löschen und Umbenennen
        info = sync_down(self.store, tmp / "ziel", PASSPHRASE)
        self.assertTrue(info["database"])
        restored = connect(tmp / "ziel" / "state.sqlite")
        try:
            self.assertEqual(restored.execute("SELECT id FROM run").fetchone()["id"], "lauf-a")
        finally:
            restored.close()



class ReleaseGenerationTests(unittest.TestCase):
    """Befund F20 (ab 1.22): ältere Fassungen der Datenbanksicherung – Vortag und je Woche eine, nur durch Umbenennen."""

    def setUp(self) -> None:
        self.github = FakeGitHub("simon/tr-aktienvergleich")
        self.store = GitHubReleaseStore(repo="simon/tr-aktienvergleich", token=TOKEN, http=HttpClient(session=self.github, sleep=lambda _s: None))

    def _save(self, day: dt.date, data: bytes, hour: int = 22) -> str | None:
        self.github.now_iso = f"{day.isoformat()}T{hour:02d}:00:00Z"
        return self.store.replace("state.sqlite.tra", data, today=day)

    def test_backup_of_a_previous_day_is_kept_by_renaming_not_uploading_twice(self) -> None:
        self._save(dt.date(2026, 11, 2), b"montag")
        self.github.calls.clear()
        kept = self._save(dt.date(2026, 11, 3), b"dienstag")
        self.assertEqual(kept, "state-2026-11-02.sqlite.tra")
        self.assertEqual(self.github.names(), {"state.sqlite.tra", "state-2026-11-02.sqlite.tra"})
        self.assertEqual(self.github.data("state-2026-11-02.sqlite.tra"), b"montag")
        self.assertEqual(self.github.data("state.sqlite.tra"), b"dienstag")
        uploads = [c for c in self.github.calls if c[0] == "POST" and c[1].startswith("https://uploads.github.com")]
        self.assertEqual(len(uploads), 1, "nur die neue Fassung wird hochgeladen")
        # derselbe Tag: die Fassung von vorhin wird ersetzt, keine weitere ältere Fassung
        self.assertIsNone(self._save(dt.date(2026, 11, 3), b"dienstag-spaet"))
        self.assertEqual(self.github.names(), {"state.sqlite.tra", "state-2026-11-02.sqlite.tra"})

    def test_late_evening_utc_counts_as_the_next_day_in_berlin(self) -> None:
        self._save(dt.date(2026, 11, 2), b"a", hour=23)  # 00:00 Uhr in Berlin am 03.11.
        self.assertIsNone(self._save(dt.date(2026, 11, 3), b"b"))
        self.assertEqual(self.github.names(), {"state.sqlite.tra"})

    def test_thirty_days_keep_at_most_four_older_copies_with_one_to_two_weeks_old(self) -> None:
        start = dt.date(2026, 11, 1)
        for i in range(31):
            self._save(start + dt.timedelta(days=i), f"tag-{i}".encode())
        older = sorted(n for n in self.github.names() if n.startswith("state-"))
        self.assertLessEqual(len(older), 4)
        days = [dt.date.fromisoformat(n[6:16]) for n in older]
        newest = dt.date(2026, 12, 1)
        self.assertIn(newest - dt.timedelta(days=1), days, "Fassung vom Vortag")
        self.assertTrue(any(7 <= (newest - d).days <= 15 for d in days), "eine Fassung ist eine bis zwei Wochen alt")
        self.assertEqual(self.github.data("state.sqlite.tra"), b"tag-30")

    def test_failed_upload_leaves_main_and_older_copies_untouched(self) -> None:
        self._save(dt.date(2026, 11, 2), b"montag")
        self._save(dt.date(2026, 11, 3), b"dienstag")
        self.github.fail_upload = "state.sqlite.tra.neu"
        with self.assertRaises(StateError):
            self._save(dt.date(2026, 11, 4), b"mittwoch")
        self.assertEqual(self.github.data("state.sqlite.tra"), b"dienstag")
        self.assertEqual(self.github.data("state-2026-11-02.sqlite.tra"), b"montag")

    def _database(self, tmp: Path, run_id: str) -> bytes:
        conn = connect(tmp / run_id / "state.sqlite")
        try:
            repo.create_run(conn, run_id, trigger="manuell", planned_start=None, attempt=1, versions={"method": "m", "metrics": "k", "ranking": "r", "frequency": "f", "software": "s"}, data_mode="demo")
            key, _ = load_or_create_key(tmp / "schluessel", PASSPHRASE, allow_new=True)
            return pack_database(conn, tmp / run_id, key).read_bytes()
        finally:
            conn.close()

    def test_restore_falls_back_to_the_newest_older_copy_when_the_main_copy_is_broken(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="generationen-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        older = self._database(tmp, "lauf-montag")
        self._save(dt.date(2026, 11, 2), older)
        self.store.upload("crypto.json", (tmp / "schluessel" / "crypto.json").read_bytes())
        self._save(dt.date(2026, 11, 3), b"TRA1-kaputt" + b"\x00" * 64)  # Hauptfassung unbrauchbar
        info = sync_down(self.store, tmp / "ziel", PASSPHRASE)
        self.assertEqual(info["database_source"], "state-2026-11-02.sqlite.tra")
        restored = connect(tmp / "ziel" / "state.sqlite")
        try:
            self.assertEqual(restored.execute("SELECT id FROM run").fetchone()["id"], "lauf-montag")
        finally:
            restored.close()
        # bewusster Neuaufbau: nie auf eine ältere Fassung ausweichen
        with self.assertRaises(Exception):
            sync_down(self.store, tmp / "ziel2", PASSPHRASE, use_generations=False)

    def test_generation_names_and_days(self) -> None:
        self.assertEqual(generation_name(dt.date(2026, 11, 7)), "state-2026-11-07.sqlite.tra")
        self.assertEqual(generation_day("state-2026-11-07.sqlite.tra"), dt.date(2026, 11, 7))
        for name in ("state.sqlite.tra", "state.sqlite.tra.neu", "state-2026-13-40.sqlite.tra", "site-2026-11-07_x.tar"):
            self.assertIsNone(generation_day(name))
        self.assertEqual(berlin_day("2026-11-07T23:30:00Z"), dt.date(2026, 11, 8))
        self.assertIsNone(berlin_day(None))
        self.assertEqual(generations_to_keep([]), set())

if __name__ == "__main__":
    unittest.main()
