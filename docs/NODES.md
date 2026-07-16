# Running a NetCoin Node

The single starting point for everything node-related: installing, running,
syncing, mining, becoming a public seed, and troubleshooting. Deeper reference
material (DNS seed operations, the mining-pool protocol, node-grant terms, the
30-day soak report) lives in dedicated files linked from each section below —
this page is the map, not a duplicate of them.

> NetCoin is educational testnet software. Testnet NET has no real-money value.

- [Quick facts](#quick-facts)
- [Install](#install)
- [Run a node](#run-a-node)
- [Confirm you're really synced](#confirm-youre-really-synced)
- [Mine blocks](#mine-blocks)
- [Become a public seed](#become-a-public-seed)
- [Run 100% locally (no public sites)](#run-100-locally-no-public-sites)
- [Keep it running (systemd)](#keep-it-running-systemd)
- [Reliability notes for public-facing nodes](#reliability-notes-for-public-facing-nodes)
- [Troubleshooting](#troubleshooting)
- [Deeper reference material](#deeper-reference-material)

## Quick facts

| | |
|---|---|
| Peer/API port | `28444` (HTTP) |
| Binary P2P port | `18447` (optional, TCP) |
| RPC port | `28445` — **never expose this to the internet** |
| Pool port | `28446` — **never expose this to the internet** |
| Public seeds | `seed1.netcoin.online`, `seed2.netcoin.online`, `seed3.netcoin.online` (all `:28444`) |
| Raw-IP fallback | `18.220.89.128`, `18.220.197.20`, `18.226.74.252` (use these if your ISP/router blocks the `netcoin.online` domain) |
| Disk | ~1 GB to start |

## Install

```bash
git clone https://github.com/netcoin-crl/netcoin.git && cd netcoin
python3 -m venv .venv && source .venv/bin/activate   # Windows: py -3 -m venv .venv ; .\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m netcoin --help
```

Full platform-specific beginner steps: [macOS](INSTRUCTIONS_MAC.md) ·
[Windows](INSTRUCTIONS_WINDOWS.md) · [Linux](INSTRUCTIONS_LINUX.md).

## Run a node

Keep node data separate from your wallet:

```bash
python -m netcoin --data ~/.netcoin-testnet init
```

Start it, connected to all three public seeds (list all three so one seed
outage doesn't isolate you):

```bash
python -m netcoin --data ~/.netcoin-testnet node \
  --host 127.0.0.1 --port 28444 \
  --sync-interval 60 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444 \
  --peer http://seed3.netcoin.online:28444
```

`--sync-interval 60` keeps discovering peers and syncing in the background so
you don't have to call `/sync` by hand. `--rate-limit-per-min` sets the
per-IP/per-path public HTTP throttle (default is sane; set `0` only on a
private dev node).

**If your network blocks the `netcoin.online` domain** (some ISPs/router
security products do), the seeds' raw IPs on the node port still work — swap
in the IPs from the [Quick facts](#quick-facts) table above. This only affects
the *domain*; it doesn't get you past a TLS-SNI site block on the HTTPS
websites, which needs a VPN or an allowlist change on the router instead.

## Confirm you're really synced

An isolated node with no reachable peers will silently build its own tiny
private chain instead of erroring. Always check:

```bash
curl -s http://127.0.0.1:28444/info | python3 -c \
  "import sys,json;n=json.load(sys.stdin)['node'];print('height',n['height'],'peers',len(n['peers']),'tip',n['tip_hash'][:12])"
```

`peers` should be **> 0** and `height` should be climbing toward the public
tip (thousands of blocks, not single digits). If `peers` is 0 and height stays
tiny, fix your `--peer` values (try the raw IPs). Compare against a seed
directly if you want to double check:

```bash
curl http://seed1.netcoin.online:28444/info
```

Force a sync any time with `curl -X POST http://127.0.0.1:28444/sync`.

## Mine blocks

You don't need a wallet file to mine — pass any address you already have with
`--address`:

```bash
python -m netcoin miner --node http://127.0.0.1:28444 \
  --address net1youraddresshere --address-type p2wpkh --blocks 1 --sync-after
```

Or against a public seed directly if you don't have a node running yet:

```bash
python -m netcoin miner --node http://seed1.netcoin.online:28444 \
  --wallet my-wallet.json --blocks 1
```

- `--address-type` (`p2wpkh`/`p2pkh`/`p2tr`/`p2sh-segwit`) must match the
  address you're paying — `p2wpkh` (`net1…`) is the modern default.
- Coinbase rewards are **spendable after 100 confirmations** (coinbase
  maturity) — a fresh reward shows as `immature` until then.
- **Etiquette:** don't hammer one seed with a long `--blocks` run; rotate
  seeds or mine to your own synced node instead. It's a shared testnet.

Two-step mining (solve now, submit later/elsewhere):

```bash
python -m netcoin miner --node http://127.0.0.1:28444 --wallet miner.json \
  --blocks 1 --save-blocks ./solved
python -m netcoin submitblock ./solved/<block-file>.json --node http://seed1.netcoin.online:28444
```

Check rewards: `python -m netcoin balance --node <any-seed-or-your-node> --address <ADDRESS>`.

Mining-pool protocol details (Stratum-lite, job templates): [M3_MINING_POOL_REFERENCE.md](M3_MINING_POOL_REFERENCE.md).

## Become a public seed

A seed is just a node that's reachable from the internet and that other
people list as a `--peer`. Simplest path — a small VPS with a real public IP,
no tunnel or port-forward needed (this is how the official `seed1/2/3` run):

```bash
sudo ufw allow 28444/tcp && sudo ufw allow 18447/tcp
python -m netcoin --data ~/.netcoin-testnet node --host 0.0.0.0 --port 28444 \
  --advertise http://YOUR_PUBLIC_IP:28444 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444
```

`--advertise` must be a real, reachable public `host:port` — a private LAN
address (`192.168.x.x`) or a placeholder will get your node banned by peers
that try to dial back and fail (score-based auto-ban, expires after an hour,
but just use your real address). The node also gossips this URL to its peers
on its own so others discover you automatically.

**On your own hardware behind a router/CGNAT** (no VPS): four tunnel options
— Cloudflare Tunnel (free, your own domain), Tailscale Funnel (free,
`*.ts.net`), ngrok (quick tests), or a reverse-SSH tunnel via a cheap VPS
(the only option that also carries the binary P2P port). Full copy/paste
commands for all four, for macOS/Linux/Windows: [PUBLIC_SEED_HOSTING.md](PUBLIC_SEED_HOSTING.md).

Confirm you're actually reachable from the outside:

```bash
curl -s http://YOUR_PUBLIC_ADDRESS:28444/info   # or your tunnel URL
```

## Run 100% locally (no public sites)

The public sites are a convenience, not a requirement — you can run the whole
stack (node, wallet, explorer) trusting only your own machine:

```bash
# 1. your node (above) — the source of truth for balances and broadcast
# 2. the local wallet, talking to your own node
python -m netcoin web --node http://127.0.0.1:28444 --port 8090
# open http://127.0.0.1:8090
# 3. the local explorer, browsing your own node's chain
cd webexplorer && NETCOIN_NODE=http://127.0.0.1:28444 python3 tools/devserver.py
# open http://127.0.0.1:8077
```

Why bother: your own node means no third party can lie to you about your
balance or the chain tip ("don't trust, verify"), nothing logs which
addresses you look up, you keep working if a public seed is down or
filtered, and every independent node/seed makes the network more
decentralized and more honestly testable.

## Keep it running (systemd)

```ini
[Unit]
Description=NetCoin testnet node
After=network-online.target

[Service]
ExecStart=/path/to/python -m netcoin --data /home/youruser/.netcoin-testnet node \
  --host 0.0.0.0 --port 28444 --sync-interval 60 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444 \
  --peer http://seed3.netcoin.online:28444
Restart=on-failure
User=youruser

[Install]
WantedBy=multi-user.target
```

Add `Environment=NETCOIN_FAST_CRYPTO=1` (with `pip install "netcoin[fast]"`
first) on any node handling real traffic — it makes large-transaction
verification instant without changing which signatures are valid.

## Reliability notes for public-facing nodes

A public node juggles seed discovery, wallet API, explorer API, mining
templates, and relay all at once — one oversized transaction or heavy
explorer page shouldn't make it feel frozen. Built-in protections: wallet
send pre-checks (balance/input-count/weight), mempool expiry for stale
unconfirmed transactions, fast `/health`/`/status-lite` endpoints, short
response caching on `/info`/`/health`/`/latest`, and address-history
pagination.

Operator commands:

```bash
curl -s http://127.0.0.1:28444/health                                    # fast health check
python -m netcoin mempool-info --node http://127.0.0.1:28444 --summary   # mempool policy/usage
python -m netcoin --data ~/.netcoin-testnet mempool-clear                 # clear unconfirmed txs (confirmed blocks/UTXOs untouched)
```

If a wallet send times out on a large amount, check health/mempool first
before retrying, and mine one block at a time (skip `--sync-after` unless you
need it — the extra peer-sync work can make the command look stuck even
after the block was accepted):

```bash
curl -s http://18.220.89.128/api/health
python -m netcoin mempool-info --node http://18.220.89.128/api --summary
python -m netcoin miner --node http://18.220.89.128/api --wallet my-wallet.json --blocks 1 --timeout 60
```

Role split for anyone running more than one box: keep `seed*` boxes boring
(sync/peer discovery only), put wallet/API traffic on a separate `api.*` box,
and serve the explorer/status pages from cached reads.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/info` times out | ISP/router filtering the domain | use the raw seed IPs |
| Height stuck at 0, `peers: 0` | no peers reachable | check `--peer` URLs and outbound firewall; try the raw IPs |
| Tip hash differs from seeds | mid-sync, or you mined a private block | `POST /sync`; the longer valid chain wins on cumulative work |
| Port already in use | another node running | pick a different `--port` |
| Your seed keeps getting banned by other nodes | `--advertise` points at an unreachable address (private LAN IP, or a placeholder) | use your real public IP/hostname, or don't advertise at all if you don't need inbound peers |
| `block does not connect to current tip` (mining) | someone else mined first | the miner automatically re-fetches a template and retries |
| Reward stays `immature` | coinbase maturity | wait 100 confirmations |

## Deeper reference material

- [PUBLIC_SEED_HOSTING.md](PUBLIC_SEED_HOSTING.md) — all four tunnel options in full, dynamic-IP notes
- [M3_NODE_OPERATOR_GUIDE.md](M3_NODE_OPERATOR_GUIDE.md) — decentralization targets, Docker Compose path
- [M3_DNS_SEEDS.md](M3_DNS_SEEDS.md) — independent DNS seed operation
- [M3_HOME_NODE_BANDWIDTH.md](M3_HOME_NODE_BANDWIDTH.md) — bandwidth modes for home connections
- [M3_MINING_POOL_REFERENCE.md](M3_MINING_POOL_REFERENCE.md) — Stratum-lite pool protocol
- [M3_NODE_GRANTS_PROGRAM.md](M3_NODE_GRANTS_PROGRAM.md) — funding terms for new independent operators
- [NODE_RUNNER.md](NODE_RUNNER.md) / [RUN_YOUR_OWN.md](RUN_YOUR_OWN.md) — the original standalone guides this page consolidates (kept in place; nothing here is a redirect, just a shorter front door)
