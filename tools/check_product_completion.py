#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.product_completion import load_product_completion_manifest, summarize_product_completion, validate_product_completion

def main() -> int:
    manifest = load_product_completion_manifest()
    issues = validate_product_completion(manifest)
    summary = summarize_product_completion(manifest, issues).to_dict()
    summary["issues"] = issues
    print(json.dumps(summary, indent=2))
    return 1 if issues else 0

if __name__ == "__main__":
    raise SystemExit(main())
