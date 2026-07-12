"""Version-bits rehearsal model for future NetCoin soft forks.

This module is intentionally not wired into consensus. It lets operators model
BIP9-style signaling windows and produce rehearsal evidence before any consensus
change is proposed through a NIP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

DEFINED = "defined"
STARTED = "started"
LOCKED_IN = "locked_in"
ACTIVE = "active"
FAILED = "failed"

VALID_STATES = {DEFINED, STARTED, LOCKED_IN, ACTIVE, FAILED}


@dataclass(frozen=True)
class VersionBitsDeployment:
    name: str
    bit: int
    start_height: int
    timeout_height: int
    period: int = 2016
    threshold: int = 1916

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.name:
            issues.append("deployment name is required")
        if self.bit < 0 or self.bit > 28:
            issues.append("version bit must be between 0 and 28")
        if self.start_height < 0:
            issues.append("start_height must be non-negative")
        if self.timeout_height <= self.start_height:
            issues.append("timeout_height must be greater than start_height")
        if self.period <= 0:
            issues.append("period must be positive")
        if self.threshold <= 0 or self.threshold > self.period:
            issues.append("threshold must be in 1..period")
        return issues


def _coerce_versions(versions: Iterable[int]) -> tuple[list[int], list[str]]:
    normalized: list[int] = []
    issues: list[str] = []
    for index, version in enumerate(versions):
        try:
            value = int(version)
        except (TypeError, ValueError):
            issues.append(f"block_versions[{index}] must be an integer")
            continue
        if value < 0:
            issues.append(f"block_versions[{index}] must be non-negative")
            continue
        normalized.append(value)
    return normalized, issues


def count_signals(versions: Iterable[int], bit: int) -> int:
    mask = 1 << bit
    normalized, issues = _coerce_versions(versions)
    if issues:
        raise ValueError("; ".join(issues))
    return sum(1 for version in normalized if version & mask)


def evaluate_period(
    deployment: VersionBitsDeployment,
    *,
    period_start_height: int,
    previous_state: str,
    block_versions: Iterable[int],
) -> dict[str, object]:
    """Evaluate one signaling period for rehearsal/test planning."""

    issues = deployment.validate()
    versions, version_issues = _coerce_versions(block_versions)
    issues.extend(version_issues)
    if previous_state not in VALID_STATES:
        issues.append(f"unknown previous_state: {previous_state}")
    if len(versions) > deployment.period:
        issues.append("block_versions cannot exceed the deployment period")
    if previous_state == STARTED and len(versions) != deployment.period:
        issues.append("started deployments require exactly one complete signaling period")
    signals = count_signals(versions, deployment.bit) if not version_issues else 0
    state = previous_state
    if issues:
        state = FAILED
    elif period_start_height < deployment.start_height:
        state = DEFINED
    elif period_start_height >= deployment.timeout_height and previous_state not in {LOCKED_IN, ACTIVE}:
        state = FAILED
    elif previous_state == DEFINED:
        state = STARTED
    elif previous_state == STARTED and signals >= deployment.threshold:
        state = LOCKED_IN
    elif previous_state == LOCKED_IN:
        state = ACTIVE
    elif previous_state == ACTIVE:
        state = ACTIVE
    return {
        "schema": "netcoin-versionbits-period-evaluation-v1",
        "deployment": deployment.__dict__,
        "period_start_height": period_start_height,
        "previous_state": previous_state,
        "signal_count": signals,
        "threshold": deployment.threshold,
        "state": state,
        "issues": issues,
        "consensus_integrated": False,
        "requires_nip_before_activation": True,
    }
