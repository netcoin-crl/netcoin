# NetCoin Professional Launch Checklist

This is the canonical checklist for moving NetCoin from a public educational testnet toward a professional-grade project. It does not mean "mainnet ready"; it means the project is organized, observable, safer to use, and honest about what is still experimental.

Legend:
- `done` - implemented and deployed or documented.
- `in progress` - partially implemented, needs hardening or polish.
- `next` - highest priority unfinished work.
- `later` - important, but not the next blocking step.

## 1. Miner

- done: Unlimited mining command with `--blocks 0`.
- done: Opt-in miner auto-harvest with `--auto-harvest`.
- done: Wallet Mining tab shows both browser-address mining and local-wallet auto-harvest mining.
- next: Miner dashboard that shows blocks mined, accepted/rejected submissions, pending rewards, mature rewards, and auto-harvest events.
- next: Safer long-running miner logs with periodic summaries.
- later: Pool mining dashboard and Stratum-compatible pool protocol.

## 2. Explorer

- done: Live explorer, search, latest blocks, transactions, address pages, mempool, token pages.
- next: Rich address pages with clearer sends/receives/mined rewards/UTXOs.
- next: Better pending transaction state and confirmations.
- next: Public "known service addresses" labels for faucet/treasury/miners.
- later: Charts for difficulty, block spacing, supply, and mempool fee pressure.

## 3. Websites

- done: Separate wallet, explorer, faucet, learn, developers/API, nodes, security, governance, and start sites.
- done: Shared navigation and beginner/developer/node mode shell.
- next: Professional readiness status page using this checklist.
- next: Make every site link to download, explorer, faucet, wallet, docs, and security from the shared shell.
- later: Screenshots, walkthrough videos, public FAQ, and public incident/history page.

## 4. App Layer

- done: Developer API keys and app-layer token/payment/community endpoints.
- done: API-key enforcement on public app-layer writes.
- done: Optional signature-bound token create/mint/transfer/burn actions.
- next: Mandatory signature rollout for tokens after client tooling adopts it.
- next: Signature-bound writes for usernames, merchant actions, and account/profile changes.
- next: App-layer nonce/replay protection.
- next: Signed webhook delivery with verification examples.
- later: Builder dashboard for API keys, usage, apps, webhooks, and logs.

## 5. Faucet

- done: Faucet cooldown, rate limits, queue support, hot-wallet controls, public status.
- done: Clear public status panel showing balance/refill/queue/cooldown.
- next: Faucet abuse dashboard and refill alert.
- later: CAPTCHA/proof-of-work mode if abuse starts.

## 6. Wallet Features

- done: Browser wallet, contacts, labels, activity, fee presets, custom fee, coin status, max send, consolidation guidance.
- done: Legacy/SegWit/P2SH-SegWit/Taproot compatibility.
- next: Wallet activity page polish with sends/receives/mined rewards/pending/confirmations grouped clearly.
- next: Old JSON wallet import/upgrade flow in the hosted wallet and local wallet docs.
- next: HD address rotation as the default beginner receive flow.
- later: PSBT, hardware signer, WebAuthn unlock, offline signing flow.

## 7. Node And Network Ops

- done: Three public seeds, deploy rollback script, health endpoints, public node checks, fast crypto on seeds.
- done: Rate limits, mempool policy caps, public status endpoints.
- next: Public node dashboard with height, tip, version, latency, mempool, peers, and crypto backend.
- next: Alerts for fork, stuck height, seed down, faucet low, and version mismatch.
- later: DNS seeds, better peer discovery, binary P2P as primary network path, compact-block relay at production depth.

## 8. Consensus And Chain Core

- done: Activation policy docs, deterministic reward schedule, spacing-v2 activation, tests.
- next: Written consensus test vectors for difficulty, blocks, transactions, address formats, and signature hashes.
- next: Reindex and crash-recovery operator docs.
- later: Headers-first sync, AssumeUTXO-style fast bootstrap, compact filters at production quality.

## 9. Cryptography

- done: Optional libsecp256k1/coincurve ECDSA verification path with pure-Python compatibility.
- done: Differential tests for fast crypto.
- next: External review of self-rolled crypto behavior and transaction signing model.
- next: Keep pure/fast backends byte-for-byte compatible in CI.
- later: Hardware signer and descriptor-wallet compatibility.

## 10. Docs

- done: Beginner guides, OS-specific instructions, deployment docs, security testing docs, roadmap, NIPs.
- done: Public API docs note optional wallet-signed token actions.
- next: Rewrite top-level README to reflect the current 0.12.x state and recommended public commands.
- next: Add "new terminal / activate venv" reminders anywhere commands span sessions.
- later: Video walkthroughs and guided troubleshooting pages.

## 11. Release And DevOps

- done: GitHub releases, deploy script with rollback, public seed check tooling.
- done: Seed deploys run test suites before restart.
- next: Reproducible release archive fix.
- next: Automated signed releases if a signing-key policy is approved.
- next: Staging deploy environment before seed1.
- later: SBOM, dependency review, release attestation.

## 12. Security And Trust

- done: SECURITY.md, security site, API-key enforcement, SSRF protections, faucet hardening, CSP/security headers.
- next: Signature-bound app-layer writes.
- next: Threat model document covering node, wallet, faucet, app-layer, and public sites.
- next: Stop long-lived decrypted wallet secret caching.
- later: Independent audit before any mainnet/real-money language.

## 13. Governance And Community

- done: NIP process and governance site.
- done: Community posts/improvements/reporting with secret-leak guardrails.
- next: Public decision log and upgrade calendar.
- next: Independent node/miner runner guide and campaign.
- later: Bug-bounty-lite program and contributor recognition.

## Current Recommended Order

1. Miner dashboard polish.
2. Explorer address/activity polish.
3. Professional readiness status page.
4. Signature-bound app-layer writes.
5. Faucet abuse dashboard/refill alerts.
6. Wallet activity/import/HD polish.
7. Node dashboard and alerting.
8. README/docs refresh.
9. Reproducible release/signing hardening.
10. Threat model and security review plan.
