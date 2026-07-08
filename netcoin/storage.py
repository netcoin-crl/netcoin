"""Optional SQLite storage backend for the NetCoin chain and mempool.

SQLite is the default backend. JSON files remain available for demos/export with
Blockchain(backend="json") or NETCOIN_BACKEND=json. Blocks, the active-chain
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
import time
from pathlib import Path
from threading import RLock
from typing import Any

from .storage_migrations import run_migrations, schema_report

SCHEMA_VERSION = "2"


class SqliteChainStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.conn = sqlite3.connect(str(self.path), timeout=30.0, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        run_migrations(self.conn)

    # -- chain --------------------------------------------------------------

    def has_chain(self) -> bool:
        return self.conn.execute("SELECT COUNT(*) FROM active_chain").fetchone()[0] > 0

    def save_chain(self, blocks: list[Any]) -> None:
        """Persist all blocks and the active-chain ordering atomically."""
        cur = self.conn.cursor()
        cur.executemany(
            "INSERT OR REPLACE INTO blocks(hash, height, prev_hash, data) VALUES(?,?,?,?)",
            [(b.hash(), b.header.height, b.header.previous_hash, json.dumps(b.to_dict())) for b in blocks],
        )
        cur.execute("DELETE FROM active_chain")
        cur.executemany(
            "INSERT INTO active_chain(position, hash) VALUES(?,?)",
            [(position, b.hash()) for position, b in enumerate(blocks)],
        )
        self.conn.commit()

    def load_chain(self) -> list[dict[str, Any]]:
        # Skip pruned blocks (NULL body); only full block bodies are returned.
        rows = self.conn.execute(
            "SELECT b.data FROM active_chain a JOIN blocks b ON a.hash = b.hash "
            "WHERE b.data IS NOT NULL ORDER BY a.position"
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    # -- meta / snapshot / pruning -----------------------------------------

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?,?)", (key, str(value)))
        self.conn.commit()

    def get_meta(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def save_utxo_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.conn.execute("INSERT OR REPLACE INTO utxo_snapshot(id, data) VALUES(1, ?)", (json.dumps(snapshot),))
        self.conn.commit()

    def load_utxo_snapshot(self) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT data FROM utxo_snapshot WHERE id=1").fetchone()
        return json.loads(row[0]) if row else None

    def pruned_below(self) -> int:
        return int(self.get_meta("pruned_below_height", "0"))

    def is_pruned(self) -> bool:
        return self.pruned_below() > 0

    def prune_bodies(self, below_height: int) -> int:
        """Drop block bodies (data) for blocks below below_height; keep headers."""
        cur = self.conn.execute("UPDATE blocks SET data = NULL WHERE height < ? AND data IS NOT NULL", (below_height,))
        self.conn.commit()
        self.set_meta("pruned_below_height", str(below_height))
        return cur.rowcount

    # -- mempool ------------------------------------------------------------

    def save_mempool(self, transactions: list[Any]) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM mempool")
        cur.executemany(
            "INSERT OR REPLACE INTO mempool(txid, data) VALUES(?,?)",
            [(tx.txid(), json.dumps(tx.to_dict(include_scripts=True, include_witness=True))) for tx in transactions],
        )
        self.conn.commit()

    def load_mempool(self) -> list[dict[str, Any]]:
        return [json.loads(row[0]) for row in self.conn.execute("SELECT data FROM mempool").fetchall()]

    def schema_report(self) -> dict[str, Any]:
        return schema_report(self.conn)

    def audit(self, event: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO chain_audit_log(event, payload, created_at) VALUES(?, ?, ?)",
            (str(event), json.dumps(payload, sort_keys=True), int(time.time())),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
