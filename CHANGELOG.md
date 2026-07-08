# Changelog

All notable changes to NetCoin are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> NetCoin is an educational, Bitcoin-like cryptocurrency and public testnet.
> Testnet NET has no real-money value. See [SECURITY.md](SECURITY.md) and the
> safety notes in [README.md](README.md).

## [Unreleased]

## [0.14.0] - 2026-07-08 — Upgrade layer plus: wallet vault, operator/exchange/indexer modules, stricter CI

### Added
- Browser wallet vault (`wallet-vault.js`) providing encrypted profile storage,
  session handling, and auto-lock behind the existing non-custodial wallet.
- Operator/exchange/indexer upgrade layer: `netcoin/exchange*`, `indexer*`,
  `wallet_policy`/`wallet_approvals`/`wallet_risk`, `coin_control`, `signer`,
  `offline`, `tx_simulator`, `recovery`, `sync`, `peerdb`, `metrics`,
  `ops_runbooks`/`ops_incidents`, `explorer_watch`, and `consensus` helpers.
- Markets logic refactored from a single `apps/markets.py` module into an
  `apps/markets/` package (orderbook, matching, oracles, integrity,
  surveillance, reconciliation, market-maker, governance, resolution).
- New release/provenance tooling (`tools/generate_provenance.py`,
  `verify_provenance.py`, `sign_release.py`, `verify_signature.py`,
  `generate_reserve_attestation.py`, `generate_ops_bundle.py`,
  `coverage_gate.py`, `check_openapi_contract.py`, `mutation_consensus_smoke.py`).
- Stricter CI: fast (compile/lint/type/fast-tests), full (coverage gate),
  fuzz+mutation, and browser wallet jobs; Makefile, pre-commit, dependabot,
  and pinned dev/prod requirement locks.

### Fixed
- Wallet SRI/cache trap: `sites/wallet/index.html` pinned the old
  `wallet-app.js` hash after the vault integration changed the file; recomputed
  SRI and bumped the cache-buster (and pinned `wallet-vault.js`) so browsers do
  not serve/block a stale script.
- `netcoin/cli.py` scan path referenced an undefined `List` (would raise
  `NameError`); use built-in `list`.
- Removed a shadowed duplicate `Block.weight` definition in `netcoin/block.py`
  whose inline formula disagreed with the authoritative `serialization.block_weight`
  used across consensus (no behavior change; the class method was already
  overridden by the module-level monkey-patch).

## [0.13.0] - 2026-07-07 — Markets Labs CLOB + professional-upgrade tracking, SBOM, CI gates

### Added
- Polymarket-style central-limit order book on Markets Labs: aggregated price
  levels, per-outcome ticker, marked portfolios, and market/IOC/FOK/post-only
  orders, exposed via `/markets/{id}/orderbook|ticker|trades|positions` and
  rendered in the Labs UI. Engine stays app-layer/play-money.
- Professional-upgrade tracking: a 15-workstream manifest
  (`config/professional_upgrade_manifest.json`), a validator module
  (`netcoin/professional_upgrade.py`), and `tools/professional_upgrade_audit.py`.
  `production_ready` stays false pending external audit.
- Source SBOM/provenance generator (`tools/generate_sbom.py`), wired into
  `tools/make_release.sh` and checksummed alongside the release archive.
- CI now compiles the package and gates on the upgrade-manifest audit, an SBOM
  smoke check, and competitive-registry validation.

### Changed
- Competitive scaffolds converted to richer per-feature configs with code/test/
  doc anchors, owner, and acceptance criteria.

### Added
- Markets Labs is now a real play-money/testnet dashboard instead of a static
  placeholder: create demo markets, place and cancel orders, view order books,
  request/approve resolution, see demo wallets/positions, and load a read-only
  Polymarket discovery feed through the NetCoin backend.

### Changed
- App-layer market logic moved into the `netcoin.apps` package split while
  keeping the public `netcoin.apps` import path compatible.
- Public microsites now use shared `sites/shared/site-shell.*` assets through
  lightweight per-site wrappers, so navigation, mode hints, quickstart text,
  and the Labs link stay consistent across Wallet, Explorer, Pay, Faucet, and
  the other sites.
- Explorer’s page shell was aligned with the rest of the public sites and no
  longer shows the wallet contact manager as the first explorer panel.

