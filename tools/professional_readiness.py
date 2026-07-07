#!/usr/bin/env python3
"""Run NetCoin professional-readiness and issue checks."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.professional import issue_report, professional_readiness, protocol_test_vectors, write_release_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NetCoin professional-readiness checker")
    parser.add_argument("--root", default=str(ROOT), help="repository root")
    parser.add_argument("--vectors", action="store_true", help="print protocol test vectors instead of readiness")
    parser.add_argument("--manifest", help="write release manifest JSON to this path")
    parser.add_argument("--issues", action="store_true", help="print compact issue report")
    parser.add_argument("--fail-on-issues", action="store_true", help="exit non-zero if high-severity readiness checks are open")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if args.vectors:
        print(json.dumps(protocol_test_vectors(), indent=2, sort_keys=True))
        return 0
    if args.manifest:
        manifest = write_release_manifest(root, args.manifest)
        print(json.dumps({"ok": True, "manifest": args.manifest, "sha256": manifest["manifest_sha256"]}, indent=2, sort_keys=True))
        return 0
    payload = issue_report(root) if args.issues else professional_readiness(root)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if args.fail_on_issues and not payload.get("ok") else 0


if __name__ == "__main__":
    raise SystemExit(main())
