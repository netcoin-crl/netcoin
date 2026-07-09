"""SQLite-backed indexer integration layer used by v0.34 release gates.

The live Python indexer remains the reference implementation. This module adds a
small, real SQLite persistence boundary for address summaries, market events,
active-chain block state, reorg rollback, and deterministic snapshot hashes.

v0.37.1 hardens the boundary so block replay is idempotent and competing blocks
at the same height do not both contribute to address or market summaries.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 2


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


class IndexerDB:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        self.conn.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS blocks (
              height INTEGER NOT NULL,
              hash TEXT PRIMARY KEY,
              prev_hash TEXT NOT NULL,
              chainwork INTEGER NOT NULL DEFAULT 0,
              active INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_blocks_height ON blocks(height);
            CREATE INDEX IF NOT EXISTS idx_blocks_active_height ON blocks(active, height);
            CREATE TABLE IF NOT EXISTS txs (
              txid TEXT PRIMARY KEY,
              block_hash TEXT NOT NULL,
              height INTEGER NOT NULL,
              raw_json TEXT NOT NULL,
              FOREIGN KEY(block_hash) REFERENCES blocks(hash) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_txs_height ON txs(height);
            CREATE INDEX IF NOT EXISTS idx_txs_block_hash ON txs(block_hash);
            CREATE TABLE IF NOT EXISTS address_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              address TEXT NOT NULL,
              txid TEXT NOT NULL,
              amount_sats INTEGER NOT NULL,
              direction TEXT NOT NULL CHECK(direction IN ('receive','send')),
              height INTEGER NOT NULL,
              FOREIGN KEY(txid) REFERENCES txs(txid) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_address_events_address ON address_events(address, height);
            CREATE TABLE IF NOT EXISTS market_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              block_hash TEXT NOT NULL,
              event_key TEXT NOT NULL,
              market_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              notional_sats INTEGER NOT NULL DEFAULT 0,
              height INTEGER NOT NULL,
              raw_json TEXT NOT NULL,
              FOREIGN KEY(block_hash) REFERENCES blocks(hash) ON DELETE CASCADE,
              UNIQUE(block_hash, event_key)
            );
            CREATE INDEX IF NOT EXISTS idx_market_events_market ON market_events(market_id, height);
            CREATE INDEX IF NOT EXISTS idx_market_events_block_hash ON market_events(block_hash);
            """)
        self._migrate_market_events_table()
        self.conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()

    def _migrate_market_events_table(self) -> None:
        """Upgrade older v0.34/v0.37 databases in-place where possible."""
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(market_events)").fetchall()}
        if "block_hash" not in columns:
            self.conn.execute("ALTER TABLE market_events ADD COLUMN block_hash TEXT NOT NULL DEFAULT ''")
        if "event_key" not in columns:
            self.conn.execute("ALTER TABLE market_events ADD COLUMN event_key TEXT NOT NULL DEFAULT ''")
        self.conn.execute("UPDATE market_events SET block_hash = 'legacy:' || height WHERE block_hash = ''")
        self.conn.execute("UPDATE market_events SET event_key = CAST(id AS TEXT) WHERE event_key = ''")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_market_events_block_hash ON market_events(block_hash)")
        self.conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_market_events_block_event ON market_events(block_hash, event_key)"
        )

    def apply_block(self, block: dict[str, Any]) -> None:
        """Apply ``block`` as the active chain from its height onward.

        Re-applying the same block is idempotent: transaction/address events and
        market events scoped to the block hash are replaced rather than appended.
        Applying a different block at the same height marks the previous block and
        any higher active descendants inactive, so summaries only reflect one
        active chain tip.
        """
        height = int(block["height"])
        block_hash = str(block["hash"])
        prev_hash = str(block.get("prev_hash", ""))
        chainwork = int(block.get("chainwork", height))
        with self.conn:
            self.conn.execute("UPDATE blocks SET active = 0 WHERE height >= ?", (height,))
            self.conn.execute(
                "INSERT OR REPLACE INTO blocks(height, hash, prev_hash, chainwork, active) VALUES(?,?,?,?,1)",
                (height, block_hash, prev_hash, chainwork),
            )
            txids = [str(tx["txid"]) for tx in block.get("txs", [])]
            for txid in txids:
                self.conn.execute("DELETE FROM address_events WHERE txid = ?", (txid,))
            self.conn.execute("DELETE FROM market_events WHERE block_hash = ?", (block_hash,))

            for tx in block.get("txs", []):
                txid = str(tx["txid"])
                self.conn.execute(
                    "INSERT OR REPLACE INTO txs(txid, block_hash, height, raw_json) VALUES(?,?,?,?)",
                    (txid, block_hash, height, json.dumps(tx, sort_keys=True)),
                )
                for event in tx.get("address_events", []):
                    self.conn.execute(
                        "INSERT INTO address_events(address, txid, amount_sats, direction, height) VALUES(?,?,?,?,?)",
                        (
                            str(event["address"]),
                            txid,
                            int(event["amount_sats"]),
                            str(event["direction"]),
                            height,
                        ),
                    )
            for index, event in enumerate(block.get("market_events", [])):
                event_key = str(event.get("event_id") or event.get("id") or f"{block_hash}:{index}")
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO market_events(
                      block_hash, event_key, market_id, event_type, notional_sats, height, raw_json
                    ) VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        block_hash,
                        event_key,
                        str(event["market_id"]),
                        str(event["type"]),
                        int(event.get("notional_sats", 0)),
                        height,
                        json.dumps(event, sort_keys=True),
                    ),
                )

    def apply_blocks(self, blocks: Iterable[dict[str, Any]]) -> None:
        for block in blocks:
            self.apply_block(block)

    def rollback_to_height(self, height: int) -> None:
        height = int(height)
        with self.conn:
            stale_txids = [row[0] for row in self.conn.execute("SELECT txid FROM txs WHERE height > ?", (height,))]
            for txid in stale_txids:
                self.conn.execute("DELETE FROM address_events WHERE txid = ?", (txid,))
            self.conn.execute("DELETE FROM txs WHERE height > ?", (height,))
            self.conn.execute("DELETE FROM market_events WHERE height > ?", (height,))
            self.conn.execute("DELETE FROM blocks WHERE height > ?", (height,))

    def address_summary(self, address: str) -> dict[str, int]:
        rows = self.conn.execute(
            """
            SELECT ae.direction, ae.amount_sats
            FROM address_events ae
            JOIN txs tx ON tx.txid = ae.txid
            JOIN blocks b ON b.hash = tx.block_hash
            WHERE ae.address = ? AND b.active = 1
            """,
            (str(address),),
        ).fetchall()
        received = sum(int(row["amount_sats"]) for row in rows if row["direction"] == "receive")
        sent = sum(int(row["amount_sats"]) for row in rows if row["direction"] == "send")
        return {"received_sats": received, "sent_sats": sent, "balance_sats": received - sent, "event_count": len(rows)}

    def market_summary(self, market_id: str) -> dict[str, int]:
        rows = self.conn.execute(
            """
            SELECT me.event_type, me.notional_sats
            FROM market_events me
            JOIN blocks b ON b.hash = me.block_hash
            WHERE me.market_id = ? AND b.active = 1
            """,
            (str(market_id),),
        ).fetchall()
        volume = sum(int(row["notional_sats"]) for row in rows if row["event_type"] == "trade")
        disputes = sum(1 for row in rows if row["event_type"] == "dispute")
        settlements = sum(1 for row in rows if row["event_type"] == "settlement")
        return {"trade_volume_sats": volume, "disputes": disputes, "settlements": settlements, "event_count": len(rows)}

    def integrity_summary(self) -> dict[str, Any]:
        block_count = int(self.conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0])
        active_block_count = int(self.conn.execute("SELECT COUNT(*) FROM blocks WHERE active = 1").fetchone()[0])
        tx_count = int(
            self.conn.execute(
                "SELECT COUNT(*) FROM txs tx JOIN blocks b ON b.hash = tx.block_hash WHERE b.active = 1"
            ).fetchone()[0]
        )
        address_event_count = int(self.conn.execute("""
                SELECT COUNT(*)
                FROM address_events ae
                JOIN txs tx ON tx.txid = ae.txid
                JOIN blocks b ON b.hash = tx.block_hash
                WHERE b.active = 1
                """).fetchone()[0])
        market_event_count = int(
            self.conn.execute(
                "SELECT COUNT(*) FROM market_events me JOIN blocks b ON b.hash = me.block_hash WHERE b.active = 1"
            ).fetchone()[0]
        )
        tip = self.conn.execute(
            "SELECT height, hash FROM blocks WHERE active = 1 ORDER BY height DESC, chainwork DESC LIMIT 1"
        ).fetchone()
        return {
            "schema_version": SCHEMA_VERSION,
            "block_count": block_count,
            "active_block_count": active_block_count,
            "tx_count": tx_count,
            "address_event_count": address_event_count,
            "market_event_count": market_event_count,
            "tip_height": int(tip["height"]) if tip else 0,
            "tip_hash": str(tip["hash"]) if tip else "",
        }

    def snapshot_hash(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.integrity_summary())).hexdigest()


