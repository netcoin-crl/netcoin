"""Version-bits rehearsal model for future NetCoin soft forks.

This module is intentionally not wired into consensus. It lets operators model
BIP9-style signaling windows and produce rehearsal evidence before any consensus
change is proposed through a NIP.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFINED = "defined"
STARTED = "started"
LOCKED_IN = "locked_in"
ACTIVE = "active"
FAILED = "failed"

VALID_STATES = {DEFINED, STARTED, LOCKED_IN, ACTIVE, FAILED}
REHEARSAL_NETWORKS = {"testnet", "regtest", "testnet-rehearsal"}
ENV_ENABLE_REHEARSAL = "NETCOIN_TESTNET_DEPLOYMENTS"


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


@dataclass(frozen=True)
class VersionBitsRehearsalConfig:
    network: str
    deployment: VersionBitsDeployment
    enabled: bool = False
    enforce_active_signal: bool = True

    def validate(self) -> list[str]:
        issues = self.deployment.validate()
        network = self.network.strip().lower()
        if network == "mainnet" or network == "main":
            issues.append("versionbits rehearsal hard-refuses mainnet")
        if network not in REHEARSAL_NETWORKS:
            issues.append(f"network must be one of {sorted(REHEARSAL_NETWORKS)}")
        return issues

    def require_safe(self) -> None:
        issues = self.validate()
        if issues:
            raise ValueError("; ".join(issues))


def rehearsal_enabled(env: dict[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(ENV_ENABLE_REHEARSAL, "")).strip().lower() in {"1", "true", "yes", "on"}


def load_rehearsal_config(path: str | Path, *, env: dict[str, str] | None = None) -> VersionBitsRehearsalConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    deployment = VersionBitsDeployment(**payload["deployment"])
    config = VersionBitsRehearsalConfig(
        network=str(payload.get("network", "")),
        deployment=deployment,
        enabled=bool(payload.get("enabled", rehearsal_enabled(env))),
        enforce_active_signal=bool(payload.get("enforce_active_signal", True)),
    )
    config.require_safe()
    return config


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


def extract_block_versions(blocks: Iterable[object]) -> list[int]:
    versions: list[int] = []
    for index, block in enumerate(blocks):
        try:
            if isinstance(block, dict):
                header = block.get("header", block)
                version = header["version"]
            else:
                version = getattr(getattr(block, "header"), "version")
        except Exception as exc:  # pragma: no cover - defensive clarity
            raise ValueError(f"block {index} does not expose a header version") from exc
        versions.append(int(version))
    return versions


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


def enforce_rehearsal_rule(
    config: VersionBitsRehearsalConfig,
    *,
    state: str,
    candidate_version: int,
) -> dict[str, object]:
    config.require_safe()
    if not config.enabled:
        return {"ok": True, "enforced": False, "reason": "rehearsal disabled"}
    if state != ACTIVE:
        return {"ok": True, "enforced": False, "reason": f"state {state} is not active"}
    if not config.enforce_active_signal:
        return {"ok": True, "enforced": False, "reason": "active signal enforcement disabled"}
    mask = 1 << config.deployment.bit
    ok = bool(int(candidate_version) & mask)
    return {
        "ok": ok,
        "enforced": True,
        "rule": "active blocks must continue signaling the rehearsal bit",
        "bit": config.deployment.bit,
        "candidate_version": int(candidate_version),
    }


def evaluate_rehearsal_chain(
    config: VersionBitsRehearsalConfig,
    block_versions: Iterable[int],
    *,
    initial_state: str = DEFINED,
) -> dict[str, object]:
    config.require_safe()
    versions, issues = _coerce_versions(block_versions)
    state = initial_state
    periods: list[dict[str, object]] = []
    active_enforcement: list[dict[str, object]] = []
    if not config.enabled:
        issues.append(f"{ENV_ENABLE_REHEARSAL} is not enabled for this rehearsal config")

    deployment = config.deployment
    for start in range(0, len(versions), deployment.period):
        period_versions = versions[start : start + deployment.period]
        previous_state = state
        evaluation = evaluate_period(
            deployment,
            period_start_height=start,
            previous_state=state,
            block_versions=period_versions,
        )
        state = str(evaluation["state"])
        periods.append(evaluation)
        if previous_state == ACTIVE or state == ACTIVE:
            for offset, version in enumerate(period_versions):
                enforcement = enforce_rehearsal_rule(
                    config,
                    state=ACTIVE,
                    candidate_version=version,
                )
                enforcement["height"] = start + offset
                active_enforcement.append(enforcement)
                if not enforcement["ok"]:
                    issues.append(f"height {start + offset} failed active rehearsal rule")

    return {
        "schema": "netcoin-versionbits-rehearsal-v1",
        "ok": not issues,
        "network": config.network,
        "enabled": config.enabled,
        "deployment": deployment.__dict__,
        "final_state": state,
        "periods": periods,
        "active_enforcement": active_enforcement,
        "issues": issues,
        "consensus_integrated": False,
        "mainnet_wired": False,
        "requires_nip_before_activation": True,
    }
