"""BIP158-style compact block filters (Golomb-Coded Sets) for NetCoin.

A compact filter is a small, probabilistic summary of the scripts a block paid
to. A light client downloads the filter (tiny), tests its own addresses against
it, and only fetches the full block when the filter says it *might* match. This
lets a wallet sync without downloading every block.

This is BIP158-*style*, not byte-for-byte Bitcoin: the Golomb-Rice coding of
sorted, hashed elements is faithful, but the per-element hash uses SHA-256 (keyed
by the block hash) rather than SipHash, and elements are NetCoin's text
scriptPubkeys. False-positive rate is ~1/M; there are no false negatives.

BIP157 filter headers chain each filter to the previous one so a light client can
verify it received the right filters from a single trusted checkpoint.
"""
from __future__ import annotations

import hashlib
from typing import Iterable, List, Set, Tuple

# Golomb-Rice parameter (P) and per-element modulus (M); FP rate ~= 1/M.
GOLOMB_P = 19
FILTER_M = 784931


def _d256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _encode_varint(value: int) -> bytes:
    if value < 0xFD:
        return bytes([value])
    if value <= 0xFFFF:
        return b"\xfd" + value.to_bytes(2, "little")
    if value <= 0xFFFFFFFF:
        return b"\xfe" + value.to_bytes(4, "little")
    return b"\xff" + value.to_bytes(8, "little")


def _decode_varint(data: bytes) -> Tuple[int, bytes]:
    first = data[0]
    if first < 0xFD:
        return first, data[1:]
    if first == 0xFD:
        return int.from_bytes(data[1:3], "little"), data[3:]
    if first == 0xFE:
        return int.from_bytes(data[1:5], "little"), data[5:]
    return int.from_bytes(data[1:9], "little"), data[9:]


class _BitWriter:
    def __init__(self) -> None:
        self._bits: List[int] = []

    def write_unary(self, quotient: int) -> None:
        self._bits.extend([1] * quotient)
        self._bits.append(0)

    def write_bits(self, value: int, count: int) -> None:
        for i in range(count - 1, -1, -1):
            self._bits.append((value >> i) & 1)

    def to_bytes(self) -> bytes:
        out = bytearray()
        for i in range(0, len(self._bits), 8):
            chunk = self._bits[i : i + 8]
            byte = 0
            for bit in chunk:
                byte = (byte << 1) | bit
            byte <<= 8 - len(chunk)  # pad the final byte with zero bits
            out.append(byte)
        return bytes(out)


class _BitReader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def read_bit(self) -> int:
        if self._pos >= len(self._data) * 8:
            return 0  # reading into the zero padding is fine
        byte = self._data[self._pos // 8]
        bit = (byte >> (7 - (self._pos % 8))) & 1
        self._pos += 1
        return bit

    def read_unary(self) -> int:
        quotient = 0
        while self.read_bit() == 1:
            quotient += 1
        return quotient

    def read_bits(self, count: int) -> int:
        value = 0
        for _ in range(count):
            value = (value << 1) | self.read_bit()
        return value


def _filter_key(block_hash_hex: str) -> bytes:
    # BIP158 keys the hash with the block hash; we use its first 16 bytes.
    return bytes.fromhex(block_hash_hex)[:16]


def _hash_to_range(element: bytes, key: bytes, modulus: int) -> int:
    return int.from_bytes(hashlib.sha256(key + element).digest(), "big") % modulus


def build_filter(elements: Iterable[bytes], key: bytes) -> bytes:
    """Build a GCS filter (varint N || Golomb-Rice coded sorted hashes)."""
    unique = set(elements)
    n = len(unique)
    if n == 0:
        return _encode_varint(0)
    field = n * FILTER_M
    hashes = sorted(_hash_to_range(e, key, field) for e in unique)
    writer = _BitWriter()
    last = 0
    for value in hashes:
        delta = value - last
        last = value
        writer.write_unary(delta >> GOLOMB_P)
        writer.write_bits(delta & ((1 << GOLOMB_P) - 1), GOLOMB_P)
    return _encode_varint(n) + writer.to_bytes()


def filter_match(filter_bytes: bytes, key: bytes, target: bytes) -> bool:
    n, body = _decode_varint(filter_bytes)
    if n == 0:
        return False
    field = n * FILTER_M
    target_hash = _hash_to_range(target, key, field)
    reader = _BitReader(body)
    last = 0
    for _ in range(n):
        delta = (reader.read_unary() << GOLOMB_P) | reader.read_bits(GOLOMB_P)
        last += delta
        if last == target_hash:
            return True
        if last > target_hash:
            return False  # the set is sorted, so we can stop early
    return False


# --- block-level helpers ---------------------------------------------------- #

def block_filter_elements(block) -> Set[bytes]:
    """The set summarized by a block's filter: every output scriptPubkey.

    This catches payments *to* a script (the light-client "did I get paid?"
    query). Spends are not summarized (that needs prevout lookups), so a light
    client detects receives via the filter and tracks its own spends locally.
    """
    elements: Set[bytes] = set()
    for tx in block.transactions:
        for output in tx.outputs:
            script = output.effective_script_pubkey()
            if script:
                elements.add(script.encode("utf-8"))
    return elements


def build_block_filter(block) -> bytes:
    return build_filter(block_filter_elements(block), _filter_key(block.hash()))


def block_filter_match(filter_bytes: bytes, block_hash_hex: str, script_pubkey: str) -> bool:
    """True if `script_pubkey` (a NetCoin text script) might be in the block."""
    return filter_match(filter_bytes, _filter_key(block_hash_hex), script_pubkey.encode("utf-8"))


def filter_hash(filter_bytes: bytes) -> str:
    return _d256(filter_bytes).hex()


def compute_filter_header(filter_bytes: bytes, prev_header_hex: str) -> str:
    """BIP157 filter header: d256(filter_hash || prev_filter_header)."""
    prev = bytes.fromhex(prev_header_hex) if prev_header_hex else b"\x00" * 32
    return _d256(_d256(filter_bytes) + prev).hex()
