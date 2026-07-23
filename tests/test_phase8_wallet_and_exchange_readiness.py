from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from netcoin.apps import AppStore, route_app_get
from netcoin.chain import Blockchain

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_phase8_wallet_ux_hardening_is_visible_and_sri_matches() -> None:
    html = read("sites/wallet/index.html")
    js = read("sites/wallet/wallet-app.js")

    for token in [
        'id="walletFlowGuide"',
        "Receive testnet NET",
        "Send safely",
        "Check activity",
        "Advanced tools",
        'id="sendChecklist"',
        "Before you send",
        "Confirm testnet send",
        "receive-shortcuts",
        "Open testnet faucet",
        "Open Explorer",
        "wallet-ux-hardening",
    ]:
        assert token in html
    for token in [
        "function friendlyWalletErrorMessage",
        "function markSendChecklist",
        "function setWalletFlowStep",
        "Open in Explorer",
        "btnCopyTxid",
        "Node connection problem",
        "Recipient problem",
    ]:
        assert token in js

    match = re.search(r'<script src="wallet-app\.js\?v=[^"]+" integrity="([^"]+)"', html)
    assert match, "wallet-app.js script tag must keep SRI"
    actual = "sha384-" + base64.b64encode(hashlib.sha384((ROOT / "sites/wallet/wallet-app.js").read_bytes()).digest()).decode()
    assert match.group(1) == actual


def test_phase8_browser_e2e_matrix_tracks_wallet_hardening_tokens() -> None:
    spec = read("sites/tests/e2e/m1-wallet-workflow.spec.js")
    runner = read("tools/run_browser_e2e_matrix.py")

    for token in [
        "walletFlowGuide",
        "sendChecklist",
        "feePresetCards",
        "speedUpCard",
        "psbtToolsCard",
        "multisigToolsCard",
        "Confirm testnet send",
    ]:
        assert token in spec
        assert token in runner

    proc = subprocess.run(
        [sys.executable, "tools/run_browser_e2e_matrix.py"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
        timeout=30,
    )
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["m1_wallet_workflow_spec"] is True


def test_exchange_listing_readiness_api_is_gated_and_not_a_real_listing(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(tmp_path / "app")
    status, payload, ctype = route_app_get(store, chain, "/api/exchange/listing-readiness", {}, node=None)

    assert status == 200
    assert ctype == "application/json"
    assert payload["status"] == "code-side-testnet-readiness"
    assert payload["real_listing_available"] is False
    assert payload["production_ready"] is False
    assert payload["testnet_only"] is True
    assert payload["real_money_value"] is False
    assert {gate["id"] for gate in payload["code_gates"]} >= {
        "deposit-withdrawal-state-machine",
        "reorg-safe-deposit-drill",
        "proof-of-reserves-tooling",
        "accounting-reconciliation",
        "operator-dashboard",
    }
    assert {blocker["id"] for blocker in payload["external_blockers"]} >= {
        "legal-review",
        "exchange-counterparty",
        "liquidity-market-maker",
        "independent-security-audit",
        "production-custody-ops",
    }
    assert "generate_external_audit_package.py" in payload["commands"]["audit_package"]


def test_exchange_listing_readiness_page_and_shell_are_discoverable() -> None:
    listing = read("sites/exchange/listing.html")
    listing_js = read("sites/exchange/listing.js")
    exchange = read("sites/exchange/index.html")
    shell = read("sites/shared/site-shell.js")
    css = read("sites/exchange/exchange.css")
    openapi = read("docs/openapi.yaml")
    features = read("netcoin/feature_catalog.py")

    for token in [
        "Listing readiness.",
        "Real exchange listing",
        "Production custody",
        "Real-money value",
        "External blockers",
        "Readiness tracker, not a listing or exchange offer",
    ]:
        assert token in listing
    assert "get('/exchange/listing-readiness')" in listing_js
    assert "Listing readiness" in exchange
    assert "listing.html" in exchange
    assert "Listing Readiness" in shell
    assert "listing readiness|real listing|exchange listing|exchange readiness" in shell
    assert "Exchange/listing readiness" in css
    assert "  /exchange/listing-readiness:" in openapi
    assert "exchange listing-readiness checks" in features


def test_exchange_listing_readiness_javascript_parses() -> None:
    if not shutil.which("node"):
        return  # syntax-check only; environments without Node.js (e.g. seed servers) skip it
    proc = subprocess.run(
        ["node", "--check", "sites/exchange/listing.js"], cwd=ROOT, text=True, capture_output=True, timeout=20
    )
    assert proc.returncode == 0, proc.stderr

    proc = subprocess.run(
        ["node", "--check", "sites/wallet/wallet-app.js"], cwd=ROOT, text=True, capture_output=True, timeout=20
    )
    assert proc.returncode == 0, proc.stderr
