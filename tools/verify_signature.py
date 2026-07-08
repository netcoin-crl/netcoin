#!/usr/bin/env python3
"""Verify a NetCoin release signature sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.crypto import verify_message  # noqa: E402


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a NetCoin release signature")
    parser.add_argument("artifact")
    parser.add_argument("signature_json")
    args = parser.parse_args()
    artifact = Path(args.artifact)
    sig = json.loads(Path(args.signature_json).read_text())
    digest = file_sha256(artifact)
    if digest != sig.get("sha256"):
        print("sha256 mismatch", file=sys.stderr)
        return 2
    ok = verify_message(sig["address"], sig["message"], sig["signature"])
    if not ok:
        print("signature invalid", file=sys.stderr)
        return 3
    print(
        json.dumps({"ok": True, "artifact": artifact.name, "sha256": digest, "address": sig["address"]}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
