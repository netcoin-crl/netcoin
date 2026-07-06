# NetCoin Exchange Integration Guide

This guide is for a sandbox exchange, test exchange, or future listing review.
NetCoin is still an educational public testnet. Do not present this as
real-money/mainnet exchange readiness until the security review checklist is
complete.

## Integration Model

An exchange should run its own NetCoin node and private RPC service.

```text
NetCoin network
  -> exchange full node
  -> private JSON-RPC
  -> deposit indexer
  -> exchange ledger database
  -> withdrawal queue
  -> offline/manual signer or tightly limited hot wallet
  -> broadcast through node
```

Do not use the public explorer, faucet, or public API as the exchange source of
truth. They are useful for humans, not custody accounting.

## Required Services

Run these on exchange infrastructure:

- Full NetCoin node, synced to the public testnet.
- Private JSON-RPC bound to `127.0.0.1` or a private network.
- Bearer token for RPC if anything other than localhost can reach it.
- Deposit watcher/indexer that records block hash, height, transaction id,
  output index, address, amount, and confirmation count.
- Withdrawal queue with manual approval for large withdrawals.
- Hot-wallet balance monitor and cold-wallet refill process.

Recommended ports:

| Port | Purpose | Exposure |
| --- | --- | --- |
| `28444` | public node HTTP API / peer API | public if operating a seed |
| `28445` | JSON-RPC | private only |
| `18447` | experimental TCP P2P | private/test only unless intentionally testing |

## Private RPC Setup

Start RPC on localhost with a token:

```bash
export NETCOIN_RPC_TOKEN='replace-with-long-random-token'
python -m netcoin rpc --host 127.0.0.1 --port 28445
```

Call it:

```bash
curl -sS http://127.0.0.1:28445 \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $NETCOIN_RPC_TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getexchangeinfo","params":[]}'
```

## Exchange-Facing RPC Methods

These methods are intentionally small and explicit. They provide the pieces a
test exchange needs without claiming full Bitcoin Core RPC compatibility.

| Method | Purpose |
| --- | --- |
| `getexchangeinfo` | Network/ticker/confirmation/custody notes for integrators |
| `validateaddress <address>` | Validate a NetCoin address and return address type metadata |
| `getaddressbalance <address>` | Confirmed total/spendable/immature balance summary |
| `getaddresssummary <address> [limit] [offset]` | Address balance plus paginated transaction ids |
| `listaddressutxos <address> [include_immature] [include_mempool_spent]` | Spendable outputs for deposits/accounting |
| `gettransactionstatus <txid>` | Confirmation count, block placement, mempool/RBF status, outputs |
| `getrawtransaction <txid> [verbose]` | Raw or decoded transaction |
| `sendrawtransaction <tx_json>` | Broadcast a signed NetCoin transaction JSON object |
| `getblockcount` | Current height |
| `getbestblockhash` | Current tip hash |
| `getblock <hash> [verbosity]` | Block data |
| `getrawmempool [verbose]` | Mempool txids or details |
| `estimatesmartfee [target_blocks]` | Fee estimate for withdrawals |

## Deposit Flow

1. Generate or assign a deposit address in the exchange wallet system.
2. Store the address with an internal user id.
3. Poll `getblockcount` and `getbestblockhash`.
4. For each watched address, call `getaddresssummary` or scan new blocks.
5. For each new txid, call `gettransactionstatus`.
6. Credit only after the configured confirmation threshold.
7. Store the credit with `txid`, `vout`, `amount_sats`, `block_height`, and
   `block_hash`.

Recommended public-testnet confirmations:

| Deposit size | Minimum confirmations |
| --- | --- |
| Faucet/test amount | `3` |
| Normal sandbox deposit | `20` |
| Large sandbox deposit | `60+` plus manual review |

NetCoin has low public-testnet hashpower. Confirmations are weaker than Bitcoin
confirmations.

## Reorg Handling

The exchange database must never assume a deposit is permanent just because it
was seen once.

Store these fields for every credited deposit:

- address
- txid
- vout
- amount_sats
- block_height
- block_hash
- credited_at_height
- confirmations_required

On every new tip:

1. Compare the stored latest `height -> block_hash` mapping to the node's chain.
2. If a recent block hash changed, mark deposits from disconnected blocks as
   pending again.
3. Re-run `gettransactionstatus` for affected txids.
4. Re-credit only after the transaction is confirmed again with enough
   confirmations.

Keep at least the last `100` block hashes in the exchange database so reorg
detection does not depend on the explorer.

## Withdrawal Flow

1. User requests withdrawal.
2. Exchange checks internal ledger balance.
3. Withdrawal service validates destination with `validateaddress`.
4. Build and sign the transaction using the exchange wallet/signing system.
5. Broadcast with `sendrawtransaction`.
6. Track with `gettransactionstatus`.
7. Mark complete after the exchange's withdrawal confirmation policy.

Minimum controls before real custody discussion:

- Daily withdrawal limit.
- Per-withdrawal review threshold.
- Manual approval for new destination addresses.
- Hot-wallet maximum balance.
- Cold-wallet refill process.
- Withdrawal queue audit log.
- Emergency pause switch.

## Address Policy

Preferred deposit type: SegWit P2WPKH (`net1q...`).

Accepted address types for testnet integration:

- `net1q...` P2WPKH
- `N...` legacy P2PKH
- `p...` P2SH / P2SH-SegWit
- `net1p...` Taproot-style

For exchange operations, use one unique deposit address per user/account or per
deposit request. Reusing a single address for many users makes accounting and
support harder.

## Accounting Rules

- The blockchain does not know user balances inside the exchange.
- The exchange ledger credits users only after confirmed deposits.
- Withdrawals reduce the exchange ledger immediately and then settle on-chain.
- Never calculate tradable balances from current UTXOs alone.
- Treat immature coinbase rewards as non-spendable until maturity.

Coinbase maturity: `100` confirmations.

## Security Requirements Before Listing

Before any real-money/mainnet exchange listing, finish:

- Independent consensus and wallet review.
- Long-running reorg, mempool, and node soak tests.
- Release signing policy with reproducible artifacts.
- Hot/cold wallet key-management design.
- Incident response and emergency pause runbook.
- Public upgrade policy and minimum supported node version policy.
- Legal/compliance review.

## Quick Sandbox Checklist

- [ ] Exchange runs its own node.
- [ ] RPC is private and token-protected.
- [ ] Deposit watcher records block hash and height.
- [ ] Deposits require confirmations.
- [ ] Reorg rollback logic is tested.
- [ ] Withdrawals use a queue.
- [ ] Large withdrawals require manual review.
- [ ] Hot wallet has a maximum balance.
- [ ] Backups and restore drills are documented.
- [ ] Monitoring alerts on node down, stuck height, fork, and low hot-wallet balance.
