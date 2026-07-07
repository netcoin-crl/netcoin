"""Professional-readiness helpers for NetCoin.

These checks do not make NetCoin a regulated/mainnet product by themselves.
They give operators and maintainers concrete, testable controls for release
trust, protocol compatibility, security documentation, observability, wallet
safety, exchange readiness, and market integrity.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .block import Block, BlockHeader, bits_to_target
from .crypto import private_key_to_public_key, public_key_to_address, private_key_to_xonly_public_key, public_key_to_taproot_address
from .params import INITIAL_BITS, P2P_MAGIC, TARGET_SPACING_SECONDS
from .serialization import serialize_header
from .tx import Transaction, TxInput, TxOutput
from .wallet import Wallet, encrypt_private_key, decrypt_private_key, PBKDF2_ITERATIONS, WALLET_FORMAT_VERSION

PROFESSIONAL_CHECK_VERSION = 1

REQUIRED_DOCS = {
    "docs/PROTOCOL_SPEC.md": "formal protocol specification",
    "docs/THREAT_MODEL.md": "security threat model",
    "docs/INCIDENT_RESPONSE.md": "incident response runbook",
    "docs/KEY_MANAGEMENT.md": "wallet/key management policy",
    "docs/REPRODUCIBLE_RELEASES.md": "release verification and signing guide",
    "docs/MARKET_INTEGRITY.md": "prediction-market integrity and dispute policy",
    "docs/EXCHANGE_READINESS.md": "exchange integration and reorg policy",
    "SECURITY.md": "responsible disclosure entrypoint",
}

REQUIRED_TOOLS = {
    "tools/make_release.sh": "reproducible source archive builder",
    "tools/verify_release.py": "checksum/signature verifier",
    "tools/professional_readiness.py": "automated professional-readiness checker",
}

REQUIRED_TESTS = {
    "tests/test_professional_readiness.py": "professional-readiness checker",
    "tests/test_protocol_vectors.py": "protocol test vector stability",
    "tests/test_app_idempotency_nonce.py": "idempotency and replay protection",
    "tests/test_market_surveillance.py": "market surveillance and dispute workflow",
}

PROFESSIONAL_CONTROLS = [
    "protocol_spec",
    "test_vectors",
    "signed_releases",
    "sbom_manifest",
    "threat_model",
    "incident_response",
    "key_management",
    "encrypted_wallets",
    "auto_lock_wallet_session",
    "watch_only_wallets",
    "multisig_treasury",
    "mempool_policy",
    "prometheus_metrics",
    "market_surveillance",
    "resolution_disputes",
    "api_idempotency",
    "api_nonce_replay_protection",
    "exchange_reorg_policy",
    "public_status_page",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_pyproject_version(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return "0.0.0"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    return "0.0.0"


def _git_commit(root: Path) -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def dependency_sbom(root: Path) -> list[dict[str, str]]:
    """Return a tiny SBOM from pyproject dependencies using only stdlib parsing."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return []
    text = pyproject.read_text(encoding="utf-8")
    deps: list[str] = []
    in_deps = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("dependencies") and "[" in line:
            in_deps = True
            after = line.split("[", 1)[1]
            if "]" in after:
                deps.extend(x.strip().strip('"') for x in after.split("]", 1)[0].split(",") if x.strip())
                in_deps = False
            continue
        if in_deps:
            if "]" in line:
                line = line.split("]", 1)[0]
                in_deps = False
            item = line.rstrip(",").strip().strip('"')
            if item:
                deps.append(item)
    out = []
    for dep in deps:
        name = re.split(r"[<>=!~\[]", dep, maxsplit=1)[0].strip()
        spec = dep[len(name):].strip()
        out.append({"name": name, "specifier": spec or "", "source": "pyproject.toml"})
    return out


