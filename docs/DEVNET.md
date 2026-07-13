# NetCoin instant devnet

Spin up a throwaway local network with pre-funded, spendable wallets in seconds —
the hardhat/anvil experience for NetCoin development and CI.

```bash
# Build a devnet with 3 pre-funded wallets (prints addresses + private keys):
python -m netcoin --data .netcoin-devnet devnet --funded 3 --reset

# Build AND serve the node (HTTP API + Esplora layer) on 127.0.0.1:28444:
python -m netcoin --data .netcoin-devnet devnet --funded 3 --reset --serve
# or: make devnet-instant
```

Each wallet starts with mature, spendable coin (round-robin coinbase over
>100 confirmations). Wallet files are saved UNENCRYPTED on purpose — a devnet is
disposable and never mainnet.

Once served, the node exposes the full API including the Esplora-compatible
layer, so tooling (BDK, scripts) can develop against it:

```bash
curl -s http://127.0.0.1:28444/esplora/blocks/tip/height
curl -s http://127.0.0.1:28444/esplora/address/<devnet-address>/utxo | jq .
```

Flags: `--funded N` (wallets), `--blocks N` (override block count),
`--reset` (wipe first), `--serve` (start the node), `--port/--p2p-port/--host`.
