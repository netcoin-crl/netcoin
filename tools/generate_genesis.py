#!/usr/bin/env python3
"""Mine a deterministic regtest/testnet-rehearsal genesis block from a manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.block import (
    Block,
    BlockError,
    BlockHeader,
    bits_to_target,
    check_proof_of_work,
    merkle_root,
    mine_header,
)
from netcoin.params import INITIAL_BITS, MAX_MONEY, ZERO_HASH
from netcoin.tx import Transaction, TxInput, TxOutput

GENESIS_REHEARSAL_SCHEMA = "netcoin-genesis-rehearsal-manifest-v1"
GENESIS_REHEARSAL_REPORT_SCHEMA = "netcoin-genesis-rehearsal-report-v1"
ALLOWED_NETWORKS = {"regtest", "testnet-rehearsal"}
REFUSED_NETWORKS = {"main", "mainnet", "mainnet-dry-run"}


class GenesisRehearsalError(ValueError):
    """Raised when a genesis rehearsal manifest or request is unsafe."""


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def manifest_hash(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()


def load_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _to_int(value: Any, field: str, issues: list[str]) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        issues.append(f"{field} must be an integer")
        return 0


def validate_manifest(manifest: dict[str, Any], *, requested_network: str) -> dict[str, Any]:
    issues: list[str] = []
    network = str(requested_network).strip().lower()
    manifest_network = str(manifest.get("network", "")).strip().lower()

    if network in REFUSED_NETWORKS or manifest_network in REFUSED_NETWORKS:
        issues.append("genesis rehearsal hard-refuses mainnet")
    if network not in ALLOWED_NETWORKS:
        issues.append(f"network must be one of {sorted(ALLOWED_NETWORKS)}")
    if manifest_network != network:
        issues.append("manifest network must match requested network")
    if manifest.get("schema") != GENESIS_REHEARSAL_SCHEMA:
        issues.append(f"schema must be {GENESIS_REHEARSAL_SCHEMA}")
    if manifest.get("status") != "rehearsal":
        issues.append("status must be rehearsal")
    height = _to_int(manifest.get("height", -1), "height", issues)
    if height != 0:
        issues.append("height must be 0")
    version = _to_int(manifest.get("version", 0), "version", issues)
    if version <= 0:
        issues.append("version must be positive")
    if str(manifest.get("previous_hash", "")).lower() != ZERO_HASH:
        issues.append("previous_hash must be the zero hash")
    timestamp = _to_int(manifest.get("timestamp"), "timestamp", issues)
    if timestamp <= 0:
        issues.append("timestamp must be positive")
    bits = _to_int(manifest.get("bits", INITIAL_BITS), "bits", issues)
    if bits <= 0:
        issues.append("bits must be positive")
    else:
        try:
            bits_to_target(bits)
        except BlockError as exc:
            issues.append(f"bits are invalid: {exc}")
    if not str(manifest.get("coinbase_message", "")).strip():
        issues.append("coinbase_message is required")

    outputs = manifest.get("outputs", [])
    if not isinstance(outputs, list):
        issues.append("outputs must be a list")
        outputs = []
    total = 0
    names: set[str] = set()
    for index, output in enumerate(outputs):
        if not isinstance(output, dict):
            issues.append(f"outputs[{index}] must be an object")
            continue
        name = str(output.get("name", "")).strip()
        if not name:
            issues.append(f"outputs[{index}].name is required")
        if name in names:
            issues.append(f"duplicate output name: {name}")
        names.add(name)
        amount = _to_int(output.get("amount"), f"outputs[{index}].amount", issues)
        if amount < 0:
            issues.append(f"outputs[{index}].amount must be non-negative")
        if amount > 0 and not output.get("address") and not output.get("script_pubkey"):
            issues.append(f"outputs[{index}] requires address or script_pubkey for positive amount")
        total += max(0, amount)
    if total > MAX_MONEY:
        issues.append("outputs exceed MAX_MONEY")

    ceremony = manifest.get("ceremony", {})
    if not isinstance(ceremony, dict):
        issues.append("ceremony must be an object")
    elif not ceremony.get("requires_nip_before_activation"):
        issues.append("ceremony.requires_nip_before_activation must be true")

    return {
        "schema": "netcoin-genesis-rehearsal-manifest-validation-v1",
        "ok": not issues,
        "network": network,
        "issues": issues,
        "manifest_hash": manifest_hash(manifest),
        "output_count": len(outputs),
        "output_total": total,
        "mainnet_wired": False,
        "consensus_integrated": False,
    }


def build_genesis_block(manifest: dict[str, Any], *, requested_network: str) -> Block:
    validation = validate_manifest(manifest, requested_network=requested_network)
    if not validation["ok"]:
        raise GenesisRehearsalError("; ".join(str(issue) for issue in validation["issues"]))

    outputs = [
        TxOutput(
            amount=int(output["amount"]),
            address=str(output.get("address", "")),
            script_pubkey=str(output.get("script_pubkey", "")),
        )
        for output in manifest.get("outputs", [])
        if int(output.get("amount", 0)) >= 0
    ]
    coinbase = Transaction(
        inputs=[TxInput(txid=ZERO_HASH, vout=-1, coinbase=str(manifest["coinbase_message"]))],
        outputs=outputs,
    )
    header = BlockHeader(
        version=int(manifest["version"]),
        previous_hash=ZERO_HASH,
        merkle_root=merkle_root([coinbase]),
        timestamp=int(manifest["timestamp"]),
        bits=int(manifest["bits"]),
        nonce=0,
        height=0,
    )
    return Block(header=mine_header(header), transactions=[coinbase])


def generate_report(manifest: dict[str, Any], *, requested_network: str) -> dict[str, Any]:
    started = time.time()
    validation = validate_manifest(manifest, requested_network=requested_network)
    if not validation["ok"]:
        return {
            "schema": GENESIS_REHEARSAL_REPORT_SCHEMA,
            "ok": False,
            "network": requested_network,
            "validation": validation,
            "issues": validation["issues"],
            "consensus_integrated": False,
            "mainnet_wired": False,
            "requires_nip_before_activation": True,
        }
    block = build_genesis_block(manifest, requested_network=requested_network)
    return {
        "schema": GENESIS_REHEARSAL_REPORT_SCHEMA,
        "ok": check_proof_of_work(block.header),
        "network": requested_network,
        "duration_seconds": round(time.time() - started, 3),
        "validation": validation,
        "manifest_hash": validation["manifest_hash"],
        "block_hash": block.hash(),
        "header": block.header.to_dict(),
        "header_raw_hex": block.header.raw_hex(),
        "block_raw_hex": block.raw_hex(),
        "block": block.to_dict(),
        "consensus_integrated": False,
        "mainnet_wired": False,
        "writes_runtime_params": False,
        "requires_nip_before_activation": True,
        "does_not_claim": [
            "mainnet genesis approval",
            "mainnet activation",
            "runtime params update",
            "consensus vector update",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a regtest/testnet-rehearsal genesis report")
    parser.add_argument("--network", required=True, help="regtest or testnet-rehearsal; mainnet is refused")
    parser.add_argument("--manifest", type=Path, default=Path("config/genesis_rehearsal_manifest.example.json"))
    parser.add_argument("--out", type=Path, default=Path("reports/genesis_rehearsal_report.json"))
    parser.add_argument("--block-out", type=Path, help="optional path for the mined block JSON")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    network = str(args.network).strip().lower()
    if network in REFUSED_NETWORKS:
        print("error: genesis rehearsal hard-refuses mainnet", file=sys.stderr)
        return 2

    manifest = load_manifest(args.manifest)
    report = generate_report(manifest, requested_network=network)
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if not args.no_write:
        out = ROOT / args.out if not args.out.is_absolute() else args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        if args.block_out:
            block_out = ROOT / args.block_out if not args.block_out.is_absolute() else args.block_out
            block_out.parent.mkdir(parents=True, exist_ok=True)
            block_out.write_text(json.dumps(report.get("block", {}), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
