"""The libsecp256k1 fast-verify path MUST accept exactly the same signatures as
the pure-Python verifier. If they ever disagree, mixed fast/pure nodes could
split on transaction validity — so this differential fuzz test is a hard gate.
"""
import secrets

import pytest

from netcoin.crypto import N, ecdsa_sign, private_key_to_public_key
from netcoin.crypto import _ecdsa_verify_pure

coincurve = pytest.importorskip("coincurve")
from netcoin.crypto import _ecdsa_verify_fast  # noqa: E402


def _cases():
    priv = 1 + secrets.randbelow(N - 1)
    pub = private_key_to_public_key(priv, compressed=True)
    other = private_key_to_public_key(1 + secrets.randbelow(N - 1), compressed=True)
    digest = secrets.token_bytes(32)
    sig = ecdsa_sign(priv, digest)
    s = int.from_bytes(sig[32:], "big")
    high_s = sig[:32] + (N - s).to_bytes(32, "big")  # valid but non-normalized
    return [
        (pub, digest, sig),                                  # valid low-s
        (pub, digest, high_s),                               # valid high-s
        (pub, secrets.token_bytes(32), sig),                 # wrong message
        (other, digest, sig),                                # wrong key
        (pub, digest, secrets.token_bytes(64)),              # garbage
        (pub, digest, (0).to_bytes(32, "big") + sig[32:]),   # r = 0
        (pub, digest, sig[:32] + (0).to_bytes(32, "big")),   # s = 0
        (pub, digest, (N).to_bytes(32, "big") + sig[32:]),   # r = N (out of range)
    ]


def test_fast_and_pure_ecdsa_agree_on_thousands_of_cases():
    mismatches = 0
    total = 0
    for _ in range(600):
        for pub, digest, sig in _cases():
            total += 1
            if _ecdsa_verify_fast(pub, digest, sig) != _ecdsa_verify_pure(pub, digest, sig):
                mismatches += 1
    assert mismatches == 0, f"{mismatches}/{total} fast/pure verify mismatches"
    assert total > 4000


def test_fast_verify_accepts_a_real_signature_and_rejects_tampering():
    priv = 0x1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF
    pub = private_key_to_public_key(priv, compressed=True)
    digest = secrets.token_bytes(32)
    sig = ecdsa_sign(priv, digest)
    assert _ecdsa_verify_fast(pub, digest, sig) is True
    tampered = sig[:-1] + bytes([sig[-1] ^ 0x01])
    assert _ecdsa_verify_fast(pub, digest, tampered) == _ecdsa_verify_pure(pub, digest, tampered)
