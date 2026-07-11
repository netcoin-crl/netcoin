"""Production custody evidence validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .exchange_accounting import AccountingLedger, reconcile_hot_wallet
from .exchange_reserves import reserve_attestation, verify_reserve_attestation
from .mainnet_readiness import strict_evidence_gate

REQUIRED_CUSTODY_EVIDENCE = [
    "balanced_double_entry_ledger",
    "segregated_hot_cold_accounts",
    "withdrawal_approval_transcript",
    "reserve_attestation",
    "cold_signing_ceremony",
    "stuck_withdrawal_recovery_drill",
]


def source_custody_smoke(db_path: str | Path) -> dict[str, Any]:
    ledger = AccountingLedger(db_path)
    ledger.post_customer_deposit(customer_id="alice", amount_sats=100_000, deposit_id="source-deposit-1")
    ledger.post_customer_withdrawal(customer_id="alice", amount_sats=25_000, withdrawal_id="source-withdrawal-1")
    balances = ledger.account_balances()
    hot_recon = reconcile_hot_wallet(ledger, observed_hot_wallet_sats=75_000)
    attestation = reserve_attestation(
        liabilities=[{"customer_id": "alice", "amount_sats": 75_000, "nonce": "source"}],
        reserves=[{"address": "source-hot-wallet", "amount_sats": 75_000, "signature": "source-only"}],
        operator="source-custody-smoke",
    )
    reserve_check = verify_reserve_attestation(attestation)
    return {
        "ok": bool(balances["balanced"] and hot_recon["ok"] and reserve_check["ok"] and reserve_check["solvent"]),
        "mode": "source",
        "balanced_double_entry_ledger": balances["balanced"],
        "hot_wallet_reconciliation": hot_recon,
        "reserve_attestation_ok": reserve_check["ok"],
        "solvent": reserve_check["solvent"],
    }


def strict_custody_evidence(evidence_path: str | Path) -> dict[str, Any]:
    gate = strict_evidence_gate("production-exchange-custody", evidence_path, REQUIRED_CUSTODY_EVIDENCE)
    return gate.to_dict()
