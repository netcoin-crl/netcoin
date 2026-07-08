"""Faucet Abuse Control midlevel competitive implementation hooks.

Purpose: Faucet anti-abuse dashboard, captcha/proof-of-work, fingerprinting, hot-wallet limits, alerts, queues, and emergency pause.

This module now targets NetCoin's 5/10 maturity baseline: deterministic
testnet/dev implementation hooks, validation helpers, operator controls, and
smoke checks. It still does not claim production/mainnet readiness.
"""

from __future__ import annotations

from typing import Any

from .level5 import area_smoke, level5_area_controls, level5_features, level5_readiness_gates
from .registry import get_area

AREA_SLUG = "faucet_abuse"


def area() -> Any:
    """Return the registry entry for this competitive feature area."""
    return get_area(AREA_SLUG)


def feature_matrix() -> list[dict[str, Any]]:
    """Return serializable midlevel feature rows for dashboards and tests."""
    return [feature.asdict() for feature in level5_features(AREA_SLUG)]


def default_controls() -> dict[str, Any]:
    """Return safe testnet/dev controls for 5/10 maturity."""
    return level5_area_controls(AREA_SLUG)


def readiness_gates() -> list[str]:
    """Gates required to preserve the 5/10 baseline."""
    return level5_readiness_gates()


def smoke_check() -> dict[str, Any]:
    """Run this area's deterministic midlevel smoke check."""
    return area_smoke(AREA_SLUG)
