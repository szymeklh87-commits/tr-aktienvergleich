"""Dauerhafte Ablage des Zustands zwischen Läufen.

Lokal: ein Verzeichnis (``state/``). Auf GitHub: Release-Assets eines festen Tags
(Standard ``datenstand``). Release-Assets sind dauerhaft, liegen nicht in der Git-
Historie und sind über die GitHub-API mit dem Workflow-Token schreibbar.

Assets:
* ``crypto.json``            öffentliche Schlüsselparameter (Salt, Iterationen, Prüfwert)
* ``state.sqlite.tra``       Datenbank (gzip + AES-GCM)
* ``site-<id>.tar``          veröffentlichte Snapshot-Dateien (bereits verschlüsselt)
* ``evidence-<id>.tra``      Prüfnachweis (verschlüsselt)

Alle Inhalte mit Kursbezug sind verschlüsselt; im öffentlichen Repository ist ohne
Passphrase nichts davon lesbar.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from ..providers.http import HttpClient
from ..store.db import backup_to, integrity_ok
from ..util import crypto
from ..util.jsonio import atomic_write_bytes, atomic_write_json, read_json
from ..util.log import get_logger

LOG = get_logger(__name__)
API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"


class StateError(RuntimeError):
    pass


def load_or_create_key(state_dir: Path, passphrase: str | None, *, allow_new: bool) -> tuple[crypto.KeyMaterial | None, dict]:
    """Leitet den Schlüssel aus Passphrase + gespeichertem Salt ab; prüft den Prüfwert."""
    path = Path(state_dir) / "crypto.json"
    if not passphrase:
        descriptor = crypto.crypto_descriptor(None)
        return None, descriptor
    if path.exists():
        descriptor = read_json(path)
        if descriptor.get("enabled"):
            try:
                key = crypto.verify_descriptor(descriptor, passphrase)
            except crypto.ContainerError as exc:
                raise StateError(
                    "Die Passphrase passt nicht zum gespeicherten Datenstand. Alte Passphrase wiederherstellen "
                    "oder den Zustand bewusst neu aufbauen (Workflow-Eingabe 'zustand_neu_aufbauen')."
                ) from exc
            descriptor = crypto.crypto_descriptor(key)  # neuer Prüfwert mit frischem IV
            atomic_write_json(path, descriptor)
            return key, descriptor
    if not allow_new and path.exists():
        raise StateError("Unverschlüsselter Zustand vorhanden, aber Passphrase gesetzt – bitte Zustand neu aufbauen")
    key = crypto.derive_key(passphrase, crypto.new_salt())
    descriptor = crypto.crypto_descriptor(key)
    atomic_write_json(path, descriptor)
    return key, descriptor


def pack_database(conn: sqlite3.Connection, state_dir: Path, key: crypto.KeyMaterial | None) -> Path:
    """Konsistente Sicherung der Datenbank als TRA1-Container."""
    tmp = Path(state_dir) / "backup" / "state.sqlite"
    backup_to(conn, tmp)
    if not integrity_ok(tmp):
        raise StateError("Integritätsprüfung der Sicherung fehlgeschlagen")
    blob = crypto.pack(tmp.read_bytes(), key, "state/state.sqlite")
    target = Path(state_dir) / "backup" / "state.sqlite.tra"
    atomic_write_bytes(target, blob)
    tmp.unlink()
    return target


def unpack_database(blob: bytes, key: crypto.KeyMaterial | None, target: Path) -> None:
    data = crypto.unpack(blob, key, "state/state.sqlite")
    atomic_write_bytes(target, data)
    if not integrity_ok(target):
        raise StateError("Wiederhergestellte Datenbank ist beschädigt")


@dataclass
class GitHubReleaseStore:
    repo: str
    token: str
    tag: str = "datenstand"
    http: HttpClient | None = None

    @classmethod
    def from_env(cls, tag: str = "datenstand") -> "GitHubReleaseStore":
        repo = os.environ.get("GITHUB_REPOSITORY")
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not repo or not token:
            raise StateError("GITHUB_REPOSITORY oder GITHUB_TOKEN fehlt")
        return cls(repo=repo, token=token, tag=tag)

    def _client(self) -> HttpClient:
        if self.http is None:
            self.http = HttpClient(timeout=300, max_retries=4)
        return self.http

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        headers.update(extra or {})
        return headers

    def release(self) -> dict:
        client = self._client()
        response = client.get(f"{API}/repos/{self.repo}/releases/tags/{quote(self.tag)}", headers=self._headers())
        if response.status_code == 200:
            return response.json()
        if response.status_code != 404:
            raise StateError(f"Release abfragen: HTTP {response.status_code}")
        body = {
            "tag_name": self.tag,
            "name": "Datenstand (automatisch, verschlüsselt)",
            "body": "Automatisch verwalteter, verschlüsselter Datenstand des täglichen Laufs. Nicht manuell bearbeiten.",
            "prerelease": True,
            "make_latest": "false",
        }
        response = client.post(f"{API}/repos/{self.repo}/releases", json_body=body, headers=self._headers())
        if response.status_code not in (200, 201):
            raise StateError(f"Release anlegen: HTTP {response.status_code}")
        return response.json()

    def assets(self) -> dict[str, dict]:
        release = self.release()
        client = self._client()
        out: dict[str, dict] = {}
        page = 1
        while True:
            response = client.get(
                f"{API}/repos/{self.repo}/releases/{release['id']}/assets", params={"per_page": "100", "page": str(page)}, headers=self._headers()
            )
            if response.status_code != 200:
                raise StateError(f"Assets abfragen: HTTP {response.status_code}")
            items = response.json()
            for item in items:
                out[item["name"]] = item
            if len(items) < 100:
                return out
            page += 1

    def download(self, asset: dict) -> bytes:
        response = self._client().get(
            f"{API}/repos/{self.repo}/releases/assets/{asset['id']}", headers=self._headers({"Accept": "application/octet-stream"})
        )
        if response.status_code != 200:
            raise StateError(f"Download {asset['name']}: HTTP {response.status_code}")
        return response.content

    def upload(self, name: str, data: bytes, existing: dict[str, dict] | None = None) -> None:
        existing = existing if existing is not None else self.assets()
        if name in existing:
            self.delete(existing[name])
        release = self.release()
        client = self._client()
        session = client._session  # roher Upload mit Bytes-Inhalt
        response = session.request(
            "POST",
            f"{UPLOADS}/repos/{self.repo}/releases/{release['id']}/assets",
            params={"name": name},
            data=data,
            headers=self._headers({"Content-Type": "application/octet-stream"}),
            timeout=600,
        )
        if int(response.status_code) not in (200, 201):
            raise StateError(f"Upload {name}: HTTP {response.status_code}")

    def delete(self, asset: dict) -> None:
        response = self._client().request("DELETE", f"{API}/repos/{self.repo}/releases/assets/{asset['id']}", headers=self._headers())
        if response.status_code not in (204, 404):
            raise StateError(f"Löschen {asset['name']}: HTTP {response.status_code}")

    def rename(self, asset: dict, name: str) -> None:
        response = self._client().request(
            "PATCH", f"{API}/repos/{self.repo}/releases/assets/{asset['id']}", json_body={"name": name}, headers=self._headers()
        )
        if response.status_code != 200:
            raise StateError(f"Umbenennen {asset['name']} → {name}: HTTP {response.status_code}")

    def replace(self, name: str, data: bytes) -> None:
        """Ersetzt ein Asset ohne Lücke: neue Fassung unter Zwischennamen hochladen, dann die alte
        löschen und die neue umbenennen. Bricht der Vorgang an irgendeiner Stelle ab, liegt immer
        mindestens eine vollständige Fassung im Release (siehe :func:`sync_down`)."""
        temp = f"{name}{PENDING_SUFFIX}"
        assets = complete_assets(self.assets())
        if temp in assets:
            if name in assets:
                self.delete(assets[temp])  # Rest eines abgebrochenen Austauschs; die Hauptfassung gilt
            else:
                self.rename(assets[temp], name)  # Austausch brach nach dem Löschen ab: Zwischenstand ist die neueste Fassung
            assets = complete_assets(self.assets())
        self.upload(temp, data, self.assets())
        assets = self.assets()
        if name in assets:
            self.delete(assets[name])
        self.rename(assets[temp], name)


PENDING_SUFFIX = ".neu"


def complete_assets(assets: dict[str, dict]) -> dict[str, dict]:
    """Nur vollständig hochgeladene Assets (GitHub kennzeichnet abgebrochene Uploads mit einem anderen ``state``)."""
    return {name: asset for name, asset in assets.items() if asset.get("state", "uploaded") == "uploaded"}


def sync_down(
    store: GitHubReleaseStore, state_dir: Path, passphrase: str | None, *, wanted_snapshots: list[str] | None = None, wanted_archives: list[str] | None = None
) -> dict:
    """Lädt Schlüsselparameter, Datenbank und gewünschte Snapshot-Archive herunter (``wanted_archives``:
    weitere Archive nach Dateiname, z. B. der aktuelle Signal-Stand)."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    assets = complete_assets(store.assets())
    info = {"database": False, "snapshots": []}
    if "crypto.json" in assets:
        atomic_write_bytes(state_dir / "crypto.json", store.download(assets["crypto.json"]))
    key, _ = load_or_create_key(state_dir, passphrase, allow_new=True)
    # Hauptfassung bevorzugen; fehlt sie (Austausch nach dem Löschen abgebrochen), gilt der Zwischenstand.
    database = assets.get("state.sqlite.tra") or assets.get(f"state.sqlite.tra{PENDING_SUFFIX}")
    if database is not None:
        unpack_database(store.download(database), key, state_dir / "state.sqlite")
        info["database"] = True
    for snapshot_id in wanted_snapshots or []:
        name = f"site-{snapshot_id}.tar"
        target = state_dir / "archives" / name
        if name in assets and not target.exists():
            atomic_write_bytes(target, store.download(assets[name]))
            info["snapshots"].append(snapshot_id)
    for name in wanted_archives or []:
        target = state_dir / "archives" / name
        if name in assets and not target.exists():
            atomic_write_bytes(target, store.download(assets[name]))
    return info


