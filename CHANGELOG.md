# Changelog

All notable changes to NetCoin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> NetCoin is an educational, Bitcoin-like cryptocurrency and public testnet.
> Testnet NET has no real-money value. See [SECURITY.md](SECURITY.md) and the
> safety notes in [README.md](README.md).

## [Unreleased]

### Added
- Node `/health` (height, tip, peers, version, uptime, services) and `/metrics`
  (Prometheus text format) endpoints.
- Version handshake: `/info` now reports `version`, `user_agent`, `network`, and
  `genesis_hash`; peers are checked for genesis/network compatibility before sync.
- Built-in public testnet seeds and a `node --seeds` flag to join without copying URLs.
- Wallet commands: `wallet-backup` (timestamped copy), `wallet-recover-test`
  (restore a seed into a temp wallet and verify the address), and
  `wallet-export-watch` (watch-only export with no private key). `wallet-info
  --show-private` now requires `--i-understand-export-risk`.
- Community/repo files: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `BRAND.md`,
  [docs/ROADMAP.md](docs/ROADMAP.md), [docs/LIMITATIONS.md](docs/LIMITATIONS.md),
  and a GitHub Actions CI workflow (`.github/workflows/ci.yml`).
- Explorer-style node JSON API: `GET /tx/<txid>` and `GET /latest?n=` (alongside the
  existing `/block/<hash>`, `/utxos?address=`, and `/mempool`).
- Monitoring alerts: the monitor compares against the previous status and posts
  transition alerts (DOWN / RECOVERED / tip divergence) to a Discord/Slack-style
  webhook (`NETCOIN_ALERT_WEBHOOK`).
- `tools/faucet_admin.py` private admin dashboard (hot-wallet balance, granted
  requests, abuse log) and `tools/backup_node.sh` / `tools/deploy_seed.sh` operator
  scripts (backup; safe update with automatic rollback).
- Docs: [docs/UPGRADING.md](docs/UPGRADING.md) and
  [docs/SECURITY_REVIEW_PLAN.md](docs/SECURITY_REVIEW_PLAN.md); GitHub issue/PR
  templates under `.github/`.

### Fixed
- `wallet-watch` was broken (`Wallet.watch_only` was referenced but never defined);
  added the missing helper so watch-only wallet files work.

### Tests
- Suite expanded to 100: mempool attack policy (dust, low fee, duplicate inputs,
  over-weight, RBF conflicts), peer-sync resilience (unreachable peers, restart
  persistence, catch-up after downtime, peer loss, delayed blocks), node JSON API,
  `/health` + `/metrics` + handshake + peer compatibility, wallet CLI (backup,
  recovery test, watch-only export, export guard), and ops tooling (faucet admin
  render, monitor alert transitions).

### Planned
- GPG-signed release artifacts published with each GitHub release (tooling exists).
- Faucet CAPTCHA.

## [0.3.0] - 2026-06-20

Hardening, recovery, and P2P release: reorg handling, peer gossip, propagation,
a searchable explorer, RPC auth, DoS caps, wallet safety, faucet hardening, tester
guides, and a release process. 67 automated tests.

### Added
- Optional JSON-RPC bearer-token authentication (`--rpc-token` / `NETCOIN_RPC_TOKEN`),
  with a startup warning when bound to a non-local address without a token.
- Request-body size cap on the node and RPC HTTP servers (`MAX_REQUEST_BODY_BYTES`)
  to blunt trivial memory-DoS attempts.
- Static testnet status dashboard generator (`tools/dashboard.py`) that renders the
  monitor `status.json` into an auto-refreshing HTML page.
- `verify-mnemonic` CLI command to confirm a seed phrase is valid and (optionally)
  regenerates a given wallet, backed by `wallet.verify_seed_phrase` and
  `Wallet.matches_seed_phrase`.
- Faucet hardening: request-body cap, a global per-minute burst throttle, an
  in-state abuse log, and a hot-wallet balance gate (all configurable via env vars).
- Node peer persistence: discovered peers are saved to `peers.json` in the data
  directory and reloaded on restart so the node reconnects to known peers.
- Stronger chain reorganization: `add_block` now keeps off-tip blocks in a bounded
  fork pool and switches to the heaviest fully valid branch by cumulative work,
  with rollback, automatic out-of-order (orphan) connection, and mempool
  revalidation that returns transactions from disconnected blocks.
