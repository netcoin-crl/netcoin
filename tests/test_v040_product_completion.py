from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from netcoin.product_completion import load_product_completion_manifest, validate_product_completion

ROOT = Path(__file__).resolve().parents[1]


def test_v040_product_completion_manifest_validates() -> None:
    manifest = load_product_completion_manifest()
    assert manifest["version"] == "0.40.1"
    assert validate_product_completion(manifest, root=ROOT) == []


def test_completion_assets_include_functional_markers() -> None:
    js = (ROOT / "sites" / "shared" / "site-shell.js").read_text(encoding="utf-8")
    css = (ROOT / "sites" / "shared" / "site-shell.css").read_text(encoding="utf-8")
    for marker in [
        "NetCoinProductCompletion",
        "buildCommandPalette",
        "buildNotificationCenter",
        "mountSurfaceCompletion",
        "recordLocalNote",
    ]:
        assert marker in js
    for marker in [
        "nc-command-palette",
        "nc-notification-center",
        "nc-upgrade-panel",
        "nc-timeline",
        "nc-status-badge",
        "nc-mobile-table",
    ]:
        assert marker in css


def test_shared_shell_javascript_parses_with_node_when_available() -> None:
    js_path = ROOT / "sites" / "shared" / "site-shell.js"
    try:
        result = subprocess.run(["node", "--check", str(js_path)], cwd=ROOT, text=True, capture_output=True, timeout=20)
    except FileNotFoundError:
        return
    assert result.returncode == 0, result.stderr


def test_product_completion_tool_runs() -> None:
    result = subprocess.run(
        [sys.executable, "tools/check_product_completion.py"], cwd=ROOT, text=True, capture_output=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
