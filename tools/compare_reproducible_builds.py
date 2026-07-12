#!/usr/bin/env python3
"""Compare local and container reproducible-build archives."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_report(local_archive: Path, docker_archive: Path) -> dict[str, object]:
    local_hash = sha256(local_archive)
    docker_hash = sha256(docker_archive)
    return {
        "ok": local_hash == docker_hash,
        "schema": "netcoin-independent-repro-build-v1",
        "local_archive": str(local_archive),
        "docker_archive": str(docker_archive),
        "local_sha256": local_hash,
        "docker_sha256": docker_hash,
        "independent_builder": "github-actions-docker-buildkit",
        "does_not_claim": [
            "third-party maintainer rebuild",
            "hardware-isolated builder",
            "mainnet release ceremony completion",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare NetCoin reproducible-build archives")
    parser.add_argument("--local-archive", required=True, type=Path)
    parser.add_argument("--docker-archive", required=True, type=Path)
    parser.add_argument("--out", default="reports/m2_evidence/independent_repro_build.json", type=Path)
    args = parser.parse_args(argv)

    report = build_report(args.local_archive, args.docker_archive)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
