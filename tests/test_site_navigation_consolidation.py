from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_site_shell_groups_secondary_surfaces_under_clear_tabs():
    shell = read("sites/shared/site-shell.js")
    assert "const navGroups = [" in shell
    assert "title: 'Governance', detail: 'NIPs and treasury'" in shell
    assert "label: 'Treasury', detail: 'grants and spending', group: 'Governance'" in shell
    assert "https://governance.netcoin.online#treasury" in shell
    assert "title: 'Build', detail: 'docs and APIs'" in shell
    assert "label: 'API', detail: 'OpenAPI', group: 'Build'" in shell
    assert "label: 'SDKs', detail: 'client libraries', group: 'Build'" in shell
    assert "label: 'Download', detail: 'install files', group: 'Build'" in shell
    assert "https://download.netcoin.online" in shell
    assert "https://learn.netcoin.online#download" not in shell


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
    assert "Secondary tools are grouped under Network, Governance, Build, and More." in html
    assert "NIPs, votes, roadmap decisions, treasury records, and grants live together." in html
    assert 'href="https://governance.netcoin.online#treasury">Treasury</a>' in html
    assert "<h2>Build</h2>" in html
