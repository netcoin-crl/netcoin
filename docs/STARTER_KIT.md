# NetCoin Testnet Starter Kit

A 10-minute, copy-paste walkthrough for new testers: install, make a wallet, get
test coins from the faucet, send a transaction, optionally mine, and report bugs.

> **Safety first.** NetCoin is educational testnet software. Testnet NET has no
> real-money value. Never reuse a real-money seed phrase here, and never share or
> commit your wallet file.

---

## 0. Requirements

- Python 3.10+
- macOS, Linux, or WSL on Windows
- Internet access to the public seeds (port **28444**)

## 1. Install

```bash
cd netcoin
python -m pip install -e .
python -m netcoin --help
```

## 2. Make a wallet (and back it up)

```bash
python -m netcoin wallet-new --out my-wallet.json --mnemonic
chmod 600 my-wallet.json
python -m netcoin wallet-info --wallet my-wallet.json
```

- Write the seed phrase on paper. It is the only way to recover the wallet.
- `chmod 600` keeps other users on your machine from reading the file.
- Copy your **address** — you'll use it for the faucet and to receive coins.

## 3. Get test coins from the faucet

Open the faucet and paste your address:

- https://18.220.89.128/faucet

The faucet sends **5 test NET** (one request per IP per 24 hours). Watch it arrive:

```bash
python -m netcoin balance \
  --node http://18.220.89.128:28444 \
  --address <YOUR_ADDRESS>
```

This asks a public seed for the address balance. You can also use your own synced
local data directory:

```bash
python -m netcoin --data ~/.netcoin-testnet balance --address <YOUR_ADDRESS>
```

The transaction must be mined before the balance changes. See the
[explorer](http://18.220.89.128/).

## 4. Point a local data dir at the network

```bash
python -m netcoin --data ~/.netcoin-testnet init
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444 \
  --peer http://seed3.netcoin.online:28444
```

Leave that running in one terminal. Confirm sync in another:

```bash
curl http://127.0.0.1:28444/info
```

## 5. Send a transaction

```bash
python -m netcoin --data ~/.netcoin-testnet send \
  --wallet my-wallet.json \
  --to <RECIPIENT_ADDRESS> \
  --amount 1 \
  --fee 0.01 \
  --broadcast-to http://seed1.netcoin.online:28444
```

Check the mempool/explorer to see it relay, then a miner will include it in a block.

## 6. (Optional) Mine a block

See [MINING.md](MINING.md). Quick version:

```bash
python -m netcoin miner --node http://127.0.0.1:28444 --wallet my-wallet.json --blocks 1
```

## 7. (Optional) Run a full node for others

See [NODE_RUNNER.md](NODE_RUNNER.md) to accept inbound peers and help the network.

---

## Reporting bugs

When something breaks, please include:

- What you ran (the exact command)
- What you expected vs. what happened
- Your NetCoin version (`python -m netcoin --help` header / `pyproject.toml`)
- Relevant node logs

**Never include** your wallet file, seed phrase, or private keys in a bug report.
See [SECURITY.md](../SECURITY.md) for how to report security-sensitive issues
privately.

## Quick reference

| Task | Command |
|---|---|
| New wallet | `wallet-new --out my-wallet.json --mnemonic` |
| Wallet info | `wallet-info --wallet my-wallet.json` |
| Balance from public seed | `balance --node http://18.220.89.128:28444 --address <ADDR>` |
| Balance from local chain | `--data ~/.netcoin-testnet balance --address <ADDR>` |
| Run node | `--data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 --peer ...` |
| Send | `send --wallet my-wallet.json --to <ADDR> --amount 1 --fee 0.01 --broadcast-to <node>` |
| Mine | `miner --node <node> --wallet my-wallet.json --blocks 1` |
| Sync now | `curl -X POST http://127.0.0.1:28444/sync` |

Public seeds: `seed1.netcoin.online`, `seed2.netcoin.online`, `seed3.netcoin.online`
(port 28444). Raw IPs: `18.220.89.128`, `18.220.197.20`, `18.226.74.252`.
