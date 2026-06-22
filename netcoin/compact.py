"""Compact block relay helpers for NetCoin.

This is a small version of the idea behind Bitcoin's compact blocks: announce a
block header plus short transaction identifiers, include a few prefilled
transactions such as the coinbase, and let peers request only the transactions
they are missing before reconstructing the block.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .block import Block, BlockHeader
from .tx import Transaction


class CompactBlockError(ValueError):
    """Raised when compact-block reconstruction cannot finish."""


@dataclass
class CompactBlock:
    header: BlockHeader
    shortids: List[str]
    prefilled: Dict[int, Transaction]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "header": self.header.to_dict() | {"hash": self.header.hash()},
            "shortids": self.shortids,
            "prefilled": {str(index): tx.to_dict(include_scripts=True, include_witness=True) for index, tx in self.prefilled.items()},
            "total_transactions": len(self.shortids) + len(self.prefilled),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompactBlock":
        header_data = dict(data["header"])
        header_data.pop("hash", None)
        return cls(
            header=BlockHeader.from_dict(header_data),
            shortids=[str(item) for item in data["shortids"]],
            prefilled={int(index): Transaction.from_dict(tx) for index, tx in data.get("prefilled", {}).items()},
        )


def short_txid(txid: str) -> str:
    # A real compact block uses SipHash keyed by header nonce. NetCoin keeps a
    # deterministic 48-bit prefix for readability and easy tests.
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


def _tx_by_shortid(transactions: Iterable[Transaction]) -> Dict[str, Transaction]:
    by_shortid: Dict[str, Transaction] = {}
    for tx in transactions:
        sid = short_txid(tx.txid())
        # A short-id collision makes reconstruction ambiguous. Real compact blocks
        # fall back to fetching full transactions; NetCoin treats it as missing.
        if sid in by_shortid:
            by_shortid.pop(sid, None)
        else:
            by_shortid[sid] = tx
    return by_shortid


def compact_block_positions(compact: CompactBlock) -> List[Tuple[int, str]]:
    """Return (transaction_index, shortid) entries for non-prefilled txs."""
    result: List[Tuple[int, str]] = []
    short_iter = iter(compact.shortids)
    total = len(compact.shortids) + len(compact.prefilled)
    for index in range(total):
        if index in compact.prefilled:
            continue
        result.append((index, next(short_iter)))
    return result


def missing_transactions(compact: CompactBlock, mempool: Iterable[Transaction]) -> List[Dict[str, Any]]:
    """List compact-block shortids that cannot be filled from this mempool."""
    by_shortid = _tx_by_shortid(mempool)
    missing: List[Dict[str, Any]] = []
    for index, sid in compact_block_positions(compact):
        if sid not in by_shortid:
            missing.append({"index": index, "shortid": sid})
    return missing


def reconstruct_compact_block(
    compact: CompactBlock,
    mempool: Iterable[Transaction],
    extra_transactions: Optional[Iterable[Transaction]] = None,
) -> Block:
    by_shortid = _tx_by_shortid(mempool)
    if extra_transactions:
        by_shortid.update(_tx_by_shortid(extra_transactions))
    txs: List[Transaction] = []
    missing: List[Dict[str, Any]] = []
    short_iter = iter(compact.shortids)
    total = len(compact.shortids) + len(compact.prefilled)
    for index in range(total):
        if index in compact.prefilled:
            txs.append(compact.prefilled[index])
            continue
        sid = next(short_iter)
        tx = by_shortid.get(sid)
        if tx is None:
            missing.append({"index": index, "shortid": sid})
            # Keep scanning to report every missing tx.
            continue
        txs.append(tx)
    if missing:
        raise CompactBlockError(f"missing compact block transactions: {missing}")
    return Block(header=compact.header, transactions=txs)


def compact_missing_payload(block: Block, have_shortids: Sequence[str]) -> Dict[str, Any]:
    """Return full transactions from block that a peer says it is missing.

    The peer passes shortids it already has; the response includes the remaining
    non-coinbase transactions so it can complete reconstruction.
    """
    have = {str(item) for item in have_shortids}
    missing = []
    for index, tx in enumerate(block.transactions):
        sid = short_txid(tx.txid())
        if index == 0 or sid in have:
            continue
        missing.append({
            "index": index,
            "shortid": sid,
            "txid": tx.txid(),
            "tx": tx.to_dict(include_scripts=True, include_witness=True),
        })
    return {"block_hash": block.hash(), "missing": missing}
