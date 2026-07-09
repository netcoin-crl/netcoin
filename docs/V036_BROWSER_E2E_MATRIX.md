# NetCoin v0.36 Browser E2E Matrix

v0.36 adds browser E2E coverage scaffolding for the main product surfaces:

- wallet
- explorer
- markets
- faucet
- operator dashboard
- exchange dashboard

Files:

- `architecture/browser-e2e-matrix.json`
- `sites/tests/e2e/netcoin-product-matrix.spec.ts`
- `tools/run_browser_e2e_matrix.py`

Run the source gate:

```bash
python tools/run_browser_e2e_matrix.py
make v036-check
```

When Playwright is installed, run the real browser matrix:

```bash
python tools/run_browser_e2e_matrix.py --run-playwright
```
