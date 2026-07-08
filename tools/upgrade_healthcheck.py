#!/usr/bin/env python3
"""Smoke-check optional professional upgrade modules."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MODULES = [
    "netcoin.indexer_insights",
    "netcoin.wallet_policy",
    "netcoin.ops_incidents",
    "netcoin.apps.markets.governance",
    "netcoin.exchange_accounting",
]


def main() -> int:
    loaded = []
    for name in MODULES:
        importlib.import_module(name)
        loaded.append(name)
    print(json.dumps({"ok": True, "loaded_modules": loaded}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
