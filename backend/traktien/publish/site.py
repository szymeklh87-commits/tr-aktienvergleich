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


def retained_snapshots(index: dict, keep: int) -> list[dict]:
    """Die letzten ``keep`` Snapshots, zusätzlich immer der neueste vollständige."""
    snapshots = index.get("snapshots", [])
    chosen = snapshots[:keep]
    complete = next((s for s in snapshots if s.get("completeness") == "vollstaendig"), None)
    if complete is not None and complete not in chosen:
        chosen.append(complete)
    return chosen


def assemble_site(
    *,
    app_dist: Path,
    state_dir: Path,
    out_dir: Path,
    crypto_descriptor: dict,
    keep: int = 5,
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
        archive = state_dir / "archives" / f"site-{item['snapshot_id']}.tar"
        if not archive.exists():
            continue
        safe_extract_tar(archive.read_bytes(), data / "snapshots")
        available.append(item)
    site_index = {"schema": "tr-snapshot-index/1", "snapshots": available}
    status = dict(status)
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
