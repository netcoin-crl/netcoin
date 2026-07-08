"""Operational runbook automation and diagnostic bundle helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .ops_incidents import runbook_for_alert


def recommended_actions(alerts: list[dict[str, Any]], *, include_commands: bool = True) -> dict[str, Any]:
    """Return de-duplicated operator actions for a set of alerts."""
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for alert in alerts:
        alert_name = str(alert.get("alert") or alert.get("name") or "UnknownAlert")
        severity = str(alert.get("severity") or "warning")
        runbook = runbook_for_alert(alert_name)["steps"]
        for idx, step in enumerate(runbook, start=1):
            key = f"{alert_name}:{step}"
            if key in seen:
                continue
            seen.add(key)
            item: dict[str, Any] = {"alert": alert_name, "severity": severity, "step": step, "order": idx}
            if include_commands:
                item["command_hint"] = command_hint_for_step(step)
            actions.append(item)
    severity_rank = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    actions.sort(key=lambda item: (severity_rank.get(item["severity"], 9), item["alert"], item["order"]))
    return {"action_count": len(actions), "actions": actions}


def command_hint_for_step(step: str) -> str:
    lowered = step.lower()
    if "peer" in lowered:
        return "netcoin status --peers"
    if "faucet" in lowered:
        return "python tools/faucet_admin.py status"
    if "mempool" in lowered or "fee" in lowered:
        return "netcoin mempool-info"
    if "webhook" in lowered:
        return "netcoin app-webhook-queue"
    if "diagnostic" in lowered or "logs" in lowered:
        return "make upgrade-healthcheck"
    return "review docs/runbooks and service logs"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, val in value.items():
            if any(
                secret in str(key).lower()
                for secret in ("secret", "token", "password", "passphrase", "api_key", "private")
            ):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(val)
        return redacted
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def diagnostic_bundle(
    *,
    metrics: dict[str, Any] | None = None,
    alerts: list[dict[str, Any]] | None = None,
    incidents: list[dict[str, Any]] | None = None,
    peer_health: dict[str, Any] | None = None,
    sync_health: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    alerts = alerts or []
    bundle = {
        "type": "netcoin-ops-diagnostic-bundle-v1",
        "created_at": int(time.time()),
        "metrics": _redact(metrics or {}),
        "alerts": _redact(alerts),
        "incidents": _redact(incidents or []),
        "peer_health": _redact(peer_health or {}),
        "sync_health": _redact(sync_health or {}),
        "recommended_actions": recommended_actions(alerts),
        "extra": _redact(extra or {}),
    }
    status = "healthy"
    if any(str(a.get("severity")) == "critical" for a in alerts):
        status = "critical"
    elif alerts or incidents:
        status = "degraded"
    bundle["status"] = status
    return bundle


def write_diagnostic_bundle(path: str | Path, **kwargs: Any) -> dict[str, Any]:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    bundle = diagnostic_bundle(**kwargs)
    out.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(out), "status": bundle["status"], "alert_count": len(bundle.get("alerts", []))}
