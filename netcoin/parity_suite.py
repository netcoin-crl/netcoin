"""Executable parity suite for the NetCoin multi-language migration.

The Python implementation remains the reference runtime.  This module turns the
frozen architecture/parity-vectors.json file into executable checks that future
Rust and TypeScript components must match before replacing live Python paths.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VECTOR_PATH = ROOT / "architecture" / "parity-vectors.json"


@dataclass(frozen=True)
class ParityCaseResult:
    lane: str
    case_id: str
    passed: bool
    expected: Any
    actual: Any
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "case_id": self.case_id,
            "passed": self.passed,
            "expected": self.expected,
            "actual": self.actual,
            "detail": self.detail,
        }


def _load_vectors(root: Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    return json.loads((base / "architecture" / "parity-vectors.json").read_text(encoding="utf-8"))


def vector_fingerprint(vectors: dict[str, Any]) -> str:
    payload = json.dumps(vectors, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def double_sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(hashlib.sha256(payload).digest()).hexdigest()


def money_in_range(amount_sats: int, max_money_sats: int) -> bool:
    return int(amount_sats) >= 0 and int(amount_sats) <= int(max_money_sats)


def headers_link(headers: list[dict[str, Any]], genesis_previous: str = "") -> bool:
    expected = str(genesis_previous or "")
    for index, header in enumerate(headers):
        prev = str(header.get("previous_hash") or header.get("prev_hash") or "")
        if index == 0 and expected and prev != expected:
            return False
        if index > 0 and prev != str(headers[index - 1].get("hash") or ""):
            return False
        if not str(header.get("hash") or ""):
            return False
    return True


def checkpoint_ok(headers: list[dict[str, Any]], checkpoints: dict[str, str] | dict[int, str]) -> bool:
    normalized = {int(k): str(v) for k, v in checkpoints.items()}
    for header in headers:
        height = int(header.get("height", -1))
        if height in normalized and str(header.get("hash") or "") != normalized[height]:
            return False
    return True


def block_weight_ok(weight: int, max_weight: int) -> bool:
    return int(weight) <= int(max_weight)


def tx_fee_ok(input_sats: int, output_sats: int) -> bool:
    return int(input_sats) >= 0 and int(output_sats) >= 0 and int(input_sats) >= int(output_sats)


def merkle_root_hex(leaves_hex: list[str]) -> str:
    """Deterministic starter Merkle root for cross-language parity vectors.

    This migration helper deliberately mirrors the existing v0.21 merkle_pair
    convention: concatenate hex strings as text, double-SHA256 the UTF-8 bytes,
    and duplicate the final leaf when a level has an odd number of items. It is
    a parity target for migration crates, not a replacement for consensus block
    serialization rules.
    """
    level = [str(item) for item in leaves_hex]
    if not level:
        return double_sha256_hex(b"")
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [double_sha256_hex((level[i] + level[i + 1]).encode("utf-8")) for i in range(0, len(level), 2)]
    return level[0]


def subsidy_at_height(base_reward_sats: int, height: int, interval: int, numerator: int, denominator: int) -> int:
    if int(interval) <= 0 or int(denominator) <= 0:
        raise ValueError("interval and denominator must be positive")
    reward = int(base_reward_sats)
    reductions = max(0, int(height) // int(interval))
    for _ in range(reductions):
        reward = reward * int(numerator) // int(denominator)
    return reward


def wallet_decision(case: dict[str, Any]) -> str:
    if (
        int(case.get("amount_sats", 0)) < 0
        or int(case.get("fee_sats", 0)) < 0
        or int(case.get("balance_after_sats", 0)) < 0
    ):
        return "block"
    warnings = [str(w).lower() for w in case.get("warnings", [])]
    fee_rate = int(case.get("fee_rate_sat_vb", 0) or 0)
    dust_change = int(case.get("dust_change_sats", 0) or 0)
    if any("frozen" in w or "poison" in w for w in warnings):
        return "block"
    if fee_rate >= 250:
        return "block"
    if (
        warnings
        or int(case.get("input_count", 0)) > 20
        or fee_rate >= 50
        or (0 < dust_change < 546)
        or bool(case.get("recipient_reused"))
    ):
        return "review"
    return "allow"


def valid_quote(case: dict[str, Any]) -> bool:
    return int(case.get("quantity", 0)) > 0 and 0 < int(case.get("price_bps", 0)) < 10_000


def probability_sum_ok(case: dict[str, Any]) -> bool:
    total = int(case.get("yes_bps", 0)) + int(case.get("no_bps", 0))
    tolerance = int(case.get("tolerance_bps", 0))
    return 10_000 - tolerance <= total <= 10_000 + tolerance


def settlement_conserves(case: dict[str, Any]) -> bool:
    return int(case.get("claimable_payout_sats", 0)) + int(case.get("fees_sats", 0)) <= int(
        case.get("locked_collateral_sats", 0)
    )


def fee_within_cap(case: dict[str, Any]) -> bool:
    return int(case.get("fee_bps", 0)) <= int(case.get("max_fee_bps", 0))


def order_notional_ok(case: dict[str, Any]) -> bool:
    notional = int(case.get("price_bps", 0)) * int(case.get("quantity", 0)) // 10_000
    return notional >= int(case.get("min_notional_sats", 0))


def _case_result(lane: str, case_id: str, expected: Any, actual: Any, detail: str = "") -> ParityCaseResult:
    return ParityCaseResult(
        lane=lane, case_id=case_id, passed=expected == actual, expected=expected, actual=actual, detail=detail
    )


def run_consensus_vectors(vectors: dict[str, Any]) -> list[ParityCaseResult]:
    results: list[ParityCaseResult] = []
    for case in vectors.get("consensus", {}).get("cases", []):
        kind = case.get("kind")
        case_id = str(case.get("id"))
        try:
            if kind == "double_sha256":
                if "input_hex" in case:
                    payload = bytes.fromhex(str(case.get("input_hex", "")))
                else:
                    payload = str(case.get("input_utf8", "")).encode("utf-8")
                results.append(_case_result("consensus", case_id, case.get("expected_hex"), double_sha256_hex(payload)))
            elif kind == "money_range":
                results.append(
                    _case_result(
                        "consensus",
                        case_id,
                        bool(case.get("expected")),
                        money_in_range(case["amount_sats"], case["max_money_sats"]),
                    )
                )
            elif kind == "headers":
                results.append(
                    _case_result(
                        "consensus",
                        case_id,
                        bool(case.get("expected")),
                        headers_link(case.get("headers", []), case.get("genesis_previous", "")),
                    )
                )
            elif kind == "checkpoint":
                results.append(
                    _case_result(
                        "consensus",
                        case_id,
                        bool(case.get("expected")),
                        checkpoint_ok(case.get("headers", []), case.get("checkpoints", {})),
                    )
                )
            elif kind == "merkle_pair":
                payload = (str(case.get("left_hex", "")) + str(case.get("right_hex", ""))).encode("utf-8")
                results.append(_case_result("consensus", case_id, case.get("expected_hex"), double_sha256_hex(payload)))
            elif kind == "block_weight":
                results.append(
                    _case_result(
                        "consensus",
                        case_id,
                        bool(case.get("expected")),
                        block_weight_ok(case["weight"], case["max_weight"]),
                    )
                )
            elif kind == "tx_fee":
                results.append(
                    _case_result(
                        "consensus",
                        case_id,
                        bool(case.get("expected")),
                        tx_fee_ok(case["input_sats"], case["output_sats"]),
                    )
                )
            elif kind == "merkle_root":
                results.append(
                    _case_result(
                        "consensus", case_id, case.get("expected_hex"), merkle_root_hex(case.get("leaves_hex", []))
                    )
                )
            elif kind == "subsidy":
                results.append(
                    _case_result(
                        "consensus",
                        case_id,
                        int(case.get("expected_sats")),
                        subsidy_at_height(
                            case["base_reward_sats"],
                            case["height"],
                            case["interval"],
                            case["numerator"],
                            case["denominator"],
                        ),
                    )
                )
            else:
                results.append(ParityCaseResult("consensus", case_id, False, "known kind", kind, "unknown case kind"))
        except Exception as exc:  # pragma: no cover - defensive result capture
            results.append(ParityCaseResult("consensus", case_id, False, "no exception", type(exc).__name__, str(exc)))
    return results


def run_wallet_vectors(vectors: dict[str, Any]) -> list[ParityCaseResult]:
    return [
        _case_result("wallet", str(case.get("id")), str(case.get("decision")), wallet_decision(case))
        for case in vectors.get("wallet", {}).get("cases", [])
    ]


def run_market_vectors(vectors: dict[str, Any]) -> list[ParityCaseResult]:
    results: list[ParityCaseResult] = []
    for case in vectors.get("markets", {}).get("cases", []):
        kind = case.get("kind")
        case_id = str(case.get("id"))
        if kind == "quote":
            actual = valid_quote(case)
        elif kind == "probability_sum":
            actual = probability_sum_ok(case)
        elif kind == "settlement":
            actual = settlement_conserves(case)
        elif kind == "fee_cap":
            actual = fee_within_cap(case)
        elif kind == "order_notional":
            actual = order_notional_ok(case)
        else:
            actual = f"unknown:{kind}"
        results.append(_case_result("markets", case_id, bool(case.get("expected")), actual))
    return results


def run_api_vectors(vectors: dict[str, Any], root: Path | None = None) -> list[ParityCaseResult]:
    base = Path(root) if root is not None else ROOT
    schemas = (base / "api" / "src" / "schemas.ts").read_text(encoding="utf-8")
    openapi = (base / "docs" / "openapi.yaml").read_text(encoding="utf-8")
    api = vectors.get("api", {})
    results = []
    for schema in api.get("required_schemas", []):
        results.append(_case_result("api", f"schema:{schema}", True, str(schema) in schemas))
    for route in api.get("required_routes", []):
        normalized = str(route).replace("{market_id}", "{market_id}").replace("{address}", "{address}")
        results.append(
            _case_result(
                "api", f"route:{route}", True, normalized in openapi or str(route).replace("/api", "") in openapi
            )
        )
    return results


def run_parity_suite(root: Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    vectors = _load_vectors(base)
    results = []
    results.extend(run_consensus_vectors(vectors))
    results.extend(run_wallet_vectors(vectors))
    results.extend(run_market_vectors(vectors))
    results.extend(run_api_vectors(vectors, base))
    lane_counts: dict[str, dict[str, int]] = {}
    for result in results:
        lane = lane_counts.setdefault(result.lane, {"passed": 0, "failed": 0, "total": 0})
        lane["total"] += 1
        lane["passed" if result.passed else "failed"] += 1
    failed = [result.to_dict() for result in results if not result.passed]
    return {
        "ok": not failed,
        "schema_version": vectors.get("schema_version"),
        "vector_fingerprint": vector_fingerprint(vectors),
        "total": len(results),
        "passed": sum(1 for result in results if result.passed),
        "failed": len(failed),
        "lanes": lane_counts,
        "failures": failed,
        "results": [result.to_dict() for result in results],
    }


__all__ = [
    "ParityCaseResult",
    "run_parity_suite",
    "run_consensus_vectors",
    "run_wallet_vectors",
    "run_market_vectors",
    "run_api_vectors",
    "merkle_root_hex",
    "tx_fee_ok",
    "subsidy_at_height",
]
