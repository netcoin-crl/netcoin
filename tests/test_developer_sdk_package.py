from pathlib import Path

from netcoin.apps import AppStore, route_app_get
from netcoin.chain import Blockchain

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_developer_sdk_endpoint_only_claims_packages_that_are_real_or_marked_planned(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    status, sdk, _ctype = route_app_get(store, chain, "/api/developer/sdk", {})
    assert status == 200
    by_language = {p["language"]: p for p in sdk["packages"]}

    js = by_language["typescript"]
    assert js["package"] == "@netcoin/developer"
    assert js["status"] == "real"
    assert "npm install" not in js.get("install", "") or "github:" in js["install"]
    assert (ROOT / js["source"]).exists()

    for lang in ("python", "unity-csharp"):
        pkg = by_language[lang]
        assert pkg["status"] == "planned"
        assert "install" not in pkg, f"{lang} package must not advertise an install command it can't fulfill"


def test_sdk_netcoin_developer_package_exists_and_wraps_the_real_endpoints():
    index_js = read("sdk/netcoin-developer/index.js")
    assert "class NetcoinDeveloperClient" in index_js
    assert "/api/developer/rewards" in index_js
    assert "/api/developer/rewards/batch" in index_js
    assert "/api/developer/withdrawals" in index_js
    assert "/api/developer/funding-policy" in index_js
    assert "/api/developer/payment-links" in index_js
    assert "/api/developer/watch-addresses" in index_js
    assert "/api/developer/webhooks" in index_js
    assert "/api/developer/webhook-events" in index_js
    assert "export async function verifyNetcoinWebhook" in index_js

    package_json = read("sdk/netcoin-developer/package.json")
    assert '"name": "@netcoin/developer"' in package_json

    readme = read("sdk/netcoin-developer/README.md")
    assert "npm install" not in readme or "github:netcoin-crl/netcoin" in readme


def test_sdk_netcoin_developer_index_js_syntax_is_valid():
    import subprocess
    import shutil

    node = shutil.which("node")
    if not node:
        return
    result = subprocess.run(
        [node, "--check", str(ROOT / "sdk/netcoin-developer/index.js")], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
