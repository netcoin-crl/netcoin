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
ZERO_HASH = "0" * 64


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


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


def tx_parse_summary(tx: dict[str, Any]) -> dict[str, Any]:
    inputs = tx.get("inputs")
    outputs = tx.get("outputs")
    if not isinstance(inputs, list) or not inputs or not isinstance(outputs, list):
        return {"valid": False}
    total_output = 0
    try:
        for output in outputs:
            amount = int(output.get("amount"))
            if amount < 0:
                return {"valid": False}
            total_output += amount
        first = inputs[0]
        coinbase = (
            len(inputs) == 1
            and str(first.get("txid", "")).lower() == ZERO_HASH
            and int(first.get("vout", 0)) == -1
            and bool(first.get("coinbase"))
        )
        return {
            "valid": True,
            "version": int(tx.get("version", 1)),
            "locktime": int(tx.get("locktime", 0)),
            "input_count": len(inputs),
            "output_count": len(outputs),
            "total_output_sats": total_output,
            "coinbase": coinbase,
        }
    except Exception:
        return {"valid": False}


def block_header_summary(header: dict[str, Any]) -> dict[str, Any]:
    try:
        previous_hash = str(header.get("previous_hash", "")).lower()
        merkle_root = str(header.get("merkle_root", "")).lower()
        if len(previous_hash) != 64 or len(merkle_root) != 64:
            return {"valid": False}
        if any(c not in "0123456789abcdef" for c in previous_hash + merkle_root):
            return {"valid": False}
        normalized = {
            "version": int(header["version"]),
            "previous_hash": previous_hash,
            "merkle_root": merkle_root,
            "timestamp": int(header["timestamp"]),
            "bits": int(header["bits"]),
            "nonce": int(header["nonce"]),
            "height": int(header["height"]),
        }
        return {
            "valid": True,
            "hash_hex": double_sha256_hex(canonical_json_bytes(normalized)),
            "height": normalized["height"],
        }
    except Exception:
        return {"valid": False}


def basic_utxo_ok(case: dict[str, Any]) -> bool:
    inputs = case.get("inputs", [])
    outputs = case.get("outputs", [])
    if not isinstance(inputs, list) or not inputs or not isinstance(outputs, list):
        return False
    spend_height = int(case.get("spend_height", 0))
    maturity = int(case.get("coinbase_maturity", 0))
    seen: set[str] = set()
    total_in = 0
    total_out = 0
    try:
        for txin in inputs:
            outpoint = str(txin.get("outpoint", ""))
            if not outpoint or outpoint in seen:
                return False
            seen.add(outpoint)
            amount = int(txin.get("amount_sats"))
            height = int(txin.get("height", 0))
            if amount < 0:
                return False
            if bool(txin.get("coinbase")) and spend_height - height < maturity:
                return False
            total_in += amount
        for output in outputs:
            amount = int(output.get("amount_sats"))
            if amount < 0:
                return False
            total_out += amount
    except Exception:
        return False
    return total_out <= total_in


def mempool_fee_rate_sat_vb(fee_sats: int, vsize: int) -> int:
    if int(vsize) <= 0:
        return 0
    return int(fee_sats) // int(vsize)


