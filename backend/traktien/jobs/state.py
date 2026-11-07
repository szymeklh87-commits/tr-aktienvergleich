"""Dauerhafte Ablage des Zustands zwischen Läufen.

Lokal: ein Verzeichnis (``state/``). Auf GitHub: Release-Assets eines festen Tags
(Standard ``datenstand``). Release-Assets sind dauerhaft, liegen nicht in der Git-
Historie und sind über die GitHub-API mit dem Workflow-Token schreibbar.

Assets:
* ``crypto.json``            öffentliche Schlüsselparameter (Salt, Iterationen, Prüfwert)
* ``state.sqlite.tra``       Datenbank (gzip + AES-GCM)
* ``state-<Datum>.sqlite.tra`` ältere Fassungen der Datenbank (ab 1.22, Befund F20): die vom letzten Sichern eines früheren
  Tages und je Kalenderwoche die erste der letzten gut zwei Wochen – entstehen durch Umbenennen, ohne zusätzlichen Upload
* ``site-<id>.tar``          veröffentlichte Snapshot-Dateien (bereits verschlüsselt)
* ``evidence-<id>.tra``      Prüfnachweis (verschlüsselt)

Alle Inhalte mit Kursbezug sind verschlüsselt; im öffentlichen Repository ist ohne
Passphrase nichts davon lesbar.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

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
    # Stufe 3: die Sicherung ist intern; schneller packen zählt hier mehr als wenige Prozent Größe (ab 1.10)
    blob = crypto.pack(tmp.read_bytes(), key, "state/state.sqlite", level=3)
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

    # Ab 1.15: Wiederholungen bei vorübergehenden Fehlern des Upload-Servers (14.10.2026, 17:18 Uhr: HTTP 502 beim
    # Sichern – die Website blieb deshalb zu Recht unverändert, der Lauf war aber vergeblich)
    UPLOAD_ATTEMPTS = 4
    UPLOAD_WAIT_S = (5.0, 15.0, 30.0)

    def upload(self, name: str, data: bytes, existing: dict[str, dict] | None = None) -> None:
        pause = self._client()._sleep  # in Tests ohne Warten
        existing = existing if existing is not None else self.assets()
        last = ""
        for attempt in range(self.UPLOAD_ATTEMPTS):
            if attempt:
                pause(self.UPLOAD_WAIT_S[min(attempt - 1, len(self.UPLOAD_WAIT_S) - 1)])
                existing = self.assets()  # ein abgebrochener Upload kann als unvollständiges Asset liegen bleiben
            if name in existing:
                self.delete(existing[name])
            release = self.release()
            session = self._client()._session  # roher Upload mit Bytes-Inhalt
            try:
                response = session.request(
                    "POST",
                    f"{UPLOADS}/repos/{self.repo}/releases/{release['id']}/assets",
                    params={"name": name},
                    data=data,
                    headers=self._headers({"Content-Type": "application/octet-stream"}),
                    timeout=600,
                )
            except Exception as exc:  # noqa: BLE001 - Verbindung abgebrochen oder Zeitüberschreitung (requests/curl_cffi)
                last = type(exc).__name__
                LOG.warning("Upload %s: %s – Versuch %d von %d", name, last, attempt + 1, self.UPLOAD_ATTEMPTS)
                continue
            status = int(response.status_code)
            if status in (200, 201):
                return
            last = f"HTTP {status}"
            if status < 500 and status != 429:
                break  # kein vorübergehender Fehler
            LOG.warning("Upload %s: %s – Versuch %d von %d", name, last, attempt + 1, self.UPLOAD_ATTEMPTS)
        raise StateError(f"Upload {name}: {last}")

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

    def replace(self, name: str, data: bytes, *, today: dt.date | None = None) -> str | None:
        """Ersetzt ein Asset ohne Lücke: neue Fassung unter Zwischennamen hochladen, dann die alte
        löschen und die neue umbenennen. Bricht der Vorgang an irgendeiner Stelle ab, liegt immer
        mindestens eine vollständige Fassung im Release (siehe :func:`sync_down`).

        Mit ``today`` (ab 1.22, nur für die Datenbank): Stammt die alte Fassung von einem früheren Tag, wird sie nicht
        gelöscht, sondern als ``state-<Tag>.sqlite.tra`` aufbewahrt (Umbenennen, kein zusätzlicher Upload); danach gelten die
        Aufbewahrungsregeln von :func:`generations_to_keep`. Rückgabe: Name der neu aufbewahrten Fassung oder ``None``."""
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
        kept = None
        if name in assets:
            old = assets[name]
            day = berlin_day(old.get("created_at"))
            generation = generation_name(day) if today is not None and day is not None and day < today else None
            if generation is not None and generation not in assets and old.get("state", "uploaded") == "uploaded":
                self.rename(old, generation)
                kept = generation
            else:
                self.delete(old)
        self.rename(assets[temp], name)
        if today is not None:
            self.prune_generations()
        return kept

    def prune_generations(self) -> list[str]:
        """Ältere Datenbankfassungen ausdünnen (:func:`generations_to_keep`)."""
        assets = complete_assets(self.assets())
        days = {day: name for name in assets if (day := generation_day(name)) is not None}
        keep = generations_to_keep(list(days))
        removed = []
        for day, name in sorted(days.items()):
            if day not in keep:
                self.delete(assets[name])
                removed.append(name)
        return removed


PENDING_SUFFIX = ".neu"

# Ältere Fassungen der Datenbanksicherung (ab 1.22, Befund F20 „nur eine Sicherungskopie“)
BERLIN = ZoneInfo("Europe/Berlin")
GENERATION_RE = re.compile(r"^state-(\d{4}-\d{2}-\d{2})\.sqlite\.tra$")
GENERATION_WINDOW_DAYS = 15


def generation_name(day: dt.date) -> str:
    return f"state-{day.isoformat()}.sqlite.tra"


def generation_day(name: str) -> dt.date | None:
    match = GENERATION_RE.match(name)
    if not match:
        return None
    try:
        return dt.date.fromisoformat(match.group(1))
    except ValueError:
        return None


def berlin_day(iso: str | None) -> dt.date | None:
    """Kalendertag (Berlin) eines Zeitstempels der GitHub-Schnittstelle („2026-11-07T13:43:13Z“)."""
    if not iso:
        return None
    try:
        return dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(BERLIN).date()
    except ValueError:
        return None


def berlin_today(now: dt.datetime | None = None) -> dt.date:
    return (now or dt.datetime.now(dt.timezone.utc)).astimezone(BERLIN).date()


def generations_to_keep(days: list[dt.date]) -> set[dt.date]:
    """Welche älteren Fassungen bleiben: die neueste (vom letzten Sichern eines früheren Tages) und je Kalenderwoche die
    erste der letzten 15 Tage – so gibt es fast immer eine Fassung, die eine bis zwei Wochen alt ist, und höchstens vier
    ältere Fassungen (je etwa so groß wie die Datenbanksicherung)."""
    if not days:
        return set()
    newest = max(days)
    keep = {newest}
    first_of_week: dict[tuple[int, int], dt.date] = {}
    for day in sorted(days):
        if day >= newest - dt.timedelta(days=GENERATION_WINDOW_DAYS):
            first_of_week.setdefault(day.isocalendar()[:2], day)
    keep.update(first_of_week.values())
    return keep


def complete_assets(assets: dict[str, dict]) -> dict[str, dict]:
    """Nur vollständig hochgeladene Assets (GitHub kennzeichnet abgebrochene Uploads mit einem anderen ``state``)."""
    return {name: asset for name, asset in assets.items() if asset.get("state", "uploaded") == "uploaded"}


def sync_down(
    store: GitHubReleaseStore,
    state_dir: Path,
    passphrase: str | None,
    *,
    wanted_snapshots: list[str] | None = None,
    wanted_archives: list[str] | None = None,
    include_database: bool = True,
    use_generations: bool = True,
) -> dict:
    """Lädt Schlüsselparameter, Datenbank und gewünschte Snapshot-Archive herunter (``wanted_archives``:
    weitere Archive nach Dateiname, z. B. der aktuelle Signal-Stand).

    ``include_database=False`` (ab 1.10): nur Archive laden. So beim Zwischenstand, dessen Datenbank lokal die
    neueste ist und gleichzeitig im Hintergrund gesichert wird – ein Herunterladen würde sie überschreiben.

    ``use_generations=False`` (ab 1.22): nie auf eine ältere Fassung ausweichen – beim bewussten Neuaufbau des Zustands."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    assets = complete_assets(store.assets())
    info = {"database": False, "snapshots": []}
    if include_database:
        if "crypto.json" in assets:
            atomic_write_bytes(state_dir / "crypto.json", store.download(assets["crypto.json"]))
        key, _ = load_or_create_key(state_dir, passphrase, allow_new=True)
        # Hauptfassung bevorzugen; fehlt sie (Austausch nach dem Löschen abgebrochen), gilt der Zwischenstand. Ab 1.22 (F20):
        # Ist keine davon verwendbar (fehlt, beschädigt, nicht entschlüsselbar), die neueste ältere Fassung – mit Warnung.
        candidates = [n for n in ("state.sqlite.tra", f"state.sqlite.tra{PENDING_SUFFIX}") if n in assets]
        if use_generations:
            candidates += [n for _, n in sorted(((generation_day(n), n) for n in assets if generation_day(n) is not None), reverse=True)]
        last_error: Exception | None = None
        for name in candidates:
            try:
                unpack_database(store.download(assets[name]), key, state_dir / "state.sqlite")
            except (StateError, crypto.ContainerError) as exc:
                last_error = exc
                LOG.warning("Datenbanksicherung %s nicht verwendbar (%s) – nächste Fassung", name, type(exc).__name__)
                continue
            info["database"] = True
            info["database_source"] = name
            if generation_day(name) is not None:
                LOG.warning("Zustand aus der älteren Fassung %s wiederhergestellt – fehlende Tage werden erneut abgerufen", name)
            break
        else:
            if last_error is not None:
                raise last_error
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


