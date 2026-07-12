#!/usr/bin/env python3
"""Verify NetCoin release checksums and optional release signatures.

Usage:
  python tools/verify_release.py dist/
  python tools/verify_release.py dist/ --require-keyless \
    --certificate-identity https://github.com/OWNER/REPO/.github/workflows/release.yml@refs/tags/vX.Y.Z

The verifier is intentionally conservative: SHA256SUMS must match every listed
file. If SHA256SUMS.asc exists and gpg is installed, the detached signature is
verified too. Missing signatures are reported as unsigned rather than treated as
checksum failure so local/dev builds remain possible. Official GitHub releases
should also publish Sigstore keyless bundles and can require them with
``--require-keyless``.
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


def verify_keyless_signatures(
    dist: Path,
    verified_files: list[str],
    *,
    certificate_identity: str | None = None,
    certificate_oidc_issuer: str = "https://token.actions.githubusercontent.com",
    require: bool = False,
) -> list[str]:
    cosign = shutil.which("cosign")
    results: list[str] = []
    for name in verified_files + ["SHA256SUMS"]:
        artifact = dist / name
        bundle = dist / f"{name}.sigstore.json"
        if not bundle.exists():
            if require:
                raise FileNotFoundError(f"missing keyless signature bundle: {bundle.name}")
            results.append(f"{name}: unsigned keyless")
            continue
        if not cosign:
            if require:
                raise FileNotFoundError("cosign not found; cannot verify required keyless signatures")
            results.append(f"{name}: keyless bundle present but cosign not installed")
            continue
        if not certificate_identity:
            if require:
                raise ValueError("--certificate-identity is required for keyless verification")
            results.append(f"{name}: keyless bundle present; pass --certificate-identity to verify")
            continue
        cmd = [cosign, "verify-blob", str(artifact), "--bundle", str(bundle)]
        cmd.extend(["--certificate-identity", certificate_identity])
        if certificate_oidc_issuer:
            cmd.extend(["--certificate-oidc-issuer", certificate_oidc_issuer])
        subprocess.run(cmd, check=True)
        results.append(f"{name}: keyless signature verified")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify NetCoin release checksums and optional signature")
    parser.add_argument("dist", nargs="?", default="dist", help="release artifact directory")
    parser.add_argument(
        "--require-keyless",
        action="store_true",
        help="fail unless every checksum-listed artifact and SHA256SUMS have Sigstore bundles",
    )
    parser.add_argument("--certificate-identity", help="expected Sigstore certificate identity for keyless releases")
    parser.add_argument(
        "--certificate-oidc-issuer",
        default="https://token.actions.githubusercontent.com",
        help="expected Sigstore OIDC issuer",
    )
    args = parser.parse_args(argv)
    dist = Path(args.dist)
    try:
        verified = verify_checksums(dist)
        sig = verify_signature(dist)
        keyless = verify_keyless_signatures(
            dist,
            verified,
            certificate_identity=args.certificate_identity,
            certificate_oidc_issuer=args.certificate_oidc_issuer,
            require=args.require_keyless,
        )
    except Exception as exc:
        print(f"release verification failed: {exc}", file=sys.stderr)
        return 1
    print("checksums verified:", ", ".join(verified))
    print(sig)
    for line in keyless:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
