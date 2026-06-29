# NetCoin v0.4.0

Educational, Bitcoin-like cryptocurrency and public 3-seed testnet.
**Testnet only — NET has no real-money value.** Not Bitcoin; not production-hardened.

This release adds a real networking stack, durable storage, and deeper protocol
fidelity on top of v0.3.0. **192 automated tests pass.**

## Highlights
- **Networking:** experimental TCP P2P transport (`p2p-server`/`p2p-call`) over the
  Bitcoin-style message layer (version/verack/ping/pong/inv/getdata/getheaders/
  headers/block/tx); relay queue + tx/block inventory cache with retry/backoff;
  background sync loop; peer scoring + banning; protocol/genesis compatibility checks.
- **Storage:** optional SQLite backend (`NETCOIN_BACKEND=sqlite`, `migrate-sqlite`);
  persistent/incremental UTXO set; **pruned mode** (drop old block bodies, keep
  headers + UTXO snapshot, keep mining); block/tx/address indexes.
- **Protocol:** lossless binary tx/block codec (round-trips preserving txid/hash);
  reorg with rollback + mempool revalidation; mempool eviction + ancestor limits.
- **Wallet:** coin control, coin-selection strategies, gap-limit scan, multisig
  address, labels/address book, backup/recover-test/unlock/watch-only export,
  KDF upgrade (600k PBKDF2, backward compatible), seed-backup confirmation.
- **Services/ops:** API-backed explorer (`explorer-server` + `/api/*`); faucet
  hardening (queue, hot-wallet isolation/refill, throttle, abuse log, balance gate);
  `/health`, `/metrics` (Prometheus), `/events`, `/relay`; GET+POST rate limiting;
  monitoring webhook alerts; backup + safe update/maintenance scripts; structured logs.

See the full [CHANGELOG](../CHANGELOG.md) for the complete list.

## Install
```bash
# from the release zip
unzip netcoin-0.4.0.zip && cd netcoin-0.4.0
python -m pip install -e .
python -m pytest -q          # expect: 192 passed
python -m netcoin --help
```

## Verify your download
```bash
sha256sum -c SHA256SUMS      # Linux
shasum -a 256 -c SHA256SUMS  # macOS
# gpg --verify SHA256SUMS.asc SHA256SUMS   # once releases are GPG-signed
```

Artifact SHA256 (`netcoin-0.4.0.zip`):
`358742fca42d3e6e76b6e5f6089552435f10c432d51e8b9bdc5df56f554c5704`

## Run / join the testnet
```bash
python -m netcoin --data ~/.netcoin-testnet node --seeds
```
See `docs/STARTER_KIT.md`, `docs/NODE_RUNNER.md`, and `docs/MINING.md`.

## Safety
NetCoin is educational software for learning how a UTXO chain, mempool, mining,
reorgs, and P2P work. Do not use it for real value. See `docs/LIMITATIONS.md` and
`SECURITY.md`.
