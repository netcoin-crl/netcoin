"""Mempool policy and fee estimation for NetCoin.

Consensus decides which blocks are valid. Mempool policy decides what an
individual node is willing to relay before a transaction is mined. Bitcoin Core
has a very large policy engine; this module implements the same core ideas in a
small, readable way: dust rejection, fee-rate checks, standard transaction
weight, ancestor/descendant limits, and simple opt-in replace-by-fee.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Dict, Iterable, List, Sequence, Tuple

from .params import (
    DUST_LIMIT,
    INCREMENTAL_RELAY_FEE,
    MAX_ANCESTORS,
    MAX_DESCENDANTS,
    MAX_MEMPOOL_TRANSACTIONS,
    MAX_STANDARD_TX_WEIGHT,
    MIN_RELAY_FEE_PER_KB,
)
from .tx import SpendableOutput, Transaction


class MempoolPolicyError(ValueError):
    """Raised when a transaction fails local relay policy."""


@dataclass(frozen=True)
class MempoolEntry:
    txid: str
    fee: int
    vsize: int
    fee_rate: float
    signals_rbf: bool


def min_relay_fee(vsize: int, fee_per_kb: int = MIN_RELAY_FEE_PER_KB) -> int:
    return (vsize * fee_per_kb + 999) // 1000


def output_is_dust(amount: int) -> bool:
    return 0 < amount < DUST_LIMIT


def transaction_fee(tx: Transaction, utxos: Dict[str, SpendableOutput]) -> int:
    if tx.is_coinbase:
        return 0
    input_total = 0
    for txin in tx.inputs:
        prevout = utxos.get(txin.outpoint())
        if prevout is None:
            raise MempoolPolicyError(f"missing UTXO for fee calculation: {txin.outpoint()}")
        input_total += prevout.output.amount
    return input_total - tx.total_output()


def mempool_entry(tx: Transaction, fee: int) -> MempoolEntry:
    vsize = max(1, tx.vsize())
    return MempoolEntry(
        txid=tx.txid(),
        fee=fee,
        vsize=vsize,
        fee_rate=fee / vsize,
        signals_rbf=tx.signals_rbf,
    )


def conflicts_with_mempool(tx: Transaction, mempool: Sequence[Transaction]) -> List[Transaction]:
    spending = {txin.outpoint() for txin in tx.inputs}
    conflicts = []
    for other in mempool:
        if spending & {txin.outpoint() for txin in other.inputs}:
            conflicts.append(other)
    return conflicts


def touches_unconfirmed_parent(tx: Transaction, mempool: Sequence[Transaction]) -> bool:
    mempool_txids = {item.txid() for item in mempool}
    return any(txin.txid in mempool_txids for txin in tx.inputs)


def ancestor_count(tx: Transaction, mempool: Sequence[Transaction]) -> int:
    by_txid = {item.txid(): item for item in mempool}
    seen = set()

    def visit(parent_txid: str) -> None:
        if parent_txid in seen or parent_txid not in by_txid:
            return
        seen.add(parent_txid)
        for txin in by_txid[parent_txid].inputs:
            visit(txin.txid)

    for txin in tx.inputs:
        visit(txin.txid)
    return len(seen)


def descendant_count(parent: Transaction, mempool: Sequence[Transaction]) -> int:
    parent_txid = parent.txid()
    descendants = set()
    changed = True
    while changed:
        changed = False
        known = descendants | {parent_txid}
        for tx in mempool:
            txid = tx.txid()
            if txid in descendants:
                continue
            if any(txin.txid in known for txin in tx.inputs):
                descendants.add(txid)
                changed = True
    return len(descendants)


def check_standard_policy(tx: Transaction, fee: int, mempool: Sequence[Transaction]) -> None:
    if tx.is_coinbase:
        raise MempoolPolicyError("coinbase transactions are not relayed through the mempool")
    if tx.weight() > MAX_STANDARD_TX_WEIGHT:
        raise MempoolPolicyError("transaction exceeds standard transaction weight")
    if len(mempool) >= MAX_MEMPOOL_TRANSACTIONS:
        raise MempoolPolicyError("local mempool is full")
    for output in tx.outputs:
        if output_is_dust(output.amount):
            raise MempoolPolicyError("transaction creates a dust output")
    required = min_relay_fee(tx.vsize())
    if fee < required:
        raise MempoolPolicyError(f"fee below min relay policy: need at least {required} satoshis")
    if ancestor_count(tx, mempool) > MAX_ANCESTORS:
        raise MempoolPolicyError("transaction exceeds ancestor limit")
    for parent in mempool:
        if descendant_count(parent, mempool) > MAX_DESCENDANTS:
            raise MempoolPolicyError("mempool exceeds descendant limit")


def replacement_allowed(new_tx: Transaction, new_fee: int, conflicts: Sequence[Tuple[Transaction, int]]) -> bool:
    """Simple opt-in RBF rule: conflicts must signal RBF and new fee must pay more."""
    if not conflicts:
        return True
    old_fee_total = sum(fee for _tx, fee in conflicts)
    old_vsize_total = sum(max(1, tx.vsize()) for tx, _fee in conflicts)
    if any(not tx.signals_rbf for tx, _fee in conflicts):
        return False
    required_delta = min_relay_fee(old_vsize_total, INCREMENTAL_RELAY_FEE)
    return new_fee >= old_fee_total + required_delta


def estimate_smart_fee(mempool: Sequence[Transaction], fee_lookup: Dict[str, int], target_blocks: int = 1) -> int:
    """Return a rough sat/vB estimate based on the local mempool."""
    rates = []
    for tx in mempool:
        fee = fee_lookup.get(tx.txid())
        if fee is not None:
            rates.append(fee / max(1, tx.vsize()))
    if not rates:
        return MIN_RELAY_FEE_PER_KB // 1000
    base = median(rates)
    multiplier = 1.0 + max(0, 6 - target_blocks) * 0.1
    return max(1, int(base * multiplier))
