#!/usr/bin/env python3
"""Run the v0.34 real SQLite indexer integration smoke gate."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.indexer_db import run_indexer_db_smoke


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persist", default="", help="Optional SQLite file path to keep after the check")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.persist:
        result = run_indexer_db_smoke(args.persist)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_indexer_db_smoke(Path(tmp) / "indexer.sqlite3")
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
