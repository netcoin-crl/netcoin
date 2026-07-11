"""Strict proof execution manifest helpers for Phase 1.

This layer validates the local/CI execution playbook that bridges sandbox
source checks to strict professional-candidate evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = ROOT / "architecture" / "strict-proof-execution.json"
REQUIRED_TOOL_IDS = {"python", "cargo", "node-npm", "playwright"}
REQUIRED_COMMAND_GROUPS = {
    "python-reference",
    "rust-workspace",
    "rust-parity",
    "typescript-api",
    "browser-e2e",
    "accessibility",
    "security-release",
    "release-readiness",
}
REQUIRED_CI_JOBS = {
    "python-source-proof",
    "rust-strict-proof",
    "typescript-api-proof",
    "browser-accessibility-proof",
    "release-readiness-scorecard",
}


def load_strict_proof_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_strict_proof_manifest(manifest: dict[str, Any], *, root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    if manifest.get("phase") != "Phase 1 - Strict Proof Execution":
        issues.append("phase must be 'Phase 1 - Strict Proof Execution'")
    if not str(manifest.get("version", "")).startswith("0.39"):
        issues.append("version must stay on the v0.39 Phase 1 line")
    if manifest.get("inherits_from") != "architecture/proof-hardening.json":
        issues.append("strict proof execution must inherit architecture/proof-hardening.json")

    tools = manifest.get("tool_requirements")
    if not isinstance(tools, list) or not tools:
        issues.append("tool_requirements must be a non-empty list")
        tool_ids: set[str] = set()
    else:
        tool_ids = {str(item.get("id")) for item in tools if isinstance(item, dict)}
        missing_tools = sorted(REQUIRED_TOOL_IDS - tool_ids)
        if missing_tools:
            issues.append("missing tool requirements: " + ", ".join(missing_tools))
        for item in tools:
            if not isinstance(item, dict):
                issues.append("tool requirement must be an object")
                continue
            if not item.get("verify_command"):
                issues.append(f"tool {item.get('id', '<unknown>')} missing verify_command")

    profiles = manifest.get("local_profiles")
    if not isinstance(profiles, dict) or not {"macos", "linux", "sandbox"}.issubset(profiles):
        issues.append("local_profiles must include macos, linux, and sandbox")
    else:
        for profile_id, profile in profiles.items():
            if not isinstance(profile, dict):
                issues.append(f"profile {profile_id} must be an object")
                continue
            if not profile.get("strict_command"):
                issues.append(f"profile {profile_id} missing strict_command")

    groups = manifest.get("strict_command_groups")
    if not isinstance(groups, list) or not groups:
        issues.append("strict_command_groups must be a non-empty list")
        group_ids: set[str] = set()
    else:
        group_ids = {str(item.get("id")) for item in groups if isinstance(item, dict)}
        missing_groups = sorted(REQUIRED_COMMAND_GROUPS - group_ids)
        if missing_groups:
            issues.append("missing strict command groups: " + ", ".join(missing_groups))
        for item in groups:
            if not isinstance(item, dict):
                issues.append("strict command group must be an object")
                continue
            if not item.get("commands") or not all(isinstance(cmd, str) and cmd for cmd in item.get("commands", [])):
                issues.append(f"group {item.get('id', '<unknown>')} must list commands")
            if not item.get("evidence"):
                issues.append(f"group {item.get('id', '<unknown>')} must list evidence artifacts")

    workflows = manifest.get("ci_workflows")
    if not isinstance(workflows, list) or not workflows:
        issues.append("ci_workflows must be a non-empty list")
    else:
        for workflow in workflows:
            if not isinstance(workflow, dict):
                issues.append("ci workflow must be an object")
                continue
            path = workflow.get("path")
            if not path:
                issues.append("ci workflow missing path")
                continue
            wf_path = root / str(path)
            if not wf_path.exists():
                issues.append(f"ci workflow file does not exist: {path}")
            required_jobs = set(workflow.get("required_jobs", []))
            missing_jobs = sorted(REQUIRED_CI_JOBS - required_jobs)
            if missing_jobs:
                issues.append(f"ci workflow {path} missing required_jobs: {', '.join(missing_jobs)}")

    blockers = manifest.get("blocker_classes")
    if not isinstance(blockers, list) or len(blockers) < 4:
        issues.append("blocker_classes must explain the main strict-proof blocker types")

    return issues


def strict_command_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    groups = manifest.get("strict_command_groups", [])
    return {
        "version": manifest.get("version"),
        "phase": manifest.get("phase"),
        "group_count": len(groups),
        "command_count": sum(len(group.get("commands", [])) for group in groups if isinstance(group, dict)),
        "evidence_count": sum(len(group.get("evidence", [])) for group in groups if isinstance(group, dict)),
        "groups": [group.get("id") for group in groups if isinstance(group, dict)],
    }
