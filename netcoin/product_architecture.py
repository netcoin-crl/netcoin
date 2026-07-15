"""Product identity and UX architecture helpers for NetCoin Phase 0.

This module intentionally stays lightweight. It gives docs, site tooling, and
release checks one canonical place to validate the anti-sprawl product model:
Core -> Network -> Build -> Ecosystem, with Explorer/Download/Home/Markets/Wallet in Core.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "architecture" / "product-ux-architecture.json"
ALLOWED_TOP_NAV = ["Core", "Network", "Build", "Ecosystem"]
REQUIRED_JOB_IDS = {
    "manage-money",
    "understand-chain",
    "participate",
    "operate-infrastructure",
    "build",
}
REQUIRED_STATUS_TERMS = {"Healthy", "Warning", "Offline", "Maintenance"}
REQUIRED_BUTTON_TYPES = {"primary", "secondary", "danger", "ghost"}
REQUIRED_CARD_TYPES = {"primary", "summary", "status", "warning", "action", "table", "timeline", "advanced"}
REQUIRED_PAGE_TEMPLATE = [
    "breadcrumb_or_context",
    "title",
    "plain_language_description",
    "one_primary_action",
    "summary_cards",
    "main_content",
    "secondary_content",
    "advanced_details",
]


@dataclass(frozen=True)
class ProductArchitectureReport:
    ok: bool
    version: str
    issues: list[str]
    jobs: list[str]
    surfaces: list[str]
    primary_navigation: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "version": self.version,
            "issues": self.issues,
            "jobs": self.jobs,
            "surfaces": self.surfaces,
            "primary_navigation": self.primary_navigation,
        }


def load_product_architecture(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical Phase 0 product architecture specification."""

    spec_path = path or SPEC_PATH
    return json.loads(spec_path.read_text(encoding="utf-8"))


def validate_product_architecture(spec: dict[str, Any] | None = None) -> ProductArchitectureReport:
    """Validate the Phase 0 anti-sprawl rules.

    This is not a full JSON schema validator. It checks the rules that matter
    for NetCoin's current product maturity: small primary navigation, five user
    jobs, every surface assigned to a job, consistent status/button/card
    vocabulary, and one canonical page template.
    """

    data = spec or load_product_architecture()
    issues: list[str] = []

    version = str(data.get("version", ""))
    if not version:
        issues.append("missing version")

    primary_navigation = list(data.get("primary_navigation", []))
    if primary_navigation != ALLOWED_TOP_NAV:
        issues.append(f"primary navigation must be {ALLOWED_TOP_NAV}, got {primary_navigation}")

    jobs = data.get("jobs", [])
    job_ids = {str(job.get("id", "")) for job in jobs}
    if job_ids != REQUIRED_JOB_IDS:
        issues.append(f"jobs must be {sorted(REQUIRED_JOB_IDS)}, got {sorted(job_ids)}")

    surface_ownership = data.get("surface_ownership", {})
    if not isinstance(surface_ownership, dict) or not surface_ownership:
        issues.append("surface_ownership must be a non-empty object")
    else:
        unknown_jobs = sorted(set(surface_ownership.values()) - REQUIRED_JOB_IDS)
        if unknown_jobs:
            issues.append(f"surface_ownership references unknown jobs: {unknown_jobs}")
        for surface in ("wallet", "explorer", "markets", "faucet", "community", "operator", "exchange", "api", "docs"):
            if surface not in surface_ownership:
                issues.append(f"surface missing from ownership map: {surface}")

    modes = data.get("user_modes", {})
    for required_mode in ("user", "trader", "operator", "developer"):
        if required_mode not in modes:
            issues.append(f"missing user mode: {required_mode}")

    page_template = list(data.get("page_template", []))
    if page_template != REQUIRED_PAGE_TEMPLATE:
        issues.append("page_template drifted from canonical Phase 0 template")

    component_rules = data.get("component_rules", {})
    status_terms = set(component_rules.get("status_terms", []))
    if status_terms != REQUIRED_STATUS_TERMS:
        issues.append(f"status terms must be {sorted(REQUIRED_STATUS_TERMS)}, got {sorted(status_terms)}")
    button_types = set(component_rules.get("button_types", []))
    if button_types != REQUIRED_BUTTON_TYPES:
        issues.append(f"button types must be {sorted(REQUIRED_BUTTON_TYPES)}, got {sorted(button_types)}")
    card_types = set(component_rules.get("allowed_card_types", []))
    if card_types != REQUIRED_CARD_TYPES:
        issues.append(f"card types must be {sorted(REQUIRED_CARD_TYPES)}, got {sorted(card_types)}")

    product_rules = data.get("product_rules", [])
    if len(product_rules) < 7:
        issues.append("product_rules should contain at least seven anti-sprawl rules")

    approved = data.get("approved_complementary_features", [])
    if "release-readiness-scorecard" not in approved or "wallet-security-center" not in approved:
        issues.append(
            "approved complementary features must include release-readiness-scorecard and wallet-security-center"
        )

    return ProductArchitectureReport(
        ok=not issues,
        version=version,
        issues=issues,
        jobs=sorted(job_ids),
        surfaces=sorted(surface_ownership.keys()) if isinstance(surface_ownership, dict) else [],
        primary_navigation=primary_navigation,
    )


def primary_navigation() -> list[str]:
    """Return the approved top-level product navigation labels."""

    return list(load_product_architecture().get("primary_navigation", []))


if __name__ == "__main__":
    print(json.dumps(validate_product_architecture().as_dict(), indent=2, sort_keys=True))
