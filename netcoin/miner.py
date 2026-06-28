"""External miner helpers for NetCoin."""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

from .block import Block, BlockError, BlockHeader, check_proof_of_work, mine_header, merkle_root, witness_commitment
from .params import MAX_BLOCK_WEIGHT
from .tx import Transaction, create_coinbase_transaction


class MinerError(ValueError):
    """Raised when a remote mining job cannot be solved."""


def transactions_from_template(template: Dict[str, Any]) -> List[Transaction]:
    transactions = []
    for item in template.get("transactions", []):
        tx_data = item.get("tx") if isinstance(item, dict) else None
        if tx_data:
            transactions.append(Transaction.from_dict(tx_data))
    return transactions


def solve_template(
    template: Dict[str, Any],
    payout_address: str,
    *,
    max_extra_nonce: int = 1_000_000,
    timestamp: Optional[int] = None,
) -> Block:
    height = int(template["height"])
    previous_hash = str(template["previous_hash"])
    bits = int(template["bits"])
    reward = int(template["coinbase_value"])
    block_time = int(timestamp or time.time())
    selected = transactions_from_template(template)

    for extra_nonce in range(max_extra_nonce + 1):
        coinbase = create_coinbase_transaction(height, payout_address, reward, extra_nonce=extra_nonce)
        transactions = [coinbase] + selected
        if any(tx.has_witness for tx in selected):
            commit = witness_commitment(transactions)
            coinbase = create_coinbase_transaction(
                height, payout_address, reward, extra_nonce=extra_nonce, witness_commitment=commit
            )
            transactions = [coinbase] + selected
        header = BlockHeader(
            version=int(template.get("version", 1)),
            previous_hash=previous_hash,
            merkle_root=merkle_root(transactions),
            timestamp=block_time,
            bits=bits,
            nonce=0,
            height=height,
        )
        try:
            solved_header = mine_header(header)
        except BlockError:
            block_time = int(time.time())
            continue
        block = Block(header=solved_header, transactions=transactions)
        if block.weight() > int(template.get("max_block_weight", MAX_BLOCK_WEIGHT)):
            raise MinerError("solved block exceeds maximum block weight")
        if not check_proof_of_work(block.header):
            raise MinerError("solved header does not satisfy proof of work")
        return block

    raise MinerError("failed to solve template after many coinbase extra nonces")


def block_summary(block: Block) -> Dict[str, Any]:
    return {
        "hash": block.hash(),
        "height": block.header.height,
        "previous_hash": block.header.previous_hash,
        "txs": len(block.transactions),
        "nonce": block.header.nonce,
        "timestamp": block.header.timestamp,
        "weight": block.weight(),
    }
