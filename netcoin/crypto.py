"""Small cryptographic toolkit for NetCoin.

The implementation is intentionally pure Python and readable. It includes the
pieces NetCoin needs for a Bitcoin-like educational chain: SHA-256, HASH160,
Base58Check, Bech32/Bech32m, ECDSA over secp256k1, and a compact BIP340-style
Schnorr signature implementation for Taproot-like outputs.

Do not use this as production wallet software. Production cryptography should
use well-reviewed constant-time libraries.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
from typing import Dict, Iterable, List, Optional, Tuple

from .params import P2PKH_ADDRESS_VERSION, P2SH_ADDRESS_VERSION, WITNESS_HRP

Point = Optional[Tuple[int, int]]

# secp256k1 domain parameters.
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
A = 0
B = 7
G_X = 55066263022277343669578718895168534326250603453777594175500187360389116729240
G_Y = 32670510020758816978083085130507043184471273380659243275938904335757337482424
G: Point = (G_X, G_Y)
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BECH32_ALPHABET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
BECH32M_CONST = 0x2BC830A3


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def double_sha256(data: bytes) -> bytes:
    return sha256(sha256(data))


def hash160(data: bytes) -> bytes:
    sha = sha256(data)
    try:
        ripe = hashlib.new("ripemd160")
    except ValueError as exc:  # pragma: no cover - depends on OpenSSL build
        raise RuntimeError("RIPEMD-160 is not available in this Python build") from exc
    ripe.update(sha)
    return ripe.digest()


def bytes_to_hex(data: bytes) -> str:
    return data.hex()


def hex_to_bytes(value: str) -> bytes:
    return bytes.fromhex(value)


# ---------------------------------------------------------------------------
# Base58Check
# ---------------------------------------------------------------------------


def base58_encode(data: bytes) -> str:
    number = int.from_bytes(data, "big")
    encoded = ""
    while number > 0:
        number, remainder = divmod(number, 58)
        encoded = BASE58_ALPHABET[remainder] + encoded
    leading_zeroes = len(data) - len(data.lstrip(b"\x00"))
    return "1" * leading_zeroes + (encoded or "")


def base58_decode(text: str) -> bytes:
    number = 0
    for char in text:
        if char not in BASE58_ALPHABET:
            raise ValueError(f"invalid Base58 character: {char!r}")
        number = number * 58 + BASE58_ALPHABET.index(char)
    payload = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    leading_ones = len(text) - len(text.lstrip("1"))
    return b"\x00" * leading_ones + payload


def base58check_encode(payload: bytes) -> str:
    checksum = double_sha256(payload)[:4]
    return base58_encode(payload + checksum)


def base58check_decode(text: str) -> bytes:
    decoded = base58_decode(text)
    if len(decoded) < 5:
        raise ValueError("Base58Check payload is too short")
    payload, checksum = decoded[:-4], decoded[-4:]
    if double_sha256(payload)[:4] != checksum:
        raise ValueError("invalid Base58Check checksum")
    return payload


# ---------------------------------------------------------------------------
# Bech32 / Bech32m
# ---------------------------------------------------------------------------


def bech32_hrp_expand(hrp: str) -> List[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def bech32_polymod(values: Iterable[int]) -> int:
    generator = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            if (top >> i) & 1:
                chk ^= generator[i]
    return chk


def bech32_create_checksum(hrp: str, data: List[int], spec: str = "bech32") -> List[int]:
    const = 1 if spec == "bech32" else BECH32M_CONST
    values = bech32_hrp_expand(hrp) + data
    polymod = bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ const
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def bech32_verify_checksum(hrp: str, data: List[int]) -> Optional[str]:
    check = bech32_polymod(bech32_hrp_expand(hrp) + data)
    if check == 1:
        return "bech32"
    if check == BECH32M_CONST:
        return "bech32m"
    return None


def bech32_encode(hrp: str, data: List[int], spec: str = "bech32") -> str:
    combined = data + bech32_create_checksum(hrp, data, spec)
    return hrp + "1" + "".join(BECH32_ALPHABET[d] for d in combined)


def bech32_decode(text: str) -> Tuple[str, List[int], str]:
    if any(ord(x) < 33 or ord(x) > 126 for x in text):
        raise ValueError("invalid Bech32 character range")
    if text.lower() != text and text.upper() != text:
        raise ValueError("mixed-case Bech32 strings are invalid")
    text = text.lower()
    pos = text.rfind("1")
    if pos < 1 or pos + 7 > len(text) or len(text) > 90:
        raise ValueError("invalid Bech32 separator or length")
    hrp = text[:pos]
    data = []
    for char in text[pos + 1 :]:
        if char not in BECH32_ALPHABET:
            raise ValueError(f"invalid Bech32 character: {char!r}")
        data.append(BECH32_ALPHABET.index(char))
    spec = bech32_verify_checksum(hrp, data)
    if spec is None:
        raise ValueError("invalid Bech32 checksum")
    return hrp, data[:-6], spec


def convertbits(data: bytes | List[int], frombits: int, tobits: int, pad: bool = True) -> List[int]:
    acc = 0
    bits = 0
    result: List[int] = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or value >> frombits:
            raise ValueError("invalid value while converting bit groups")
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            result.append((acc >> bits) & maxv)
    if pad:
        if bits:
            result.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("invalid padding in converted bit groups")
    return result


def encode_witness_address(version: int, program: bytes, hrp: str = WITNESS_HRP) -> str:
    if not 0 <= version <= 16:
        raise ValueError("witness version out of range")
    if not 2 <= len(program) <= 40:
        raise ValueError("witness program must be 2..40 bytes")
    if version == 0 and len(program) not in (20, 32):
        raise ValueError("version 0 witness program must be 20 or 32 bytes")
    spec = "bech32" if version == 0 else "bech32m"
    data = [version] + convertbits(program, 8, 5, True)
    return bech32_encode(hrp, data, spec)


def decode_witness_address(address: str, hrp: str = WITNESS_HRP) -> Tuple[int, bytes, str]:
    got_hrp, data, spec = bech32_decode(address)
    if got_hrp != hrp:
        raise ValueError("wrong witness address human-readable part")
    if not data:
        raise ValueError("empty witness data")
    version = data[0]
    if version > 16:
        raise ValueError("witness version out of range")
    program = bytes(convertbits(data[1:], 5, 8, False))
    if not 2 <= len(program) <= 40:
        raise ValueError("witness program must be 2..40 bytes")
    if version == 0:
        if spec != "bech32":
            raise ValueError("version 0 witness address must use Bech32")
        if len(program) not in (20, 32):
            raise ValueError("version 0 witness program must be 20 or 32 bytes")
    elif spec != "bech32m":
        raise ValueError("version 1+ witness address must use Bech32m")
    return version, program, spec


# ---------------------------------------------------------------------------
# secp256k1 operations
# ---------------------------------------------------------------------------


def is_on_curve(point: Point) -> bool:
    if point is None:
        return True
    x, y = point
    return (y * y - (x * x * x + A * x + B)) % P == 0


def inverse_mod(k: int, modulus: int) -> int:
    if k == 0:
        raise ZeroDivisionError("division by zero")
    return pow(k % modulus, -1, modulus)


def point_add(p1: Point, p2: Point) -> Point:
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2

    if x1 == x2 and (y1 + y2) % P == 0:
        return None

    if p1 == p2:
        slope = (3 * x1 * x1 + A) * inverse_mod(2 * y1, P) % P
    else:
        slope = (y2 - y1) * inverse_mod(x2 - x1, P) % P

    x3 = (slope * slope - x1 - x2) % P
    y3 = (slope * (x1 - x3) - y1) % P
    return (x3, y3)


def scalar_mult(k: int, point: Point = G) -> Point:
    if k % N == 0 or point is None:
        return None
    if k < 0:
        return scalar_mult(-k, (point[0], -point[1] % P))

    result: Point = None
    addend = point
    while k:
        if k & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        k >>= 1
    return result


def generate_private_key() -> int:
    return secrets.randbelow(N - 1) + 1


def private_key_to_bytes(private_key: int) -> bytes:
    if not 1 <= private_key < N:
        raise ValueError("private key is outside the secp256k1 range")
    return private_key.to_bytes(32, "big")


def private_key_from_hex(text: str) -> int:
    value = int(text, 16)
    if not 1 <= value < N:
        raise ValueError("private key is outside the secp256k1 range")
    return value


def private_key_to_public_key(private_key: int, compressed: bool = True) -> bytes:
    point = scalar_mult(private_key, G)
    if point is None:
        raise ValueError("invalid private key")
    return encode_public_key(point, compressed=compressed)


def private_key_to_xonly_public_key(private_key: int) -> bytes:
    point = scalar_mult(private_key, G)
    if point is None:
        raise ValueError("invalid private key")
    return point[0].to_bytes(32, "big")


def encode_public_key(point: Point, compressed: bool = True) -> bytes:
    if point is None or not is_on_curve(point):
        raise ValueError("invalid public key point")
    x, y = point
    if compressed:
        prefix = b"\x02" if y % 2 == 0 else b"\x03"
        return prefix + x.to_bytes(32, "big")
    return b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")


def lift_x(x: int) -> Point:
    if x >= P:
        raise ValueError("x coordinate outside field")
    y_sq = (pow(x, 3, P) + 7) % P
    y = pow(y_sq, (P + 1) // 4, P)
    if pow(y, 2, P) != y_sq:
        raise ValueError("x coordinate is not on secp256k1")
    if y & 1:
        y = P - y
    return (x, y)


def decode_xonly_public_key(public_key: bytes) -> Point:
    if len(public_key) != 32:
        raise ValueError("x-only public key must be 32 bytes")
    return lift_x(int.from_bytes(public_key, "big"))


def decode_public_key(public_key: bytes) -> Point:
    if len(public_key) == 33 and public_key[0] in (2, 3):
        x = int.from_bytes(public_key[1:], "big")
        y_sq = (pow(x, 3, P) + B) % P
        y = pow(y_sq, (P + 1) // 4, P)
        if (y % 2 == 0) != (public_key[0] == 2):
            y = P - y
        point = (x, y)
    elif len(public_key) == 65 and public_key[0] == 4:
        point = (int.from_bytes(public_key[1:33], "big"), int.from_bytes(public_key[33:], "big"))
    else:
        raise ValueError("unsupported public key encoding")
    if not is_on_curve(point):
        raise ValueError("public key is not on secp256k1")
    return point


# ---------------------------------------------------------------------------
# Address helpers
# ---------------------------------------------------------------------------


def public_key_to_address(public_key: bytes) -> str:
    return base58check_encode(P2PKH_ADDRESS_VERSION + hash160(public_key))


def public_key_to_p2wpkh_address(public_key: bytes) -> str:
    return encode_witness_address(0, hash160(public_key))


def public_key_to_taproot_address(public_key_or_xonly: bytes) -> str:
    if len(public_key_or_xonly) == 32:
        program = public_key_or_xonly
    else:
        point = decode_public_key(public_key_or_xonly)
        program = point[0].to_bytes(32, "big")
    return encode_witness_address(1, program)


def script_hash_to_p2sh_address(script_hash: bytes) -> str:
    if len(script_hash) != 20:
        raise ValueError("P2SH script hash must be HASH160 length")
    return base58check_encode(P2SH_ADDRESS_VERSION + script_hash)


# ---------------------------------------------------------------------------
# Signed messages (Bitcoin-style signmessage / verifymessage)
# ---------------------------------------------------------------------------

# 0x18 == len("NetCoin Signed Message:\n"); mirrors Bitcoin's magic prefix.
MESSAGE_MAGIC = b"\x18NetCoin Signed Message:\n"


def _message_varint(value: int) -> bytes:
    if value < 0xFD:
        return bytes([value])
    if value <= 0xFFFF:
        return b"\xfd" + value.to_bytes(2, "little")
    if value <= 0xFFFFFFFF:
        return b"\xfe" + value.to_bytes(4, "little")
    return b"\xff" + value.to_bytes(8, "little")


def message_digest(message: str) -> bytes:
    body = message.encode("utf-8")
    return double_sha256(MESSAGE_MAGIC + _message_varint(len(body)) + body)


def _recover_public_point(digest: bytes, r: int, s: int, recid: int) -> Optional[Point]:
    x = r + (recid // 2) * N
    if x >= P:
        return None
    alpha = (pow(x, 3, P) + A * x + B) % P
    beta = pow(alpha, (P + 1) // 4, P)
    y = beta if (beta % 2) == (recid % 2) else (P - beta)
    candidate = (x, y)
    if not is_on_curve(candidate):
        return None
    e = int.from_bytes(digest, "big")
    r_inv = inverse_mod(r, N)
    s_r = scalar_mult(s, candidate)
    e_g = scalar_mult(e, G)
    neg_e_g = None if e_g is None else (e_g[0], (-e_g[1]) % P)
    return scalar_mult(r_inv, point_add(s_r, neg_e_g))


def _point_to_compressed(point: Point) -> bytes:
    x, y = point
    return (b"\x03" if (y & 1) else b"\x02") + x.to_bytes(32, "big")


def sign_message(private_key: int, message: str) -> str:
    """Sign a message, returning a base64 recoverable signature (no pubkey needed
    to verify) — the same shape as Bitcoin Core's signmessage."""
    digest = message_digest(message)
    signature = ecdsa_sign(private_key, digest)
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    target = decode_public_key(private_key_to_public_key(private_key, compressed=True))
    for recid in range(4):
        if _recover_public_point(digest, r, s, recid) == target:
            return base64.b64encode(bytes([27 + recid + 4]) + signature).decode("ascii")
    raise ValueError("unable to produce a recoverable signature")


