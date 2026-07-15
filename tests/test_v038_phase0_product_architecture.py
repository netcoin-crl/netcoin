from pathlib import Path

from netcoin.product_architecture import validate_product_architecture, load_product_architecture

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_phase0_product_architecture_spec_is_valid():
    report = validate_product_architecture()
    assert report.ok, report.issues
    assert report.version == "0.38.5"
    assert report.primary_navigation == ["Core", "Network", "Build", "Ecosystem"]
    assert "wallet" in report.surfaces
    assert "explorer" in report.surfaces
    assert "markets" in report.surfaces


def test_phase0_spec_has_five_jobs_and_anti_sprawl_rules():
    spec = load_product_architecture()
    assert len(spec["jobs"]) == 5
    assert spec["north_star"].startswith("A first-time user")
    assert "release-readiness-scorecard" in spec["approved_complementary_features"]
    assert "cross-chain-bridges" in spec["avoid_until_after_audit_candidate"]
    assert any("Every page has exactly one" in rule for rule in spec["product_rules"])


def test_shared_site_shell_uses_phase0_primary_nav_and_modes():
    shell = read("sites/shared/site-shell.js")
    assert "const MODE_KEY = 'nc.siteMode.v3'" in shell
    assert "label: 'User'" in shell
    assert "label: 'Trader'" in shell
    assert "label: 'Operator'" in shell
    assert "label: 'Developer'" in shell
    assert "label: 'Wallet', detail: 'send and receive', group: 'Core', primary: true" in shell
    assert "label: 'Explorer', detail: 'verify activity', group: 'Core', primary: true" in shell
    assert "label: 'Download', detail: 'install files', group: 'Core', primary: true" in shell
    assert "label: 'Home', detail: 'testnet hub', group: 'Core', primary: true" in shell
    assert "label: 'Markets', detail: 'trade test markets', group: 'Core', primary: true" in shell
    assert "const navGroups = [" in shell
    assert "title: 'Core', detail: 'main tools'" in shell
    assert "label: 'Treasury', detail: 'grants and spending', group: 'Ecosystem'" in shell
    assert "title: 'Build', detail: 'docs and APIs'" in shell
    assert "label: 'SDKs', detail: 'client libraries', group: 'Build'" in shell
    assert "site-nav-group" in shell
    assert "<summary>More</summary>" not in shell
    assert "const primary = links.filter((link) => link.primary);" not in shell
    assert "label: 'Features'," not in shell
    assert "label: 'Architecture'," not in shell


def test_homepage_is_wallet_first_and_grouped():
    html = read("sites/www/index.html")
    assert "wallet-first public testnet" in html
    assert "Open Wallet" in html
    assert "Search Explorer" in html
    assert "Download" in html
    assert "Browse Markets" in html
    assert "Network" in html
    assert "Governance" in html
    assert "Build" in html
    assert "Every new NetCoin capability" in html


def test_phase0_checker_script_exists():
    assert (ROOT / "tools" / "check_product_architecture.py").exists()
    assert "Validate the Phase 0" in read("tools/check_product_architecture.py")