def sync_up(store: GitHubReleaseStore, state_dir: Path, conn: sqlite3.Connection, key: crypto.KeyMaterial | None, *, keep_archives: int = 60) -> dict:
    """Lädt Datenbank, Schlüsselparameter und neue Archive hoch; ältere Archive werden ausgedünnt."""
    state_dir = Path(state_dir)
    uploaded = []
    db_blob = pack_database(conn, state_dir, key).read_bytes()
    store.replace("state.sqlite.tra", db_blob)
    uploaded.append("state.sqlite.tra")
    # Die Schlüsselparameter (Salt, Prüfwert) ändern sich nach dem Anlegen nie; ein erneutes
    # Hochladen hätte nur das Risiko, sie zwischen Löschen und Upload zu verlieren.
    crypto_path = state_dir / "crypto.json"
    if crypto_path.exists() and "crypto.json" not in complete_assets(store.assets()):
        store.upload("crypto.json", crypto_path.read_bytes(), store.assets())
        uploaded.append("crypto.json")
    assets = store.assets()
    complete = complete_assets(assets)
    for path in sorted((state_dir / "archives").glob("*")):
        if path.name not in complete:  # fehlt oder Upload wurde abgebrochen → (neu) hochladen
            store.upload(path.name, path.read_bytes(), assets)
            uploaded.append(path.name)
    # Aufbewahrung: nur die neuesten Archive behalten (append-only bis zur Grenze).
    assets = store.assets()
    site_assets = sorted((n for n in assets if n.startswith("site-")), reverse=True)
    removed = []
    for name in site_assets[keep_archives:]:
        store.delete(assets[name])
        evidence = name.replace("site-", "evidence-").replace(".tar", ".tra")
        if evidence in assets:
            store.delete(assets[evidence])
        removed.append(name)
    # Signal-Stände: nur die drei neuesten (jeder Stand ist vollständig, ältere werden nicht gebraucht)
    for name in sorted((n for n in assets if n.startswith("signale-")), reverse=True)[3:]:
        store.delete(assets[name])
        removed.append(name)
    return {"uploaded": uploaded, "removed": removed}


def write_local_marker(state_dir: Path, info: dict) -> None:
    atomic_write_json(Path(state_dir) / "last_sync.json", info)


def read_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def as_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
