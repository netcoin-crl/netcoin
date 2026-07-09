#!/usr/bin/env python3
"""Verify lightweight NetCoin release provenance metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify NetCoin provenance JSON against an artifact")
    parser.add_argument("artifact")
    parser.add_argument("provenance_json")
    args = parser.parse_args()
    artifact = Path(args.artifact)
    prov = json.loads(Path(args.provenance_json).read_text())
    errors = []
    if prov.get("provenance_type") != "netcoin-release-provenance-v1":
        errors.append("unexpected provenance_type")
    if prov.get("artifact") != artifact.name:
        errors.append("artifact name mismatch")
    if prov.get("sha256") != sha256_file(artifact):
        errors.append("sha256 mismatch")
    if int(prov.get("size_bytes", -1)) != artifact.stat().st_size:
        errors.append("size_bytes mismatch")
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, sort_keys=True))
        return 2
    print(json.dumps({"ok": True, "artifact": artifact.name, "sha256": prov.get("sha256")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
