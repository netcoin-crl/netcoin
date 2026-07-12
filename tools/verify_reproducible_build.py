#!/usr/bin/env python3
"""Create and verify a normalized source archive for reproducibility checks."""

from __future__ import annotations

import argparse
import hashlib
import gzip
import io
import json
import os
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ["netcoin", "tools", "docs", "sites", "architecture", "api", "README.md", "LICENSE", "pyproject.toml"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: Path):
    for item in INCLUDE:
        p = root / item
        if not p.exists():
            continue
        if p.is_file():
            yield p
        else:
            for child in sorted(p.rglob("*")):
                if (
                    child.is_file()
                    and "__pycache__" not in child.parts
                    and not child.name.endswith((".pyc", ".sqlite3"))
                ):
                    yield child


def create_archive(root: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as tf:
        for path in iter_files(root):
            info = tf.gettarinfo(str(path), arcname=str(path.relative_to(root)))
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = int(os.environ.get("SOURCE_DATE_EPOCH", "1704067200"))
            with path.open("rb") as fh:
                tf.addfile(info, fh)
    with out.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write(tar_buffer.getvalue())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/reproducible_build_source_report.json")
    parser.add_argument("--archive", default="dist/netcoin-source-repro.tar.gz")
    args = parser.parse_args()
    archive = ROOT / args.archive
    create_archive(ROOT, archive)
    with tempfile.TemporaryDirectory() as tmp:
        second = Path(tmp) / "netcoin-source-repro.tar.gz"
        create_archive(ROOT, second)
        first_hash = sha256(archive)
        second_hash = sha256(second)
    result = {
        "ok": first_hash == second_hash,
        "schema": "netcoin-reproducible-build-source-v1",
        "archive": str(archive.relative_to(ROOT)),
        "sha256": first_hash,
        "second_sha256": second_hash,
        "independent_builder_required_for_strict_m2": True,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
