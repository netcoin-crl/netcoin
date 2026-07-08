"""Wallet policy profiles and approval receipts.

The transaction simulator explains a transaction. This module turns that preview
into reusable wallet policy profiles, approval requests, and tamper-evident
receipts that can be shown in the browser wallet or saved by operators.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from .wallet_risk import policy_decision


@dataclass(frozen=True)
class WalletPolicyProfile:
    name: str
    max_fee_sats: int = 100_000
    max_risk_level: str = "medium"
    require_no_critical: bool = True
    max_recipient_outputs: int = 25
    max_input_count: int = 50
    require_manual_review_above_sats: int = 10_000_000_000

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


POLICY_PROFILES: dict[str, WalletPolicyProfile] = {
    "starter": WalletPolicyProfile(
        "starter",
        max_fee_sats=25_000,
        max_risk_level="low",
        max_input_count=15,
        require_manual_review_above_sats=1_000_000_000,
    ),
    "standard": WalletPolicyProfile("standard"),
    "operator": WalletPolicyProfile(
        "operator",
        max_fee_sats=500_000,
        max_risk_level="high",
        max_input_count=200,
        require_manual_review_above_sats=100_000_000_000,
    ),
}


def get_policy_profile(name: str | None = None) -> WalletPolicyProfile:
    key = str(name or "standard").lower()
    if key not in POLICY_PROFILES:
        raise ValueError(f"unknown wallet policy profile: {name}")
    return POLICY_PROFILES[key]


def evaluate_with_profile(preview: dict[str, Any], profile: WalletPolicyProfile | str = "standard") -> dict[str, Any]:
    if isinstance(profile, str):
        profile = get_policy_profile(profile)
    decision = policy_decision(
        preview,
        max_fee_sats=profile.max_fee_sats,
        max_risk_level=profile.max_risk_level,
        require_no_critical=profile.require_no_critical,
    )
    reasons = list(decision.get("reasons", []))
    if len(preview.get("recipient_outputs", [])) > profile.max_recipient_outputs:
        reasons.append("too_many_recipient_outputs")
    if len(preview.get("inputs", [])) > profile.max_input_count:
        reasons.append("too_many_inputs")
    if (
        int(preview.get("output_sats", 0) or 0) >= profile.require_manual_review_above_sats
        and decision.get("action") == "allow"
    ):
        decision["action"] = "review"
        reasons.append("amount_requires_manual_review")
    if reasons and decision.get("action") == "allow":
        decision["action"] = "block" if any(reason.startswith("too_many") for reason in reasons) else "review"
    decision["reasons"] = reasons
    decision["profile"] = profile.to_dict()
    return decision


def approval_request(
    preview: dict[str, Any], profile: WalletPolicyProfile | str = "standard", *, requester: str = "wallet"
) -> dict[str, Any]:
    decision = evaluate_with_profile(preview, profile)
    body = {
        "type": "netcoin-wallet-approval-v1",
        "created_at": int(time.time()),
        "requester": requester,
        "txid": preview.get("txid"),
        "fee_sats": int(preview.get("fee_sats", 0) or 0),
        "output_sats": int(preview.get("output_sats", 0) or 0),
        "risk_score": int(preview.get("risk_score", 0) or 0),
        "risk_level": preview.get("risk_level", "low"),
        "decision": decision,
    }
    body["request_hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return body


def approval_receipt(request: dict[str, Any], *, approver: str, approved: bool, note: str = "") -> dict[str, Any]:
    receipt = {
        "type": "netcoin-wallet-approval-receipt-v1",
        "created_at": int(time.time()),
        "request_hash": request.get("request_hash"),
        "txid": request.get("txid"),
        "approver": approver,
        "approved": bool(approved),
        "note": note[:1000],
    }
    receipt["receipt_hash"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return receipt


def verify_approval_receipt(request: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    expected = request.get("request_hash")
    ok = bool(expected and receipt.get("request_hash") == expected)
    return {
        "ok": ok,
        "request_hash": expected,
        "receipt_hash": receipt.get("receipt_hash"),
        "approved": bool(receipt.get("approved")),
    }
