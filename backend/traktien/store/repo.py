"""Datenzugriff (parametrisierte SQL-Abfragen, keine String-Verkettung mit Eingaben)."""

from __future__ import annotations

import json
import math
import sqlite3
from typing import Iterable

import numpy as np

from ..analytics.quality import SplitEvent
from ..providers.base import ListingCandidate, PriceHistory
from ..providers.exchanges import ExchangeTable, unit_info
from ..providers.identity import IdentityResult
from ..util.timeutil import iso_utc, utc_now


def now_iso() -> str:
    return iso_utc(utc_now())


# ----------------------------------------------------------------- KV

def kv_get(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def kv_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT INTO kv(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


# ----------------------------------------------------------- Universum

def latest_universe(conn: sqlite3.Connection, status: str = "akzeptiert", data_mode: str | None = None):
    sql = "SELECT * FROM universe_snapshot WHERE status = ?"
    params: list = [status]
    if data_mode:
        sql += " AND data_mode = ?"
        params.append(data_mode)
    sql += " ORDER BY retrieved_at DESC, created_at DESC LIMIT 1"
    return conn.execute(sql, params).fetchone()


def universe_by_id(conn: sqlite3.Connection, universe_id: str):
    return conn.execute("SELECT * FROM universe_snapshot WHERE id = ?", (universe_id,)).fetchone()


def universe_members(conn: sqlite3.Connection, universe_id: str) -> dict[str, dict]:
    rows = conn.execute("SELECT isin, tr_name, isin_valid, page FROM universe_member WHERE universe_id = ? ORDER BY isin", (universe_id,))
    return {r["isin"]: {"name": r["tr_name"], "valid": bool(r["isin_valid"]), "page": r["page"]} for r in rows}


def insert_universe(conn: sqlite3.Connection, meta: dict, entries, status: str, reason: str, previous_id: str | None, added: int, removed: int) -> None:
    existing = universe_by_id(conn, meta["id"])
    if existing is not None:
        conn.execute(
            "UPDATE universe_snapshot SET retrieved_at = ?, http_last_modified = ?, http_etag = ? WHERE id = ?",
            (meta["retrieved_at"], meta.get("http_last_modified"), meta.get("http_etag"), meta["id"]),
        )
        return
    conn.execute(
        """INSERT INTO universe_snapshot(id, source_url, retrieved_at, http_last_modified, http_etag, pdf_creation_date,
               pdf_mod_date, sha256, parser_version, isin_count, invalid_isins, status, status_reason, previous_id,
               added_count, removed_count, data_mode, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            meta["id"], meta["source_url"], meta["retrieved_at"], meta.get("http_last_modified"), meta.get("http_etag"),
            meta.get("pdf_creation_date"), meta.get("pdf_mod_date"), meta["sha256"], meta["parser_version"],
            len(entries), sum(1 for e in entries if not e.valid), status, reason, previous_id, added, removed,
            meta.get("data_mode", "produktiv"), now_iso(),
        ),
    )
    conn.executemany(
        "INSERT INTO universe_member(universe_id, isin, tr_name, isin_valid, page) VALUES (?, ?, ?, ?, ?)",
        [(meta["id"], e.isin, e.name, int(e.valid), e.page) for e in entries],
    )


def set_universe_status(conn: sqlite3.Connection, universe_id: str, status: str, reason: str) -> None:
    conn.execute("UPDATE universe_snapshot SET status = ?, status_reason = ? WHERE id = ?", (status, reason, universe_id))


def record_universe_changes(conn: sqlite3.Connection, universe_id: str, added, removed, renamed) -> None:
    at = now_iso()
    rows = [(universe_id, i, "neu", None, at) for i in added]
    rows += [(universe_id, i, "entfallen", None, at) for i in removed]
    rows += [(universe_id, i, "name_geaendert", json.dumps({"vorher": a, "nachher": b}, ensure_ascii=False), at) for i, a, b in renamed]
    conn.executemany("INSERT INTO universe_change(universe_id, isin, change, detail, recorded_at) VALUES (?, ?, ?, ?, ?)", rows)


# --------------------------------------------------------- Instrumente

def ensure_instruments(conn: sqlite3.Connection, members: dict[str, dict]) -> None:
    at = now_iso()
    for isin, info in members.items():
        status = "offen" if info["valid"] else "isin_ungueltig"
        conn.execute(
            """INSERT INTO instrument(isin, full_name, identity_status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(isin) DO NOTHING""",
            (isin, info["name"], status, at, at),
        )
        if not info["valid"]:
            conn.execute("UPDATE instrument SET identity_status = 'isin_ungueltig', updated_at = ? WHERE isin = ?", (at, isin))
        add_alias(conn, isin, info["name"], "tr_name", "tr_liste")


def add_alias(conn: sqlite3.Connection, isin: str, alias: str | None, kind: str, source: str) -> None:
    if not alias:
        return
    at = now_iso()
    conn.execute(
        """INSERT INTO instrument_alias(instrument_id, alias, kind, source, first_seen, last_seen)
           SELECT id, ?, ?, ?, ?, ? FROM instrument WHERE isin = ?
           ON CONFLICT(instrument_id, alias, kind) DO UPDATE SET last_seen = excluded.last_seen""",
        (alias.strip(), kind, source, at, at, isin),
    )


def aliases(conn: sqlite3.Connection, isins: Iterable[str]) -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {}
    rows = conn.execute(
        """SELECT i.isin, a.alias, a.kind FROM instrument_alias a JOIN instrument i ON i.id = a.instrument_id
           ORDER BY i.isin, a.first_seen"""
    )
    wanted = set(isins)
    for r in rows:
        if r["isin"] in wanted:
            out.setdefault(r["isin"], []).append((r["alias"], r["kind"]))
    return out


def instruments(conn: sqlite3.Connection, isins: Iterable[str]) -> dict[str, sqlite3.Row]:
    wanted = set(isins)
    return {r["isin"]: r for r in conn.execute("SELECT * FROM instrument") if r["isin"] in wanted}


def identity_due(conn: sqlite3.Connection, isins: Iterable[str], max_age_days: int) -> list[str]:
    """ISINs ohne geprüfte Identität oder mit veralteter Prüfung (älteste zuerst)."""
    rows = instruments(conn, isins)
    due: list[tuple[str, str]] = []
    now = utc_now()
    for isin, row in rows.items():
        if row["identity_status"] == "isin_ungueltig":
            continue
        checked = row["identity_checked_at"]
        if row["identity_status"] == "offen" or not checked:
            due.append(("", isin))
            continue
        from ..util.timeutil import parse_iso_utc

        age = (now - parse_iso_utc(checked)).days
        if age >= max_age_days:
            due.append((checked, isin))
    due.sort()
    return [isin for _, isin in due]


def save_identity(conn: sqlite3.Connection, result: IdentityResult, table: ExchangeTable, provider: str) -> int | None:
    """Speichert Identität und Referenznotierung. Gibt die Listing-ID zurück."""
    at = now_iso()
    row = conn.execute("SELECT id FROM instrument WHERE isin = ?", (result.isin,)).fetchone()
    if row is None:
        raise KeyError(result.isin)
    instrument_id = row[0]
    display = result.names.get("openfigi") or result.names.get("yahoo_search") or result.names.get("demo") or result.names.get("eodhd") or result.names.get("tr")
    conn.execute(
        """UPDATE instrument SET identity_status = ?, identity_reason = ?, identity_checked_at = ?, identity_source = ?,
               instrument_type = ?, warnings = ?, full_name = COALESCE(full_name, ?), updated_at = ? WHERE id = ?""",
        (result.status, result.reason, at, ",".join(sorted({c.source for c in result.candidates})) or None,
         result.instrument_type, result.warnings, display, at, instrument_id),
    )
    for source, name in result.names.items():
        add_alias(conn, result.isin, name, "tr_name" if source == "tr" else "name", source)
    ref = result.reference
    if ref is None or result.status != "verifiziert":
        conn.execute("UPDATE listing SET is_reference = 0, updated_at = ? WHERE instrument_id = ?", (at, instrument_id))
        return None
    exchange = table.exchanges[ref.exchange_key]
    _, factor = unit_info(exchange.currency)
    existing = conn.execute(
        "SELECT id FROM listing WHERE provider = ? AND provider_symbol = ?", (provider, ref.provider_symbol)
    ).fetchone()
    with_ref = conn.execute("SELECT id FROM listing WHERE instrument_id = ? AND is_reference = 1", (instrument_id,)).fetchone()
    if with_ref is not None and (existing is None or with_ref[0] != existing[0]):
        conn.execute("UPDATE listing SET is_reference = 0, updated_at = ? WHERE id = ?", (at, with_ref[0]))
    if existing is None:
        cur = conn.execute(
            """INSERT INTO listing(instrument_id, provider, provider_symbol, ticker, exchange_key, mic, exchange_name, exchange_tz,
                   calendar_code, currency, price_unit, unit_factor, is_reference, selection_reason, figi, composite_figi,
                   share_class_figi, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)""",
            (instrument_id, provider, ref.provider_symbol, ref.ticker, exchange.key, exchange.mic, exchange.name, exchange.tz,
             exchange.calendar, exchange.currency, exchange.currency, factor, result.reason, ref.figi, ref.composite_figi,
             ref.share_class_figi, at, at),
        )
        listing_id = int(cur.lastrowid)
    else:
        listing_id = int(existing[0])
        if existing[0] != (with_ref[0] if with_ref else None):
            conn.execute("UPDATE listing SET is_reference = 1, selection_reason = ?, updated_at = ? WHERE id = ?", (result.reason, at, listing_id))
    add_alias(conn, result.isin, ref.ticker, "ticker", ref.source)
    add_alias(conn, result.isin, ref.provider_symbol, "symbol", provider)
    return listing_id


def mark_identity_unclear(conn: sqlite3.Connection, isin: str, reason: str) -> None:
    at = now_iso()
    conn.execute(
        "UPDATE instrument SET identity_status = 'unklar', identity_reason = ?, identity_checked_at = ?, updated_at = ? WHERE isin = ?",
        (reason, at, at, isin),
    )
    conn.execute(
        "UPDATE listing SET is_reference = 0, updated_at = ? WHERE instrument_id = (SELECT id FROM instrument WHERE isin = ?)",
        (at, isin),
    )


def reference_listings(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        """SELECT i.isin, l.* FROM listing l JOIN instrument i ON i.id = l.instrument_id WHERE l.is_reference = 1"""
    )
    return {r["isin"]: r for r in rows}


def update_listing_fetch(conn: sqlite3.Connection, listing_id: int, *, status: str, error: str | None = None, full: bool = False, meta: PriceHistory | None = None) -> None:
    at = now_iso()
    conn.execute(
        "UPDATE listing SET last_fetch_at = ?, last_fetch_status = ?, last_error = ?, updated_at = ? WHERE id = ?",
        (at, status, error, at, listing_id),
    )
    if full:
        conn.execute("UPDATE listing SET last_full_fetch_at = ? WHERE id = ?", (at, listing_id))
    if meta is not None:
        conn.execute(
            """UPDATE listing SET provider_name = COALESCE(?, provider_name), provider_exchange = COALESCE(?, provider_exchange),
                   provider_type = COALESCE(?, provider_type), price_unit = COALESCE(?, price_unit),
                   unit_factor = COALESCE(?, unit_factor) WHERE id = ?""",
            (meta.long_name or meta.short_name, meta.exchange_name, meta.instrument_type, meta.price_unit, meta.unit_factor, listing_id),
        )


def set_listing_hold(conn: sqlite3.Connection, listing_id: int, hold: bool, reason: str | None) -> None:
    conn.execute("UPDATE listing SET hold_all = ?, hold_reason = ?, updated_at = ? WHERE id = ?", (int(hold), reason, now_iso(), listing_id))


# --------------------------------------------------------------- Kurse

def bar_range(conn: sqlite3.Connection, listing_id: int, revision: int) -> tuple[int | None, int | None, int]:
    row = conn.execute(
        "SELECT MIN(session_day), MAX(session_day), COUNT(*) FROM daily_bar WHERE listing_id = ? AND revision = ?",
        (listing_id, revision),
    ).fetchone()
    return row[0], row[1], int(row[2])


def _nan_to_none(value: float) -> float | None:
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else float(value)


def store_bars(conn: sqlite3.Connection, listing_id: int, revision: int, history: PriceHistory) -> int:
    at = iso_utc(history.fetched_at) if history.fetched_at else now_iso()
    rows = []
    for k in range(len(history.days)):
        rows.append(
            (
                listing_id,
                int(history.days[k]),
                revision,
                _nan_to_none(history.open[k]),
                _nan_to_none(history.high[k]),
                _nan_to_none(history.low[k]),
                float(history.close[k]),
                _nan_to_none(history.close_raw[k]) if history.close_raw is not None else None,
                _nan_to_none(history.close_total[k]) if history.close_total is not None else None,
                _nan_to_none(history.volume[k]),
                history.bar_times_utc[k] if k < len(history.bar_times_utc) else None,
                at,
            )
        )
    conn.executemany(
        """INSERT INTO daily_bar(listing_id, session_day, revision, open, high, low, close_split, close_raw, close_total,
               volume, bar_time_utc, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(listing_id, revision, session_day) DO UPDATE SET
               open = excluded.open, high = excluded.high, low = excluded.low, close_split = excluded.close_split,
               close_raw = excluded.close_raw, close_total = excluded.close_total, volume = excluded.volume,
               bar_time_utc = excluded.bar_time_utc, fetched_at = excluded.fetched_at""",
        rows,
    )
    return len(rows)


def load_bars(conn: sqlite3.Connection, listing_id: int, revision: int, from_day: int | None = None) -> dict[str, np.ndarray]:
    sql = "SELECT session_day, open, high, low, close_split, close_raw, volume FROM daily_bar WHERE listing_id = ? AND revision = ?"
    params: list = [listing_id, revision]
    if from_day is not None:
        sql += " AND session_day >= ?"
        params.append(from_day)
    sql += " ORDER BY session_day"
    rows = conn.execute(sql, params).fetchall()

    def column(k: int) -> np.ndarray:
        return np.array([np.nan if r[k] is None else r[k] for r in rows], dtype=np.float64)

    return {
        "days": np.array([r[0] for r in rows], dtype=np.int64),
        "open": column(1),
        "high": column(2),
        "low": column(3),
        "close": column(4),
        "close_raw": column(5),
        "volume": column(6),
    }


def new_revision(conn: sqlite3.Connection, listing_id: int, reason: str) -> int:
    row = conn.execute("SELECT data_revision FROM listing WHERE id = ?", (listing_id,)).fetchone()
    revision = int(row[0]) + 1
    conn.execute("UPDATE listing SET data_revision = ?, updated_at = ? WHERE id = ?", (revision, now_iso(), listing_id))
    conn.execute(
        "INSERT INTO bar_revision(listing_id, revision, created_at, reason, bars) VALUES (?, ?, ?, ?, 0)",
        (listing_id, revision, now_iso(), reason),
    )
    return revision


def finalize_revision(conn: sqlite3.Connection, listing_id: int, revision: int) -> None:
    count = conn.execute("SELECT COUNT(*) FROM daily_bar WHERE listing_id = ? AND revision = ?", (listing_id, revision)).fetchone()[0]
    conn.execute("UPDATE bar_revision SET bars = ? WHERE listing_id = ? AND revision = ?", (count, listing_id, revision))


def prune_old_revisions(conn: sqlite3.Connection, listing_id: int, keep_revision: int) -> None:
    conn.execute("DELETE FROM daily_bar WHERE listing_id = ? AND revision < ?", (listing_id, keep_revision))


def prune_old_bars(conn: sqlite3.Connection, before_day: int) -> int:
    cur = conn.execute("DELETE FROM daily_bar WHERE session_day < ?", (before_day,))
    return cur.rowcount


# ------------------------------------------------- Kapitalmaßnahmen

def store_corporate_actions(conn: sqlite3.Connection, listing_id: int, history: PriceHistory) -> list[SplitEvent]:
    """Speichert Splits/Dividenden; gibt bisher unbekannte Splits zurück."""
    at = now_iso()
    new_splits: list[SplitEvent] = []
    for event in history.splits:
        cur = conn.execute(
            """INSERT INTO corporate_action(listing_id, kind, ex_day, factor, source, first_seen)
               VALUES (?, 'split', ?, ?, ?, ?) ON CONFLICT(listing_id, kind, ex_day) DO NOTHING""",
            (listing_id, event.day, event.factor, history.provider, at),
        )
        if cur.rowcount:
            new_splits.append(event)
    for day, amount in history.dividends:
        conn.execute(
            """INSERT INTO corporate_action(listing_id, kind, ex_day, amount, source, first_seen)
               VALUES (?, 'dividende', ?, ?, ?, ?) ON CONFLICT(listing_id, kind, ex_day) DO NOTHING""",
            (listing_id, day, amount, history.provider, at),
        )
    return new_splits


def splits_for(conn: sqlite3.Connection, listing_id: int) -> list[SplitEvent]:
    rows = conn.execute(
        "SELECT ex_day, factor FROM corporate_action WHERE listing_id = ? AND kind = 'split' AND factor IS NOT NULL ORDER BY ex_day",
        (listing_id,),
    )
    return [SplitEvent(int(r[0]), float(r[1])) for r in rows]


# ------------------------------------------------ Prüfentscheidungen

def sync_review_decisions(conn: sqlite3.Connection, decisions: list[dict]) -> None:
    from ..util.timeutil import iso_to_day

    for item in decisions or []:
        day = item["datum"] if isinstance(item["datum"], int) else iso_to_day(str(item["datum"]))
        conn.execute(
            """INSERT INTO review_decision(isin, day, decision, source, note, decided_at) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(isin, day) DO UPDATE SET decision = excluded.decision, source = excluded.source, note = excluded.note""",
            (item["isin"], day, item["entscheidung"], item.get("quelle"), item.get("notiz"), str(item.get("entschieden_am") or now_iso())),
        )


def review_map(conn: sqlite3.Connection) -> dict[str, dict[int, str]]:
    out: dict[str, dict[int, str]] = {}
    for r in conn.execute("SELECT isin, day, decision FROM review_decision"):
        out.setdefault(r[0], {})[int(r[1])] = r[2]
    return out


# ------------------------------------------------------------- Läufe

def create_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    trigger: str,
    planned_start: str | None,
    attempt: int,
    versions: dict,
    data_mode: str,
    started_at: str | None = None,
) -> None:
    started = started_at or now_iso()
    conn.execute(
        """INSERT INTO run(id, trigger, planned_start, started_at, status, attempt, method_version, metrics_version,
               ranking_version, frequency_version, software_version, heartbeat_at, data_mode)
           VALUES (?, ?, ?, ?, 'laeuft', ?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, trigger, planned_start, started, attempt, versions["method"], versions["metrics"], versions["ranking"],
         versions["frequency"], versions["software"], started, data_mode),
    )


def update_run(conn: sqlite3.Connection, run_id: str, **fields) -> None:
    allowed = {
        "status", "status_detail", "finished_at", "cutoff_day", "universe_id", "data_revision", "checkpoint", "error_count",
        "requests", "throttled", "heartbeat_at", "snapshot_id",
    }
    keys = [k for k in fields if k in allowed]
    if not keys:
        return
    assignments = ", ".join(f"{k} = ?" for k in keys)
    conn.execute(f"UPDATE run SET {assignments} WHERE id = ?", [fields[k] for k in keys] + [run_id])  # noqa: S608 - Spaltennamen aus Whitelist


def log_event(conn: sqlite3.Connection, run_id: str, step: str, message: str, level: str = "INFO") -> None:
    conn.execute("INSERT INTO run_event(run_id, at, level, step, message) VALUES (?, ?, ?, ?, ?)", (run_id, now_iso(), level, step, message))


def acquire_lock(conn: sqlite3.Connection, name: str, run_id: str, stale_after_minutes: int = 120) -> tuple[bool, str | None]:
    from ..util.timeutil import parse_iso_utc

    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT run_id, heartbeat_at FROM run_lock WHERE name = ?", (name,)).fetchone()
        if row is not None:
            age = (utc_now() - parse_iso_utc(row["heartbeat_at"])).total_seconds() / 60
            if age < stale_after_minutes and row["run_id"] != run_id:
                conn.execute("ROLLBACK")
                return False, row["run_id"]
            conn.execute(
                "UPDATE run SET status = 'abgebrochen', status_detail = 'Sperre verwaist – Lauf ohne Abschluss', finished_at = ? WHERE id = ? AND status = 'laeuft'",
                (now_iso(), row["run_id"]),
            )
        conn.execute(
            "INSERT INTO run_lock(name, run_id, acquired_at, heartbeat_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET run_id = excluded.run_id, acquired_at = excluded.acquired_at, heartbeat_at = excluded.heartbeat_at",
            (name, run_id, now_iso(), now_iso()),
        )
        conn.execute("COMMIT")
        return True, None
    except Exception:
        conn.execute("ROLLBACK")
        raise


def heartbeat(conn: sqlite3.Connection, name: str, run_id: str) -> None:
    at = now_iso()
    conn.execute("UPDATE run_lock SET heartbeat_at = ? WHERE name = ? AND run_id = ?", (at, name, run_id))
    conn.execute("UPDATE run SET heartbeat_at = ? WHERE id = ?", (at, run_id))


def release_lock(conn: sqlite3.Connection, name: str, run_id: str) -> None:
    conn.execute("DELETE FROM run_lock WHERE name = ? AND run_id = ?", (name, run_id))


def clear_orphaned_locks(conn: sqlite3.Connection, reason: str) -> list[str]:
    """Gibt Sperren frei, deren Lauf nachweislich nicht mehr läuft (z. B. aus einer
    wiederhergestellten Sicherung, wenn GitHub-Concurrency bereits Exklusivität garantiert).
    Der betroffene Lauf wird als abgebrochen protokolliert, nie als erfolgreich."""
    rows = conn.execute("SELECT name, run_id FROM run_lock").fetchall()
    for row in rows:
        conn.execute(
            "UPDATE run SET status = 'abgebrochen', status_detail = ?, finished_at = ? WHERE id = ? AND status NOT IN ('veroeffentlicht', 'keine_neuen_daten', 'fehlgeschlagen', 'abgebrochen')",
            (reason, now_iso(), row["run_id"]),
        )
        conn.execute("DELETE FROM run_lock WHERE name = ?", (row["name"],))
    conn.commit()
    return [row["run_id"] for row in rows]


def attempts_for_cutoff(conn: sqlite3.Connection, cutoff_day: int, data_mode: str, trigger: str | None = None) -> int:
    """Bisherige Läufe für einen Stichtag (optional nur mit einem bestimmten Auslöser)."""
    if trigger is None:
        query, params = "SELECT COUNT(*) FROM run WHERE cutoff_day = ? AND data_mode = ?", (cutoff_day, data_mode)
    else:
        query, params = "SELECT COUNT(*) FROM run WHERE cutoff_day = ? AND data_mode = ? AND trigger = ?", (cutoff_day, data_mode, trigger)
    return int(conn.execute(query, params).fetchone()[0])


def mark_fetched(conn: sqlite3.Connection, target_key: str, listing_id: int, status: str) -> None:
    conn.execute(
        """INSERT INTO fetch_checkpoint(target_key, listing_id, status, at) VALUES (?, ?, ?, ?)
           ON CONFLICT(target_key, listing_id) DO UPDATE SET status = excluded.status, at = excluded.at""",
        (target_key, listing_id, status, now_iso()),
    )


def fetched(conn: sqlite3.Connection, target_key: str) -> dict[int, str]:
    return {int(r[0]): r[1] for r in conn.execute("SELECT listing_id, status FROM fetch_checkpoint WHERE target_key = ?", (target_key,))}


def clear_old_checkpoints(conn: sqlite3.Connection, keep_key: str) -> None:
    conn.execute("DELETE FROM fetch_checkpoint WHERE target_key != ?", (keep_key,))


# ---------------------------------------------------------- Snapshots

def snapshot_by_key(conn: sqlite3.Connection, key: str):
    return conn.execute("SELECT * FROM snapshot_manifest WHERE idempotency_key = ?", (key,)).fetchone()


def insert_snapshot(conn: sqlite3.Connection, **fields) -> None:
    columns = [
        "id", "idempotency_key", "cutoff_day", "computed_at", "published_at", "completeness", "data_mode", "universe_id",
        "run_id", "supersedes", "summary_json", "site_archive", "evidence_archive", "status",
    ]
    conn.execute(
        f"INSERT INTO snapshot_manifest({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",  # noqa: S608
        [fields.get(c) for c in columns],
    )


def published_snapshots(conn: sqlite3.Connection, data_mode: str | None = None, limit: int = 1000) -> list[sqlite3.Row]:
    sql = "SELECT * FROM snapshot_manifest WHERE status = 'veroeffentlicht'"
    params: list = []
    if data_mode:
        sql += " AND data_mode = ?"
        params.append(data_mode)
    sql += " ORDER BY cutoff_day DESC, published_at DESC LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def latest_for_cutoff(conn: sqlite3.Connection, cutoff_day: int, data_mode: str):
    return conn.execute(
        "SELECT * FROM snapshot_manifest WHERE cutoff_day = ? AND data_mode = ? AND status = 'veroeffentlicht' ORDER BY published_at DESC LIMIT 1",
        (cutoff_day, data_mode),
    ).fetchone()


def candidate_from_json(text: str) -> ListingCandidate:
    return ListingCandidate(**json.loads(text))


# ---------------------------------------------------------------- Wechselkurse


def store_fx_rates(conn: sqlite3.Connection, rows: list[tuple[int, str, float]], *, source: str, fetched_at: str) -> int:
    """Speichert Referenzkurse je EUR; ein Eintrag je Tag und Währung (neuere Abrufe überschreiben)."""
    conn.executemany(
        "INSERT INTO fx_rate(day, currency, per_eur, source, fetched_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(day, currency) DO UPDATE SET per_eur = excluded.per_eur, source = excluded.source, fetched_at = excluded.fetched_at",
        [(int(day), currency, float(rate), source, fetched_at) for day, currency, rate in rows],
    )
    return len(rows)


def fx_rates_since(conn: sqlite3.Connection, first_day: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT day, currency, per_eur, source, fetched_at FROM fx_rate WHERE day >= ? ORDER BY day, currency", (int(first_day),)
    ).fetchall()


def prune_fx_rates(conn: sqlite3.Connection, keep_from_day: int) -> None:
    conn.execute("DELETE FROM fx_rate WHERE day < ?", (int(keep_from_day),))


# ---------------------------------------------------------- Zweiter Börsenplatz


def venue_listings(conn: sqlite3.Connection, isins: Iterable[str]) -> dict[str, sqlite3.Row]:
    """Gespeicherte Wahl des zweiten Börsenplatzes je ISIN (nur angefragte ISINs)."""
    wanted = list(isins)
    out: dict[str, sqlite3.Row] = {}
    for start in range(0, len(wanted), 500):
        chunk = wanted[start : start + 500]
        marks = ",".join("?" for _ in chunk)
        for row in conn.execute(f"SELECT * FROM venue_listing WHERE isin IN ({marks})", chunk):
            out[row["isin"]] = row
    return out


def save_venue_listing(conn: sqlite3.Connection, isin: str, *, symbol: str | None, exchange_key: str | None, source: str | None) -> None:
    status = "gefunden" if symbol and exchange_key else "kein_vergleichsplatz"
    conn.execute(
        "INSERT INTO venue_listing(isin, status, provider_symbol, exchange_key, source, checked_at) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(isin) DO UPDATE SET status = excluded.status, provider_symbol = excluded.provider_symbol, "
        "exchange_key = excluded.exchange_key, source = excluded.source, checked_at = excluded.checked_at",
        (isin, status, symbol, exchange_key, source, now_iso()),
    )


# ---------------------------------------------------------- Wochenwerte (Umschichtungs-Regel)


def ensure_long_history(conn: sqlite3.Connection, listing_ids: Iterable[int]) -> int:
    """Nimmt Notierungen in die Langhistorie auf (Status „offen“); gibt die Zahl neuer Einträge zurück."""
    at = now_iso()
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO long_history(listing_id, status, added_at) VALUES (?, 'offen', ?)",
        [(int(listing_id), at) for listing_id in listing_ids],
    )
    return conn.total_changes - before


def long_history_rows(conn: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    return {int(r["listing_id"]): r for r in conn.execute("SELECT * FROM long_history")}


def long_history_due(conn: sqlite3.Connection, limit: int) -> list[int]:
    rows = conn.execute(
        # zuerst „erneut“ (nach einem Split sind die älteren Wochenkurse bis zum Neuladen unbereinigt)
        "SELECT listing_id FROM long_history WHERE status IN ('offen', 'erneut') "
        "ORDER BY CASE status WHEN 'erneut' THEN 0 ELSE 1 END, added_at, listing_id LIMIT ?",
        (int(limit),),
    )
    return [int(r[0]) for r in rows]


def set_long_history(conn: sqlite3.Connection, listing_id: int, status: str, *, first_week: int | None = None, error: str | None = None) -> None:
    conn.execute(
        "UPDATE long_history SET status = ?, first_week = COALESCE(?, first_week), fetched_at = ?, last_error = ? WHERE listing_id = ?",
        (status, first_week, now_iso(), error, int(listing_id)),
    )


def mark_long_history_refresh(conn: sqlite3.Connection, listing_id: int) -> None:
    """Nach einem neuen Split: Langhistorie neu laden (ältere Wochenkurse wären sonst unbereinigt)."""
    conn.execute("UPDATE long_history SET status = 'erneut' WHERE listing_id = ? AND status = 'ok'", (int(listing_id),))


def store_week_bars(conn: sqlite3.Connection, listing_id: int, agg, *, only_before: int | None = None) -> int:
    """Speichert Wochenwerte (``analytics.weekly.WeekAggregates``); Wochen ohne Kurs und ohne Sitzung entfallen."""
    rows = []
    for k, week_end in enumerate(agg.week_ends.tolist()):
        if only_before is not None and week_end >= only_before:
            continue
        close = float(agg.close[k])
        if not math.isfinite(close) and int(agg.sessions[k]) == 0:
            continue
        first_close = float(agg.first_close[k])
        first_day = int(agg.first_day[k])
        rows.append(
            (
                int(listing_id),
                int(week_end),
                close if math.isfinite(close) else None,
                float(agg.turnover[k]),
                int(agg.with_data[k]),
                int(agg.positive[k]),
                int(agg.observed[k]),
                int(agg.sessions[k]),
                float(agg.jump[k]),
                first_close if math.isfinite(first_close) else None,
                first_day if first_day >= 0 else None,
            )
        )
    conn.executemany(
        "INSERT INTO week_bar(listing_id, week_end, close, turnover, with_data, positive, observed, sessions, jump, first_close, first_day) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(listing_id, week_end) DO UPDATE SET close = excluded.close, turnover = excluded.turnover, with_data = excluded.with_data, "
        "positive = excluded.positive, observed = excluded.observed, sessions = excluded.sessions, jump = excluded.jump, "
        "first_close = excluded.first_close, first_day = excluded.first_day",
        rows,
    )
    return len(rows)


def week_bars_since(conn: sqlite3.Connection, listing_ids: list[int], first_week: int) -> dict[int, list[sqlite3.Row]]:
    out: dict[int, list[sqlite3.Row]] = {}
    for start in range(0, len(listing_ids), 500):
        chunk = listing_ids[start : start + 500]
        marks = ",".join("?" for _ in chunk)
        for row in conn.execute(
            f"SELECT * FROM week_bar WHERE listing_id IN ({marks}) AND week_end >= ? ORDER BY listing_id, week_end", (*chunk, int(first_week))
        ):
            out.setdefault(int(row["listing_id"]), []).append(row)
    return out


def prune_week_bars(conn: sqlite3.Connection, keep_from_week: int) -> None:
    conn.execute("DELETE FROM week_bar WHERE week_end < ?", (int(keep_from_week),))
