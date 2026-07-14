from __future__ import annotations

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from netcoin.bandwidth import TokenBucket, budget_for_mode, relay_plan
from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode
from tools.run_bandwidth_relay_probe import run_probe


ROOT = Path(__file__).resolve().parents[1]


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def counting_peer():
    counts = {"posts": 0, "bytes": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            counts["bytes"] += length
            counts["posts"] += 1
            self.rfile.read(length)
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_address[1]}", counts


def test_token_bucket_throttles_bytes_with_fake_clock():
    clock = FakeClock()
    bucket = TokenBucket(100, burst_seconds=1, clock=clock.time, sleeper=clock.sleep)
    assert bucket.consume(50) == 0
    waited = bucket.consume(100)
    assert waited == pytest.approx(0.5)
    assert bucket.total_bytes == 150
    assert bucket.throttle_events >= 1
    assert sum(clock.sleeps) == pytest.approx(0.5)


def test_node_post_json_uses_outbound_relay_bucket(tmp_path: Path):
    server, thread, url, counts = counting_peer()
    node = NetCoinNode(Blockchain(tmp_path / "chain"), persist=False, bandwidth_mode="home")
    clock = FakeClock()
    node.outbound_relay_bucket = TokenBucket(100, burst_seconds=1, clock=clock.time, sleeper=clock.sleep)
    payload = {"blob": "x" * 250}
    try:
        assert node.post_json(f"{url}/probe", payload)["ok"] is True
        assert counts["posts"] == 1
        assert counts["bytes"] == len(json.dumps(payload).encode("utf-8"))
        assert node.bandwidth_status()["outbound_relay"]["throttle_events"] >= 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_bandwidth_modes_are_runtime_visible(tmp_path: Path):
    home = NetCoinNode(Blockchain(tmp_path / "home"), persist=False, bandwidth_mode="home")
    low = NetCoinNode(Blockchain(tmp_path / "low"), persist=False, bandwidth_mode="low")
    normal = NetCoinNode(Blockchain(tmp_path / "normal"), persist=False, bandwidth_mode="normal")
    assert home.bandwidth_status()["budget"]["max_bytes_per_second"] == 500 * 1024
    assert low.bandwidth_status()["budget"]["max_bytes_per_second"] == 250 * 1024
    assert normal.bandwidth_status()["outbound_relay"]["enabled"] is False
    assert "netcoin_outbound_relay_bytes_total" in home.metrics_text()


def test_relay_plan_remains_compatible_with_budget_modes():
    plan = relay_plan("low", peer_count=12, pending_inventory=8000)
    assert plan["selected_outbound_peers"] == 4
    assert plan["inventory_to_relay"] == 0
    assert budget_for_mode("home").max_bytes_per_second == 500 * 1024


def test_bandwidth_cli_exposes_node_mode():
    proc = subprocess.run(
        [sys.executable, "-m", "netcoin", "node", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--bandwidth-mode" in proc.stdout


@pytest.mark.localnet
def test_bandwidth_relay_probe_enforces_home_mode_on_localnet(tmp_path: Path):
    report = run_probe(mode="home", nodes=3, payload_bytes=700_000, root_dir=tmp_path / "bandwidth-localnet")
    assert report["ok"] is True, report
    assert report["delivered"] == 3
    assert report["sustained_bytes_per_second"] <= report["max_bytes_per_second"]
    assert report["throttle_events"] >= 1
