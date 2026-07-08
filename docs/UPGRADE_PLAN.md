# NetCoin Upgrade Plan — raising production readiness

Honest status: as an **educational chain** NetCoin is ~8.5/10; as a **production
cryptocurrency** it is ~4/10. This document tracks the changes that move the
production number, plus the next 20 biggest upgrades.

Two items cap everything else and cannot be solved with code alone:
- **A) Third-party crypto audit** (money + auditor)
- **B) Real decentralization** (independent human operators)

Nothing security-sensitive exceeds ~6 until (A) lands.

---

## The top-10 readiness levers

| # | Change | Buildable by us? | Status / plan |
|---|--------|------------------|---------------|
| 1 | Crypto audit / move all crypto to audited libs | Partial (libs yes, audit no) | ECDSA *verify* already on libsecp256k1 (coincurve). **Plan:** move signing + Schnorr + address codec onto audited libs behind the same differential-test gate; commission an audit when funded. |
| 2 | Independent node operators | Enablers only | **Plan:** one-command installer, node-diversity dashboard on nodes.netcoin.online, "run a seed" incentive + docs. People must follow. |
| 3 | Signature-bound app-layer writes | **Yes** | **Next release (v0.13).** Require a signed-message envelope proving control of the `from` address for token transfer / username / escrow writes. Removes the "API key ≠ owner" gap. |
| 4 | Wallet key-handling hardening | **Yes** | Stop caching decrypted secret in sessionStorage; auto-lock timer; memory zeroing; optional hardware-wallet signing path. |
| 5 | Second implementation / consensus test vectors | Partial | **Plan:** publish frozen consensus test vectors + a minimal independent verifier (Rust/Go) run in CI against the live chain. |
| 6 | Real persistence/scale | **Yes** | Make SQLite backend the default; add covering indexes; move signature verification off the request thread so big txs never stall reads. |
| 7 | Hardened P2P | **Yes (partial)** | Addr-relay hardening, eclipse-attack resistance (peer diversity buckets), per-peer DoS budgets, binary transport as default. |
| 8 | Monitoring / alerting / incident response | **Yes** | Prometheus metrics (already exposed) → alerting; public status history; on-call runbook. |
| 9 | Supply-chain / release hardening | **Yes** | Full reproducible-build attestation, dependency pinning + audit, CI-signed artifacts, SLSA-style provenance. |
| 10 | Economic-security honesty / mainnet plan | **Yes (doc)** | Document the lone-miner floor as permanent-testnet, OR write a credible mainnet security plan (checkpoints, sustained hashpower, fair launch). |

---

## The next 20 biggest upgrades (ranked)

1. **Signature-bound app-layer writes** (#3) — token/username/escrow ownership. *Highest value/effort.*
2. **Wallet + Pay UI remake** — single-screen send, no scrolling, no visible send cap (auto-consolidate-then-send under the hood), size-scaled fees.
3. **Auto-consolidate-then-send** in the wallet — removes the 200-input send ceiling transparently.
4. **Dynamic fee estimator** — fee scales with tx weight/input count instead of a flat value (partly addressed: presets raised).
5. **SQLite backend by default** + off-thread verification (#6).
6. **Wallet key hardening** (#4) — sessionStorage, auto-lock, hardware wallet.
7. **Node-diversity dashboard + one-command installer** (#2 enabler).
8. **Signed-message standard (NIP-0008)** — the envelope format that #1/#3 both use.
9. **Move signing + Schnorr onto audited libs** (#1 code portion).
10. **Consensus test vectors + independent verifier in CI** (#5).
11. **Prometheus alerting + public status history** (#8).
12. **Reproducible-build attestation + CI-signed artifacts** (#9).
13. **P2P hardening: addr-relay + eclipse resistance + DoS budgets** (#7).
14. **Light-client mode** — headers + block filters already exist; ship an SPV wallet path.
15. **RBF / CPFP fee bumping** in the wallet + mempool policy (gated as a NIP).
16. **WebSocket event stream** for wallets/explorer (push new blocks/txs; SSE exists, upgrade).
17. **HD account management UI** — multiple accounts, gap-limit scan, watch-only, in the browser wallet.
18. **Merchant/Pay production hardening** — idempotency keys, webhook retries with backoff + dead-letter UI, refund reconciliation.
19. **Token standard v2** — signature-bound transfers, allowances/approvals, metadata, token explorer analytics.
20. **Mainnet readiness checklist execution** — checkpoints, fair-launch parameters, difficulty bootstrap, published security model (#10).

---

## Sequencing

- **v0.13** — #3 signature-bound writes + NIP-0008 signed-message standard.
- **v0.14** — Wallet/Pay UI remake + auto-consolidate-then-send + dynamic fees (#2, #3, #4 of the 20).
- **v0.15** — SQLite-default + off-thread verify + wallet key hardening (#5, #6).
- **v0.16** — Node-diversity dashboard, installer, monitoring/alerting (#7, #11).
- **Ongoing** — audit fundraising (#1), independent operators (#2), mainnet plan (#10/#20).
