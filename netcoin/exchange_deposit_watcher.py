"""Wires the exchange deposit/withdrawal state machine (ExchangeLedger) to the
double-entry ledger (AccountingLedger) and to real chain-reorg detection.

Both ExchangeLedger and AccountingLedger already existed as solid, independent
pieces: ExchangeLedger tracks deposit/withdrawal state (including 'reorged'
and 'reversed' states) and custody-account policy; AccountingLedger is the
balanced double-entry journal. Nothing previously connected them, and nothing
detected when a *credited* deposit's block had been reorged out from under it
-- ExchangeLedger.mark_deposit_reorged existed but nothing called it. This
module is that connection.
"""

from __future__ import annotations

from typing import Any

from .chain import Blockchain
from .exchange import ExchangeLedger
from .exchange_accounting import AccountingLedger


class ExchangeDepositWatcher:
    def __init__(self, exchange_ledger: ExchangeLedger, accounting: AccountingLedger):
        self.exchange_ledger = exchange_ledger
        self.accounting = accounting

    def _customer_id_for_deposit(self, deposit: dict[str, Any]) -> str:
        # Per-user deposit addresses map 1:1 to a customer id in the simplest
        # case. A caller with a shared-address/derivation-index model should
        # subclass and override this to look up the real customer id.
        return str(deposit["address"])

    def sync_confirmations_and_credit(self, chain: Blockchain) -> dict[str, Any]:
        """Advance deposit confirmations against the current chain tip, and
        post each newly-credited deposit to the accounting ledger exactly
        once (idempotent via AccountingLedger.has_reference)."""
        height = chain.height()
        result = self.exchange_ledger.update_deposit_confirmations(height)
        credited_now: list[str] = []
        with self.exchange_ledger.connect() as conn:
            rows = [dict(r) for r in conn.execute("SELECT deposit_id FROM deposits WHERE state='credited'")]
        for row in rows:
            deposit_id = row["deposit_id"]
            if self.accounting.has_reference(deposit_id):
                continue
            deposit = self.exchange_ledger.get_deposit(deposit_id)
            self.accounting.post_customer_deposit(
                customer_id=self._customer_id_for_deposit(deposit),
                amount_sats=int(deposit["amount_sats"]),
                deposit_id=deposit_id,
            )
            credited_now.append(deposit_id)
        result["newly_credited_and_posted"] = credited_now
        return result

    def check_for_reorgs(self, chain: Blockchain) -> dict[str, Any]:
        """Detect credited deposits whose recorded block is no longer on the
        main chain (the exact 'deposit, trade, reorg, withdraw' exchange
        failure mode), reverse their ledger credit, and flag the account if
        the customer already spent against it (reversal would drive their
        liability negative)."""
        reversed_deposits: list[str] = []
        frozen_accounts: list[dict[str, Any]] = []
        with self.exchange_ledger.connect() as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM deposits WHERE state='credited'")]
        for row in rows:
            block_hash = row.get("block_hash") or ""
            if not block_hash or chain.block_index.get(block_hash) is not None:
                continue  # no recorded block, or still on the main chain
            deposit_id = row["deposit_id"]
            self.exchange_ledger.mark_deposit_reorged(deposit_id, reason="chain reorg orphaned the deposit block")
            self.accounting.reverse_reference(deposit_id, reason="deposit reorged out of the main chain")
            reversed_deposits.append(deposit_id)
            customer_id = self._customer_id_for_deposit(row)
            liability = self.accounting.customer_liability_sats(customer_id)
            if liability < 0:
                frozen_accounts.append(
                    {"customer_id": customer_id, "deficit_sats": liability, "deposit_id": deposit_id}
                )
        return {"reversed_deposit_ids": reversed_deposits, "frozen_accounts": frozen_accounts}

    def sync(self, chain: Blockchain) -> dict[str, Any]:
        """Reorg check first (so a just-reorged deposit can't get credited on
        this same pass), then advance confirmations and credit."""
        reorg_result = self.check_for_reorgs(chain)
        credit_result = self.sync_confirmations_and_credit(chain)
        return {"reorg": reorg_result, "credit": credit_result}
