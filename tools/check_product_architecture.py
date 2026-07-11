#!/usr/bin/env python3
"""Validate the Phase 0 NetCoin product/UX architecture specification."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.product_architecture import validate_product_architecture


def main() -> int:
    report = validate_product_architecture()
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
