#!/usr/bin/env python3
"""Validate the v0.42 website UI polish pass."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.site_ui_polish import audit_site_ui_polish


def main() -> int:
    result = audit_site_ui_polish(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
