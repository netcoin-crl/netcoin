"""Block, Merkle tree, and proof-of-work helpers for NetCoin."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from .crypto import double_sha256
from .params import MAX_BLOCK_WEIGHT, POW_LIMIT_BITS, ZERO_HASH
from .tx import Transaction, canonical_json


class BlockError(ValueError):
    """Raised when a block is malformed or invalid."""


@dataclass
class BlockHeader:
    version: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    bits: int
    nonce: int
    height: int

    def __post_init__(self) -> None:
        self.version = int(self.version)
        self.previous_hash = self.previous_hash.lower()
        self.merkle_root = self.merkle_root.lower()
        self.timestamp = int(self.timestamp)
        self.bits = int(self.bits)
        self.nonce = int(self.nonce)
        self.height = int(self.height)
        for name, value in (("previous_hash", self.previous_hash), ("merkle_root", self.merkle_root)):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise BlockError(f"{name} must be a 32-byte lowercase hex string")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "bits": self.bits,
            "nonce": self.nonce,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlockHeader":
        return cls(
            version=int(data["version"]),
            previous_hash=str(data["previous_hash"]),
            merkle_root=str(data["merkle_root"]),
            timestamp=int(data["timestamp"]),
            bits=int(data["bits"]),
            nonce=int(data["nonce"]),
            height=int(data["height"]),
        )

    def serialize(self) -> bytes:
        return canonical_json(self.to_dict())

    def hash(self) -> str:
        return double_sha256(self.serialize()).hex()

    def to_bytes(self) -> bytes:
        from .serialization import serialize_header

        return serialize_header(self)

    def raw_hex(self) -> str:
        return self.to_bytes().hex()


@dataclass
class Block:
    header: BlockHeader
    transactions: List[Transaction]

    def __post_init__(self) -> None:
        if not self.transactions:
            raise BlockError("block must contain at least one transaction")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "header": self.header.to_dict(),
            "transactions": [tx.to_dict(include_scripts=True, include_witness=True) for tx in self.transactions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        return cls(
            header=BlockHeader.from_dict(data["header"]),
            transactions=[Transaction.from_dict(item) for item in data["transactions"]],
        )

    def hash(self) -> str:
        return self.header.hash()

    def to_bytes(self, include_witness: bool = True) -> bytes:
        from .serialization import serialize_block

        return serialize_block(self, include_witness=include_witness)

    def raw_hex(self, include_witness: bool = True) -> str:
        return self.to_bytes(include_witness=include_witness).hex()

    def weight(self) -> int:
        from .serialization import block_weight

        return block_weight(self)

    def total_fees_placeholder(self) -> int:
        return 0

    def weight(self) -> int:
        # Bitcoin weighs the 80-byte header at 4x and discounts witness data.
        # NetCoin uses JSON for storage, so this is an approximate policy/consensus
        # weight that still enforces the same block-weight concept.
        header_weight = len(self.header.serialize()) * 4
        return header_weight + sum(tx.weight() for tx in self.transactions)

    def is_over_weight_limit(self) -> bool:
        return self.weight() > MAX_BLOCK_WEIGHT


def merkle_root(transactions: Iterable[Transaction]) -> str:
    tx_hashes = [bytes.fromhex(tx.txid()) for tx in transactions]
    if not tx_hashes:
        return ZERO_HASH
    layer = tx_hashes
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        next_layer = []
        for i in range(0, len(layer), 2):
            next_layer.append(double_sha256(layer[i] + layer[i + 1]))
        layer = next_layer
    return layer[0].hex()



def witness_merkle_root(transactions: Iterable[Transaction]) -> str:
    tx_hashes = [bytes.fromhex(tx.wtxid()) for tx in transactions]
    if not tx_hashes:
        return ZERO_HASH
    layer = tx_hashes
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        next_layer = []
        for i in range(0, len(layer), 2):
            next_layer.append(double_sha256(layer[i] + layer[i + 1]))
        layer = next_layer
    return layer[0].hex()


WITNESS_RESERVED_VALUE = "00" * 32
WITNESS_COMMITMENT_PREFIX = "OP_RETURN NETCOIN_WITNESS_COMMITMENT"


def witness_commitment_root(transactions: Iterable[Transaction]) -> str:
    """Return the witness merkle root used for NetCoin's SegWit-style commitment.

    Like Bitcoin's witness commitment idea, the coinbase witness hash is treated
    as zero so the commitment can be placed inside the coinbase without becoming
    circular. Non-coinbase transactions use their wtxid values.
    """
    txs = list(transactions)
    if not txs:
        return ZERO_HASH
    tx_hashes = [bytes.fromhex(ZERO_HASH)]
    tx_hashes.extend(bytes.fromhex(tx.wtxid()) for tx in txs[1:])
    layer = tx_hashes
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        next_layer = []
        for i in range(0, len(layer), 2):
            next_layer.append(double_sha256(layer[i] + layer[i + 1]))
        layer = next_layer
    return layer[0].hex()


def witness_commitment(transactions: Iterable[Transaction], reserved_value_hex: str = WITNESS_RESERVED_VALUE) -> str:
    """Commit to all transaction witnesses using root || reserved_value.

    This is an educational BIP141-shaped rule, not byte-for-byte Bitcoin: the
    commitment is encoded as a zero-value coinbase OP_RETURN script:
    OP_RETURN NETCOIN_WITNESS_COMMITMENT <hex>.
    """
    reserved = bytes.fromhex(reserved_value_hex)
    if len(reserved) != 32:
        raise BlockError("witness reserved value must be 32 bytes")
    return double_sha256(bytes.fromhex(witness_commitment_root(transactions)) + reserved).hex()


def coinbase_witness_commitment(block: "Block") -> str | None:
    """Extract the last NetCoin witness commitment from the coinbase, if present."""
    if not block.transactions:
        return None
    for output in reversed(block.transactions[0].outputs):
        script = getattr(output, "script_pubkey", "") or ""
        if script.startswith(WITNESS_COMMITMENT_PREFIX + " "):
            parts = script.split()
            if len(parts) == 3 and len(parts[2]) == 64:
                return parts[2].lower()
    return None


def block_requires_witness_commitment(block: "Block") -> bool:
    """True when a block includes non-coinbase witness data."""
    return any(tx.has_witness for tx in block.transactions[1:])


def validate_witness_commitment(block: "Block") -> bool:
    if not block_requires_witness_commitment(block):
        return True
    found = coinbase_witness_commitment(block)
    if found is None:
        return False
    return found == witness_commitment(block.transactions)

def bits_to_target(bits: int) -> int:
    exponent = bits >> 24
    mantissa = bits & 0x007FFFFF
    negative = bits & 0x00800000
    if negative:
        raise BlockError("negative compact targets are not allowed")
    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        target = mantissa << (8 * (exponent - 3))
    if target <= 0:
        raise BlockError("proof-of-work target must be positive")
    pow_limit = compact_to_target_unchecked(POW_LIMIT_BITS)
    if target > pow_limit:
        raise BlockError("proof-of-work target exceeds POW limit")
    return target


def compact_to_target_unchecked(bits: int) -> int:
    exponent = bits >> 24
    mantissa = bits & 0x007FFFFF
    if exponent <= 3:
        return mantissa >> (8 * (3 - exponent))
    return mantissa << (8 * (exponent - 3))


def target_to_bits(target: int) -> int:
    if target <= 0:
        raise BlockError("target must be positive")
    pow_limit = compact_to_target_unchecked(POW_LIMIT_BITS)
    if target > pow_limit:
        target = pow_limit
    raw = target.to_bytes(32, "big").lstrip(b"\x00")
    if not raw:
        return 0
    exponent = len(raw)
    if raw[0] & 0x80:
        exponent += 1
        mantissa_bytes = b"\x00" + raw[:2]
    else:
        mantissa_bytes = raw[:3]
    mantissa_bytes = mantissa_bytes.ljust(3, b"\x00")
    mantissa = int.from_bytes(mantissa_bytes, "big")
    return (exponent << 24) | mantissa


def block_hash_int(block_hash: str) -> int:
    return int(block_hash, 16)


def check_proof_of_work(header: BlockHeader) -> bool:
    target = bits_to_target(header.bits)
    return block_hash_int(header.hash()) <= target


def mine_header(header: BlockHeader, max_nonce: int = 2**32 - 1) -> BlockHeader:
    target = bits_to_target(header.bits)
    nonce = header.nonce
    while nonce <= max_nonce:
        header.nonce = nonce
        if block_hash_int(header.hash()) <= target:
            return header
        nonce += 1
    raise BlockError("nonce space exhausted; change timestamp or coinbase extra nonce")


def make_block(previous_hash: str, height: int, bits: int, transactions: List[Transaction],
               timestamp: int | None = None) -> Block:
    root = merkle_root(transactions)
    header = BlockHeader(
        version=1,
        previous_hash=previous_hash,
        merkle_root=root,
        timestamp=int(time.time()) if timestamp is None else int(timestamp),
        bits=bits,
        nonce=0,
        height=height,
    )
    return Block(header=mine_header(header), transactions=transactions)


def cumulative_work(blocks: Iterable[Block]) -> int:
    work = 0
    two_256 = 1 << 256
    for block in blocks:
        target = bits_to_target(block.header.bits)
        work += two_256 // (target + 1)
    return work

# Override any earlier educational approximation with the serialization-based
# block weight used by the v2 CLI/RPC.
def _block_weight(self: Block) -> int:
    from .serialization import block_weight

    return block_weight(self)


def _block_is_over_weight_limit(self: Block) -> bool:
    from .params import MAX_BLOCK_WEIGHT

    return _block_weight(self) > MAX_BLOCK_WEIGHT


Block.weight = _block_weight  # type: ignore[assignment]
Block.is_over_weight_limit = _block_is_over_weight_limit  # type: ignore[assignment]
