from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wallet_has_bundled_qr_descriptor_and_psbt_ui():
    html = (ROOT / "webwallet-browser" / "public" / "wallet.html").read_text()
    js = (ROOT / "webwallet-browser" / "public" / "wallet-app.js").read_text()
    assert "qrCanvas" in html
    assert "Descriptors &amp; offline signing" in html
    assert "function makeQrMatrix" in js
    assert "function makeUnsignedPsbt" in js
    assert "function descriptorToWatchAddress" in js


def test_wallet_qr_renderer_does_not_depend_on_external_scripts():
    js = (ROOT / "webwallet-browser" / "public" / "wallet-app.js").read_text()
    assert "challenges.cloudflare.com" not in js
    assert "chart.googleapis.com" not in js
    assert "api.qrserver" not in js