- More reliable block propagation: relay de-duplication (a bounded memory of
  broadcast hashes) prevents echoed blocks from looping, and accepting a block
  that triggers a reorg also relays the new tip.
- Searchable explorer: the generated `index.html` now embeds a per-block index and
  a client-side search box for height, block hash, txid, and address (still static).
- Peer gossip / auto-discovery: nodes pull peer lists from known peers
  (`discover_peers`), announce an advertised URL so peers can dial back
  (`announce_self`, `node --advertise`), and `bootstrap` combines announce +
  discover + sync on startup. Self-exclusion and a peer cap bound growth.
- Tester guides: [docs/STARTER_KIT.md](docs/STARTER_KIT.md),
  [docs/NODE_RUNNER.md](docs/NODE_RUNNER.md), [docs/MINING.md](docs/MINING.md).
- Release process and tooling: [docs/RELEASING.md](docs/RELEASING.md) and
  `tools/make_release.sh` (reproducible archive + SHA256SUMS + optional GPG signature).

### Security
- Expanded automated tests to 67: subsidy/halving schedule, RPC auth (401/200),
  node and faucet body/throttle limits, wallet recovery and encryption round-trips
  (incl. tamper/wrong-passphrase rejection), peer persistence, chain reorg
  (heavier-fork adoption, equal-work tie kept, invalid/bad-PoW fork rejection,
  out-of-order connection, mempool revalidation), explorer/dashboard rendering
  with HTML-escaping, and a fuzz suite for transaction/block parsing,
  raw-transaction decoding, script parsing, and node endpoints.

## [0.2.0] - 2026-06-20

First public 3-seed testnet release.

### Added
- **Consensus & chain**: UTXO validation, proof-of-work mining, Merkle roots,
  coinbase rewards with 100-block maturity, 21,000,000 NET cap, 210,000-block
  halvings, block-weight limit, difficulty retargeting, and orphan-candidate
  handling.
- **Transactions**: creation/signing/validation, mempool policy (dust, min relay
  fee, weight, ancestor limits), locktime/sequence, opt-in RBF, SegWit-style
  txid/wtxid split, raw hex export and decoding.
- **Wallets**: creation, deterministic seed phrases, restore, WIF import,
  encrypted and watch-only wallet files, balance/UTXO commands.
- **Addresses & signatures**: secp256k1 ECDSA, Base58Check legacy addresses,
  Bech32 P2WPKH, Bech32m P2TR, BIP340-style Schnorr key-path spends, P2SH-SegWit.
- **Scripts**: educational script engine with P2PKH/P2SH/P2WPKH/P2WSH/P2TR
  templates, multisig, and CLTV/CSV timelock helpers.
- **Networking**: HTTP peer node with `/info`, `/peers`, `/chain`, `/headers`,
  `/block`, `/compact-block`, `/blocktemplate`, `/mempool`, `/utxos`, and POST
  relay/sync endpoints; headers-first sync shape; P2P message framing helpers.
- **Mining workflow**: external `miner` and `submitblock` CLI commands,
  `GET /blocktemplate?address=...`, `POST /submitblock`, and an `submitblock` RPC
  method (`netcoin/miner.py`).
- **RPC & pool**: JSON-RPC server, educational mining-pool template server,
  PSBT-like signing container.
- **Explorer / faucet / monitoring**: static HTML explorer generator, testnet
  faucet, and a status monitor (`tools/`).
- **Docs**: [docs/TESTNET.md](docs/TESTNET.md) runbook,
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and
  [docs/SECURITY_TESTING.md](docs/SECURITY_TESTING.md).

### Security
- Regression suite (`tests/test_security_regressions.py`) covering malformed and
  over-weight blocks, far-future timestamps, internal/mempool/cross-block double
  spends, forged and wrong-key signatures, transaction replay, peer-sync
  adoption/rejection, headers clamping, and node resilience to garbage input.
  Full suite: 28 passing.

### Known limitations
- Educational software, not production-hardened. Not Bitcoin; does not connect to
  the Bitcoin network. `SECURITY.md` currently uses a placeholder reporting
  contact. Public endpoints are not yet rate-limited.

[Unreleased]: https://github.com/Adoniyas1/netcoin/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Adoniyas1/netcoin/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Adoniyas1/netcoin/releases/tag/v0.2.0
