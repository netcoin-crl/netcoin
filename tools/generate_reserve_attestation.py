#!/usr/bin/env python3
"""Generate a NetCoin proof-of-reserves attestation from JSON inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_repo_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_ensure_repo_on_path()

from netcoin.exchange_reserves import reserve_attestation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("liabilities", help="JSON array of {customer_id, amount_sats, nonce}")
    parser.add_argument("reserves", help="JSON array of {address, amount_sats}")
    parser.add_argument("--operator", default="exchange")
    parser.add_argument("--out", default="dist/netcoin-reserve-attestation.json")
    args = parser.parse_args()
    liabilities = json.loads(Path(args.liabilities).read_text())
    reserves = json.loads(Path(args.reserves).read_text())
    payload = reserve_attestation(liabilities=liabilities, reserves=reserves, operator=args.operator)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "ok": True,
                "out": str(out),
                "solvent": payload["solvent"],
                "attestation_hash": payload["attestation_hash"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
