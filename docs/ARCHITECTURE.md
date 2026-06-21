# NetCoin Architecture

NetCoin is a small Bitcoin-like educational chain written in Python. The current public network is a testnet: coins have no real-money value, security review is not complete, and the goal is to prove the network shape before treating it like production software.

## 1. Current Public Testnet

Domain:

- `netcoin.online`

Public seed nodes:

- `seed1.netcoin.online:28444` -> `18.220.89.128`
- `seed2.netcoin.online:28444` -> `18.220.197.20`
- `seed3.netcoin.online:28444` -> `18.226.74.252`

Public web services:

- `explorer.netcoin.online` -> `18.220.89.128`
- `faucet.netcoin.online` -> `18.220.89.128`
- raw explorer fallback: `http://18.220.89.128/`
- raw faucet fallback: `http://18.220.89.128/faucet`
- raw monitor fallback: `http://18.220.89.128/status.json`

Current node port policy:

- `28444`: public node HTTP API
- `28445`: JSON-RPC, private/local only
- `28446`: pool/template server, private/local only
- `80`: public explorer/faucet/status on seed1
- `22`: SSH admin only

## 2. High-Level Layout

```text
Users / miners
    |
    | HTTP node API, port 28444
    v
Public seed mesh
    seed1 <----> seed2
      ^  \      /  ^
      |   \    /   |
      |    seed3   |
      +------------+
    |
    | local chain data on each seed
    v
NetCoin blockchain state

seed1 also hosts:
    - static block explorer
    - faucet
    - monitor status JSON
```

The three seed nodes are peers. Each node knows the other two by DNS name. Blocks submitted to one node can relay to the others, and each seed can sync from its peers.

## 3. Code Architecture

Core blockchain modules:

- `netcoin/block.py`: block structure, block hashing, merkle roots, proof-of-work helpers
- `netcoin/chain.py`: blockchain state, validation, UTXO set, block acceptance
- `netcoin/tx.py`: transactions, inputs, outputs, fees, ids
- `netcoin/mempool.py`: pending transaction storage and mempool policy
- `netcoin/params.py`: network parameters and money rules

Wallet and signing modules:

- `netcoin/wallet.py`: wallet files, addresses, mnemonic-style seed phrases
- `netcoin/crypto.py`: key and signature helpers
- `netcoin/script.py`: educational script templates and validation
- `netcoin/psbt.py`: PSBT-like signing container

Network and service modules:

- `netcoin/node.py`: public HTTP node API on port `28444`
- `netcoin/rpc.py`: private JSON-RPC server on port `28445`
- `netcoin/pool.py`: private pool/template server on port `28446`
- `netcoin/p2p.py`: message envelope helpers
- `netcoin/compact.py`: compact block summary helpers

User tools:

- `netcoin/cli.py`: command-line interface
- `netcoin/miner.py`: external miner workflow helpers
- `netcoin/explorer.py`: static explorer generator
- `tools/faucet_server.py`: faucet web app
- `tools/monitor_netcoin.py`: public status monitor

## 4. Node API Flow

Health and discovery:

```text
GET /info
GET /peers
GET /headers
GET /compactblocks
```

Mining:

```text
GET /blocktemplate?address=MINER_ADDRESS
miner solves proof-of-work locally
POST /submitblock
node validates block
node stores block
node relays block to peers
```

Transactions:

```text
wallet creates transaction
wallet signs transaction
wallet broadcasts to node
node validates policy
node stores in mempool
miner includes mempool txs in next block
```

Sync:

```text
POST /sync
node asks peers for chain data
node adopts valid higher-work chain
```

## 5. Mining Architecture

There are two mining modes:

- local direct mining: writes blocks into a local chain folder
- daemon mining: asks a running public seed for a block template, solves it, then submits it back

Public testnet miners should use daemon mining:

```bash
python -m netcoin miner \
  --node http://18.220.89.128:28444 \
  --wallet miner.json \
  --blocks 1
```

