# v0.40.1 Browser Strict Proof Bugfix

This release fixes the first real strict-browser failure reported from a local Mac run. The Playwright gate was reaching pages, but localhost surface detection mounted the generic completion panel instead of wallet/markets/faucet/operator panels. The browser matrix then failed token checks even though the site files loaded.

## Fixes

- Local surface detection now prefers `body[data-site]` and `/sites/<surface>/...` paths before hostname-derived subdomains.
- Wallet, markets, faucet, and operator completion panels expose the matrix tokens expected by the strict browser test.
- A root `package.json` pins `@playwright/test` and `playwright` so local `node_modules/.bin/playwright` is created after `npm install`.
- Browser and accessibility runners prefer the local Playwright binary before falling back to `npx`.
- Local proof runner rewrites `python ...` proof commands to the current Python interpreter, so macOS `python3` installs do not require an alias.
- Static GET fallback JSON files reduce local `python3 -m http.server` E2E noise for health/operator/exchange/faucet demo endpoints.

## Local strict browser commands

```bash
cd ~/Downloads/netcoin-main
npm install
npm run playwright:install
python3 tools/run_browser_e2e_matrix.py --run-playwright
python3 tools/run_accessibility_matrix.py --strict
python3 tools/run_local_proof.py --profile strict --timeout 300
```

The project still cannot honestly claim hardware signer device coverage, real CAPTCHA credentials, production custody operations, or external security audit until those are run outside the source tree.
