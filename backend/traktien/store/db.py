"""SQLite-Verbindung und Migrationen.

Begründung SQLite statt PostgreSQL (siehe docs/10_Architektur.md): ein einziger
schreibender Tageslauf, kein gleichzeitiger Mehrbenutzerzugriff, Zustand als eine
Datei, die zwischen Läufen gesichert und wiederhergestellt wird. Kennzahlen und
Ranglisten (rund eine Million Fenster × elf Gewichte je Snapshot) werden nicht als
redundante SQL-Zeilen gespeichert, sondern als kompakte, unveränderliche Snapshot-
Dateien mit Prüfnachweis.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from ..util.timeutil import iso_utc, utc_now

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_NAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> list[int]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    done: list[int] = []
    for file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = _NAME.match(file.name)
        if not match:
            continue
        version = int(match.group(1))
        if version in applied:
            continue
        sql = file.read_text(encoding="utf-8")
        conn.execute("BEGIN")
        try:
            for statement in _split_sql(sql):
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, match.group(2), iso_utc(utc_now())),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        done.append(version)
    return done


def _split_sql(sql: str) -> list[str]:
    statements, current = [], []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current))
            current = []
    if current:
        statements.append("\n".join(current))
    return statements


class Transaction:
    """Kontextmanager für eine explizite Transaktion."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def __enter__(self) -> sqlite3.Connection:
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.conn.execute("COMMIT")
        else:
            self.conn.execute("ROLLBACK")


def backup_to(conn: sqlite3.Connection, target: Path | str) -> None:
    """Konsistente Sicherung (Online-Backup-API), auch während WAL aktiv ist."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    dest = sqlite3.connect(str(target))
    try:
        conn.backup(dest)
        dest.execute("PRAGMA journal_mode = DELETE")
    finally:
        dest.close()


def integrity_ok(path: Path | str) -> bool:
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()
