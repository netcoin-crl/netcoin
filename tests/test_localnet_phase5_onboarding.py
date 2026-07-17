from __future__ import annotations

import subprocess
from pathlib import Path

from netcoin.apps import AppStore, route_app_get
from netcoin.chain import Blockchain

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_phase5_localnet_status_route_is_read_only_and_testnet_labeled(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(tmp_path / "app")

    status, payload, ctype = route_app_get(store, chain, "/api/localnet/status", {}, node=None)

    assert status == 200
    assert ctype == "application/json"
    assert payload["schema"] == "netcoin-localnet-status-v1"
    assert payload["testnet_only"] is True
    assert payload["real_money_value"] is False
    assert payload["services"]["node_api"]["height"] == chain.height()
    assert payload["services"]["wallet"]["endpoint"] == "/api/wallet/workflow"
    assert payload["services"]["faucet"]["endpoint"] == "/api/faucet/status"
    assert payload["services"]["explorer"]["endpoint"] == "/api/explorer/mempool"
    assert "run_localnet.py" in payload["commands"]["localnet_harness"]
    assert "127.0.0.1" in payload["commands"]["single_node"]


def test_phase5_localnet_guide_exposes_copyable_launch_path_without_mainnet_claims() -> None:
    html = read("sites/docs/localnet.html")
    js = read("sites/docs/localnet.js")
    css = read("sites/docs/docs.css")

    for text in [
        "Launch a local NetCoin testnet.",
        "testnet only",
        "no real-money value",
        "Run the localnet harness",
        "Open local wallet",
        "Create wallet and mine",
        "Verify from CLI",
        "/api/localnet/status",
    ]:
        assert text in html
    for command in [
        "python3 -m venv .venv",
        "tools/run_localnet.py --nodes 3",
        "python3 -m netcoin --data ~/.netcoin-local node",
        "python3 -m netcoin web --node http://127.0.0.1:28444",
        "python3 -m netcoin miner --node http://127.0.0.1:28444",
    ]:
        assert command in html
    assert "data-copy-target=\"cmdInstall\"" in html
    assert "onclick=" not in html
    assert "mainnet launch" in html.lower()
    assert "production custody" in html.lower()
    assert "localnet_onboarding" not in html
    assert "fetch('/api/localnet/status'" in js
    assert "navigator.clipboard.writeText" in js
    assert "Localnet onboarding" in css


def test_phase5_localnet_is_discoverable_from_docs_learn_nodes_and_shell() -> None:
    docs = read("sites/docs/index.html")
    learn = read("sites/learn/index.html")
    nodes = read("sites/nodes/index.html")
    shell = read("sites/shared/site-shell.js")
    openapi = read("docs/openapi.yaml")

    assert 'href="localnet.html"' in docs
    assert "Localnet guide: install -> node -> wallet -> mining -> explorer" in docs
    assert "https://docs.netcoin.online/localnet.html" in learn
    assert "Launch localnet" in learn
    assert "Localnet onboarding" in nodes
    assert "label: 'Localnet', detail: 'launch guide', group: 'Build'" in shell
    assert "['Localnet', 'https://docs.netcoin.online/localnet.html']" in shell
    assert "  /localnet/status:" in openapi


def test_phase5_localnet_javascript_parses() -> None:
    proc = subprocess.run(
        ["node", "--check", "sites/docs/localnet.js"], cwd=ROOT, text=True, capture_output=True, timeout=20
    )
    assert proc.returncode == 0, proc.stderr
