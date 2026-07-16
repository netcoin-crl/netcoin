# NetCoin v0.16 Product + Reliability Polish

This pass focuses on the existing user/operator-facing product rather than adding a new protocol feature.

## Added

- Dedicated Operator dashboard site: `sites/operator/`
- Dedicated Exchange/custody dashboard site: `sites/exchange/`
- Unified product health center: `netcoin/health_center.py`
- API endpoints: `/api/health-center` and `/api/product/status`
- Product-surface checker: `tools/check_product_surface.py`
- Full-suite planning/report tool: `tools/full_suite_report.py`
- Additional Playwright E2E coverage for operator, exchange, explorer, markets, community, and features pages
- Richer Explorer quick cards for mempool, latest blocks, address lookup, and operator health
- Markets quick strip for orderbook, portfolio, disputes, and settlement
- Shared site shell now includes Operator and Exchange navigation entries

## Purpose

The project already has many features. The v0.16 goal is to make them easier to find, easier to operate, and easier to test.

## Validation commands

```bash
python -m compileall -q netcoin tools
python tools/professional_upgrade_audit.py --fail-on-issues
python tools/check_openapi_contract.py
python tools/check_product_surface.py
make test-fast
make site-audit
python -m pytest -q tests/test_v016_product_reliability.py
```

## Remaining work

- Run the monolithic full test suite in CI with enough time and a clean dev environment.
- Connect exchange dashboard to live deposit/withdrawal rows.
- Connect operator dashboard to live logs and backup/restore drills.
- Run Playwright E2E tests in a browser-enabled CI job.
- Continue hardening P2P block relay and hardware signer vendor adapters.
