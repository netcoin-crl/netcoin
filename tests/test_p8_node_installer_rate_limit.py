import json
import subprocess
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode, RateLimiter, api_key_identity_from_headers, make_handler
from tools.run_rate_limit_loadtest import run_loadtest


ROOT = Path(__file__).resolve().parents[1]


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


def test_token_bucket_returns_retry_after():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.check(("ip", "key", "GET", "/info")).allowed is True
    assert limiter.check(("ip", "key", "GET", "/info")).allowed is True
    blocked = limiter.check(("ip", "key", "GET", "/info"))
    assert blocked.allowed is False
    assert blocked.retry_after >= 1
    assert limiter.check(("ip", "other-key", "GET", "/info")).allowed is True


def test_api_key_identity_is_fingerprinted_and_anonymous():
    assert api_key_identity_from_headers({}) == "anonymous"
    identity = api_key_identity_from_headers({"Authorization": "Bearer secret-token"})
    assert identity.startswith("key:")
    assert "secret-token" not in identity


def test_http_429_includes_retry_after_and_keys_by_api_key(tmp_path: Path):
    node = NetCoinNode(Blockchain(tmp_path / "chain"), persist=False, rate_limit_per_min=1)
    with served(node) as s:
        first = Request(f"{s.url}/info", headers={"X-Netcoin-Api-Key": "alpha"})
        with urlopen(first, timeout=5) as response:
            assert response.status == 200
        second = Request(f"{s.url}/info", headers={"X-Netcoin-Api-Key": "alpha"})
        try:
            urlopen(second, timeout=5)
        except HTTPError as exc:
            assert exc.code == 429
            assert int(exc.headers["Retry-After"]) >= 1
            payload = json.loads(exc.read().decode())
            assert payload["error"] == "rate limit exceeded"
        beta = Request(f"{s.url}/info", headers={"X-Netcoin-Api-Key": "beta"})
        with urlopen(beta, timeout=5) as response:
            assert response.status == 200


def test_rate_limit_loadtest_proves_limit_holds():
    report = run_loadtest(rate_limit_per_min=4, requests=12, workers=4, api_key="pytest-load")
    assert report["ok"] is True
    assert report["accepted"] <= 4
    assert report["rejected"] >= 8
    assert all(value >= 1 for value in report["retry_after_values"])


def test_public_node_operator_scripts_are_safe_and_dry_runnable(tmp_path: Path):
    scripts = [
        "tools/install_public_node.sh",
        "tools/uninstall_public_node.sh",
        "tools/upgrade_public_node.sh",
    ]
    for script in scripts:
        subprocess.run(["sh", "-n", str(ROOT / script)], check=True)

    prefix = tmp_path / "node"
    install = subprocess.run(
        [
            "sh",
            str(ROOT / "tools/install_public_node.sh"),
            "--dry-run",
            "--prefix",
            str(prefix),
            "--advertise",
            "127.0.0.1:28444",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "dry run:         1" in install.stdout
    assert not prefix.exists()

    uninstall = subprocess.run(
        ["sh", str(ROOT / "tools/uninstall_public_node.sh"), "--dry-run", "--prefix", str(prefix)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "remove data:  0" in uninstall.stdout

    upgrade = subprocess.run(
        ["sh", str(ROOT / "tools/upgrade_public_node.sh"), "--dry-run", "--prefix", str(prefix)],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "dry run:  1" in upgrade.stdout


def test_uninstall_refuses_without_confirmation(tmp_path: Path):
    result = subprocess.run(
        ["sh", str(ROOT / "tools/uninstall_public_node.sh"), "--prefix", str(tmp_path / "node")],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert "--yes" in result.stderr


def test_node_installer_workflow_runs_compose_waits_mines_and_tears_down():
    workflow = (ROOT / ".github/workflows/node-installer-smoke.yml").read_text()
    assert "docker compose -f docker-compose.node.yml up -d --build" in workflow
    assert "curl -fsS http://127.0.0.1:28444/info" in workflow
    assert "python -m netcoin miner" in workflow
    assert "--blocks 1" in workflow
    assert "docker compose -f docker-compose.node.yml down -v" in workflow
    assert "if: always()" in workflow
