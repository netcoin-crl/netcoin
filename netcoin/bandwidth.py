"""Home-node bandwidth budgeting for M3 decentralized testnet operations."""

from __future__ import annotations

from dataclasses import dataclass


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


def relay_plan(
    mode: str, *, peer_count: int, pending_inventory: int, compact_block_supported: bool = True
) -> dict[str, object]:
    """Return a deterministic relay plan without sleeping or touching sockets."""
    budget = budget_for_mode(mode)
    outbound = min(max(0, int(peer_count)), budget.max_outbound_peers)
    inventory_limit = 0 if not budget.relay_mempool_inventory else min(int(pending_inventory), 5000)
    return {
        "schema": "netcoin-bandwidth-plan-v1",
        "budget": budget.to_dict(),
        "selected_outbound_peers": outbound,
        "inventory_to_relay": inventory_limit,
        "compact_block_relay": bool(budget.relay_compact_blocks and compact_block_supported),
        "under_500kbps_home_target": budget.mode != "home" or budget.max_bytes_per_second <= 500 * 1024,
    }
