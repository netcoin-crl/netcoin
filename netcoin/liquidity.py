"""M6 liquidity and market metadata helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

LIQUIDITY_SCHEMA = "netcoin-liquidity-market-metadata-v1"


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_liquidity_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    if metadata.get("schema") != LIQUIDITY_SCHEMA:
        issues.append(f"schema must be {LIQUIDITY_SCHEMA}")
    max_supply = int(metadata.get("max_supply_sats") or 0)
    circulating = int(metadata.get("circulating_supply_sats") or 0)
    if max_supply <= 0:
        issues.append("max_supply_sats must be positive")
    if circulating < 0 or circulating > max_supply:
        issues.append("circulating_supply_sats must be between 0 and max_supply_sats")
    lockups = metadata.get("lockups") or []
    lockup_total = sum(int(item.get("amount_sats") or 0) for item in lockups)
    if lockup_total + circulating > max_supply:
        issues.append("circulating supply plus lockups exceeds max supply")
    for venue in metadata.get("venues") or []:
        if venue.get("status") == "listed" and not venue.get("proof_url"):
            issues.append(f"listed venue {venue.get('name')} requires proof_url")
    result = {
        "schema": "netcoin-liquidity-validation-v1",
        "ok": not issues,
        "issues": issues,
        "max_supply_sats": max_supply,
        "circulating_supply_sats": circulating,
        "lockup_total_sats": lockup_total,
        "venue_count": len(metadata.get("venues") or []),
        "metadata_hash": _hash(metadata),
    }
    return result


def coingecko_asset_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    validation = validate_liquidity_metadata(metadata)
    if not validation["ok"]:
        raise ValueError("invalid liquidity metadata: " + "; ".join(validation["issues"]))
    return {
        "id": metadata.get("coingecko_id", "netcoin"),
        "symbol": "NET",
        "name": "NetCoin",
        "asset_platform_id": None,
        "public_notice": "NetCoin market data is draft-only until live exchange evidence exists.",
        "links": metadata.get("links", {}),
        "circulating_supply": validation["circulating_supply_sats"] / 100_000_000,
        "max_supply": validation["max_supply_sats"] / 100_000_000,
    }
