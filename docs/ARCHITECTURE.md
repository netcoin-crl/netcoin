# NetCoin Architecture Overview

NetCoin is an educational public-testnet cryptocurrency project. It is designed to be small enough to read while still showing the major pieces found in a Bitcoin-like system.

## Main components

| Component | Purpose |
| --- | --- |
| Chain | Validates blocks, transactions, proof of work, UTXO updates, and reorgs |
| Wallet | Creates keys, addresses, wallet files, signed transactions, and backups |
| Node API | Exposes public read endpoints and transaction submission endpoints |
| P2P layer | Experiments with peer discovery, inventory relay, and sync behavior |
| Mempool | Holds unconfirmed transactions and applies policy limits |
| Miner | Builds candidate blocks and searches for valid proof of work |
| Explorer | Reads node data and displays blocks, transactions, addresses, and health |
| Faucet | Gives limited public-testnet coins to new users |
| App layer | Demonstrates payments, merchant tools, community features, and markets |

## Public app split

The hosted public apps are separated by user intent:

- Wallet: user wallet actions and wallet tools.
- Explorer: chain lookup and network health.
- Pay: customer checkout and payment requests.
- Merchant: business dashboard and integrations.
- Faucet: public-testnet coin requests.
- Community: campaigns, bounties, gifts, and leaderboards.
- Markets: prediction-market demos and Phase 7 experiments.
- Docs: public guides.
- API Docs: endpoint reference and examples.

This prevents the Explorer from becoming a catch-all dashboard.

## Chain model

NetCoin uses a UTXO model. Transactions consume previous outputs and create new outputs. Blocks commit to transactions using a Merkle root. The node validates transaction signatures, script rules, coinbase maturity, block proof of work, and cumulative-work fork choice.

## Wallet model

Wallet files can be encrypted. The project includes deterministic seed phrases, HD derivation, watch-only wallet support, descriptor helpers, signed messages, payment URIs, and PSBT-like signing flows.

## Network model

Public testnet nodes expose an HTTP API and experimental peer-to-peer behavior. Use these public seed hostnames in examples:

```text
http://seed1.netcoin.online:28444
http://seed2.netcoin.online:28444
http://seed3.netcoin.online:28444
```

## Data and storage

The reference implementation uses simple local files for readability. Optional SQLite support exists for some storage paths. A production-quality network would require more hardening, monitoring, review, and operational controls than this educational repository provides.

## Security boundaries

Never publish wallet files, seed phrases, private keys, API tokens, or admin credentials. Public reports should include only non-sensitive logs, public transaction IDs, public addresses, and reproducible steps.

## What this project is not

NetCoin is not Bitcoin, is not a production money system, and does not have real-world liquidity. It is a public-testnet learning project and experimentation environment.
