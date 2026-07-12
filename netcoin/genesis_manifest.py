"""Draft mainnet genesis manifest validation.

This validator is safe for source checks: it validates structure and governance
status but never generates, mines, or activates a real genesis block.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS_MANIFEST_SCHEMA = "netcoin-genesis-manifest-v1"


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_genesis_manifest(manifest: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    issues: list[str] = []
    if manifest.get("schema") != GENESIS_MANIFEST_SCHEMA:
        issues.append(f"schema must be {GENESIS_MANIFEST_SCHEMA}")
    allocations = manifest.get("allocations") or []
    if not allocations:
        issues.append("allocations are required")
    total_bps = 0
    names = set()
    for allocation in allocations:
        name = str(allocation.get("name") or "")
        bps = int(allocation.get("basis_points") or 0)
        if not name:
            issues.append("allocation name is required")
        if name in names:
            issues.append(f"duplicate allocation name: {name}")
        names.add(name)
        if bps <= 0:
            issues.append(f"allocation {name or '<unknown>'} must have positive basis_points")
        total_bps += bps
        if allocation.get("category") == "team" and not allocation.get("vesting"):
            issues.append("team allocation requires vesting")
        if allocation.get("category") == "treasury" and not allocation.get("multisig"):
            issues.append("treasury allocation requires multisig")
    if total_bps != 10_000:
        issues.append(f"allocations must sum to 10000 basis points, got {total_bps}")
    governance = manifest.get("governance") or {}
    if strict:
        for field in ("nip_id", "public_vote_url", "approval_txid", "legal_review_id"):
            if governance.get(field) in (None, "", [], {}):
                issues.append(f"strict genesis manifest requires governance.{field}")
        if manifest.get("status") != "approved":
            issues.append("strict genesis manifest status must be approved")
    result = {
        "schema": "netcoin-genesis-manifest-validation-v1",
        "ok": not issues,
        "strict": strict,
        "issues": issues,
        "allocation_count": len(allocations),
        "total_basis_points": total_bps,
        "does_not_generate_or_mine_genesis": True,
        "manifest_hash": _hash(manifest),
    }
    return result
