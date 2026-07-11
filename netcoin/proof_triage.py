"""Phase 1 proof triage and CI alignment helpers.

This layer does not run expensive proof gates. It reads the reports created by
Phase 1 tools, classifies blockers, maps them to owners and next commands, and
checks that CI has a matching proof-hardening workflow. The goal is to make the
next local action obvious instead of leaving scattered logs for the developer to
interpret manually.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = ROOT / "architecture" / "proof-triage.json"
ALLOWED_SEVERITIES = {"P0", "P1", "P2"}
REQUIRED_GATE_IDS = {
    "python-reference",
    "rust-workspace",
    "rust-parity",
    "typescript-api",
    "browser-e2e",
    "accessibility",
    "security-release",
    "phase0-guardrails",
}
REQUIRED_INPUTS = {
    "local_proof_report",
    "evidence_bundle",
    "release_readiness_scorecard",
    "proof_hardening_manifest",
    "strict_proof_manifest",
}
REQUIRED_OUTPUTS = {"triage_report", "human_summary"}


@dataclass(frozen=True)
class TriageItem:
    """One classified proof blocker or follow-up item."""

    gate_id: str
    owner: str
    status: str
    blocker_class: str
    severity: str
    meaning: str
    next_command: str
    remediation: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "owner": self.owner,
            "status": self.status,
            "class": self.blocker_class,
            "severity": self.severity,
            "meaning": self.meaning,
            "next_command": self.next_command,
            "remediation": self.remediation,
            "source": self.source,
        }


def load_proof_triage_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_proof_triage_manifest(manifest: dict[str, Any], *, root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    if manifest.get("phase") != "Phase 1 - Proof Triage and CI Alignment":
        issues.append("phase must be 'Phase 1 - Proof Triage and CI Alignment'")
    if not str(manifest.get("version", "")).startswith("0.39"):
        issues.append("version must stay on the v0.39 Phase 1 line")
    if manifest.get("inherits_from") != "architecture/local-proof-runner.json":
        issues.append("proof triage must inherit architecture/local-proof-runner.json")

    inputs = manifest.get("inputs")
    if not isinstance(inputs, dict):
        issues.append("inputs must be an object")
    else:
        missing_inputs = sorted(REQUIRED_INPUTS - set(inputs))
        if missing_inputs:
            issues.append("inputs missing: " + ", ".join(missing_inputs))
        for key in ["proof_hardening_manifest", "strict_proof_manifest"]:
            path = inputs.get(key)
            if path and not (root / str(path)).exists():
                issues.append(f"input {key} path does not exist: {path}")

    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        issues.append("outputs must be an object")
    else:
        missing_outputs = sorted(REQUIRED_OUTPUTS - set(outputs))
        if missing_outputs:
            issues.append("outputs missing: " + ", ".join(missing_outputs))

    rules = manifest.get("classification_rules")
    if not isinstance(rules, list) or len(rules) < 6:
        issues.append("classification_rules must include at least six classes")
    else:
        seen_classes: set[str] = set()
        for rule in rules:
            if not isinstance(rule, dict):
                issues.append("classification rule must be an object")
                continue
            cls = str(rule.get("class", ""))
            if not cls:
                issues.append("classification rule missing class")
            if cls in seen_classes:
                issues.append(f"duplicate classification class: {cls}")
            seen_classes.add(cls)
            if rule.get("severity") not in ALLOWED_SEVERITIES:
                issues.append(f"classification {cls} has invalid severity")
            if not isinstance(rule.get("matches"), list) or not rule.get("matches"):
                issues.append(f"classification {cls} missing matches")
            for key in ["meaning", "default_next_action"]:
                if not rule.get(key):
                    issues.append(f"classification {cls} missing {key}")

    owners = manifest.get("gate_owners")
    if not isinstance(owners, dict):
        issues.append("gate_owners must be an object")
    else:
        missing_owners = sorted(REQUIRED_GATE_IDS - set(owners))
        if missing_owners:
            issues.append("gate_owners missing: " + ", ".join(missing_owners))

    commands = manifest.get("next_command_map")
    if not isinstance(commands, dict):
        issues.append("next_command_map must be an object")
    else:
        missing_commands = sorted(REQUIRED_GATE_IDS - set(commands))
        if missing_commands:
            issues.append("next_command_map missing: " + ", ".join(missing_commands))

    ci = manifest.get("ci_alignment")
    if not isinstance(ci, dict):
        issues.append("ci_alignment must be an object")
    else:
        workflow = ci.get("workflow")
        if not workflow or not (root / str(workflow)).exists():
            issues.append("ci_alignment.workflow must point to an existing workflow")
        jobs = ci.get("required_jobs")
        if not isinstance(jobs, list) or len(jobs) < 5:
            issues.append("ci_alignment.required_jobs must list proof jobs")
        if not ci.get("local_to_ci_rule"):
            issues.append("ci_alignment.local_to_ci_rule is required")

    criteria = manifest.get("phase1_4_exit_criteria")
    if not isinstance(criteria, list) or len(criteria) < 5:
        issues.append("phase1_4_exit_criteria must list concrete exit criteria")

    inherited = root / "architecture" / "local-proof-runner.json"
    if not inherited.exists():
        issues.append("inherited local-proof-runner manifest is missing")
    return issues


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _rule_for(rule_text: str, manifest: dict[str, Any]) -> dict[str, Any]:
    haystack = rule_text.lower()
    fallback = {
        "class": "command-failure",
        "severity": "P0",
        "meaning": "The proof gate did not produce a clean pass.",
        "default_next_action": "Open the per-gate log, fix the failing command, and rerun the same gate.",
    }
    for rule in manifest.get("classification_rules", []):
        for needle in rule.get("matches", []):
            if str(needle).lower() in haystack:
                return rule
    return fallback


def _status_text(gate: dict[str, Any]) -> str:
    return " ".join(
        str(part)
        for part in [
            gate.get("status"),
            gate.get("gate_id"),
            gate.get("blocked_reason"),
            gate.get("class"),
            gate.get("remediation"),
            json.dumps(gate.get("commands", []), sort_keys=True)[:1200] if gate.get("commands") else "",
            json.dumps(gate.get("missing_paths", []), sort_keys=True) if gate.get("missing_paths") else "",
        ]
        if part
    )


def _item_from_gate(gate: dict[str, Any], *, manifest: dict[str, Any], source: str) -> TriageItem:
    gate_id = str(gate.get("gate_id") or gate.get("id") or "unknown")
    status = str(gate.get("status", "unknown"))
    text = _status_text(gate)
    # Command failures should not be reclassified as missing-tool merely because
    # their remediation mentions npm/cargo. Blocked gates still use the full
    # text so explicit missing-tool reasons win.
    if status == "fail":
        rule = next((item for item in manifest.get("classification_rules", []) if item.get("class") == "command-failure"), _rule_for(text, manifest))
    else:
        rule = _rule_for(text, manifest)
    owner = str(manifest.get("gate_owners", {}).get(gate_id, "Unassigned"))
    next_command = str(manifest.get("next_command_map", {}).get(gate_id, rule.get("default_next_action", "rerun the gate")))
    remediation = str(gate.get("remediation") or rule.get("default_next_action") or "rerun the gate")
    return TriageItem(
        gate_id=gate_id,
        owner=owner,
        status=status,
        blocker_class=str(rule.get("class")),
        severity=str(rule.get("severity", "P1")),
        meaning=str(rule.get("meaning", "Proof item needs attention.")),
        next_command=next_command,
        remediation=remediation,
        source=source,
    )


def _items_from_local_report(report: dict[str, Any], *, manifest: dict[str, Any]) -> list[TriageItem]:
    items: list[TriageItem] = []
    for gate in report.get("gates", []):
        status = str(gate.get("status"))
        if status in {"pass"}:
            continue
        if report.get("profile") != "strict" and status == "source_only":
            items.append(_item_from_gate(gate, manifest=manifest, source="local_proof_report"))
        elif status in {"fail", "blocked", "not_run", "source_only"}:
            items.append(_item_from_gate(gate, manifest=manifest, source="local_proof_report"))
    return items


def _items_from_evidence_bundle(bundle: dict[str, Any], *, manifest: dict[str, Any]) -> list[TriageItem]:
    items: list[TriageItem] = []
    for blocker in bundle.get("blockers", []):
        if isinstance(blocker, dict):
            gate_id = str(blocker.get("gate_id", "unknown"))
            gate = {"gate_id": gate_id, "status": blocker.get("class", "blocked"), "class": blocker.get("class"), "missing_paths": blocker.get("paths", [])}
            items.append(_item_from_gate(gate, manifest=manifest, source="evidence_bundle"))
    for gate in bundle.get("gates", []):
        status = str(gate.get("status"))
        if status in {"fail", "blocked", "source_only"}:
            items.append(_item_from_gate(gate, manifest=manifest, source="evidence_bundle"))
    return items


def _dedupe_items(items: list[TriageItem]) -> list[TriageItem]:
    severity_rank = {"P0": 0, "P1": 1, "P2": 2}
    best: dict[tuple[str, str], TriageItem] = {}
    for item in items:
        key = (item.gate_id, item.blocker_class)
        current = best.get(key)
        if current is None or severity_rank.get(item.severity, 9) < severity_rank.get(current.severity, 9):
            best[key] = item
    return sorted(best.values(), key=lambda item: (severity_rank.get(item.severity, 9), item.gate_id, item.blocker_class))


def check_ci_alignment(manifest: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    ci = manifest.get("ci_alignment", {})
    workflow_path = root / str(ci.get("workflow", ""))
    required_jobs = [str(job) for job in ci.get("required_jobs", [])]
    text = workflow_path.read_text(encoding="utf-8") if workflow_path.exists() else ""
    missing = [job for job in required_jobs if job not in text]
    # The workflow may use aggregate job names for source fallbacks. We still
    # expose missing names as alignment items instead of pretending they pass.
    return {
        "ok": workflow_path.exists() and not missing,
        "workflow": str(ci.get("workflow", "")),
        "required_jobs": required_jobs,
        "missing_jobs": missing,
        "rule": ci.get("local_to_ci_rule"),
    }


def build_proof_triage_report(
    manifest: dict[str, Any],
    *,
    root: Path = ROOT,
    local_report_path: str | None = None,
    evidence_bundle_path: str | None = None,
) -> dict[str, Any]:
    """Build a proof triage report from existing local proof/evidence reports."""

    issues = validate_proof_triage_manifest(manifest, root=root)
    if issues:
        return {"ok": False, "manifest_issues": issues}

    inputs = manifest.get("inputs", {})
    local_path = root / (local_report_path or str(inputs.get("local_proof_report")))
    evidence_path = root / (evidence_bundle_path or str(inputs.get("evidence_bundle")))
    local = _read_json(local_path)
    evidence = _read_json(evidence_path)

    items: list[TriageItem] = []
    source_notes: list[str] = []
    if local is None:
        source_notes.append(f"missing local proof report: {local_path.relative_to(root) if local_path.is_absolute() and root in local_path.parents else local_path}")
    else:
        items.extend(_items_from_local_report(local, manifest=manifest))
    if evidence is None:
        source_notes.append(f"missing evidence bundle: {evidence_path.relative_to(root) if evidence_path.is_absolute() and root in evidence_path.parents else evidence_path}")
    else:
        items.extend(_items_from_evidence_bundle(evidence, manifest=manifest))

    ci_alignment = check_ci_alignment(manifest, root=root)
    if not ci_alignment.get("ok"):
        for job in ci_alignment.get("missing_jobs", []):
            items.append(
                TriageItem(
                    gate_id=str(job),
                    owner="CI/release ops",
                    status="missing_ci_alignment",
                    blocker_class="not-run",
                    severity="P2",
                    meaning="The proof-hardening CI workflow does not clearly name this required proof job.",
                    next_command="Update .github/workflows/proof-hardening.yml so local and CI proof gates align.",
                    remediation="Add or document the missing CI proof job/fallback.",
                    source="ci_alignment",
                )
            )

    deduped = _dedupe_items(items)
    severity_counts = {severity: 0 for severity in sorted(ALLOWED_SEVERITIES)}
    class_counts: dict[str, int] = {}
    for item in deduped:
        severity_counts[item.severity] = severity_counts.get(item.severity, 0) + 1
        class_counts[item.blocker_class] = class_counts.get(item.blocker_class, 0) + 1
    strict_ready = not deduped and not source_notes and ci_alignment.get("ok")
    return {
        "ok": True,
        "version": manifest.get("version"),
        "phase": manifest.get("phase"),
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "strict_ready": strict_ready,
        "claim_level": "strict-local-candidate" if strict_ready else "triaged-source-checked-testnet",
        "source_notes": source_notes,
        "item_count": len(deduped),
        "severity_counts": severity_counts,
        "class_counts": class_counts,
        "ci_alignment": ci_alignment,
        "items": [item.to_dict() for item in deduped],
        "next_priority": deduped[0].to_dict() if deduped else None,
    }


def proof_triage_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": report.get("ok"),
        "version": report.get("version"),
        "phase": report.get("phase"),
        "claim_level": report.get("claim_level"),
        "strict_ready": report.get("strict_ready"),
        "item_count": report.get("item_count"),
        "severity_counts": report.get("severity_counts"),
        "ci_alignment_ok": (report.get("ci_alignment") or {}).get("ok"),
        "next_priority": report.get("next_priority"),
    }


def render_triage_markdown(report: dict[str, Any]) -> str:
    lines = ["# NetCoin Proof Triage Summary", ""]
    lines.append(f"Version: `{report.get('version')}`")
    lines.append(f"Claim level: `{report.get('claim_level')}`")
    lines.append(f"Strict ready: `{report.get('strict_ready')}`")
    lines.append("")
    if report.get("source_notes"):
        lines.append("## Source notes")
        for note in report.get("source_notes", []):
            lines.append(f"- {note}")
        lines.append("")
    next_priority = report.get("next_priority")
    if next_priority:
        lines.append("## Next priority")
        lines.append(f"- **{next_priority['severity']} {next_priority['gate_id']}**: {next_priority['meaning']}")
        lines.append(f"- Run: `{next_priority['next_command']}`")
        lines.append("")
    lines.append("## Items")
    items = report.get("items", [])
    if not items:
        lines.append("No triage items. Strict proof appears ready from available evidence.")
    else:
        for item in items:
            lines.append(f"- **{item['severity']}** `{item['gate_id']}` ({item['owner']}) - {item['class']}: {item['meaning']}")
            lines.append(f"  - Next: `{item['next_command']}`")
    lines.append("")
    return "\n".join(lines)
