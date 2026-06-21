# Running an Independent NetCoin Node

This guide is for friends and testers who want to run their own NetCoin full node
outside the project's AWS seed servers. Running more independent nodes makes the
testnet healthier and more decentralized.

> NetCoin is educational testnet software. Testnet NET has no real-money value.

## What you need

- Python 3.10 or newer
- An open outbound internet connection (to reach the public seeds)
- About 1 GB free disk to start (the testnet chain is small today but grows)

## 1. Install

```bash
# Get the source (release zip or git clone), then:
cd netcoin
python -m pip install -e .
# or run without installing using: python -m netcoin ...
```

Verify:

```bash
python -m netcoin --help
```

## 2. Initialize a data directory

Keep node data separate from your wallet.

```bash
python -m netcoin --data ~/.netcoin-testnet init
```

## 3. Start the node and connect to the public seeds

The public seeds listen on port **28444**. Use the hostnames; fall back to raw IPs
if your local network blocks the fresh `netcoin.online` domain.

```bash
python -m netcoin --data ~/.netcoin-testnet node \
  --host 127.0.0.1 \
  --port 28444 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444 \
  --peer http://seed3.netcoin.online:28444
```

Raw-IP fallback:

```bash
  --peer http://18.220.89.128:28444 \
  --peer http://18.220.197.20:28444 \
  --peer http://18.226.74.252:28444
```

On startup the node prints its height and tip, then syncs from peers.

## 4. Confirm you are in sync

In a second terminal:

```bash
curl http://127.0.0.1:28444/info
```

Compare your `height` and `tip_hash` against a public seed:

```bash
curl http://seed1.netcoin.online:28444/info
```

They should match once your node finishes syncing. You can also force a sync:

```bash
curl -X POST http://127.0.0.1:28444/sync
```

## 5. (Optional) Accept inbound peers

If you want others to peer with **your** node, bind to `0.0.0.0` and open the port
in your firewall / router. Only expose the **peer port (28444)**.

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 0.0.0.0 --port 28444 --peer ...
```

> **Do not** expose the RPC port (28445) or the pool port (28446) to the internet.
> Keep them bound to `127.0.0.1`. See [RPC authentication](#) notes in the README.

### Let peers discover you (gossip)

If your node has a public URL, advertise it so peers can dial you back and share
it with others. On startup the node announces this URL to its peers and pulls
their peer lists (gossip), so you only need to seed a few peers to join the mesh.

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 0.0.0.0 --port 28444 \
  --advertise http://YOUR_PUBLIC_HOST:28444 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444 \
  --peer http://seed3.netcoin.online:28444
```

Discovered peers are saved to `peers.json` in your data directory and reloaded on
restart, so the node reconnects to the mesh automatically.

## 6. Keep it running (Linux/systemd)

For an always-on node, see the systemd unit pattern in
[docs/TESTNET.md](TESTNET.md). The short version:

```ini
[Unit]
Description=NetCoin testnet node
After=network-online.target

[Service]
ExecStart=/path/to/python -m netcoin --data /home/youruser/.netcoin-testnet node \
  --host 0.0.0.0 --port 28444 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444 \
  --peer http://seed3.netcoin.online:28444
Restart=on-failure
User=youruser

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/info` times out from your Mac | local ISP/router filtering the new domain | use the raw seed IPs |
| Height stuck at 0 | no peers reachable | check `--peer` URLs and outbound firewall |
| Tip hash differs from seeds | mid-sync, or you mined a private block | `POST /sync`; a longer valid chain wins on cumulative work |
| Port already in use | another node is running | pick a different `--port` |

## Good neighbor notes

- Don't point your node at only one seed — list all three so a single seed outage
  doesn't isolate you.
- If you mine locally, your blocks relay to peers automatically when they connect.
- Report problems with node logs (never paste wallet files or private keys).

See also: [MINING.md](MINING.md) to mine, and [STARTER_KIT.md](STARTER_KIT.md) for a
full from-scratch walkthrough.
