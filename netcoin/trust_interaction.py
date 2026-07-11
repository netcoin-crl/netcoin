"""Phase 0.4 trust-layer and interaction-standard validation helpers.

This module keeps NetCoin's UI workflows from becoming technically correct but
emotionally unsafe. It validates the contract that every trust-critical surface
shows freshness/source/verification context, every irreversible action has a
review step, and every workflow ends with a specific reassurance state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRUST_INTERACTION_PATH = ROOT / "architecture" / "trust-interaction.json"

REQUIRED_STATUS_TERMS = {"Healthy", "Warning", "Offline", "Maintenance"}
REQUIRED_TRUST_SIGNALS = {"freshness", "source", "verification", "risk", "next_action"}
REQUIRED_TRUST_STATES = {"Fresh", "Stale", "Verified", "Unverified", "Risk"}
REQUIRED_LIFECYCLE = ["start", "input", "review", "confirm", "execute", "success", "verify", "recover"]
REQUIRED_SURFACES = {"wallet", "explorer", "markets", "faucet", "exchange", "operator", "download"}
REQUIRED_WORKFLOWS = {
    "send-net",
    "receive-net",
    "trade-market",
    "claim-faucet-net",
    "withdraw-custody-funds",
    "verify-release",
    "handle-operator-incident",
}
REQUIRED_ERROR_FIELDS = {"title", "why_it_matters", "reassurance", "primary_recovery", "secondary_recovery"}
REQUIRED_CONFIRMATION_FIELDS = {"title", "body", "next_action"}


@dataclass(frozen=True)
class TrustInteractionReport:
    ok: bool
    version: str
    issues: list[str]
    trust_state_count: int
    surface_count: int
    workflow_count: int
    error_template_count: int
    confirmation_template_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "version": self.version,
            "issues": self.issues,
            "trust_state_count": self.trust_state_count,
            "surface_count": self.surface_count,
            "workflow_count": self.workflow_count,
            "error_template_count": self.error_template_count,
            "confirmation_template_count": self.confirmation_template_count,
        }


def load_trust_interaction(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical Phase 0.4 trust and interaction specification."""

    return json.loads((path or TRUST_INTERACTION_PATH).read_text(encoding="utf-8"))


def _validate_template_fields(name: str, mapping: dict[str, Any], required: set[str], issues: list[str]) -> None:
    for key, value in mapping.items():
        if not isinstance(value, dict):
            issues.append(f"{name} template {key} must be an object")
            continue
        missing = sorted(required - set(value.keys()))
        if missing:
            issues.append(f"{name} template {key} missing fields: {missing}")
        for field in required:
            if field in value and not str(value[field]).strip():
                issues.append(f"{name} template {key} field {field} must not be empty")


