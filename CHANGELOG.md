# Changelog

All notable changes to NetCoin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> NetCoin is an educational, Bitcoin-like cryptocurrency and public testnet.
> Testnet NET has no real-money value. See [SECURITY.md](SECURITY.md) and the
> safety notes in [README.md](README.md).

## [Unreleased]

### Added
- **Local multi-node soak/stress harness** (`python -m netcoin soak`) starts
  multiple in-process HTTP nodes, connects them as peers, mines mature funds,
  relays transactions/blocks, syncs tips, and reports convergence for release
  and deployment smoke testing.
- **Deterministic fuzz smoke runner** (`python -m netcoin fuzz`) exercises parser
  and public endpoint surfaces; CI now runs it under Python dev mode.
- **Crash-safe chain persistence + reindex.** The JSON backend now writes
  `chain.json`/`mempool.json` via fsync'd temp files, atomic `os.replace`, and a
  `.bak` mirror of the last committed state. On load, a corrupt live file is
  recovered from the backup (or a leftover `.tmp`) without losing the most recent
  block, and a corrupt mempool is dropped rather than blocking startup. New
  `python -m netcoin reindex` rebuilds the indexes and UTXO set from block data
  and reports a chainstate integrity check.

## [0.4.2] - 2026-06-22

### Added
- **Spending from P2SH-SegWit (P2SH-P2WPKH) addresses** is now wired into
  `sign_input`/`verify_input`: the nested P2WPKH redeem script goes in the
  scriptSig and the signature + pubkey go in the witness, matching how a wrapped
  SegWit input is spent. Closes the only remaining known gap from v0.4.1.
  (`create_transaction ... from_type="p2sh-segwit"`; 2 new tests, 233 total.)

## [0.4.1] - 2026-06-21

Protocol-depth and wallet release: real headers-first sync, compact-block relay
with missing-tx requests, SegWit witness commitment, fuller Script VM, full PSBT,
output descriptors, change-address rotation, wallet auto-lock, and migration.
231 automated tests.

### Added
- **Real headers-first sync**: nodes validate remote headers, then fetch missing
  blocks by hash (with a legacy `/chain` fallback); a TCP P2P helper does the same
  over `getheaders → headers → getdata(block) → block`.
- **Compact-block relay** with missing-transaction detection and a
  `/compact-block-missing` endpoint.
- **SegWit-style witness commitment** for blocks containing witness transactions.
- **Change-address rotation** (`send --rotate-change`, persisted `change_index`).
- **Wallet auto-lock** sessions (`wallet-unlock --ttl-seconds`).
- **Faucet CAPTCHA hooks** (simple challenge / Cloudflare Turnstile / hCaptcha).
- **Explorer API pagination** for latest blocks and address history.
- **Wallet file format versioning + migration**: wallet files now carry a
  `wallet_version`; `wallet-migrate` upgrades older files to the current format and
  re-encrypts at the upgraded KDF cost (backing up the original first).
- **Output descriptors** (`netcoin/descriptors.py`): `pkh`/`wpkh`/`tr`/`sh(wpkh)` and
  `sh(multi(...))` descriptors; `wallet-descriptor` exports a wallet's descriptors and
  `descriptor-address` resolves a descriptor to its address (watch-only, no keys).
- **Full PSBT workflow**: `PartiallySignedTransaction.create` (build an unsigned
  PSBT from inputs/outputs) and `combine` (merge signatures from multiple parties,
  each signing the inputs it owns), plus `combine_psbts` and `finalize`/`extract`
  — completing create → sign → combine → finalize → extract.
- **Fuller Script VM**: the script engine gains conditionals (`OP_IF`/`OP_NOTIF`/
  `OP_ELSE`/`OP_ENDIF`), arithmetic/comparison opcodes (`OP_ADD`, `OP_SUB`, `OP_MIN`/
  `MAX`, `OP_WITHIN`, `OP_NUMEQUAL(VERIFY)`, `OP_LESSTHAN`/`GREATERTHAN`, …), stack
  ops (`OP_SWAP`/`OVER`/`ROT`/`NIP`/`TUCK`/`2DUP`/`DEPTH`/`IFDUP`), more hashing
  (`OP_SHA256`/`HASH256`/`RIPEMD160`), `OP_SIZE`, `OP_RETURN`, `OP_CHECKSIGVERIFY`/
  `OP_CHECKMULTISIGVERIFY`, with strict errors and unbalanced-conditional detection.

