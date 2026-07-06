# Known Limitations

NetCoin is an **educational testnet**. Being honest about what it is *not* is part
of the project. Read this before relying on NetCoin for anything.

## Top-line

- **Not Bitcoin** and not connected to the Bitcoin network.
- **No real-money value.** Testnet NET is for learning only.
- **Not production-hardened** and **not externally security-reviewed**.
- **Testnet may be reset.** Balances and history can be wiped without notice.

## Technical limitations

- **Educational cryptography:** new encrypted wallet files use ChaCha20-Poly1305
  AEAD from the vetted `cryptography` package with PBKDF2-HMAC-SHA256, and old
  HMAC-stream wallets can be opened for migration. The wider wallet/key-management
  system is still not externally reviewed, so it remains testnet-only.
- **HTTP remains the stable public seed API.** NetCoin now has an experimental
  TCP P2P transport using Bitcoin-style message envelopes, but it is not yet a
  full Bitcoin Core-style networking stack.
- **Headers-first sync is shape-only**; full block download still happens.
- **Script engine is a teaching model**, not the full Bitcoin Script VM.
- **SegWit/Taproot are "-style"** approximations, not byte-exact Bitcoin behavior.
- **PSBT is "-like"**, not full BIP174.
- **Small network:** few nodes/miners; low hashpower means low reorg cost. Do not
  treat confirmations as strong security.
- **No package relay, descriptors, coin control, or hardware-wallet support.**
- **Not exchange-listed/mainnet-ready.** The exchange guide is for sandbox
  integration and future review, not real-money custody.

## Operational limitations

- Public services (explorer, faucet, monitor) run on a single seed host today.
- The live explorer is backed by local node data, not a separate production
  search database yet.
- Faucet rate limiting is basic; queued payouts and refill checks reduce hot-wallet
  exposure, but there is no CAPTCHA yet.
- RPC must stay bound to localhost (optionally token-protected); never expose it.

## What to do instead

- Use NetCoin to **learn** how a UTXO chain, mempool, mining, and reorgs work.
- Run a node, mine a block, use the faucet, send a transaction, read the code.
- Report bugs via the GitHub issue templates. For security issues, see
  [../SECURITY.md](../SECURITY.md).

See also [BRAND.md](../BRAND.md) and [docs/SECURITY_REVIEW_PLAN.md](SECURITY_REVIEW_PLAN.md).
