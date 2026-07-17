from pathlib import Path

from netcoin.feature_catalog import feature_catalog

ROOT = Path(__file__).resolve().parents[1]


def _features():
    catalog = feature_catalog()
    for group in catalog["groups"].values():
        yield from group


def test_feature_catalog_exposes_phase6_availability_metadata():
    catalog = feature_catalog()
    assert catalog["schema"] == "netcoin-feature-catalog-v1"
    assert "availability_scale" in catalog
    assert "no real-money value" in catalog["disclaimer"]

    required = {
        "availability",
        "ui",
        "api",
        "cli",
        "test_coverage",
        "production_ready",
        "badge",
        "availability_notes",
    }
    features = list(_features())
    assert len(features) >= 80
    for feature in features:
        assert required.issubset(feature.keys()), feature["name"]
        assert feature["production_ready"] is False, feature["name"]
        assert feature["availability_notes"]


def test_phase6_known_available_surfaces_are_labeled_without_overclaiming():
    by_name = {feature["name"]: feature for feature in _features()}

    assert by_name["Dynamic fee / RBF"]["ui"] == "Available"
    assert by_name["Payment Links"]["ui"] == "Available"
    assert by_name["Explorer watchlists"]["api"] == "Available"
    assert by_name["Localnet harness + chaos drill"]["ui"] == "Guide/status available"
    assert by_name["Production custody"]["badge"] == "Not production"
    assert by_name["Hardware signer"]["badge"] == "Experimental"


def test_features_page_renders_availability_controls_and_disclaimer():
    html = (ROOT / "sites" / "features" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "sites" / "features" / "features.js").read_text(encoding="utf-8")
    css = (ROOT / "sites" / "features" / "features.css").read_text(encoding="utf-8")

    assert "Availability, not production readiness" in html
    assert "featureSurface" in html
    assert "catalogDisclaimer" in html
    assert "Production-ready:" in js
    assert "surfaceBadge('UI'" in js
    assert "surfaceBadge('API'" in js
    assert "surfaceBadge('CLI'" in js
    assert "surfaceBadge('Tests'" in js
    assert "availability-disclaimer" in css
    assert "prod-chip" in css


def test_public_shell_adds_testnet_readiness_banner_and_is_synced():
    shared_js = (ROOT / "sites" / "shared" / "site-shell.js").read_text(encoding="utf-8")
    shared_css = (ROOT / "sites" / "shared" / "site-shell.css").read_text(encoding="utf-8")

    assert "buildReadinessBanner" in shared_js
    assert "Public testnet." in shared_js
    assert "not production claims" in shared_js
    assert "NET has no real-money value" in shared_js
    assert "nc-readiness-banner" in shared_css

    for site_dir in sorted((ROOT / "sites").iterdir()):
        if not site_dir.is_dir() or site_dir.name == "shared":
            continue
        js = site_dir / "site-shell.js"
        css = site_dir / "site-shell.css"
        if js.exists():
            assert js.read_text(encoding="utf-8") == shared_js, js
        if css.exists():
            assert css.read_text(encoding="utf-8") == shared_css, css


def test_openapi_documents_feature_catalog_availability_labels():
    for rel in ["docs/openapi.yaml", "sites/api/openapi.yaml"]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "/features:" in text
        assert "availability labels" in text
        assert "testnet-only production-readiness disclaimers" in text