## [0.12.0] - 2026-07-05 — large sends fixed: fast verify, O(1) lookups, self-defragmenting wallet

Fixes the "can't send a lot of NET / it lags the explorer" problem. Root causes
were performance, not a hard cap: pure-Python ECDSA froze the single-process
node on many-input transactions, and address lookups scanned the whole UTXO set.

### Performance
- **Per-address UTXO index**: `/balance` and `/utxos` are now
  O(coins-at-address) instead of scanning the entire UTXO set on every call.
  Kills the explorer/wallet lag as the chain grows. Asserted consistent with the
  authoritative set in `verify_integrity()`.
- **Optional libsecp256k1 fast verification** (`coincurve`, enabled with
  `NETCOIN_FAST_CRYPTO=1`): ECDSA verification goes from ~13 ms to ~0.02 ms per
  input, so a 200-input transaction verifies in ~90 ms instead of ~2.7 s and no
  longer stalls other requests. **Safety:** a differential fuzz test
  (`tests/test_fast_crypto_differential.py`) proves the fast path accepts exactly
  the same signatures as the pure-Python verifier — it changes speed, never
  validity, so mixed fast/pure nodes cannot split. Off by default; install with
  `pip install netcoin[fast]`.

### Coin management
- **Consolidating coin selection** (CLI + browser): every send sweeps in extra
  small coins up to the input/weight budget, so normal spending shrinks the UTXO
  set instead of fragmenting it further.
- **Honest large-send guidance**: instead of "too many inputs", the wallet says
  how much you can send right now and points to `netcoin consolidate`.

### Relay/policy caps raised (NOT consensus; env-overridable)
- `MAX_STANDARD_TX_INPUTS` 250 → 1000, `MAX_WALLET_SEND_INPUTS` 120 → 200,
  `MAX_MEMPOOL_ANCESTORS` 25 → 100, standard-tx weight 400k → 1M. Safe now that
  verification is cheap; override via `NETCOIN_MAX_*` for pure-Python operators.

## [0.11.1] - 2026-07-05 — hosted wallet: all four address types

### Added (wallet)
- The hosted browser wallet now derives, displays, **and spends** every
  address era of a key: SegWit (default), Taproot, Legacy, and P2SH-SegWit.
  The Address-type selector shows each type's live balance, so coins on any
  address the wallet has are visible and usable. Sends accept all four
  address formats.
- JS crypto core gained base58check derivation plus p2pkh field-signing and
  nested-P2SH-SegWit redeem+witness signing. Verified: address derivation
  matches Python byte-for-byte (crosscheck) and fully JS-signed legacy and
  P2SH-SegWit spends are accepted by the node's own validation.


## [0.11.0] - 2026-07-04 — SegWit by default, browser Taproot, coin consolidation

### Changed (defaults — no consensus change)
- **SegWit (`net1q…`) is the default address type everywhere**: all CLI
  `--address-type`/`--from-type` defaults moved from `p2pkh` to `p2wpkh`, and
  the local web wallet now defaults to the SegWit view (was legacy). Legacy and
  P2SH-SegWit remain fully spendable for existing coins but are
  compatibility-only, listed last.

