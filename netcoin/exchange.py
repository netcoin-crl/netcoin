"""Exchange deposit and withdrawal state machines for NetCoin integrations."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .tx import sats_to_amount

DEPOSIT_STATES = ("seen", "confirming", "credited", "reorged", "reversed")
WITHDRAWAL_STATES = ("requested", "approved", "signed", "broadcast", "confirmed", "failed", "canceled")


class ExchangeLedgerError(ValueError):
    pass


class ExchangeLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS deposits(
                    deposit_id TEXT PRIMARY KEY,
                    txid TEXT NOT NULL,
                    vout INTEGER NOT NULL,
                    address TEXT NOT NULL,
                    amount_sats INTEGER NOT NULL,
                    seen_height INTEGER NOT NULL,
                    block_hash TEXT DEFAULT '',
                    confirmations INTEGER NOT NULL DEFAULT 0,
                    required_confirmations INTEGER NOT NULL DEFAULT 1,
                    state TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(txid, vout)
                )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS withdrawals(
                    withdrawal_id TEXT PRIMARY KEY,
                    address TEXT NOT NULL,
                    amount_sats INTEGER NOT NULL,
                    fee_sats INTEGER NOT NULL DEFAULT 0,
                    state TEXT NOT NULL,
                    requested_by TEXT DEFAULT '',
                    approved_by TEXT DEFAULT '',
                    signed_by TEXT DEFAULT '',
                    txid TEXT DEFAULT '',
                    raw_tx_hash TEXT DEFAULT '',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    metadata_json TEXT DEFAULT '{}'
                )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_deposits_state ON deposits(state)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_withdrawals_state ON withdrawals(state)")
            conn.commit()

    @staticmethod
    def _deposit_id(txid: str, vout: int) -> str:
        return f"dep_{txid[:16]}_{int(vout)}"

    def record_deposit(
        self,
        *,
        txid: str,
        vout: int,
        address: str,
        amount_sats: int,
        height: int,
        block_hash: str = "",
        required_confirmations: int = 1,
        current_height: int | None = None,
    ) -> dict[str, Any]:
        confirmations = 0 if current_height is None else max(0, int(current_height) - int(height) + 1)
        state = (
            "credited"
            if confirmations >= int(required_confirmations)
            else "confirming" if confirmations > 0 else "seen"
        )
        current = int(time.time())
        dep_id = self._deposit_id(txid, vout)
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO deposits(deposit_id,txid,vout,address,amount_sats,seen_height,block_hash,confirmations,required_confirmations,state,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(txid,vout) DO UPDATE SET confirmations=excluded.confirmations,state=excluded.state,updated_at=excluded.updated_at,block_hash=excluded.block_hash""",
                (
                    dep_id,
                    txid,
                    int(vout),
                    address,
                    int(amount_sats),
                    int(height),
                    block_hash,
                    confirmations,
                    int(required_confirmations),
                    state,
                    current,
                    current,
                ),
            )
            conn.commit()
        return self.get_deposit(dep_id)

    def update_deposit_confirmations(self, current_height: int) -> dict[str, Any]:
        updated = 0
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM deposits WHERE state IN ('seen','confirming')").fetchall()
            for row in rows:
                confirmations = max(0, int(current_height) - int(row["seen_height"]) + 1)
                state = (
                    "credited"
                    if confirmations >= int(row["required_confirmations"])
                    else "confirming" if confirmations > 0 else "seen"
                )
                conn.execute(
                    "UPDATE deposits SET confirmations=?,state=?,updated_at=? WHERE deposit_id=?",
                    (confirmations, state, int(time.time()), row["deposit_id"]),
                )
                updated += 1
            conn.commit()
        return {"updated": updated, "current_height": int(current_height)}

    def mark_deposit_reorged(self, deposit_id: str, *, reason: str = "chain reorg") -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                "UPDATE deposits SET state='reorged', confirmations=0, updated_at=? WHERE deposit_id=?",
                (int(time.time()), deposit_id),
            )
            conn.commit()
        rec = self.get_deposit(deposit_id)
        rec["reason"] = reason
        return rec

    def reverse_deposit(self, deposit_id: str, *, reason: str = "operator reversal") -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                "UPDATE deposits SET state='reversed', updated_at=? WHERE deposit_id=?", (int(time.time()), deposit_id)
            )
            conn.commit()
        rec = self.get_deposit(deposit_id)
        rec["reason"] = reason
        return rec

    def request_withdrawal(
        self,
        withdrawal_id: str,
        *,
        address: str,
        amount_sats: int,
        fee_sats: int = 0,
        requested_by: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = int(time.time())
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO withdrawals(withdrawal_id,address,amount_sats,fee_sats,state,requested_by,created_at,updated_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    withdrawal_id,
                    address,
                    int(amount_sats),
                    int(fee_sats),
                    "requested",
                    requested_by,
                    current,
                    current,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            conn.commit()
        return self.get_withdrawal(withdrawal_id)

    def transition_withdrawal(
        self, withdrawal_id: str, state: str, *, operator: str = "operator", txid: str = "", raw_tx: str = ""
    ) -> dict[str, Any]:
        if state not in WITHDRAWAL_STATES:
            raise ExchangeLedgerError(f"invalid withdrawal state: {state}")
        current = int(time.time())
        fields = {"approved": "approved_by", "signed": "signed_by"}
        updates = ["state=?", "updated_at=?"]
        values: list[Any] = [state, current]
        if state in fields:
            updates.append(f"{fields[state]}=?")
            values.append(operator)
        if txid:
            updates.append("txid=?")
            values.append(txid)
        if raw_tx:
            import hashlib

            updates.append("raw_tx_hash=?")
            values.append(hashlib.sha256(raw_tx.encode()).hexdigest())
        values.append(withdrawal_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE withdrawals SET {', '.join(updates)} WHERE withdrawal_id=?", tuple(values))
            conn.commit()
        return self.get_withdrawal(withdrawal_id)

    def get_deposit(self, deposit_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM deposits WHERE deposit_id=?", (deposit_id,)).fetchone()
        if not row:
            raise ExchangeLedgerError("deposit not found")
        data = dict(row)
        data["amount"] = sats_to_amount(int(data["amount_sats"]))
        return data

    def get_withdrawal(self, withdrawal_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM withdrawals WHERE withdrawal_id=?", (withdrawal_id,)).fetchone()
        if not row:
            raise ExchangeLedgerError("withdrawal not found")
        data = dict(row)
        data["amount"] = sats_to_amount(int(data["amount_sats"]))
        data["fee"] = sats_to_amount(int(data["fee_sats"]))
        data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
        return data

    def reconciliation_report(self) -> dict[str, Any]:
        with self.connect() as conn:
            dep = [
                dict(r)
                for r in conn.execute(
                    "SELECT state, COUNT(*) count, COALESCE(SUM(amount_sats),0) sats FROM deposits GROUP BY state"
                ).fetchall()
            ]
            wd = [
                dict(r)
                for r in conn.execute(
                    "SELECT state, COUNT(*) count, COALESCE(SUM(amount_sats),0) sats FROM withdrawals GROUP BY state"
                ).fetchall()
            ]
        return {
            "deposits": dep,
            "withdrawals": wd,
            "deposit_states": DEPOSIT_STATES,
            "withdrawal_states": WITHDRAWAL_STATES,
        }

    def risk_limits_report(
        self,
        *,
        hot_wallet_balance_sats: int = 0,
        max_single_withdrawal_sats: int = 10_000_000_000,
        daily_limit_sats: int = 100_000_000_000,
    ) -> dict[str, Any]:
        """Evaluate exchange hot-wallet and withdrawal risk limits."""
        with self.connect() as conn:
            pending_rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM withdrawals WHERE state IN ('requested','approved','signed','broadcast')"
                ).fetchall()
            ]
        pending_total = sum(int(r.get("amount_sats") or 0) + int(r.get("fee_sats") or 0) for r in pending_rows)
        oversized = [
            r["withdrawal_id"] for r in pending_rows if int(r.get("amount_sats") or 0) > int(max_single_withdrawal_sats)
        ]
        blockers = []
        if pending_total > int(hot_wallet_balance_sats):
            blockers.append("pending_withdrawals_exceed_hot_wallet")
        if pending_total > int(daily_limit_sats):
            blockers.append("pending_withdrawals_exceed_daily_limit")
        if oversized:
            blockers.append("single_withdrawal_limit_exceeded")
        return {
            "ok": not blockers,
            "blockers": blockers,
            "pending_withdrawal_count": len(pending_rows),
            "pending_total_sats": pending_total,
            "pending_total": sats_to_amount(pending_total),
            "hot_wallet_balance_sats": int(hot_wallet_balance_sats),
            "hot_wallet_balance": sats_to_amount(int(hot_wallet_balance_sats)),
            "oversized_withdrawals": oversized,
        }

    def outstanding_liabilities(self) -> dict[str, Any]:
        with self.connect() as conn:
            credited = conn.execute(
                "SELECT COALESCE(SUM(amount_sats),0) sats FROM deposits WHERE state='credited'"
            ).fetchone()["sats"]
            withdrawals = conn.execute(
                "SELECT COALESCE(SUM(amount_sats+fee_sats),0) sats FROM withdrawals WHERE state IN ('confirmed','broadcast','signed','approved','requested')"
            ).fetchone()["sats"]
        net = int(credited or 0) - int(withdrawals or 0)
        return {
            "credited_deposits_sats": int(credited or 0),
            "withdrawal_obligations_sats": int(withdrawals or 0),
            "net_liability_sats": net,
            "net_liability": sats_to_amount(net),
        }
