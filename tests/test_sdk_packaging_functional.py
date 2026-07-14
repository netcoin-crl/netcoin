"""Proof that the JS and Python SDKs are real distributable packages."""

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _node_version() -> str:
    for line in (ROOT / "netcoin" / "params.py").read_text().splitlines():
        if line.strip().startswith("NODE_VERSION"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise AssertionError("NODE_VERSION not found")


def test_js_sdk_package_manifest_is_valid_and_versioned():
    pkg = json.loads((ROOT / "sdk" / "netcoin-js" / "package.json").read_text())
    assert pkg["name"] == "@netcoin/sdk"
    assert pkg["type"] == "module"
    assert pkg["main"] == "index.js"
    assert (ROOT / "sdk" / "netcoin-js" / pkg["main"]).exists()
    for listed in pkg["files"]:
        assert (ROOT / "sdk" / "netcoin-js" / listed).exists()
    assert pkg["version"] == _node_version()


def test_python_sdk_pyproject_is_valid_and_versioned():
    data = tomllib.loads((ROOT / "sdk" / "netcoin-python" / "pyproject.toml").read_text())
    assert data["project"]["name"] == "netcoin-sdk"
    modules = data["tool"]["setuptools"]["py-modules"]
    assert "netcoin_sdk" in modules
    assert (ROOT / "sdk" / "netcoin-python" / "netcoin_sdk.py").exists()
    assert data["project"]["version"] == _node_version()


def test_sdk_versions_match_each_other():
    js = json.loads((ROOT / "sdk" / "netcoin-js" / "package.json").read_text())["version"]
    py = tomllib.loads((ROOT / "sdk" / "netcoin-python" / "pyproject.toml").read_text())["project"]["version"]
    rust = tomllib.loads((ROOT / "sdk" / "netcoin-rs" / "Cargo.toml").read_text())["package"]["version"]
    assert js == py == rust == _node_version()


def test_rust_sdk_manifest_is_publish_ready():
    data = tomllib.loads((ROOT / "sdk" / "netcoin-rs" / "Cargo.toml").read_text())
    package = data["package"]
    assert package["name"] == "netcoin-rs"
    assert package["edition"] == "2021"
    assert package["license"] == "MIT"
    assert package["readme"] == "README.md"
    assert (ROOT / "sdk" / "netcoin-rs" / "README.md").exists()
    assert (ROOT / "sdk" / "netcoin-rs" / "src" / "lib.rs").exists()
    assert (ROOT / "sdk" / "netcoin-rs" / "tests" / "local_client.rs").exists()
