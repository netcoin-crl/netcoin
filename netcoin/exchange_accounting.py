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

    def has_reference(self, reference: str) -> bool:
        """True if any posting already exists under this reference. Callers use
        this to make crediting a deposit (or any other event) idempotent."""
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM ledger_entries WHERE reference=? LIMIT 1", (reference,)).fetchone()
        return row is not None

    def reverse_reference(self, reference: str, *, reason: str = "") -> dict[str, Any]:
        """Post an exact compensating entry (debit/credit swapped) for every
        posting under `reference`. Idempotent: calling twice is a no-op the
        second time, so a retried reorg-drill or crash-recovery pass can't
        double-reverse the same event."""
        reversal_ref = f"reversal:{reference}"
        if self.has_reference(reversal_ref):
            return {"ok": True, "already_reversed": True, "reference": reversal_ref, "entry_ids": []}
        with self.connect() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT account, debit_sats, credit_sats FROM ledger_entries WHERE reference=?", (reference,)
                ).fetchall()
            ]
        if not rows:
            raise ValueError(f"no ledger entries found for reference {reference!r}; nothing to reverse")
        postings = [
            {"account": r["account"], "debit_sats": r["credit_sats"], "credit_sats": r["debit_sats"]} for r in rows
        ]
        return self.post(postings, reference=reversal_ref, memo=f"reversal: {reason}" if reason else "reversal")

    def customer_liability_sats(self, customer_id: str) -> int:
        """Amount owed to this customer. Positive = we owe them; liability
        accounts are credit-normal, so this is credits minus debits (the
        inverse of account_balances' generic debit-minus-credit convention,
        which is written for asset-account readability)."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(credit_sats),0) c, COALESCE(SUM(debit_sats),0) d FROM ledger_entries WHERE account=?",
                (f"liability:customer:{customer_id}",),
            ).fetchone()
        return int(row["c"]) - int(row["d"])

    def invariant_check(self) -> dict[str, Any]:
        """The two invariants every write must preserve: (1) the ledger as a
        whole balances (debit==credit is already enforced per-post, but a
        drifted/tampered file would show up here too), and (2) no customer
        liability account is negative (we can never owe a customer less than
        zero, i.e. they can never have spent more than they were credited)."""
        balances = self.account_balances()
        with self.connect() as conn:
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT account, COALESCE(SUM(credit_sats),0) c, COALESCE(SUM(debit_sats),0) d "
                    "FROM ledger_entries WHERE account LIKE 'liability:customer:%' GROUP BY account"
                ).fetchall()
            ]
        negative = [
            {"account": r["account"], "balance_sats": int(r["c"]) - int(r["d"])}
            for r in rows
            if int(r["c"]) - int(r["d"]) < 0
        ]
        return {
            "ok": balances["balanced"] and not negative,
            "balanced": balances["balanced"],
            "negative_customer_liabilities": negative,
            "total_debits_sats": balances["total_debits_sats"],
            "total_credits_sats": balances["total_credits_sats"],
        }


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
