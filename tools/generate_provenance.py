#!/usr/bin/env python3
"""Generate lightweight release provenance metadata for NetCoin artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_value(args: list[str], default: str = "") -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return default


def build_provenance(artifact: Path, *, builder: str = "local", source_ref: str = "") -> dict[str, object]:
    artifact = artifact.resolve()
    return {
        "provenance_type": "netcoin-release-provenance-v1",
        "created_at": int(time.time()),
        "artifact": artifact.name,
        "artifact_path": str(artifact),
        "sha256": sha256_file(artifact),
        "size_bytes": artifact.stat().st_size,
        "builder": builder,
        "source_ref": source_ref or git_value(["rev-parse", "HEAD"], "unknown"),
        "source_dirty": bool(git_value(["status", "--porcelain"], "")),
        "python_version": sys.version.split()[0],
        "environment": {
            "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "github_repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "github_ref": os.environ.get("GITHUB_REF", ""),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate NetCoin release provenance JSON")
    parser.add_argument("artifact")
    parser.add_argument("--out", default="")
    parser.add_argument("--builder", default=(os.environ.get("GITHUB_ACTIONS") and "github-actions") or "local")
    parser.add_argument("--source-ref", default="")
    args = parser.parse_args()
    artifact = Path(args.artifact)
    payload = build_provenance(artifact, builder=args.builder, source_ref=args.source_ref)
    out = Path(args.out) if args.out else artifact.with_suffix(artifact.suffix + ".provenance.json")
    out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