### Added
- **`netcoin consolidate`** — sweeps many small coins into one (batches of up
  to 120 inputs, weight-checked, via any node's API) so large sends stop
  failing with "too many inputs". Plus a README section explaining the
  120-input/180k-weight wallet-send policy.
- **Browser-wallet Taproot**: the hosted wallet gains an Address-type selector
  (SegWit default / Taproot). Key-path P2TR receive **and spend** in JS
  (BIP340 schnorr via @noble, bech32m `net1p…`), crosschecked byte-for-byte
  against Python fixtures (address/scriptPubkey/sighash) and proven end-to-end:
  a fully JS-signed taproot spend is accepted by the node's own validation.
  Sends now accept both `net1q…` and `net1p…` recipients.
- `tools/gen_fixtures.py` now emits the taproot and seed-phrase fixtures
  (previously the seed block was hand-maintained in fixtures.json).

## [0.10.1] - 2026-07-04 — spacing v2 activation moved up to height 5,010; README overhaul

### Changed (consensus — activation height only; chain NOT reset)
- **Spacing v2 (5-minute blocks) now activates at height 5,010** instead of
  6,000 (5,010 is the nearest retarget boundary to the requested 5,000; the
  public tip was ~4,745 and every public seed was upgraded in the same
  rollout). **All miners must run ≥0.10.1 before height 5,010 or they fork.**

### Docs
- README rewritten around a 5-minute quickstart (wallet → faucet → mine →
  balance), Docker one-liner, developer quickstart (API keys, OpenAPI, SDKs,
  examples, tokens), and a key-network-facts table.

## [0.10.0] - 2026-07-04 — Phase 0 complete: developer-key auth on app-layer writes; token UI

### Added (security / API — NIP-0004)
- **Self-service developer API keys**: open `POST /api/keys/register` returns a
  free `nck_…` key (SHA-256 hash stored, per-IP daily cap). With
  `NETCOIN_APP_REQUIRE_API_KEY=1` (on for the hosted relay) all app-layer
  writes require the key via `X-Netcoin-Api-Key`; reads, `POST /tx`, and the
  community carve-outs stay open. `docs/nips/NIP-0004.md` specifies the
  standard, including the explicit limitation that keys identify apps, not
  coin owners (signature-bound app writes are the planned follow-up).
- `site-shell.js` now auto-registers and attaches a key per browser, so every
  official site keeps working unchanged with enforcement on.

### Added (token UI)
- Explorer: `#/tokens` list + `#/token/<ref>` detail pages (supply, holders,
  events) and a home-page tokens card.
- Wallet: read-only **Tokens** tab (business/advanced/developer modes) showing
  your balance in every app-layer token, with the security caveat stated.

## [0.9.0] - 2026-07-03 — 5-minute blocks (activation-gated), hourly faucet, NIP process

### Changed (consensus — activation-gated at height 6,000; chain NOT reset)
- **Spacing v2: 5-minute target blocks** from height `6,000` (a retarget
  boundary). Below the activation height the original 2-minute rules apply
  byte-for-byte, so all historical blocks stay valid. The retarget timespan and
  the lone-miner floor gap (now 600s) follow the active spacing
  (`target_spacing_at` / `target_timespan_at` / `min_difficulty_gap_at` in
  `params.py`). Documented as the first formal NIP-0005 activation.
  **Miners must run ≥0.9.0 before height 6,000 or they will fork.**

### Changed (services)
- **Faucet cooldown default is now 1 hour** (was 24h); still overridable with
  `NETCOIN_FAUCET_COOLDOWN_SECONDS`.

### Added
- `docs/nips/NIP-0001.md` (the improvement-proposal process) and
  `docs/nips/NIP-0005.md` (the height-gated upgrade-activation standard with the
  activation history table) — the Phase 0 process items from ROADMAP.md.
- `/info` now reports `target_spacing_seconds` (for the next block) and
  `spacing_v2_activation_height`.
- Browser wallet: **Mining tab** (simple mode) with live chain stats and a
  copyable personal `python -m netcoin miner ...` command; maturity ETA now
  uses the node-reported block spacing instead of assuming 2-minute blocks.

## [0.8.0] - 2026-07-03 — roadmap Phases 1–3: wallet safety, builder platform, app-layer tokens

### Added (app layer — not consensus)
- **NET-20 style token ledger**: create / mint / transfer / burn app-layer tokens
  keyed by NetCoin address or `@username`, with holder lists and an event log.
  Endpoints under `/api/tokens`; covered by `tests/test_app_tokens.py`. The base
  chain never validates tokens (turn-it-off test passes).
- **OpenAPI 3 specification** at `docs/openapi.yaml` (also served from the
  Developers site) covering the node API, app layer, and tokens.
- **Docker dev node**: `Dockerfile` + `docker-compose.yml` run a testnet-joined
  node with one command; volume-persisted chain data and health checks.
- **Starter examples** in `examples/`: store checkout (invoice + polling) and
  loyalty-points token flow, both on the bundled Python SDK.
- Python and JavaScript SDKs gained token methods (`create_token`,
  `mint_token`, `transfer_token`, `burn_token`, `token_balance`, `list_tokens`).

### Added (wallet)
- **Recovery-phrase verification quiz** in the browser-wallet create flow (asks
  for two random words before opening the wallet; skippable but recorded).
- **Address-poisoning warning**: the send review flags recipients that look
  similar to a saved contact, watch-only entry, or your own address.
- **Large-send warning** when a payment spends more than half the spendable balance.
- **Maturity countdown**: `/balance/<address>` now reports
  `immature_next_mature_in_blocks` / `immature_all_mature_in_blocks`, and the
  wallet shows "all spendable in ~N blocks (~ETA)".

## [0.7.4] - 2026-06-30 — reward schedule activation height 4,200

### Changed (consensus — activation-gated; chain NOT reset)
- Replaces the random-emission experiment with a deterministic reward schedule: `50 NET` starting subsidy and a **20% reduction every 210,000 blocks** (`50 -> 40 -> 32 -> 25.6 ...`). The new schedule activates at height `4,200` so already-mined public-testnet blocks stay valid; the first public reduction remains absolute height `210,000`.

### Security
- Encrypted wallet files now use `cryptography`'s ChaCha20-Poly1305 AEAD with
  PBKDF2-HMAC-SHA256-derived keys and fixed associated data. Legacy
  `netcoin-hmac-stream-v1/v2` wallets still open so `wallet-migrate` can
  re-encrypt them into v3 format.

## [0.7.2] - 2026-06-26 — bring emission activation forward

### Changed (consensus — additive, activation-gated; chain NOT reset)
- **`EMISSION_ACTIVATION_HEIGHT` lowered 5_000 → 1_000** so the random-emission
  schedule activates sooner on testnet. Still additive (well above the live tip of
  ~361) and below the first halving. Every node — **including any miner** — must run
  ≥0.7.2 before the chain reaches height 1_000, or old-subsidy blocks past that
  height would be rejected by updated nodes (a fork). The seeds run no miner and the
  chain was idle when this shipped, so there was no active mining to fork.

## [0.7.1] - 2026-06-26 — peer-ban hardening

### Fixed (P2P resilience)
- **Trusted seeds are no longer self-partitioned.** Peers configured via `--peer`
  are now never auto-banned and are auto-unbanned at startup. Previously a run of
  transient sync failures (e.g. a `ConnectionResetError` while a peer restarts for
  a deploy) could drive a configured seed's reputation past `ban_threshold`,
  permanently ban it, and — because `add_peer()` skips banned peers — keep `--peer`
  from ever re-adding it. (Reputation scores still track trusted peers for
  visibility; they're just never banned.)
- **Bans now expire.** Added `ban_ttl_seconds` (default 1h; `0` = permanent) so a
  transient ban on an untrusted peer heals instead of lingering forever. The
  `banned_peers.json` format gains an optional `ban_times` map; old files load fine
  (their bans start the TTL clock at load time).

### Added (consensus — additive, activation-gated; chain NOT reset)
- **Random-emission schedule (NRE).** Replaces Bitcoin-style halvings with a yearly
  random "cut": each emission year may drop the block reward 10%, decided by sampling
  100 blocks of the prior year (via a delayed anti-grinding seed) and counting **even
  hashes** (`>= EMISSION_EVEN_THRESHOLD`, default 40). Safety: a cut is forced after 3
  consecutive no-cut years. New `netcoin/emission.py`; wired into `Blockchain.subsidy`.
  **Additive & activation-gated** at `EMISSION_ACTIVATION_HEIGHT` (5_000 on testnet):
  below it the legacy halving subsidy is unchanged, so the existing chain stays valid
  (per `docs/UPGRADE_POLICY.md`). `EMISSION_YEAR_BLOCKS` is network-aware (720 on
  testnet so cuts are observable, 262_800 on mainnet). Base reward 15 NET at
  activation. Full spec in `docs/ECONOMICS_PLAN.md`.

### Added
- **Balance migration across a relaunch** (`netcoin/migration.py` + `export-allocation`):
  snapshot per-address balances from the old chain and bake them into a new genesis
  via `Blockchain(genesis_allocation=...)`, so a hard fork/relaunch carries everyone's
  coins forward (same keys, same address, same balance). The default genesis is
  unchanged when no allocation is given. Documented in `docs/UPGRADE_POLICY.md`
  (PATCH/MINOR never reset the chain; only a MAJOR/relaunch may, and it ships a
  snapshot allocation).

### Fixed
- **CI test gate.** Declared a `test` extra (pytest) and install `.[test]` in the CI
  and release workflows; the test jobs previously failed with "No module named pytest".
- **`tools/make_release.sh`** no longer aborts with "unbound variable" on bash 3.2
  (macOS) when building an unsigned release (empty-array expansion under `set -u`).

## [0.6.0] - 2026-06-22 — testnet v2 relaunch (real proof-of-work)

### Changed (consensus — resets the chain)
- **Real difficulty.** Blocks now target **2 minutes** (`TARGET_SPACING_SECONDS=120`)
  with a **30-block retarget** (~1h) so difficulty tracks the live miner set. Launch
  is at the PoW floor and the fast retarget ramps difficulty as miners join.
- **Testnet lone-miner rule** (`MIN_DIFFICULTY_GAP_SECONDS`): a block mined more than
  2× the spacing after its parent may use the PoW floor, so the chain can't stall if
  hashpower drops (`chain._bits_acceptable`).
- **New genesis** (`GENESIS_MESSAGE`/`GENESIS_TIMESTAMP`) — testnet v2 is a fresh,
  incompatible chain (height resets to 0; previous coins/faucet balance do not carry
  over). `make_block` takes an explicit timestamp so mining and the lone-miner rule
  agree. `SIGHASH_ALL` and all non-difficulty behavior are unchanged.

## [0.5.0] - 2026-06-22

### Added
- **Binary P2P as a node transport.** Every `node` now serves the binary TCP P2P
  protocol (`--p2p-port`, default 18447) alongside its HTTP API, and gains
  `sync_over_p2p` — peers are synced node-to-node over the binary protocol
  (getheaders → headers → getdata → block), with HTTP kept as the API for
  explorers/faucets/wallets/light clients and as a sync fallback.
- **Lightning-style payment channels** (`netcoin/channel.py`): two parties lock
  funds in a 2-of-2 multisig (on-chain), make unlimited **off-chain** payments by
  re-agreeing the balance split, and settle with a cooperative close that both
  cosign. Only open and close touch the chain. CLI `channel-demo` runs the full
  open → off-chain pays → close lifecycle. (Educational: no revocation/HTLC/routing.)
- **Taproot script-path spends** (BIP341/342-style, `netcoin/taproot.py`): commit a
  tree of alternative tapscripts to a Taproot output by tweaking the internal key
  with the tree's merkle root, then spend by revealing one leaf + a merkle proof
  (control block). The key tweak is validated against the official BIP341 test
  vector. `tx.py` gains a witness-v1 script-path branch (verifies the commitment,
  then runs the leaf via the Script VM); key-path Taproot is unchanged. CLI
  `taproot-tree` builds a script-tree address + control blocks. (Consensus Item 2.)
- **Multiple SIGHASH types** (`SIGHASH_ALL` / `NONE` / `SINGLE` + `ANYONECANPAY`):
  `sign_input`/`verify_input` accept a `sighash_type` so a signature can commit to a
  subset of the transaction — NONE leaves outputs free, SINGLE pins only the
  same-index output, ANYONECANPAY commits to only its own input (others can be
  added). A one-byte flag rides on the signature; `ALL` stays the default and
  byte-identical, so existing signatures and chain data are unaffected.
  (Consensus Item 1 of docs/CONSENSUS_PLAN.md.)
- **Web wallet transaction history**: the Wallet tab now shows a "Recent activity"
  list of the loaded address's transactions (via `/api/history`), each clickable
  to open it in the Explorer.
- **BIP21-style payment URIs** (`netcoin:<address>?amount=&label=&message=`):
  encode a payment request into one shareable string. New `netcoin/paymenturi.py`
  (`build_uri`/`parse_uri`), CLI `payment-uri` (build or `--decode`), and web-wallet
  integration — a "Request payment" link generator plus a "paste a payment link"
  field that pre-fills the Send form.

## [0.4.4] - 2026-06-22

### Added
- **Signed messages** (Bitcoin-style `signmessage` / `verifymessage`): sign a
  message with a wallet key to prove address control. Produces a base64
  recoverable signature that verifies against a legacy or P2WPKH address with no
  public key needed (`crypto.sign_message` / `verify_message`, CLI `signmessage`
  and `verifymessage`).
- **BIP32 HD wallets** (`netcoin/hd.py`), validated against the official BIP32
  test vectors: one mnemonic/seed derives an unlimited tree of keys, with standard
  `xprv`/`xpub` extended keys and hardened + watch-only (xpub→xpub) derivation.
  BIP39-style seed (`mnemonic_to_seed`, PBKDF2-HMAC-SHA512). New CLI: `hd-derive`
  (mnemonic + path → NetCoin addresses, WIF, xprv, xpub) and `hd-address`
  (watch-only receive address from an account xpub, no private key).
- **BIP158-style compact block filters** (`netcoin/blockfilter.py`): each block
  gets a small Golomb-Coded-Set filter summarizing its output scripts. A light
  client downloads filters (bytes, not full blocks), tests its addresses, and only
  fetches blocks that might match. New node endpoint `GET /cfilter/<blockhash>`
  (advertised as the `compact-filters` service), filter-header chaining (BIP157),
  and CLI: `blockfilter` (compute/fetch a filter) and `scan-filters` (light-client
  scan of a wallet/address over a height range). ~1/M false-positive rate, no
  false negatives.
- **Local web wallet / faucet / explorer page** (`python -m netcoin web`): a
  single-page browser UI on `127.0.0.1` that wraps the CLI — create/load a wallet,
  view balance, send (built, signed locally, broadcast to a remote node), open the
  faucet, and browse/search the chain. Keys never leave the machine; only the
  signed transaction is sent to the node. Turns "clone the repo and run the CLI"
  into "open a URL."

### Fixed
- **Node starts serving immediately (listen-first).** `node` previously ran
  bootstrap (announce + peer discovery + initial sync) *before* binding the HTTP
  server, so a slow or unreachable peer could delay or prevent the node from ever
  listening. The server now binds first and bootstrap runs in a background thread.

## [0.4.3] - 2026-06-22

### Added
- **Local multi-node soak/stress harness** (`python -m netcoin soak`) starts
  multiple in-process HTTP nodes, connects them as peers, mines mature funds,
  relays transactions/blocks, syncs tips, and reports convergence for release
  and deployment smoke testing.
- **Deterministic fuzz smoke runner** (`python -m netcoin fuzz`) exercises parser
  and public endpoint surfaces; CI now runs it under Python dev mode.
- **Remote-node compatibility warning.** `balance --node` and `miner --node` now
  check the seed's `/info` first and print a clear warning when it looks like an
  older/mismatched NetCoin (no `version` field, protocol mismatch, or a missing
  service) instead of failing with only a raw `HTTP 400/404`. Also fixed the
  stale `__version__` (`0.2.0`) and `NODE_VERSION` so the client and node report a
  consistent version (now sourced from one constant).
- **Crash-safe chain persistence + reindex.** The JSON backend now writes
  `chain.json`/`mempool.json` via fsync'd temp files, atomic `os.replace`, and a
  `.bak` mirror of the last committed state. On load, a corrupt live file is
  recovered from the backup (or a leftover `.tmp`) without losing the most recent
  block, and a corrupt mempool is dropped rather than blocking startup. New
  `python -m netcoin reindex` rebuilds the indexes and UTXO set from block data
  and reports a chainstate integrity check.
- **Seed log-growth cap** (`tools/harden_logging.sh`): bounds journald to 200M and
  rotates rsyslog logs daily/100M (checked hourly), so a chatty service can no
  longer fill a seed's root disk.

### Fixed
- **`deploy_seed.sh`** now installs `pytest` into the recreated venv before the
  test gate. The venv lives inside the swapped source dir and is wiped on each
  deploy, so the fresh venv lacked test deps and the gate aborted into a rollback.

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
  **maintaining tagged releases** with rollback.
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

[Unreleased]: https://github.com/netcoin-crl/netcoin/compare/v0.7.2...HEAD
[0.7.2]: https://github.com/netcoin-crl/netcoin/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/netcoin-crl/netcoin/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/netcoin-crl/netcoin/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/netcoin-crl/netcoin/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/netcoin-crl/netcoin/compare/v0.4.4...v0.5.0
[0.4.4]: https://github.com/netcoin-crl/netcoin/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/netcoin-crl/netcoin/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/netcoin-crl/netcoin/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/netcoin-crl/netcoin/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/netcoin-crl/netcoin/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/netcoin-crl/netcoin/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/netcoin-crl/netcoin/releases/tag/v0.2.0
