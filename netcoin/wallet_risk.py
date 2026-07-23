"""Wallet transaction and address risk-scoring helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from .params import DUST_THRESHOLD


@dataclass(frozen=True)
class RiskWarning:
    code: str
    severity: str
    message: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def address_similarity(a: str, b: str) -> float:
    a = str(a or "")
    b = str(b or "")
    if not a or not b:
        return 0.0
    prefix = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        prefix += 1
    suffix = 0
    for x, y in zip(reversed(a), reversed(b), strict=False):
        if x != y:
            break
        suffix += 1
    return min(1.0, (prefix + suffix) / max(len(a), len(b)))


def detect_address_poisoning(
    destination: str, recent_addresses: Iterable[str], *, threshold: float = 0.42
) -> dict[str, Any]:
    """Detect look-alike addresses commonly used in address-poisoning attacks."""
    matches = []
    for candidate in recent_addresses:
        candidate = str(candidate)
        if candidate == destination:
            continue
        score = address_similarity(destination, candidate)
        if score >= threshold:
            matches.append({"address": candidate, "similarity": round(score, 4)})
    matches.sort(key=lambda item: item["similarity"], reverse=True)
    return {"suspicious": bool(matches), "matches": matches[:10], "threshold": threshold}


def score_warnings(warnings: Iterable[RiskWarning | dict[str, Any]]) -> dict[str, Any]:
    weights = {"info": 3, "low": 8, "medium": 18, "high": 35, "critical": 55}
    total = 0
    items = []
    for warning in warnings:
        data = warning.to_dict() if hasattr(warning, "to_dict") else dict(warning)
        items.append(data)
        total += weights.get(str(data.get("severity", "low")), 8)
    score = min(100, total)
    level = "low" if score < 20 else "medium" if score < 50 else "high" if score < 80 else "critical"
    return {"risk_score": score, "risk_level": level, "warnings": items, "warning_count": len(items)}


def output_dust_warning(address: str, amount_sats: int) -> RiskWarning | None:
    if int(amount_sats) and int(amount_sats) < DUST_THRESHOLD:
        return RiskWarning(
            "dust_output",
            "medium",
            "Output is below the dust threshold.",
            {"address": address, "amount_sats": int(amount_sats), "dust_threshold": DUST_THRESHOLD},
        )
    return None


RISK_LEVELS = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def policy_decision(
    preview: dict[str, Any],
    *,
    max_fee_sats: int = 100_000,
    max_risk_level: str = "medium",
    require_no_critical: bool = True,
) -> dict[str, Any]:
    """Turn a transaction preview into an allow/review/block policy decision."""
    warnings = list(preview.get("warnings", []))
    risk_level = str(preview.get("risk_level", "low"))
    max_allowed = RISK_LEVELS.get(max_risk_level, 2)
    fee_sats = int(preview.get("fee_sats", 0) or 0)
    reasons: list[str] = []
    if fee_sats > int(max_fee_sats):
        reasons.append("fee_exceeds_policy")
    if RISK_LEVELS.get(risk_level, 1) > max_allowed:
        reasons.append("risk_level_exceeds_policy")
    if require_no_critical and any(str(w.get("severity")) == "critical" for w in warnings):
        reasons.append("critical_warning_present")
    action = "allow" if not reasons and risk_level == "low" else "review" if not reasons else "block"
    return {
        "action": action,
        "reasons": reasons,
        "risk_level": risk_level,
        "fee_sats": fee_sats,
        "max_fee_sats": int(max_fee_sats),
    }


def safety_report(
    preview: dict[str, Any], *, policy: dict[str, Any] | None = None, operator_note: str = ""
) -> dict[str, Any]:
    """Create a stable wallet-safety report that can be exported or signed."""
    import hashlib
    import json
    import time

    decision = policy_decision(preview, **(policy or {}))
    body = {
        "report_type": "netcoin-wallet-safety-v1",
        "created_at": int(time.time()),
        "txid": preview.get("txid"),
        "fee_sats": int(preview.get("fee_sats", 0) or 0),
        "risk_score": int(preview.get("risk_score", 0) or 0),
        "risk_level": preview.get("risk_level", "low"),
        "warning_count": int(preview.get("warning_count", 0) or 0),
        "decision": decision,
        "operator_note": operator_note[:1000],
    }
    body["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return body


def sign_safety_report(report: dict[str, Any], wallet: Any) -> dict[str, Any]:
    """Attach a wallet signmessage proof to a safety report."""
    from .crypto import sign_message

    message = "NetCoin wallet safety report\n" + str(report.get("sha256", ""))
    signature = sign_message(wallet.private_key, message)
    return dict(report) | {
        "signature_type": "netcoin-signmessage-v1",
        "signer_address": wallet.address,
        "message": message,
        "signature": signature,
    }
