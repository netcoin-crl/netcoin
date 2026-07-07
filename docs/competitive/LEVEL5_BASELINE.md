# NetCoin Competitive 5/10 Baseline

This document records the upgrade from skeleton-only competitive features to a
midlevel **5/10** baseline across every competitive feature area.

A 5/10 feature in this repository means:

- the feature is represented by deterministic testnet/dev code,
- operator controls are available from the feature module,
- the feature is included in JSON/Markdown reports,
- smoke checks and validation tests exist,
- failure paths are represented where practical,
- production and real-money claims are still blocked.

A 5/10 feature does **not** mean:

- externally audited,
- mainnet-ready,
- custody-grade,
- legally cleared,
- exchange-certified,
- safe for real-money event markets.

Run checks:

```bash
python tools/competitive_gap_report.py --level5 --json
python tools/competitive_gap_report.py --level5 --validate
python tools/competitive_gap_report.py --smoke
python -m netcoin.cli competitive-check --level5 --validate --fail-on-issues
pytest tests/test_competitive_level5.py
```

The implementation lives mainly in `netcoin/competitive/level5.py`, while each
area module exposes area-specific controls and smoke checks.
