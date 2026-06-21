# NetCoin Security Testing

This checklist is for the public testnet. Testnet NET has no real-money value, but the public services should still fail safely.

## Current Automated Coverage

Run:

```bash
python -m pytest
```

The regression suite covers:

- malformed block with a bad merkle root is rejected
- block with a wrong previous hash is rejected
- block with a far-future timestamp is rejected
- block that exceeds the weight limit is rejected
- block containing an internal double spend is rejected
- transaction changed after signing is rejected
- transaction with a forged signature is rejected
- input signed by the wrong key is refused at signing time
- replayed transaction after mining is rejected
- conflicting non-RBF double spend is rejected from the mempool
- double spend of an already-mined UTXO is rejected
- duplicate block submission is idempotent
- headers limit is clamped (unit level and over HTTP)
- malformed node JSON returns an error without crashing the node
- garbage block POST returns 400 and the node keeps serving `/info`
- peer sync adopts a longer valid chain
- peer sync ignores an invalid chain and lower/equal-work chains
- node and RPC servers reject oversized request bodies
- JSON-RPC requires a bearer token when one is configured (401 vs 200)
- subsidy halving schedule (including zero past 64 halvings, negative-height guard)
- explorer generation and status-dashboard rendering (with HTML escaping)
- fuzz suite: transaction/block parsing, raw-tx decoding, script parsing, and node
  endpoints survive random/garbage input without crashing
- wallet seed-phrase verification, recovery round-trips, encrypted save/load with
  wrong-passphrase and tamper rejection, and key/address mismatch rejection
- faucet hardening: body cap, per-minute burst throttle, abuse-log capping, and the
  wallet-balance gate
- node peer persistence reloads known peers across restarts
- chain reorg: adopts a heavier valid fork, keeps the first-seen tip on equal work,
  rejects invalid and bad-proof-of-work forks, connects out-of-order blocks, and
  returns disconnected-block transactions to the mempool
- block relay de-duplication (echoed blocks are not re-broadcast) and tip relay
- explorer embeds a searchable per-block index (height/hash/txid/address)
- peer gossip: discover peers by pull, announce self by push, exclude self, and
  cap the peer set to bound growth
- faucet invalid-address and IP cooldown logic

## Live Public Smoke Checks

Use raw IPs if the local network blocks fresh `netcoin.online` hostnames.

```bash
curl http://18.220.89.128:28444/info
curl http://18.220.197.20:28444/info
curl http://18.226.74.252:28444/info
curl http://18.220.89.128/status.json
```

Expected:

- all seeds return JSON
- all seed heights match
- all seed tip hashes match
- `ok` is `true` in status JSON

## Malformed Blocks

Safe local tests:

- submit a block with a bad merkle root
- submit a block with a wrong previous hash
- submit a block with invalid proof of work
- submit a block with a future timestamp
- submit a block with two coinbase transactions
- submit a block with no coinbase transaction
- submit the same valid block twice

Expected:

- invalid blocks return `{ "ok": false, "error": "..." }`
- node height does not change
- service remains running
- duplicate valid block returns the same hash without creating orphan noise

Avoid blasting the live seeds with large fuzz payloads until rate limits and payload-size limits are added.

## Bad Transactions

Safe local tests:

- invalid address output
- negative output amount
- output above `MAX_MONEY`
- dust output
- fee below minimum relay fee
- duplicate input outpoints
- immature coinbase spend
- bad signature
- replay a transaction after it was mined
- double-spend a non-RBF mempool transaction
- RBF replacement with too-low fee

Expected:

- bad transactions are rejected from the mempool
- mempool size does not increase
- node remains available
- valid RBF replacement only succeeds with higher fee

## Faucet Abuse

Safe local tests:

- invalid address
- repeat request from same IP
- very long address string
- empty address
- form post to wrong path
- unavailable node behind faucet
- faucet wallet with insufficient funds

Expected:

- invalid input does not call the send command
- same IP is limited by cooldown
- faucet errors are shown without leaking server paths or secrets
- state file remains valid JSON

Recommended next hardening:

- cap request body size
- ignore or restrict untrusted `X-Forwarded-For` unless set by trusted Nginx
- add basic per-minute throttle, not only 24-hour cooldown
- keep faucet wallet balance low

## Node Crash Testing

Safe local tests:

- malformed JSON POST
- unknown path
- missing fields
- invalid query params
- slow client connection
- many concurrent `/info` requests
- many concurrent invalid `/tx` requests

Expected:

- node returns 400 or 404 where appropriate
- node still answers `/info`
- systemd restarts the service if the process exits
- logs do not expose secrets

Recommended next hardening:

- cap request body size in the node handler
- add per-IP reverse-proxy rate limits
- add structured logs for rejected inputs
- run public nodes behind Nginx if traffic grows

## Replay Issues

Test:

- rebroadcast already-mined transaction
- rebroadcast already-known mempool transaction
- resubmit already-mined block
- submit older lower-work chain to `/sync`

Expected:

- already-mined transaction is rejected as spent
- already-known mempool transaction returns same txid without duplication
- duplicate block is idempotent
- lower-work chains are not adopted

## Public Endpoint Limits

Check:

- `/headers?limit=999999`
- `/blocktemplate` without address
- `/utxos?address=bad`
- `/block/unknown`
- `/compact-block/unknown`
- repeated `/sync`

Expected:

- limits are clamped
- bad addresses return errors
- unknown block hashes return 404
- sync does not lower chain work

Recommended next hardening:

- explicit maximum JSON body size
- Nginx `limit_req` for public endpoints
- Nginx `client_max_body_size`
- separate faucet/explorer host from seed nodes
- automated uptime checks from outside AWS

## Production Gate

Before calling the network production-like:

- tests pass locally and on each seed
- at least two independent node runners are online
- at least two independent miners have mined blocks
- public release checksum is published
- release artifact is signed
- node, faucet, and explorer have rate limits
- no wallet mnemonic or private key is published

