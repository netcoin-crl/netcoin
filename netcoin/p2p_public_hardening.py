"""Public P2P hardening contracts for the decentralized testnet."""

from __future__ import annotations

import hashlib
import json
from typing import Any

P2P_HARDENING_SCHEMA = "netcoin-public-p2p-hardening-v1"
MAX_HOME_BANDWIDTH_KBPS = 500


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_dns_seed_plan(plan: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    domains = plan.get("domains") or []
    if len(domains) < 2:
        issues.append("at least two DNS seed domains are required")
    operators = {item.get("operator") for item in domains if isinstance(item, dict)}
    if len(operators - {None, ""}) < 2:
        issues.append("DNS seed plan needs at least two operators")
    for item in domains:
        if not isinstance(item, dict) or not item.get("domain") or not item.get("operator"):
            issues.append("each DNS seed entry needs domain and operator")
    return issues


def validate_operator_manifest(manifest: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required = ("operator", "contact", "node_endpoint", "region", "cloud_or_hardware", "version", "public_key")
    for field in required:
        if manifest.get(field) in (None, "", [], {}):
            issues.append(f"missing operator manifest field: {field}")
    if (
        manifest.get("bandwidth_mode") == "home"
        and int(manifest.get("relay_kbps_limit") or 0) > MAX_HOME_BANDWIDTH_KBPS
    ):
        issues.append("home bandwidth mode must stay at or below 500 KB/s")
    if not str(manifest.get("node_endpoint", "")).endswith(":28444"):
        issues.append("node_endpoint should include port 28444")
    return issues


def public_p2p_hardening_plan(
    *,
    dns_seed_plan: dict[str, Any],
    operator_manifests: list[dict[str, Any]],
    compact_blocks_enabled: bool,
    pex_enabled: bool,
    addrv2_enabled: bool,
    home_bandwidth_kbps: int = MAX_HOME_BANDWIDTH_KBPS,
) -> dict[str, Any]:
    issues = []
    issues.extend(validate_dns_seed_plan(dns_seed_plan))
    for manifest in operator_manifests:
        issues.extend(validate_operator_manifest(manifest))
    if not compact_blocks_enabled:
        issues.append("compact block relay must be enabled for M3/M6 public network hardening")
    if not pex_enabled:
        issues.append("PEX must be enabled")
    if not addrv2_enabled:
        issues.append("AddrV2 must be enabled")
    if home_bandwidth_kbps > MAX_HOME_BANDWIDTH_KBPS:
        issues.append("home-node bandwidth mode must stay under 500 KB/s")
    plan = {
        "schema": P2P_HARDENING_SCHEMA,
        "dns_seed_plan": dns_seed_plan,
        "operator_count": len(operator_manifests),
        "operator_manifests": operator_manifests,
        "compact_blocks_enabled": compact_blocks_enabled,
        "pex_enabled": pex_enabled,
        "addrv2_enabled": addrv2_enabled,
        "home_bandwidth_kbps": home_bandwidth_kbps,
        "ok": not issues,
        "issues": issues,
    }
    plan["plan_hash"] = _hash(plan)
    return plan
