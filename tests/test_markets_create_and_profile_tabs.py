from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_markets_page_exposes_new_market_action_and_operator_drawer() -> None:
    html = read("sites/markets/index.html")
    assert 'id="newMarketButton"' in html
    assert ">New market<" in html
    assert 'id="operatorTools"' in html
    assert 'id="createMarketForm"' in html
    assert 'id="resolutionQueue"' in html


def test_markets_create_falls_back_to_local_browser_draft() -> None:
    js = read("sites/markets/markets.js")
    assert 'const localMarketsKey = "nc.markets.local.v1"' in js
    assert "function saveLocalMarket" in js
    assert 'mode: "local_browser_draft"' in js
    assert "Saved local market draft" in js
    assert "API write unavailable · saved local draft" in js


def test_local_market_buy_publishes_then_continues_in_place() -> None:
    js = read("sites/markets/markets.js")
    assert 'localDraft ? "Publish & buy"' in js
    assert "async function publishLocalMarket(m)" in js
    assert 'await publishLocalMarket(m)' in js
    assert 'saveLocalMarkets(localMarkets().filter' in js
    assert "browser-only market draft" not in js
    assert 'alert("This is a browser-only' not in js
    assert '$("#newMarketButton")?.addEventListener("click", openCreateMarket)' in js
    assert "source_end_time" in js
    assert "auto_resolution: true" in js
    assert "function renderResolutionQueue" in js


def test_markets_buy_stays_on_markets_and_requires_a_published_market() -> None:
    js = read("sites/markets/markets.js")
    html = read("sites/markets/index.html")
    assert "function requestMarketOrderSignature" in js
    assert "netcoin.signMarketOrder" in js
    assert "local_only" in js
    assert "https://wallet.netcoin.online/?" not in js
    assert "frame-src https://wallet.netcoin.online" in html
    assert 'id="deleteMarket"' in js
    assert "function deleteMarket" in js


def test_trade_panel_supports_selling_not_just_buying() -> None:
    # The buy panel previously only ever submitted BUY orders (side was
    # hardcoded), so a book could only ever fill with one-sided resting buy
    # orders that never cross an opposite order -- the displayed "chance %"
    # froze at whatever the first buy's default price was (50%) because real
    # two-sided price discovery was impossible from the normal UI. A Buy/Sell
    # toggle wired into the real order side is what fixes that.
    js = read("sites/markets/markets.js")
    assert 'orderSide: "buy"' in js
    assert 'data-order-side="buy"' in js
    assert 'data-order-side="sell"' in js
    assert '"[data-order-side]"' in js
    assert 'side: state.orderSide === "sell" ? "sell" : "buy"' in js
    assert 'side: "buy",' not in js


def test_site_profile_controls_are_hidden_from_public_shell() -> None:
    shell = read("sites/shared/site-shell.js")
    css = read("sites/shared/site-shell.css")
    assert "function settingsHtml()" in shell
    assert "return '';" in shell
    assert "netcoinSiteMode" not in shell
    assert "site-settings-panel" not in shell
    assert "site-tools site-tools-compact" in shell
    assert ".site-tools.site-tools-compact" in css


def test_site_shell_assets_stay_synced_after_profile_change() -> None:
    shared_js = read("sites/shared/site-shell.js")
    shared_css = read("sites/shared/site-shell.css")
    for path in sorted((ROOT / "sites").glob("*/site-shell.js")):
        assert path.read_text(encoding="utf-8") == shared_js, path
    for path in sorted((ROOT / "sites").glob("*/site-shell.css")):
        assert path.read_text(encoding="utf-8") == shared_css, path
