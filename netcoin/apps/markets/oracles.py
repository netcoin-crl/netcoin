"""Oracle and evidence registry for prediction-market resolution."""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class OracleRecord:
    oracle_id: str
    name: str
    source_type: str = "manual"
    url: str = ""
    public_key: str = ""
    reputation: int = 0
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evidence_hash(evidence: dict[str, Any]) -> str:
    body = repr(sorted((str(k), str(v)) for k, v in evidence.items())).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


class OracleRegistry:
    def __init__(self, state: dict[str, Any] | None = None):
        self.state = state if state is not None else {}
        self.state.setdefault("oracles", {})
        self.state.setdefault("evidence", {})
        self.state.setdefault("disputes", {})

    def register_oracle(
        self,
        oracle_id: str,
        name: str,
        *,
        source_type: str = "manual",
        url: str = "",
        public_key: str = "",
        reputation: int = 0,
        active: bool = True,
    ) -> dict[str, Any]:
        if not oracle_id:
            raise ValueError("oracle_id is required")
        rec = OracleRecord(
            oracle_id=oracle_id,
            name=name or oracle_id,
            source_type=source_type,
            url=url,
            public_key=public_key,
            reputation=int(reputation),
            active=bool(active),
        ).to_dict()
        rec["updated_at"] = int(time.time())
        self.state["oracles"][oracle_id] = rec
        return rec

    def submit_evidence(
        self,
        market_id: str,
        *,
        oracle_id: str = "manual",
        url: str = "",
        title: str = "",
        source_type: str = "url",
        submitter: str = "operator",
        statement: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ev = {
            "evidence_id": f"ev_{hashlib.sha256((market_id + oracle_id + url + statement + str(time.time())).encode()).hexdigest()[:16]}",
            "market_id": market_id,
            "oracle_id": oracle_id,
            "url": url,
            "title": title,
            "source_type": source_type,
            "submitter": submitter,
            "statement": statement,
            "payload": payload or {},
            "created_at": int(time.time()),
        }
        ev["sha256"] = evidence_hash(ev)
        self.state["evidence"].setdefault(market_id, []).append(ev)
        return ev

    def dispute(self, market_id: str, *, commenter: str, comment: str, evidence_id: str = "") -> dict[str, Any]:
        rec = {
            "dispute_id": f"dsp_{hashlib.sha256((market_id + commenter + comment + str(time.time())).encode()).hexdigest()[:16]}",
            "market_id": market_id,
            "commenter": commenter,
            "comment": comment[:2000],
            "evidence_id": evidence_id,
            "created_at": int(time.time()),
        }
        self.state["disputes"].setdefault(market_id, []).append(rec)
        return rec

    def dossier(self, market_id: str) -> dict[str, Any]:
        evidence = self.state.get("evidence", {}).get(market_id, [])
        disputes = self.state.get("disputes", {}).get(market_id, [])
        approved = [
            e
            for e in evidence
            if self.state.get("oracles", {}).get(e.get("oracle_id"), {}).get("active", e.get("oracle_id") == "manual")
        ]
        return {
            "market_id": market_id,
            "evidence": evidence,
            "disputes": disputes,
            "approved_evidence": approved,
            "evidence_count": len(evidence),
            "dispute_count": len(disputes),
        }

    def reputation_report(self) -> dict[str, Any]:
        """Summarize oracle reputation and evidence usage for operator review."""
        oracles = list(self.state.get("oracles", {}).values())
        evidence_by_oracle: dict[str, int] = {}
        for items in self.state.get("evidence", {}).values():
            for ev in items:
                oid = str(ev.get("oracle_id") or "manual")
                evidence_by_oracle[oid] = evidence_by_oracle.get(oid, 0) + 1
        rows = []
        for oracle in oracles:
            rows.append(dict(oracle) | {"evidence_count": evidence_by_oracle.get(str(oracle.get("oracle_id")), 0)})
        rows.sort(
            key=lambda item: (
                int(item.get("active", True)),
                int(item.get("reputation", 0)),
                int(item.get("evidence_count", 0)),
            ),
            reverse=True,
        )
        return {"oracle_count": len(rows), "active_count": sum(1 for o in rows if o.get("active")), "oracles": rows}

    def resolution_readiness(
        self, market_id: str, *, min_approved_evidence: int = 1, max_disputes: int = 0
    ) -> dict[str, Any]:
        dossier = self.dossier(market_id)
        approved = len(dossier.get("approved_evidence", []))
        disputes = int(dossier.get("dispute_count", 0))
        ready = approved >= int(min_approved_evidence) and disputes <= int(max_disputes)
        blockers = []
        if approved < int(min_approved_evidence):
            blockers.append("insufficient_approved_evidence")
        if disputes > int(max_disputes):
            blockers.append("open_disputes")
        return {
            "market_id": market_id,
            "ready": ready,
            "approved_evidence_count": approved,
            "dispute_count": disputes,
            "blockers": blockers,
        }
