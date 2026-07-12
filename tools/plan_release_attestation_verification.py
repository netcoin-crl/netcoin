#!/usr/bin/env python3
"""Print GitHub artifact-attestation verification commands for a release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def attested_subjects(dist: Path) -> list[Path]:
    subjects = sorted(dist.glob("netcoin-*.zip"))
    for name in ["netcoin-sbom.json", "SHA256SUMS"]:
        path = dist / name
        if path.exists():
            subjects.append(path)
    return subjects


def plan(dist: Path, repository: str) -> dict[str, object]:
    subjects = attested_subjects(dist)
    return {
        "ok": bool(subjects),
        "schema": "netcoin-release-attestation-verification-plan-v1",
        "repository": repository,
        "subjects": [str(path) for path in subjects],
        "commands": [f"gh attestation verify {path} -R {repository}" for path in subjects],
        "does_not_verify_offline": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan GitHub artifact-attestation verification commands")
    parser.add_argument("dist", nargs="?", default="dist", type=Path)
    parser.add_argument(
        "--repository",
        required=True,
        help="OWNER/REPO that owns the GitHub release workflow",
    )
    parser.add_argument("--json", action="store_true", help="print the full JSON plan")
    args = parser.parse_args(argv)

    payload = plan(args.dist, args.repository)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for command in payload["commands"]:
            print(command)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
