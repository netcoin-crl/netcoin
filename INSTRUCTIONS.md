# NetCoin instructions — pick your system

New to NetCoin? Follow the guide for **your** computer. Each one is complete and
beginner-friendly — install, make a wallet, mine test coins, check your balance,
and open a wallet in your browser, with nothing to skip between systems.

| Your computer | Guide |
| --- | --- |
| 🍎 **Mac** | **[macOS guide →](docs/INSTRUCTIONS_MAC.md)** |
| 🪟 **Windows** | **[Windows guide →](docs/INSTRUCTIONS_WINDOWS.md)** |
| 🐧 **Linux** | **[Linux guide →](docs/INSTRUCTIONS_LINUX.md)** |

> NetCoin is a **learning project on a test network**. It is not Bitcoin, does not
> connect to the Bitcoin network, and test NET has **no real-money value**.

## Prefer the hosted apps?

You don't have to install anything to try it — use the public sites:

- Wallet: <https://wallet.netcoin.online>
- Explorer: <https://explorer.netcoin.online>
- Faucet: <https://faucet.netcoin.online>

## Going further

- **Run a node**: install, sync, mine, and troubleshoot in one place —
  **[docs/NODES.md](docs/NODES.md)**
- **Run everything yourself** (your own node, become a public seed, use NetCoin
  fully offline with no reliance on the public sites): [docs/RUN_YOUR_OWN.md](docs/RUN_YOUR_OWN.md)
- **Public-seed hosting options** (tunnels, VPS, dynamic IPs): [docs/PUBLIC_SEED_HOSTING.md](docs/PUBLIC_SEED_HOSTING.md)

## Become a public seed

A public seed is a NetCoin node reachable from the internet that other people
list as a `--peer`. Quick path (simplest on a small VPS with a real public IP;
tunnel options for home hardware behind a router are in
[docs/PUBLIC_SEED_HOSTING.md](docs/PUBLIC_SEED_HOSTING.md)):

```bash
sudo ufw allow 28444/tcp && sudo ufw allow 18447/tcp
python -m netcoin --data ~/.netcoin-testnet node --host 0.0.0.0 --port 28444 \
  --advertise http://YOUR_PUBLIC_IP:28444 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444
```

`--advertise` must be a real, reachable public address — a private LAN IP or
a placeholder gets your node banned by peers that try to dial back and fail.
Full walkthrough: [docs/NODES.md#become-a-public-seed](docs/NODES.md#become-a-public-seed).

## Safety reminders

- Never share your recovery phrase, private key, or wallet file.
- Public-testnet NET has no real-money value.
- Keep local browser tools bound to `127.0.0.1` unless you understand the risks.
