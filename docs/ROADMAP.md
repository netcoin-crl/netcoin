# NetCoin Public Roadmap

This is a direction, not a promise. NetCoin is educational testnet software; there
is no commitment to a mainnet or to any real-money value. Items may change.

## Now — v0.3.x (public launch hygiene & operations)

Shipped in the v0.3.0 line / in progress:

- [x] Reorg handling, peer gossip, propagation, searchable explorer
- [x] RPC auth, request-body caps, fuzz/security/mempool/sync tests
- [x] Wallet safety (verify-mnemonic, backup, recovery test, export guard)
- [x] Explorer JSON API (`/tx`, `/latest`), `/health`, `/metrics`
- [x] Monitoring alerts (webhook), backup and maintenance scripts
- [x] Issue/PR templates, CONTRIBUTING, CODE_OF_CONDUCT, BRAND, this roadmap
- [ ] Real `SECURITY.md` contact, public repo, GitHub Release with artifacts
- [ ] GPG-signed releases, GitHub Actions CI, public status page

## Next — v0.3.2 (operations hardening)

- Faucet CAPTCHA and per-endpoint rate limits
- Disaster-recovery drill (restore from backup)
- Better block-propagation logging
- Public docs website (install / faucet / mining / node / safety)

## v0.4.0 (decentralization push)

- Independent node-runner and miner campaigns
- Peer scoring and banning; stronger compatibility checks
- More sync-resilience and mempool-attack tests
- Public bug-bounty-lite program and weekly status updates
- Testnet reset policy

## v0.5.0 (deeper Bitcoin-like protocol work)

- More complete binary serialization and Script VM
- Better SegWit witness commitment and Taproot/Tapscript behavior
- Full PSBT (BIP174) compatibility; descriptor wallet prototype
- Pruned-node mode, block filters, more realistic compact-block relay
- Stratum-style mining prototype

## Not planned soon (and not without external review)

Mainnet, real-money value, exchange listings, custody, and Lightning-style layer 2
are explicitly **out of scope** until the gates in
[docs/SECURITY_REVIEW_PLAN.md](SECURITY_REVIEW_PLAN.md) are met.
