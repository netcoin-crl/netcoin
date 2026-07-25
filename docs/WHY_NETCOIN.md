# Why NetCoin exists

Most people learn how cryptocurrencies work from diagrams and explainer articles. NetCoin exists so you can learn by running one.

It's a from-scratch, Bitcoin-family PoW chain — written in Python, with a real UTXO model, real proof-of-work mining, real peer-to-peer nodes, and a real mempool — plus the layer of things people actually build on top of a chain: a non-custodial wallet, a block explorer, escrow and multisig, on-chain usernames, a Reddit-style community, and Polymarket-style prediction markets, all wired to the real chain rather than mocked.

**NetCoin is not Bitcoin, doesn't touch the Bitcoin network, and NET has no real-money value — by design, permanently.** That's not a "not ready yet" disclaimer; it's the point. Keeping it play-money is what lets the project stay focused on being a clean, readable reference for how these systems fit together, instead of becoming a financial product with all the legal and security stakes that come with real money.

## Who this is for

- **People learning how blockchains actually work**, past the whitepaper level — clone it, read `netcoin/chain.py`, mine a block, and watch a transaction move through mempool → block → confirmation.
- **Developers who want a sandbox** to build wallet, payments, or market-layer apps against a real (if small) chain without touching mainnet funds or paying real fees.
- **Anyone who wants to see the whole stack** — consensus, networking, wallet cryptography, and the app layer people build on top — in one project small enough to actually read.

## What's real vs. what's a testnet convenience

Real: proof-of-work mining and difficulty retargeting, UTXO validation, P2P block/tx propagation, wallet key derivation and signing, multisig/escrow/PSBTs, the mempool and fee market.

Testnet convenience: a faucet for free test coins (so you don't need to mine to try things), and no real-world value or exchange listing — that's the deliberate boundary described above.

## Where to go next

- New to the project? Start with the [README](../README.md)'s 5-minute quickstart.
- Want the technical tour? [docs/NODES.md](NODES.md) and [docs/RUN_YOUR_OWN.md](RUN_YOUR_OWN.md).
- Curious where this is headed? [ROADMAP.md](../ROADMAP.md).