def verify_message(address: str, message: str, signature_b64: str) -> bool:
    """Verify a signed message against an address (legacy or P2WPKH)."""
    try:
        raw = base64.b64decode(signature_b64, validate=True)
    except (binascii.Error, ValueError):
        return False
    if len(raw) != 65 or not (27 <= raw[0] <= 34):
        return False
    recid = (raw[0] - 27) & 0x03
    r = int.from_bytes(raw[1:33], "big")
    s = int.from_bytes(raw[33:65], "big")
    if not (0 < r < N and 0 < s < N):
        return False
    point = _recover_public_point(message_digest(message), r, s, recid)
    if point is None:
        return False
    pub = _point_to_compressed(point)
    candidates = {public_key_to_address(pub)}
    try:
        candidates.add(public_key_to_p2wpkh_address(pub))
    except ValueError:
        pass
    return address in candidates


def decode_address(address: str) -> Dict[str, object]:
    try:
        payload = base58check_decode(address)
        if len(payload) == 21 and payload[:1] == P2PKH_ADDRESS_VERSION:
            return {"type": "p2pkh", "hash160": payload[1:], "address": address}
        if len(payload) == 21 and payload[:1] == P2SH_ADDRESS_VERSION:
            return {"type": "p2sh", "hash160": payload[1:], "address": address}
    except ValueError:
        pass
    try:
        version, program, spec = decode_witness_address(address)
        if version == 0 and len(program) == 20:
            kind = "p2wpkh"
        elif version == 0 and len(program) == 32:
            kind = "p2wsh"
        elif version == 1 and len(program) == 32:
            kind = "p2tr"
        else:
            kind = f"witness_v{version}"
        return {"type": kind, "version": version, "program": program, "encoding": spec, "address": address}
    except ValueError:
        pass
    raise ValueError("address is not a valid NetCoin address")


