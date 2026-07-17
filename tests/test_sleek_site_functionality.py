from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _word_count(html: str) -> int:
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    text = re.sub(r"<[^>]+>", " ", text)
    return len(re.findall(r"\b\w+\b", text))


def test_homepage_is_compact_but_keeps_all_workflow_entrypoints() -> None:
    html = read("sites/www/index.html")
    assert _word_count(html) <= 230
    for token in [
        'data-surface="wallet"',
        'data-surface="developer"',
        'data-surface="explorer"',
        'data-surface="operator"',
        'data-surface="localnet"',
        'data-surface="features"',
        "https://faucet.netcoin.online",
        "https://api.netcoin.online",
        "https://governance.netcoin.online",
        "https://pay.netcoin.online",
        "https://community.netcoin.online",
    ]:
        assert token in html
    assert "Testnet only; no real-money value." in html
    assert "real-money exchange behavior stay locked until proven" in html


def test_wallet_sleek_pass_preserves_available_feature_controls() -> None:
    html = read("sites/wallet/index.html")
    required_ids = [
        "feePresetCards",
        "speedUpCard",
        "btnPreviewRbfBump",
        "psbtToolsCard",
        "btnMakePsbt",
        "btnSignPsbtOffline",
        "btnBroadcastSignedPsbt",
        "multisigToolsCard",
        "btnCreateMultisig",
        "btnCreateMultisigSpend",
        "btnSignMultisigSpend",
        "btnExtractMultisigSpend",
        "txHistory",
        "watchAddress",
        "btnWalletStatement",
    ]
    for value in required_ids:
        assert f'id="{value}"' in html
    assert "wallet-sleek-pass" in html
    assert html.count("</html>") == 1
    assert html.strip().endswith("</html>")


def test_developer_explorer_operator_localnet_and_listing_surfaces_still_expose_tools() -> None:
    checks = {
        "sites/developers/console.html": ["paymentLinkCreator", "apiKeyManager", "webhookManager", "rewardSimulator"],
        "sites/explorer/address.html": ["addrInput", "result", "address"],
        "sites/explorer/tx.html": ["txInput", "result", "transaction"],
        "sites/explorer/mempool.html": ["mempool", "fee"],
        "sites/operator/index.html": ["ledger", "chainstate", "advertise", "maintenance"],
        "sites/docs/localnet.html": ["localnetStatusJson", "cmdHarness", "Start localnet"],
        "sites/exchange/listing.html": ["Code-side gates", "External blockers", "Real listing status"],
        "sites/features/index.html": ["featureSurface", "catalogDisclaimer", "Feature map"],
    }
    for rel, tokens in checks.items():
        html = read(rel)
        if rel.startswith("sites/explorer/"):
            html += "\n" + read("sites/explorer/explorer-pro.js")
        lowered = html.lower()
        for token in tokens:
            assert token.lower() in lowered, (rel, token)


def test_public_shell_is_sleek_and_synced_across_sites() -> None:
    shared_js = read("sites/shared/site-shell.js")
    shared_css = read("sites/shared/site-shell.css")
    assert "Public testnet." in shared_js
    assert "Availability labels are not production claims" in shared_js
    assert "sleek functionality pass" in shared_css
    assert "font-size:14px" in shared_css
    for site_dir in sorted((ROOT / "sites").iterdir()):
        if not site_dir.is_dir() or site_dir.name == "shared":
            continue
        js = site_dir / "site-shell.js"
        css = site_dir / "site-shell.css"
        if js.exists():
            assert js.read_text(encoding="utf-8") == shared_js, js
        if css.exists():
            assert css.read_text(encoding="utf-8") == shared_css, css
