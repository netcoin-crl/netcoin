"""Typed prediction-market model helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

MARKET_STATES = ("draft", "open", "paused", "closed", "resolving", "disputed", "resolved", "settled", "canceled")
ORDER_TIME_IN_FORCE = ("GTC", "IOC", "FOK", "DAY", "GTD")


@dataclass(frozen=True)
class ResolutionEvidence:
    url: str
    title: str = ""
    timestamp: int = 0
    submitter: str = "operator"
    source_type: str = "url"
    sha256: str = ""
    comments: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_terminal_state(state: str) -> bool:
    return state in {"resolved", "settled", "canceled"}


def normalize_market_state(state: str) -> str:
    state = str(state or "open").lower()
    if state not in MARKET_STATES:
        raise ValueError(f"unknown market state: {state}")
    return state
