# NetCoin Documentation

NetCoin is an educational, Bitcoin-like **public-testnet** project. It is not
Bitcoin, does not connect to the Bitcoin network, and testnet NET has **no
real-money value**.

This page is the map. Everything is grouped by topic below — start with
**Getting started** if you're new.

---

## 🚀 Getting started (how to use NetCoin)

Everything about *using* NetCoin — installing, making a wallet, getting test
coins, sending, and mining — lives here.

| Doc | What it covers |
| --- | --- |
| [INSTRUCTIONS](../INSTRUCTIONS.md) | Pick your operating system — the beginner entry point |
| [macOS](INSTRUCTIONS_MAC.md) · [Windows](INSTRUCTIONS_WINDOWS.md) · [Linux](INSTRUCTIONS_LINUX.md) | Complete per-OS install → wallet → mine → balance walkthroughs |
| [User Guide](USER_GUIDE.md) | **The comprehensive guide**: hosted apps, install, wallet (browser + CLI), faucet, explorer, mining, local node, and app-layer features |
| [Starter Kit](STARTER_KIT.md) | A 10-minute copy-paste quickstart for new testers |
| [Mining](MINING.md) | Mining NetCoin from your own machine, in depth |
| [Run Your Own](RUN_YOUR_OWN.md) | Run everything yourself with no reliance on the public sites |
| [Devnet](DEVNET.md) | Spin up an instant local devnet |
| [Testnet Runbook](TESTNET.md) | Operating on the public testnet |

## 💳 Wallet & keys

| Doc | What it covers |
| --- | --- |
| [PSBT, RBF, CPFP, watch-only](PSBT_RBF_CPFP_WATCH_ONLY.md) | Advanced spending: fee bumping, partially-signed txs, xpub/watch-only |
| [Key Management](KEY_MANAGEMENT.md) | Key handling policy |
| [Hardware Wallet Integration](HARDWARE_WALLET_INTEGRATION.md) | Offline / hardware signer runbook |
| [Wallet modes & site split](WALLET_MODES_AND_SITE_SPLIT.md) | How wallet surfaces map to the sites |

## 🖧 Running a node & becoming a seed

| Doc | What it covers |
| --- | --- |
| **[NODES](NODES.md)** | **One consolidated guide**: install, sync, mine, become a public seed, troubleshoot |
| [Public Seed Hosting](PUBLIC_SEED_HOSTING.md) | Tunnels, VPS, and dynamic-IP options for exposing a seed |
| [Node Runner](NODE_RUNNER.md) | Running an independent node |
| [Node Reliability & Load](NODE_RELIABILITY_AND_LOAD.md) | Keeping a node healthy under load |
| [Deploy](DEPLOY.md) | Deploying a node from git |
| [Troubleshooting](LOCAL_WALLET_NODE_TROUBLESHOOTING.md) | Local wallet/miner connection problems |

## 🛠️ Developer & API

| Doc | What it covers |
| --- | --- |
| [Architecture Overview](ARCHITECTURE.md) | How the pieces fit together |
| [Developer API — Top 5](DEVELOPER_API_TOP5.md) | The most useful API endpoints |
| [Esplora-compatible API](ESPLORA_API.md) | Block-explorer-style API surface |
| [App-Layer Phases](APP_LAYER_PHASES.md) | Invoices, tokens, escrow, polls, markets |
| [Storage Schema](STORAGE_SCHEMA.md) | On-disk data model |
| [OpenAPI spec](openapi.yaml) | Machine-readable API contract |
| SDKs | [Python](../sdk/netcoin-python/) · [JS](../sdk/netcoin-js/) · [Developer](../sdk/netcoin-developer/) · [Rust](../sdk/netcoin-rs/) |

## 📜 Protocol specification

| Doc | What it covers |
| --- | --- |
| [Spec index](spec/README.md) | The formal protocol specification set |
| [Protocol Spec](PROTOCOL_SPEC.md) | Top-level protocol summary |
| [Consensus Plan](CONSENSUS_PLAN.md) | Consensus-fidelity plan |
| [Economics Plan](ECONOMICS_PLAN.md) · [Upgrade Policy](UPGRADE_POLICY.md) | Emission, and chain-continuity/upgrade rules |

## 🔒 Security

