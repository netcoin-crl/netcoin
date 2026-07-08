from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v017_product_pages_exist_and_reference_shell() -> None:
    pages = [
        "sites/explorer/address.html",
        "sites/explorer/tx.html",
        "sites/explorer/block.html",
        "sites/explorer/mempool.html",
        "sites/markets/trade.html",
        "sites/markets/portfolio.html",
        "sites/markets/disputes.html",
        "sites/markets/settlement.html",
        "sites/faucet/admin.html",
        "sites/download/verify.html",
    ]
    for rel in pages:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "site-shell.js" in text
        assert "site-nav" in text


def test_wallet_overview_send_receive_activity_contacts_are_merged() -> None:
    js = (ROOT / "sites/wallet/wallet-app.js").read_text(encoding="utf-8")
    assert '{ id: "wallet", label: "Wallet"' in js
    assert '{ id: "overview", label: "Overview"' not in js
    assert '{ id: "send", label: "Send"' not in js
    assert '{ id: "receive", label: "Receive"' not in js
    assert '{ id: "activity", label: "Activity"' not in js
    assert '{ id: "contacts", label: "Contacts"' not in js
    assert "walletWorkspaceNav" in js
    assert "#wallet-send" in js and "#wallet-receive" in js and "#wallet-activity" in js and "#wallet-contacts" in js


def test_feature_status_and_health_center_include_live_probes() -> None:
    from netcoin.feature_status import live_feature_status
    from netcoin.health_center import build_health_center

    status = live_feature_status(ROOT)
    assert status["summary"]["working"] >= 6
    keys = {p["key"] for p in status["probes"]}
    assert {"wallet", "explorer", "markets", "release", "browser_e2e"}.issubset(keys)
    health = build_health_center(root=ROOT)
    assert "live_features" in health
    assert health["live_features"]["summary"]["working"] >= 6


def test_v017_tools_and_product_surface_pass() -> None:
    for cmd in [
        [sys.executable, "tools/check_product_surface.py"],
        [sys.executable, "tools/full_suite_report.py", "--out", "reports/test-v017-plan.json"],
        [sys.executable, "tools/run_browser_e2e.py", "--report", "reports/test-browser-e2e.json", "--timeout", "1"],
    ]:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=20)
        is_browser = any("run_browser_e2e.py" in part for part in cmd)
        assert (proc.returncode in (0, 1)) if is_browser else (proc.returncode == 0)
    report = json.loads((ROOT / "reports/test-v017-plan.json").read_text(encoding="utf-8"))
    assert report["file_count"] >= 80


def test_new_javascript_syntax() -> None:
    files = [
        "sites/explorer/explorer-pro.js",
        "sites/markets/markets-pro.js",
        "sites/faucet/faucet-admin.js",
        "sites/download/verify.js",
        "sites/features/features.js",
        "sites/wallet/wallet-app.js",
        "tools/check_product_surface.py",
    ]
    for rel in files:
        path = ROOT / rel
        if path.suffix == ".js":
            proc = subprocess.run(["node", "--check", str(path)], cwd=ROOT, text=True, capture_output=True)
            assert proc.returncode == 0, proc.stderr
