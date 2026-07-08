"""Persistent wallet approval queue for risky transaction previews."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .wallet_policy import approval_receipt, approval_request, verify_approval_receipt


class WalletApprovalQueue:
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
            conn.execute("""CREATE TABLE IF NOT EXISTS wallet_approval_requests(
                    request_hash TEXT PRIMARY KEY,
                    wallet_id TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    request_json TEXT NOT NULL,
                    receipt_json TEXT DEFAULT ''
                )""")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_wallet_approvals_status ON wallet_approval_requests(status, created_at)"
            )
            conn.commit()

    def create_request(
        self, wallet_id: str, preview: dict[str, Any], *, profile: str = "standard", requester: str = "wallet"
    ) -> dict[str, Any]:
        req = approval_request(preview, profile, requester=requester)
        current = int(time.time())
        status = "pending" if req.get("decision", {}).get("action") != "block" else "blocked"
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO wallet_approval_requests(request_hash,wallet_id,profile,status,created_at,updated_at,request_json)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(request_hash) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at, request_json=excluded.request_json""",
                (req["request_hash"], wallet_id, profile, status, current, current, json.dumps(req, sort_keys=True)),
            )
            conn.commit()
        return self.get(req["request_hash"])

    def get(self, request_hash: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM wallet_approval_requests WHERE request_hash=?", (request_hash,)
            ).fetchone()
        if not row:
            return {}
        return self._decode(dict(row))

    @staticmethod
    def _decode(row: dict[str, Any]) -> dict[str, Any]:
        row["request"] = json.loads(row.pop("request_json") or "{}")
        receipt_text = row.pop("receipt_json") or ""
        row["receipt"] = json.loads(receipt_text) if receipt_text else None
        return row

    def list(
        self, *, status: str | None = None, wallet_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM wallet_approval_requests"
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if wallet_id:
            clauses.append("wallet_id=?")
            params.append(wallet_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 1000)))
        with self.connect() as conn:
            rows = [self._decode(dict(row)) for row in conn.execute(sql, tuple(params)).fetchall()]
        return rows

    def approve(self, request_hash: str, *, approver: str, approved: bool = True, note: str = "") -> dict[str, Any]:
        req_row = self.get(request_hash)
        if not req_row:
            raise ValueError("approval request not found")
        if req_row["status"] == "blocked" and approved:
            raise ValueError("blocked request cannot be approved")
        receipt = approval_receipt(req_row["request"], approver=approver, approved=approved)
        if note:
            receipt["note"] = note
        check = verify_approval_receipt(req_row["request"], receipt)
        if not check.get("ok"):
            raise ValueError("approval receipt failed verification")
        status = "approved" if approved else "denied"
        with self.connect() as conn:
            conn.execute(
                "UPDATE wallet_approval_requests SET status=?, updated_at=?, receipt_json=? WHERE request_hash=?",
                (status, int(time.time()), json.dumps(receipt, sort_keys=True), request_hash),
            )
            conn.commit()
        return self.get(request_hash)

    def summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    "SELECT status, COUNT(*) count FROM wallet_approval_requests GROUP BY status"
                ).fetchall()
            ]
        return {
            "counts": {row["status"]: int(row["count"]) for row in rows},
            "total": sum(int(row["count"]) for row in rows),
        }
