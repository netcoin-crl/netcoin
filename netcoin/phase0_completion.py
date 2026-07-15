"""Phase 0 completion validation for NetCoin product architecture.

This module validates that Phase 0 is complete before future releases continue
into proof hardening. Phase 0 is intentionally non-feature work: it locks the
product identity, design-system rules, simplification gates, trust language, and
no-dead-end workflow contract so NetCoin does not sprawl into disconnected mini
apps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from netcoin.design_system import validate_design_system
from netcoin.product_architecture import validate_product_architecture
from netcoin.product_coherence import validate_product_coherence
from netcoin.product_simplification import validate_product_simplification
from netcoin.trust_interaction import validate_trust_interaction

ROOT = Path(__file__).resolve().parents[1]
PHASE0_COMPLETION_PATH = ROOT / "architecture" / "phase0-completion.json"

REQUIRED_LAYER_IDS = {
    "product-identity",
    "design-system",
    "workflow-architecture",
    "product-simplification",
    "trust-interaction",
    "product-coherence",
}
REQUIRED_CHECKERS = {
    "python tools/check_product_architecture.py",
    "python tools/check_design_system.py",
    "python tools/check_product_simplification.py",
    "python tools/check_trust_interaction.py",
    "python tools/check_product_coherence.py",
    "python tools/check_phase0_complete.py",
}
REQUIRED_PRIMARY_NAVIGATION = ["Core", "Network", "Build", "Ecosystem"]
REQUIRED_LENSES = {"NetCoin", "NetCoin Network", "NetCoin Studio"}
REQUIRED_JOBS = {"Manage money", "Understand the blockchain", "Participate", "Operate infrastructure", "Build"}
REQUIRED_STATUS = {"Healthy", "Warning", "Offline", "Maintenance"}
REQUIRED_TRUST = {"Fresh", "Stale", "Verified", "Unverified", "Risk"}
REQUIRED_COMPLEMENTARY = {
    "Release Readiness Scorecard",
    "Wallet Security Center",
    "Global command/search palette",
    "Unified notification center",
    "Guided testnet onboarding",
    "Local labels and notes",
    "Market order preview",
    "Custody risk dashboard",
    "E2E screenshot dashboard",
    "Audit bundle generator",
}
REQUIRED_FORBIDDEN = {"NFTs", "cross-chain bridges", "multi-chain wallet", "mainnet launch marketing page"}
REQUIRED_PHASE1_EVIDENCE = {
    "full Python test-suite report",
    "cargo test --workspace report",
    "all Rust parity binary reports",
    "npm ci && npm run ci:api report",
    "real Playwright E2E report",
    "accessibility report",
    "release readiness scorecard",
}


@dataclass(frozen=True)
class Phase0CompletionReport:
    ok: bool
    version: str
    issues: list[str]
    completed_layer_count: int
    quality_gate_count: int
    acceptance_criteria_count: int
    roadmap_phase_count: int
    complementary_feature_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "version": self.version,
            "issues": self.issues,
            "completed_layer_count": self.completed_layer_count,
            "quality_gate_count": self.quality_gate_count,
            "acceptance_criteria_count": self.acceptance_criteria_count,
            "roadmap_phase_count": self.roadmap_phase_count,
            "complementary_feature_count": self.complementary_feature_count,
        }


def load_phase0_completion(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical Phase 0 completion specification."""

    return json.loads((path or PHASE0_COMPLETION_PATH).read_text(encoding="utf-8"))


def _check_child_validators(issues: list[str]) -> None:
    child_reports = [
        ("product architecture", validate_product_architecture()),
        ("design system", validate_design_system()),
        ("product simplification", validate_product_simplification()),
        ("trust interaction", validate_trust_interaction()),
        ("product coherence", validate_product_coherence()),
    ]
    for name, report in child_reports:
        if not report.ok:
            issues.append(f"{name} validator failed: {report.issues}")