def sync_up(
    store: GitHubReleaseStore,
    state_dir: Path,
    conn: sqlite3.Connection,
    key: crypto.KeyMaterial | None,
    *,
    keep_archives: int = 60,
    archive_names: list[str] | None = None,
    today: dt.date | None = None,
) -> dict:
    """Lädt Datenbank, Schlüsselparameter und neue Archive hoch; ältere Archive werden ausgedünnt. Die Fassung eines
    früheren Tages bleibt als ``state-<Tag>.sqlite.tra`` erhalten (ab 1.22, ``today`` Standard: heute in Berlin).

    ``archive_names`` (ab 1.10): nur diese Archive betrachten – nötig, wenn gleichzeitig andere Archive in den
    Ordner geladen werden (Sichern läuft parallel zum Zusammenstellen der Website)."""
    state_dir = Path(state_dir)
    uploaded = []
    db_blob = pack_database(conn, state_dir, key).read_bytes()
    kept = store.replace("state.sqlite.tra", db_blob, today=today or berlin_today())
    uploaded.append("state.sqlite.tra")
    # Die Schlüsselparameter (Salt, Prüfwert) ändern sich nach dem Anlegen nie; ein erneutes
    # Hochladen hätte nur das Risiko, sie zwischen Löschen und Upload zu verlieren.
    crypto_path = state_dir / "crypto.json"
    if crypto_path.exists() and "crypto.json" not in complete_assets(store.assets()):
        store.upload("crypto.json", crypto_path.read_bytes(), store.assets())
        uploaded.append("crypto.json")
    assets = store.assets()
    complete = complete_assets(assets)
    candidates = (
        [state_dir / "archives" / name for name in archive_names]
        if archive_names is not None
        else [path for path in (state_dir / "archives").glob("*") if not path.name.startswith(".")]
    )
    for path in sorted(candidates):
        if not path.exists():
            continue
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
    # Zwischenstände (ab 1.8): nur der neueste wird gebraucht
    keep_intraday = latest_intraday_archive(conn)
    for name in sorted(n for n in assets if is_intraday_archive(n) and n != keep_intraday and n not in removed):
        store.delete(assets[name])
        removed.append(name)
    return {"uploaded": uploaded, "removed": removed, "generation": kept}


def is_intraday_archive(name: str) -> bool:
    """``site-2026-10-14_z0930ab12cd.tar`` – Kennungen offizieller Stände enthalten nach dem Datum nur Hexziffern."""
    return name.startswith("site-") and name.endswith(".tar") and "_z" in name


def latest_intraday_archive(conn: sqlite3.Connection) -> str | None:
    try:
        row = conn.execute("SELECT site_archive FROM zwischenstand ORDER BY created_at DESC LIMIT 1").fetchone()
    except sqlite3.OperationalError:  # Datenbank vor 1.8
        return None
    return row[0] if row else None


def write_local_marker(state_dir: Path, info: dict) -> None:
    atomic_write_json(Path(state_dir) / "last_sync.json", info)


def read_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def as_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
