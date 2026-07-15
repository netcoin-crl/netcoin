from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_site_shell_groups_secondary_surfaces_under_clear_tabs():
    shell = read("sites/shared/site-shell.js")
    assert "const navGroups = [" in shell
    assert "title: 'Core', detail: 'main tools'" in shell
    assert "title: 'Ecosystem', detail: 'governance, community, and commerce'" in shell
    assert "label: 'Treasury', detail: 'grants and spending', group: 'Ecosystem'" in shell
    assert "https://governance.netcoin.online#treasury" in shell
    assert "title: 'Build', detail: 'docs and APIs'" in shell
    assert "label: 'API', detail: 'OpenAPI', group: 'Build'" in shell
    assert "label: 'SDKs', detail: 'client libraries', group: 'Build'" in shell
    assert "label: 'Download', detail: 'install files', group: 'Core'" in shell
    assert "https://download.netcoin.online" in shell
    assert "https://learn.netcoin.online#download" not in shell


def test_site_shell_core_tabs_render_flat_without_a_details_wrapper():
    shell = read("sites/shared/site-shell.js")
    assert "function coreTabsHtml()" in shell
    assert "function categoryTabsHtml()" in shell
    assert "filter((group) => group.title !== 'Core')" in shell


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
    assert "Core tools are Explorer, Download, Home, Markets, and Wallet, always visible." in html
    assert "Governance, treasury records, community, guides, pay, and merchant tools live together." in html
    assert 'href="https://governance.netcoin.online#treasury">Treasury</a>' in html
    assert "<h2>Build</h2>" in html
    assert "<h2>Ecosystem</h2>" in html
