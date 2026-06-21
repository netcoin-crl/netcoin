# Known Limitations

NetCoin is an **educational testnet**. Being honest about what it is *not* is part
of the project. Read this before relying on NetCoin for anything.

## Top-line

- **Not Bitcoin** and not connected to the Bitcoin network.
- **No real-money value.** Testnet NET is for learning only.
- **Not production-hardened** and **not externally security-reviewed**.
- **Testnet may be reset.** Balances and history can be wiped without notice.

## Technical limitations

- **Educational cryptography:** the wallet file encryption is a simple HMAC-stream
  construction, not a vetted AEAD. Fine for testnet, not for real secrets.
- **JSON over HTTP P2P**, not the Bitcoin binary wire protocol. Endpoints are
  readable but not bandwidth- or DoS-optimized like Bitcoin Core.
- **Headers-first sync is shape-only**; full block download still happens.
- **Script engine is a teaching model**, not the full Bitcoin Script VM.
- **SegWit/Taproot are "-style"** approximations, not byte-exact Bitcoin behavior.
- **PSBT is "-like"**, not full BIP174.
- **Small network:** few nodes/miners; low hashpower means low reorg cost. Do not
  treat confirmations as strong security.
- **No package relay, descriptors, coin control, or hardware-wallet support.**

## Operational limitations

- Public services (explorer, faucet, monitor) run on a single seed host today.
- Rate limiting is basic; no CAPTCHA on the faucet yet.
- RPC must stay bound to localhost (optionally token-protected); never expose it.

## What to do instead

- Use NetCoin to **learn** how a UTXO chain, mempool, mining, and reorgs work.
- Run a node, mine a block, use the faucet, send a transaction, read the code.
- Report bugs via the GitHub issue templates. For security issues, see
  [../SECURITY.md](../SECURITY.md).

See also [BRAND.md](../BRAND.md) and [docs/SECURITY_REVIEW_PLAN.md](SECURITY_REVIEW_PLAN.md).
