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
from urllib.request import urlopen

import pytest

from netcoin import cli
import netcoin.webwallet as ww
from netcoin.chain import Blockchain
from netcoin.tx import Transaction
from netcoin.wallet import Wallet


def test_page_contains_app():
    assert b"NetCoin Wallet" in ww.PAGE.encode("utf-8")
    assert b"/api/wallet/send" in ww.PAGE.encode("utf-8")


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
    out = ww.build_and_broadcast(wallet, dest, amount_sats=100_000_000, fee_sats=1_000_000, from_type="legacy", node_url="http://x")
    assert out["txid"] == captured["txid"]
    assert chain.mempool_info()["size"] == 1


def test_insufficient_funds_rejected(tmp_path, monkeypatch):
    wallet = Wallet.create()
    monkeypatch.setattr(ww, "_node_get", lambda u, p, timeout=15: {"node": {"height": 0}} if p == "/info" else {"utxos": []})
    try:
        ww.build_and_broadcast(wallet, "Ncdest", 100, 1, "legacy", "http://x")
        assert False, "expected failure"
    except ValueError as exc:
        assert "spendable" in str(exc) or "mature" in str(exc)


def test_server_serves_page_and_config():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ww.make_handler("http://node.example", faucet_url="http://faucet.example"))
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


def test_web_command_default_faucet_points_to_live_https_route():
    args = cli.build_parser().parse_args(["web"])
    assert args.faucet == "https://18.220.89.128/faucet"


def test_history_endpoint_proxies_address_summary(monkeypatch):
    monkeypatch.setattr(ww, "_node_get", lambda url, path, timeout=15: {"transaction_count": 2, "transaction_ids": ["aa", "bb"]})
    server = ThreadingHTTPServer(("127.0.0.1", 0), ww.make_handler("http://node.example"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        data = json.loads(urlopen(base + "/api/history?address=Ncabc").read())
        assert data["transaction_count"] == 2 and data["transaction_ids"] == ["aa", "bb"]
    finally:
        server.shutdown()
