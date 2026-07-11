#!/usr/bin/env python3
"""Validate NetCoin Phase 0.2 design-system and workflow architecture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.design_system import validate_design_system


def main() -> int:
    report = validate_design_system()
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
