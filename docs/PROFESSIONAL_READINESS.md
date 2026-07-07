# Professional Readiness Automation

Run the checker:

```bash
python tools/professional_readiness.py
python tools/professional_readiness.py --issues
netcoin professional-check --issues
```

The checker validates documentation, release tooling, protocol vectors, wallet safeguards, mempool policy, node metrics, market surveillance, idempotency, nonce replay controls, status pages, and tests.

The `mainnet_safe` field intentionally remains false. Automated checks cannot replace independent audit, legal review, incident drills, public testnet history, or custody due diligence.
