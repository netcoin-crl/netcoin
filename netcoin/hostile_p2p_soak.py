"""Deterministic hostile P2P/network soak simulation gates for NetCoin.

These helpers are intentionally small and reproducible.  They do not try to be a
full network emulator; they turn frozen soak scenarios into release-gate metrics
that exercise the same safety questions every time: can the node reject bad
headers, score hostile peers, heal partitions, and detect eclipse conditions?
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIOS = ROOT / "architecture" / "hostile-p2p-soak-scenarios.json"


@dataclass(frozen=True)
class SoakSummary:
    ok: bool
    accepted_headers: int
    rejected_headers: int
    duplicate_headers: int
    banned_peers: int
    best_height: int
    partition_healed: bool
    eclipse_detected: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "accepted_headers": self.accepted_headers,
            "rejected_headers": self.rejected_headers,
            "duplicate_headers": self.duplicate_headers,
            "banned_peers": self.banned_peers,
            "best_height": self.best_height,
            "partition_healed": self.partition_healed,
            "eclipse_detected": self.eclipse_detected,
        }


def run_hostile_p2p_soak_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Run one deterministic hostile-network soak scenario.

    The scoring model is deliberately transparent so future Rust/node tests can
    port it exactly before replacing this Python reference gate.
    """

    honest_headers = int(scenario.get("honest_headers", 0))
    invalid_headers = int(scenario.get("invalid_headers", 0))
    duplicate_headers = int(scenario.get("duplicate_headers", 0))
    penalty = invalid_headers * int(scenario.get("invalid_header_penalty", 20))
    penalty += duplicate_headers * int(scenario.get("duplicate_penalty", 5))
    banned_peers = penalty // int(scenario.get("ban_threshold", 100))
    best_height = honest_headers
    eclipse_detected = float(scenario.get("eclipse_peer_ratio", 0.0)) > float(scenario.get("max_eclipse_ratio", 0.33))
    partition_healed = int(scenario.get("partition_ticks", 0)) < int(scenario.get("duration_ticks", 1))
    ok = best_height >= int(scenario.get("min_final_height", 0)) and partition_healed and not eclipse_detected
    return SoakSummary(
        ok=ok,
        accepted_headers=honest_headers,
        rejected_headers=invalid_headers,
        duplicate_headers=duplicate_headers,
        banned_peers=banned_peers,
        best_height=best_height,
        partition_healed=partition_healed,
        eclipse_detected=eclipse_detected,
    ).to_dict()


def load_soak_scenarios(path: str | Path = DEFAULT_SCENARIOS) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_hostile_p2p_soak(path: str | Path = DEFAULT_SCENARIOS) -> dict[str, Any]:
    vectors = load_soak_scenarios(path)
    results = []
    for scenario in vectors.get("scenarios", []):
        actual = run_hostile_p2p_soak_scenario(scenario)
        expected = scenario.get("expected_summary", {})
        results.append(
            {
                "id": str(scenario.get("id", "")),
                "passed": actual == expected,
                "expected": expected,
                "actual": actual,
                "detected_hostility": bool(actual.get("eclipse_detected") or actual.get("banned_peers", 0) > 0),
            }
        )
    failed = [item for item in results if not item["passed"]]
    return {
        "ok": not failed,
        "scenario_count": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "results": results,
    }


__all__ = [
    "SoakSummary",
    "run_hostile_p2p_soak_scenario",
    "load_soak_scenarios",
    "run_hostile_p2p_soak",
]
