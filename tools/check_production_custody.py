#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.custody_production import source_custody_smoke, strict_custody_evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--evidence", default="reports/mainnet_evidence/production_custody_evidence.json")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.strict:
        result = strict_custody_evidence(
            ROOT / args.evidence if not Path(args.evidence).is_absolute() else args.evidence
        )
    else:
        with tempfile.TemporaryDirectory() as tmp:
            result = source_custody_smoke(Path(tmp) / "custody-smoke.sqlite")
            result["gate_id"] = "production-exchange-custody"
            result["status"] = "source-complete-evidence-required"
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
