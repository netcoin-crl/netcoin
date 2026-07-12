# M3 Node Operator Guide

M3 goal: at least 10 independent operators run public NetCoin testnet nodes, the chain runs unattended for 30 days, and at least one non-founder operator mines a block.

## Roles

- Public relay node: validates and relays blocks/transactions on TCP `28444`.
- Seed node: public relay node with stable uptime and DNS visibility.
- Miner: node that attempts to produce testnet blocks.
- Observer: non-mining node that reports uptime, peers, block height, and propagation metrics.

## Minimum operator checklist

1. Use a host not controlled by the founder.
2. Open TCP `28444` inbound.
3. Run current NetCoin software from a signed release once available.
4. Keep wallet private keys off public seed machines.
5. Enable home bandwidth mode if running from a home ISP.
6. Report operator name, rough region, endpoint, and uptime evidence.
7. Run for at least 30 days during the M3 public soak.

## One-command source installer

Review before running:

```bash
curl -fsSL https://download.netcoin.online/install-public-node.sh -o install-public-node.sh
sh install-public-node.sh --dry-run
sh install-public-node.sh --prefix "$HOME/.netcoin-public-node" --advertise YOUR_PUBLIC_IP_OR_DNS:28444
```

## Docker Compose path

```bash
cp docker-compose.node.yml docker-compose.yml
NETCOIN_ADVERTISE=YOUR_PUBLIC_IP_OR_DNS:28444 docker compose up -d
```

## Evidence to submit

- Endpoint: `host:28444`
- Operator handle
- Cloud/home/bare-metal category
- Region/country level only, never street address
- 24h uptime sample
- Peer count sample
- Block height sample
- If mining, a block hash mined by this operator
