#!/usr/bin/env python3
"""Verify NetCoin release checksums and, when available, the GPG signature.

Usage:
  python tools/verify_release.py dist/

The verifier is intentionally conservative: SHA256SUMS must match every listed
file. If SHA256SUMS.asc exists and gpg is installed, the detached signature is
verified too. Missing signatures are reported as unsigned rather than treated as
checksum failure so local/dev builds remain possible.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_sums(path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"invalid checksum line: {line!r}")
        digest, name = parts
        rows.append((digest.lower(), name.lstrip("*")))
    return rows


def verify_checksums(dist: Path) -> list[str]:
    sums = dist / "SHA256SUMS"
    if not sums.exists():
        raise FileNotFoundError(f"missing {sums}")
    verified: list[str] = []
    for expected, name in parse_sums(sums):
        target = dist / name
        if not target.exists():
            raise FileNotFoundError(f"checksum target missing: {target}")
        actual = sha256_file(target)
        if actual != expected:
            raise ValueError(f"checksum mismatch for {name}: expected {expected}, got {actual}")
        verified.append(name)
    return verified


def verify_signature(dist: Path) -> str:
    asc = dist / "SHA256SUMS.asc"
    sums = dist / "SHA256SUMS"
    if not asc.exists():
        return "unsigned: SHA256SUMS.asc not present"
    gpg = shutil.which("gpg")
    if not gpg:
        return "signature present but not checked: gpg not installed"
    subprocess.run([gpg, "--verify", str(asc), str(sums)], check=True)
    return "signature verified"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify NetCoin release checksums and optional signature")
    parser.add_argument("dist", nargs="?", default="dist", help="release artifact directory")
    args = parser.parse_args(argv)
    dist = Path(args.dist)
    try:
        verified = verify_checksums(dist)
        sig = verify_signature(dist)
    except Exception as exc:  # noqa: BLE001 - command-line tool wants concise failure
        print(f"release verification failed: {exc}", file=sys.stderr)
        return 1
    print("checksums verified:", ", ".join(verified))
    print(sig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
