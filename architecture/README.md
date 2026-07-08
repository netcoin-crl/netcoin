# NetCoin Professional Architecture Space

This directory is the transition plan from the current Python reference app to a professional hybrid system.

The final target is:

- **Rust** for money-critical core logic: consensus, P2P, wallet-core, mempool, matching/settlement invariants.
- **TypeScript** for the product app: web UI, public API, SDKs, dashboards, community, markets, explorer surfaces.
- **Python** for reference behavior, test vectors, release tooling, QA automation, simulations, and operations.

The existing Python app remains runnable and authoritative until a new component passes parity tests against frozen vectors.
