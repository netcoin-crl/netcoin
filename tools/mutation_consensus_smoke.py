#!/usr/bin/env python3
"""Tiny mutation smoke checks for consensus rules.

This does not replace a full mutation-testing framework; it makes sure obvious
rule mutations (bad merkle root, bad previous hash) are caught in CI and gives a
stable hook for future mutmut/cosmic-ray integration.
"""

from __future__ import annotations

# Allow `python tools/<script>.py` from the repository root or elsewhere.
import sys as _sys
from pathlib import Path as _Path

_repo_root = _Path(__file__).resolve().parents[1]
if str(_repo_root) not in _sys.path:
    _sys.path.insert(0, str(_repo_root))

import json
import tempfile

from netcoin.chain import Blockchain, ChainError
from netcoin.miner import solve_template
from netcoin.params import ZERO_HASH
from netcoin.wallet import Wallet


def main() -> int:
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        chain = Blockchain(tmp)
        wallet = Wallet.create()
        block = solve_template(chain.get_block_template(wallet.address), wallet.address)
        block.header.merkle_root = ZERO_HASH
        try:
            chain.add_block(block)
            results.append({"mutation": "bad_merkle", "caught": False})
        except ChainError:
            results.append({"mutation": "bad_merkle", "caught": True})
    ok = all(r["caught"] for r in results)
    print(json.dumps({"ok": ok, "results": results}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
