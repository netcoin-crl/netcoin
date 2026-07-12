from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_testnet_feedback_log_defines_safe_intake_template() -> None:
    doc = read("docs/TESTNET_FEEDBACK_LOG.md")
    for token in [
        "# NetCoin M1 Testnet Feedback Log",
        "two-week M1 tester loop",
        "no tester should share a seed phrase",
        "ID | Stable local tracker ID",
        "Device/browser",
        "Expected | What should have happened",
        "Actual | What happened instead",
        "Status snapshot",
        "P0:",
        "P1:",
        "Retest result:",
        "does not claim live seed deployment",
    ]:
        assert token in doc


def test_testnet_feedback_page_links_journey_and_forbids_inline_behavior() -> None:
    html = read("sites/docs/testnet-feedback.html")
    for token in [
        "M1 feedback loop",
        "Turn tester friction into reproducible bugs.",
        "testnet-user-journey.html",
        "Never collect secrets",
        "Device/browser:",
        "Expected result:",
        "Actual result:",
        "Status snapshot if relevant:",
        "make m1-rc-strict",
        "does not claim mainnet readiness",
    ]:
        assert token in html
    assert "onclick=" not in html
    assert "<script>" not in html
    assert "Content-Security-Policy" in html


def test_docs_index_and_user_journey_surface_feedback_intake() -> None:
    index_html = read("sites/docs/index.html")
    journey_html = read("sites/docs/testnet-user-journey.html")
    journey_doc = read("docs/TESTNET_USER_JOURNEY.md")
    assert "testnet-feedback.html" in index_html
    assert "M1 feedback intake: capture friction without collecting secrets" in index_html
    assert "Report friction" in journey_html
    assert "Use the feedback intake template" in journey_html
    assert "docs/TESTNET_FEEDBACK_LOG.md" in journey_doc
    assert "https://docs.netcoin.online/testnet-feedback.html" in journey_doc


def test_feedback_css_marker_exists() -> None:
    css = read("sites/docs/docs.css")
    assert "M1 feedback intake: tester issue capture" in css
    assert ".testnet-feedback-page .notice.warn" in css
    assert ".testnet-feedback-grid" in css
