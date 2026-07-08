"""Wallet coin-control, freezing, fee planning, and dust/poisoning helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .params import DUST_THRESHOLD, MIN_RELAY_FEE_PER_KB
from .serialization import transaction_vsize
from .tx import SpendableOutput, Transaction


@dataclass
class CoinControlPolicy:
    frozen_outpoints: set[str] = field(default_factory=set)
    strategy: str = "largest-first"
    max_inputs: int = 500

    def freeze(self, outpoint: str) -> None:
        self.frozen_outpoints.add(outpoint)

    def unfreeze(self, outpoint: str) -> None:
        self.frozen_outpoints.discard(outpoint)

    def spendable(self, coins: Iterable[SpendableOutput]) -> list[SpendableOutput]:
        return [c for c in coins if c.outpoint() not in self.frozen_outpoints]


def estimate_dynamic_fee_sats(
    vsize: int, *, mempool_bytes: int = 0, min_relay_fee_per_kb: int = MIN_RELAY_FEE_PER_KB
) -> int:
    pressure_multiplier = 1
    if mempool_bytes > 5_000_000:
        pressure_multiplier = 4
    elif mempool_bytes > 1_000_000:
        pressure_multiplier = 2
    return max(1, (max(1, int(vsize)) * int(min_relay_fee_per_kb) * pressure_multiplier + 999) // 1000)


def estimate_tx_fee(tx: Transaction, *, mempool_bytes: int = 0) -> int:
    return estimate_dynamic_fee_sats(transaction_vsize(tx), mempool_bytes=mempool_bytes)


def detect_address_reuse(history: Mapping[str, Any], address: str) -> dict[str, object]:
    count = (
        len(history.get(address, []))
        if isinstance(history.get(address, []), list)
        else int(history.get(address, 0) or 0)
    )
    return {"address": address, "reuse_detected": count > 1, "seen_count": count}


def detect_address_poisoning(recent_addresses: Iterable[str], candidate: str) -> dict[str, object]:
    candidate = str(candidate)
    warnings = []
    for addr in recent_addresses:
        addr = str(addr)
        if addr == candidate:
            continue
        if len(addr) >= 12 and len(candidate) >= 12 and addr[:6] == candidate[:6] and addr[-6:] == candidate[-6:]:
            warnings.append(addr)
    return {"candidate": candidate, "possible_poisoning": bool(warnings), "similar_recent_addresses": warnings[:10]}


def plan_consolidation(
    coins: Iterable[SpendableOutput], *, dust_threshold: int = DUST_THRESHOLD, max_inputs: int = 400
) -> dict[str, object]:
    small = [c for c in coins if c.output.amount <= max(dust_threshold * 10, dust_threshold)]
    total = sum(c.output.amount for c in small[:max_inputs])
    return {
        "small_coin_count": len(small),
        "selected_count": min(len(small), max_inputs),
        "selected_total_sats": total,
        "should_consolidate": len(small) > 20,
    }
