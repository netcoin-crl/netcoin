"""Optional SQLite storage backend for the NetCoin chain and mempool.

JSON files remain the default backend. When the SQLite backend is selected
(Blockchain(backend="sqlite") or NETCOIN_BACKEND=sqlite), blocks, the active-chain
ordering, and the mempool are stored in a single SQLite database instead of
chain.json / mempool.json. The in-memory chain logic is unchanged; only persistence
is routed through this store.

Schema:
  blocks(hash, height, prev_hash, data)   -- every known block (JSON in `data`)
  active_chain(position, hash)            -- ordered hashes of the active chain
  mempool(txid, data)                     -- current mempool transactions (JSON)
  meta(key, value)                        -- schema_version and misc metadata
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

SCHEMA_VERSION = "1"


class SqliteChainStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS blocks(
                hash TEXT PRIMARY KEY, height INTEGER, prev_hash TEXT, data TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_blocks_height ON blocks(height);
            CREATE TABLE IF NOT EXISTS active_chain(position INTEGER PRIMARY KEY, hash TEXT);
            CREATE TABLE IF NOT EXISTS mempool(txid TEXT PRIMARY KEY, data TEXT);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            """
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)", (SCHEMA_VERSION,)
        )
        self.conn.commit()

    # -- chain --------------------------------------------------------------

    def has_chain(self) -> bool:
        return self.conn.execute("SELECT COUNT(*) FROM active_chain").fetchone()[0] > 0

    def save_chain(self, blocks: List[Any]) -> None:
        """Persist all blocks and the active-chain ordering atomically."""
        cur = self.conn.cursor()
        cur.executemany(
            "INSERT OR REPLACE INTO blocks(hash, height, prev_hash, data) VALUES(?,?,?,?)",
            [
                (b.hash(), b.header.height, b.header.previous_hash, json.dumps(b.to_dict()))
                for b in blocks
            ],
        )
        cur.execute("DELETE FROM active_chain")
        cur.executemany(
            "INSERT INTO active_chain(position, hash) VALUES(?,?)",
            [(position, b.hash()) for position, b in enumerate(blocks)],
        )
        self.conn.commit()

    def load_chain(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT b.data FROM active_chain a JOIN blocks b ON a.hash = b.hash ORDER BY a.position"
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    # -- mempool ------------------------------------------------------------

    def save_mempool(self, transactions: List[Any]) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM mempool")
        cur.executemany(
            "INSERT OR REPLACE INTO mempool(txid, data) VALUES(?,?)",
            [
                (tx.txid(), json.dumps(tx.to_dict(include_scripts=True, include_witness=True)))
                for tx in transactions
            ],
        )
        self.conn.commit()

    def load_mempool(self) -> List[Dict[str, Any]]:
        return [json.loads(row[0]) for row in self.conn.execute("SELECT data FROM mempool").fetchall()]

    def close(self) -> None:
        self.conn.close()
