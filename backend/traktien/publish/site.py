"""Zusammenbau der statischen Website (App-Hülle + Daten der letzten Snapshots).

Die Veröffentlichung ist atomar: GitHub Pages schaltet eine Bereitstellung als Ganzes
um. Lokal wird erst in ein temporäres Verzeichnis geschrieben und dann umbenannt.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from ..util import crypto
from ..util.jsonio import atomic_write_json, read_json
from .snapshot_writer import safe_extract_tar


# Stände auf der Website, ein Zwischenstand mitgezählt (``aufbewahrung.site_snapshots``). Ab 14.10.2026 drei statt
# fünf: weniger zu prüfen, hochzuladen und bereitzustellen. Ältere Stände bleiben als Archiv im Release.
SITE_SNAPSHOTS_DEFAULT = 3


def retained_snapshots(index: dict, keep: int) -> list[dict]:
    """Die letzten ``keep`` Snapshots, zusätzlich immer der neueste vollständige.

    Ab 1.17.1 je Kurstag und Art (Stand mit Schlusskursen bzw. Zwischenstand) nur der neueste: Wurde ein Stichtag noch
    einmal gerechnet, verdrängte bis 1.17.0 die ältere Fassung desselben Tages einen älteren Kurstag aus „Frühere Stände“
    (am 24.10.2026: zweimal der 23.10., dafür fehlte der 21.10.)."""
    snapshots = index.get("snapshots", [])
    chosen: list[dict] = []
    seen: set[tuple] = set()
    for entry in snapshots:
        day = entry.get("cutoff_session_date") or str(entry.get("snapshot_id", "")).split("_", 1)[0]
        kind = (day, entry.get("art") or "offiziell")
        if kind in seen:
            continue
        seen.add(kind)
        chosen.append(entry)
        if len(chosen) >= keep:
            break
    complete = next((s for s in snapshots if s.get("completeness") == "vollstaendig"), None)
    if complete is not None and complete not in chosen:
        chosen.append(complete)
    return chosen


CACHE_DIR = "site_cache"  # ab 1.12: im Voraus entpackte Archive (Unterordner „snapshots“ und „signale“)


def link_tree(source: Path, target: Path) -> int:
    """Dateien eines Ordners als harte Verweise an einen anderen Ort legen (ohne zu kopieren); geht das nicht
    (anderes Dateisystem), wird kopiert. Rückgabe: Zahl der Dateien."""
    count = 0
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        dest = target / path.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(path, dest)
        except OSError:
            shutil.copy2(path, dest)
        count += 1
    return count


def prepare_site_cache(state_dir: Path, snapshot_ids: list[str], signal_archives: list[str]) -> dict:
    """Archive älterer Stände und des Signal-Stands im Voraus entpacken (ab 1.12, im Hintergrund während des
    Kursabrufs): ``<state>/site_cache/snapshots/<id>/…`` und ``<state>/site_cache/signale/<id>/…``. Das
    Zusammenstellen der Website legt diese Dateien danach nur noch als Verweise ab. Fehlt ein Archiv, wird es
    übersprungen (dann gilt der bisherige Weg)."""
    state_dir = Path(state_dir)
    cache = state_dir / CACHE_DIR
    done: dict[str, list[str]] = {"snapshots": [], "signale": []}
    for snapshot_id in snapshot_ids:
        archive = state_dir / "archives" / f"site-{snapshot_id}.tar"
        if not archive.exists() or (cache / "snapshots" / snapshot_id).exists():
            continue
        staging = cache / "snapshots" / f".tmp-{snapshot_id}"
        if staging.exists():
            shutil.rmtree(staging)
        safe_extract_tar(archive.read_bytes(), staging)
        if (staging / snapshot_id / "manifest.bin").exists():
            (staging / snapshot_id).rename(cache / "snapshots" / snapshot_id)
        shutil.rmtree(staging, ignore_errors=True)
        done["snapshots"].append(snapshot_id)
    for name in signal_archives:
        archive = state_dir / "archives" / name
        if not archive.exists():
            continue
        staging = cache / "signale" / f".tmp-{name}"
        if staging.exists():
            shutil.rmtree(staging)
        safe_extract_tar(archive.read_bytes(), staging)
        for child in staging.iterdir():
            if child.is_dir() and not (cache / "signale" / child.name).exists():
                child.rename(cache / "signale" / child.name)
        shutil.rmtree(staging, ignore_errors=True)
        done["signale"].append(name)
    return done


def _place_snapshot(state_dir: Path, snapshot_id: str, target: Path) -> bool:
    """Snapshot-Dateien in die Website legen: zuerst aus dem Vorab-Entpackten, dann aus dem eben geschriebenen
    Ordner des Laufs (Verweise), sonst wie bisher aus dem Archiv. False, wenn es nichts davon gibt."""
    for source in (state_dir / CACHE_DIR / "snapshots" / snapshot_id, state_dir / "snapshots" / snapshot_id):
        if (source / "manifest.bin").exists():
            link_tree(source, target / snapshot_id)
            return True
    archive = state_dir / "archives" / f"site-{snapshot_id}.tar"
    if not archive.exists():
        return False
    safe_extract_tar(archive.read_bytes(), target)
    return True


def assemble_site(
    *,
    app_dist: Path,
    state_dir: Path,
    out_dir: Path,
    crypto_descriptor: dict,
    keep: int = SITE_SNAPSHOTS_DEFAULT,
) -> dict:
    app_dist, state_dir, out_dir = Path(app_dist), Path(state_dir), Path(out_dir)
    tmp = out_dir.parent / f".tmp-{out_dir.name}"
    if tmp.exists():
        shutil.rmtree(tmp)
    if not (app_dist / "index.html").exists():
        raise FileNotFoundError(f"App-Build fehlt: {app_dist}/index.html")
    shutil.copytree(app_dist, tmp)
    data = tmp / "data"
    (data / "snapshots").mkdir(parents=True, exist_ok=True)
    meta_dir = state_dir / "site_meta"
    index = read_json(meta_dir / "index.json") if (meta_dir / "index.json").exists() else {"schema": "tr-snapshot-index/1", "snapshots": []}
    status = read_json(meta_dir / "status.json") if (meta_dir / "status.json").exists() else {"schema": "tr-status/1", "latest_snapshot_id": None}
    chosen = retained_snapshots(index, keep)
    available = []
    for item in chosen:
        if _place_snapshot(state_dir, item["snapshot_id"], data / "snapshots"):
            available.append(item)
    site_index = {"schema": "tr-snapshot-index/1", "snapshots": available}
    status = dict(status)
    # Signal-Stand (ab 1.6): Kennzahlen, Kursziele und Signale – unabhängig vom Kurs-Datenstand aktualisierbar
    status.pop("signale", None)
    signals = read_json(meta_dir / "signale.json") if (meta_dir / "signale.json").exists() else None
    if signals and signals.get("archiv"):
        archive = state_dir / "archives" / signals["archiv"]
        cached = state_dir / CACHE_DIR / "signale" / str(signals.get("id") or "")
        if signals.get("id") and (cached / "signale.bin").exists():
            link_tree(cached, data / "signale" / signals["id"])
            status["signale"] = {k: signals.get(k) for k in SIGNAL_STATUS_KEYS}
        elif archive.exists():
            (data / "signale").mkdir(parents=True, exist_ok=True)
            safe_extract_tar(archive.read_bytes(), data / "signale")
            status["signale"] = {k: signals.get(k) for k in SIGNAL_STATUS_KEYS}
    status["aktualisieren"] = update_links()
    status["encryption"] = {"enabled": bool(crypto_descriptor.get("enabled")), "descriptor": "data/crypto.json"}
    status["retained_snapshot_ids"] = [s["snapshot_id"] for s in available]
    if status.get("latest_snapshot_id") not in status["retained_snapshot_ids"]:
        status["latest_snapshot_id"] = available[0]["snapshot_id"] if available else None
    atomic_write_json(data / "status.json", status)
    atomic_write_json(data / "crypto.json", crypto_descriptor)
    atomic_write_json(data / "snapshots" / "index.json", site_index)
    (tmp / ".nojekyll").write_text("", encoding="utf-8")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    tmp.rename(out_dir)
    return {"snapshots": [s["snapshot_id"] for s in available], "status": status}


WORKFLOW_FILE = "taeglich.yml"
SIGNAL_STATUS_KEYS = (
    "id", "erstellt_utc", "kursstand", "snapshot_id", "aktien", "mit_kennzahlen", "mit_kursziel", "beide_gruen", "kurz_gruen", "lang_gruen",
    "gesamt_stark", "gesamt_mittel", "version",
)


def update_links() -> dict | None:
    """Links zum manuellen Start des täglichen Laufs (nur in GitHub Actions bekannt).

    Die App startet den Lauf nicht selbst – sie enthält aus Sicherheitsgründen keinen Schlüssel.
    Gestartet wird auf GitHub mit der Anmeldung des Nutzers („Run workflow“).
    """
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        return None
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").strip().rstrip("/")
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+", server):
        return None
    return {
        "repository": repository,
        "workflow": WORKFLOW_FILE,
        "starten_url": f"{server}/{repository}/actions/workflows/{WORKFLOW_FILE}",
        "laeufe_url": f"{server}/{repository}/actions",
    }


def descriptor_for(key: crypto.KeyMaterial | None) -> dict:
    return crypto.crypto_descriptor(key)


def write_json(path: Path, value) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
