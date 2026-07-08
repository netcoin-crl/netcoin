"""Carry balances across a chain relaunch (a "snapshot airdrop").

When a relaunch needs a new genesis (e.g. a consensus change), balances would
normally reset to zero. Instead, snapshot the old chain's UTXO set into an
allocation (address -> total balance) and bake it into the new genesis, so every
holder keeps their coins on the new chain. Same keys, same address, same balance.

Usage:
    old = Blockchain("old-data")
    allocation = export_allocation(old)        # {address: sats}
    save_allocation(allocation, "alloc.json")
    # at relaunch, every node starts the new chain with this allocation:
    new = Blockchain("new-data", genesis_allocation=load_allocation("alloc.json"))

Allocated coins live in the genesis coinbase, so they follow the normal coinbase
maturity rule (spendable after COINBASE_MATURITY blocks on the new chain).
"""

from __future__ import annotations

import json


def export_allocation(chain) -> dict[str, int]:
    """Total balance (in sats) per address from a chain's current UTXO set."""
    allocation: dict[str, int] = {}
    for utxo in chain._utxos.values():
        address = utxo.output.address
        if address and utxo.output.amount > 0:
            allocation[address] = allocation.get(address, 0) + utxo.output.amount
    return allocation


def save_allocation(allocation: dict[str, int], path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"allocation": allocation, "total_sats": sum(allocation.values())}, handle, indent=2, sort_keys=True)


def load_allocation(path: str) -> dict[str, int]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    raw = data.get("allocation", data)
    return {str(addr): int(amount) for addr, amount in raw.items()}
