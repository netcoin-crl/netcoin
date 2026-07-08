from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from netcoin.apps import AppStore, route_app_get
from netcoin.chain import Blockchain
from netcoin.feature_status import live_feature_status
from netcoin.wallet import Wallet

ROOT = Path(__file__).resolve().parents[1]


def test_v018_live_routes_return_payloads(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(tmp_path / "app")
    wallet = Wallet.create()
    routes = [
        f"/api/explorer/address/{wallet.address}",
        "/api/explorer/mempool",
        "/api/explorer/watchlist",
        "/api/wallet/workflow",
        "/api/operator/live",
        "/api/exchange/live",
        "/api/release/verify",
    ]
    for route in routes:
        status, payload, ctype = route_app_get(store, chain, route, {}, node=None)
        assert status == 200, route
        assert ctype in {"application/json", "text/csv"}
        assert payload is not None


def test_v018_explorer_csv_and_missing_tx_block_are_safe(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(tmp_path / "app")
    wallet = Wallet.create()
    status, csv_text, ctype = route_app_get(store, chain, f"/api/explorer/address/{wallet.address}/csv", {}, node=None)
    assert status == 200
    assert ctype == "text/csv"
    assert "txid,height" in csv_text
    for route in ["/api/explorer/tx/00", "/api/explorer/block/unknown"]:
        status, payload, _ = route_app_get(store, chain, route, {}, node=None)
        assert status == 200
        assert payload["ok"] is False


def test_v018_feature_status_and_product_surface_include_live_routes() -> None:
    status = live_feature_status(ROOT)
    keys = {p["key"] for p in status["probes"]}
    assert {"wallet", "explorer", "operator", "exchange"}.issubset(keys)
    explorer = next(p for p in status["probes"] if p["key"] == "explorer")
    assert explorer["status"] == "working"
    proc = subprocess.run(
        [sys.executable, "tools/check_product_surface.py"], cwd=ROOT, text=True, capture_output=True, timeout=30
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_v018_frontend_js_syntax_and_release_verify_file_input() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    files = [
        "sites/explorer/explorer-pro.js",
        "sites/markets/markets-pro.js",
        "sites/wallet/wallet-app.js",
        "sites/faucet/faucet-admin.js",
        "sites/operator/operator.js",
        "sites/exchange/exchange.js",
        "sites/download/verify.js",
    ]
    for rel in files:
        proc = subprocess.run(["node", "--check", str(ROOT / rel)], cwd=ROOT, text=True, capture_output=True)
        assert proc.returncode == 0, proc.stderr
    assert "artifactFile" in (ROOT / "sites/download/verify.html").read_text(encoding="utf-8")
    assert "btnSaveDraft" in (ROOT / "sites/wallet/index.html").read_text(encoding="utf-8")


def test_v018_openapi_documents_live_product_routes() -> None:
    spec = (ROOT / "docs" / "openapi.yaml").read_text(encoding="utf-8")
    for route in [
        "/explorer/address/{address}",
        "/explorer/tx/{txid}",
        "/explorer/block/{id}",
        "/explorer/mempool",
        "/wallet/workflow",
        "/wallet/drafts",
        "/operator/live",
        "/exchange/live",
        "/release/verify",
    ]:
        assert f"  {route}:" in spec
