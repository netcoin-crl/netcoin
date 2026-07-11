#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.mainnet_readiness import load_manifest, validate_manifest


def main() -> int:
    manifest = load_manifest()
    issues = validate_manifest(manifest)
    result = {
        "ok": not issues,
        "version": manifest.get("version"),
        "phase": manifest.get("phase"),
        "gate_count": len(manifest.get("gates", [])),
        "issues": issues,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
