"""Versioned SQLite schema migrations for chain and app-layer stores."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _v1_chain_core(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS blocks(hash TEXT PRIMARY KEY, height INTEGER, prev_hash TEXT, data TEXT);
        CREATE INDEX IF NOT EXISTS idx_blocks_height ON blocks(height);
        CREATE TABLE IF NOT EXISTS active_chain(position INTEGER PRIMARY KEY, hash TEXT);
        CREATE TABLE IF NOT EXISTS mempool(txid TEXT PRIMARY KEY, data TEXT);
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS utxo_snapshot(id INTEGER PRIMARY KEY CHECK(id=1), data TEXT);
        """)


def _v2_indexes_and_audit(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tx_index(txid TEXT PRIMARY KEY, block_hash TEXT, height INTEGER, position INTEGER);
        CREATE INDEX IF NOT EXISTS idx_tx_index_height ON tx_index(height);
        CREATE TABLE IF NOT EXISTS address_index(address TEXT, txid TEXT, PRIMARY KEY(address, txid));
        CREATE TABLE IF NOT EXISTS chain_audit_log(
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        );
        """)


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "chain core tables", _v1_chain_core),
    Migration(2, "indexes and audit log", _v2_indexes_and_audit),
)


def ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations(
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        )
        """)


def applied_versions(conn: sqlite3.Connection) -> set[int]:
    ensure_migration_table(conn)
    return {int(row[0]) for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}


def run_migrations(conn: sqlite3.Connection) -> list[dict[str, object]]:
    ensure_migration_table(conn)
    done = applied_versions(conn)
    applied: list[dict[str, object]] = []
    for migration in MIGRATIONS:
        if migration.version in done:
            continue
        migration.apply(conn)
        conn.execute(
            "INSERT OR REPLACE INTO schema_migrations(version, name) VALUES(?, ?)",
            (migration.version, migration.name),
        )
        applied.append({"version": migration.version, "name": migration.name})
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
        (str(max(m.version for m in MIGRATIONS)),),
    )
    conn.commit()
    return applied


def schema_report(conn: sqlite3.Connection) -> dict[str, object]:
    ensure_migration_table(conn)
    rows = conn.execute("SELECT version, name, applied_at FROM schema_migrations ORDER BY version").fetchall()
    tables = [
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    ]
    return {
        "schema_version": max([0] + [int(row[0]) for row in rows]),
        "migrations": [{"version": int(v), "name": str(n), "applied_at": int(t)} for v, n, t in rows],
        "tables": tables,
    }
