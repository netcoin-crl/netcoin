# P2P And Node API

## Node Runtime

The node runtime is implemented by `NetCoinNode` in `netcoin/node.py`.
It wraps a `Blockchain`, peer list, peer manager, sync scheduler, relay queue,
and HTTP API server.

The public HTTP node is intentionally local/testnet-oriented. Production
operator policy such as rate limits, peer scoring, and seed choices are not
consensus rules.

## Peer Discovery

Peer discovery is implemented by:

- `netcoin/node.py`: `/peers` endpoint, peer exchange, peer manager wiring;
- `netcoin/pex.py`: peer exchange helpers;
- `netcoin/peerdb.py`: persistent peer records;
- `netcoin/addrv2.py`: AddrV2-safe address records.

Nodes advertise service names including `network`, `headers`,
`compact-blocks`, `mempool`, `block-template`, `explorer-api`, and
`compact-filters`.

## P2P Messages

Structured P2P message handling lives in `netcoin/p2p.py`. The implemented
message families include:

- `version` / `verack`
- `ping` / `pong`
- `getheaders` / `headers`
- `inv`
- `getdata`
- `block`
- `tx`

P2P parity behavior is mirrored in `core-rs/crates/node/src/lib.rs`.

## HTTP Read Endpoints

Important read endpoints in `netcoin/node.py` include:

- `/info`
- `/health`
- `/block/<hash>`
- `/tx/<txid>`
- `/mempool`
- `/blocktemplate`
- `/peers`
- `/compact-block/<hash>`
- `/compact-block-missing/<hash>`
- metrics/status routes documented elsewhere.

These endpoints expose node state and relay helpers. They do not define
additional consensus rules beyond the underlying block/transaction validation
code paths.

## HTTP Write Endpoints

Important write endpoints include:

- `POST /tx`
- `POST /block`
- `POST /submitblock`
- `POST /compact-block`
- `POST /peers`
- `POST /sync`
- `POST /relay`

Write endpoints are bounded by `MAX_REQUEST_BODY_BYTES` and node policy. Blocks
submitted through `/block` or `/submitblock` still pass through chain validation.
Transactions submitted through `/tx` pass through mempool policy.

## Relay Queue

Relay queue behavior is implemented in `NetCoinNode.enqueue_relay()` and
`NetCoinNode.drain_relay_queue()` in `netcoin/node.py`. The relay queue is
bounded and retries failed peers with backoff. Peer failures can affect peer
score but do not alter consensus validity.

## Compact Blocks

Compact block helpers live in `netcoin/compact.py`:

- compact block construction;
- short transaction ids;
- missing transaction discovery;
- reconstruction from extra transactions.

Node endpoints `/compact-block/<hash>`, `/compact-block-missing/<hash>`, and
`POST /compact-block` expose this behavior for relay and testing.

## Sync And Headers

Sync helpers live in `netcoin/sync.py` and `netcoin/node.py`. Header linkage is
validated before block download work is assigned. Bad peers can be marked in the
sync scheduler without changing chain validation rules.

## Localnet Validation

`tools/run_localnet.py` starts real node subprocesses on `127.0.0.1`, exercises
peer exchange, header sync, transaction relay, compact blocks, restart replay,
and reorg resolution. Tests are marked `@pytest.mark.localnet` in
`tests/test_localnet_harness.py`.

## Validation Entry Points

Primary code paths:

- `netcoin/node.py`: HTTP API, relay queue, peer wiring, block/tx submission.
- `netcoin/p2p.py`: structured P2P messages.
- `netcoin/addrv2.py`: safe address records.
- `netcoin/compact.py`: compact block encoding/reconstruction.
- `netcoin/sync.py`: header/sync scheduler behavior.
- `netcoin/peerdb.py`: peer persistence.

Coverage and vectors:

- `tests/test_p2p_messages.py`
- `tests/test_p2p_node_sync.py`
- `tests/test_remaining_code_upgrades.py`
- `tests/test_localnet_harness.py`
- `core-rs/fixtures/parity-vectors.json` p2p lane
- `core-rs/crates/node/src/lib.rs`
