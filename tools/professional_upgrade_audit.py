#!/usr/bin/env python3
from __future__ import annotations

# Allow `python tools/<script>.py` from the repository root or elsewhere.
import sys as _sys
from pathlib import Path as _Path

_repo_root = _Path(__file__).resolve().parents[1]
if str(_repo_root) not in _sys.path:
    _sys.path.insert(0, str(_repo_root))

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
