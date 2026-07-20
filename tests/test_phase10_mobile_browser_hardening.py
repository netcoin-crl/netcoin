from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase10_shared_shell_has_mobile_touch_target_contract() -> None:
    css = read("sites/shared/site-shell.css")
    assert "Mobile viewport and touch-target hardening" in css
    assert "--nc-touch-target:44px" in css
    assert "overflow-x:hidden" in css
    assert "overflow-wrap:anywhere" in css
    assert "@media (max-width:720px)" in css
    assert "site-nav{display:grid" in css
    assert "min-height:44px" in css


def test_phase10_wallet_mobile_hardening_is_present() -> None:
    html = read("sites/wallet/index.html")
    assert 'id=\"wallet-mobile-hardening\"' in html
    assert "wallet-tabs{display:grid" in html
    assert "fee-preset-cards{grid-template-columns:1fr" in html
    assert "wallet-flow-guide" in html
    assert "overflow-wrap:anywhere" in html


def test_phase10_browser_and_accessibility_tools_reference_real_smoke_runner() -> None:
    runner = read("tools/run_browser_accessibility_smoke.py")
    access = read("tools/run_accessibility_matrix.py")
    browser = read("tools/run_browser_e2e_matrix.py")
    spec = read("sites/tests/e2e/phase10-mobile-accessibility.spec.js")
    assert "sync_playwright" in runner
    assert "--require-browser" in runner
    assert "ERR_BLOCKED_BY_ADMINISTRATOR" not in runner
    assert "browser accessibility smoke" in access
    assert "run_browser_accessibility_smoke.py" in access
    assert "PHASE10_SPEC_PATH" in browser
    assert "expectNoHorizontalOverflow" in spec
    assert "wallet mobile surface" in spec


def test_phase10_source_gates_pass() -> None:
    for cmd in (
        [sys.executable, "tools/run_browser_e2e_matrix.py"],
        [sys.executable, "tools/run_accessibility_matrix.py", "--source-only"],
    ):
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        result = json.loads(proc.stdout)
        assert result["ok"] is True


def test_phase10_cache_busters_point_at_phase10_shell_assets() -> None:
    html_files = list((ROOT / "sites").glob("**/*.html"))
    assert html_files
    joined = "\n".join(p.read_text(encoding="utf-8") for p in html_files)
    assert "site-shell.css?v=20260719-fullwidth-shell" in joined
    assert "site-shell.js?v=20260718-nav-cleanup" in joined
