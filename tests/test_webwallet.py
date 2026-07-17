"""Local web wallet/faucet/explorer page (#web): page serves, and the remote
send path produces a chain-valid, broadcastable transaction."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request
from urllib.request import urlopen

import pytest

import netcoin.webwallet as ww
from netcoin import cli
from netcoin.chain import Blockchain
from netcoin.fee_bump import DEFAULT_RBF_SEQUENCE
from netcoin.script import script_to_p2sh_address
from netcoin.tx import SpendableOutput, Transaction, TxInput, TxOutput
from netcoin.wallet import Wallet


def test_page_contains_app():
    page = ww.PAGE.encode("utf-8")
    assert b"NetCoin Wallet" in page
    assert b"/api/wallet/send" in page
    assert b"/api/fee-estimates" in page
    assert b"/api/wallet/rbf-bump" in page
    assert b"/api/wallet/multisig/create" in page
    assert b"multisigCard" in page


def test_page_escapes_dynamic_html_and_hardens_external_links():
    assert "const esc=" in ww.PAGE
    assert "const jsq=" in ww.PAGE
    assert "function safeUrl" in ww.PAGE
    assert 'rel="noopener noreferrer"' in ww.PAGE


def test_page_javascript_is_valid():
    """A JS syntax error in the embedded page kills every button, so guard it.

    Catches the Python-escaped-quote pitfall (\\' inside the page string collapses
    to ', producing searchFor('' ...) ) both statically and, if node is present,
    with a real syntax check."""
    assert "searchFor(''" not in ww.PAGE  # signature of the collapsed-escape bug
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for a full JS syntax check")
    js = re.search(r"<script>(.*)</script>", ww.PAGE, re.S).group(1)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
        handle.write(js)
        path = handle.name
    try:
        result = subprocess.run([node, "--check", path], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    finally:
        os.unlink(path)


def test_build_and_broadcast_produces_valid_tx(tmp_path, monkeypatch):
    chain = Blockchain(tmp_path / "c")
    wallet = Wallet.create()
    addr = wallet.address_for("legacy")
    for _ in range(102):  # fund + mature the first coinbase
        chain.mine_block(addr)

    def fake_get(node_url, path, timeout=15):
        if path == "/info":
            return {"node": {"height": chain.height()}}
        if path.startswith("/utxos"):
            return {"utxos": [u.to_dict() for u in chain.utxos_for_address(addr)]}
        raise AssertionError(f"unexpected GET {path}")

    captured = {}

    def fake_post(node_url, path, payload, timeout=15):
        assert path == "/tx"
        tx = Transaction.from_dict(payload)
        captured["txid"] = chain.add_mempool_transaction(tx)  # full consensus validation
        return {"txid": captured["txid"], "ok": True}

    monkeypatch.setattr(ww, "_node_get", fake_get)
    monkeypatch.setattr(ww, "_node_post", fake_post)

    dest = Wallet.create().address_for("segwit")
    out = ww.build_and_broadcast(
        wallet, dest, amount_sats=100_000_000, fee_sats=1_000_000, from_type="legacy", node_url="http://x"
    )
    assert out["txid"] == captured["txid"]
    assert chain.mempool_info()["size"] == 1


def test_insufficient_funds_rejected(tmp_path, monkeypatch):
    wallet = Wallet.create()
    monkeypatch.setattr(
        ww, "_node_get", lambda u, p, timeout=15: {"node": {"height": 0}} if p == "/info" else {"utxos": []}
    )
    try:
        ww.build_and_broadcast(wallet, "Ncdest", 100, 1, "legacy", "http://x")
        assert False, "expected failure"
    except ValueError as exc:
        assert "spendable" in str(exc) or "mature" in str(exc)


def test_server_serves_page_and_config():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), ww.make_handler("http://node.example", faucet_url="http://faucet.example")
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        page = urlopen(base + "/").read()
        assert b"NetCoin Wallet" in page
        cfg = json.loads(urlopen(base + "/api/config").read())
        assert cfg["node"] == "http://node.example" and cfg["faucet"] == "http://faucet.example"
        current = json.loads(urlopen(base + "/api/wallet/current").read())
        assert current["address"] is None
    finally:
        server.shutdown()


def _post_json(base: str, path: str, payload: dict) -> dict:
    req = Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urlopen(req).read())


def test_local_webwallet_fee_estimates_and_rbf_bump(monkeypatch):
    wallet = Wallet.create()
    replacement_seen = {}

    def fake_get(_node_url, path, timeout=15):
        if path == "/fee-estimates":
            return {"presets": {"fast": {"estimated_fee_sats": 1500}, "normal": {"estimated_fee_sats": 1000}}}
        raise AssertionError(f"unexpected GET {path}")

    def fake_post(_node_url, path, payload, timeout=30):
        assert path == "/tx"
        replacement_seen["tx"] = Transaction.from_dict(payload)
        return {"ok": True, "txid": replacement_seen["tx"].txid()}

    monkeypatch.setattr(ww, "_node_get", fake_get)
    monkeypatch.setattr(ww, "_node_post", fake_post)
    server = ThreadingHTTPServer(("127.0.0.1", 0), ww.make_handler("http://node.example"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        fees = json.loads(urlopen(base + "/api/fee-estimates").read())
        assert fees["presets"]["fast"]["estimated_fee_sats"] == 1500
        _post_json(base, "/api/wallet/private-key", {"private_key_hex": wallet.private_key_hex})

        prevout = SpendableOutput(
            "a" * 64,
            0,
            TxOutput(amount=1_000_000, address=wallet.address_for("segwit")),
            height=1,
            coinbase=False,
        )
        recipient = Wallet.create().address_for("segwit")
        original = Transaction(
            inputs=[TxInput(txid=prevout.txid, vout=prevout.vout, sequence=DEFAULT_RBF_SEQUENCE)],
            outputs=[TxOutput(amount=700_000, address=recipient), TxOutput(amount=200_000, address=wallet.address_for("segwit"))],
        )
        original.sign_input(0, wallet.private_key, prevout)
        bumped = _post_json(
            base,
            "/api/wallet/rbf-bump",
            {
                "original_tx": original.to_dict(),
                "prevouts": [prevout.to_dict()],
                "new_fee": "0.0015",
                "change_address": wallet.address_for("segwit"),
                "broadcast": True,
            },
        )
        assert bumped["old_fee"] == 100_000
        assert bumped["new_fee"] == 150_000
        assert bumped["signals_rbf"] is True
        assert replacement_seen["tx"].outputs[-1].amount == 150_000
    finally:
        server.shutdown()


def test_local_webwallet_multisig_psbt_flow(monkeypatch):
    w1, w2, w3 = Wallet.create(), Wallet.create(), Wallet.create()
    redeem = w1.create_multisig_address(2, [w1.public_key_hex, w2.public_key_hex, w3.public_key_hex])["redeem_script"]
    multisig_address = script_to_p2sh_address(redeem)
    funding = SpendableOutput(
        "b" * 64,
        0,
        TxOutput(amount=1_000_000, address=multisig_address),
        height=1,
        coinbase=False,
    )

    def fake_get(_node_url, path, timeout=15):
        if path == f"/utxos?address={multisig_address}":
            return {"utxos": [funding.to_dict()]}
        raise AssertionError(f"unexpected GET {path}")

    monkeypatch.setattr(ww, "_node_get", fake_get)
    server = ThreadingHTTPServer(("127.0.0.1", 0), ww.make_handler("http://node.example"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        _post_json(base, "/api/wallet/private-key", {"private_key_hex": w1.private_key_hex})
        created = _post_json(
            base,
            "/api/wallet/multisig/create",
            {"required": 2, "pubkeys": [w1.public_key_hex, w2.public_key_hex, w3.public_key_hex]},
        )
        assert created["address"] == multisig_address
        assert created["redeem_script"] == redeem

        unsigned = _post_json(
            base,
            "/api/wallet/multisig/psbt/create",
            {"redeem_script": redeem, "to": Wallet.create().address_for("segwit"), "amount": "0.005", "fee": "0.001"},
        )
        assert unsigned["multisig_address"] == multisig_address
        assert unsigned["progress"]["collected"] == 0

        signed_one = _post_json(
            base,
            "/api/wallet/multisig/psbt/sign",
            {"psbt": unsigned["unsigned_psbt"], "redeem_script": redeem},
        )
        assert signed_one["progress"]["collected"] == 1
        assert signed_one["progress"]["ready"] is False

        _post_json(base, "/api/wallet/private-key", {"private_key_hex": w2.private_key_hex})
        signed_two = _post_json(
            base,
            "/api/wallet/multisig/psbt/sign",
            {"psbt": signed_one["signed_psbt"], "redeem_script": redeem},
        )
        assert signed_two["progress"]["collected"] == 2
        assert signed_two["progress"]["ready"] is True
        extracted = _post_json(base, "/api/wallet/psbt/extract", {"psbt": signed_two["signed_psbt"]})
        assert extracted["progress"]["ready"] is True
        assert extracted["tx"]["inputs"][0]["script_sig"]
    finally:
        server.shutdown()


def test_local_node_control_is_disabled_unless_enabled():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ww.make_handler("http://node.example"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        status = json.loads(urlopen(base + "/api/local-node/status").read())
        assert status["enabled"] is False
        req = Request(base + "/api/local-node/start", method="POST")
        try:
            urlopen(req).read()
            assert False, "expected disabled local node control to reject start"
        except HTTPError as exc:
            body = json.loads(exc.read())
            assert exc.code == 400
            assert "local node control" in body["error"]
    finally:
        server.shutdown()


def test_local_node_control_reports_external_running_node(monkeypatch):
    monkeypatch.setattr(
        ww,
        "_node_get",
        lambda url, path, timeout=15: {"node": {"height": 7, "peers": 2, "version": "test"}} if path == "/info" else {},
    )
    handler = ww.make_handler("http://node.example", allow_node_control=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        status = json.loads(urlopen(base + "/api/local-node/status").read())
        assert status["enabled"] is True
        assert status["running"] is True
        assert status["external"] is True
        assert status["height"] == 7
    finally:
        server.shutdown()


def test_web_command_default_faucet_points_to_live_https_route():
    args = cli.build_parser().parse_args(["web"])
    assert args.faucet == "https://faucet.netcoin.online"


def test_history_endpoint_proxies_address_summary(monkeypatch):
    monkeypatch.setattr(
        ww, "_node_get", lambda url, path, timeout=15: {"transaction_count": 2, "transaction_ids": ["aa", "bb"]}
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), ww.make_handler("http://node.example"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        data = json.loads(urlopen(base + "/api/history?address=Ncabc").read())
        assert data["transaction_count"] == 2 and data["transaction_ids"] == ["aa", "bb"]
    finally:
        server.shutdown()
