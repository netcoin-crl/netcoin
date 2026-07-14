from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_site_shell_detects_localhost_surface_from_path() -> None:
    js = (ROOT / "sites" / "shared" / "site-shell.js").read_text(encoding="utf-8")
    assert "match(/\/sites\/([^\/]+)/)" in js
    assert "body.getAttribute('data-site')" in js
    for token in [
        "Browse play-money markets, open the order book",
        "Health alerts",
        "diagnostics bundle",
    ]:
        assert token in js


def test_root_playwright_package_manifest_exists() -> None:
    data = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert data["type"] == "module"
    assert data["devDependencies"]["@playwright/test"] == "1.61.1"
    assert "proof:browser" in data["scripts"]


def test_static_local_e2e_api_fallbacks_exist() -> None:
    for rel in [
        "api/health-center",
        "api/operator/live",
        "api/exchange/live",
        "api/health",
        "api/latest",
        "api/mempool",
        "api/peers",
        "faucet/history",
    ]:
        path = ROOT / rel
        assert path.exists(), rel
        assert path.read_text(encoding="utf-8").strip().startswith("{")
