from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.apps.auth import should_require_signed_envelope
from netcoin.chain import Blockchain
from netcoin.crypto import (
    N,
    ecdsa_sign,
    ecdsa_verify,
    private_key_to_public_key,
    private_key_to_xonly_public_key,
    schnorr_sign,
    schnorr_verify,
)
from netcoin.signer import HardwareSigner, signer_status


def test_sqlite_is_default_chain_backend(tmp_path: Path):
    chain = Blockchain(tmp_path / "node")
    assert chain.backend == "sqlite"
    assert (tmp_path / "node" / "netcoin.sqlite").exists()
    legacy = Blockchain(tmp_path / "json-node", backend="json")
    assert legacy.backend == "json"
    assert (tmp_path / "json-node" / "chain.json").exists()


def test_tool_scripts_run_without_pythonpath(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    out = subprocess.check_output([sys.executable, str(root / "tools" / "regen_genesis.py")], cwd=tmp_path)
    payload = json.loads(out)
    assert payload["height"] == 0
    assert len(payload["genesis_hash"]) == 64


def test_signed_envelopes_required_by_default_for_public_http_sensitive_writes(monkeypatch):
    monkeypatch.delenv("NETCOIN_APP_ALLOW_UNSIGNED_SENSITIVE", raising=False)
    assert should_require_signed_envelope("POST", "/markets/demo/order", {"__netcoin_http_request": True}) is True
    assert should_require_signed_envelope("POST", "/tokens", {"__netcoin_http_request": True}) is True
    assert should_require_signed_envelope("POST", "/community/posts", {"__netcoin_http_request": True}) is False
    assert (
        should_require_signed_envelope("POST", "/markets/demo/order", {}) is False
    )  # local Python tests/tools remain compatible
    monkeypatch.setenv("NETCOIN_APP_REQUIRE_SIGNED_ENVELOPES", "1")
    assert should_require_signed_envelope("POST", "/markets/demo/order", {}) is True
    monkeypatch.setenv("NETCOIN_APP_ALLOW_UNSIGNED_SENSITIVE", "1")
    assert should_require_signed_envelope("POST", "/markets/demo/order", {"__netcoin_http_request": True}) is False


def test_bip340_reference_vector_private_key_three_zero_aux_zero_message():
    # BIP340 reference vector: secret key 3, x-only public key F930..., zero message and aux rand.
    priv = 3
    digest = bytes.fromhex("00" * 32)
    expected_pub = bytes.fromhex("F9308A019258C31049344F85F89D5229B531C845836F99B08601F113BCE036F9")
    expected_sig = bytes.fromhex(
        "E907831F80848D1069A5371B402410364BDF1C5F8307B0084C55F1CE2DCA8215"
        "25F66A4A85EA8B71E482A74F382D2CE5EBEEE8FDB2172F477DF4900D310536C0"
    )
    assert private_key_to_xonly_public_key(priv) == expected_pub
    assert schnorr_sign(priv, digest, aux_rand=b"\x00" * 32) == expected_sig
    assert schnorr_verify(expected_pub, digest, expected_sig) is True
    assert schnorr_verify(expected_pub, b"\x01" * 32, expected_sig) is False


def test_ecdsa_deterministic_nonce_low_s_and_malleability_rejection_boundaries():
    priv = 0x1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF
    digest = bytes.fromhex("42" * 32)
    sig1 = ecdsa_sign(priv, digest)
    sig2 = ecdsa_sign(priv, digest)
    assert sig1 == sig2
    r = int.from_bytes(sig1[:32], "big")
    s = int.from_bytes(sig1[32:], "big")
    assert 1 <= r < N
    assert 1 <= s <= N // 2
    pub = private_key_to_public_key(priv, compressed=True)
    assert ecdsa_verify(pub, digest, sig1) is True
    assert ecdsa_verify(pub, digest, (0).to_bytes(32, "big") + sig1[32:]) is False
    assert ecdsa_verify(pub, digest, sig1[:32] + (0).to_bytes(32, "big")) is False
    assert ecdsa_verify(pub, digest, N.to_bytes(32, "big") + sig1[32:]) is False
    high_s = sig1[:32] + (N - s).to_bytes(32, "big")
    assert ecdsa_verify(pub, digest, high_s) is True  # documented legacy accept-set; signing always emits low-S


def test_openapi_contract_lists_polymarket_routes():
    root = Path(__file__).resolve().parents[1]
    text = (root / "docs" / "openapi.yaml").read_text()
    for route in [
        "/markets/{market_id}/orderbook",
        "/markets/{market_id}/ticker",
        "/markets/{market_id}/trades",
        "/markets/{market_id}/positions",
        "/markets/portfolio",
    ]:
        assert route in text
    app_routes = (root / "netcoin" / "apps" / "__init__.py").read_text()
    for suffix in ["orderbook", "ticker", "trades", "positions"]:
        assert suffix in app_routes


def test_hardware_signer_is_explicitly_marked_as_placeholder():
    status = signer_status(HardwareSigner("demo-device"))
    assert status["can_sign"] is False
    assert status["experimental_stub"] is True
    assert "placeholder" in status["name"]
