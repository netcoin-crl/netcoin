#!/usr/bin/env python3
"""Recreate and print deterministic NetCoin genesis parameters."""

from __future__ import annotations

# Allow `python tools/<script>.py` from the repository root or elsewhere.
import sys as _sys
from pathlib import Path as _Path

_repo_root = _Path(__file__).resolve().parents[1]
if str(_repo_root) not in _sys.path:
    _sys.path.insert(0, str(_repo_root))

import argparse
import json

from netcoin.chain import create_genesis_block
from netcoin.params import GENESIS_MESSAGE, GENESIS_TIMESTAMP, INITIAL_BITS


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args()
    block = create_genesis_block()
    payload = {
        "genesis_hash": block.hash(),
        "height": block.header.height,
        "previous_hash": block.header.previous_hash,
        "merkle_root": block.header.merkle_root,
        "timestamp": GENESIS_TIMESTAMP,
        "bits": INITIAL_BITS,
        "message": GENESIS_MESSAGE,
        "block": block.to_dict(),
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
