"""Phase 0 design-system and workflow validation helpers.

These helpers keep NetCoin's UI/product architecture from drifting back into
one-off pages, ad-hoc status words, and duplicated workflow patterns.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESIGN_SYSTEM_PATH = ROOT / "architecture" / "design-system.json"
WORKFLOWS_PATH = ROOT / "architecture" / "product-workflows.json"
SHARED_CSS_PATH = ROOT / "sites" / "shared" / "design-system.css"

REQUIRED_STATUS = {"Healthy", "Warning", "Offline", "Maintenance"}
REQUIRED_BUTTONS = {"primary", "secondary", "danger", "ghost"}
REQUIRED_CARDS = {"primary", "summary", "status", "warning", "action", "table", "timeline", "advanced"}
REQUIRED_PAGE_SLOTS = [
    "breadcrumb_or_context",
    "title",
    "plain_language_description",
    "one_primary_action",
    "summary_cards",
    "main_content",
    "secondary_content",
    "advanced_details",
]
REQUIRED_WORKFLOWS = {
    "receive-net",
    "send-net",
    "search-chain",
    "claim-faucet-net",
    "trade-market",
    "withdraw-custody-funds",
    "handle-operator-incident",
    "build-integration",
    "verify-release",
    "prepare-audit",
}
REQUIRED_JOBS = {"manage-money", "understand-chain", "participate", "operate-infrastructure", "build"}


@dataclass(frozen=True)
class DesignSystemReport:
    ok: bool
    version: str
    issues: list[str]
    component_count: int
    workflow_count: int
    css_tokens_present: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "version": self.version,
            "issues": self.issues,
            "component_count": self.component_count,
            "workflow_count": self.workflow_count,
            "css_tokens_present": self.css_tokens_present,
        }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_design_system(path: Path | None = None) -> dict[str, Any]:
    return load_json(path or DESIGN_SYSTEM_PATH)


def load_product_workflows(path: Path | None = None) -> dict[str, Any]:
    return load_json(path or WORKFLOWS_PATH)


def _validate_design_system(data: dict[str, Any], issues: list[str]) -> int:
    version = str(data.get("version", ""))
    if not version:
        issues.append("design system missing version")

    tokens = data.get("tokens", {})
    spacing = tokens.get("spacing_px", [])
    if spacing != [4, 8, 12, 16, 24, 32, 48]:
        issues.append(f"spacing scale drifted: {spacing}")

    typography = tokens.get("typography_px", {})
    for key in ("display", "page", "section", "card", "body", "caption"):
        if key not in typography:
            issues.append(f"typography token missing: {key}")

    status = set(data.get("status_vocabulary", {}).keys())
    if status != REQUIRED_STATUS:
        issues.append(f"status vocabulary must be {sorted(REQUIRED_STATUS)}, got {sorted(status)}")

    page_slots = [str(item.get("slot", "")) for item in data.get("page_template", [])]
    if page_slots != REQUIRED_PAGE_SLOTS:
        issues.append("page template drifted from canonical Phase 0 slot order")

    components = data.get("components", {})
    cards = set(components.get("cards", []))
    buttons = set(components.get("buttons", []))
    if cards != REQUIRED_CARDS:
        issues.append(f"card taxonomy must be {sorted(REQUIRED_CARDS)}, got {sorted(cards)}")
    if buttons != REQUIRED_BUTTONS:
        issues.append(f"button taxonomy must be {sorted(REQUIRED_BUTTONS)}, got {sorted(buttons)}")

    interaction_rules = data.get("interaction_rules", [])
    if len(interaction_rules) < 6:
        issues.append("interaction rules must include at least six rules")
    if not any("Irreversible actions require review" in rule for rule in interaction_rules):
        issues.append("interaction rules must preserve irreversible action review rule")

    accessibility = data.get("accessibility_baseline", [])
    if len(accessibility) < 6:
        issues.append("accessibility baseline must include at least six checks")

    return sum(len(v) if isinstance(v, list) else 0 for v in components.values())


def _validate_workflows(data: dict[str, Any], issues: list[str]) -> int:
    workflows = data.get("workflows", [])
    ids = {str(w.get("id", "")) for w in workflows}
    missing = sorted(REQUIRED_WORKFLOWS - ids)
    if missing:
        issues.append(f"missing required workflows: {missing}")

    state_model = data.get("state_model", [])
    for state in ("start", "input", "review", "confirm", "execute", "success", "verify", "recover"):
        if state not in state_model:
            issues.append(f"workflow state missing: {state}")

    for workflow in workflows:
        wid = str(workflow.get("id", ""))
        job = str(workflow.get("job", ""))
        if job not in REQUIRED_JOBS:
            issues.append(f"workflow {wid} references unknown job: {job}")
        if not workflow.get("surface"):
            issues.append(f"workflow {wid} missing surface")
        if not workflow.get("primary_action"):
            issues.append(f"workflow {wid} missing primary_action")
        steps = workflow.get("steps", [])
        if not isinstance(steps, list) or len(steps) < 4:
            issues.append(f"workflow {wid} must have at least four steps")
        trust = workflow.get("trust_signals", [])
        if not isinstance(trust, list) or len(trust) < 3:
            issues.append(f"workflow {wid} must expose at least three trust signals")
        advanced = workflow.get("advanced_hidden_until_needed", [])
        if not isinstance(advanced, list):
            issues.append(f"workflow {wid} advanced controls must be a list")
    return len(workflows) if isinstance(workflows, list) else 0


def _count_css_tokens(path: Path = SHARED_CSS_PATH) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    required = [
        "--nc-bg",
        "--nc-surface",
        "--nc-primary",
        "--nc-warning",
        "--nc-danger",
        "--nc-space-1",
        "--nc-type-page",
        ".nc-card",
        ".nc-btn-primary",
        ".nc-status-healthy",
    ]
    return sum(1 for token in required if token in text)


def validate_design_system(
    design: dict[str, Any] | None = None,
    workflows: dict[str, Any] | None = None,
) -> DesignSystemReport:
    """Validate NetCoin's Phase 0.2 design-system and workflow architecture."""

    design_data = design or load_design_system()
    workflow_data = workflows or load_product_workflows()
    issues: list[str] = []

    component_count = _validate_design_system(design_data, issues)
    workflow_count = _validate_workflows(workflow_data, issues)
    css_tokens_present = _count_css_tokens()
    if css_tokens_present < 10:
        issues.append("shared design-system CSS is missing required Phase 0 tokens/classes")

    version = str(design_data.get("version", ""))
    if version != str(workflow_data.get("version", "")):
        issues.append("design-system and workflow versions must match")

    return DesignSystemReport(
        ok=not issues,
        version=version,
        issues=issues,
        component_count=component_count,
        workflow_count=workflow_count,
        css_tokens_present=css_tokens_present,
    )


if __name__ == "__main__":
    print(json.dumps(validate_design_system().as_dict(), indent=2, sort_keys=True))
