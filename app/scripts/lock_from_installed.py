"""Erzeugt app/package-lock.json aus einer vorhandenen npm-Installation (versteckte Lockdatei).

Hintergrund: In der Entwicklungsumgebung gab es keinen Registry-Zugang. Die benötigten Pakete
lagen bereits installiert vor (mit npm-eigener ``node_modules/.package-lock.json`` inklusive
``resolved`` und ``integrity``). Dieses Skript übernimmt daraus genau die Abhängigkeitshülle
der App, damit ``npm ci`` in GitHub Actions reproduzierbar dieselben Versionen installiert.

Aufruf:  python app/scripts/lock_from_installed.py /opt/npm-tools/node_modules/.package-lock.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
PUBLIC_REGISTRY = "https://registry.npmjs.org/"
KEEP = ("version", "resolved", "integrity", "license", "dependencies", "optionalDependencies", "peerDependencies", "peerDependenciesMeta", "bin", "engines", "os", "cpu", "funding", "hasInstallScript")


def public_url(url: str | None, name: str) -> str | None:
    """Spiegel-Adressen (z. B. interne Artifactory) auf die öffentliche npm-Registry umschreiben.

    Die ``integrity``-Prüfsumme bleibt gültig: Ein Spiegel liefert dieselbe Paketdatei aus.
    GitHub Actions erreicht nur die öffentliche Registry.
    """
    if not url or url.startswith(PUBLIC_REGISTRY):
        return url
    marker = f"/{name}/-/"
    if marker not in url:
        raise SystemExit(f"{name}: unbekanntes Adressformat {url}")
    return PUBLIC_REGISTRY + name + "/-/" + url.split(marker, 1)[1]


def main(source: str) -> None:
    hidden = json.loads(Path(source).read_text(encoding="utf-8"))["packages"]
    pkg = json.loads((APP / "package.json").read_text(encoding="utf-8"))
    direct = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    dev_only = set(pkg.get("devDependencies", {}))
    out: dict[str, dict] = {}
    missing: list[str] = []
    queue = [(name, name in dev_only) for name in direct]
    prod_names: set[str] = set()
    seen: dict[str, bool] = {}
    while queue:
        name, dev = queue.pop()
        key = f"node_modules/{name}"
        entry = hidden.get(key)
        if entry is None:
            missing.append(name)
            continue
        if name in seen and (seen[name] is False or dev):
            continue
        seen[name] = dev if name not in seen else (seen[name] and dev)
        if not dev:
            prod_names.add(name)
        for dep in {**entry.get("dependencies", {}), **entry.get("peerDependencies", {})}:
            queue.append((dep, dev))
        for dep in entry.get("optionalDependencies", {}):
            if f"node_modules/{dep}" in hidden:
                queue.append((dep, dev))
    for name in sorted(seen):
        entry = hidden[f"node_modules/{name}"]
        record = {k: entry[k] for k in KEEP if k in entry}
        record["resolved"] = public_url(record.get("resolved"), name)
        if name not in prod_names:
            record["dev"] = True
        if entry.get("optional"):
            record["optional"] = True
        out[f"node_modules/{name}"] = record
    for name, spec in direct.items():
        version = out.get(f"node_modules/{name}", {}).get("version")
        if version != spec:
            raise SystemExit(f"{name}: package.json verlangt {spec}, installiert ist {version}")
    lock = {
        "name": pkg["name"],
        "version": pkg["version"],
        "lockfileVersion": 3,
        "requires": True,
        "packages": {
            "": {
                "name": pkg["name"],
                "version": pkg["version"],
                "dependencies": pkg.get("dependencies", {}),
                "devDependencies": pkg.get("devDependencies", {}),
                "engines": pkg.get("engines", {}),
            },
            **out,
        },
    }
    (APP / "package-lock.json").write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"package-lock.json: {len(out)} Pakete; nicht gefunden (optional, plattformfremd): {sorted(set(missing))}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/opt/npm-tools/node_modules/.package-lock.json")
