from __future__ import annotations

import os
import signal
import time
from multiprocessing import Process
from pathlib import Path

from netcoin.exchange_accounting import AccountingLedger
from tools.run_ledger_audit import audit_ledger


def _writer(path: str, run_id: int, iterations: int) -> None:
    ledger = AccountingLedger(path)
    for i in range(iterations):
        amount = 1_000 + ((run_id + i) % 97)
        ledger.post(
            [
                {"account": "asset:hot_wallet", "debit_sats": amount},
                {"account": f"liability:customer:chaos-{run_id}", "credit_sats": amount},
            ],
            reference=f"chaos-{run_id}-{i}",
            memo="chaos deposit",
        )


def test_accounting_ledger_survives_killed_writer_processes(tmp_path: Path):
    path = tmp_path / "accounting.sqlite"
    AccountingLedger(path).post_customer_deposit(customer_id="seed", amount_sats=1_000, deposit_id="seed-dep")

    for run_id in range(20):
        proc = Process(target=_writer, args=(str(path), run_id, 1000))
        proc.start()
        time.sleep(0.01)
        if proc.pid is not None and proc.is_alive():
            os.kill(proc.pid, signal.SIGKILL)
        proc.join(timeout=2)
        assert not proc.is_alive()
        result = audit_ledger(path)
        assert result["ok"] is True
        assert result["mismatches"] == []
