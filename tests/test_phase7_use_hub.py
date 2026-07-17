from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_homepage_exposes_sleek_use_hub_without_production_claims():
    html = read("sites/www/index.html")
    css = read("sites/www/ui-polish.css")

    assert "Public testnet hub" in html
    assert "NetCoin public testnet." in html
    assert "Developer Console" in html
    assert "https://developers.netcoin.online/console.html" in html
    assert "https://docs.netcoin.online/localnet.html" in html
    assert "id=\"available-now\"" in html
    assert "data-surface=\"wallet\"" in html
    assert "data-surface=\"developer\"" in html
    assert "data-surface=\"explorer\"" in html
    assert "data-surface=\"operator\"" in html
    assert "data-surface=\"localnet\"" in html
    assert "Feature status" in html
    assert "Gated" in html
    assert "production custody" in html
    assert "Testnet only; no real-money value." in html
    assert "No real-money value" in html
    assert "use-hub-grid" in css
    assert "not-ready-card" in css


def test_phase7_homepage_links_to_every_available_workflow():
    html = read("sites/www/index.html")
    required_links = [
        "https://wallet.netcoin.online",
        "https://developers.netcoin.online/console.html",
        "https://explorer.netcoin.online",
        "https://operator.netcoin.online",
        "https://docs.netcoin.online/localnet.html",
        "https://features.netcoin.online",
        "https://faucet.netcoin.online",
        "https://api.netcoin.online",
    ]
    for link in required_links:
        assert link in html

    for phrase in [
        "Fees, RBF preview, PSBT, multisig, history",
        "Payment links, API keys, webhooks, simulations",
        "Addresses, UTXOs, tx risk, mempool",
        "Audit, chainstate, peers, maintenance status",
        "Copy commands and verify services",
    ]:
        assert phrase in html


def test_site_shell_search_and_palette_surface_available_workflows():
    shell = read("sites/shared/site-shell.js")
    assert "Developer Console" in shell
    assert "payment links, API keys, webhooks" in shell
    assert "Localnet" in shell
    assert "copyable testnet launch commands" in shell
    assert "Feature status" in shell
    assert "availability labels and test coverage" in shell
    assert "rbf|speed up|fee preset|psbt|multisig" in shell
    assert "ledger audit|chainstate|peer advertise|maintenance" in shell
    assert "developer console|payment link|api key|webhook|reward simulation" in shell
    assert "localnet|local testnet|launch local|copyable command" in shell
    assert "availability|available now|feature status|test coverage" in shell

    shared = read("sites/shared/site-shell.js")
    for site_dir in sorted((ROOT / "sites").iterdir()):
        if not site_dir.is_dir() or site_dir.name == "shared":
            continue
        js = site_dir / "site-shell.js"
        if js.exists():
            assert js.read_text(encoding="utf-8") == shared, js
