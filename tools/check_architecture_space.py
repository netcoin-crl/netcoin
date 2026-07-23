#!/usr/bin/env python3
"""Verify NetCoin's professional hybrid architecture spaces exist."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.architecture import architecture_status, architecture_summary


def main() -> int:
    status = architecture_status(ROOT)
    summary = architecture_summary(ROOT)
    result = {
        "ok": status["ok"],
        "version": summary["version"],
        "target": summary["final_version_target"],
        "space_count": len(status["spaces"]),
        "missing": status["missing"],
        "spaces": status["spaces"],
    }
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
