"""Market governance helpers for oracle quorum and dispute escalation."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class OracleVote:
    oracle_id: str
    market_id: str
    outcome_id: str
    confidence_bps: int
    evidence_hash: str
    created_at: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evidence_hash(evidence: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def create_oracle_vote(
    oracle_id: str, market_id: str, outcome_id: str, evidence: dict[str, Any], *, confidence_bps: int = 10_000
) -> dict[str, Any]:
    vote = OracleVote(
        oracle_id=str(oracle_id),
        market_id=str(market_id),
        outcome_id=str(outcome_id),
        confidence_bps=max(0, min(int(confidence_bps), 10_000)),
        evidence_hash=evidence_hash(evidence),
        created_at=int(time.time()),
    )
    data = vote.to_dict()
    data["vote_id"] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]
    return data


def tally_oracle_votes(
    votes: list[dict[str, Any]], *, quorum: int = 3, min_confidence_bps: int = 6_000
) -> dict[str, Any]:
    unique: dict[str, dict[str, Any]] = {}
    for vote in votes:
        oracle = str(vote.get("oracle_id", ""))
        if not oracle:
            continue
        unique[oracle] = vote
    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    for vote in unique.values():
        outcome = str(vote.get("outcome_id", ""))
        confidence = int(vote.get("confidence_bps", 0) or 0)
        if not outcome:
            continue
        totals[outcome] = totals.get(outcome, 0) + confidence
        counts[outcome] = counts.get(outcome, 0) + 1
    winner = None
    if totals:
        winner = sorted(totals.items(), key=lambda item: (-item[1], item[0]))[0][0]
    ready = bool(
        winner
        and counts.get(winner, 0) >= int(quorum)
        and totals.get(winner, 0) // max(1, counts.get(winner, 1)) >= int(min_confidence_bps)
    )
    return {
        "ready": ready,
        "winning_outcome_id": winner,
        "unique_oracles": len(unique),
        "counts": counts,
        "confidence_totals_bps": totals,
        "quorum": int(quorum),
        "min_confidence_bps": int(min_confidence_bps),
    }


def dispute_escalation_plan(
    market: dict[str, Any], disputes: list[dict[str, Any]], votes: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    votes = votes or []
    tally = tally_oracle_votes(votes) if votes else {"ready": False, "unique_oracles": 0}
    severity = "low"
    actions = ["collect_additional_evidence"]
    if len(disputes) >= 3:
        severity = "high"
        actions.append("pause_settlement")
    if tally.get("ready"):
        actions.append("resolver_review_quorum_result")
    else:
        actions.append("request_more_oracle_votes")
    if market.get("state") in {"resolved", "settled"} and disputes:
        severity = "critical"
        actions.append("freeze_claims_until_operator_review")
    return {
        "market_id": market.get("market_id"),
        "severity": severity,
        "dispute_count": len(disputes),
        "oracle_tally": tally,
        "actions": actions,
    }
