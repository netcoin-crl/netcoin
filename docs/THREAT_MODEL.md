# NetCoin Threat Model

NetCoin should be treated as testnet software unless independent audits, legal review, and long-running public testnet operation are complete.

## Assets

- private keys and seed phrases
- wallet files and passphrases
- node chainstate and UTXO set
- faucet hot-wallet funds
- merchant API keys and webhook secrets
- app-layer market/order/refund/treasury state
- release artifacts and checksums
- public seed node availability

## Primary Threats

1. **Key compromise**: stolen wallet files, weak passphrases, exposed seeds, decrypted keys left in memory.
2. **Transaction replay or duplicate writes**: API clients retrying writes or attackers replaying signed app-layer actions.
3. **Node eclipse or peer abuse**: malicious peers isolating a node or feeding invalid data.
4. **Mempool spam**: dust, low-fee transactions, replacement abuse, ancestor/descendant bloat.
5. **Release substitution**: users downloading modified artifacts or unsigned bundles.
6. **Webhook SSRF and secret leakage**: merchant webhooks pointing to private hosts or posts containing secrets.
7. **Prediction-market manipulation**: wash trading, concentration, disputed outcomes, rushed resolution.
8. **Faucet abuse**: repeated claims, queue exhaustion, hot-wallet drain.
9. **Operational outage**: stuck tip, chain split, seed downtime, corrupt node storage.

## Implemented Controls

- encrypted wallet format with AEAD and stronger PBKDF2 defaults
- wallet backup/recovery checks and watch-only exports
- app-layer optional signatures, idempotency keys, nonce replay protection, and API usage tracking
- webhook SSRF guard and signed webhook delivery
- mempool dust/fee/ancestor/descendant/RBF policy
- Prometheus node metrics and monitor tooling
- market compliance warnings, demo-only restrictions, surveillance alerts, and dispute records
- release checksum verification and manifest generation
- professional readiness checker

## Residual Risks

These controls do not replace external code audit, hardware custody, legal review, production incident drills, or public bug bounty programs.
