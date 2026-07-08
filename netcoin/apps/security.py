"""Security/compliance helpers for app-layer features."""

from __future__ import annotations

PREDICTION_MARKET_WARNING = (
    "Demo/testnet-only event market. Do not use for regulated real-money " "markets without legal and security review."
)

RESTRICTED_MARKET_TERMS = {
    "election",
    "political",
    "sportsbook",
    "sports betting",
    "terror",
    "assassination",
}


def market_compliance_record(*, mode: str, legal_acknowledged: bool, operator_override: bool) -> dict[str, object]:
    return {
        "status": "demo_restricted",
        "mode": mode,
        "legal_acknowledged": legal_acknowledged,
        "operator_override": operator_override,
        "real_money_enabled": False,
        "requires_legal_review_before_mainnet": True,
        "warning": PREDICTION_MARKET_WARNING,
    }
