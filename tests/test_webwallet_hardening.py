"""Local web wallet CSRF/Origin protection, body-size ceiling, and security headers."""

import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import netcoin.webwallet as ww


def _server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), ww.make_handler("http://node.example"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def test_cross_origin_post_is_rejected():
    server, base = _server()
    try:
        req = Request(
            base + "/api/wallet/new",
            data=b"{}",
            headers={"Content-Type": "application/json", "Origin": "http://evil.example"},
            method="POST",
        )
        try:
            urlopen(req)
            assert False, "expected a 403"
        except HTTPError as exc:
            assert exc.code == 403
    finally:
        server.shutdown()


def test_same_origin_post_is_allowed():
    server, base = _server()
    try:
        req = Request(
            base + "/api/wallet/new",
            data=b"{}",
            headers={"Content-Type": "application/json", "Origin": base},
            method="POST",
        )
        result = json.loads(urlopen(req).read())
        assert result["address"]
    finally:
        server.shutdown()


def test_oversized_body_is_rejected():
    server, base = _server()
    try:
        oversized = json.dumps({"passphrase": "x" * (6 * 1024 * 1024)}).encode("utf-8")
        req = Request(
            base + "/api/wallet/load",
            data=oversized,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(req)
            assert False, "expected a rejection"
        except HTTPError as exc:
            assert exc.code == 400
        except URLError:
            # The server closes the connection as soon as it sees an
            # oversized Content-Length, before the client finishes writing
            # the body -- a broken pipe on the client side is an equally
            # valid sign the ceiling was enforced.
            pass
    finally:
        server.shutdown()


def test_responses_carry_no_store_and_security_headers():
    server, base = _server()
    try:
        resp = urlopen(base + "/api/config")
        assert resp.headers.get("Cache-Control") == "no-store"
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
    finally:
        server.shutdown()
