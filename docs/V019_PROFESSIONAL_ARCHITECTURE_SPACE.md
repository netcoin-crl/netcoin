# NetCoin v0.19 — Professional Architecture Space

v0.19 does not replace the current Python reference app. It creates the professional language layout and upgrade lanes for the final system.

## Final target

| Layer | Language | Role |
|---|---|---|
| Core | Rust | consensus, transaction validation, mempool, wallet-core, market invariants |
| Node | Rust | P2P, sync, peer scoring, metrics/RPC bridge |
| Indexer | Rust | block/address/mempool/market event indexing and reorg rollback |
| API | TypeScript | product API, auth/RBAC, community, faucet, market and exchange dashboard routes |
| Web | TypeScript / Next.js | wallet, explorer, markets, community, faucet, operator, exchange, release verification |
| Desktop | Rust + TypeScript/Tauri | desktop wallet, offline signing, hardware signer UI |
| Mobile | React Native TypeScript first, Swift/Kotlin later | mobile wallet and QR workflows |
| Ops | Python | reference implementation, tests, release tooling, simulations, reports |

## Upgrade spaces added

- `core-rs/`
- `node-rs/`
- `indexer-rs/`
- `api/`
- `web/`
- `desktop/`
- `mobile/`
- `ops/python/`
- `architecture/`
- `sites/architecture/`

## New checks

```bash
make arch-check
```

This confirms the hybrid architecture spaces exist and the manifest is readable.

## Final version gates

NetCoin should not call itself production/mainnet-ready until all final-version gates in `architecture/final-system-manifest.json` pass, including full tests, Rust parity vectors, hostile P2P soak, browser E2E, release verification, hardware/offline signing verification, and external audit evidence.
