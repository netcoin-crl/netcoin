import subprocess
import sys
from pathlib import Path

from netcoin.apps import AppStore, route_app_get
from netcoin.chain import Blockchain
from netcoin.health_center import build_health_center, feature_status, site_inventory


def test_health_center_reports_sites_features_release_and_api(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(tmp_path / "app")
    payload = build_health_center(root=root, chain=chain, store=store)
    assert payload["status"] in {"healthy", "partial", "critical"}
    assert payload["sites"]["site_count"] >= 20
    assert payload["features"]["catalog_count"] >= 50
    assert payload["release"]["score"] >= 4
    assert payload["api_contract"]["has_health_center"] is True
    assert payload["fingerprint"]


def test_health_center_app_route(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(tmp_path / "app")
    status, payload, ctype = route_app_get(store, chain, "/api/health-center", {}, node=None)
    assert status == 200
    assert ctype == "application/json"
    assert payload["sites"]["site_count"] >= 20
    assert any(check["name"] == "sites" for check in payload["checks"])
    assert (root / "sites" / "operator" / "index.html").exists()
    assert (root / "sites" / "exchange" / "index.html").exists()


def test_product_surface_checker_and_site_inventory_pass():
    root = Path(__file__).resolve().parents[1]
    inv = site_inventory(root)
    names = {s["site"] for s in inv["sites"]}
    assert {"operator", "exchange", "explorer", "markets", "wallet"}.issubset(names)
    assert "operator" not in inv["missing_shell"]
    result = subprocess.run(
        [sys.executable, "tools/check_product_surface.py"], cwd=root, text=True, capture_output=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_product_feature_status_and_shell_links():
    root = Path(__file__).resolve().parents[1]
    status = feature_status(root)
    areas = {a["area"]: a for a in status["areas"]}
    assert areas["operator"]["status"] == "working"
    assert areas["exchange"]["status"] == "working"
    shell = (root / "sites" / "shared" / "site-shell.js").read_text()
    assert "operator.netcoin.online" in shell
    assert "exchange.netcoin.online" in shell
    assert "health center" in shell.lower()