def mempool_policy_summary(case: dict[str, Any]) -> dict[str, Any]:
    txid = str(case.get("txid", ""))
    fee_sats = int(case.get("fee_sats", 0))
    vsize = int(case.get("vsize", 0))
    fee_rate = mempool_fee_rate_sat_vb(fee_sats, vsize)
    current_pool = {str(item) for item in case.get("current_pool_txids", [])}
    inputs = case.get("inputs", [])
    outputs = case.get("outputs", [])
    accepted = True
    code = "accepted"
    if (
        not txid
        or not isinstance(inputs, list)
        or not inputs
        or not isinstance(outputs, list)
        or not outputs
        or vsize <= 0
        or fee_sats < 0
    ):
        accepted, code = False, "malformed"
    elif txid in current_pool:
        accepted, code = False, "duplicate"
    elif vsize > int(case.get("max_vsize", 100_000)):
        accepted, code = False, "too_large"
    elif any(not bool(txin.get("available", True)) for txin in inputs):
        accepted, code = False, "orphan"
    elif int(case.get("locktime", 0)) > int(case.get("current_height", 0)):
        accepted, code = False, "nonfinal"
    elif int(case.get("ancestor_count", 0)) > int(case.get("max_ancestors", 25)):
        accepted, code = False, "too_many_ancestors"
    elif int(case.get("descendant_count", 0)) > int(case.get("max_descendants", 25)):
        accepted, code = False, "too_many_descendants"
    elif any(int(output.get("amount_sats", 0)) < int(case.get("dust_threshold_sats", 546)) for output in outputs):
        accepted, code = False, "dust"
    elif fee_rate < int(case.get("min_relay_fee_rate_sat_vb", 1)):
        accepted, code = False, "low_fee_rate"
    elif "replacement_for" in case and fee_sats <= int(case.get("old_fee_sats", 0)) + int(
        case.get("min_replacement_delta_sats", 0)
    ):
        accepted, code = False, "insufficient_replacement_fee"
    return {"accepted": accepted, "code": code, "fee_rate_sat_vb": fee_rate}


def mempool_ordering_summary(case: dict[str, Any]) -> dict[str, Any]:
    txs = []
    for item in case.get("txs", []):
        txs.append(
            {
                **item,
                "_fee_rate": mempool_fee_rate_sat_vb(int(item.get("fee_sats", 0)), int(item.get("vsize", 0))),
            }
        )
    txs.sort(key=lambda item: (-int(item["_fee_rate"]), str(item.get("txid", ""))))
    return {
        "ordered_txids": [str(item.get("txid", "")) for item in txs],
        "top_fee_rate_sat_vb": int(txs[0]["_fee_rate"]) if txs else 0,
    }


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


def price_tick_ok(case: dict[str, Any]) -> bool:
    price = int(case.get("price_bps", 0))
    tick = int(case.get("tick_bps", 1))
    return tick > 0 and 0 < price < 10_000 and price % tick == 0


def collateral_ok(case: dict[str, Any]) -> bool:
    required = int(case.get("required_collateral_sats", 0))
    available = int(case.get("available_collateral_sats", 0))
    return required >= 0 and available >= required


def order_crosses(case: dict[str, Any]) -> bool:
    bid = int(case.get("best_bid_bps", 0))
    ask = int(case.get("best_ask_bps", 10_000))
    side = str(case.get("side", "")).lower()
    price = int(case.get("price_bps", 0))
    if side == "buy":
        return price >= ask
    if side == "sell":
        return price <= bid
    return False


def lifecycle_allows_order(case: dict[str, Any]) -> bool:
    return str(case.get("state", "")).lower() in {"open", "trading"}


def settlement_state_ok(case: dict[str, Any]) -> bool:
    state = str(case.get("state", "")).lower()
    has_outcome = bool(case.get("resolved_outcome"))
    disputed = bool(case.get("disputed", False))
    if state == "resolved":
        return has_outcome and not disputed
    if state == "disputed":
        return disputed
    return not has_outcome


def portfolio_conserves(case: dict[str, Any]) -> bool:
    cash = int(case.get("cash_sats", 0))
    position_value = int(case.get("position_value_sats", 0))
    locked = int(case.get("locked_collateral_sats", 0))
    equity = int(case.get("equity_sats", 0))
    return cash >= 0 and position_value >= 0 and locked >= 0 and cash + position_value + locked == equity


def signer_digest(case: dict[str, Any]) -> str:
    payload = case.get("payload", {})
    return double_sha256_hex(canonical_json_bytes(payload))