### Known gaps
- Spending *from* a P2SH-SegWit address was not yet wired in `sign_input` (only
  address generation was supported). _Resolved in [Unreleased]._

## [0.4.0] - 2026-06-21

Networking, storage, and protocol-depth release: TCP P2P transport, relay queue +
inventory cache, background sync, SQLite backend + pruned mode, a persistent UTXO
set, a lossless binary codec, an API-backed explorer, and faucet hardening.
192 automated tests.

### Added
- **TCP P2P transport** (`p2p-server` / `p2p-call`, `DEFAULT_P2P_PORT=18447`) running
  the P2P message layer over real sockets; HTTP remains the stable public seed API.
- **Relay queue + tx/block inventory cache** (retry/backoff) with `GET`/`POST /relay`
  and a background sync loop; `/health` adds `relay_queue`, `/metrics` adds
  `netcoin_relay_queue_items`.
- **API-backed explorer service** (`netcoin/explorer_server.py`, `explorer-server`):
  live HTML pages plus `/api/latest|block|tx|address|search`.
- **Faucet send queue + hot-wallet isolation/refill** (queued mode, `/queue`,
  `/status`, admin `process-queue`, configurable via env vars).
- **GET + POST per-IP/per-path rate limiting** (`--rate-limit-per-min`; `0` disables).
- **Lossless binary codec** (`tx_to_binary`/`tx_from_binary`,
  `block_to_binary`/`block_from_binary`): a compact binary encoding that round-trips
  full transactions and blocks while preserving txid/wtxid/hash — complements the
  existing Bitcoin-style raw-hex export.
- **Bitcoin-style P2P message layer** (`netcoin/p2p.py`): `version`, `verack`,
  `ping`, `pong`, `inv`, `getdata`, `getheaders`, `headers`, `block`, and `tx`
  messages over the magic/command/length/checksum envelope, with a `handle_message`
  flow (version→verack, ping→pong, getheaders→headers, inv→getdata, getdata→block/tx).
  Block/tx messages carry the binary codec payload.
- **Persistent/incremental UTXO set**: `utxo_set()` now serves an authoritative
  in-memory cache (kept in sync through mining and reorgs, verified against a full
  recompute) instead of rescanning the whole chain on every call.
- **Pruned mode** (SQLite backend): `prune` command / `Blockchain.prune(keep_depth)`
  drops old block bodies from disk while keeping headers and a UTXO snapshot. A
  reloaded pruned node trusts the snapshot, keeps the recent tail, and can keep
  mining. (A pruned node can't deep-reorg below the pruned floor — the standard
  pruned-node tradeoff; keep at least the 2016-block difficulty window.)
- `wallet-scan` (gap-limit): derive addresses `0..gap` from a seed and report
  on-chain activity per index.

### Changed
- **Wallet KDF upgrade**: new encrypted wallets use 600k PBKDF2 iterations (was
  250k) and `cipher` `netcoin-hmac-stream-v2`. Older 250k wallets still open
  (the iteration count is read from the file); re-saving upgrades them.

### Security
- Mempool **ancestor limit**: a transaction with too many unconfirmed ancestors
  (> `MAX_MEMPOOL_ANCESTORS`) is rejected.

### Added (continued)
- **Optional SQLite storage backend** (`netcoin/storage.py`) for blocks, the
  active-chain ordering, and the mempool. Select with `backend="sqlite"` or
  `NETCOIN_BACKEND=sqlite`; JSON remains the default. New `migrate-sqlite` command
  converts an existing JSON data directory. Survives mining, reorgs, and restarts.
- **UTXO snapshot** export/verify with a deterministic digest (`utxo-snapshot` CLI,
  `export_utxo_snapshot` / `verify_utxo_snapshot`).