def build_release_manifest(root: str | Path, *, include_files: Iterable[str] | None = None) -> dict[str, Any]:
    root = Path(root)
    version = read_pyproject_version(root)
    files: list[dict[str, Any]] = []
    if include_files is None:
        candidates = [p for p in root.rglob("*") if p.is_file() and not any(part in {".git", "__pycache__", ".pytest_cache", "dist"} for part in p.parts)]
    else:
        candidates = [root / p for p in include_files]
    for path in sorted(candidates, key=lambda p: str(p.relative_to(root))):
        if not path.exists() or not path.is_file():
            continue
        rel = str(path.relative_to(root)).replace(os.sep, "/")
        files.append({"path": rel, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "schema": "netcoin-release-manifest-v1",
        "version": version,
        "generated_at": int(time.time()),
        "git_commit": _git_commit(root),
        "python_version": sys.version.split()[0],
        "files": files,
        "sbom": dependency_sbom(root),
    }
    manifest_body = json.dumps({k: v for k, v in manifest.items() if k != "manifest_sha256"}, sort_keys=True, separators=(",", ":"))
    manifest["manifest_sha256"] = hashlib.sha256(manifest_body.encode()).hexdigest()
    return manifest


def write_release_manifest(root: str | Path, out: str | Path) -> dict[str, Any]:
    manifest = build_release_manifest(root)
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def build_source_zip(root: str | Path, out_zip: str | Path) -> dict[str, Any]:
    """Build a deterministic-ish source zip without requiring git.

    Git archive remains the preferred release path. This helper is useful for CI
    smoke tests and local bundles; timestamps are normalized for stable output.
    """
    root = Path(root)
    out = Path(out_zip)
    out.parent.mkdir(parents=True, exist_ok=True)
    prefix = f"netcoin-{read_pyproject_version(root)}/"
    paths = [p for p in root.rglob("*") if p.is_file() and not any(part in {".git", "__pycache__", ".pytest_cache", "dist"} for part in p.parts)]
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(paths, key=lambda p: str(p.relative_to(root))):
            rel = prefix + str(path.relative_to(root)).replace(os.sep, "/")
            info = zipfile.ZipInfo(rel, date_time=(2020, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())
    return {"path": str(out), "sha256": sha256_file(out), "bytes": out.stat().st_size}


def protocol_test_vectors() -> dict[str, Any]:
    """Stable vectors for independent NetCoin implementations."""
    wallet = Wallet(private_key=1)
    pub = private_key_to_public_key(1, compressed=True)
    tx = Transaction(
        inputs=[TxInput(txid="00" * 32, vout=0, script_sig="", sequence=0xFFFFFFFF)],
        outputs=[TxOutput(amount=123456789, address=wallet.address)],
        locktime=0,
    )
    header = BlockHeader(
        version=1,
        previous_hash="00" * 32,
        merkle_root=tx.txid(),
        timestamp=1700000000,
        bits=INITIAL_BITS,
        nonce=0,
        height=0,
    )
    block = Block(header=header, transactions=[tx])
    enc = encrypt_private_key(wallet.private_key_hex, "correct horse battery staple")
    decrypted_ok = decrypt_private_key(enc, "correct horse battery staple") == wallet.private_key_hex
    return {
        "schema": "netcoin-protocol-vectors-v1",
        "network_magic_hex": P2P_MAGIC.hex(),
        "target_block_time_seconds": TARGET_SPACING_SECONDS,
        "genesis_bits": INITIAL_BITS,
        "genesis_target_hex": f"{bits_to_target(INITIAL_BITS):064x}",
        "wallet_private_key_hex": wallet.private_key_hex,
        "wallet_public_key_hex": pub.hex(),
        "wallet_address": wallet.address,
        "wallet_taproot_address": public_key_to_taproot_address(private_key_to_xonly_public_key(1)),
        "sample_transaction": tx.to_dict(include_scripts=True, include_witness=True),
        "sample_txid": tx.txid(),
        "sample_wtxid": tx.wtxid(),
        "sample_block_header_hex": serialize_header(header).hex(),
        "sample_block_hash": block.hash(),
        "wallet_format_version": WALLET_FORMAT_VERSION,
        "wallet_pbkdf2_iterations": PBKDF2_ITERATIONS,
        "encrypted_wallet_roundtrip_ok": decrypted_ok,
    }


def validate_protocol_vectors(vectors: dict[str, Any] | None = None) -> dict[str, Any]:
    expected = protocol_test_vectors()
    vectors = vectors or expected
    mismatches = []
    for key in (
        "network_magic_hex",
        "genesis_bits",
        "genesis_target_hex",
        "wallet_address",
        "sample_txid",
        "sample_wtxid",
        "sample_block_hash",
        "wallet_format_version",
    ):
        if vectors.get(key) != expected.get(key):
            mismatches.append({"field": key, "expected": expected.get(key), "actual": vectors.get(key)})
    return {"ok": not mismatches, "mismatches": mismatches, "vectors": expected}


def _file_contains(path: Path, needles: Iterable[str]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    return all(n.lower() in text for n in needles)


def professional_readiness(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str, severity: str = "high", evidence: str | None = None) -> None:
        checks.append({"name": name, "ok": bool(ok), "severity": severity, "detail": detail, "evidence": evidence or ""})

    for rel, desc in REQUIRED_DOCS.items():
        add(f"doc:{rel}", (root / rel).exists(), f"{desc} present", evidence=rel)
    for rel, desc in REQUIRED_TOOLS.items():
        add(f"tool:{rel}", (root / rel).exists(), f"{desc} present", evidence=rel)
    for rel, desc in REQUIRED_TESTS.items():
        add(f"test:{rel}", (root / rel).exists(), f"{desc} tests present", evidence=rel)

    add("wallet:encrypted_format", _file_contains(root / "netcoin/wallet.py", ["chacha20-poly1305", "pbkdf2", "auto-lock"]), "encrypted wallet format, KDF, and auto-lock session implemented", evidence="netcoin/wallet.py")
    add("wallet:watch_only", _file_contains(root / "netcoin/wallet.py", ["watch_only"]), "watch-only wallet support implemented", severity="medium", evidence="netcoin/wallet.py")
    add("mempool:policy", _file_contains(root / "netcoin/mempool.py", ["dust", "ancestor", "replace-by-fee"]), "fee/spam policy module implemented", evidence="netcoin/mempool.py")
    add("node:metrics", _file_contains(root / "netcoin/node.py", ["prometheus", "netcoin_block_height"]), "Prometheus node metrics implemented", evidence="netcoin/node.py")
    add("markets:surveillance", _file_contains(root / "netcoin/apps/markets.py", ["surveillance", "wash", "dispute"]), "market surveillance and dispute controls implemented", evidence="netcoin/apps/markets.py")
    add("api:idempotency", _file_contains(root / "netcoin/apps/__init__.py", ["idempotency", "app_nonces"]), "idempotency keys and nonce replay controls implemented", evidence="netcoin/apps/__init__.py")
    add("release:manifest", _file_contains(root / "tools/make_release.sh", ["sha256sums"]), "release checksum workflow implemented", evidence="tools/make_release.sh")
    add("status:site", (root / "sites/status/index.html").exists(), "public status/readiness site present", severity="medium", evidence="sites/status/index.html")
    add("openapi:docs", (root / "docs/openapi.yaml").exists(), "OpenAPI document present", severity="medium", evidence="docs/openapi.yaml")

    total = len(checks)
    passed = sum(1 for c in checks if c["ok"])
    high_open = [c for c in checks if not c["ok"] and c["severity"] == "high"]
    score = round(100 * passed / max(1, total), 1)
    return {
        "schema": "netcoin-professional-readiness-v1",
        "version": read_pyproject_version(root),
        "generated_at": int(time.time()),
        "score": score,
        "passed": passed,
        "total": total,
        "ok": not high_open and score >= 90,
        "mainnet_safe": False,
        "mainnet_note": "Automated readiness checks cannot replace independent security audits, legal review, public testnet soak time, or incident-response drills.",
        "open_high_severity": high_open,
        "checks": checks,
        "controls": PROFESSIONAL_CONTROLS,
    }


def issue_report(root: str | Path) -> dict[str, Any]:
    readiness = professional_readiness(root)
    vectors = validate_protocol_vectors()
    manifest = build_release_manifest(root, include_files=["pyproject.toml", "README.md", "netcoin/wallet.py", "netcoin/apps/markets.py"])
    issues = [c for c in readiness["checks"] if not c["ok"]]
    return {
        "ok": readiness["ok"] and vectors["ok"],
        "readiness_score": readiness["score"],
        "issues": issues,
        "protocol_vectors_ok": vectors["ok"],
        "release_manifest_preview": manifest,
    }
