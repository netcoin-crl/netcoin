"""BIP21-style netcoin: payment URIs — build/parse roundtrip, validation, and
the web-wallet payment-uri / parse-uri endpoints."""

import json
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import quote
from urllib.request import urlopen

import pytest

import netcoin.webwallet as ww
from netcoin.paymenturi import build_uri, parse_uri
from netcoin.wallet import Wallet

ADDR = Wallet.create().address_for("legacy")


def test_build_parse_roundtrip():
    uri = build_uri(ADDR, amount="12.5", label="Coffee", message="thanks & cheers")
    parsed = parse_uri(uri)
    assert parsed["address"] == ADDR
    assert parsed["amount"] == "12.5"
    assert parsed["label"] == "Coffee"
    assert parsed["message"] == "thanks & cheers"  # special chars survive encoding


def test_bare_address_uri():
    assert parse_uri(build_uri(ADDR)) == {"address": ADDR}


def test_rejects_bad_uris():
    with pytest.raises(ValueError):
        parse_uri(f"bitcoin:{ADDR}")
    with pytest.raises(ValueError):
        parse_uri("netcoin:not-an-address")
    with pytest.raises(ValueError):
        parse_uri(f"netcoin:{ADDR}?amount=-1")
    with pytest.raises(ValueError):
        build_uri(ADDR, amount="abc")


def test_web_endpoints_build_and_parse():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ww.make_handler("http://node.example"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        built = json.loads(urlopen(f"{base}/api/payment-uri?address={ADDR}&amount=3").read())
        assert built["uri"].startswith(f"netcoin:{ADDR}") and "amount=3" in built["uri"]
        parsed = json.loads(urlopen(f"{base}/api/parse-uri?uri={quote(built['uri'])}").read())
        assert parsed["address"] == ADDR and parsed["amount"] == "3"
    finally:
        server.shutdown()
