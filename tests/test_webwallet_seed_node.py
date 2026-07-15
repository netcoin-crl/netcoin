import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import netcoin.webwallet as webwallet
from netcoin.webwallet import LocalNodeController, make_handler


def test_seed_node_defaults_to_public_bind_and_the_real_network_port(tmp_path: Path):
    controller = LocalNodeController(enabled=True, port=28444, data_dir=tmp_path / "seed", bind_host="0.0.0.0")
    status = controller.status()
    assert status["bind_host"] == "0.0.0.0"
    assert status["port"] == 28444
    assert status["public"] is True


def test_local_node_stays_private_by_default(tmp_path: Path):
    controller = LocalNodeController(enabled=True, data_dir=tmp_path / "local")
    status = controller.status()
    assert status["bind_host"] == "127.0.0.1"
    assert status["public"] is False


class _wallet_server:
    """Spin up netcoin.webwallet's real HTTP handler for route-level tests."""

    def __init__(self):
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler("https://api.netcoin.online/api", "", allow_node_control=True),
        )
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _post(url: str, path: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = Request(url + path, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_seed_node_start_rejects_a_malformed_advertise_value(monkeypatch):
    monkeypatch.setattr(
        webwallet.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not spawn"))
    )
    with _wallet_server() as srv:
        status, body = _post(srv.url, "/api/seed-node/start", {"advertise": "not-a-host-port"})
    assert status == 400
    assert "host:port" in body["error"]


def test_seed_node_start_rejects_an_invalid_bandwidth_mode(monkeypatch):
    monkeypatch.setattr(
        webwallet.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not spawn"))
    )
    with _wallet_server() as srv:
        status, body = _post(srv.url, "/api/seed-node/start", {"bandwidth_mode": "turbo"})
    assert status == 400
    assert "normal, home, or low" in body["error"]


def test_seed_node_start_passes_through_valid_config(monkeypatch):
    class FakeProcess:
        pid = 999

        def poll(self):
            return None

    popen_calls = []

    def fake_popen(cmd, **kwargs):
        popen_calls.append(cmd)
        return FakeProcess()

    monkeypatch.setattr(webwallet.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        LocalNodeController,
        "_external_info",
        lambda self: ({"height": 1, "peers": [], "version": "test"} if popen_calls else None),
    )
    with _wallet_server() as srv:
        status, body = _post(
            srv.url, "/api/seed-node/start", {"advertise": "203.0.113.5:28444", "bandwidth_mode": "home", "port": 28450}
        )
    assert status == 200
    assert body["message"] == "node started"
    assert body["advertise"] == "203.0.113.5:28444"
    assert body["port"] == 28450
    assert popen_calls, "expected the seed node to actually spawn a subprocess"
    assert "--advertise" in popen_calls[0]
    assert "203.0.113.5:28444" in popen_calls[0]
    assert "--bandwidth-mode" in popen_calls[0]
    assert "home" in popen_calls[0]