def sample_indexer_blocks() -> list[dict[str, Any]]:
    return [
        {
            "height": 1,
            "hash": "h1",
            "prev_hash": "genesis",
            "chainwork": 1,
            "txs": [
                {
                    "txid": "tx1",
                    "address_events": [{"address": "net1alice", "direction": "receive", "amount_sats": 5000}],
                }
            ],
            "market_events": [],
        },
        {
            "height": 2,
            "hash": "h2",
            "prev_hash": "h1",
            "chainwork": 2,
            "txs": [
                {
                    "txid": "tx2",
                    "address_events": [
                        {"address": "net1alice", "direction": "send", "amount_sats": 1200},
                        {"address": "net1bob", "direction": "receive", "amount_sats": 1200},
                    ],
                }
            ],
            "market_events": [
                {"market_id": "m1", "type": "trade", "notional_sats": 2000},
                {"market_id": "m1", "type": "settlement", "notional_sats": 0},
            ],
        },
        {
            "height": 3,
            "hash": "h3",
            "prev_hash": "h2",
            "chainwork": 3,
            "txs": [
                {
                    "txid": "tx3",
                    "address_events": [{"address": "net1alice", "direction": "receive", "amount_sats": 700}],
                }
            ],
            "market_events": [{"market_id": "m1", "type": "dispute", "notional_sats": 0}],
        },
    ]


def run_indexer_db_smoke(path: str | Path = ":memory:") -> dict[str, Any]:
    db = IndexerDB(path)
    try:
        db.apply_blocks(sample_indexer_blocks())
        before = db.address_summary("net1alice")
        market = db.market_summary("m1")
        db.rollback_to_height(2)
        after = db.address_summary("net1alice")
        integrity = db.integrity_summary()
        ok = before == {"received_sats": 5700, "sent_sats": 1200, "balance_sats": 4500, "event_count": 3}
        ok = ok and after == {"received_sats": 5000, "sent_sats": 1200, "balance_sats": 3800, "event_count": 2}
        ok = ok and market == {"trade_volume_sats": 2000, "disputes": 1, "settlements": 1, "event_count": 3}
        ok = (
            ok
            and integrity["tip_height"] == 2
            and integrity["block_count"] == 2
            and integrity["active_block_count"] == 2
        )
        return {"ok": ok, "before_reorg": before, "after_reorg": after, "market": market, "integrity": integrity}
    finally:
        db.close()


__all__ = ["IndexerDB", "run_indexer_db_smoke", "sample_indexer_blocks", "SCHEMA_VERSION"]
