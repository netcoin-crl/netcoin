# NetCoin v0.18 Live Product Wiring

This release connects the polished v0.17 surfaces to live app/node APIs and adds regression checks for the product wiring.

## Added

- Rich Explorer APIs: `/api/explorer/address/{address}`, `/api/explorer/tx/{txid}`, `/api/explorer/block/{id}`, `/api/explorer/mempool`, `/api/explorer/watchlist`, address CSV exports.
- Markets pages now read live orderbook, ticker, portfolio, dispute/oracle, surveillance, and reconciliation APIs.
- Wallet send workspace now exposes draft saving, unsigned export, and `/api/wallet/workflow` status.
- Community moderation remains available from the Community UI; the existing posts/votes/comments/mod queue APIs stay wired.
- Faucet admin now has operational controls for pause/resume, challenge difficulty, daily cap, blocked requests, and abuse exports.
- Exchange dashboard now reads `/api/exchange/live` for deposits, withdrawals, approvals, custody balances, reserve attestations, and alerts.
- Operator dashboard now reads `/api/operator/live` and exposes `/api/operator/diagnostics/bundle`.
- Feature status probes now map to the live product APIs and v0.18 tests.
- Browser E2E coverage now includes v0.18 live flow surfaces.
- Release verification page supports artifact file hashing and `/api/release/verify` checksum verification.

## Validation performed

- `python -m compileall -q netcoin tools`
- `python tools/professional_upgrade_audit.py --fail-on-issues`
- `python tools/check_openapi_contract.py`
- `python tools/check_product_surface.py`
- `make site-audit`
- `make test-fast`
- `python -m pytest -q tests/test_v018_live_product_wiring.py tests/test_v017_product_polish.py tests/test_v016_product_reliability.py`
- JavaScript syntax checks for Explorer, Markets, Wallet, Faucet Admin, Operator, Exchange, and Download Verify.

## Remaining production caveat

This is still a serious testnet/educational product build, not a mainnet/audited release. The next hardening pass should focus on real browser E2E execution in CI, deeper custody audits, P2P adversarial testing, and external security review.
