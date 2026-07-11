"""Phase 0.5 product coherence and no-dead-end workflow validation.

This module keeps NetCoin's Phase 0 work focused on product coherence. It
validates that every major surface belongs to a product lens, user job,
workflow, trust signal, and next action so the site does not drift back into a
collection of disconnected mini-apps.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_COHERENCE_PATH = ROOT / "architecture" / "product-coherence.json"

REQUIRED_LENSES = {"netcoin", "netcoin-network", "netcoin-studio"}
REQUIRED_JOBS = {"manage-money", "understand-chain", "participate", "operate-infrastructure", "build"}
REQUIRED_PUBLIC_SURFACES = {"wallet", "explorer", "markets"}
REQUIRED_SURFACES = {
    "wallet",
    "explorer",
    "markets",
    "faucet",
    "community",
    "exchange",
    "operator",
    "docs",
    "api",
    "downloads",
}
REQUIRED_WORKFLOWS = {
    "receive-net",
    "send-net",
    "search-chain",
    "trade-market",
    "claim-faucet-net",
    "withdraw-custody-funds",
    "handle-operator-incident",
    "verify-release",
}
REQUIRED_EXIT_FIELDS = {
    "surface",
    "lens",
    "job",
    "primary_action",
    "trust_signal",
    "next_step",
    "advanced_destination",
}
REQUIRED_END_STATES = {
    "explorer",
    "wallet",
    "portfolio",
    "settlement",
    "ledger",
    "runbook",
    "diagnostics",
    "install",
    "blocked",
}


@dataclass(frozen=True)
class ProductCoherenceReport:
    ok: bool
    version: str
    issues: list[str]
    lens_count: int
    job_count: int
    surface_count: int
    workflow_count: int
    no_dead_end_rule_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "version": self.version,
            "issues": self.issues,
            "lens_count": self.lens_count,
            "job_count": self.job_count,
            "surface_count": self.surface_count,
            "workflow_count": self.workflow_count,
            "no_dead_end_rule_count": self.no_dead_end_rule_count,
        }


def load_product_coherence(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical Phase 0.5 product coherence specification."""

    return json.loads((path or PRODUCT_COHERENCE_PATH).read_text(encoding="utf-8"))


def _contains_end_state(value: str) -> bool:
    lower = value.lower()
    return any(state in lower for state in REQUIRED_END_STATES)