def validate_address(address: str) -> bool:
    try:
        decode_address(address)
        return True
    except ValueError:
        return False


def address_to_hash160(address: str) -> bytes:
    decoded = decode_address(address)
    if decoded["type"] not in ("p2pkh", "p2sh"):
        raise ValueError("address does not contain a HASH160 payload")
    return decoded["hash160"]  # type: ignore[return-value]


def address_type(address: str) -> str:
    return str(decode_address(address)["type"])


# ---------------------------------------------------------------------------
# ECDSA
# ---------------------------------------------------------------------------


def deterministic_k(private_key: int, digest: bytes) -> int:
    """RFC 6979 deterministic nonce generation for ECDSA/SHA-256."""
    if len(digest) != 32:
        raise ValueError("digest must be 32 bytes")
    x = private_key_to_bytes(private_key)
    h1 = digest
    v = b"\x01" * 32
    k = b"\x00" * 32
    k = hmac.new(k, v + b"\x00" + x + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + x + h1, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        t = b""
        while len(t) < 32:
            v = hmac.new(k, v, hashlib.sha256).digest()
            t += v
        candidate = int.from_bytes(t[:32], "big")
        if 1 <= candidate < N:
            return candidate
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def ecdsa_sign(private_key: int, digest: bytes) -> bytes:
    if len(digest) != 32:
        raise ValueError("digest must be 32 bytes")
    z = int.from_bytes(digest, "big")
    while True:
        k = deterministic_k(private_key, digest)
        point = scalar_mult(k, G)
        if point is None:
            continue
        r = point[0] % N
        if r == 0:
            continue
        s = (inverse_mod(k, N) * (z + r * private_key)) % N
        if s == 0:
            continue
        if s > N // 2:
            s = N - s
        return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def ecdsa_verify(public_key: bytes, digest: bytes, signature: bytes) -> bool:
    if len(digest) != 32 or len(signature) != 64:
        return False
    try:
        point = decode_public_key(public_key)
    except ValueError:
        return False
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    if not (1 <= r < N and 1 <= s < N):
        return False
    z = int.from_bytes(digest, "big")
    try:
        w = inverse_mod(s, N)
    except ZeroDivisionError:
        return False
    u1 = (z * w) % N
    u2 = (r * w) % N
    check = point_add(scalar_mult(u1, G), scalar_mult(u2, point))
    if check is None:
        return False
    return check[0] % N == r


# ---------------------------------------------------------------------------
# BIP340-style Schnorr signatures for Taproot-like key path spends
# ---------------------------------------------------------------------------


def tagged_hash(tag: str, msg: bytes) -> bytes:
    tag_hash = sha256(tag.encode("ascii"))
    return sha256(tag_hash + tag_hash + msg)


def schnorr_sign(private_key: int, digest: bytes, aux_rand: Optional[bytes] = None) -> bytes:
    if len(digest) != 32:
        raise ValueError("digest must be 32 bytes")
    if aux_rand is None:
        aux_rand = b"\x00" * 32
    if len(aux_rand) != 32:
        raise ValueError("aux_rand must be 32 bytes")
    point = scalar_mult(private_key, G)
    if point is None:
        raise ValueError("invalid private key")
    d = private_key if point[1] % 2 == 0 else N - private_key
    pub = scalar_mult(d, G)
    if pub is None:
        raise ValueError("invalid private key")
    px = pub[0].to_bytes(32, "big")
    t = d.to_bytes(32, "big")
    rand = tagged_hash("BIP0340/aux", aux_rand)
    t = bytes(a ^ b for a, b in zip(t, rand))
    k0 = int.from_bytes(tagged_hash("BIP0340/nonce", t + px + digest), "big") % N
    if k0 == 0:
        raise ValueError("schnorr nonce is zero")
    r_point = scalar_mult(k0, G)
    if r_point is None:
        raise ValueError("invalid schnorr nonce")
    k = N - k0 if r_point[1] % 2 else k0
    rx = r_point[0].to_bytes(32, "big")
    e = int.from_bytes(tagged_hash("BIP0340/challenge", rx + px + digest), "big") % N
    s = (k + e * d) % N
    return rx + s.to_bytes(32, "big")


def schnorr_verify(xonly_public_key: bytes, digest: bytes, signature: bytes) -> bool:
    if len(xonly_public_key) != 32 or len(digest) != 32 or len(signature) != 64:
        return False
    try:
        pub = decode_xonly_public_key(xonly_public_key)
    except ValueError:
        return False
    r = int.from_bytes(signature[:32], "big")
    s = int.from_bytes(signature[32:], "big")
    if r >= P or s >= N:
        return False
    e = int.from_bytes(tagged_hash("BIP0340/challenge", signature[:32] + xonly_public_key + digest), "big") % N
    r_point = point_add(scalar_mult(s, G), scalar_mult(-e % N, pub))
    if r_point is None or r_point[1] % 2 != 0:
        return False
    return r_point[0] == r

# ---------------------------------------------------------------------------
# Compatibility aliases and WIF helpers for v2 CLI
# ---------------------------------------------------------------------------
try:
    from .params import WIF_VERSION
except Exception:  # pragma: no cover
    WIF_VERSION = bytes([0xB5])


def public_key_to_wpkh_address(public_key: bytes) -> str:
    return public_key_to_p2wpkh_address(public_key)


def private_key_to_wif(private_key: int, compressed: bool = True) -> str:
    suffix = b"\x01" if compressed else b""
    return base58check_encode(WIF_VERSION + private_key_to_bytes(private_key) + suffix)


def private_key_from_wif(wif: str) -> int:
    payload = base58check_decode(wif)
    if not payload.startswith(WIF_VERSION):
        raise ValueError("WIF belongs to a different network")
    body = payload[len(WIF_VERSION) :]
    if len(body) == 33 and body[-1] == 1:
        body = body[:-1]
    if len(body) != 32:
        raise ValueError("invalid WIF length")
    return private_key_from_hex(body.hex())
