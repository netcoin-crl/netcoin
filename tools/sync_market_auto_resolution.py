#!/usr/bin/env python3
"""Poll the live Polymarket Gamma API for every imported market still waiting
on a real-world result, and complete auto-resolution for any that now have a
winner.

_sync_auto_resolution_queue() (in netcoin/apps/markets) already handles the
time-based half of this — flipping a market to "awaiting_source_result" once
its close_time passes — but it can only *finish* resolving a market once a
source_winning_outcome_label is known. This script is the missing other half:
it makes the real outbound HTTP call to Polymarket so nobody has to type the
winner in by hand.

Run this on a schedule (cron, systemd timer) rather than on every page load —
it makes real network calls per pending market.

Usage:
    python tools/sync_market_auto_resolution.py [--data DATA_DIR] [--out report.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.apps import AppStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=".netcoin-testnet", help="node data directory (default: .netcoin-testnet)")
    parser.add_argument("--out", default=None, help="write the report JSON to this path")
    args = parser.parse_args()

    store = AppStore(args.data)
    report = store.sync_all_pending_auto_resolutions()
    print(json.dumps(report, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
