# NetCoin

**NetCoin** is an educational, from-scratch, Bitcoin-like cryptocurrency written in
Python (runs on macOS / Linux / Windows). Wallet-file encryption uses the vetted
`cryptography` package for AEAD. It is **not Bitcoin**, does not connect to the
Bitcoin network, and has **no real-money value**.

> ⚠️ **Testnet only.** This is learning software. Never use a real wallet seed here,
> and never treat test NET as money.

- **Source code:** <https://github.com/netcoin-crl/netcoin>
- **Current release:** v0.7.2 — [changelog](https://github.com/netcoin-crl/netcoin/blob/main/CHANGELOG.md)
- **Releases & downloads:** <https://github.com/netcoin-crl/netcoin/releases>

## Get started

```bash
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python3 -m pip install -e .
python3 -m netcoin --help
```

Prefer a browser to the command line? Launch the local web wallet (wallet,
faucet, and explorer in one page — keys stay on your machine):

```bash
python3 -m netcoin web --node http://seed1.netcoin.online:28444
# then open http://127.0.0.1:8088/
```

## Verify a download

Releases are signed with the NetCoin signing key
(`84F7 F2B9 50C9 D16F A628  AC67 5546 3C98 D439 9B90`):

```bash
gpg --import netcoin-signing-key.asc
gpg --verify SHA256SUMS.asc SHA256SUMS   # "Good signature from NetCoin"
shasum -a 256 -c SHA256SUMS              # checksum OK
```

## Guides

### Start here
- **[Complete Guide](GUIDE.md) — step-by-step for macOS/Linux/Windows: install → wallet → mine → node → public seed → GitHub/AWS**
- [Starter Kit](STARTER_KIT.md) — 10-minute walkthrough: install, wallet, faucet, send, mine
- [Tester Invite](BETA_INVITE.md) — copy-paste beta-tester flow

### Run the network
- [Run a Node](NODE_RUNNER.md) — your own full node, peered with the public seeds
- [Host a Public Seed](PUBLIC_SEED_HOSTING.md) — make a node publicly reachable with **no port forwarding** (Cloudflare Tunnel / Tailscale / ngrok / VPS), macOS/Linux/Windows
- [Mining](MINING.md) — mine testnet blocks from your machine
- [Testnet Layout](TESTNET.md) — seed nodes, ports, DNS, launch order
- [Operations](OPERATIONS.md) — backups, deploy/upgrade, monitoring, SQLite backend

### Understand it
- [Architecture](ARCHITECTURE.md) — components, data flows, trust boundaries
- [Limitations](LIMITATIONS.md) — what this is and isn't
- [Roadmap](ROADMAP.md)

### Maintain & secure
- [Upgrading](UPGRADING.md) — update between releases without wiping data
- [Releasing](RELEASING.md) — versioning, signed artifacts, verification
- [Security Testing](SECURITY_TESTING.md)
- [Security Review Plan](SECURITY_REVIEW_PLAN.md) — gates any mainnet discussion

## Public testnet

| Service | Endpoint |
| --- | --- |
| Seed 1 | `seed1.netcoin.online:28444` |
| Seed 2 | `seed2.netcoin.online:28444` |
| Seed 3 | `seed3.netcoin.online:28444` |
| Explorer | <http://18.220.89.128/> |
| Faucet | <https://18.220.89.128/faucet> |
| Status | <http://18.220.89.128/status.json> |

```bash
curl http://seed1.netcoin.online:28444/info
```
