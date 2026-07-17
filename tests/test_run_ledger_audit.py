from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from netcoin.exchange_accounting import AccountingLedger
from tools.run_ledger_audit import audit_ledger, independent_balances


ROOT = Path(__file__).resolve().parents[1]


def test_ledger_audit_recomputes_balances_and_passes_clean_ledger(tmp_path: Path):
    path = tmp_path / "accounting.sqlite"
    ledger = AccountingLedger(path)
    ledger.post_customer_deposit(customer_id="alice", amount_sats=50_000, deposit_id="dep-1")
    ledger.post_customer_withdrawal(customer_id="alice", amount_sats=10_000, withdrawal_id="wd-1")

    result = audit_ledger(path)

    assert result["ok"] is True
    assert result["mismatches"] == []
    assert independent_balances(path)["total_debits_sats"] == 60_000
    liability = next(r for r in result["independent"]["accounts"] if r["account"] == "liability:customer:alice")
    assert liability["balance_sats"] == -40_000


def test_ledger_audit_exits_nonzero_on_drift(tmp_path: Path):
    path = tmp_path / "accounting.sqlite"
    ledger = AccountingLedger(path)
    ledger.post_customer_deposit(customer_id="alice", amount_sats=50_000, deposit_id="dep-1")
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE ledger_entries SET debit_sats = debit_sats + 1 WHERE account = 'asset:hot_wallet'")

    result = subprocess.run(
        [sys.executable, "tools/run_ledger_audit.py", "--ledger", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["independent"]["balanced"] is False
    assert payload["invariant"]["balanced"] is False
