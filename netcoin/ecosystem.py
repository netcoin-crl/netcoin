"""M7 ecosystem, SDK, grants, and utility validation helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

ECOSYSTEM_SCHEMA = "netcoin-ecosystem-utility-v1"
ALLOWED_UTILITY_FOCUS = {"dev-first-bitcoin-family-sandbox", "payments", "settlement", "identity-anchor"}


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_ecosystem_plan(plan: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    if plan.get("schema") != ECOSYSTEM_SCHEMA:
        issues.append(f"schema must be {ECOSYSTEM_SCHEMA}")
    focus = plan.get("utility_focus")
    if focus not in ALLOWED_UTILITY_FOCUS:
        issues.append("utility_focus must be one explicit supported focus")
    sdks = plan.get("sdks") or []
    languages = {sdk.get("language") for sdk in sdks}
    for required in ("typescript", "python", "rust"):
        if required not in languages:
            issues.append(f"missing SDK plan for {required}")
    grants = plan.get("grants") or {}
    if not grants.get("public_tracker"):
        issues.append("grants.public_tracker is required")
    metrics = set(plan.get("metrics") or [])
    for metric in ("weekly_active_addresses", "non_airdrop_tx_count", "developer_apps"):
        if metric not in metrics:
            issues.append(f"missing ecosystem metric: {metric}")
    result = {
        "schema": "netcoin-ecosystem-plan-validation-v1",
        "ok": not issues,
        "issues": issues,
        "utility_focus": focus,
        "sdk_count": len(sdks),
        "plan_hash": _hash(plan),
    }
    return result
