#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.professional_upgrade import validate_upgrade_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate NetCoin professional-upgrade workstream anchors")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out")
    parser.add_argument("--fail-on-issues", action="store_true")
    args = parser.parse_args()
    report = validate_upgrade_manifest(args.root)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n")
    else:
        print(text)
    return 1 if args.fail_on_issues and not report["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
