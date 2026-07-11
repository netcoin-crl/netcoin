#!/usr/bin/env python3
"""Validate the Phase 1 proof-hardening manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.proof_hardening import load_proof_manifest, validate_proof_manifest  # noqa: E402


def main() -> int:
    manifest = load_proof_manifest()
    issues = validate_proof_manifest(manifest)
    result = {
        "ok": not issues,
        "version": manifest.get("version"),
        "phase": manifest.get("phase"),
        "gate_count": len(manifest.get("gate_groups", [])),
        "issues": issues,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