def signer_policy_summary(case: dict[str, Any]) -> dict[str, Any]:
    required = int(case.get("required_signers", 1))
    available = int(case.get("available_signers", 0))
    amount = int(case.get("amount_sats", 0))
    limit = int(case.get("hardware_limit_sats", 0))
    offline = bool(case.get("offline", False))
    hardware = bool(case.get("hardware", False))
    unknown_sighash = bool(case.get("unknown_sighash", False))
    if amount < 0 or required <= 0 or available < required or unknown_sighash:
        decision = "block"
    elif hardware and limit > 0 and amount > limit:
        decision = "review"
    elif offline or hardware:
        decision = "review"
    else:
        decision = "allow"
    return {"decision": decision, "required_signers": required, "available_signers": available}


def signer_envelope_summary(case: dict[str, Any]) -> dict[str, Any]:
    envelope = {
        "kind": str(case.get("kind_label", "offline-signing-envelope")),
        "address": str(case.get("address", "")),
        "tx_digest": str(case.get("tx_digest", "")),
        "network": str(case.get("network", "testnet")),
    }
    return {
        "valid": bool(envelope["address"] and envelope["tx_digest"]),
        "digest": double_sha256_hex(canonical_json_bytes(envelope)),
    }


def p2p_peer_summary(case: dict[str, Any]) -> dict[str, Any]:
    peers = case.get("peers", [])
    candidates = [peer for peer in peers if not bool(peer.get("banned", False))]
    if not candidates:
        return {"best_peer": "", "height": 0, "chainwork": 0}
    best = sorted(
        candidates,
        key=lambda p: (
            int(p.get("chainwork", 0)),
            int(p.get("height", 0)),
            int(p.get("score", 0)),
            str(p.get("address", "")),
        ),
        reverse=True,
    )[0]
    return {
        "best_peer": str(best.get("address", "")),
        "height": int(best.get("height", 0)),
        "chainwork": int(best.get("chainwork", 0)),
    }


def p2p_header_sync_summary(case: dict[str, Any]) -> dict[str, Any]:
    headers = case.get("headers", [])
    linked = headers_link(headers, case.get("genesis_previous", ""))
    checkpoint = checkpoint_ok(headers, case.get("checkpoints", {}))
    protocol_ok = int(case.get("peer_protocol", 0)) == int(case.get("local_protocol", 0))
    return {
        "accepted": bool(linked and checkpoint and protocol_ok),
        "linked": linked,
        "checkpoint_ok": checkpoint,
        "protocol_ok": protocol_ok,
    }


def p2p_ban_score_summary(case: dict[str, Any]) -> dict[str, Any]:
    score = int(case.get("score", 0)) + int(case.get("penalty", 0))
    threshold = int(case.get("ban_threshold", 100))
    return {"score": score, "banned": score >= threshold}


def indexer_address_summary(case: dict[str, Any]) -> dict[str, Any]:
    events = case.get("events", [])
    received = sum(int(e.get("amount_sats", 0)) for e in events if str(e.get("direction", "")) == "receive")
    sent = sum(int(e.get("amount_sats", 0)) for e in events if str(e.get("direction", "")) == "send")
    return {"received_sats": received, "sent_sats": sent, "balance_sats": received - sent, "event_count": len(events)}


def indexer_reorg_summary(case: dict[str, Any]) -> dict[str, Any]:
    old_height = int(case.get("old_tip_height", 0))
    fork_height = int(case.get("fork_height", 0))
    new_height = int(case.get("new_tip_height", 0))
    rollback = max(0, old_height - fork_height)
    apply = max(0, new_height - fork_height)
    return {"rollback_blocks": rollback, "apply_blocks": apply, "new_tip_height": new_height}


def indexer_market_event_summary(case: dict[str, Any]) -> dict[str, Any]:
    events = case.get("events", [])
    volume = sum(int(e.get("notional_sats", 0)) for e in events if str(e.get("type", "")) == "trade")
    disputes = sum(1 for e in events if str(e.get("type", "")) == "dispute")
    settlements = sum(1 for e in events if str(e.get("type", "")) == "settlement")
    return {"trade_volume_sats": volume, "disputes": disputes, "settlements": settlements, "event_count": len(events)}


