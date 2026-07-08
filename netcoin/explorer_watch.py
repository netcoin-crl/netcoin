"""Explorer watchlists and notification helpers.

This module is intentionally derived-index data: it watches the explorer indexer
for addresses, transactions, or blocks operators/users care about, then records
idempotent notifications.  It can be rebuilt from the indexer and does not affect
consensus.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

WATCH_TYPES = {"address", "transaction", "block"}


def _storage(indexer: Any) -> Any:
    return getattr(indexer, "storage", indexer)


class ExplorerWatchStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS watch_items(
                    item_id TEXT PRIMARY KEY,
                    watch_type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    label TEXT DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(watch_type, value)
                )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS watch_notifications(
                    notification_id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    watch_type TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    value TEXT NOT NULL,
                    txid TEXT DEFAULT '',
                    block_hash TEXT DEFAULT '',
                    height INTEGER DEFAULT NULL,
                    address TEXT DEFAULT '',
                    amount_sats INTEGER DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    seen INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_watch_items_active ON watch_items(active, watch_type)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_watch_notifications_item ON watch_notifications(item_id, created_at)"
            )
            conn.commit()

    @staticmethod
    def _item_id(watch_type: str, value: str) -> str:
        return hashlib.sha256(f"{watch_type}:{value}".encode()).hexdigest()[:20]

    @staticmethod
    def _notification_id(
        item_id: str, kind: str, txid: str = "", block_hash: str = "", address: str = "", height: int | None = None
    ) -> str:
        body = f"{item_id}|{kind}|{txid}|{block_hash}|{address}|{height if height is not None else ''}"
        return hashlib.sha256(body.encode()).hexdigest()[:24]

    def add_watch(
        self, watch_type: str, value: str, *, label: str = "", metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        watch_type = str(watch_type).lower().strip()
        if watch_type not in WATCH_TYPES:
            raise ValueError(f"unknown watch type: {watch_type}")
        value = str(value).strip()
        if not value:
            raise ValueError("watch value is required")
        item_id = self._item_id(watch_type, value)
        current = int(time.time())
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO watch_items(item_id,watch_type,value,label,active,created_at,metadata_json)
                   VALUES(?,?,?,?,1,?,?)
                   ON CONFLICT(watch_type,value) DO UPDATE SET label=excluded.label, active=1, metadata_json=excluded.metadata_json""",
                (item_id, watch_type, value, label, current, json.dumps(metadata or {}, sort_keys=True)),
            )
            conn.commit()
        return self.get_watch(item_id)

    def get_watch(self, item_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM watch_items WHERE item_id=?", (item_id,)).fetchone()
        if not row:
            return {}
        data = dict(row)
        data["active"] = bool(data["active"])
        data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
        return data

    def deactivate_watch(self, item_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute("UPDATE watch_items SET active=0 WHERE item_id=?", (item_id,))
            conn.commit()
        return self.get_watch(item_id)

    def list_watches(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM watch_items"
        params: tuple[Any, ...] = ()
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY created_at DESC, value"
        with self.connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
        for row in rows:
            row["active"] = bool(row["active"])
            row["metadata"] = json.loads(row.pop("metadata_json") or "{}")
        return rows

    def _insert_notification(
        self, conn: sqlite3.Connection, item: dict[str, Any], kind: str, payload: dict[str, Any]
    ) -> bool:
        txid = str(payload.get("txid") or "")
        block_hash = str(payload.get("block_hash") or "")
        address = str(payload.get("address") or "")
        height = payload.get("height")
        nid = self._notification_id(
            item["item_id"], kind, txid, block_hash, address, int(height) if height is not None else None
        )
        cur = conn.execute(
            """INSERT OR IGNORE INTO watch_notifications(notification_id,item_id,watch_type,kind,value,txid,block_hash,height,address,amount_sats,created_at,payload_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                nid,
                item["item_id"],
                item["watch_type"],
                kind,
                item["value"],
                txid,
                block_hash,
                int(height) if height is not None else None,
                address,
                int(payload.get("amount_sats") or 0),
                int(payload.get("timestamp") or time.time()),
                json.dumps(payload, sort_keys=True),
            ),
        )
        return cur.rowcount > 0

    def scan_indexer(self, indexer: Any, *, since_height: int | None = None) -> dict[str, Any]:
        storage = _storage(indexer)
        watches = self.list_watches(active_only=True)
        inserted = 0
        scanned = 0
        with self.connect() as conn:
            for item in watches:
                scanned += 1
                if item["watch_type"] == "address":
                    sql = "SELECT * FROM address_events WHERE address=?"
                    params: tuple[Any, ...] = (item["value"],)
                    if since_height is not None:
                        sql += " AND height>=?"
                        params = (item["value"], int(since_height))
                    for row in storage.rows(sql, params):
                        inserted += int(self._insert_notification(conn, item, "address_activity", dict(row)))
                elif item["watch_type"] == "transaction":
                    for row in storage.rows("SELECT * FROM transactions WHERE txid=?", (item["value"],)):
                        inserted += int(self._insert_notification(conn, item, "transaction_seen", dict(row)))
                elif item["watch_type"] == "block":
                    rows = []
                    if item["value"].isdigit():
                        rows = storage.rows("SELECT * FROM blocks WHERE height=?", (int(item["value"]),))
                    if not rows:
                        rows = storage.rows("SELECT * FROM blocks WHERE block_hash=?", (item["value"],))
                    for row in rows:
                        inserted += int(self._insert_notification(conn, item, "block_seen", dict(row)))
            conn.commit()
        return {"scanned_watches": scanned, "new_notifications": inserted}

    def notifications(
        self, *, item_id: str | None = None, unseen_only: bool = False, limit: int = 100
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM watch_notifications"
        clauses: list[str] = []
        params: list[Any] = []
        if item_id:
            clauses.append("item_id=?")
            params.append(item_id)
        if unseen_only:
            clauses.append("seen=0")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 1000)))
        with self.connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]
        for row in rows:
            row["seen"] = bool(row["seen"])
            row["payload"] = json.loads(row.pop("payload_json") or "{}")
        return rows

    def mark_seen(self, notification_ids: list[str]) -> dict[str, Any]:
        if not notification_ids:
            return {"updated": 0}
        with self.connect() as conn:
            cur = conn.executemany(
                "UPDATE watch_notifications SET seen=1 WHERE notification_id=?", [(nid,) for nid in notification_ids]
            )
            conn.commit()
        return {"updated": cur.rowcount}

    def summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            watches = [
                dict(row)
                for row in conn.execute(
                    "SELECT watch_type, COUNT(*) count FROM watch_items WHERE active=1 GROUP BY watch_type"
                ).fetchall()
            ]
            unseen = conn.execute("SELECT COUNT(*) count FROM watch_notifications WHERE seen=0").fetchone()["count"]
            total = conn.execute("SELECT COUNT(*) count FROM watch_notifications").fetchone()["count"]
        return {
            "active_watches": {row["watch_type"]: int(row["count"]) for row in watches},
            "unseen_notifications": int(unseen),
            "total_notifications": int(total),
        }
