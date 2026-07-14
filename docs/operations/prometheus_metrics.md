# NetCoin Prometheus Metrics

`GET /metrics` exposes Prometheus text format for node operators. The endpoint is
read-only and has no consensus effect.

## Core Series

- `netcoin_block_height` - active chain height.
- `netcoin_chain_tip_info{network,tip_hash}` - tip identity as a labelled gauge.
- `netcoin_mempool_transactions` - transactions currently admitted to mempool.
- `netcoin_mempool_bytes` - virtual bytes currently admitted to mempool.
- `netcoin_peers` - configured or discovered peers.
- `netcoin_banned_peers` - banned peers.
- `netcoin_orphan_candidates` - off-tip block candidates retained for fork/reorg handling.
- `netcoin_relay_queue_items` - pending relay queue items.
- `netcoin_outbound_relay_bytes_total` - outbound relay bytes sent.
- `netcoin_outbound_relay_throttle_events_total` - relay throttling events.
- `netcoin_cumulative_work` - cumulative active-chain work.
- `netcoin_uptime_seconds` - node process uptime.
- `netcoin_build_info{version,protocol_version,network,user_agent}` - static node metadata.

## Grafana

Import `ops/grafana/netcoin-node-dashboard.json` and point it at the Prometheus
data source scraping `/metrics`.
