# NetCoin v0.17 Full Validation + Product Polish

This upgrade focuses on finishing the product surfaces that users and operators touch most.

## Added

### Full validation workflow
- `make test-full` now runs the suite by file with per-file timeouts.
- `make test-report` writes a deterministic full-suite plan to `reports/full_suite_plan.json`.
- `make ci-local` mirrors the main quality gates locally.
- `tools/run_browser_e2e.py` starts a local server and runs Playwright, saving `reports/browser_e2e_report.json`.

### Explorer polish
- Added rich Explorer pages:
  - `sites/explorer/address.html`
  - `sites/explorer/tx.html`
  - `sites/explorer/block.html`
  - `sites/explorer/mempool.html`
- Added `sites/explorer/explorer-pro.js` and `explorer-pro.css` for address lookup, UTXO tables, CSV statement export links, tx/block detail views, and mempool summaries.

### Markets polish
- Added trading-grade entry pages:
  - `sites/markets/trade.html`
  - `sites/markets/portfolio.html`
  - `sites/markets/disputes.html`
  - `sites/markets/settlement.html`
- Added compact order ticket, price ladder, chart placeholder, open orders, dispute panel, and settlement report panels.

### Wallet merge
- Merged Overview, Send, Receive, Activity, and Contacts into one sleek **Wallet** workspace.
- Added sticky section shortcuts for Overview, Send, Receive, Activity, and Contacts.
- Kept advanced features available in mode-based tabs: Mining, Tokens, Payments, Reports, Watch-only, Escrow, Advanced, Contracts, Developer, Settings.

### Faucet admin
- Added `sites/faucet/admin.html` and `faucet-admin.js` with abuse decisions, daily spend cap, challenge bits, reputation records, emergency pause placeholder, and export shortcut.

### Exchange dashboard v2
- Expanded Exchange dashboard with deposit states, withdrawal states, custody balance cards, reserve checks, risk alerts, and release verification shortcuts.

### Operator diagnostics
- Expanded Operator dashboard with live feature wiring, health fingerprint, runbook recommendations, and better alert summaries.

### Feature catalog live status
- Added `netcoin/feature_status.py`.
- Added `/api/feature-status`.
- The Features site now displays live file/test/route probes next to the static rating catalog.

### Release verification page
- Added `sites/download/verify.html` and `verify.js` with checksum comparison, signature/provenance commands, SBOM instructions, and Health Center release-trust status.

## Validation run

- `python -m compileall -q netcoin tools`
- `python tools/professional_upgrade_audit.py --fail-on-issues`
- `python tools/check_openapi_contract.py`
- `python tools/check_product_surface.py`
- `make site-audit`
- `make test-fast`
- `python -m pytest -q tests/test_v017_product_polish.py`
- `python -m pytest -q tests/test_v016_product_reliability.py tests/test_do_it_big_impact_fixes.py tests/test_thorough_rerate_fixes.py`
- JS syntax checks for wallet, explorer, markets, faucet admin, download verify, and features scripts.

## Still not a production/mainnet claim

This version improves user-facing polish, testing workflow, and operator visibility. Production/mainnet readiness still requires full long-running public testnet evidence, external crypto/security audit, hardened P2P soak testing, and real release signing/provenance adoption in CI.