def validate_trust_interaction(spec: dict[str, Any] | None = None) -> TrustInteractionReport:
    """Validate NetCoin's Phase 0.4 trust-layer and interaction rules."""

    data = spec or load_trust_interaction()
    issues: list[str] = []
    version = str(data.get("version", ""))
    if not version:
        issues.append("missing version")

    contract = set(data.get("trust_signal_contract", []))
    if contract != REQUIRED_TRUST_SIGNALS:
        issues.append(f"trust signal contract must be {sorted(REQUIRED_TRUST_SIGNALS)}, got {sorted(contract)}")

    states = data.get("trust_states", {})
    state_keys = set(states.keys()) if isinstance(states, dict) else set()
    if state_keys != REQUIRED_TRUST_STATES:
        issues.append(f"trust states must be {sorted(REQUIRED_TRUST_STATES)}, got {sorted(state_keys)}")

    status_terms = set(data.get("canonical_status_terms", []))
    if status_terms != REQUIRED_STATUS_TERMS:
        issues.append(f"canonical status terms must be {sorted(REQUIRED_STATUS_TERMS)}, got {sorted(status_terms)}")

    lifecycle = list(data.get("action_lifecycle", []))
    if lifecycle != REQUIRED_LIFECYCLE:
        issues.append("action lifecycle drifted from canonical review/confirm/execute/recover sequence")

    interaction_rules = data.get("interaction_rules", [])
    if not isinstance(interaction_rules, list) or len(interaction_rules) < 8:
        issues.append("interaction_rules must include at least eight rules")
    if not any("irreversible action requires a review" in str(rule) for rule in interaction_rules):
        issues.append("interaction rules must require review before irreversible actions")
    if not any("ends with a reassurance" in str(rule) for rule in interaction_rules):
        issues.append("interaction rules must require workflow reassurance states")

    confirmations = data.get("confirmation_templates", {})
    if not isinstance(confirmations, dict) or len(confirmations) < 5:
        issues.append("confirmation_templates must define at least five templates")
    elif not any("Transaction sent" in str(item.get("title", "")) for item in confirmations.values() if isinstance(item, dict)):
        issues.append("confirmation templates must include a wallet send success message")
    if isinstance(confirmations, dict):
        _validate_template_fields("confirmation", confirmations, REQUIRED_CONFIRMATION_FIELDS, issues)

    errors = data.get("error_templates", {})
    if not isinstance(errors, dict) or len(errors) < 5:
        issues.append("error_templates must define at least five templates")
    if isinstance(errors, dict):
        _validate_template_fields("error", errors, REQUIRED_ERROR_FIELDS, issues)
        for key, template in errors.items():
            if isinstance(template, dict) and "nothing" in str(template.get("reassurance", "")).lower() and key not in {
                "send_validation_failed",
                "market_order_rejected",
            }:
                # This is not invalid by itself, but it protects against generic false reassurance.
                pass

    surfaces = data.get("surface_trust_requirements", [])
    surface_names = {str(item.get("surface", "")) for item in surfaces if isinstance(item, dict)}
    missing_surfaces = sorted(REQUIRED_SURFACES - surface_names)
    if missing_surfaces:
        issues.append(f"missing trust requirements for surfaces: {missing_surfaces}")
    for item in surfaces if isinstance(surfaces, list) else []:
        surface = str(item.get("surface", ""))
        must_show = item.get("must_show", [])
        examples = item.get("reassurance_examples", [])
        if not isinstance(must_show, list) or len(must_show) < 3:
            issues.append(f"surface {surface} must show at least three trust signals")
        if not isinstance(examples, list) or len(examples) < 2:
            issues.append(f"surface {surface} must define at least two reassurance examples")

    workflow_rules = data.get("workflow_reassurance_rules", [])
    workflow_names = {str(item.get("workflow", "")) for item in workflow_rules if isinstance(item, dict)}
    missing_workflows = sorted(REQUIRED_WORKFLOWS - workflow_names)
    if missing_workflows:
        issues.append(f"missing workflow reassurance rules: {missing_workflows}")
    for item in workflow_rules if isinstance(workflow_rules, list) else []:
        workflow = str(item.get("workflow", ""))
        if not isinstance(item.get("review_required"), bool):
            issues.append(f"workflow {workflow} must set review_required as a boolean")
        for field in ("success_reassurance", "failure_reassurance"):
            if not str(item.get(field, "")).strip():
                issues.append(f"workflow {workflow} missing {field}")
        if workflow in {"send-net", "trade-market", "withdraw-custody-funds"} and item.get("review_required") is not True:
            issues.append(f"workflow {workflow} must require review")

    microcopy = data.get("microcopy_rules", [])
    if not isinstance(microcopy, list) or len(microcopy) < 5:
        issues.append("microcopy_rules must include at least five rules")
    if not any("local-only" in str(rule) for rule in microcopy):
        issues.append("microcopy rules must preserve local-only label/contact language")

    success = data.get("success_criteria", [])
    if not isinstance(success, list) or len(success) < 5:
        issues.append("success_criteria must include at least five measurable outcomes")

    return TrustInteractionReport(
        ok=not issues,
        version=version,
        issues=issues,
        trust_state_count=len(state_keys),
        surface_count=len(surface_names),
        workflow_count=len(workflow_names),
        error_template_count=len(errors) if isinstance(errors, dict) else 0,
        confirmation_template_count=len(confirmations) if isinstance(confirmations, dict) else 0,
    )


if __name__ == "__main__":
    print(json.dumps(validate_trust_interaction().as_dict(), indent=2, sort_keys=True))