def validate_phase0_completion(
    spec: dict[str, Any] | None = None, *, run_child_validators: bool = True
) -> Phase0CompletionReport:
    """Validate the final Phase 0 completion and handoff contract."""

    data = spec or load_phase0_completion()
    issues: list[str] = []
    version = str(data.get("version", ""))
    if not version:
        issues.append("missing version")
    if data.get("phase") != "phase-0-complete":
        issues.append("phase must be phase-0-complete")
    if data.get("completion_status") != "complete":
        issues.append("completion_status must be complete")
    if "Core -> Network -> Build -> Ecosystem" not in str(data.get("north_star", "")):
        issues.append("north_star must keep Core -> Network -> Build -> Ecosystem as the public mental model")

    layers = data.get("completed_layers", [])
    layer_ids = {str(item.get("id", "")) for item in layers if isinstance(item, dict)}
    missing_layers = sorted(REQUIRED_LAYER_IDS - layer_ids)
    if missing_layers:
        issues.append(f"missing completed Phase 0 layers: {missing_layers}")
    for item in layers if isinstance(layers, list) else []:
        layer_id = str(item.get("id", ""))
        for field in ("artifact", "checker", "locked_decision"):
            if not str(item.get(field, "")).strip():
                issues.append(f"layer {layer_id} missing {field}")
        artifact = ROOT / str(item.get("artifact", ""))
        if not artifact.exists():
            issues.append(f"layer {layer_id} artifact does not exist: {artifact}")

    locked = data.get("locked_product_decisions", {})
    if locked.get("primary_navigation") != REQUIRED_PRIMARY_NAVIGATION:
        issues.append("locked primary navigation must be Core, Network, Build, Ecosystem")
    if set(locked.get("product_lenses", [])) != REQUIRED_LENSES:
        issues.append("locked product lenses must be NetCoin, NetCoin Network, and NetCoin Studio")
    if set(locked.get("user_jobs", [])) != REQUIRED_JOBS:
        issues.append("locked user jobs must match the five-job model")
    if set(locked.get("status_vocabulary", [])) != REQUIRED_STATUS:
        issues.append("status vocabulary must be Healthy, Warning, Offline, Maintenance")
    if set(locked.get("trust_vocabulary", [])) != REQUIRED_TRUST:
        issues.append("trust vocabulary must be Fresh, Stale, Verified, Unverified, Risk")
    for field in ("page_rule", "anti_sprawl_rule", "new_surface_rule"):
        if len(str(locked.get(field, "")).split()) < 8:
            issues.append(f"locked decision {field} is too vague")
    if "improve an existing workflow" not in str(locked.get("anti_sprawl_rule", "")):
        issues.append("anti_sprawl_rule must require improving existing workflows")

    gates = data.get("phase0_quality_gates", [])
    missing_gates = sorted(REQUIRED_CHECKERS - set(gates if isinstance(gates, list) else []))
    if missing_gates:
        issues.append(f"missing Phase 0 quality gates: {missing_gates}")
    if not any(str(gate).startswith("make v0385-check") for gate in gates if isinstance(gates, list)):
        issues.append("phase0_quality_gates must include make v0385-check")

    criteria = data.get("phase0_acceptance_criteria", [])
    if not isinstance(criteria, list) or len(criteria) < 12:
        issues.append("phase0_acceptance_criteria must include at least twelve criteria")
    if not any("anti-sprawl" in str(item) for item in criteria):
        issues.append("acceptance criteria must mention anti-sprawl rules")

    roadmap = data.get("approved_next_roadmap", [])
    if not isinstance(roadmap, list) or len(roadmap) < 7:
        issues.append("approved_next_roadmap must include at least seven phases")
    roadmap_names = [str(item.get("name", "")) for item in roadmap if isinstance(item, dict)]
    for required in [
        "Proof Hardening",
        "Wallet Professional UX",
        "Explorer and Indexer Trust",
        "Markets Risk and Settlement",
        "Exchange and Custody Safety",
    ]:
        if required not in roadmap_names:
            issues.append(f"approved_next_roadmap missing {required}")
    if roadmap and isinstance(roadmap[0], dict) and roadmap[0].get("name") != "Proof Hardening":
        issues.append("first post-Phase-0 roadmap phase must be Proof Hardening")

    complementary = set(data.get("approved_complementary_features", []))
    if not REQUIRED_COMPLEMENTARY.issubset(complementary):
        issues.append(f"approved complementary features missing: {sorted(REQUIRED_COMPLEMENTARY - complementary)}")
    forbidden = set(data.get("forbidden_until_after_audit_candidate", []))
    if not REQUIRED_FORBIDDEN.issubset(forbidden):
        issues.append(f"forbidden list missing hard no-go features: {sorted(REQUIRED_FORBIDDEN - forbidden)}")

    handoff = data.get("phase1_handoff", {})
    if handoff.get("next_phase") != "Phase 1 - Proof Hardening":
        issues.append("phase1_handoff must point to Phase 1 - Proof Hardening")
    evidence = set(handoff.get("required_evidence", [])) if isinstance(handoff, dict) else set()
    if not REQUIRED_PHASE1_EVIDENCE.issubset(evidence):
        issues.append(f"phase1 handoff missing evidence: {sorted(REQUIRED_PHASE1_EVIDENCE - evidence)}")
    blocked = set(handoff.get("blocked_claims_until_complete", [])) if isinstance(handoff, dict) else set()
    for claim in ["production ready", "mainnet ready", "externally audited"]:
        if claim not in blocked:
            issues.append(f"phase1 handoff must block claim: {claim}")

    done = data.get("definition_of_done", [])
    if not isinstance(done, list) or len(done) < 6:
        issues.append("definition_of_done must include at least six items")
    if not any("Phase 1 proof-hardening handoff" in str(item) for item in done):
        issues.append("definition_of_done must include Phase 1 proof-hardening handoff")

    if run_child_validators:
        _check_child_validators(issues)

    return Phase0CompletionReport(
        ok=not issues,
        version=version,
        issues=issues,
        completed_layer_count=len(layer_ids),
        quality_gate_count=len(gates) if isinstance(gates, list) else 0,
        acceptance_criteria_count=len(criteria) if isinstance(criteria, list) else 0,
        roadmap_phase_count=len(roadmap) if isinstance(roadmap, list) else 0,
        complementary_feature_count=len(complementary),
    )


if __name__ == "__main__":
    print(json.dumps(validate_phase0_completion().as_dict(), indent=2, sort_keys=True))
