#!/usr/bin/env python3
"""Explain active-chain cumulative work for operators."""

from __future__ import annotations

# Allow `python tools/<script>.py` from the repository root or elsewhere.
import sys as _sys
from pathlib import Path as _Path

_repo_root = _Path(__file__).resolve().parents[1]
if str(_repo_root) not in _sys.path:
    _sys.path.insert(0, str(_repo_root))

import argparse
import json
from pathlib import Path

from netcoin.block import Block
from netcoin.chain import Blockchain
from netcoin.consensus import audit_cumulative_work


def load_branch(path: str) -> list[Block]:
    data = json.loads(Path(path).read_text())
    blocks = data.get("blocks", data if isinstance(data, list) else [])
    return [Block.from_dict(b) for b in blocks]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=".netcoin")
    parser.add_argument("branches", nargs="*")
    args = parser.parse_args()
    chain = Blockchain(args.data)
    candidates = [load_branch(p) for p in args.branches]
    print(json.dumps(audit_cumulative_work(chain.chain, candidates), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
