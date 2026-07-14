"""Home-node bandwidth budgeting for M3 decentralized testnet operations."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Callable


@dataclass(frozen=True)
class BandwidthBudget:
    mode: str = "normal"
    max_bytes_per_second: int = 0
    relay_compact_blocks: bool = True
    relay_mempool_inventory: bool = True
    max_outbound_peers: int = 8

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "max_bytes_per_second": self.max_bytes_per_second,
            "relay_compact_blocks": self.relay_compact_blocks,
            "relay_mempool_inventory": self.relay_mempool_inventory,
            "max_outbound_peers": self.max_outbound_peers,
        }


MODES = {
    "normal": BandwidthBudget(mode="normal", max_bytes_per_second=0, max_outbound_peers=8),
    "home": BandwidthBudget(mode="home", max_bytes_per_second=500 * 1024, max_outbound_peers=6),
    "low": BandwidthBudget(
        mode="low",
        max_bytes_per_second=250 * 1024,
        relay_compact_blocks=True,
        relay_mempool_inventory=False,
        max_outbound_peers=4,
    ),
}


def budget_for_mode(mode: str) -> BandwidthBudget:
    try:
        return MODES[str(mode).lower()]
    except KeyError as exc:
        raise ValueError(f"unknown bandwidth mode: {mode}") from exc


class TokenBucket:
    """Byte-rate token bucket for outbound relay throttling."""

    def __init__(
        self,
        rate_bytes_per_second: int,
        *,
        burst_seconds: float = 1.0,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ):
        self.rate_bytes_per_second = max(0, int(rate_bytes_per_second))
        self.capacity = max(1.0, self.rate_bytes_per_second * max(0.1, float(burst_seconds)))
        self.tokens = self.capacity
        self.clock = clock or time.monotonic
        self.sleeper = sleeper or time.sleep
        self.updated_at = self.clock()
        self.total_wait_seconds = 0.0
        self.total_bytes = 0
        self.throttle_events = 0
        self._lock = Lock()

    @property
    def enabled(self) -> bool:
        return self.rate_bytes_per_second > 0

    def _refill(self, now: float) -> None:
        elapsed = max(0.0, now - self.updated_at)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_bytes_per_second)
        self.updated_at = now

    def consume(self, byte_count: int) -> float:
        """Consume bytes and sleep as needed. Returns seconds waited."""
        amount = max(0, int(byte_count))
        if amount == 0 or not self.enabled:
            self.total_bytes += amount
            return 0.0
        waited = 0.0
        with self._lock:
            remaining = amount
            while remaining > 0:
                now = self.clock()
                self._refill(now)
                if self.tokens < 1.0:
                    wait_for = (1.0 - self.tokens) / self.rate_bytes_per_second
                    self.throttle_events += 1
                    self.total_wait_seconds += wait_for
                    waited += wait_for
                    self.sleeper(wait_for)
                    continue
                spend = min(remaining, int(self.tokens))
                self.tokens -= spend
                remaining -= spend
                if remaining <= 0:
                    break
                wait_for = remaining / self.rate_bytes_per_second
                self.throttle_events += 1
                self.total_wait_seconds += wait_for
                waited += wait_for
                self.sleeper(wait_for)
                self._refill(self.clock())
            self.total_bytes += amount
        return waited

    def snapshot(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "rate_bytes_per_second": self.rate_bytes_per_second,
            "capacity": int(self.capacity),
            "available_tokens": int(self.tokens),
            "bytes": self.total_bytes,
            "throttle_events": self.throttle_events,
            "wait_seconds": round(self.total_wait_seconds, 6),
        }


def relay_plan(
    mode: str, *, peer_count: int, pending_inventory: int, compact_block_supported: bool = True
) -> dict[str, object]:
    """Return a deterministic relay plan without sleeping or touching sockets."""
    budget = budget_for_mode(mode)
    outbound = min(max(0, int(peer_count)), budget.max_outbound_peers)
    safe_pending_inventory = max(0, int(pending_inventory))
    inventory_limit = 0 if not budget.relay_mempool_inventory else min(safe_pending_inventory, 5000)
    return {
        "schema": "netcoin-bandwidth-plan-v1",
        "budget": budget.to_dict(),
        "selected_outbound_peers": outbound,
        "inventory_to_relay": inventory_limit,
        "compact_block_relay": bool(budget.relay_compact_blocks and compact_block_supported),
        "under_500kbps_home_target": budget.mode != "home" or budget.max_bytes_per_second <= 500 * 1024,
    }
