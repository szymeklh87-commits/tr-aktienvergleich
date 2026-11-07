"""Kurzbericht eines Laufs als Hinweis in der GitHub-Laufübersicht.

Das Protokoll eines Laufs ist lang und lässt sich nur als Ganzes öffnen. Die wichtigsten Angaben
stehen deshalb zusätzlich als Hinweis („notice“) in der Übersicht des Laufs: Ergebnis,
Stichtagskurse je Markt mit Beispielen, Identitätsprüfung, Kursabruf und die Meldungen der
einzelnen Schritte – in dieser Reihenfolge, weil GitHub lange Hinweise abschneidet.

Der Bericht enthält nur Zählungen, Börsencodes, Fehlerarten und Kalendertage – keine Kurse und keine
Schlüssel. Ab 1.21.0 (Befund F19) auch keine Kürzel, Anbietersymbole oder ISINs von Aktien: Die Laufübersicht eines
öffentlichen Repositorys kann jeder lesen. Statt Beispielen je Börse stehen dort die Fehlerarten mit ihrer Anzahl; was
trotzdem in einer Meldung steht (z. B. „Anbieter drosselt bei …“), wird beim Zusammenstellen unkenntlich gemacht.
Die vollständigen Meldungen bleiben im verschlüsselten Zustand (Tabelle ``run_event``).
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter

# Schritte, deren Meldungen einzeln in den Bericht gehören (je Lauf nur wenige)
INFO_STEPS = ("universum", "identitaet", "stichtag", "kurse", "wechselkurse", "berechnung", "kursabgleich", "boersenplatz", "umschichtung")
MAX_BEISPIELE = 3
MAX_ZEICHEN = 160
# GitHub kürzt Hinweise bei etwa 4 KB; mit Reserve für Titel und Maskierung
MAX_BYTES = 3500


_ISIN = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-=^&]*")
# Großgeschriebene Wörter der eigenen Meldungen, die zufällig auch ein Kürzel sein können
_KEEP = frozenset({
    "API", "ATR", "CRV", "CSE", "CSV", "DEMO", "ETF", "EZB", "GPW", "HTTP", "HTTPS", "ISIN", "JSON", "KI", "NAS", "NCM", "NGM", "NMS", "NOCP",
    "OK", "OTC", "RSI", "SIX", "SMA", "TMX", "TR", "TSX", "URL", "US", "UTC",
})


def identifiers(conn: sqlite3.Connection) -> frozenset[str]:
    """Kürzel und Anbietersymbole aller Notierungen (auch frühere) – sie kommen nicht in den öffentlichen Bericht.
    Nur Werte mit mindestens einem Buchstaben und ohne Kleinbuchstaben: Zählungen wie „2780 Abrufe“ bleiben stehen,
    obwohl es Börsen mit Ziffernkürzeln gibt; Börsencodes und Währungen bleiben lesbar."""
    values: set[str] = set()
    for row in conn.execute("SELECT provider_symbol, ticker FROM listing"):
        values.update(str(v) for v in row if v)
    for row in conn.execute("SELECT alias FROM instrument_alias WHERE kind IN ('ticker', 'symbol')"):
        values.add(str(row[0]))
    keep = set(_KEEP)
    for row in conn.execute("SELECT DISTINCT exchange_key, mic, currency FROM listing"):
        keep.update(str(v) for v in row if v)
    return frozenset(v for v in values if len(v) >= 2 and v == v.upper() and any(c.isalpha() for c in v) and v not in keep)


def public_text(text: str, known: frozenset[str]) -> str:
    """ISINs und bekannte Kürzel unkenntlich machen (ab 1.21.0, Befund F19)."""
    text = _ISIN.sub("[ISIN]", text)

    def mask(match: re.Match) -> str:
        word = match.group(0)
        core = word.rstrip(".-")
        return "[Kürzel]" + word[len(core):] if core in known else word

    return _TOKEN.sub(mask, text)


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
        return [public_text(line, identifiers(conn)) for line in lines]

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
        for status, label in (("keine_daten", "Keine Kursdaten"), ("fehler", "Abruffehler")):
            line = _failures_by_exchange(conn, f"{run['cutoff_day']}:{run['data_mode']}", status, label)
            if line:
                lines.append(line)

    warnings: dict[str, list[str]] = {}
    events = conn.execute("SELECT level, step, message FROM run_event WHERE run_id = ? ORDER BY id", (outcome.run_id,)).fetchall()
    for event in events:
        if event["level"] == "INFO":
            if event["step"] in INFO_STEPS:
                lines.append(_short(event["message"]))
        else:
            first_line = event["message"].splitlines()[0] if event["message"] else ""
            warnings.setdefault(f"{event['level']} {event['step']}", []).append(_short(first_line))
    for label, messages in warnings.items():
        more = f" (+{len(messages) - MAX_BEISPIELE} weitere)" if len(messages) > MAX_BEISPIELE else ""
        lines.append(f"{label}: {len(messages)}× – " + "; ".join(messages[:MAX_BEISPIELE]) + more)
    # Beispiele ohne Stichtagskurs zuletzt und in einer Zeile: bei vielen betroffenen Börsen würden sie
    # sonst die Zählungen aus dem (von GitHub gekürzten) Hinweis verdrängen. Ab 1.21.0 ohne Kürzel: nur der letzte
    # Kurstag davor („vorher 2026-10-09“) mit Anzahl
    examples = []
    for code, items in sorted(gaps.items()):
        kinds = Counter(item.rsplit(" (", 1)[-1].rstrip(")") if " (" in item else "ohne Angabe" for item in items)
        if kinds:
            examples.append(f"{code} " + ", ".join(f"{kind} {n}×" for kind, n in kinds.most_common()))
    if examples:
        lines.append(_short_long("Ohne Stichtagskurs, Beispiele je Börse: " + "; ".join(examples), 1200))
    known = identifiers(conn)
    return [public_text(line, known) for line in lines]


def _failures_by_exchange(conn: sqlite3.Connection, target_key: str, status: str, label: str) -> str | None:
    """„Keine Kursdaten je Börse: XTSE 512 (Symbol unbekannt (404) 510, keine gültigen Tageskurse im Zeitraum 2), …“ –
    zeigt, ob ein Symbolformat oder eine ganze Börse betroffen ist. Bis 1.20 mit zwei Kürzeln als Beispiel, ab 1.21.0
    die zwei häufigsten Fehlerarten mit Anzahl (Befund F19: keine Kürzel im öffentlichen Bericht)."""
    rows = conn.execute(
        "SELECT COALESCE(l.exchange_key, '?') AS exchange, COUNT(*) AS n FROM fetch_checkpoint f "
        "JOIN listing l ON l.id = f.listing_id WHERE f.target_key = ? AND f.status = ? GROUP BY 1 ORDER BY n DESC, exchange",
        (target_key, status),
    ).fetchall()
    if not rows:
        return None
    parts = []
    for row in rows:
        text = f"{row['exchange']} {row['n']}"
        if len(parts) < 6:
            errors = conn.execute(
                "SELECT l.provider_symbol AS symbol, l.last_error AS error FROM fetch_checkpoint f JOIN listing l ON l.id = f.listing_id "
                "WHERE f.target_key = ? AND f.status = ? AND COALESCE(l.exchange_key, '?') = ?",
                (target_key, status, row["exchange"]),
            ).fetchall()
            kinds = Counter(_reason(e["symbol"] or "", e["error"]) if e["error"] else "ohne Meldung" for e in errors)
            shown = [f"{kind} {n}" for kind, n in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))[:2]]
            text += f" ({', '.join(shown)}{', …' if len(kinds) > 2 else ''})"
        parts.append(text)
    return _short_long(f"{label} je Börse: " + ", ".join(parts))


def _reason(symbol: str, error: str) -> str:
    text = " ".join(str(error).split())
    prefix = f"{symbol}: "
    if symbol and text.startswith(prefix):
        text = text[len(prefix):]
    if symbol:
        text = text.replace(symbol, "[Kürzel]")
    return text if len(text) <= 60 else text[:59] + "…"


def _short_long(text: str, limit: int = 900) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


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
