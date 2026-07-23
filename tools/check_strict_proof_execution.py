#!/usr/bin/env python3
"""Validate the Phase 1 strict proof execution playbook."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.strict_proof_execution import (
    load_strict_proof_manifest,
    strict_command_summary,
    validate_strict_proof_manifest,
)


def main() -> int:
    manifest = load_strict_proof_manifest()
    issues = validate_strict_proof_manifest(manifest)
    payload = {"ok": not issues, "issues": issues, **strict_command_summary(manifest)}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
