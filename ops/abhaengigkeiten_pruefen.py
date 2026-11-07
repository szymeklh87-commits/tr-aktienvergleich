"""Bekannte Sicherheitslücken in den festgelegten Abhängigkeiten suchen (ab 1.22, Befund F17) – nur Standardbibliothek.

Fragt die öffentliche, kostenlose Datenbank OSV (https://osv.dev, Google; ohne Konto und ohne Schlüssel) nach jeder
Bibliothek mit ihrer genauen Version aus

* ``backend/requirements.txt`` und ``backend/requirements-dev.txt`` (PyPI) und
* ``app/package-lock.json`` (npm; auch Bibliotheken, die nur zum Bauen gebraucht werden, gekennzeichnet).

Ausgabe: je Fund eine Hinweiszeile mit Bibliothek, Version und Kennung der Lücke (öffentlich unbedenklich – keine Kursdaten),
dazu eine Zusammenfassung. Standard: Funde sind Warnungen (Rückgabe 0), damit eine neu bekannt gewordene Lücke einer mittelbar
gebrauchten Bibliothek nicht jeden Lauf rot macht; mit ``--streng`` Rückgabe 1. Ist OSV nicht erreichbar: Warnung, Rückgabe 0
(``--streng``: 2) – die Prüfung ist eine Kontrolle, kein Teil des Betriebs.

Aufruf: ``python ops/abhaengigkeiten_pruefen.py`` (Workflow „Prüfung“ bei jeder Änderung, „Sicherung prüfen“ monatlich).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
BATCH = 500

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sperrdatei_pruefen import read_lock  # noqa: E402


def python_packages(files: list[Path]) -> list[tuple[str, str, str]]:
    out: dict[str, tuple[str, str, str]] = {}
    for path in files:
        if path.exists():
            pins, _ = read_lock(path)
            for name, version in pins.values():
                out[name.lower()] = ("PyPI", name, version)
    return sorted(out.values())


def npm_packages(lock: Path) -> list[tuple[str, str, str]]:
    if not lock.exists():
        return []
    data = json.loads(lock.read_text(encoding="utf-8"))
    out = []
    for key, entry in sorted((data.get("packages") or {}).items()):
        if not key.startswith("node_modules/") or not entry.get("version"):
            continue
        name = key.split("node_modules/")[-1]
        out.append(("npm", name, str(entry["version"])))
    return out


Opener = Callable[[urllib.request.Request, float], object]


def _default_opener(request: urllib.request.Request, timeout: float):
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310 - feste https-Adresse


def query(packages: list[tuple[str, str, str]], opener: Opener = _default_opener) -> dict[tuple[str, str, str], list[str]]:
    """``{(Ökosystem, Name, Version): [Kennungen]}`` – nur Pakete mit Fund."""
    found: dict[tuple[str, str, str], list[str]] = {}
    for start in range(0, len(packages), BATCH):
        part = packages[start : start + BATCH]
        body = json.dumps({"queries": [{"package": {"ecosystem": eco, "name": name}, "version": version} for eco, name, version in part]}).encode()
        request = urllib.request.Request(OSV_BATCH, data=body, headers={"Content-Type": "application/json", "User-Agent": "tr-aktienvergleich-abhaengigkeiten"})
        with opener(request, 60.0) as response:  # type: ignore[attr-defined]
            results = json.loads(response.read().decode("utf-8")).get("results") or []
        for package, result in zip(part, results):
            ids = sorted({v.get("id") for v in (result or {}).get("vulns") or [] if v.get("id")})
            if ids:
                found[package] = ids
    return found


def main(argv: list[str] | None = None, opener: Opener = _default_opener) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--streng", action="store_true", help="Funde machen den Schritt rot")
    args = parser.parse_args(argv)
    backend = ROOT / "backend"
    packages = python_packages([backend / "requirements.txt", backend / "requirements-dev.txt"]) + npm_packages(ROOT / "app" / "package-lock.json")
    try:
        found = query(packages, opener)
    except Exception as exc:  # noqa: BLE001 - Netz, Antwortformat
        print(f"::warning title=Abhängigkeiten::OSV nicht erreichbar ({type(exc).__name__}) – {len(packages)} Bibliotheken ungeprüft")
        return 2 if args.streng else 0
    level = "error" if args.streng else "warning"
    for (eco, name, version), ids in sorted(found.items()):
        print(f"::{level} title=Bekannte Lücke ({eco})::{name} {version}: {', '.join(ids[:8])}{' …' if len(ids) > 8 else ''}")
    python_n = sum(1 for p in packages if p[0] == "PyPI")
    line = f"Abhängigkeiten geprüft (OSV): {python_n} Python-Bibliotheken, {len(packages) - python_n} npm-Pakete – {len(found)} mit bekannter Lücke"
    print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")
    return 1 if (found and args.streng) else 0


if __name__ == "__main__":
    sys.exit(main())