- **Multisig address** builder CLI (`multisig-address --required M --pubkey ...`).
- **Structured JSON logging** (`netcoin/logsetup.py`, `NETCOIN_LOG_JSON=1`); the node
  emits propagation events as JSON lines.
- Explorer **mempool section** (unconfirmed transactions with fee rates).
- Operations guide (`docs/OPERATIONS.md`): structured logging, **log rotation**, and
  **deploying tagged releases** with rollback.
- **Address index** (`address_summary`) and a node `GET /address/<addr>` endpoint
  returning balance, UTXO count, and the transactions that touch an address.
- **Node config file** (`netcoin.conf`, JSON or `key=value`) via `node --config`.
- Faucet **public history API** (`GET /history`, recent grants without client IPs).
- Metrics polish: added `netcoin_banned_peers` gauge.
- Persistent block and transaction **indexes** for O(1) `/block` and `/tx` lookups
  (rebuilt on load and kept in sync through mining and reorgs), plus a
  `verify_integrity()` chainstate check.
- **Peer reputation**: scoring (`score_peer`) and banning (`ban_peer`, persisted to
  `banned_peers.json`) with auto-ban at a threshold; `/peers` reports scores/bans.
- **Protocol-version negotiation**: peers on a different protocol version are rejected.
- **Mempool eviction**: `evict_expired_mempool` (age) and `evict_mempool_to_size`
  (lowest-fee-rate first).
- **Coin-selection strategies** for spending: `send --coin-strategy`
  (greedy / largest-first / smallest-first / random).
- GitHub Actions **release workflow** (build + checksum + GitHub Release on tag).
- Coin control: `send --utxo TXID:VOUT` (repeatable) to spend specific UTXOs.
- Wallet labels / address book (`netcoin/labels.py`, `label` CLI: `--set/--get/--remove/--list`).
- `wallet-unlock` command (verify an encrypted wallet opens; optionally write a
  decrypted copy) and `wallet-new --confirm-backup` (re-enter the seed to confirm backup).
- Per-IP, per-endpoint **rate limiting** on POST endpoints (configurable, 429 on excess).
- Block-propagation **event log** with a `GET /events` endpoint
  (block received/accepted/rejected/relayed, orphan connected, tx received).
- Configurable peer-fetch **timeout and retries**.
- Private beta tester invite doc ([docs/BETA_INVITE.md](docs/BETA_INVITE.md)).
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
- Suite expanded to 171 (adds binary-codec round-trips for coinbase/signed/segwit
  txs and blocks, and the P2P message layer: framing, binary block/tx payloads,
  and handler flow).
- Earlier: 159 (adds persistent-UTXO correctness through spends/reorgs and
  pruned-mode round-trips: prune, reload, keep mining, balances).
- Earlier: 151 (adds KDF upgrade + legacy-wallet compatibility, mempool
  ancestor limit, and gap-limit scan).
- Earlier: 146 (adds the SQLite backend: persistence, restart, reorg,
  mempool, store unit, and migration).
- Earlier: 141 (adds UTXO snapshot export/verify, multisig address,
  structured-log formatting, and the explorer mempool section).
- Earlier: 134 (adds address index + /address endpoint, node config
  file parsing, and faucet public-history).
- Earlier: 128 (adds block/tx index + chainstate integrity, peer
  banning/scoring + protocol negotiation, mempool eviction, coin-selection
  strategies, and a monitor alert-payload test).
- Earlier: suite expanded to 114 (adds node ops: event log, rate limiting, timeout/retry,
  multi-node mempool propagation; and wallet features: coin control, seed
  confirmation, wallet unlock, label store).
- Earlier in this line, suite expanded to 100: mempool attack policy (dust, low fee, duplicate inputs,
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

[Unreleased]: https://github.com/netcoin-crl/netcoin/compare/v0.4.2...HEAD
[0.4.2]: https://github.com/netcoin-crl/netcoin/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/netcoin-crl/netcoin/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/netcoin-crl/netcoin/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/netcoin-crl/netcoin/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/netcoin-crl/netcoin/releases/tag/v0.2.0