def indexer_snapshot_hash(case: dict[str, Any]) -> str:
    return double_sha256_hex(canonical_json_bytes(case.get("snapshot", {})))


def api_codegen_summary(vectors: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    api = vectors.get("api", {})
    schemas_text = (base / "api" / "src" / "schemas.ts").read_text(encoding="utf-8")
    client_text = (base / "api" / "src" / "client.ts").read_text(encoding="utf-8")
    openapi_text = (base / "docs" / "openapi.yaml").read_text(encoding="utf-8")
    openapi_parity_text = (
        (base / "api" / "src" / "openapi-parity.ts").read_text(encoding="utf-8")
        if (base / "api" / "src" / "openapi-parity.ts").exists()
        else ""
    )
    schema_ok = all(str(schema) in schemas_text for schema in api.get("required_schemas", []))
    route_ok = all(
        str(route) in openapi_text or str(route).replace("/api", "") in openapi_text
        for route in api.get("required_routes", [])
    )
    client_ok = all(str(name) in client_text for name in api.get("required_client_methods", []))
    codegen_ok = all(str(symbol) in openapi_parity_text for symbol in api.get("required_codegen_symbols", []))
    return {"schema_ok": schema_ok, "route_ok": route_ok, "client_ok": client_ok, "codegen_ok": codegen_ok}


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
            elif kind == "tx_parse":
                results.append(
                    _case_result(
                        "consensus", case_id, case.get("expected_summary"), tx_parse_summary(case.get("tx", {}))
                    )
                )
            elif kind == "block_header":
                results.append(
                    _case_result(
                        "consensus", case_id, case.get("expected_summary"), block_header_summary(case.get("header", {}))
                    )
                )
            elif kind == "basic_utxo":
                results.append(_case_result("consensus", case_id, bool(case.get("expected")), basic_utxo_ok(case)))
            else:
                results.append(ParityCaseResult("consensus", case_id, False, "known kind", kind, "unknown case kind"))
        except Exception as exc:  # pragma: no cover - defensive result capture
            results.append(ParityCaseResult("consensus", case_id, False, "no exception", type(exc).__name__, str(exc)))
    return results


def run_mempool_vectors(vectors: dict[str, Any]) -> list[ParityCaseResult]:
    results: list[ParityCaseResult] = []
    for case in vectors.get("mempool", {}).get("cases", []):
        kind = case.get("kind")
        case_id = str(case.get("id"))
        if kind == "policy":
            actual = mempool_policy_summary(case)
        elif kind == "ordering":
            actual = mempool_ordering_summary(case)
        else:
            actual = {"accepted": False, "code": f"unknown:{kind}", "fee_rate_sat_vb": 0}
        results.append(_case_result("mempool", case_id, case.get("expected_summary"), actual))
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
        elif kind == "price_tick":
            actual = price_tick_ok(case)
        elif kind == "collateral":
            actual = collateral_ok(case)
        elif kind == "crossing":
            actual = order_crosses(case)
        elif kind == "lifecycle":
            actual = lifecycle_allows_order(case)
        elif kind == "settlement_state":
            actual = settlement_state_ok(case)
        elif kind == "portfolio":
            actual = portfolio_conserves(case)
        else:
            actual = f"unknown:{kind}"
        results.append(_case_result("markets", case_id, bool(case.get("expected")), actual))
    return results


def run_signer_vectors(vectors: dict[str, Any]) -> list[ParityCaseResult]:
    results: list[ParityCaseResult] = []
    for case in vectors.get("signer", {}).get("cases", []):
        kind = case.get("kind")
        case_id = str(case.get("id"))
        if kind == "digest":
            results.append(_case_result("signer", case_id, case.get("expected_hex"), signer_digest(case)))
        elif kind == "policy":
            results.append(_case_result("signer", case_id, case.get("expected_summary"), signer_policy_summary(case)))
        elif kind == "envelope":
            results.append(_case_result("signer", case_id, case.get("expected_summary"), signer_envelope_summary(case)))
        else:
            results.append(ParityCaseResult("signer", case_id, False, "known kind", kind, "unknown case kind"))
    return results


def run_p2p_vectors(vectors: dict[str, Any]) -> list[ParityCaseResult]:
    results: list[ParityCaseResult] = []
    for case in vectors.get("p2p", {}).get("cases", []):
        kind = case.get("kind")
        case_id = str(case.get("id"))
        if kind == "best_peer":
            results.append(_case_result("p2p", case_id, case.get("expected_summary"), p2p_peer_summary(case)))
        elif kind == "header_sync":
            results.append(_case_result("p2p", case_id, case.get("expected_summary"), p2p_header_sync_summary(case)))
        elif kind == "ban_score":
            results.append(_case_result("p2p", case_id, case.get("expected_summary"), p2p_ban_score_summary(case)))
        else:
            results.append(ParityCaseResult("p2p", case_id, False, "known kind", kind, "unknown case kind"))
    return results


def run_indexer_vectors(vectors: dict[str, Any]) -> list[ParityCaseResult]:
    results: list[ParityCaseResult] = []
    for case in vectors.get("indexer", {}).get("cases", []):
        kind = case.get("kind")
        case_id = str(case.get("id"))
        if kind == "address_summary":
            results.append(
                _case_result("indexer", case_id, case.get("expected_summary"), indexer_address_summary(case))
            )
        elif kind == "reorg":
            results.append(_case_result("indexer", case_id, case.get("expected_summary"), indexer_reorg_summary(case)))
        elif kind == "market_events":
            results.append(
                _case_result("indexer", case_id, case.get("expected_summary"), indexer_market_event_summary(case))
            )
        elif kind == "snapshot_hash":
            results.append(_case_result("indexer", case_id, case.get("expected_hex"), indexer_snapshot_hash(case)))
        else:
            results.append(ParityCaseResult("indexer", case_id, False, "known kind", kind, "unknown case kind"))
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
    for method in api.get("required_client_methods", []):
        client = (base / "api" / "src" / "client.ts").read_text(encoding="utf-8")
        results.append(_case_result("api", f"client:{method}", True, str(method) in client))
    for symbol in api.get("required_codegen_symbols", []):
        path = base / "api" / "src" / "openapi-parity.ts"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        results.append(_case_result("api", f"codegen:{symbol}", True, str(symbol) in text))
    if api.get("expected_codegen_summary"):
        results.append(
            _case_result(
                "api",
                "openapi-codegen-summary",
                api.get("expected_codegen_summary"),
                api_codegen_summary(vectors, base),
            )
        )
    return results


def run_parity_suite(root: Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    vectors = _load_vectors(base)
    results = []
    results.extend(run_consensus_vectors(vectors))
    results.extend(run_mempool_vectors(vectors))
    results.extend(run_wallet_vectors(vectors))
    results.extend(run_market_vectors(vectors))
    results.extend(run_signer_vectors(vectors))
    results.extend(run_p2p_vectors(vectors))
    results.extend(run_indexer_vectors(vectors))
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
    "run_mempool_vectors",
    "run_wallet_vectors",
    "run_market_vectors",
    "run_signer_vectors",
    "run_p2p_vectors",
    "run_indexer_vectors",
    "run_api_vectors",
    "merkle_root_hex",
    "tx_fee_ok",
    "subsidy_at_height",
    "tx_parse_summary",
    "block_header_summary",
    "basic_utxo_ok",
    "mempool_fee_rate_sat_vb",
    "mempool_policy_summary",
    "mempool_ordering_summary",
    "price_tick_ok",
    "collateral_ok",
    "order_crosses",
    "lifecycle_allows_order",
    "settlement_state_ok",
    "portfolio_conserves",
    "signer_digest",
    "signer_policy_summary",
    "signer_envelope_summary",
    "p2p_peer_summary",
    "p2p_header_sync_summary",
    "p2p_ban_score_summary",
    "indexer_address_summary",
    "indexer_reorg_summary",
    "indexer_market_event_summary",
    "indexer_snapshot_hash",
    "api_codegen_summary",
]
