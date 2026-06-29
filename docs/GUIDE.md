# NetCoin Public Guide

This guide is for public-testnet users, developers, miners, and experimenters.

NetCoin is educational software. Public-testnet NET has no real-money value.

## 1. Use the hosted apps

- Wallet: <https://wallet.netcoin.online>
- Explorer: <https://explorer.netcoin.online>
- Faucet: <https://faucet.netcoin.online>
- Pay: <https://pay.netcoin.online>
- Merchant: <https://merchant.netcoin.online>
- Community: <https://community.netcoin.online>
- Markets: <https://markets.netcoin.online>
- API Docs: <https://api.netcoin.online>

## 2. Create or restore a wallet

Open the Wallet site, then create a new wallet or restore from an existing recovery phrase.

Back up your recovery phrase before sending or receiving testnet coins. Anyone with the phrase can control the wallet.

## 3. Request testnet coins

Open the Faucet site and paste a NetCoin testnet address from your wallet.

Faucet limits may apply. Testnet coins are for experiments only.

## 4. Explore blocks and transactions

Open the Explorer site to search for blocks, transactions, addresses, and network health.

Explorer is intentionally focused on chain lookup. Wallet tools stay in Wallet, business tools stay in Merchant, community tools stay in Community, and prediction-market demos stay in Markets.

## 5. Install locally from source

macOS / Linux:

```bash
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m netcoin --help
```

Windows PowerShell:

```powershell
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m netcoin --help
```

## 6. Public node URLs

Use these public seed hostnames when a command asks for a node URL:

```text
http://seed1.netcoin.online:28444
http://seed2.netcoin.online:28444
http://seed3.netcoin.online:28444
```

Health check:

```bash
curl http://seed1.netcoin.online:28444/info
curl http://seed2.netcoin.online:28444/health
curl "http://seed3.netcoin.online:28444/latest?n=5"
```

## 7. Create a local CLI wallet

```bash
python -m netcoin wallet-new --out miner.json --mnemonic --confirm-backup
python -m netcoin wallet-info --wallet miner.json
```

Store the recovery phrase safely. Do not post wallet files or seed phrases publicly.

## 8. Mine on the public testnet

Mine one block:

```bash
python -m netcoin miner --node http://seed1.netcoin.online:28444 --wallet miner.json --blocks 1
```

Mine continuously until stopped:

```bash
while true; do
  python -m netcoin miner --node http://seed2.netcoin.online:28444 --wallet miner.json --blocks 1
done
```

Coinbase rewards become spendable after 100 more blocks.

## 9. Check balance

```bash
python -m netcoin balance --node http://seed1.netcoin.online:28444 --wallet miner.json
python -m netcoin balance --node http://seed1.netcoin.online:28444 --address <NETCOIN_ADDRESS>
```

## 10. Run a local node

Start a local node:

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 --sync-interval 60 --peer http://seed1.netcoin.online:28444 --peer http://seed2.netcoin.online:28444 --peer http://seed3.netcoin.online:28444
```

In another terminal, check it:

```bash
curl http://127.0.0.1:28444/info
```

Mine through your local node:

```bash
python -m netcoin miner --node http://127.0.0.1:28444 --wallet miner.json --blocks 1
```

## 11. Build and test

```bash
python -m pip install -e .[dev]
pytest -q
```

## 12. Safety checklist

- Never share seed phrases, private keys, wallet files, API keys, or tokens.
- Treat public-testnet coins as valueless test coins.
- Use HTTPS hosted apps when using browser wallet features.
- Review code before running experimental tools.
- Do not expose private wallet data through public issue reports, screenshots, logs, or demos.
