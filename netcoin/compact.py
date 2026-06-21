"""Compact block relay helpers for NetCoin.

This is a small version of the idea behind Bitcoin's compact blocks: announce a
block header plus short transaction identifiers, and include a few prefilled
transactions such as the coinbase. Peers that already have the transactions in
their mempool can reconstruct the block with less bandwidth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .block import Block, BlockHeader
from .tx import Transaction


@dataclass
class CompactBlock:
    header: BlockHeader
    shortids: List[str]
    prefilled: Dict[int, Transaction]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "header": self.header.to_dict(),
            "shortids": self.shortids,
            "prefilled": {str(index): tx.to_dict(include_scripts=True, include_witness=True) for index, tx in self.prefilled.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompactBlock":
        return cls(
            header=BlockHeader.from_dict(data["header"]),
            shortids=[str(item) for item in data["shortids"]],
            prefilled={int(index): Transaction.from_dict(tx) for index, tx in data.get("prefilled", {}).items()},
        )


def short_txid(txid: str) -> str:
    # A real compact block uses SipHash keyed by header nonce. NetCoin keeps a
    # deterministic 48-bit prefix for readability.
    return txid[:12]


def make_compact_block(block: Block, prefill_indexes: Optional[Iterable[int]] = None) -> CompactBlock:
    prefill = set(prefill_indexes if prefill_indexes is not None else [0])
    shortids = []
    prefilled: Dict[int, Transaction] = {}
    for index, tx in enumerate(block.transactions):
        if index in prefill:
            prefilled[index] = tx
        else:
            shortids.append(short_txid(tx.txid()))
    return CompactBlock(header=block.header, shortids=shortids, prefilled=prefilled)


def reconstruct_compact_block(compact: CompactBlock, mempool: Iterable[Transaction]) -> Block:
    by_shortid = {short_txid(tx.txid()): tx for tx in mempool}
    txs: List[Transaction] = []
    short_iter = iter(compact.shortids)
    total = len(compact.shortids) + len(compact.prefilled)
    for index in range(total):
        if index in compact.prefilled:
            txs.append(compact.prefilled[index])
            continue
        sid = next(short_iter)
        if sid not in by_shortid:
            raise ValueError(f"missing transaction for compact shortid {sid}")
        txs.append(by_shortid[sid])
    return Block(header=compact.header, transactions=txs)
