"""BIP32 hierarchical-deterministic key derivation + BIP39-style seed.

One mnemonic/seed derives an unlimited tree of keys, so a wallet backs up a single
secret and generates endless addresses (and watch-only `xpub` branches). This is
standard BIP32 — verified against the official BIP32 test vectors — so extended
keys serialize as the usual `xprv`/`xpub`. The leaf keys then produce NetCoin
addresses via NetCoin's own address encodings.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from .crypto import (
    G,
    N,
    base58check_decode,
    base58check_encode,
    hash160,
    point_add,
    private_key_to_public_key,
    scalar_mult,
)

HARDENED = 0x80000000
XPRV_VERSION = bytes.fromhex("0488ade4")
XPUB_VERSION = bytes.fromhex("0488b21e")


class HDError(ValueError):
    pass


def _ser32(value: int) -> bytes:
    return value.to_bytes(4, "big")


def _ser256(value: int) -> bytes:
    return value.to_bytes(32, "big")


def _compress_point(point: tuple[int, int]) -> bytes:
    x, y = point
    return (b"\x03" if (y & 1) else b"\x02") + x.to_bytes(32, "big")


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    """BIP39 seed: PBKDF2-HMAC-SHA512(mnemonic, "mnemonic"+passphrase, 2048)."""
    return hashlib.pbkdf2_hmac(
        "sha512",
        mnemonic.encode("utf-8"),
        ("mnemonic" + passphrase).encode("utf-8"),
        2048,
        dklen=64,
    )


def parse_path(path: str) -> list[int]:
    parts = path.strip().split("/")
    if parts and parts[0] in ("m", "M"):
        parts = parts[1:]
    indexes: list[int] = []
    for part in parts:
        if not part:
            continue
        hardened = part[-1] in ("'", "h", "H")
        number = int(part[:-1] if hardened else part)
        if number < 0 or number >= HARDENED:
            raise HDError(f"index out of range: {part}")
        indexes.append(number + HARDENED if hardened else number)
    return indexes


@dataclass
class HDKey:
    """A BIP32 node. Holds a private key, or (for xpub branches) just a point."""

    chain_code: bytes
    key: int = 0  # private scalar; 0 when public-only
    point: tuple[int, int] | None = None  # public point; set when public-only
    depth: int = 0
    parent_fingerprint: bytes = b"\x00\x00\x00\x00"
    child_number: int = 0

    @property
    def private(self) -> bool:
        return self.point is None

    # --- construction ---

    @classmethod
    def from_seed(cls, seed: bytes) -> HDKey:
        digest = hmac.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
        left, right = digest[:32], digest[32:]
        secret = int.from_bytes(left, "big")
        if secret == 0 or secret >= N:
            raise HDError("seed produced an invalid master key")
        return cls(chain_code=right, key=secret)

    @classmethod
    def from_mnemonic(cls, mnemonic: str, passphrase: str = "") -> HDKey:
        return cls.from_seed(mnemonic_to_seed(mnemonic, passphrase))

    # --- key material ---

    @property
    def public_key(self) -> bytes:
        if self.private:
            return private_key_to_public_key(self.key, compressed=True)
        return _compress_point(self.point)

    def fingerprint(self) -> bytes:
        return hash160(self.public_key)[:4]

    def neuter(self) -> HDKey:
        """Return the watch-only (public-only) version of this node."""
        if not self.private:
            return self
        return HDKey(
            chain_code=self.chain_code,
            point=scalar_mult(self.key, G),
            depth=self.depth,
            parent_fingerprint=self.parent_fingerprint,
            child_number=self.child_number,
        )

    # --- derivation ---

    def derive(self, index: int) -> HDKey:
        hardened = index >= HARDENED
        if self.private:
            data = (b"\x00" + _ser256(self.key) if hardened else self.public_key) + _ser32(index)
            digest = hmac.new(self.chain_code, data, hashlib.sha512).digest()
            il = int.from_bytes(digest[:32], "big")
            if il >= N:
                raise HDError("invalid child key; try the next index")
            child_secret = (il + self.key) % N
            if child_secret == 0:
                raise HDError("invalid child key; try the next index")
            return HDKey(
                chain_code=digest[32:],
                key=child_secret,
                depth=self.depth + 1,
                parent_fingerprint=self.fingerprint(),
                child_number=index,
            )
        if hardened:
            raise HDError("cannot derive a hardened child from a public key")
        data = self.public_key + _ser32(index)
        digest = hmac.new(self.chain_code, data, hashlib.sha512).digest()
        il = int.from_bytes(digest[:32], "big")
        if il >= N:
            raise HDError("invalid child key; try the next index")
        child_point = point_add(scalar_mult(il, G), self.point)
        if child_point is None:
            raise HDError("invalid child key; try the next index")
        return HDKey(
            chain_code=digest[32:],
            point=child_point,
            depth=self.depth + 1,
            parent_fingerprint=self.fingerprint(),
            child_number=index,
        )

    def derive_path(self, path: str) -> HDKey:
        node = self
        for index in parse_path(path):
            node = node.derive(index)
        return node

    # --- serialization ---

    def extended_private_key(self) -> str:
        if not self.private:
            raise HDError("no private key to export")
        payload = (
            XPRV_VERSION
            + bytes([self.depth])
            + self.parent_fingerprint
            + _ser32(self.child_number)
            + self.chain_code
            + b"\x00"
            + _ser256(self.key)
        )
        return base58check_encode(payload)

    def extended_public_key(self) -> str:
        payload = (
            XPUB_VERSION
            + bytes([self.depth])
            + self.parent_fingerprint
            + _ser32(self.child_number)
            + self.chain_code
            + self.public_key
        )
        return base58check_encode(payload)

    @classmethod
    def from_extended_key(cls, text: str) -> HDKey:
        payload = base58check_decode(text)
        if len(payload) != 78:
            raise HDError("bad extended key length")
        version = payload[:4]
        depth = payload[4]
        parent_fp = payload[5:9]
        child_number = int.from_bytes(payload[9:13], "big")
        chain_code = payload[13:45]
        key_data = payload[45:78]
        if version == XPRV_VERSION:
            if key_data[0] != 0:
                raise HDError("bad xprv key data")
            return cls(
                chain_code=chain_code,
                key=int.from_bytes(key_data[1:], "big"),
                depth=depth,
                parent_fingerprint=parent_fp,
                child_number=child_number,
            )
        if version == XPUB_VERSION:
            prefix = key_data[0]
            x = int.from_bytes(key_data[1:], "big")
            y_sq = (pow(x, 3, _P) + 7) % _P
            y = pow(y_sq, (_P + 1) // 4, _P)
            if (y & 1) != (prefix & 1):
                y = _P - y
            return cls(
                chain_code=chain_code,
                point=(x, y),
                depth=depth,
                parent_fingerprint=parent_fp,
                child_number=child_number,
            )
        raise HDError("unknown extended-key version")


# secp256k1 field prime, for decompressing xpub points.
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
