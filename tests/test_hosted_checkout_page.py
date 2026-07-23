from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_pay_site_has_a_hosted_checkout_view():
    html = read("sites/pay/index.html")
    assert 'id="checkout"' in html
    assert 'id="checkoutQr"' in html
    assert 'id="checkoutStatusText"' in html
    assert 'id="checkoutWalletLink"' in html
    assert "<script>" not in html
    assert "Content-Security-Policy" in html
    assert "script-src 'self'" in html


def test_pay_js_implements_checkout_polling_without_new_script_sources():
    js = read("sites/pay/pay.js")
    assert "function checkoutInvoiceId" in js
    assert "function renderCheckout" in js
    assert "function pollCheckout" in js
    assert "function initCheckout" in js
    assert "setInterval(() => pollCheckout(id), 4000)" in js
    # reads either query param or a /pay/<id> path so it works with or without
    # server-side path routing for the checkout_url the developer API returns
    assert "params.get('invoice')" in js
    assert "/pay/" in js


def test_pay_js_syntax_is_valid():
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        return
    result = subprocess.run([node, "--check", str(ROOT / "sites/pay/pay.js")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
