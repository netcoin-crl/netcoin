from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from netcoin.apps import AppStore, route_app_get
from netcoin.architecture import architecture_status, architecture_summary
from netcoin.chain import Blockchain

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_spaces_and_manifest_exist() -> None:
    status = architecture_status(ROOT)
    assert status["ok"] is True
    spaces = {item["path"]: item for item in status["spaces"]}
    for rel in ["core-rs", "node-rs", "indexer-rs", "api", "web", "desktop", "mobile", "ops/python", "architecture"]:
        assert rel in spaces
        assert spaces[rel]["exists"] is True
    summary = architecture_summary(ROOT)
    assert summary["final_version_target"].startswith("v1.0 production-candidate")
    assert any(layer["language"] == "Rust" for layer in summary["layers"])
    assert any("TypeScript" in layer["language"] for layer in summary["layers"])
    assert any(layer["language"] == "Python" for layer in summary["layers"])


def test_architecture_api_and_site_are_wired(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(tmp_path / "app")
    code, payload, ctype = route_app_get(store, chain, "/api/architecture", {}, node=None)
    assert code == 200
    assert ctype == "application/json"
    assert payload["status"]["ok"] is True
    html = (ROOT / "sites/architecture/index.html").read_text(encoding="utf-8")
    assert "site-shell.js" in html
    assert "Professional stack map" in html


def test_architecture_checks_and_openapi_pass() -> None:
    for cmd in [
        [sys.executable, "tools/check_architecture_space.py"],
        [sys.executable, "tools/check_product_surface.py"],
    ]:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=40)
        assert proc.returncode == 0, proc.stdout + proc.stderr
    spec = (ROOT / "docs" / "openapi.yaml").read_text(encoding="utf-8")
    assert "  /architecture:" in spec


def test_rust_and_typescript_upgrade_scaffolds_are_parseable() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    assert (ROOT / "core-rs/Cargo.toml").exists()
    assert (ROOT / "api/tsconfig.json").exists()
    assert (ROOT / "web/tsconfig.json").exists()
    assert "netcoin-consensus" in (ROOT / "core-rs/crates/consensus/Cargo.toml").read_text(encoding="utf-8")
    proc = subprocess.run(
        ["node", "--check", str(ROOT / "sites/architecture/architecture.js")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert proc.returncode == 0, proc.stderr
