from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_generated_platform_files_are_not_packaged() -> None:
    noisy = [str(p.relative_to(ROOT)) for p in ROOT.rglob(".DS_Store")]
    assert noisy == []


def test_public_surfaces_use_product_names_not_internal_phase_labels() -> None:
    public_files = [
        "sites/www/index.html",
        "sites/www/ui-polish.css",
        "sites/wallet/index.html",
        "sites/wallet/wallet-app.js",
        "sites/features/index.html",
        "sites/features/features.css",
        "sites/operator/index.html",
        "sites/operator/operator.css",
        "sites/operator/operator.js",
        "sites/docs/localnet.html",
        "sites/docs/docs.css",
        "sites/exchange/index.html",
        "sites/exchange/listing.html",
        "sites/exchange/exchange.css",
        "netcoin/feature_catalog.py",
    ]
    joined = "\n".join(read(path) for path in public_files)
    for token in ("Phase 5", "Phase 6", "Phase 7", "Phase 8", "Phase 9", "Phase 10"):
        assert token not in joined
    for token in (
        "wallet-flow-guide",
        "send-confirmation-checklist",
        "wallet-availability-card",
        "operator-status-grid",
        "Public testnet hub",
        "A real blockchain you can actually read.",
    ):
        assert token in joined


def test_shared_shell_copies_stay_synced_after_cleanup() -> None:
    shared_js = read("sites/shared/site-shell.js")
    shared_css = read("sites/shared/site-shell.css")
    for site_dir in sorted((ROOT / "sites").iterdir()):
        if not site_dir.is_dir() or site_dir.name == "shared":
            continue
        js = site_dir / "site-shell.js"
        css = site_dir / "site-shell.css"
        if js.exists():
            assert js.read_text(encoding="utf-8") == shared_js, js
        if css.exists():
            assert css.read_text(encoding="utf-8") == shared_css, css
