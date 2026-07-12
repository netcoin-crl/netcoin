#!/usr/bin/env python3
"""Generate a minimal SLSA-style provenance statement for a release subject."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", default="dist/netcoin-sbom.json")
    parser.add_argument("--out", default="dist/netcoin-slsa-provenance.json")
    args = parser.parse_args()
    subject = ROOT / args.subject
    if not subject.exists():
        raise SystemExit(f"missing subject: {subject}")
    payload = {
        "_type": "https://in-toto.io/Statement/v1",
        "predicateType": "https://slsa.dev/provenance/v1",
        "subject": [
            {
                "name": str(subject.relative_to(ROOT)),
                "digest": {"sha256": sha256(subject)},
            }
        ],
        "predicate": {
            "buildDefinition": {
                "buildType": "https://netcoin.online/build/source-release/v1",
                "externalParameters": {
                    "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH", "1704067200"),
                },
                "internalParameters": {},
            },
            "runDetails": {
                "builder": {"id": "netcoin-local-source-builder"},
                "metadata": {"startedOn": int(time.time()), "finishedOn": int(time.time())},
            },
        },
        "strict_m2_note": "SLSA-3 requires hosted builder controls and independent verification; this is source provenance scaffolding.",
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"ok": True, "out": str(out.relative_to(ROOT)), "subject": str(subject.relative_to(ROOT))}, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
