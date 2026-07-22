from __future__ import annotations

import base64
import hashlib
import re
import shutil
import subprocess
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


def test_wallet_accepts_visible_signing_requests_only_from_netcoin_sites():
    js = _read(SITE_WALLET / "wallet-app.js")
    assert 'requesterHost !== "netcoin.online"' in js
    assert 'requesterHost.endsWith(".netcoin.online")' in js
    assert 'request.type !== "netcoin.signAppRequest"' in js
    assert '"netcoin.marketOrderSignature" : "netcoin.appRequestSignature"' in js
    assert 'id="btnAuthorizeMarketRequest"' in js


def test_wallet_api_helper_never_surfaces_a_raw_non_json_response_body():
    """Regression: a 502/504 from nginx returns a full raw HTML error page as
    the response body. The shared api() helper must never hand that page to
    the user as an error message (it previously did, via `data = { error: text }`
    on a JSON.parse failure) — it must fall back to a short, bounded message."""
    js = _read(SITE_WALLET / "wallet-app.js")
    assert "data = { error: text }" not in js
    assert "non-JSON response from node" in js
    match = re.search(r"async function api\(path, opts\) \{(.*?)\n  \}", js, re.DOTALL)
    assert match, "api() helper not found"
    body = match.group(1)
    assert "let parsed = true" in body
    assert "parsed = false" in body



def test_wallet_rbf_and_multisig_controls_are_exposed():
    html = _read(SITE_WALLET / "index.html")
    js = _read(SITE_WALLET / "wallet-app.js")
    for token in [
        'id="feePreset"',
        'id="feePresetCards"',
        'data-fee-preset="slow"',
        'data-fee-preset="normal"',
        'data-fee-preset="fast"',
        'id="rbfOptIn"',
        'id="speedUpCard"',
        'id="rbfOriginalTx"',
        'id="rbfPrevouts"',
        'id="rbfBroadcastNow" type="checkbox" /> Broadcast replacement immediately',
        'id="btnPreviewRbfBump"',
        'id="btnBumpFee"',
        'id="psbtToolsCard"',
        'id="btnMakePsbt"',
        'id="signedPsbtOut"',
        'id="multisigToolsCard"',
        'id="btnCreateMultisig"',
        'id="multisigSpendPsbt"',
        'id="multisigProgress"',
    ]:
        assert token in html
    for token in [
        'api("/fee-estimates")',
        'function updateFeePresetCards(tiers)',
        'function chooseFeePreset(presetName)',
        'broadcast = Boolean($("rbfBroadcastNow")?.checked)',
        'function hydrateRbfBumpCard()',
        'function bumpFeeFromCard()',
        'rbf: true,',
        'api("/wallet/multisig/create"',
        'api("/wallet/multisig/psbt/create"',
        'api("/wallet/multisig/psbt/sign"',
        'api("/wallet/psbt/extract"',
        'function setMultisigProgress(progress)',
        'rbf: Boolean($("rbfOptIn")?.checked)',
    ]:
        assert token in js


def test_phase1_wallet_tools_are_available_on_normal_wallet_tab():
    html = _read(SITE_WALLET / "index.html")
    js = _read(SITE_WALLET / "wallet-app.js")
    assert 'class="card wallet-availability-card" id="speedUpCard"' in html
    assert 'class="card wallet-availability-card" id="psbtToolsCard"' in html
    assert 'class="card wallet-availability-card" id="multisigToolsCard"' in html
    assert 'card.classList.contains("wallet-availability-card")' in js
    assert 'tab = "wallet"' in js[js.index('card.classList.contains("wallet-availability-card")') : js.index('else if (card.querySelector("#contactsImportFile"))')]
    assert "Preview is non-broadcast by default" in html
    assert 'id="rbfBroadcastNow" type="checkbox" /> Broadcast replacement immediately' in html


def test_wallet_browser_bundle_sets_rbf_sequence_when_requested():
    node = shutil.which("node")
    if not node:
        return
    script = """
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync("sites/wallet/netcoin-wallet.js", "utf8");
const ctx = { crypto: require("crypto").webcrypto, TextEncoder, TextDecoder };
vm.createContext(ctx);
vm.runInContext(code + ";this.NCW=NCW;", ctx);
const W = ctx.NCW;
const priv = W.newRandomPrivateKey();
const wallet = W.walletFromPrivateKey(priv, "segwit");
const recipient = W.walletFromPrivateKey(W.newRandomPrivateKey(), "segwit").address;
const common = {
  privHex: priv,
  utxos: [{ txid: "00".repeat(32), vout: 0, amount: 100000, address: wallet.address }],
  toAddress: recipient,
  amount: 50000,
  fee: 1000,
  changeAddress: wallet.address,
};
const finalTx = W.buildSignedPayment({ ...common, rbf: false });
const rbfTx = W.buildSignedPayment({ ...common, rbf: true });
if (finalTx.inputs[0].sequence !== 0xffffffff) throw new Error("non-RBF send should keep final sequence");
if (rbfTx.inputs[0].sequence !== 0xfffffffd) throw new Error("RBF send should use an opt-in sequence");
"""
    result = subprocess.run([node, "-e", script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
