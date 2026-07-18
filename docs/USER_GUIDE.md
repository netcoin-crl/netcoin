# NetCoin User Guide

The complete guide to using NetCoin — hosted apps, local install, wallet
(browser and CLI), faucet, explorer, mining, running a local node, and the
app-layer features.

NetCoin is educational public-testnet software. Testnet NET has **no real-money
value**. Never reuse a real-money seed phrase here, and never share or commit
your wallet file.

> **New here?** For a fast 10-minute copy-paste path, use the
> [Starter Kit](STARTER_KIT.md). For a per-operating-system walkthrough, use the
> [macOS](INSTRUCTIONS_MAC.md) / [Windows](INSTRUCTIONS_WINDOWS.md) /
> [Linux](INSTRUCTIONS_LINUX.md) guides. This page is the full reference.

---

## 1. Use the hosted apps (no install)

| App | Link |
| --- | --- |
| Wallet | <https://wallet.netcoin.online> |
| Explorer | <https://explorer.netcoin.online> |
| Faucet | <https://faucet.netcoin.online> |
| Pay | <https://pay.netcoin.online> |
| Merchant | <https://merchant.netcoin.online> |
| Community | <https://community.netcoin.online> |
| Markets | <https://markets.netcoin.online> |
| API Docs | <https://api.netcoin.online> |

Each site does one job: chain lookup stays in Explorer, business tools in
Merchant, community tools in Community, and prediction-market demos in Markets.

## 2. Wallet basics (browser)

Open the Wallet site to:

- create a new wallet or restore from a recovery phrase
- copy your receive address and show a QR / payment link
- save contacts, send NetCoin, and review transaction labels/notes
- export contacts and backups

**Always back up your recovery phrase before sending or receiving.** Anyone with
the phrase can control the wallet. Write it on paper; never post wallet files or
seed phrases publicly.

## 3. Install locally from source

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

Every new terminal needs the venv activated again (`source .venv/bin/activate`
on macOS/Linux, `.\.venv\Scripts\Activate.ps1` on Windows) before
`python -m netcoin ...`.

## 4. Public node URLs

Use these when a command asks for a node URL. Start with the API proxy; fall
back to the raw IP if your network blocks the domain or custom ports.

```text
https://api.netcoin.online/api          # preferred
http://18.220.89.128/api                # raw-IP fallback
http://seed1.netcoin.online:28444
http://seed2.netcoin.online:28444
http://seed3.netcoin.online:28444
```

Health check:

```bash
curl https://api.netcoin.online/api/info
curl http://seed1.netcoin.online:28444/health
```

## 5. Create a CLI wallet (and back it up)

```bash
python -m netcoin wallet-new --out my-wallet.json --mnemonic --confirm-backup
chmod 600 my-wallet.json
python -m netcoin wallet-info --wallet my-wallet.json
```

Store the recovery phrase safely — it is the only way to recover the wallet.
`chmod 600` keeps other users on your machine from reading the file. Copy your
**address**; you'll use it for the faucet and to receive coins.

## 6. Get test coins from the faucet

Open <https://faucet.netcoin.online> and paste your NetCoin testnet address.
Faucet limits apply (typically one claim per hour). Test coins are for
experiments only.

## 7. Explore blocks and transactions

Open <https://explorer.netcoin.online> to search blocks, transactions,
addresses, and network health.

## 8. Mine on the public testnet

Mine one block:

```bash
python -m netcoin miner --node https://api.netcoin.online/api --wallet my-wallet.json --blocks 1 --sync-after
```

Mine continuously until stopped:

```bash
while true; do
  python -m netcoin miner --node http://seed2.netcoin.online:28444 --wallet my-wallet.json --blocks 1
done
```

Coinbase rewards become spendable after **100** more blocks. See
[MINING.md](MINING.md) for depth.

## 9. Check balance

```bash
python -m netcoin balance --node https://api.netcoin.online/api --wallet my-wallet.json
python -m netcoin balance --node https://api.netcoin.online/api --address <NETCOIN_ADDRESS>
```

## 10. Run a local node

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 \
  --sync-interval 60 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444 \
  --peer http://seed3.netcoin.online:28444
```

Check it, and mine through it:

```bash
curl http://127.0.0.1:28444/info
python -m netcoin miner --node http://127.0.0.1:28444 --wallet my-wallet.json --blocks 1
```

To make a node reachable from the internet as a public seed, see
[NODES.md](NODES.md#become-a-public-seed).

## 11. Payments, invoices, and public pages

NetCoin's app layer supports invoices and checkout pages. An invoice carries a
recipient address, amount, memo, expiration, and confirmation requirement; the
checkout page shows a payment URI and a status (unpaid, pending, confirmed,
underpaid, overpaid, expired).

Public app-layer pages:

```text
/pay/<invoice_id>       checkout page
/receipt/<txid>         receipt page
/receipt/<txid>.pdf     receipt PDF
/u/<username>           public profile
/tip/<username>         tip page
/donate/<username>      donation page
/gift/<claim_code>      gift claim page
```

## 12. Community and app-layer tools

Testnet/demo tools include gifts, airdrop payout plans, bounties, community
rewards, tip buttons, and leaderboards. Payouts are **planned first, then
reviewed and manually signed by an operator**.

Further app-layer tools: recurring payment agreements, 2-of-3 escrow records,
signed-message polls, testnet/play-money prediction markets, and simple contract
templates. These are app-layer/demo features, **not** Ethereum-style consensus
contracts.

## 13. Build and test (contributors)

```bash
python -m pip install -e ".[dev]"
pytest -q
```

## Safety checklist

- Never share seed phrases, private keys, wallet files, API keys, or tokens.
- Treat public-testnet coins as valueless test coins.
- Use the HTTPS hosted apps for browser wallet features.
- Review code before running experimental tools.
- Don't expose private wallet data through issue reports, screenshots, or logs.
- Unless an operator explicitly announces otherwise, treat this as testnet/demo
  software — not for real-value payments or regulated markets.
