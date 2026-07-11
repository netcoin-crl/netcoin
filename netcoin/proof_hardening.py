"""Phase 1 proof-hardening manifest helpers.

This module is intentionally small and deterministic. It validates the proof
manifest and builds release-readiness scorecards from observed gate results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = ROOT / "architecture" / "proof-hardening.json"
ALLOWED_GATE_STATUSES = {"pass", "fail", "blocked", "not_run", "source_only"}
REQUIRED_GATE_FIELDS = {
    "id",
    "label",
    "owner",
    "strict_commands",
    "sandbox_commands",
    "hard_ceiling_removed",
}


@dataclass(frozen=True)
class ProofGateResult:
    """Observed status for one proof gate."""

    gate_id: str
    label: str
    status: str
    mode: str
    command_count: int
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "label": self.label,
            "status": self.status,
            "mode": self.mode,
            "command_count": self.command_count,
            "issues": list(self.issues),
        }


def load_proof_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_proof_manifest(manifest: dict[str, Any]) -> list[str]:
    """Return manifest issues. Empty means the Phase 1 manifest is valid."""

    issues: list[str] = []
    if manifest.get("phase") != "Phase 1 - Proof Hardening":
        issues.append("phase must be 'Phase 1 - Proof Hardening'")
    if not str(manifest.get("version", "")).startswith("0.39"):
        issues.append("version must identify the v0.39 proof-hardening line")
    if manifest.get("inherits_from") != "architecture/phase0-completion.json":
        issues.append("manifest must explicitly inherit Phase 0 completion")
    modes = manifest.get("modes")
    if not isinstance(modes, dict) or not {"sandbox", "strict"}.issubset(modes):
        issues.append("modes must include sandbox and strict")
    terms = set(manifest.get("gate_status_terms", []))
    if terms != ALLOWED_GATE_STATUSES:
        issues.append(f"gate_status_terms must be {sorted(ALLOWED_GATE_STATUSES)}")
    gate_groups = manifest.get("gate_groups")
    if not isinstance(gate_groups, list) or not gate_groups:
        issues.append("gate_groups must be a non-empty list")
        return issues
    gate_ids: set[str] = set()
    for idx, gate in enumerate(gate_groups):
        if not isinstance(gate, dict):
            issues.append(f"gate_groups[{idx}] must be an object")
            continue
        missing = sorted(REQUIRED_GATE_FIELDS - set(gate))
        if missing:
            issues.append(f"gate {idx} missing fields: {', '.join(missing)}")
        gate_id = str(gate.get("id", ""))
        if not gate_id:
            issues.append(f"gate {idx} has empty id")
        elif gate_id in gate_ids:
            issues.append(f"duplicate gate id {gate_id}")
        gate_ids.add(gate_id)
        for field in ["strict_commands", "sandbox_commands"]:
            value = gate.get(field)
            if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
                issues.append(f"gate {gate_id or idx} {field} must contain commands")
    required = {"python-reference", "rust-workspace", "rust-parity", "typescript-api", "browser-e2e", "accessibility", "security-release", "phase0-guardrails"}
    missing_required = sorted(required - gate_ids)
    if missing_required:
        issues.append(f"missing required proof gates: {', '.join(missing_required)}")
    scorecard = manifest.get("release_readiness_scorecard", {})
    if not isinstance(scorecard, dict) or not scorecard.get("path"):
        issues.append("release_readiness_scorecard.path is required")
    exit_criteria = manifest.get("phase1_exit_criteria")
    if not isinstance(exit_criteria, list) or len(exit_criteria) < 5:
        issues.append("phase1_exit_criteria must list concrete strict-mode blockers")
    return issues


def scorecard_from_results(
    manifest: dict[str, Any],
    results: Iterable[ProofGateResult],
    *,
    mode: str,
) -> dict[str, Any]:
    """Build a release-readiness scorecard from observed gate results."""

    result_list = [item.to_dict() for item in results]
    counts = {status: 0 for status in sorted(ALLOWED_GATE_STATUSES)}
    for item in result_list:
        status = str(item.get("status"))
        if status in counts:
            counts[status] += 1
    blocking = set(manifest.get("release_readiness_scorecard", {}).get("blocking_statuses", []))
    blockers = [item for item in result_list if item.get("status") in blocking]
    ok = not blockers if mode == "strict" else not any(item.get("status") == "fail" for item in result_list)
    return {
        "version": manifest.get("version"),
        "phase": manifest.get("phase"),
        "mode": mode,
        "ok": ok,
        "claim_level": "professional-candidate" if mode == "strict" and ok else "source-checked-testnet",
        "gate_count": len(result_list),
        "status_counts": counts,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "results": result_list,
        "caveat": None
        if mode == "strict"
        else "Sandbox/source-only evidence is not enough for professional or mainnet readiness.",
    }