Raw IPs currently work best from the Mac network because the brand-new `netcoin.online` hostnames are being redirected by the local Charter/CUJO security filter.

## 6. Seed Node Runtime

Each AWS seed uses:

```text
/opt/netcoin/netcoin-v2
/opt/netcoin/netcoin-v2/.venv
/opt/netcoin/.netcoin-testnet
netcoin-node.service
```

Service shape:

```text
python -m netcoin \
  --data /opt/netcoin/.netcoin-testnet \
  node \
  --host 0.0.0.0 \
  --port 28444 \
  --peer http://seedX.netcoin.online:28444 \
  --peer http://seedY.netcoin.online:28444
```

The chain state lives on disk per node. The seed nodes are intentionally simple: no public RPC wallet, no public private keys, and no public pool port.

## 7. Explorer Architecture

The explorer is static HTML generated from the seed1 chain data.

Flow:

```text
seed1 chain data
    |
    v
python -m netcoin explorer
    |
    v
/var/www/netcoin-explorer
    |
    v
Nginx port 80
```

It refreshes by cron every two minutes. This keeps the explorer simple and safer than a dynamic database-backed explorer at this stage.

## 8. Faucet Architecture

The faucet is a small HTTP app on seed1 behind Nginx.

Flow:

```text
user enters address
    |
    v
faucet app validates address
    |
    v
faucet wallet creates transaction
    |
    v
transaction broadcasts to local seed1 node
```

Current faucet policy:

- sends `5` test NET
- uses `0.01` NET fee
- one request per IP per 24 hours
- uses a hot testnet wallet on seed1

The faucet wallet is only for testnet coins.

## 9. Monitoring Architecture

The monitor runs on seed1 and checks:

- seed1 node
- seed2 node
- seed3 node
- explorer
- faucet

It writes public JSON to:

```text
/opt/netcoin/monitor/status.json
```

Nginx serves it at:

```text
http://18.220.89.128/status.json
```

The status file tracks node heights, tips, availability, and whether the seed tips match.

## 10. Trust Boundaries

Public:

- node HTTP API on `28444`
- explorer
- faucet
- status JSON

Private:

- SSH keys
- wallet files
- faucet hot wallet
- JSON-RPC
- pool/template server
- server filesystem

Rules:

- never expose `28445` publicly
- never expose `28446` publicly until the pool design is reviewed
- never publish wallet mnemonics or private keys
- keep faucet wallet limited to small testnet funds
- treat all public testnet code as experimental

## 11. Current Architecture Weak Spots

- All public web services are currently on seed1.
- All seed nodes are in the same AWS account and region.
- The faucet uses a hot wallet on the server.
- The explorer is static and refreshes every two minutes, so it is not instant.
- The brand-new domain is being blocked by at least one local ISP/router security filter.
- The project is not yet on GitHub.
- There are no signed releases yet.
- No third-party security review has happened yet.

## 12. Target Architecture

Near-term target:

```text
3 official seed nodes
2+ independent community nodes
2+ independent miners
public explorer
public faucet
public monitor
GitHub repo
release zip + checksum
basic security test checklist
```

Better target:

```text
official seed nodes in multiple providers/regions
community-run nodes outside the founder account
separate explorer host
separate faucet host
faucet wallet with low balance limits
signed release artifacts
automated tests on every release
documented upgrade process
```

Long-term target:

```text
real peer-to-peer networking
database-backed explorer
rate-limited public APIs
proper miner/pool protocol
node versioning and compatibility rules
automated monitoring and alerts
security review
repeatable reproducible builds
```

## 13. Roadmap Order

Completed:

- three public seed nodes
- seed DNS records
- first public testnet blocks
- public explorer
- public faucet
- public monitoring
- external daemon miner workflow

Next:

- add independent node runners
- add independent miners
- publish GitHub repo
- add release checksums and signatures
- start security testing
- split explorer/faucet away from seed1 when the network grows

