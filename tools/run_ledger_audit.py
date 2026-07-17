#!/usr/bin/env python3
"""Run an independent double-entry ledger audit."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.exchange_accounting import AccountingLedger


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        present = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ledger_entries'"
        ).fetchone()
        if not present:
            return []
        return [
            dict(row)
            for row in conn.execute(
                "SELECT account, debit_sats, credit_sats, reference FROM ledger_entries ORDER BY entry_id"
            ).fetchall()
        ]
    finally:
        conn.close()


def independent_balances(path: str | Path) -> dict[str, Any]:
    accounts: dict[str, dict[str, int | str]] = {}
    total_debits = 0
    total_credits = 0
    for row in _rows(Path(path)):
        account = str(row["account"])
        debit = int(row["debit_sats"] or 0)
        credit = int(row["credit_sats"] or 0)
        total_debits += debit
        total_credits += credit
        item = accounts.setdefault(account, {"account": account, "debits": 0, "credits": 0})
        item["debits"] = int(item["debits"]) + debit
        item["credits"] = int(item["credits"]) + credit
    rows = []
    for account in sorted(accounts):
        item = accounts[account]
        rows.append(
            {
                "account": account,
                "debits": int(item["debits"]),
                "credits": int(item["credits"]),
                "balance_sats": int(item["debits"]) - int(item["credits"]),
            }
        )
    negative = [
        {"account": r["account"], "balance_sats": r["credits"] - r["debits"]}
        for r in rows
        if r["account"].startswith("liability:customer:") and r["credits"] - r["debits"] < 0
    ]
    return {
        "balanced": total_debits == total_credits,
        "total_debits_sats": total_debits,
        "total_credits_sats": total_credits,
        "accounts": rows,
        "negative_customer_liabilities": negative,
    }


def audit_ledger(path: str | Path) -> dict[str, Any]:
    ledger = AccountingLedger(path)
    independent = independent_balances(path)
    materialized = ledger.account_balances()
    invariant = ledger.invariant_check()
    independent_accounts = {row["account"]: row for row in independent["accounts"]}
    materialized_accounts = {row["account"]: row for row in materialized["accounts"]}
    mismatches = []
    for account in sorted(set(independent_accounts) | set(materialized_accounts)):
        left = independent_accounts.get(account)
        right = materialized_accounts.get(account)
        if left != right:
            mismatches.append({"account": account, "independent": left, "materialized": right})
    ok = bool(independent["balanced"] and invariant["ok"] and not mismatches)
    return {
        "ok": ok,
        "ledger_path": str(path),
        "independent": independent,
        "materialized": materialized,
        "invariant": invariant,
        "mismatches": mismatches,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a NetCoin AccountingLedger sqlite database")
    parser.add_argument("--ledger", required=True, help="Path to the AccountingLedger sqlite database")
    parser.add_argument("--out", default="", help="Optional JSON report path")
    args = parser.parse_args(argv)
    result = audit_ledger(args.ledger)
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
