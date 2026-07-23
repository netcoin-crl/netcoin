#!/usr/bin/env python3
"""Print the Phase 1 local strict-proof plan for a target profile."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.strict_proof_execution import load_strict_proof_manifest, validate_strict_proof_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Print NetCoin strict proof commands")
    parser.add_argument("--profile", default="macos", choices=["macos", "linux", "sandbox"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest = load_strict_proof_manifest()
    issues = validate_strict_proof_manifest(manifest)
    if issues:
        print(json.dumps({"ok": False, "issues": issues}, indent=2))
        return 1

    profile = manifest["local_profiles"][args.profile]
    payload = {
        "ok": True,
        "version": manifest.get("version"),
        "profile": args.profile,
        "setup_commands": profile.get("setup_commands", []),
        "strict_command": profile.get("strict_command"),
        "strict_command_groups": manifest.get("strict_command_groups", []),
        "claim": profile.get("claim", "strict professional-candidate proof only if all gates pass"),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"NetCoin {payload['version']} strict proof plan ({args.profile})")
    print("\nSetup commands:")
    for command in payload["setup_commands"]:
        print(f"  {command}")

    print("\nStrict proof groups:")
    for group in payload["strict_command_groups"]:
        print(f"\n[{group['id']}]")
        for command in group.get("commands", []):
            print(f"  {command}")
        print("  evidence: " + ", ".join(group.get("evidence", [])))

    print("\nOne-command scorecard:")
    print(f"  {payload['strict_command']}")
    print(f"\nClaim: {payload['claim']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
