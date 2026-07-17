from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from netcoin.site_ui_polish import audit_site_ui_polish, validate_site_ui_polish

ROOT = Path(__file__).resolve().parents[1]


def test_v042_site_ui_polish_audit_passes() -> None:
    result = audit_site_ui_polish(ROOT)
    assert result["version"] == "0.42.0"
    assert result["design_flaw_count"] >= 8
    assert result["copy_budget"]["panel_intro_count"] >= 8
    assert result["ok"], result["issues"]
    assert validate_site_ui_polish(ROOT) == []


def test_directory_is_collapsed_and_copy_is_shorter() -> None:
    js = (ROOT / "sites" / "shared" / "site-shell.js").read_text(encoding="utf-8")
    css = (ROOT / "sites" / "shared" / "site-shell.css").read_text(encoding="utf-8")
    assert "document.createElement('details')" in js
    assert "feature-dock-compact" in js
    assert "This page follows the Phase 0/1" not in js
    assert "NetCoin product completion layer" not in js
    assert "nc-ui-v042" in css
    assert "feature-dock-panel" in css


def test_browser_e2e_tokens_survive_copy_reduction() -> None:
    js = (ROOT / "sites" / "shared" / "site-shell.js").read_text(encoding="utf-8").lower()
    for token in [
        "overview",
        "send",
        "receive",
        "activity",
        "address",
        "tx",
        "block",
        "mempool",
        "orderbook",
        "portfolio",
        "trades",
        "settlement",
        "challenge",
        "claim",
        "status",
        "admin",
        "health",
        "diagnostics",
        "bundle",
        "alerts",
        "deposits",
        "withdrawals",
        "custody",
        "reserves",
    ]:
        assert token in js


def test_v042_tool_and_javascript_parse() -> None:
    result = subprocess.run(
        [sys.executable, "tools/check_site_ui_polish.py"], cwd=ROOT, text=True, capture_output=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    try:
        node = subprocess.run(
            ["node", "--check", "sites/shared/site-shell.js"], cwd=ROOT, text=True, capture_output=True, timeout=20
        )
    except FileNotFoundError:
        return
    assert node.returncode == 0, node.stderr


def test_minimalist_shell_reduces_nav_and_type_scale() -> None:
    js = (ROOT / "sites" / "shared" / "site-shell.js").read_text(encoding="utf-8")
    css = (ROOT / "sites" / "shared" / "site-shell.css").read_text(encoding="utf-8")
    assert "const primaryNavLabels = ['Home', 'Wallet', 'Explorer', 'Markets']" in js
    assert "site-nav-more" in js
    assert "font-size:clamp(24px,2.7vw,36px)!important" in css
    assert "--max:1280px!important" in css
    assert "site-nav-panel-wide" in css
