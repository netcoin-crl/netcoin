#!/usr/bin/env python3
"""Generate a small repository SBOM/provenance inventory for NetCoin releases.

This is intentionally dependency-light so it can run in CI before packaging. It
records Python project metadata plus SHA-256 hashes for source, docs, ops, and
site files that ship in the source release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

INCLUDE_DIRS = ("netcoin", "tools", "docs", "sites", "sdk", "bots", "exchange", "ops", "config")
INCLUDE_FILES = ("README.md", "pyproject.toml", "Dockerfile", "docker-compose.yml", "LICENSE", "SECURITY.md")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_release_files(root: Path) -> Iterable[Path]:
    for name in INCLUDE_FILES:
        p = root / name
        if p.exists() and p.is_file():
            yield p
    for d in INCLUDE_DIRS:
        base = root / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith((".pyc", ".sqlite3")):
                yield p


def build_sbom(root: Path) -> dict:
    files = []
    for p in sorted(set(iter_release_files(root))):
        files.append({"path": str(p.relative_to(root)), "sha256": sha256(p), "bytes": p.stat().st_size})
    version = "unknown"
    params = root / "netcoin" / "params.py"
    if params.exists():
        for line in params.read_text().splitlines():
            if line.startswith("NODE_VERSION"):
                version = line.split("=", 1)[1].strip().strip('"')
                break
    return {
        "schema": "netcoin-source-sbom-v1",
        "name": "netcoin",
        "version": version,
        "file_count": len(files),
        "files": files,
        "production_ready": False,
        "note": "SBOM/provenance inventory for source-release verification; not an audit statement.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate NetCoin source SBOM")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="dist/netcoin-sbom.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    sbom = build_sbom(root)
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"out": str(out), "file_count": sbom["file_count"], "version": sbom["version"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
