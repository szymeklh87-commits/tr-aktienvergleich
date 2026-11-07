"""Sperrdatei der Python-Abhängigkeiten prüfen (ab 1.22, Befund F08) – nur Standardbibliothek.

Prüft drei Dinge und meldet jede Abweichung mit Bibliothek und Version (öffentlich unbedenklich – keine Kursdaten):

1. ``backend/requirements.txt`` legt jede Bibliothek mit genau einer Version fest (``name==version``), ohne Doppelungen.
2. Jede Version liegt im erlaubten Bereich aus ``backend/requirements.in`` (``>=``, ``<``, ``<=``, ``>``, ``==``).
3. Mit ``--umgebung``: Die installierte Umgebung entspricht genau den Sperrdateien (``requirements.txt`` und, falls
   angegeben, weiteren wie ``requirements-dev.txt``) – keine zusätzliche, fehlende oder abweichende Bibliothek. So zeigt die
   Prüfung auf GitHub, wenn eine mittelbar gebrauchte Bibliothek in der Sperrdatei fehlt.

Aufruf im Workflow „Prüfung“ nach der Installation:

    python ops/sperrdatei_pruefen.py --umgebung backend/requirements.txt backend/requirements-dev.txt

Rückgabe 0 = in Ordnung, 1 = Abweichung (mit ``::error``-Zeilen).
"""

from __future__ import annotations

import argparse
import re
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "backend" / "requirements.txt"
RANGES = ROOT / "backend" / "requirements.in"
# Werkzeuge der Umgebung selbst – gehören in keine Sperrdatei
IGNORE = {"pip", "setuptools", "wheel", "packaging"}

_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([0-9][0-9A-Za-z.+-]*)$")
_SPEC = re.compile(r"(>=|<=|==|!=|>|<)\s*([0-9][0-9A-Za-z.*+-]*)")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def version_key(version: str) -> tuple:
    """Vergleichbarer Schlüssel für die hier vorkommenden Versionen (Zahlen, gefolgt von optionalem Zusatz)."""
    parts: list = []
    for piece in re.split(r"[.+-]", version):
        match = re.match(r"^(\d+)(.*)$", piece)
        if match:
            parts.append((int(match.group(1)), match.group(2)))
        else:
            parts.append((-1, piece))
    while parts and parts[-1] == (0, ""):
        parts.pop()
    return tuple(parts)


def satisfies(version: str, spec: str) -> bool:
    for op, bound in _SPEC.findall(spec):
        a, b = version_key(version), version_key(bound.rstrip(".*"))
        if op == ">=" and not a >= b:
            return False
        if op == ">" and not a > b:
            return False
        if op == "<=" and not a <= b:
            return False
        if op == "<" and not a < b:
            return False
        if op == "==" and not (a == b or (bound.endswith(".*") and a[: len(b)] == b)):
            return False
        if op == "!=" and a == b:
            return False
    return True


def read_lock(path: Path) -> tuple[dict[str, tuple[str, str]], list[str]]:
    """``{normalisierter Name: (Name, Version)}`` und Fehler; ``-r`` wird gefolgt."""
    pins: dict[str, tuple[str, str]] = {}
    errors: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-r "):
            sub, sub_errors = read_lock(path.parent / line[3:].strip())
            errors += sub_errors
            for key, value in sub.items():
                if key in pins:
                    errors.append(f"{path.name}: {value[0]} doppelt festgelegt")
                pins[key] = value
            continue
        match = _PIN.match(line)
        if not match:
            errors.append(f"{path.name}: „{line}“ ist nicht genau festgelegt (verlangt: name==version)")
            continue
        key = normalize(match.group(1))
        if key in pins:
            errors.append(f"{path.name}: {match.group(1)} doppelt festgelegt")
        pins[key] = (match.group(1), match.group(2))
    return pins, errors


def read_ranges(path: Path) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)$", line)
        if match:
            out[normalize(match.group(1))] = (match.group(1), match.group(2).strip())
    return out


def installed() -> dict[str, tuple[str, str]]:
    out = {}
    for dist in metadata.distributions():
        name = dist.metadata.get("Name") or ""
        if name:
            out[normalize(name)] = (name, dist.version)
    return out


def check(lock_files: list[Path], ranges_file: Path, environment: dict[str, tuple[str, str]] | None) -> list[str]:
    errors: list[str] = []
    pins: dict[str, tuple[str, str]] = {}
    for path in lock_files:
        found, found_errors = read_lock(path)
        errors += found_errors
        pins.update(found)
    runtime, _ = read_lock(lock_files[0])
    for key, (name, spec) in read_ranges(ranges_file).items():
        if key not in runtime:
            errors.append(f"{name} steht in requirements.in, fehlt aber in der Sperrdatei")
        elif spec and not satisfies(runtime[key][1], spec):
            errors.append(f"{name}=={runtime[key][1]} liegt nicht im erlaubten Bereich „{spec}“")
    if environment is not None:
        for key, (name, version) in sorted(environment.items()):
            if key in IGNORE:
                continue
            if key not in pins:
                errors.append(f"installiert, aber nicht in der Sperrdatei: {name}=={version}")
            elif version_key(pins[key][1]) != version_key(version):
                errors.append(f"{name}: installiert {version}, festgelegt {pins[key][1]}")
        for key, (name, version) in sorted(pins.items()):
            if key not in environment:
                errors.append(f"festgelegt, aber nicht installiert: {name}=={version}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("dateien", nargs="*", type=Path, help="Sperrdateien (Standard: backend/requirements.txt)")
    parser.add_argument("--umgebung", action="store_true", help="installierte Umgebung mit den Sperrdateien vergleichen")
    args = parser.parse_args(argv)
    files = args.dateien or [LOCK]
    errors = check(files, RANGES, installed() if args.umgebung else None)
    for error in errors:
        print(f"::error title=Sperrdatei::{error}")
    if not errors:
        pins, _ = read_lock(files[0])
        print(f"Sperrdatei in Ordnung: {len(pins)} Bibliotheken genau festgelegt" + (", Umgebung stimmt überein" if args.umgebung else ""))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
