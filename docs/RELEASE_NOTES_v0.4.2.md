# NetCoin v0.4.2

Educational, Bitcoin-like cryptocurrency and public testnet software.
**Testnet only — NET has no real-money value.** Not Bitcoin; not production-hardened.

This release fixes the remaining wrapped-SegWit spend gap and carries forward the
v0.4.x networking, explorer, faucet, storage, wallet, and release-verification work.
**233 automated tests pass.**

## Highlights

- **P2SH-SegWit spending fixed:** `from_type="p2sh-segwit"` now creates a proper
  P2SH-P2WPKH spend with the nested P2WPKH redeem script in `scriptSig` and
  signature + pubkey in witness.
- **Release verification:** `dist/netcoin-0.4.2.zip`, `dist/SHA256SUMS`, and
  `dist/SHA256SUMS.asc` are produced locally; checksum and GPG signature verify.
- **Public repo links updated:** stale `old personal repo location` references were replaced
  with `netcoin-crl/netcoin`.
- **Inherited from v0.4.x:** headers-first sync, experimental TCP P2P, relay queues,
  API-backed explorer, faucet queue/CAPTCHA hooks, SQLite/pruning support, fuller
  Script VM, descriptors, PSBT flow, wallet migration, and public endpoint limits.

See the full [CHANGELOG](../CHANGELOG.md) for details.

## Install

```bash
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
git checkout v0.4.2
python -m pip install -e .
python -m pytest -q          # expect: 233 passed
python -m netcoin --help
```

## Verify The Release Artifact

```bash
shasum -a 256 -c SHA256SUMS
gpg --verify SHA256SUMS.asc SHA256SUMS
```

Artifact SHA256 (`netcoin-0.4.2.zip`):

```text
1c56cd3985492d1aef717076ed832df3ec08bead26b15bf847291a7037b84323
```

Signing key:

```text
NetCoin <netcoin2026@gmail.com>
84F7F2B950C9D16FA628AC6755463C98D4399B90
```

## Run / Join The Testnet

```bash
python -m netcoin --data ~/.netcoin-testnet node --seeds
```

See `docs/STARTER_KIT.md`, `docs/NODE_RUNNER.md`, and `docs/MINING.md`.

## Safety

NetCoin is educational software for learning how a UTXO chain, mempool, mining,
reorgs, wallets, and P2P work. Do not use it for real value. See
`docs/LIMITATIONS.md` and `SECURITY.md`.
