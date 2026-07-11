#!/usr/bin/env python3
"""Validate the v0.39.3 local proof runner manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.local_proof_runner import load_local_proof_manifest, validate_local_proof_manifest  # noqa: E402


def main() -> int:
    manifest = load_local_proof_manifest()
    issues = validate_local_proof_manifest(manifest, root=ROOT)
    result = {"ok": not issues, "version": manifest.get("version"), "phase": manifest.get("phase"), "issues": issues}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
