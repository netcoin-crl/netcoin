from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M1_SPEC = ROOT / "sites" / "tests" / "e2e" / "m1-wallet-workflow.spec.js"
RUNNER = ROOT / "tools" / "run_browser_e2e_matrix.py"
WEBWALLET_SPEC = ROOT / "webwallet-browser" / "tests" / "e2e" / "wallet.spec.js"


def test_m1_wallet_workflow_spec_covers_required_user_paths():
    spec = M1_SPEC.read_text(encoding="utf-8")
    for token in [
        "create wallet",
        "receive",
        "send",
        "lock",
        "unlock",
        "tab shell",
        "btnQuizSkip",
        "btnConfirmSend",
        "btnLock",
        "walletTabs",
        "mockWalletApi",
    ]:
        assert token in spec
    assert "page.route('**/api/**'" in spec
    assert "window.localStorage.clear()" in spec
    assert "window.sessionStorage.clear()" in spec


def test_browser_e2e_matrix_source_gate_includes_m1_wallet_workflow():
    proc = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["surface_count"] == 6
    assert result["m1_wallet_workflow_spec"] is True


def test_webwallet_browser_e2e_points_to_existing_wallet_html():
    spec = WEBWALLET_SPEC.read_text(encoding="utf-8")
    assert "/webwallet-browser/public/wallet.html" in spec
    assert "/webwallet-browser/public/index.html" not in spec
    assert (ROOT / "webwallet-browser" / "public" / "wallet.html").exists()
