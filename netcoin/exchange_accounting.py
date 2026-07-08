"""Double-entry accounting helpers for exchange integrations."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class AccountingLedger:
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
            conn.execute("""CREATE TABLE IF NOT EXISTS ledger_entries(
                    entry_id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    account TEXT NOT NULL,
                    debit_sats INTEGER NOT NULL DEFAULT 0,
                    credit_sats INTEGER NOT NULL DEFAULT 0,
                    reference TEXT DEFAULT '',
                    memo TEXT DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )""")
            conn.commit()

    @staticmethod
    def _entry_id(account: str, debit_sats: int, credit_sats: int, reference: str, memo: str, created_at: int) -> str:
        import hashlib

        body = f"{created_at}|{account}|{debit_sats}|{credit_sats}|{reference}|{memo}"
        return hashlib.sha256(body.encode()).hexdigest()[:20]

    def post(
        self,
        postings: list[dict[str, Any]],
        *,
        reference: str = "",
        memo: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        debit = sum(int(p.get("debit_sats", 0) or 0) for p in postings)
        credit = sum(int(p.get("credit_sats", 0) or 0) for p in postings)
        if debit != credit:
            raise ValueError("double-entry postings must balance")
        created_at = int(time.time())
        ids: list[str] = []
        with self.connect() as conn:
            for posting in postings:
                account = str(posting.get("account") or "")
                if not account:
                    raise ValueError("posting account is required")
                debit_sats = int(posting.get("debit_sats", 0) or 0)
                credit_sats = int(posting.get("credit_sats", 0) or 0)
                entry_id = self._entry_id(account, debit_sats, credit_sats, reference, memo, created_at)
                conn.execute(
                    "INSERT INTO ledger_entries(entry_id,created_at,account,debit_sats,credit_sats,reference,memo,metadata_json) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        entry_id,
                        created_at,
                        account,
                        debit_sats,
                        credit_sats,
                        reference,
                        memo,
                        json.dumps(metadata or {}, sort_keys=True),
                    ),
                )
                ids.append(entry_id)
            conn.commit()
        return {"ok": True, "reference": reference, "entry_ids": ids, "debit_sats": debit, "credit_sats": credit}

    def account_balances(self) -> dict[str, Any]:
        with self.connect() as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    "SELECT account, COALESCE(SUM(debit_sats),0) AS debits, COALESCE(SUM(credit_sats),0) AS credits FROM ledger_entries GROUP BY account ORDER BY account"
                ).fetchall()
            ]
        for row in rows:
            row["balance_sats"] = int(row["debits"]) - int(row["credits"])
        total_debits = sum(int(row["debits"]) for row in rows)
        total_credits = sum(int(row["credits"]) for row in rows)
        return {
            "balanced": total_debits == total_credits,
            "total_debits_sats": total_debits,
            "total_credits_sats": total_credits,
            "accounts": rows,
        }

    def post_customer_deposit(self, *, customer_id: str, amount_sats: int, deposit_id: str) -> dict[str, Any]:
        return self.post(
            [
                {"account": "asset:hot_wallet", "debit_sats": int(amount_sats)},
                {"account": f"liability:customer:{customer_id}", "credit_sats": int(amount_sats)},
            ],
            reference=deposit_id,
            memo="customer deposit credited",
        )

    def post_customer_withdrawal(self, *, customer_id: str, amount_sats: int, withdrawal_id: str) -> dict[str, Any]:
        return self.post(
            [
                {"account": f"liability:customer:{customer_id}", "debit_sats": int(amount_sats)},
                {"account": "asset:hot_wallet", "credit_sats": int(amount_sats)},
            ],
            reference=withdrawal_id,
            memo="customer withdrawal broadcast",
        )


def reconcile_hot_wallet(ledger: AccountingLedger, *, observed_hot_wallet_sats: int) -> dict[str, Any]:
    balances = ledger.account_balances()
    hot = next((row for row in balances["accounts"] if row["account"] == "asset:hot_wallet"), {"balance_sats": 0})
    expected = int(hot.get("balance_sats", 0) or 0)
    observed = int(observed_hot_wallet_sats)
    return {
        "ok": expected == observed,
        "expected_hot_wallet_sats": expected,
        "observed_hot_wallet_sats": observed,
        "delta_sats": observed - expected,
        "ledger_balanced": balances["balanced"],
    }