| Doc | What it covers |
| --- | --- |
| [Security Policy](../SECURITY.md) | How to report vulnerabilities |
| [Threat Model](THREAT_MODEL.md) · [Limitations](LIMITATIONS.md) | Attack surface and known limits |
| [Security Testing](SECURITY_TESTING.md) · [Security Review Plan](SECURITY_REVIEW_PLAN.md) | Testing methodology and external-review plan |
| [Pre-Mainnet Security Checklist](PRE_MAINNET_SECURITY_CHECKLIST.md) · [Bitcoin CVE Review](BITCOIN_CVE_THREAT_REVIEW.md) | Hardening gates |
| [Bug Bounty Scope](BUG_BOUNTY_SCOPE.md) · [Web Security Headers](SECURITY_HEADERS.md) | Disclosure scope and web hardening |

## 📦 Release & verification

| Doc | What it covers |
| --- | --- |
| [Releasing](RELEASING.md) | How releases are cut and signed |
| [Reproducible Builds](REPRODUCIBLE_BUILDS.md) · [Reproducible Releases](REPRODUCIBLE_RELEASES.md) | Verifying binaries match source |

## 🏦 Exchange & custody

| Doc | What it covers |
| --- | --- |
| [Exchange Integration](EXCHANGE_INTEGRATION.md) | Sandbox integration: deposits, withdrawals, confirmations, reorgs |
| [Exchange Readiness](EXCHANGE_READINESS.md) · [Manual Payout Signer Flow](MANUAL_PAYOUT_SIGNER_FLOW.md) | Custody readiness and signing flow |
| [Market Integrity](MARKET_INTEGRITY.md) | Prediction-market integrity policy |

## 🧭 Operations & runbooks

| Doc | What it covers |
| --- | --- |
| [Incident Response](INCIDENT_RESPONSE.md) | On-call incident runbook |
| [Admin Operator Dashboard](ADMIN_OPERATOR_DASHBOARD.md) | Operator health tooling |
| [Chaos Drill](CHAOS_DRILL.md) · [Performance Benchmarks](PERFORMANCE_BENCHMARKS.md) | Resilience and perf |
| [Prometheus Metrics](operations/prometheus_metrics.md) · [Localnet Harness](operations/localnet_harness.md) | Monitoring and local multi-node testing |

## 🗺️ Roadmap, mainnet planning & execution

| Doc | What it covers |
| --- | --- |
| [Roadmap](../ROADMAP.md) | The public roadmap |
| [Execution plans](execution/00_MASTER_EXECUTION_PLAN.md) | Milestone-by-milestone execution (M1–M7) |
| [Real-Value Exchange Plan](REAL_VALUE_EXCHANGE_PLAN.md) | What becoming a real-value exchange would take |
| Mainnet gates | [Protocol freeze](MAINNET_PROTOCOL_SPEC_FREEZE.md) · [Monetary policy](MAINNET_MONETARY_POLICY.md) · [Genesis](MAINNET_GENESIS_DISTRIBUTION_PROPOSAL.md) · [Migration](MAINNET_MIGRATION_PLAN.md) · [Governance/legal](MAINNET_GOVERNANCE_LEGAL_RUNBOOK.md) |

## 🏛️ Governance

| Doc | What it covers |
| --- | --- |
| [NIP-0001](nips/NIP-0001.md) | The NetCoin Improvement Proposal process |
| [NIP-0004](nips/NIP-0004.md) · [NIP-0005](nips/NIP-0005.md) | Public node/API standard; upgrade-activation standard |

## 📊 Competitive analysis

Per-domain "how NetCoin compares and what would make it a 10" analyses live in
[docs/competitive/](competitive/README.md).

## 🗄️ Archive

Historical per-version and per-phase completion reports are kept in
[docs/archive/](archive/README.md) for reference — nothing current depends on them.

---

## Public apps

| App | Link |
| --- | --- |
| Wallet | <https://wallet.netcoin.online> |
| Explorer | <https://explorer.netcoin.online> |
| Pay | <https://pay.netcoin.online> |
| Merchant | <https://merchant.netcoin.online> |
| Faucet | <https://faucet.netcoin.online> |
| Markets | <https://markets.netcoin.online> |
| Nodes | <https://nodes.netcoin.online> |
| Community | <https://community.netcoin.online> |
| API Docs | <https://api.netcoin.online> |

Full per-site purpose breakdown: [Public Site Map](PUBLIC_SITE_MAP.md).

## Public testnet node URLs

For local wallet, miner, and balance commands, start with the public API proxy.
Use the seed URLs when testing node-to-node behavior. If your network blocks the
domain, use the raw-IP fallback.

```text
https://api.netcoin.online/api          # preferred
http://18.220.89.128/api                # raw-IP fallback if the domain is blocked
http://seed1.netcoin.online:28444
http://seed2.netcoin.online:28444
http://seed3.netcoin.online:28444
```

## Safety

Never share wallet files, seed phrases, private keys, API keys, or tokens.
Public-testnet coins are for testing only and have no real-money value.
