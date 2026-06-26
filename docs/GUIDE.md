# NetCoin — Complete Step-by-Step Guide (macOS / Linux / Windows)

Everything you can do with NetCoin, in order: install → wallet → coins → send →
mine → browser wallet → run a node → run a public seed → light-client → and how
the project itself is built and deployed (GitHub + AWS).

> NetCoin is **testnet-only educational software**. Test NET has **no real-money
> value**. Never reuse a real seed phrase. The CLI is identical on every OS — only
> the install step and a couple of commands (`open` / file paths) differ.
>
> **Network endpoints** used below:
> `http://seed1.netcoin.online:28444` (also seed2/seed3). If your network blocks
> the hostnames (some ISP/content filters), use the **IPs** instead:
> `18.220.89.128`, `18.220.197.20`, `18.226.74.252` (all on port `28444`).

---

## 1. Install (Python 3.10+; `pip` installs the project dependencies)

### macOS
```bash
# Python 3 ships with macOS, or: brew install python
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e .
python -m netcoin --help
```

### Linux (Debian/Ubuntu)
```bash
sudo apt update && sudo apt install -y python3 python3-venv git
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e .
python -m netcoin --help
```

### Windows (PowerShell)
```powershell
# Install Python 3.10+ from python.org (check "Add python.exe to PATH") and Git from git-scm.com
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
python -m netcoin --help
```

Run every command below **from the project root** (the folder with `pyproject.toml`).

---

## 2. Make a wallet

```bash
python -m netcoin wallet-new --out miner.json --mnemonic --confirm-backup
python -m netcoin wallet-info --wallet miner.json     # shows your addresses
```
Write the recovery phrase on paper. On macOS/Linux protect the file: `chmod 600 miner.json`.

**HD wallet (one seed → many addresses, standard BIP32):**
```bash
python -m netcoin hd-derive --mnemonic "your words here" --path "m/44'/0'/0'/0/0"
```

---

## 3. Get coins from the faucet (instant, spendable)

Open the faucet and paste your address (gives test NET, once per IP per day):
- <http://18.220.89.128/faucet>

Faucet coins are normal payments, so they're **spendable immediately** (unlike
mined coins, which mature after 100 blocks — see step 5).

---

## 4. Check your balance

```bash
python -m netcoin balance --node http://seed1.netcoin.online:28444 --wallet miner.json
```
`spendable` is what you can send now; `immature` is mined rewards still maturing.

---

## 5. Mine

```bash
python -m netcoin miner --node http://seed1.netcoin.online:28444 --wallet miner.json --blocks 10
```
Each block you mine rewards your wallet, but **mining rewards (coinbase) are locked
for 100 blocks** ("immature") before you can spend them — standard Bitcoin
behaviour. Mine more (or use the faucet) to get spendable coins sooner.

---

## 6. Use the browser wallet (easiest send + explorer)

```bash
python -m netcoin web --node http://seed1.netcoin.online:28444
# then open http://127.0.0.1:8088/   (macOS: open … / Linux: xdg-open … / Windows: start …)
```
In the page: **Wallet** (create/load, balance, **send**, request-payment links,
history), **Faucet**, **Explorer** (search blocks/txs/addresses). Keys stay on your
machine — it is a local tool, not a hosted wallet.

To **send** from the CLI you need a local synced chain; the browser wallet is the
simple path (it builds + signs locally and broadcasts to the node).

---

## 7. Run a full node (validate the whole chain yourself)

A node syncs the entire chain and serves the HTTP API + the binary P2P transport.
Peer by **IP** to avoid hostname filters:

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 \
  --peer http://18.220.89.128:28444 \
  --peer http://18.220.197.20:28444 \
  --peer http://18.226.74.252:28444
```
(Windows: use `$env:USERPROFILE\.netcoin-testnet` for `--data`.) Check it synced:
open `http://127.0.0.1:28444/info` — your `height` should climb to match the seeds.

---

## 8. Run a public seed (others connect to you) — no port forwarding

To let other nodes bootstrap from you, you must be publicly reachable. You can do
that **without router port forwarding** (works behind CGNAT) with a tunnel, then
`--advertise` the public URL. Full per-OS steps for Cloudflare Tunnel / Tailscale /
ngrok / VPS are in **[PUBLIC_SEED_HOSTING.md](PUBLIC_SEED_HOSTING.md)**. Fastest test:

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 &
cloudflared tunnel --url http://localhost:28444     # prints a public https URL (no account)
# restart the node with: --advertise <that-url>
```

---

## 9. Light-client scan (sync receives without full blocks)

```bash
python -m netcoin scan-filters --node http://seed1.netcoin.online:28444 --wallet miner.json
```
Downloads tiny BIP158 compact filters and flags only the blocks that might pay you.

---

## 10. Other handy commands

```bash
python -m netcoin signmessage   --wallet miner.json --message "I own this address"
python -m netcoin verifymessage --address <ADDR> --message "I own this address" --signature <SIG>
python -m netcoin payment-uri   --address <ADDR> --amount 2.5 --label Coffee
python -m netcoin taproot-tree  --wallet miner.json --script "OP_SHA256 <hash> OP_EQUAL"
python -m netcoin channel-demo  --capacity 10 --pay a:3 --pay b:1     # payment-channel demo
python -m netcoin reindex       --data ~/.netcoin-testnet            # rebuild from block data
python -m pytest -q             # run the full test suite (~280+ tests)
```

---

## 11. The project: GitHub + AWS (for operators)

**GitHub** — source, releases, and signed artifacts live at
<https://github.com/netcoin-crl/netcoin>.
```bash
git clone https://github.com/netcoin-crl/netcoin.git      # anyone
# maintainers push over SSH; releases are GPG-signed (see docs/RELEASING.md):
NETCOIN_SIGNING_KEY=55463C98D4399B90 tools/make_release.sh vX.Y.Z
```

**AWS seeds** — the public `seed1/2/3.netcoin.online` are Ubuntu VMs on AWS. They
need **no port forwarding** (a VM has a public IP); you just open the port in the
**EC2 security group** (TCP `28444` for the API, `18447` for binary P2P). The node
runs under systemd (`netcoin-node.service`), data in `/opt/netcoin/.netcoin-testnet`.

Deploy/upgrade a seed safely (backs up, runs tests, restarts, auto-rolls-back):
```bash
# build the signed artifact locally
NETCOIN_SIGNING_KEY=55463C98D4399B90 tools/make_release.sh vX.Y.Z
# copy up and deploy (per seed)
scp -i <key>.pem dist/netcoin-X.Y.Z.zip ubuntu@<seed-ip>:/tmp/
ssh  -i <key>.pem ubuntu@<seed-ip> 'sudo /opt/netcoin/netcoin-v2/tools/deploy_seed.sh --zip /tmp/netcoin-X.Y.Z.zip'
```
Operational details (logging, backups, monitoring, log caps) are in
[OPERATIONS.md](OPERATIONS.md); the testnet layout/DNS is in [TESTNET.md](TESTNET.md).

---

## Where to go next
- [STARTER_KIT.md](STARTER_KIT.md) — the 10-minute quickstart
- [NODE_RUNNER.md](NODE_RUNNER.md) · [MINING.md](MINING.md) — deeper node/mining docs
- [PUBLIC_SEED_HOSTING.md](PUBLIC_SEED_HOSTING.md) — no-port-forward seed hosting
- [ARCHITECTURE.md](ARCHITECTURE.md) · [LIMITATIONS.md](LIMITATIONS.md) — how it works, and what it isn't
