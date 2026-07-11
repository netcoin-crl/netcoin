#!/usr/bin/env python3
"""Validate the Phase 1 proof triage manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.proof_triage import load_proof_triage_manifest, validate_proof_triage_manifest  # noqa: E402


def main() -> int:
    manifest = load_proof_triage_manifest()
    issues = validate_proof_triage_manifest(manifest, root=ROOT)
    result = {
        "ok": not issues,
        "version": manifest.get("version"),
        "phase": manifest.get("phase"),
        "issue_count": len(issues),
        "issues": issues,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
