# Bitcoin-style upgrade tracker

This document tracks the 50 requested upgrades in a dependency-aware order. Items marked **implemented** have code in this branch. Items marked **scaffolded** have APIs, docs, tests, or UI entry points prepared but still need a deeper protocol/security implementation.

| Order | Upgrade | Status | Notes |
|---:|---|---|---|
| 1 | Wallet contact save/delete/select | Implemented | `webwallet-browser/public/wallet-app.js`, shared `ncw.contacts.v1`. |
| 2 | Explorer contact save/delete/select | Implemented | `webexplorer/public/explorer-app.js`, shared storage. |
| 3 | GitHub Actions CI | Implemented | `.github/workflows/ci.yml`. |
| 4 | Automatic tests before merge | Implemented | CI runs pytest across Python versions. |
| 5 | Dependency audit | Implemented | `.github/workflows/security.yml` runs `pip-audit` and `npm audit`. |
| 6 | Remove stale signatures after file changes | Implemented policy | Stale wallet manifest signatures are not carried forward after manifest changes. |
| 7 | Signed release checksums | Implemented | Existing release workflow builds and verifies `SHA256SUMS`. |
| 8 | GPG-signed releases | Partially implemented | Release workflow can import `NETCOIN_GPG_PRIVATE_KEY` / `NETCOIN_GPG_KEY_ID` secrets and verify artifacts; actual private key material must be supplied by the maintainer. |
| 9 | Address validation warnings | Implemented | Browser wallet validates recipient/payment link before send. |
| 10 | Offline/stale-data warning | Implemented | Browser wallet status bar reports online/offline refresh state. |
| 11 | Copy address button improvements | Implemented | Existing copy button retained; payment URI copy added. |
| 12 | QR code receive page | Implemented | Payment URI creation/copy/share plus a bundled offline canvas QR renderer for normal-length receive links. |
| 13 | QR code send scanner | Implemented where supported | Uses browser `BarcodeDetector` + camera; falls back to paste instructions. |
| 14 | NetCoin URI support | Implemented | Browser wallet parses and creates `netcoin:` URIs. |
| 15 | Payment request links | Implemented | Receive panel creates shareable payment links. |
| 16 | Confirm-before-send screen | Implemented | Send flow now requires a review/confirm step. |
| 17 | Saved contact import/export | Implemented | Browser wallet imports/exports contact JSON. |
| 18 | Encrypted contact backup file | Implemented | AES-GCM encrypted contact backup with user password. |
| 19 | Wallet transaction history labels/notes | Implemented | Local per-transaction labels under `ncw.txlabels.v1`. |
| 20 | Explorer contact labels | Implemented | Explorer shows saved contact names beside addresses. |
| 21 | Multiple wallet profiles/accounts | Implemented | Browser wallet now stores multiple separately encrypted local profiles, migrates the legacy single-wallet store, and lets users create/restore/unlock/delete profiles. |
| 22 | Watch-only wallet mode | Implemented | Browser wallet now has local watch-only address monitoring; no private key is imported for watched addresses. |
| 23 | Descriptor wallet system exposed in UI | Partially implemented | Core descriptor code exists; browser wallet now exports the active wpkh() descriptor and can import simple wpkh() descriptors into watch-only monitoring. Full descriptor checksum/range discovery remains future work. |
| 24 | Multisig wallet support | Scaffolded | PSBT/descriptors exist; full UX remains TODO. |
| 25 | Hardware-wallet-style/offline PSBT signing | Partially implemented | Existing PSBT tests/code provide foundation; browser wallet can now export an unsigned NetCoin PSBT from the send form/coin-control selection. Full hardware-wallet integration remains future work. |
| 26 | Rich transaction decode page | Implemented | Explorer transaction page now shows status, wtxid, inputs/outputs, and raw JSON. |
| 27 | Address page upgrades in explorer | Implemented | Address page now includes local contact labels and improved recent tx display. |
| 28 | Block reward + fee breakdown page | Implemented | Node/explorer block APIs now expose coinbase value, subsidy, and fee totals; explorer displays the breakdown. |
| 29 | Newest blocks live feed | Implemented | Home auto-refreshes latest blocks. |
| 30 | Newest transactions live feed | Implemented | Node/explorer expose latest-txs APIs; explorer home shows newest mempool and confirmed transactions. |
| 31 | API docs page | Implemented | Explorer has an API docs route. |
| 32 | WebSocket/live wallet/explorer updates | Partially implemented | Node and live explorer expose Server-Sent Events at `/events/stream` / `/api/events/stream`; browser explorer uses SSE with polling fallback. |
| 33 | Mempool explorer page | Implemented | Explorer route `#/mempool`; API endpoints added. |
| 34 | Fee estimator slow/normal/fast | Implemented | Node/explorer expose `fee-estimates`; wallet consumes presets. |
| 35 | Coin control / UTXO picker | Implemented | Browser wallet can fetch spendable UTXOs, select exact outpoints, review selected total, and build the transaction from those coins only. |
| 36 | RBF / CPFP / package relay | Partially implemented | Opt-in RBF now requires higher absolute fee, higher fee rate, and incremental relay delta. Compact CPFP/package acceptance and `/package` relay endpoint are implemented. Full Bitcoin Core package policy remains deeper work. |
| 37 | Faucet rate limits/CAPTCHA | Partially implemented | Faucet hardening tests exist; CAPTCHA remains deployment-specific. |
| 38 | Faucet status page | Implemented | Faucet exposes `/status`; explorer has a Faucet page that reads same-origin `/faucet/status` or proxied `/api/faucet/status`. |
| 39 | Seed node / peer status page | Implemented | Explorer peer route added; node exposes `/peers`. |
| 40 | Network hash rate / difficulty charts | Partially implemented | Explorer has a Network Stats page with recent difficulty-bit history and average block interval; exact hash-rate estimates remain approximate on test networks. |
| 41 | Headers-first sync | Partially implemented | Header APIs exist; full headers-first sync pipeline remains TODO. |
| 42 | Orphan transaction/block handling | Partially implemented | Orphan candidate tracking exists; deeper policy remains TODO. |
| 43 | Peer scoring/banning/rate limits/eclipsing | Partially implemented | Peer scores/banned list/rate limiter exist; eclipse-resistance hardening remains TODO. |
| 44 | Stronger P2P network layer | Partially implemented | Binary P2P exists; production-hardening remains TODO. |
| 45 | Compact block relay | Partially implemented | Compact block endpoints/code exist; deployment tuning remains TODO. |
| 46 | Compact block filters/light wallet mode | Partially implemented | Block filter endpoint exists; light-wallet scanning UX remains TODO. |
| 47 | AssumeUTXO-style snapshot sync | Partially implemented | UTXO snapshot/digest functions exist; trusted snapshot bootstrapping remains TODO. |
| 48 | Production-grade consensus validation | Ongoing | Core checks exist; needs long-running fuzzing, invariants, reorg/regression expansion, and review. |
| 49 | External security review/audit | Not implemented | Must be performed by independent reviewers after code freeze. |
| 50 | Final production-readiness cleanup | Not implemented | Depends on audit fixes, release signing, and protocol hardening. |

## Remaining non-one-pass work

The remaining gaps are not honest single-edit completions. They require either long-running validation, deployment secrets, or independent human review:

1. Full external security audit after a code freeze.
2. Real hardware-wallet vendor integration.
3. Full Bitcoin Core-level package mempool policy and adversarial relay testing.
4. Compact-filter light-wallet scanning UX across many wallet scripts/ranges.
5. AssumeUTXO trusted bootstrap release process with signed snapshots and background verification.
6. Long-running consensus/P2P fuzzing, reorg, and eclipse-resistance testing before any mainnet-style deployment.

## Functional phases 1–6 implementation pass

A later pass added app-layer utility on top of the Bitcoin-style wallet/explorer work:

- payment/invoice creation, checkout status, receipts, validation API
- usernames/profiles, SDK starters, shareable profile data
- merchant API keys, webhook registry/event queue, refund records, sales CSV
- gifts, airdrop dry runs, bounties, leaderboards, bot starter folders
- wallet statements, CSV reports, alerts, limits, backup health, team wallet records
- labels, network health, mining dashboard/calculator, node map, reward countdown, treasury transparency

These features are deliberately app-layer state in `app_layer.json`; they are not consensus changes.
