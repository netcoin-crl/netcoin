from pathlib import Path

from netcoin.apps import AppStore

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_site_shell_groups_secondary_surfaces_under_clear_tabs():
    shell = read("sites/shared/site-shell.js")
    assert "const navGroups = [" in shell
    assert "title: 'Core', detail: 'main tools'" in shell
    assert "title: 'Ecosystem', detail: 'governance, community, and commerce'" in shell
    assert "label: 'Treasury', detail: 'grants and spending', group: 'Ecosystem'" in shell
    assert "https://treasury.netcoin.online" in shell
    assert "title: 'Build', detail: 'docs and APIs'" in shell
    assert "label: 'API', detail: 'OpenAPI', group: 'Build'" in shell
    assert "label: 'Developers', detail: 'SDKs and client libraries', group: 'Build'" in shell
    assert "label: 'Developer Console', detail: 'payment links, API keys, webhooks', group: 'Build'" in shell
    assert "label: 'Download', detail: 'install files', group: 'Core'" in shell
    assert "https://download.netcoin.online" in shell
    assert "https://learn.netcoin.online#download" not in shell


def test_site_shell_core_tabs_render_flat_without_a_details_wrapper():
    shell = read("sites/shared/site-shell.js")
    assert "function coreTabsHtml()" in shell
    assert "function categoryTabsHtml()" in shell
    assert "const primaryNavLabels = ['Home', 'Wallet', 'Explorer', 'Markets']" in shell
    assert "filter((group) => group.title !== 'Core')" in shell
    assert "<summary>More</summary>" in shell


def test_site_shell_copies_stay_in_sync_for_all_subdomains():
    shared_js = read("sites/shared/site-shell.js")
    shared_css = read("sites/shared/site-shell.css")
    for site_dir in sorted((ROOT / "sites").iterdir()):
        if site_dir.name == "shared" or not site_dir.is_dir():
            continue
        js = site_dir / "site-shell.js"
        css = site_dir / "site-shell.css"
        if js.exists():
            assert js.read_text(encoding="utf-8") == shared_js, js
        if css.exists():
            assert css.read_text(encoding="utf-8") == shared_css, css


def test_homepage_presents_consolidated_navigation_buckets():
    html = read("sites/www/index.html")
    assert "NetCoin public testnet." in html
    assert "https://community.netcoin.online" in html
    assert 'href="https://governance.netcoin.online">Governance</a>' in html
    assert "<h2>Build</h2>" in html
    assert "<h2>Ecosystem</h2>" in html
    assert "https://developers.netcoin.online/console.html" in html
    assert "https://docs.netcoin.online/localnet.html" in html


def test_treasury_is_a_live_ui_instead_of_a_redirect():
    html = read("sites/treasury/index.html")
    js = read("sites/treasury/treasury.js")
    assert 'http-equiv="refresh"' not in html
    assert 'id="treasuryProposals"' in html
    assert 'id="refreshTreasury"' in html
    assert "/api/treasury/governance" in js
    assert "treasury_addresses" in js
    assert "ready_for_signing" in js
    assert hasattr(AppStore, "treasury_governance")
    assert hasattr(AppStore, "create_treasury_proposal")
    assert hasattr(AppStore, "approve_treasury_proposal")


def test_raw_json_has_a_readable_progressive_disclosure_view():
    shell = read("sites/shared/site-shell.js")
    css = read("sites/shared/site-shell.css")
    assert "function enhance(pre)" in shell
    assert "JSON.parse(pre.textContent.trim())" in shell
    assert "Raw JSON" in shell
    assert "MAX_ITEMS = 40" in shell
    assert ".nc-data-view" in css
    assert ".nc-raw-json" in css
