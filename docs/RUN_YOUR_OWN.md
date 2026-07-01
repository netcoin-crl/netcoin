# Run NetCoin yourself (no reliance on the public websites)

The public sites (wallet.netcoin.online, explorer, seeds, API) are a convenience.
**Nothing requires them.** You can run the whole thing on your own machine and
trust only your own node. This guide shows how — and why you'd want to.

- [Why run your own node and seed](#why-run-your-own-node-and-seed)
- [Mine to an address you already have](#mine-to-an-address-you-already-have)
- [Run your own full node](#run-your-own-full-node)
- [Run your own public seed](#run-your-own-public-seed)
- [Use NetCoin 100% locally](#use-netcoin-100-locally)

First, install from source (see [INSTRUCTIONS.md](../INSTRUCTIONS.md)) so
`python -m netcoin --help` works in your activated virtualenv.

---

## Why run your own node and seed

- **Trust nothing but math.** When you query your own node, no third party can lie
  to you about your balance, a transaction, or the chain tip. "Don't trust, verify."
- **Privacy.** Public explorers/wallets can log which addresses you look up and
  where your requests come from. Your own node tells no one.
- **Availability & censorship-resistance.** If a public seed is down, filtered by
  your ISP, or blocks you, your own node keeps working and can reach peers directly.
- **You strengthen the network.** Every independent node validates the rules for
  itself; every seed helps new nodes find peers. More seeds = more decentralized.
- **It's the honest test of the coin.** A currency you can only use through one
  company's website isn't decentralized. Running your own proves it doesn't need them.

---

## Mine to an address you already have

If you already have an address (from the wallet, a `wallet.json`, or anywhere),
you do **not** need a wallet file to mine — pass the address directly with
`--address`. Rewards are paid straight to it.

Mine one block to your address, against your own node (recommended) or a public one:

```bash
# against YOUR node (see below) — fully self-reliant:
python -m netcoin miner --node http://127.0.0.1:28444 \
  --address net1youraddresshere --address-type p2wpkh --blocks 1 --sync-after

# or against a public seed, if you don't run a node yet:
python -m netcoin miner --node http://seed1.netcoin.online:28444 \
  --address net1youraddresshere --address-type p2wpkh --blocks 1 --sync-after
```

Mine continuously until you stop it (Ctrl+C):

```bash
while true; do
  python -m netcoin miner --node http://127.0.0.1:28444 \
    --address net1youraddresshere --address-type p2wpkh --blocks 1 --sync-after
done
```

`--address-type` can be `p2wpkh` (the modern `net1…` SegWit address, recommended),
`p2pkh`, `p2tr`, or `p2sh-segwit` — match the address you're paying to. Coinbase
rewards are **spendable after 100 confirmations** (coinbase maturity).

---

## Run your own full node

A full node downloads and **validates** the chain itself, then serves a local API
your wallet/miner/explorer can use. It connects out to public seeds to find peers;
you don't need to be reachable from the internet.

```bash
python -m netcoin --data ~/.netcoin-testnet node \
  --host 127.0.0.1 --port 28444 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444 \
  --peer http://seed3.netcoin.online:28444
```

Leave that terminal running. Check it in another terminal:

```bash
curl -s http://127.0.0.1:28444/info | python3 -m json.tool   # height, tip, peers, version
```

Now point everything (`--node http://127.0.0.1:28444`) at your own node instead of
a public one. Your balance and transactions are verified locally.

> Keep your node updated: any consensus change (e.g. the reward schedule) must be
> on **≥ the network version** before its activation height, or you'll fork off.
> See [DEPLOY.md](DEPLOY.md).

---

## Run your own public seed

A **seed** is just a full node that (a) is reachable from the internet on its
port and (b) that others list as a `--peer`. To run one:

1. Run the node with `--host 0.0.0.0` so it accepts inbound connections:
   ```bash
   python -m netcoin --data ~/.netcoin-seed node --host 0.0.0.0 --port 28444 \
     --peer http://seed1.netcoin.online:28444 \
     --peer http://seed2.netcoin.online:28444
   ```
2. Open the port to the internet (router port-forward, or cloud security-group
   inbound rule for TCP `28444`).
3. Share your node URL (`http://your-host:28444`) so others can add it as a peer.
4. To keep it running across reboots, install it as a service — see the systemd
   unit pattern in [OPERATIONS.md](OPERATIONS.md) / [NODE_RUNNER.md](NODE_RUNNER.md).

More independent seeds is exactly what makes the network resilient — if one
operator disappears, the others carry it.

---

## Use NetCoin 100% locally

You can create/hold funds, send, mine, and explore without touching any
`netcoin.online` site. Run three things on your machine:

**1. Your node** (above) — the source of truth for balances and broadcast.

**2. The local browser wallet** — the same non-custodial wallet, served from your
own machine, talking to your own node. Keys never leave your browser.

```bash
# serve the browser wallet locally (from a repo checkout)
cd webwallet-browser && python3 -m http.server 8099 --directory public
```
Open `http://127.0.0.1:8099/wallet.html`. Point its API at your node by adding a
meta tag / config that sets the API base to `http://127.0.0.1:28444` (the wallet
defaults to a same-origin `/api`; for a local node, run a tiny proxy or use the
dev server in `webexplorer/tools/devserver.py` as a template).

Or use the built-in local wallet tool (server-side, single-user, on your own machine only):
```bash
python -m netcoin web --node http://127.0.0.1:28444 --port 8090
# then open http://127.0.0.1:8090
```

**3. The local explorer** — browse your own node's chain:
```bash
cd webexplorer && NETCOIN_NODE=http://127.0.0.1:28444 python3 tools/devserver.py
# then open http://127.0.0.1:8077
```

That's the whole system — wallet, node, miner, explorer — running on your machine,
depending on no one. The public websites become just a convenience you can ignore.
