"""Mainnet readiness evidence gates for v0.41.

These helpers intentionally separate source implementation from real-world
completion. A gate can be source-complete while still requiring strict evidence
from hardware devices, live providers, independent auditors, or public network
operations.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "architecture" / "mainnet-readiness-gates.json"
EVIDENCE_DIR = ROOT / "reports" / "mainnet_evidence"
REQUIRED_GATE_IDS = {
    "hardware-wallet-device-testing",
    "captcha-provider-integration",
    "production-exchange-custody",
    "external-crypto-security-audit",
    "public-production-p2p-soak",
    "long-python-suite-confidence",
    "mainnet-launch-checklist-approval",
    "public-testnet-incident-history",
}
REQUIRED_COMMAND_FIELDS = {"source_command", "strict_command"}


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    ok: bool
    mode: str
    status: str
    issues: tuple[str, ...] = ()
    evidence_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "ok": self.ok,
            "mode": self.mode,
            "status": self.status,
            "issues": list(self.issues),
            "evidence_path": self.evidence_path,
        }


def now() -> int:
    return int(time.time())


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash_json(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_manifest(path: str | Path = MANIFEST) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_manifest(manifest: dict[str, Any], *, root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    if manifest.get("version") != "0.41.0":
        issues.append("mainnet readiness manifest version must be 0.41.0")
    if manifest.get("phase") != "Phase 3 - Mainnet Readiness Evidence Gates":
        issues.append("manifest phase must be Phase 3 - Mainnet Readiness Evidence Gates")
    if "cannot be fabricated" not in str(manifest.get("honesty_policy", "")):
        issues.append("honesty_policy must state real-world evidence cannot be fabricated")
    gates = manifest.get("gates")
    if not isinstance(gates, list):
        issues.append("gates must be a list")
        return issues
    seen: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            issues.append("gate entries must be objects")
            continue
        gate_id = str(gate.get("id", ""))
        if not gate_id:
            issues.append("gate missing id")
        if gate_id in seen:
            issues.append(f"duplicate gate id: {gate_id}")
        seen.add(gate_id)
        missing_fields = sorted(REQUIRED_COMMAND_FIELDS - set(gate))
        if missing_fields:
            issues.append(f"gate {gate_id} missing fields: {', '.join(missing_fields)}")
        if not isinstance(gate.get("required_evidence"), list) or not gate.get("required_evidence"):
            issues.append(f"gate {gate_id} must list required_evidence")
        if "production_done_when" not in gate:
            issues.append(f"gate {gate_id} missing production_done_when")
    missing = sorted(REQUIRED_GATE_IDS - seen)
    if missing:
        issues.append("missing required mainnet gates: " + ", ".join(missing))
    extra = sorted(seen - REQUIRED_GATE_IDS)
    if extra:
        issues.append("unknown mainnet gates: " + ", ".join(extra))
    aggregate = manifest.get("aggregate_gate")
    if not isinstance(aggregate, dict):
        issues.append("aggregate_gate must be an object")
    else:
        if "production_claim_allowed_only_when" not in aggregate:
            issues.append("aggregate_gate must define production_claim_allowed_only_when")
    # Check that every command references a shipped tool.
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        for field in REQUIRED_COMMAND_FIELDS:
            cmd = str(gate.get(field, ""))
            parts = cmd.split()
            tool = next((part for part in parts if part.startswith("tools/") and part.endswith(".py")), "")
            if tool and not (root / tool).exists():
                issues.append(f"gate {gate.get('id')} {field} references missing tool {tool}")
    return issues


def source_gate(gate_id: str, details: dict[str, Any] | None = None) -> GateResult:
    payload = details or {}
    issues = [str(item) for item in payload.get("issues", [])]
    return GateResult(
        gate_id=gate_id,
        ok=not issues,
        mode="source",
        status="source-complete-evidence-required" if not issues else "source-issues",
        issues=tuple(issues),
    )


def validate_required_fields(payload: dict[str, Any], required: list[str]) -> list[str]:
    issues: list[str] = []
    for key in required:
        value = payload.get(key)
        if value in (None, "", [], {}):
            issues.append(f"missing required evidence field: {key}")
    return issues


def load_evidence(path: str | Path) -> tuple[dict[str, Any], list[str]]:
    p = Path(path)
    if not p.exists():
        return {}, [f"missing evidence file: {p}"]
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"invalid JSON evidence {p}: {exc}"]
    return payload, []


def strict_evidence_gate(
    gate_id: str,
    evidence_path: str | Path,
    required_fields: list[str],
    *,
    extra_issues: list[str] | None = None,
) -> GateResult:
    payload, issues = load_evidence(evidence_path)
    if payload:
        issues.extend(validate_required_fields(payload, required_fields))
        if payload.get("gate_id") not in (None, gate_id):
            issues.append(f"evidence gate_id mismatch: expected {gate_id}, got {payload.get('gate_id')}")
        if payload.get("ok") is not True:
            issues.append("evidence ok must be true")
        if not payload.get("evidence_hash"):
            body = {k: v for k, v in payload.items() if k != "evidence_hash"}
            issues.append("evidence_hash is required; expected " + stable_hash_json(body))
        else:
            body = {k: v for k, v in payload.items() if k != "evidence_hash"}
            expected = stable_hash_json(body)
            if payload.get("evidence_hash") != expected:
                issues.append("evidence_hash mismatch")
    if extra_issues:
        issues.extend(extra_issues)
    return GateResult(
        gate_id=gate_id,
        ok=not issues,
        mode="strict",
        status="strict-pass" if not issues else "strict-evidence-required",
        issues=tuple(issues),
        evidence_path=str(evidence_path),
    )


def manifest_gate_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(gate.get("id")): gate for gate in manifest.get("gates", []) if isinstance(gate, dict)}


def aggregate_results(results: list[GateResult], *, version: str = "0.41.0") -> dict[str, Any]:
    blocking = [r for r in results if not r.ok]
    return {
        "ok": not blocking,
        "version": version,
        "phase": "Phase 3 - Mainnet Readiness Evidence Gates",
        "claim_level": "mainnet-candidate" if not blocking and results else "testnet-evidence-gated",
        "gate_count": len(results),
        "pass_count": len([r for r in results if r.ok]),
        "blocker_count": len(blocking),
        "results": [r.to_dict() for r in results],
        "cannot_claim_production_until_blocker_count_zero": True,
    }
