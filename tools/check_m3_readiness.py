#!/usr/bin/env python3
"""Source and strict-evidence gate for M3 decentralized public testnet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "architecture" / "m3-decentralized-testnet.json"

TOKEN_CHECKS = {
    "one-command-node-installer": {
        "tools/install_public_node.sh": ["--dry-run", "--advertise", "NETCOIN_BANDWIDTH_MODE"],
        "docker-compose.node.yml": ["28444", "NETCOIN_ADVERTISE", "NETCOIN_BANDWIDTH_MODE"],
        "docs/M3_NODE_OPERATOR_GUIDE.md": ["10 independent operators", "Docker Compose", "28444"],
    },
    "multi-domain-dns-seeds": {
        "config/dns_seeds.json": ["netcoin-seeds.net", "independent_seed_operators"],
        "docs/M3_DNS_SEEDS.md": ["independent DNS", "reports/m3_evidence/dns_seed_delegation.json"],
    },
    "pex-addrv2-python-rust": {
        "netcoin/addrv2.py": ["ADDRV2_SCHEMA", "torv3", "diversity_key"],
        "netcoin/pex.py": ["PEXPolicy", "select_pex_records", "ingest_pex_records"],
        "netcoin/p2p.py": ["getaddr", "addr", "pex", "parse_addr_payload"],
        "core-rs/crates/node/src/lib.rs": ["AddrV2Snapshot", "pex_select_addrs", "addrv2_network_id"],
    },
    "compact-block-relay": {
        "netcoin/compact.py": ["CompactBlock", "missing_transactions", "compact_missing_payload"],
        "netcoin/p2p.py": ["cmpctblock", "getblocktxn", "blocktxn"],
    },
    "home-node-bandwidth-mode": {
        "netcoin/bandwidth.py": ["BandwidthBudget", "home", "500 * 1024"],
        "docs/M3_HOME_NODE_BANDWIDTH.md": ["500 KB/s", "NETCOIN_BANDWIDTH_MODE=home"],
    },
    "public-node-map": {
        "sites/nodes/index.html": ["Independent operator map", "nodeMapData", "M3"],
        "sites/nodes/nodes.js": ["nodes/map", "nodeMapData", "operator_count"],
        "api/nodes/map": ["netcoin-public-node-map-v1", "static-fallback"],
        "tools/export_node_map.py": ["node_map_from_peer_database", "public_node_map"],
    },
    "node-grants-program": {
        "docs/M3_NODE_GRANTS_PROGRAM.md": ["500 testnet NET", "2,000 testnet NET", "governance approval"],
    },
    "thirty-day-soak-report": {
        "docs/M3_30_DAY_SOAK_REPORT.md": ["30-day", "P50/P99", "reports/m3_evidence/soak_30_day_report.json"],
        "tools/validate_m3_soak_report.py": ["independent_operator_count", "non_founder_mined_block_hash"],
    },
    "testnet-soft-fork-rehearsal": {
        "docs/M3_TESTNET_SOFT_FORK_REHEARSAL.md": ["Consensus/version-bits", "explicit same-session signoff", "NIP"],
    },
    "mining-pool-reference": {
        "docs/M3_MINING_POOL_REFERENCE.md": ["Stratum-lite", "non-founder mined block", "pool/job"],
    },
}

SOURCE_COMMANDS = [
    "python3 -m py_compile netcoin/addrv2.py netcoin/pex.py netcoin/bandwidth.py netcoin/p2p.py tools/check_m3_readiness.py tools/run_m3_release_candidate.py tools/export_node_map.py tools/validate_m3_soak_report.py",
    "python3 -m pytest tests/test_m3_decentralized_testnet.py -q",
    "python3 tools/export_node_map.py --input api/nodes/map --out reports/m3_node_map_source_report.json",
]

STRICT_EVIDENCE = {
    "independent_nodes": "reports/m3_evidence/independent_nodes.json",
    "dns_seed_delegation": "reports/m3_evidence/dns_seed_delegation.json",
    "soak_30_day_report": "reports/m3_evidence/soak_30_day_report.json",
    "non_founder_mined_block": "reports/m3_evidence/non_founder_mined_block.json",
    "soft_fork_rehearsal": "reports/m3_evidence/testnet_soft_fork_rehearsal.json",
}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="ignore")


def validate_manifest() -> tuple[dict[str, Any], list[str]]:
    if not MANIFEST.exists():
        return {}, ["missing architecture/m3-decentralized-testnet.json"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    issues = []
    if manifest.get("milestone") != "M3":
        issues.append("manifest milestone must be M3")
    if "Operational M3 requires strict evidence" not in manifest.get("claim_policy", ""):
        issues.append("manifest claim_policy must require strict evidence")
    ids = {item.get("id") for item in manifest.get("deliverables", []) if isinstance(item, dict)}
    missing = sorted(set(TOKEN_CHECKS) - ids)
    if missing:
        issues.append("missing M3 deliverables: " + ", ".join(missing))
    return manifest, issues


def source_gate() -> dict[str, Any]:
    manifest, issues = validate_manifest()
    results = []
    for gate_id, files in TOKEN_CHECKS.items():
        gate_issues = []
        for rel, tokens in files.items():
            path = ROOT / rel
            if not path.exists():
                gate_issues.append(f"missing {rel}")
                continue
            text = _read(rel)
            for token in tokens:
                if token not in text:
                    gate_issues.append(f"{rel} missing token: {token}")
        results.append({"id": gate_id, "ok": not gate_issues, "issues": gate_issues})
        issues.extend(f"{gate_id}: {issue}" for issue in gate_issues)
    return {
        "ok": not issues,
        "milestone": "M3",
        "mode": "source",
        "claim_level": "m3-source-complete-evidence-required" if not issues else "m3-source-incomplete",
        "deliverable_count": len(TOKEN_CHECKS),
        "pass_count": len([item for item in results if item["ok"]]),
        "blocker_count": len([item for item in results if not item["ok"]]),
        "results": results,
        "issues": issues,
        "cannot_claim_operational_m3_without_strict_evidence": True,
        "manifest_version": manifest.get("schema"),
    }


def strict_gate() -> dict[str, Any]:
    result = source_gate()
    evidence_issues = []
    for label, rel in STRICT_EVIDENCE.items():
        path = ROOT / rel
        if not path.exists():
            evidence_issues.append(f"missing strict evidence: {rel}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            evidence_issues.append(f"invalid JSON evidence {rel}: {exc}")
            continue
        if payload.get("ok") is not True:
            evidence_issues.append(f"strict evidence {rel} ok must be true")
    result["mode"] = "strict"
    result["strict_evidence"] = STRICT_EVIDENCE
    result["issues"] = list(result.get("issues", [])) + evidence_issues
    result["ok"] = not result["issues"]
    result["claim_level"] = "m3-operationally-verified" if result["ok"] else "m3-strict-evidence-required"
    result["blocker_count"] = len(result["issues"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out", default="reports/m3_readiness_source_report.json")
    args = parser.parse_args()
    result = strict_gate() if args.strict else source_gate()
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
