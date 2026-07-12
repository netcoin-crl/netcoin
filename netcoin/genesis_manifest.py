"""Draft mainnet genesis manifest validation.

This validator is safe for source checks: it validates structure and governance
status but never generates, mines, or activates a real genesis block.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS_MANIFEST_SCHEMA = "netcoin-genesis-manifest-v1"
REQUIRED_ALLOCATION_CATEGORIES = {"emission", "community", "treasury", "team"}
APPROVED_GOVERNANCE_FIELDS = ("nip_id", "public_vote_url", "approval_txid", "legal_review_id")


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _to_int(value: Any, field: str, issues: list[str]) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        issues.append(f"{field} must be an integer")
        return 0


def _is_final_governance_value(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    text = str(value).strip().lower()
    return bool(text) and not text.startswith("draft") and text not in {"todo", "tbd", "placeholder"}


def validate_genesis_manifest(manifest: dict[str, Any], *, strict: bool = False) -> dict[str, Any]:
    issues: list[str] = []
    if manifest.get("schema") != GENESIS_MANIFEST_SCHEMA:
        issues.append(f"schema must be {GENESIS_MANIFEST_SCHEMA}")
    allocations = manifest.get("allocations") or []
    if not isinstance(allocations, list) or not allocations:
        issues.append("allocations are required")
        allocations = []
    total_bps = 0
    names = set()
    categories = set()
    for index, allocation in enumerate(allocations):
        if not isinstance(allocation, dict):
            issues.append(f"allocation[{index}] must be an object")
            continue
        name = str(allocation.get("name") or "")
        category = str(allocation.get("category") or "")
        bps = _to_int(allocation.get("basis_points"), f"allocation {name or index} basis_points", issues)
        if not name:
            issues.append("allocation name is required")
        if name in names:
            issues.append(f"duplicate allocation name: {name}")
        names.add(name)
        if category not in REQUIRED_ALLOCATION_CATEGORIES:
            issues.append(f"allocation {name or '<unknown>'} has unsupported category: {category or '<missing>'}")
        else:
            categories.add(category)
        if bps <= 0:
            issues.append(f"allocation {name or '<unknown>'} must have positive basis_points")
        total_bps += bps
        if category == "team" and not allocation.get("vesting"):
            issues.append("team allocation requires vesting")
        if category == "treasury" and not allocation.get("multisig"):
            issues.append("treasury allocation requires multisig")
    missing_categories = sorted(REQUIRED_ALLOCATION_CATEGORIES - categories)
    if missing_categories:
        issues.append("allocations missing required categories: " + ", ".join(missing_categories))
    if total_bps != 10_000:
        issues.append(f"allocations must sum to 10000 basis points, got {total_bps}")
    governance = manifest.get("governance") or {}
    if not isinstance(governance, dict):
        issues.append("governance must be an object")
        governance = {}
    if manifest.get("status") == "approved":
        for field in APPROVED_GOVERNANCE_FIELDS:
            if not _is_final_governance_value(governance.get(field)):
                issues.append(f"approved genesis manifest requires final governance.{field}")
    if strict:
        for field in APPROVED_GOVERNANCE_FIELDS:
            if not _is_final_governance_value(governance.get(field)):
                issues.append(f"strict genesis manifest requires final governance.{field}")
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
