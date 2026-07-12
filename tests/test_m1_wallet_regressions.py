from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_WALLET = ROOT / "sites" / "wallet"
WEB_WALLET = ROOT / "webwallet-browser" / "public"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_wallet_tab_shell_does_not_anchor_to_lock_button_or_cards():
    """Guard the historical ensureWalletTabShell regression.

    A prior redesign nested #btnLock and code that inserted sections relative to
    that button broke the create/unlock path. The shell may append/prepend top
    level chrome, but it must not depend on #btnLock or an existing card anchor.
    """
    for path in [SITE_WALLET / "wallet-app.js", WEB_WALLET / "wallet-app.js"]:
        js = _read(path)
        assert "function ensureWalletTabShell()" in js
        assert "wallet.prepend(tabs);" in js
        assert "insertBefore(tabs" not in js
        assert "insertBefore(section" not in js
        assert (
            '$("btnLock")'
            not in js[js.index("function ensureWalletTabShell()") : js.index("function applyWalletMode()")]
        )


def test_wallet_m1_polish_markup_is_present():
    html = _read(SITE_WALLET / "index.html")
    assert 'class="wallet-page-title"' in html
    assert 'class="pill testnet-pill" id="netpill"' in html
    assert '<details class="balance-explain">' in html
    assert "<summary>What this balance means</summary>" in html
    assert '<button id="btnCopy">Copy address</button>' in html
    assert '<button id="btnRefresh" class="secondary ghost">Refresh</button>' in html
    assert '<h1 style="font-size:' not in html
    assert "<h2>Receive</h2>" in html
    assert "<h2>Send</h2>" in html
    assert 'class="wallet-page m1-hide-shell-search"' in html
    assert "body.m1-hide-shell-search .site-search{display:none!important}" in html


def test_wallet_auto_lock_controls_are_exposed_and_configurable():
    html = _read(SITE_WALLET / "index.html")
    js = _read(SITE_WALLET / "wallet-app.js")
    for token in ["unlockAutoLock", "privateKeyAutoLock"]:
        assert token in html
        assert token in js
    assert "sessionAutoLock" in js
    assert 'const AUTO_LOCK_STORE = "ncw.autoLockMinutes.v1";' in js
    assert "function scheduleAutoLock()" in js
    assert "function noteWalletActivity()" in js
    assert "Auto-lock disabled for this tab" in js


def test_wallet_app_sri_matches_site_html():
    html = _read(SITE_WALLET / "index.html")
    match = re.search(r'<script src="wallet-app\.js\?v=[^"]+" integrity="([^"]+)"', html)
    assert match, "wallet-app.js script tag must keep SRI"
    actual = (
        "sha384-" + base64.b64encode(hashlib.sha384((SITE_WALLET / "wallet-app.js").read_bytes()).digest()).decode()
    )
    assert match.group(1) == actual
