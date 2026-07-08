# NetCoin Storage Schema

Generated from `netcoin/storage_migrations.py`.

## `active_chain`

| Column | Type | Not null | Default | Primary key |
|---|---|---:|---|---:|
| `position` | `INTEGER` | 0 | `None` | 1 |
| `hash` | `TEXT` | 0 | `None` | 0 |

## `address_index`

| Column | Type | Not null | Default | Primary key |
|---|---|---:|---|---:|
| `address` | `TEXT` | 0 | `None` | 1 |
| `txid` | `TEXT` | 0 | `None` | 2 |

## `blocks`

| Column | Type | Not null | Default | Primary key |
|---|---|---:|---|---:|
| `hash` | `TEXT` | 0 | `None` | 1 |
| `height` | `INTEGER` | 0 | `None` | 0 |
| `prev_hash` | `TEXT` | 0 | `None` | 0 |
| `data` | `TEXT` | 0 | `None` | 0 |

## `chain_audit_log`

| Column | Type | Not null | Default | Primary key |
|---|---|---:|---|---:|
| `event_id` | `INTEGER` | 0 | `None` | 1 |
| `event` | `TEXT` | 1 | `None` | 0 |
| `payload` | `TEXT` | 1 | `None` | 0 |
| `created_at` | `INTEGER` | 1 | `strftime('%s','now')` | 0 |

## `mempool`

| Column | Type | Not null | Default | Primary key |
|---|---|---:|---|---:|
| `txid` | `TEXT` | 0 | `None` | 1 |
| `data` | `TEXT` | 0 | `None` | 0 |

## `meta`

| Column | Type | Not null | Default | Primary key |
|---|---|---:|---|---:|
| `key` | `TEXT` | 0 | `None` | 1 |
| `value` | `TEXT` | 0 | `None` | 0 |

## `schema_migrations`

| Column | Type | Not null | Default | Primary key |
|---|---|---:|---|---:|
| `version` | `INTEGER` | 0 | `None` | 1 |
| `name` | `TEXT` | 1 | `None` | 0 |
| `applied_at` | `INTEGER` | 1 | `strftime('%s','now')` | 0 |

## `sqlite_sequence`

| Column | Type | Not null | Default | Primary key |
|---|---|---:|---|---:|
| `name` | `` | 0 | `None` | 0 |
| `seq` | `` | 0 | `None` | 0 |

## `tx_index`

| Column | Type | Not null | Default | Primary key |
|---|---|---:|---|---:|
| `txid` | `TEXT` | 0 | `None` | 1 |
| `block_hash` | `TEXT` | 0 | `None` | 0 |
| `height` | `INTEGER` | 0 | `None` | 0 |
| `position` | `INTEGER` | 0 | `None` | 0 |

## `utxo_snapshot`

| Column | Type | Not null | Default | Primary key |
|---|---|---:|---|---:|
| `id` | `INTEGER` | 0 | `None` | 1 |
| `data` | `TEXT` | 0 | `None` | 0 |
