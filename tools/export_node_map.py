#!/usr/bin/env python3
"""Export a public M3 node-map payload from peer records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.addrv2 import AddrV2Record, public_node_map
from netcoin.peerdb import PeerDatabase


def load_records(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if "nodes" in data:
        return list(data["nodes"])
    if "addresses" in data:
        return list(data["addresses"])
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--peerdb", default="")
    parser.add_argument("--input", default="api/nodes/map")
    parser.add_argument("--out", default="api/nodes/map")
    args = parser.parse_args()
    if args.peerdb:
        db = PeerDatabase(ROOT / args.peerdb)
        from netcoin.pex import node_map_from_peer_database

        result = node_map_from_peer_database(db)
    else:
        records = [AddrV2Record.from_dict(item) for item in load_records(ROOT / args.input)]
        result = public_node_map(records)
        result["source"] = "static-export"
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
