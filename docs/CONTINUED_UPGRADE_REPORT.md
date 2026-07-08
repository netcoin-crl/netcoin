# Continued Upgrade Report

This build continues the v0.13 professional upgrade path after the batch-upgrade release.  It focuses on improving existing features rather than adding unrelated surface area.

## Explorer and indexer

- Added rich address profiles with first/last seen metadata, received/sent totals, activity counts, dust flags, and coinbase receive counts.
- Added top-address ranking by derived balance and volume.
- Added mempool summary from the derived explorer index.
- Added CSV export for address history.
- Added index integrity checks for orphan address events, missing block references, and duplicate block rows.
- Exposed convenience wrappers through `netcoin.indexer_api`.

## Wallet safety and recovery

- Added transaction policy decisions: allow, review, or block based on fee and risk thresholds.
- Added wallet safety report generation with a stable SHA-256 report hash.
- Added NetCoin signmessage signing for wallet safety reports.
- Added recovery action planning for invalid seed phrases, undecrypted backups, migration needs, and HD scan findings.
- Added recovery report export with embedded action plan.

## Network and operations

- Added peer database health reports, outbound peer selection, and stale peer pruning.
- Added sync scheduler assignment, stalled job detection, and sync health reports.
- Added in-memory metrics history and service-health summaries for dashboards and alerting.

## Markets Labs

- Added oracle reputation reporting.
- Added market resolution-readiness checks based on approved evidence and disputes.
- Added market-maker inventory risk reports and rebalance suggestions.
- Added stricter settlement audit reports with accounting checklist rows.

## Exchange and release trust

- Added exchange withdrawal risk-limit reports for hot wallet and daily-limit checks.
- Added outstanding-liability summaries for credited deposits versus withdrawal obligations.
- Added release provenance generation and verification tools.
- Added `make provenance-check`.

## Validation

The following checks were run successfully:

```text
python -m compileall -q netcoin tools
python -m pytest -q tests/test_continued_upgrades.py tests/test_upgrade_batches.py tests/test_node_ops.py tests/test_sqlite_backend.py
python tools/professional_upgrade_audit.py --fail-on-issues
python tools/check_openapi_contract.py
make test-fast
make provenance-check
```

This is still a testnet/educational codebase and not an external audit or mainnet readiness claim.
