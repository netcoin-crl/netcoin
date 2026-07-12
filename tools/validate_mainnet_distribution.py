#!/usr/bin/env python3
"""Validate the draft mainnet distribution manifest without creating genesis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if payload.get("schema") != "netcoin-mainnet-distribution-draft-v1":
        issues.append("schema must be netcoin-mainnet-distribution-draft-v1")
    if payload.get("status") == "approved":
        issues.append("source package must not mark draft distribution approved")
    if payload.get("requires_public_approval") is not True:
        issues.append("requires_public_approval must be true")
    if payload.get("requires_nip") is not True:
        issues.append("requires_nip must be true")
    buckets = payload.get("buckets")
    if not isinstance(buckets, list) or len(buckets) < 4:
        issues.append("buckets must list team, treasury, community, and miner emission")
        return issues
    ids = {str(item.get("id")) for item in buckets if isinstance(item, dict)}
    for required in {"team_vested", "treasury_multisig", "community_grants_airdrops", "miner_emission"}:
        if required not in ids:
            issues.append(f"missing distribution bucket: {required}")
    if "not an approved genesis allocation" not in str(payload.get("claim_policy", "")):
        issues.append("claim_policy must state this is not an approved genesis allocation")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="config/mainnet_distribution.example.json")
    parser.add_argument("--out", default="reports/m4_mainnet_distribution_source_report.json")
    args = parser.parse_args()
    path = ROOT / args.input
    issues = [f"missing {args.input}"] if not path.exists() else validate(load(path))
    result = {
        "ok": not issues,
        "mode": "source",
        "claim_level": "draft-only-not-approved-genesis",
        "input": args.input,
        "issues": issues,
        "does_not_generate_genesis": True,
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
