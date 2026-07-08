"""SQLite storage for the NetCoin production-style explorer indexer."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any


class IndexerStorage:
    """Small normalized SQLite store for explorer/indexer data.

    The indexer is intentionally derived state: it can always be rebuilt from a
    trusted chain database.  That makes reorg handling and corruption recovery
    simpler than treating explorer rows as consensus data.
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS indexer_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("""CREATE TABLE IF NOT EXISTS blocks(
                    height INTEGER PRIMARY KEY,
                    block_hash TEXT UNIQUE NOT NULL,
                    previous_hash TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    tx_count INTEGER NOT NULL,
                    weight INTEGER NOT NULL
                )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS transactions(
                    txid TEXT PRIMARY KEY,
                    block_hash TEXT,
                    height INTEGER,
                    position INTEGER,
                    timestamp INTEGER,
                    input_sats INTEGER NOT NULL DEFAULT 0,
                    output_sats INTEGER NOT NULL DEFAULT 0,
                    fee_sats INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL,
                    mempool INTEGER NOT NULL DEFAULT 0
                )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS address_events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    txid TEXT NOT NULL,
                    block_hash TEXT,
                    height INTEGER,
                    vout INTEGER,
                    direction TEXT NOT NULL,
                    amount_sats INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    coinbase INTEGER NOT NULL DEFAULT 0,
                    spent_outpoint TEXT DEFAULT ''
                )""")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_address_events_addr_height ON address_events(address, height, txid)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_address_events_txid ON address_events(txid)")
            conn.execute("""CREATE TABLE IF NOT EXISTS market_events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    txid TEXT DEFAULT '',
                    height INTEGER,
                    timestamp INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS token_events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    account TEXT DEFAULT '',
                    amount_units INTEGER NOT NULL DEFAULT 0,
                    height INTEGER,
                    timestamp INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )""")
            conn.execute(
                "INSERT OR REPLACE INTO indexer_meta(key,value) VALUES('schema_version', ?)",
                (str(self.SCHEMA_VERSION),),
            )
            conn.commit()

    def reset(self) -> None:
        with self.connect() as conn:
            for table in ("blocks", "transactions", "address_events", "market_events", "token_events"):
                conn.execute(f"DELETE FROM {table}")
            conn.execute("INSERT OR REPLACE INTO indexer_meta(key,value) VALUES('tip_height','-1')")
            conn.execute("INSERT OR REPLACE INTO indexer_meta(key,value) VALUES('tip_hash','')")
            conn.commit()

    def set_meta(self, key: str, value: Any) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO indexer_meta(key,value) VALUES(?,?)", (key, json.dumps(value, sort_keys=True))
            )
            conn.commit()

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM indexer_meta WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    def rollback_to_height(self, height: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM blocks WHERE height > ?", (height,))
            conn.execute("DELETE FROM transactions WHERE height > ? AND mempool=0", (height,))
            conn.execute("DELETE FROM address_events WHERE height > ?", (height,))
            conn.execute("DELETE FROM market_events WHERE height > ?", (height,))
            conn.execute("DELETE FROM token_events WHERE height > ?", (height,))
            tip = conn.execute("SELECT height, block_hash FROM blocks ORDER BY height DESC LIMIT 1").fetchone()
            conn.execute(
                "INSERT OR REPLACE INTO indexer_meta(key,value) VALUES('tip_height',?)",
                (json.dumps(int(tip["height"])) if tip else "-1",),
            )
            conn.execute(
                "INSERT OR REPLACE INTO indexer_meta(key,value) VALUES('tip_hash',?)",
                (json.dumps(str(tip["block_hash"])) if tip else '""',),
            )
            conn.commit()

    def rows(self, sql: str, args: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, tuple(args)).fetchall()]