def validate_product_coherence(spec: dict[str, Any] | None = None) -> ProductCoherenceReport:
    """Validate the Phase 0.5 product-lens and no-dead-end workflow rules."""

    data = spec or load_product_coherence()
    issues: list[str] = []
    version = str(data.get("version", ""))
    if not version:
        issues.append("missing version")

    lenses = data.get("product_lenses", [])
    lens_ids = {str(item.get("id", "")) for item in lenses if isinstance(item, dict)}
    missing_lenses = sorted(REQUIRED_LENSES - lens_ids)
    if missing_lenses:
        issues.append(f"missing product lenses: {missing_lenses}")
    for lens in lenses if isinstance(lenses, list) else []:
        lens_id = str(lens.get("id", ""))
        primary = lens.get("primary_surfaces", [])
        secondary = lens.get("secondary_surfaces", [])
        for field in ("label", "audience", "promise", "default_mode"):
            if not str(lens.get(field, "")).strip():
                issues.append(f"lens {lens_id} missing {field}")
        if not isinstance(primary, list) or not primary:
            issues.append(f"lens {lens_id} must define primary surfaces")
        if not isinstance(secondary, list):
            issues.append(f"lens {lens_id} secondary surfaces must be a list")
        if lens_id == "netcoin" and not REQUIRED_PUBLIC_SURFACES.issubset(set(primary)):
            issues.append("public NetCoin lens must keep wallet, explorer, and markets as primary surfaces")

    jobs = data.get("jobs", [])
    job_ids = {str(item.get("id", "")) for item in jobs if isinstance(item, dict)}
    missing_jobs = sorted(REQUIRED_JOBS - job_ids)
    if missing_jobs:
        issues.append(f"missing jobs: {missing_jobs}")
    for job in jobs if isinstance(jobs, list) else []:
        job_id = str(job.get("id", ""))
        if not str(job.get("plain_language", "")).strip():
            issues.append(f"job {job_id} missing plain_language")
        if not isinstance(job.get("surfaces", []), list) or not job.get("surfaces"):
            issues.append(f"job {job_id} must list surfaces")
        if not isinstance(job.get("primary_workflows", []), list) or not job.get("primary_workflows"):
            issues.append(f"job {job_id} must list primary workflows")

    ownership = data.get("surface_ownership", [])
    surface_names = {str(item.get("surface", "")) for item in ownership if isinstance(item, dict)}
    missing_surfaces = sorted(REQUIRED_SURFACES - surface_names)
    if missing_surfaces:
        issues.append(f"missing surface ownership: {missing_surfaces}")
    for item in ownership if isinstance(ownership, list) else []:
        surface = str(item.get("surface", ""))
        missing_fields = sorted(REQUIRED_EXIT_FIELDS - set(item.keys()))
        if missing_fields:
            issues.append(f"surface {surface} missing fields: {missing_fields}")
        if item.get("lens") not in lens_ids:
            issues.append(f"surface {surface} references unknown lens {item.get('lens')}")
        if item.get("job") not in job_ids:
            issues.append(f"surface {surface} references unknown job {item.get('job')}")
        for field in ("primary_action", "trust_signal", "next_step", "advanced_destination"):
            if not str(item.get(field, "")).strip():
                issues.append(f"surface {surface} must define non-empty {field}")
        if str(item.get("primary_action", "")).strip().lower() in {"done", "back", "close", "submit"}:
            issues.append(f"surface {surface} has a vague primary action")

    workflow_evidence = data.get("workflow_evidence", [])
    workflow_names = {str(item.get("workflow", "")) for item in workflow_evidence if isinstance(item, dict)}
    missing_workflows = sorted(REQUIRED_WORKFLOWS - workflow_names)
    if missing_workflows:
        issues.append(f"missing workflow evidence: {missing_workflows}")
    for item in workflow_evidence if isinstance(workflow_evidence, list) else []:
        workflow = str(item.get("workflow", ""))
        for field in ("starts_at", "ends_at", "success_reassurance", "failure_recovery"):
            if not str(item.get(field, "")).strip():
                issues.append(f"workflow {workflow} missing {field}")
        if item.get("must_not_dead_end") is not True:
            issues.append(f"workflow {workflow} must_not_dead_end must be true")
        if not _contains_end_state(str(item.get("ends_at", ""))):
            issues.append(f"workflow {workflow} must end in a recognized verification/recovery state")
        if len(str(item.get("success_reassurance", "")).split()) < 4:
            issues.append(f"workflow {workflow} success reassurance is too vague")
        if len(str(item.get("failure_recovery", "")).split()) < 4:
            issues.append(f"workflow {workflow} failure recovery is too vague")

    rules = data.get("no_dead_end_rules", [])
    if not isinstance(rules, list) or len(rules) < 8:
        issues.append("no_dead_end_rules must include at least eight rules")
    if not any("Every page must define one owner job" in str(rule) for rule in rules):
        issues.append("no-dead-end rules must require owner job and primary action")
    if not any("Every empty state" in str(rule) for rule in rules):
        issues.append("no-dead-end rules must cover empty states")
    if not any("Every success state" in str(rule) for rule in rules):
        issues.append("no-dead-end rules must cover success states")

    contract = data.get("page_exit_contract", {})
    required_fields = set(contract.get("required_fields", [])) if isinstance(contract, dict) else set()
    if not REQUIRED_EXIT_FIELDS.issubset(required_fields):
        issues.append(f"page exit contract missing fields: {sorted(REQUIRED_EXIT_FIELDS - required_fields)}")
    forbidden = set(contract.get("forbidden_exit_labels", [])) if isinstance(contract, dict) else set()
    if not {"Done", "Back", "Close", "Submit"}.issubset(forbidden):
        issues.append("page exit contract must forbid vague exit labels")
    if int(contract.get("minimum_reassurance_words", 0)) < 4:
        issues.append("page exit contract must require meaningful reassurance copy")

    criteria = data.get("success_criteria", [])
    if not isinstance(criteria, list) or len(criteria) < 6:
        issues.append("success_criteria must include at least six outcomes")

    return ProductCoherenceReport(
        ok=not issues,
        version=version,
        issues=issues,
        lens_count=len(lens_ids),
        job_count=len(job_ids),
        surface_count=len(surface_names),
        workflow_count=len(workflow_names),
        no_dead_end_rule_count=len(rules) if isinstance(rules, list) else 0,
    )


if __name__ == "__main__":
    print(json.dumps(validate_product_coherence().as_dict(), indent=2, sort_keys=True))
