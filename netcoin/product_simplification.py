"""Phase 0.3 product simplification validation helpers.

This module keeps NetCoin from drifting back into feature sprawl. It validates
that new UI/product work stays wallet-first, mode-aware, workflow-owned, and
progressively disclosed instead of creating more top-level pages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SIMPLIFICATION_PATH = ROOT / "architecture" / "product-simplification.json"

REQUIRED_PRIMARY_NAV = ["Wallet", "Explorer", "Markets"]
REQUIRED_MODES = {"user", "trader", "operator", "developer"}
REQUIRED_DISCLOSURE_LEVELS = {"beginner", "intermediate", "advanced", "operator", "developer"}
REQUIRED_COMPLEMENTARY_FEATURES = {
    "release-readiness-scorecard",
    "wallet-security-center",
    "global-command-search",
    "unified-notification-center",
    "guided-testnet-onboarding",
    "local-labels-notes",
    "market-order-preview",
    "custody-risk-dashboard",
    "e2e-screenshot-dashboard",
    "audit-bundle-generator",
}
REQUIRED_NEW_PAGE_FIELDS = {
    "owner_job",
    "primary_action",
    "workflow",
    "target_mode",
    "panel_rejected_reason",
    "trust_signal",
    "empty_state",
    "loading_state",
    "error_state",
}
REQUIRED_WORKFLOW_SURFACES = {
    "receive-net": "wallet",
    "send-net": "wallet",
    "search-chain": "explorer",
    "trade-market": "markets",
    "withdraw-custody-funds": "exchange",
    "verify-release": "download",
}
AVOID_HARD_CEILINGS = {"cross-chain-bridges", "multi-chain-wallet", "mobile-app-rewrite"}


@dataclass(frozen=True)
class ProductSimplificationReport:
    ok: bool
    version: str
    issues: list[str]
    mode_count: int
    disclosure_level_count: int
    complementary_feature_count: int
    workflow_rule_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "version": self.version,
            "issues": self.issues,
            "mode_count": self.mode_count,
            "disclosure_level_count": self.disclosure_level_count,
            "complementary_feature_count": self.complementary_feature_count,
            "workflow_rule_count": self.workflow_rule_count,
        }


def load_product_simplification(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical Phase 0.3 product simplification specification."""

    return json.loads((path or SIMPLIFICATION_PATH).read_text(encoding="utf-8"))


def _feature_ids(items: list[Any]) -> set[str]:
    ids: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            ids.add(str(item.get("id", "")))
        else:
            ids.add(str(item))
    return {item for item in ids if item}


def validate_product_simplification(spec: dict[str, Any] | None = None) -> ProductSimplificationReport:
    """Validate the Phase 0.3 anti-sprawl and progressive-disclosure rules."""

    data = spec or load_product_simplification()
    issues: list[str] = []

    version = str(data.get("version", ""))
    if not version:
        issues.append("missing version")

    visibility = data.get("visibility_model", {})
    if visibility.get("primary_nav") != REQUIRED_PRIMARY_NAV:
        issues.append(f"primary_nav must stay {REQUIRED_PRIMARY_NAV}")

    modes = visibility.get("mode_defaults", {})
    mode_keys = set(modes.keys()) if isinstance(modes, dict) else set()
    missing_modes = sorted(REQUIRED_MODES - mode_keys)
    if missing_modes:
        issues.append(f"missing mode defaults: {missing_modes}")
    for mode, config in modes.items() if isinstance(modes, dict) else []:
        for field in ("show", "deemphasize", "hide_until_needed"):
            if not isinstance(config.get(field), list):
                issues.append(f"mode {mode} must define list field {field}")
        if mode in {"user", "trader"} and "operator" in config.get("show", []):
            issues.append(f"mode {mode} must not show operator tools by default")
        if mode == "user" and "wallet" not in config.get("show", []):
            issues.append("user mode must show wallet")

    consolidation = data.get("page_consolidation_rules", [])
    if not isinstance(consolidation, list) or len(consolidation) < 7:
        issues.append("page_consolidation_rules must contain at least seven rules")
    if not any("Never create a new top-level page" in str(rule) for rule in consolidation):
        issues.append("consolidation rules must include the no-new-top-level-page rule")

    levels = data.get("progressive_disclosure_levels", {})
    level_keys = set(levels.keys()) if isinstance(levels, dict) else set()
    missing_levels = sorted(REQUIRED_DISCLOSURE_LEVELS - level_keys)
    if missing_levels:
        issues.append(f"missing progressive disclosure levels: {missing_levels}")
    for level, config in levels.items() if isinstance(levels, dict) else []:
        if not isinstance(config.get("show"), list) or not config.get("show"):
            issues.append(f"disclosure level {level} must list shown capabilities")
        if not isinstance(config.get("hide"), list):
            issues.append(f"disclosure level {level} must list hidden capabilities")

    features = _feature_ids(data.get("approved_complementary_features", []))
    missing_features = sorted(REQUIRED_COMPLEMENTARY_FEATURES - features)
    if missing_features:
        issues.append(f"missing approved complementary features: {missing_features}")

    avoid = set(data.get("avoid_until_after_audit_candidate", []))
    if not AVOID_HARD_CEILINGS.issubset(avoid):
        issues.append("avoid list must include cross-chain bridges, multi-chain wallet, and mobile app rewrite")

    workflow_rules = data.get("workflow_to_surface_rules", [])
    mapping = {str(item.get("workflow", "")): str(item.get("surface", "")) for item in workflow_rules if isinstance(item, dict)}
    for workflow, surface in REQUIRED_WORKFLOW_SURFACES.items():
        if mapping.get(workflow) != surface:
            issues.append(f"workflow {workflow} must be owned by surface {surface}")
    for item in workflow_rules if isinstance(workflow_rules, list) else []:
        if not item.get("primary_action"):
            issues.append(f"workflow rule {item.get('workflow')} missing primary_action")
        if not isinstance(item.get("secondary_surfaces", []), list):
            issues.append(f"workflow rule {item.get('workflow')} secondary_surfaces must be a list")

    gate = data.get("new_page_gate", {})
    fields = set(gate.get("required_fields", [])) if isinstance(gate, dict) else set()
    if not REQUIRED_NEW_PAGE_FIELDS.issubset(fields):
        issues.append(f"new page gate missing required fields: {sorted(REQUIRED_NEW_PAGE_FIELDS - fields)}")
    if gate.get("maximum_primary_actions") != 1:
        issues.append("new page gate must allow exactly one primary action")
    if gate.get("must_reference_existing_component") is not True:
        issues.append("new page gate must require existing component reuse")
    if gate.get("must_define_progressive_disclosure_level") is not True:
        issues.append("new page gate must require a progressive disclosure level")

    criteria = data.get("success_criteria", [])
    if not isinstance(criteria, list) or len(criteria) < 5:
        issues.append("success_criteria must contain at least five measurable outcomes")

    return ProductSimplificationReport(
        ok=not issues,
        version=version,
        issues=issues,
        mode_count=len(mode_keys),
        disclosure_level_count=len(level_keys),
        complementary_feature_count=len(features),
        workflow_rule_count=len(workflow_rules) if isinstance(workflow_rules, list) else 0,
    )


if __name__ == "__main__":
    print(json.dumps(validate_product_simplification().as_dict(), indent=2, sort_keys=True))
