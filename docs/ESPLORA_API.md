# NetCoin Esplora-compatible API

NetCoin nodes expose a read-only subset of the [Blockstream Esplora HTTP API]
under `/esplora/*`, so Bitcoin-family tooling (BDK, wallet libraries, scripts)
can point at a NetCoin node with only a base-URL change.

Base URL: `http://<node>:28444/esplora`

## Endpoints

| Endpoint | Returns |
|---|---|
| `GET /esplora/blocks/tip/height` | tip height (plain text integer) |
| `GET /esplora/blocks/tip/hash` | tip block hash (plain text) |
| `GET /esplora/block-height/:height` | block hash at height (plain text) |
| `GET /esplora/block/:hash` | block object (`id, height, version, timestamp, tx_count, merkle_root, previousblockhash, nonce, bits`) |
| `GET /esplora/tx/:txid` | tx object (`txid, version, locktime, vin[], vout[], value, status`) |
| `GET /esplora/address/:address` | `{address, chain_stats, mempool_stats}` |
| `GET /esplora/address/:address/utxo` | `[{txid, vout, value, status}]` |
| `GET /esplora/fee-estimates` | confirmation-target → sat/vB map |

`status` is `{confirmed, block_height, block_hash, block_time}`. Values are in
satoshis, matching Esplora.

## Compatibility notes (honest scope)

- This is a **read** subset; the endpoints wallets use most for balance/history/
  fee estimation are covered.
- Fields NetCoin does not model — raw `scriptpubkey` hex/asm, per-mempool
  address stats, tx `size`/`weight`/`fee` on lookups — are **omitted rather than
  faked**. `scriptpubkey_address` and `value` (what wallets actually read) are
  always present; `mempool_stats` is reported as zeros.
- Not yet mapped: `/address/:address/txs` pagination, `/tx/:txid/hex`,
  broadcast via `POST /tx` (use the native `POST /tx` route). These are additive
  and can follow if tooling needs them.

## Verify against a running node

```bash
curl -s http://127.0.0.1:28444/esplora/blocks/tip/height
curl -s http://127.0.0.1:28444/esplora/fee-estimates | jq .
H=$(curl -s http://127.0.0.1:28444/esplora/blocks/tip/hash)
curl -s http://127.0.0.1:28444/esplora/block/$H | jq .
```

[Blockstream Esplora HTTP API]: https://github.com/Blockstream/esplora/blob/master/API.md
