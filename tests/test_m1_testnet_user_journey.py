from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_public_testnet_user_journey_doc_exists_and_names_m1_loop() -> None:
    doc = read("docs/TESTNET_USER_JOURNEY.md")
    for token in [
        "# NetCoin M1 Testnet User Journey",
        "Open the wallet",
        "Claim faucet NET",
        "Confirm the incoming transaction",
        "Send a small test payment",
        "Lock the wallet",
        "Check the status page",
        "testnet NET has no real-money value",
        "does not claim mainnet readiness",
    ]:
        assert token in doc


def test_public_testnet_user_journey_page_links_core_surfaces() -> None:
    html = read("sites/docs/testnet-user-journey.html")
    for token in [
        "M1 tester path",
        "wallet.netcoin.online",
        "faucet.netcoin.online",
        "explorer.netcoin.online",
        "status.netcoin.online",
        "First-time tester checklist",
        "make m1-rc-check",
        "make m1-rc-strict",
        "Host: wallet.netcoin.online",
        "does not claim mainnet readiness",
    ]:
        assert token in html
    assert "onclick=" not in html
    assert "<script>" not in html
    assert "Content-Security-Policy" in html


def test_docs_index_surfaces_testnet_user_journey() -> None:
    html = read("sites/docs/index.html")
    assert "testnet-user-journey.html" in html
    assert "M1 tester path: wallet -> faucet -> explorer -> status" in html


def test_user_journey_css_marker_exists() -> None:
    css = read("sites/docs/docs.css")
    assert "M1 user journey: public tester path" in css
    assert ".testnet-journey-page .journey-steps" in css
