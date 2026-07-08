"""Exchange proof-of-reserves and Merkle liability helpers."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def liability_leaf_hash(customer_id: str, amount_sats: int, *, nonce: str = "") -> str:
    body = json.dumps(
        {"customer_id": str(customer_id), "amount_sats": int(amount_sats), "nonce": str(nonce)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return _sha256_hex(b"netcoin-liability-leaf-v1\0" + body)


def _parent_hash(left: str, right: str) -> str:
    return _sha256_hex(b"netcoin-liability-node-v1\0" + bytes.fromhex(left) + bytes.fromhex(right))


@dataclass(frozen=True)
class LiabilityLeaf:
    customer_id: str
    amount_sats: int
    nonce: str = ""

    @property
    def hash(self) -> str:
        return liability_leaf_hash(self.customer_id, self.amount_sats, nonce=self.nonce)

    def to_public_dict(self) -> dict[str, Any]:
        customer_hash = _sha256_hex(str(self.customer_id).encode())
        return {"customer_hash": customer_hash, "amount_sats": int(self.amount_sats), "leaf_hash": self.hash}


class LiabilityMerkleTree:
    def __init__(self, liabilities: list[dict[str, Any]]):
        leaves = [
            LiabilityLeaf(str(row["customer_id"]), int(row["amount_sats"]), str(row.get("nonce", "")))
            for row in liabilities
        ]
        leaves.sort(key=lambda leaf: leaf.customer_id)
        self.leaves = leaves
        self.levels: list[list[str]] = []
        if leaves:
            self.levels.append([leaf.hash for leaf in leaves])
            while len(self.levels[-1]) > 1:
                level = self.levels[-1]
                nxt = []
                for i in range(0, len(level), 2):
                    left = level[i]
                    right = level[i + 1] if i + 1 < len(level) else left
                    nxt.append(_parent_hash(left, right))
                self.levels.append(nxt)

    @property
    def root(self) -> str:
        return self.levels[-1][0] if self.levels else ""

    @property
    def total_sats(self) -> int:
        return sum(leaf.amount_sats for leaf in self.leaves)

    def proof_for_customer(self, customer_id: str) -> dict[str, Any]:
        index = next((i for i, leaf in enumerate(self.leaves) if leaf.customer_id == customer_id), None)
        if index is None:
            return {"found": False, "customer_id": customer_id}
        leaf = self.leaves[index]
        proof = []
        idx = index
        for level in self.levels[:-1]:
            sibling_idx = idx ^ 1
            if sibling_idx >= len(level):
                sibling_idx = idx
            proof.append({"position": "right" if idx % 2 == 0 else "left", "hash": level[sibling_idx]})
            idx //= 2
        return {
            "found": True,
            "customer_id": customer_id,
            "amount_sats": leaf.amount_sats,
            "nonce": leaf.nonce,
            "leaf_hash": leaf.hash,
            "root": self.root,
            "proof": proof,
        }

    def public_summary(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "customer_count": len(self.leaves),
            "total_liabilities_sats": self.total_sats,
            "leaves": [leaf.to_public_dict() for leaf in self.leaves],
        }


def verify_liability_proof(
    customer_id: str, amount_sats: int, nonce: str, proof: list[dict[str, Any]], root: str
) -> bool:
    current = liability_leaf_hash(customer_id, amount_sats, nonce=nonce)
    for step in proof:
        sibling = str(step.get("hash") or "")
        if not sibling:
            return False
        if step.get("position") == "left":
            current = _parent_hash(sibling, current)
        else:
            current = _parent_hash(current, sibling)
    return current == root


def reserve_attestation(
    *, liabilities: list[dict[str, Any]], reserves: list[dict[str, Any]], operator: str = "exchange"
) -> dict[str, Any]:
    tree = LiabilityMerkleTree(liabilities)
    total_reserves = sum(int(row.get("amount_sats", 0) or 0) for row in reserves)
    payload = {
        "type": "netcoin-proof-of-reserves-v1",
        "created_at": int(time.time()),
        "operator": operator,
        "liability_root": tree.root,
        "customer_count": len(tree.leaves),
        "total_liabilities_sats": tree.total_sats,
        "total_reserves_sats": total_reserves,
        "surplus_sats": total_reserves - tree.total_sats,
        "reserve_addresses": reserves,
    }
    payload["solvent"] = payload["surplus_sats"] >= 0
    payload["attestation_hash"] = _sha256_hex(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    return payload


def verify_reserve_attestation(attestation: dict[str, Any]) -> dict[str, Any]:
    body = {k: v for k, v in attestation.items() if k != "attestation_hash"}
    expected = _sha256_hex(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
    surplus = int(attestation.get("total_reserves_sats", 0) or 0) - int(
        attestation.get("total_liabilities_sats", 0) or 0
    )
    return {
        "ok": expected == attestation.get("attestation_hash")
        and surplus == int(attestation.get("surplus_sats", 0) or 0),
        "solvent": surplus >= 0,
        "expected_hash": expected,
        "surplus_sats": surplus,
    }
