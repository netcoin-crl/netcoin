"""Dependency-free core ledger helpers for a future Discord tip bot."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TipLedger:
    balances: dict[str, int] = field(default_factory=dict)

    def credit(self, user_id: str, sats: int) -> int:
        if sats <= 0:
            raise ValueError("credit must be positive")
        self.balances[user_id] = self.balances.get(user_id, 0) + sats
        return self.balances[user_id]

    def debit(self, user_id: str, sats: int) -> int:
        if sats <= 0:
            raise ValueError("debit must be positive")
        if self.balances.get(user_id, 0) < sats:
            raise ValueError("insufficient balance")
        self.balances[user_id] -= sats
        return self.balances[user_id]

    def tip(self, sender_id: str, receiver_id: str, sats: int) -> None:
        self.debit(sender_id, sats)
        self.credit(receiver_id, sats)
