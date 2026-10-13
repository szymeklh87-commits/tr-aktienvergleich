"""Kurzbericht eines Laufs als Hinweis in der GitHub-Laufübersicht.

Das Protokoll eines Laufs ist lang und lässt sich nur als Ganzes öffnen. Die wichtigsten Angaben
stehen deshalb zusätzlich als Hinweis („notice“) in der Übersicht des Laufs: Ergebnis,
Stichtagskurse je Markt mit Beispielen, Identitätsprüfung, Kursabruf und die Meldungen der
einzelnen Schritte – in dieser Reihenfolge, weil GitHub lange Hinweise abschneidet.

Der Bericht enthält nur Zählungen, Börsensymbole und Kalendertage – keine Kurse und keine
Schlüssel. Dieselben Angaben stehen ohnehin im (öffentlichen) Protokoll des Laufs.
"""

from __future__ import annotations

import sqlite3

# Schritte, deren Meldungen einzeln in den Bericht gehören (je Lauf nur wenige)
INFO_STEPS = ("universum", "identitaet", "stichtag", "kurse", "wechselkurse", "berechnung")
MAX_BEISPIELE = 3
MAX_ZEICHEN = 160
# GitHub kürzt Hinweise bei etwa 4 KB; mit Reserve für Titel und Maskierung
MAX_BYTES = 3500


def _escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _title(text: str) -> str:
    return _escape(text).replace(":", "%3A").replace(",", "%2C")


def _short(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= MAX_ZEICHEN else text[: MAX_ZEICHEN - 1] + "…"


def report_lines(conn: sqlite3.Connection, outcome) -> list[str]:
    """Zeilen des Kurzberichts für den Lauf ``outcome.run_id``, Wichtigstes zuerst."""
    lines = [outcome.message]
    run = conn.execute("SELECT * FROM run WHERE id = ?", (outcome.run_id,)).fetchone()
    if run is None:
        return lines

    details = outcome.details or {}
    completeness = details.get("details") or {}
    per_market = completeness.get("per_market") or {}
    if per_market:
        threshold = float(completeness.get("market_threshold", 0.8))
        parts = []
        for code, stats in sorted(per_market.items()):
            if not stats.get("expected"):
                continue
            share = stats["present"] / stats["expected"]
            parts.append(f"{code} {stats['present']}/{stats['expected']} ({share:.0%}){'' if share >= threshold else ' ✗'}")
        if parts:
            lines.append(f"Stichtagskurse je Markt (nötig {threshold:.0%}): " + ", ".join(parts))
    gaps = details.get("ohne_stichtag") or {}
    for code, examples in sorted(gaps.items()):
        if examples:
            lines.append(f"Ohne Stichtagskurs {code}, z. B.: " + ", ".join(examples[:MAX_BEISPIELE]))

    if run["universe_id"]:
        rows = conn.execute(
            "SELECT COALESCE(i.identity_status, 'offen') AS status, COUNT(*) AS n FROM universe_member m "
            "LEFT JOIN instrument i ON i.isin = m.isin WHERE m.universe_id = ? GROUP BY 1 ORDER BY n DESC",
            (run["universe_id"],),
        ).fetchall()
        if rows:
            lines.append("Identität: " + ", ".join(f"{r['status']} {r['n']}" for r in rows))
    if run["cutoff_day"] is not None:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM fetch_checkpoint WHERE target_key = ? GROUP BY status ORDER BY n DESC",
            (f"{run['cutoff_day']}:{run['data_mode']}",),
        ).fetchall()
        if rows:
            lines.append("Kursabruf zum Stichtag: " + ", ".join(f"{r['status']} {r['n']}" for r in rows))

    warnings: dict[str, list[str]] = {}
    for event in conn.execute("SELECT level, step, message FROM run_event WHERE run_id = ? ORDER BY id", (outcome.run_id,)):
        if event["level"] == "INFO":
            if event["step"] in INFO_STEPS:
                lines.append(_short(event["message"]))
        else:
            first_line = event["message"].splitlines()[0] if event["message"] else ""
            warnings.setdefault(f"{event['level']} {event['step']}", []).append(_short(first_line))
    for label, messages in warnings.items():
        more = f" (+{len(messages) - MAX_BEISPIELE} weitere)" if len(messages) > MAX_BEISPIELE else ""
        lines.append(f"{label}: {len(messages)}× – " + "; ".join(messages[:MAX_BEISPIELE]) + more)
    return lines


def workflow_notice(conn: sqlite3.Connection, outcome) -> str:
    """Eine ``::notice``-Zeile für GitHub Actions (auf die Länge gekürzt, die GitHub anzeigt)."""
    kept: list[str] = []
    size = 0
    lines = report_lines(conn, outcome)
    for index, line in enumerate(lines):
        cost = len(_escape(line).encode("utf-8")) + 3
        if size + cost > MAX_BYTES:
            kept.append(f"… {len(lines) - index} weitere Zeilen im Protokoll")
            break
        kept.append(line)
        size += cost
    return f"::notice title={_title(f'Lauf: {outcome.status}')}::{_escape(chr(10).join(kept))}"
