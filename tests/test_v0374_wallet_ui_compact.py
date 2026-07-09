from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_wallet_workspace_subtabs_removed_from_runtime_ui():
    js = read("sites/wallet/wallet-app.js")
    html = read("sites/wallet/index.html")
    assert "walletWorkspaceNav" not in js
    assert "#walletWorkspaceNav{display:none!important}" in html
    assert '["Overview", "#wallet-home"]' not in js
    assert '["Send", "#wallet-send"]' not in js


def test_wallet_send_receive_side_by_side_and_compact_balance_css_present():
    css = read("sites/wallet/ui-polish.css") + read("sites/wallet/index.html")
    assert "#walletView:not(.hide){display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "#wallet-home .bal{font-size:clamp(26px,3.1vw,40px)" in css
    assert "#wallet-receive.active-section,#wallet-send.active-section" in css
    assert ".send-recipient-row,.send-amount-row,.send-quick-row" in css


def test_backups_are_settings_owned_and_contact_send_autolabel_exists():
    js = read("sites/wallet/wallet-app.js")
    assert 'card.querySelector("#contactsImportFile")) { tab = "settings"' in js
    assert "wallet-settings-backups" in js
    assert 'const SEND_META_STORE = "ncw.sentMeta.v1"' in js
    assert "recordSentTxMeta(txid, sent.to, sent.amt, sent.fee)" in js
    assert "Sent to ${contact.name}" in js
