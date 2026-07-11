"""Public testnet incident/runbook history validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_INCIDENT_FIELDS = ["id", "severity", "detected_at", "runbook_ref", "summary", "status"]
ALLOWED_SEVERITIES = {"SEV0", "SEV1", "SEV2", "SEV3", "none"}


def load_history(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_incident_history(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not payload.get("public_testnet_start"):
        issues.append("missing public_testnet_start")
    if not payload.get("runbook_links"):
        issues.append("missing runbook_links")
    incidents = payload.get("incidents")
    no_incident = payload.get("no_incident_attestation")
    if not incidents and not no_incident:
        issues.append("provide incidents or no_incident_attestation")
    if incidents and not isinstance(incidents, list):
        issues.append("incidents must be a list")
    for item in incidents or []:
        if not isinstance(item, dict):
            issues.append("incident entry must be object")
            continue
        for field in REQUIRED_INCIDENT_FIELDS:
            if not item.get(field):
                issues.append(f"incident missing {field}")
        if item.get("severity") not in ALLOWED_SEVERITIES:
            issues.append(f"incident {item.get('id')} invalid severity")
        if item.get("status") not in {"mitigated", "resolved", "monitoring", "postmortem-complete"}:
            issues.append(f"incident {item.get('id')} invalid status")
        if item.get("status") in {"resolved", "postmortem-complete"} and not item.get("postmortem_ref"):
            issues.append(f"incident {item.get('id')} resolved without postmortem_ref")
    return issues


def source_history_template() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "source",
        "required_top_level": ["public_testnet_start", "runbook_links", "incidents or no_incident_attestation"],
        "required_incident_fields": REQUIRED_INCIDENT_FIELDS,
    }
