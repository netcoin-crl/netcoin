from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_testnet_pilot_plan_defines_entry_criteria_and_stop_conditions() -> None:
    doc = read("docs/TESTNET_PILOT_PLAN.md")
    for token in [
        "# NetCoin M1 Two-Week Testnet Pilot Plan",
        "5-10 friends actively use the wallet for two weeks",
        "make m1-rc-check",
        "make m1-rc-strict",
        "Start with 5 testers",
        "expand to 10",
        "Required tester loop",
        "Daily operating rhythm",
        "Stop conditions",
        "Closeout report template",
        "does not claim live seed deployment",
        "real CAPTCHA credentials in source control",
    ]:
        assert token in doc


def test_testnet_pilot_page_is_static_and_links_m1_surfaces() -> None:
    html = read("sites/docs/testnet-pilot.html")
    for token in [
        "M1 pilot plan",
        "Run the two-week tester loop without losing evidence.",
        "testnet-user-journey.html",
        "testnet-feedback.html",
        "https://wallet.netcoin.online",
        "https://faucet.netcoin.online",
        "https://explorer.netcoin.online",
        "https://status.netcoin.online",
        "make m1-rc-check",
        "make m1-rc-strict",
        "Start with 5 testers",
        "expand to 10",
        "Stop conditions",
        "Closeout report fields",
        "does not claim mainnet readiness",
    ]:
        assert token in html
    assert "onclick=" not in html
    assert "<script>" not in html
    assert "Content-Security-Policy" in html


def test_docs_index_journey_and_feedback_surface_pilot_plan() -> None:
    index_html = read("sites/docs/index.html")
    journey_html = read("sites/docs/testnet-user-journey.html")
    feedback_html = read("sites/docs/testnet-feedback.html")
    journey_doc = read("docs/TESTNET_USER_JOURNEY.md")
    feedback_doc = read("docs/TESTNET_FEEDBACK_LOG.md")
    assert "testnet-pilot.html" in index_html
    assert "M1 two-week pilot plan: 5-10 testers with stop conditions" in index_html
    assert "testnet-pilot.html" in journey_html
    assert "Pilot plan" in journey_html
    assert "testnet-pilot.html" in feedback_html
    assert "Open pilot plan" in feedback_html
    assert "docs/TESTNET_PILOT_PLAN.md" in journey_doc
    assert "https://docs.netcoin.online/testnet-pilot.html" in journey_doc
    assert "docs/TESTNET_PILOT_PLAN.md" in feedback_doc


def test_pilot_plan_css_marker_exists() -> None:
    css = read("sites/docs/docs.css")
    assert "M1 pilot plan: two-week tester loop" in css
    assert ".testnet-pilot-page .pilot-checklist" in css
    assert ".testnet-pilot-grid" in css
