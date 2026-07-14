import json
import shutil
import subprocess
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode, make_handler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk" / "netcoin-python"))
from netcoin_sdk import NetcoinClient as PythonNetcoinClient  # noqa: E402


class served:
    def __init__(self, node: NetCoinNode):
        self.node = node
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(node))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def read_json_response(url: str, *, method: str = "GET", body: bytes | None = None):
    request = Request(url, data=body, headers={"Content-Type": "application/json"} if body else {}, method=method)
    with urlopen(request, timeout=5) as response:
        return response, json.loads(response.read().decode("utf-8"))


def test_v1_aliases_work_and_legacy_routes_are_deprecated(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    with served(NetCoinNode(chain, persist=False)) as s:
        legacy_response, legacy = read_json_response(f"{s.url}/info")
        v1_response, v1 = read_json_response(f"{s.url}/v1/info")
        _root_response, root = read_json_response(f"{s.url}/v1")
        health_response, health = read_json_response(f"{s.url}/v1/health")
    assert legacy["node"]["height"] == v1["node"]["height"] == root["node"]["height"]
    assert legacy_response.headers["API-Version"] == "legacy"
    assert legacy_response.headers["Deprecation"] == "true"
    assert '</v1/info>; rel="successor-version"' in legacy_response.headers["Link"]
    assert v1_response.headers["API-Version"] == "v1"
    assert "Deprecation" not in v1_response.headers
    assert health_response.headers["API-Version"] == "v1"
    assert health["ok"] is True


def test_v1_post_alias_uses_canonical_route_and_headers(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    with served(NetCoinNode(chain, persist=False)) as s:
        try:
            read_json_response(f"{s.url}/v1/tx", method="POST", body=b"{}")
        except HTTPError as exc:
            payload = json.loads(exc.read().decode("utf-8"))
            assert exc.code == 400
            assert exc.headers["API-Version"] == "v1"
            assert "Deprecation" not in exc.headers
            assert payload["ok"] is False


def test_node_openapi_v1_source_checker_passes():
    proc = subprocess.run(
        [sys.executable, "tools/check_node_openapi_v1.py"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    report = json.loads(proc.stdout)
    assert report["ok"] is True
    assert report["node_get_route_count"] >= 27
    assert report["node_post_route_count"] >= 10


def test_python_sdk_hits_local_v1_node(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    with served(NetCoinNode(chain, persist=False)) as s:
        client = PythonNetcoinClient(s.url)
        info = client.node_info()
        health = client.node_health()
        template = client.block_template()
    assert info["node"]["height"] == 0
    assert health["ok"] is True
    assert template["height"] == 1


def test_js_sdk_hits_local_v1_node(tmp_path: Path):
    node_bin = shutil.which("node")
    if not node_bin:
        return
    chain = Blockchain(tmp_path / "chain")
    script = tmp_path / "sdk-smoke.mjs"
    script.write_text(
        """
import { NetcoinClient } from '%s';
const client = new NetcoinClient(process.argv[2]);
const info = await client.nodeInfo();
const health = await client.nodeHealth();
const template = await client.blockTemplate();
console.log(JSON.stringify({ height: info.node.height, ok: health.ok, templateHeight: template.height }));
""" % (ROOT / "sdk" / "netcoin-js" / "index.js"),
        encoding="utf-8",
    )
    with served(NetCoinNode(chain, persist=False)) as s:
        proc = subprocess.run([node_bin, str(script), s.url], check=True, text=True, capture_output=True)
    payload = json.loads(proc.stdout)
    assert payload == {"height": 0, "ok": True, "templateHeight": 1}


def test_rust_sdk_crate_tests_pass_when_cargo_is_available():
    cargo = shutil.which("cargo")
    if not cargo:
        return
    proc = subprocess.run(
        [cargo, "test", "--manifest-path", "sdk/netcoin-rs/Cargo.toml"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "test result: ok" in proc.stdout or "test result: ok" in proc.stderr
