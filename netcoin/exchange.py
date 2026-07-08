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
            conn.execute("""CREATE TABLE IF NOT EXISTS custody_accounts(
                    account_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    address TEXT NOT NULL,
                    balance_sats INTEGER NOT NULL DEFAULT 0,
                    daily_limit_sats INTEGER NOT NULL DEFAULT 0,
                    single_limit_sats INTEGER NOT NULL DEFAULT 0,
                    min_approvals INTEGER NOT NULL DEFAULT 1,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    metadata_json TEXT DEFAULT '{}'
                )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS withdrawal_approvals(
                    approval_id TEXT PRIMARY KEY,
                    withdrawal_id TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT DEFAULT '',
                    created_at INTEGER NOT NULL,
                    UNIQUE(withdrawal_id, operator)
                )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_custody_kind ON custody_accounts(kind)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_withdrawal_approvals ON withdrawal_approvals(withdrawal_id)")
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

    def configure_custody_account(
        self,
        account_id: str,
        *,
        kind: str,
        address: str,
        balance_sats: int = 0,
        daily_limit_sats: int = 0,
        single_limit_sats: int = 0,
        min_approvals: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or update a hot/warm/cold custody account policy."""
        if kind not in {"hot", "warm", "cold"}:
            raise ExchangeLedgerError("custody account kind must be hot, warm, or cold")
        current = int(time.time())
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO custody_accounts(account_id,kind,address,balance_sats,daily_limit_sats,single_limit_sats,min_approvals,created_at,updated_at,metadata_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(account_id) DO UPDATE SET
                       kind=excluded.kind,address=excluded.address,balance_sats=excluded.balance_sats,
                       daily_limit_sats=excluded.daily_limit_sats,single_limit_sats=excluded.single_limit_sats,
                       min_approvals=excluded.min_approvals,updated_at=excluded.updated_at,metadata_json=excluded.metadata_json""",
                (
                    account_id,
                    kind,
                    address,
                    int(balance_sats),
                    int(daily_limit_sats),
                    int(single_limit_sats),
                    int(min_approvals),
                    current,
                    current,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            conn.commit()
        return self.get_custody_account(account_id)

    def get_custody_account(self, account_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM custody_accounts WHERE account_id=?", (account_id,)).fetchone()
        if not row:
            raise ExchangeLedgerError("custody account not found")
        data = dict(row)
        data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
        data["balance"] = sats_to_amount(int(data["balance_sats"]))
        data["daily_limit"] = sats_to_amount(int(data["daily_limit_sats"]))
        data["single_limit"] = sats_to_amount(int(data["single_limit_sats"]))
        return data

    def custody_status(self) -> dict[str, Any]:
        with self.connect() as conn:
            rows = [
                dict(r) for r in conn.execute("SELECT * FROM custody_accounts ORDER BY kind, account_id").fetchall()
            ]
            pending = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM withdrawals WHERE state IN ('requested','approved','signed','broadcast') ORDER BY created_at"
                ).fetchall()
            ]
        accounts = []
        for row in rows:
            row["metadata"] = json.loads(row.pop("metadata_json") or "{}")
            row["balance"] = sats_to_amount(int(row["balance_sats"]))
            accounts.append(row)
        hot_balance = sum(
            int(a["balance_sats"]) for a in accounts if a.get("kind") == "hot" and int(a.get("active") or 0)
        )
        cold_balance = sum(
            int(a["balance_sats"]) for a in accounts if a.get("kind") == "cold" and int(a.get("active") or 0)
        )
        pending_total = sum(int(w.get("amount_sats") or 0) + int(w.get("fee_sats") or 0) for w in pending)
        return {
            "accounts": accounts,
            "hot_balance_sats": hot_balance,
            "hot_balance": sats_to_amount(hot_balance),
            "cold_balance_sats": cold_balance,
            "cold_balance": sats_to_amount(cold_balance),
            "pending_withdrawal_sats": pending_total,
            "pending_withdrawal_total": sats_to_amount(pending_total),
            "hot_wallet_coverage_ok": hot_balance >= pending_total,
        }

    def withdrawal_policy(self, withdrawal_id: str) -> dict[str, Any]:
        withdrawal = self.get_withdrawal(withdrawal_id)
        with self.connect() as conn:
            hot = [
                dict(r) for r in conn.execute("SELECT * FROM custody_accounts WHERE kind='hot' AND active=1").fetchall()
            ]
            approvals = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM withdrawal_approvals WHERE withdrawal_id=?", (withdrawal_id,)
                ).fetchall()
            ]
        amount = int(withdrawal["amount_sats"]) + int(withdrawal["fee_sats"])
        blockers: list[str] = []
        required = 1
        eligible_accounts = []
        for acct in hot:
            required = max(required, int(acct.get("min_approvals") or 1))
            if int(acct.get("single_limit_sats") or 0) and amount > int(acct["single_limit_sats"]):
                blockers.append(f"single_limit_exceeded:{acct['account_id']}")
                continue
            if amount <= int(acct.get("balance_sats") or 0):
                eligible_accounts.append(acct["account_id"])
        if not hot:
            blockers.append("no_active_hot_wallet")
        if not eligible_accounts:
            blockers.append("hot_wallet_balance_insufficient")
        approved = [a for a in approvals if a.get("decision") == "approved"]
        denied = [a for a in approvals if a.get("decision") == "denied"]
        if denied:
            blockers.append("approval_denied")
        return {
            "withdrawal_id": withdrawal_id,
            "amount_sats": amount,
            "required_approvals": required,
            "approved_count": len(approved),
            "denied_count": len(denied),
            "eligible_hot_accounts": eligible_accounts,
            "ready_to_sign": len(approved) >= required and not blockers,
            "blockers": sorted(set(blockers)),
        }

    def approve_withdrawal(
        self, withdrawal_id: str, *, operator: str, decision: str = "approved", reason: str = ""
    ) -> dict[str, Any]:
        if decision not in {"approved", "denied"}:
            raise ExchangeLedgerError("approval decision must be approved or denied")
        approval_id = f"appr_{withdrawal_id}_{operator}"
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO withdrawal_approvals(approval_id,withdrawal_id,operator,decision,reason,created_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(withdrawal_id, operator) DO UPDATE SET decision=excluded.decision,reason=excluded.reason,created_at=excluded.created_at""",
                (approval_id, withdrawal_id, operator, decision, reason, int(time.time())),
            )
            conn.commit()
        policy = self.withdrawal_policy(withdrawal_id)
        if policy["ready_to_sign"] and self.get_withdrawal(withdrawal_id)["state"] == "requested":
            self.transition_withdrawal(withdrawal_id, "approved", operator=operator)
            policy = self.withdrawal_policy(withdrawal_id)
        return policy

    def prepare_hot_withdrawal_batch(self, *, limit: int = 25) -> dict[str, Any]:
        with self.connect() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT withdrawal_id FROM withdrawals WHERE state IN ('requested','approved') ORDER BY created_at LIMIT ?",
                    (int(limit),),
                ).fetchall()
            ]
        ready = []
        blocked = []
        for row in rows:
            policy = self.withdrawal_policy(row["withdrawal_id"])
            if policy["ready_to_sign"]:
                ready.append(policy)
            else:
                blocked.append(policy)
        return {"ready": ready, "blocked": blocked, "ready_count": len(ready), "blocked_count": len(blocked)}

    def record_cold_to_hot_transfer(
        self, *, cold_account_id: str, hot_account_id: str, amount_sats: int, txid: str = ""
    ) -> dict[str, Any]:
        amount = int(amount_sats)
        cold = self.get_custody_account(cold_account_id)
        hot = self.get_custody_account(hot_account_id)
        if cold["kind"] != "cold" or hot["kind"] != "hot":
            raise ExchangeLedgerError("cold-to-hot transfer requires cold source and hot destination")
        if int(cold["balance_sats"]) < amount:
            raise ExchangeLedgerError("cold account balance is insufficient")
        with self.connect() as conn:
            now = int(time.time())
            conn.execute(
                "UPDATE custody_accounts SET balance_sats=balance_sats-?,updated_at=? WHERE account_id=?",
                (amount, now, cold_account_id),
            )
            conn.execute(
                "UPDATE custody_accounts SET balance_sats=balance_sats+?,updated_at=? WHERE account_id=?",
                (amount, now, hot_account_id),
            )
            conn.commit()
        return {
            "ok": True,
            "from": cold_account_id,
            "to": hot_account_id,
            "amount_sats": amount,
            "amount": sats_to_amount(amount),
            "txid": txid,
        }
