#!/usr/bin/env python3
"""Generate a redacted NetCoin operations diagnostic bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_repo_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_ensure_repo_on_path()

from netcoin.ops_runbooks import write_diagnostic_bundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="dist/netcoin-ops-bundle.json", help="Output JSON bundle path")
    parser.add_argument("--metrics", default="", help="Optional metrics JSON file")
    parser.add_argument("--alerts", default="", help="Optional alerts JSON file")
    args = parser.parse_args()
    metrics = {}
    alerts = []
    if args.metrics:
        metrics = json.loads(Path(args.metrics).read_text())
    if args.alerts:
        alerts = json.loads(Path(args.alerts).read_text())
    result = write_diagnostic_bundle(args.out, metrics=metrics, alerts=alerts)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
