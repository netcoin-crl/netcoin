from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase9_shared_shell_has_keyboard_and_dialog_contracts() -> None:
    js = read("sites/shared/site-shell.js")
    css = read("sites/shared/site-shell.css")
    assert "function buildSkipLink" in js
    assert "Skip to main content" in js
    assert "aria-labelledby','ncCommandTitle'" in js
    assert "aria-controls=\"ncCommandResults\"" in js
    assert "role=\"listbox\"" in js
    assert "role=\"option\"" in js
    assert "trapFloatingFocus" in js
    assert "paletteReturnFocus" in js
    assert ".nc-skip-link" in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css


def test_phase9_wallet_critical_controls_have_live_regions_and_labels() -> None:
    html = read("sites/wallet/index.html")
    assert 'id="walletStatus" class="muted" role="status" aria-live="polite"' in html
    assert 'id="reviewWarning" class="err hide" role="alert" aria-live="assertive"' in html
    assert 'id="sendMsg" role="status" aria-live="polite"' in html
    assert 'id="rbfBumpOut" class="mono muted" role="status" aria-live="polite"' in html
    assert 'aria-label="Recipient address or payment link"' in html
    assert 'aria-label="Replacement transaction fee in NET"' in html
    assert 'aria-label="Import signed PSBT file"' in html


def test_phase9_new_surface_inputs_are_labeled() -> None:
    assert 'id="addrInput" aria-label="Search address"' in read("sites/explorer/address.html")
    assert 'id="txInput" aria-label="Search transaction ID"' in read("sites/explorer/tx.html")
    assert 'id="mempoolInput" aria-label="Search mempool transactions"' in read("sites/explorer/mempool.html")
    assert 'id="blockInput" aria-label="Search block height or hash"' in read("sites/explorer/block.html")
    assert 'id="featureSearch" type="search" placeholder="Search wallet, markets, P2P, explorer..." aria-label="Search feature catalog"' in read("sites/features/index.html")
    localnet = read("sites/docs/localnet.html")
    assert 'class="localnet-status-grid" role="status" aria-live="polite"' in localnet
    assert 'id="localnetStatusJson" class="compact-json" role="status" aria-live="polite"' in localnet


def test_phase9_accessibility_source_gate_covers_new_spec() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/run_accessibility_matrix.py", "--source-only"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["mode"] == "source-only"
    assert result["surface_count"] >= 6
    spec = read("sites/tests/e2e/phase9-accessibility.spec.js")
    assert "shared shell exposes skip link" in spec
    assert "wallet critical messages use live regions" in spec
