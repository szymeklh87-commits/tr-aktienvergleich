"""Reihenfolge der gestaffelten Aktualisierung (ab 1.10/1.11): welche Aktien zuerst neue Kurse bekommen.

Wunsch vom 14.10.2026: „Die Aktien, die sich wiederholen, die lukrativ waren, gestiegen sind, auf den höchsten
Rängen als erstes aktualisieren, um zu prüfen, ob sie noch gut sind – Neuzugänge bei Bedarf einfügen.“

Grundlage ist der zuletzt veröffentlichte Datenstand (offiziell oder Zwischenstand): seine Kopfdateien
``windows/<h>.bin`` enthalten die ersten 50 Plätze jeder Rangliste (Gruppe A und B, alle elf Gewichtungen,
1–90 Tage). Je Aktie wird gezählt, wie oft sie auf Platz 1, unter den ersten 3, 10 und ``top_n`` stand –
getrennt für die Standardauswahl der App (40/60, 50/50, 60/40, 1–30 Tage) und für alle Ranglisten.

Reihenfolge: Top-10-Nennungen in der Standardauswahl, dann erste Plätze, Top-10- und Top-``top_n``-Nennungen
über alle Ranglisten, bei Gleichstand nach ISIN. Das ist nur die Reihenfolge des Kursabrufs – gerechnet wird
danach wie immer mit allen Regeln; Aktien ohne neuen Kurs bleiben in Stufe 1 außen vor und kommen in Stufe 2.
"""

from __future__ import annotations

import io
import json
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

from ..util import crypto

STANDARD_WEIGHTS = (40, 50, 60)
STANDARD_DAYS = 30


@dataclass
class PriorityCounts:
    isin: str
    std_n1: int = 0
    std_n10: int = 0
    n1: int = 0
    n3: int = 0
    n10: int = 0
    n_top: int = 0
    best: int = 10**6
    windows: set = field(default_factory=set)

    def key(self) -> tuple:
        return (-self.std_n10, -self.std_n1, -self.n1, -self.n10, -self.n_top, self.best, self.isin)


def _read_member(tar: tarfile.TarFile, snapshot_id: str, relative: str, key) -> dict | None:
    try:
        member = tar.getmember(f"{snapshot_id}/{relative}")
    except KeyError:
        return None
    handle = tar.extractfile(member)
    if handle is None:
        return None
    plain = crypto.unpack(handle.read(), key, f"snapshots/{snapshot_id}/{relative}")
    return json.loads(plain.decode("utf-8"))


def _rankings(payload: dict) -> list[tuple[str, int, list[int]]]:
    """(Gruppe, Gewichtung, Reihenfolge) aller Ranglisten einer Kopfdatei; 0/100 ist die reine Renditeliste."""
    orders = payload.get("orders") or {}
    out: list[tuple[str, int, list[int]]] = [("a", 0, list(orders.get("v0") or []))]
    for weight, order in (orders.get("u") or {}).items():
        if int(weight) != 0:
            out.append(("a", int(weight), list(order or [])))
    if orders.get("v0l"):
        out.append(("b", 0, list(orders.get("v0l") or [])))
    for weight, order in (orders.get("ul") or {}).items():
        if int(weight) != 0:
            out.append(("b", int(weight), list(order or [])))
    return out


def priority_counts(archive: bytes | Path, snapshot_id: str, key, *, top_n: int = 25) -> list[PriorityCounts]:
    """Zählungen je Aktie aus dem Archiv ``site-<snapshot_id>.tar`` (Reihenfolge: wichtigste zuerst)."""
    data = archive.read_bytes() if isinstance(archive, Path) else archive
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
        instruments = _read_member(tar, snapshot_id, "instruments.bin", key)
        if not instruments:
            return []
        isins: list[str] = list(instruments.get("isin") or [])
        counts: dict[int, PriorityCounts] = {}
        for h in range(1, 91):
            payload = _read_member(tar, snapshot_id, f"windows/{h}.bin", key)
            if payload is None:
                continue
            for _group, weight, order in _rankings(payload):
                standard = h <= STANDARD_DAYS and weight in STANDARD_WEIGHTS
                for position, idx in enumerate(order[:top_n]):
                    if not (0 <= idx < len(isins)):
                        continue
                    entry = counts.get(idx)
                    if entry is None:
                        entry = counts[idx] = PriorityCounts(isin=isins[idx])
                    entry.n_top += 1
                    entry.best = min(entry.best, position + 1)
                    entry.windows.add(h)
                    if position < 10:
                        entry.n10 += 1
                        if standard:
                            entry.std_n10 += 1
                    if position < 3:
                        entry.n3 += 1
                    if position == 0:
                        entry.n1 += 1
                        if standard:
                            entry.std_n1 += 1
    return sorted(counts.values(), key=PriorityCounts.key)


def priority_isins(archive: bytes | Path, snapshot_id: str, key, *, top_n: int = 25, limit: int | None = None) -> list[str]:
    """ISINs in der Reihenfolge der gestaffelten Aktualisierung (höchstens ``limit``)."""
    ranked = [entry.isin for entry in priority_counts(archive, snapshot_id, key, top_n=top_n)]
    return ranked if limit is None else ranked[:limit]
