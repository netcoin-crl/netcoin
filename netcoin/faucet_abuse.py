"""Faucet proof-of-work, reputation, and daily-spend controls."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FaucetChallenge:
    challenge: str
    difficulty: int
    issued_at: int
    expires_at: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hex_zeros(difficulty: int) -> str:
    return "0" * max(0, int(difficulty))


def challenge_id(ip: str, *, secret: str, now: int | None = None, window_seconds: int = 300) -> str:
    now = int(time.time()) if now is None else int(now)
    bucket = now // int(window_seconds)
    material = f"netcoin-faucet|{ip}|{bucket}".encode()
    return hmac.new(secret.encode(), material, hashlib.sha256).hexdigest()


def issue_challenge(
    ip: str, *, secret: str, difficulty: int = 4, now: int | None = None, ttl_seconds: int = 300
) -> FaucetChallenge:
    now = int(time.time()) if now is None else int(now)
    return FaucetChallenge(
        challenge=challenge_id(ip, secret=secret, now=now, window_seconds=ttl_seconds),
        difficulty=int(difficulty),
        issued_at=now,
        expires_at=now + int(ttl_seconds),
    )


def verify_pow(challenge: str, nonce: str, *, difficulty: int) -> bool:
    if not challenge or not nonce:
        return False
    digest = hashlib.sha256(f"{challenge}:{nonce}".encode()).hexdigest()
    return digest.startswith(_hex_zeros(difficulty))


def solve_pow(challenge: str, *, difficulty: int, max_nonce: int = 2_000_000) -> str:
    """Small deterministic solver for tests and low-difficulty browser demos."""
    prefix = _hex_zeros(difficulty)
    for nonce in range(int(max_nonce)):
        text = str(nonce)
        if hashlib.sha256(f"{challenge}:{text}".encode()).hexdigest().startswith(prefix):
            return text
    raise ValueError("no proof-of-work nonce found within limit")


def reputation_score(
    state: dict[str, Any], *, ip: str, address: str = "", device: str = "", now: int | None = None
) -> dict[str, Any]:
    now = int(time.time()) if now is None else int(now)
    abuse = state.get("abuse", []) or []
    requests = state.get("requests", []) or []
    queue = state.get("queue", []) or []
    score = 100
    reasons: list[str] = []
    recent_abuse = [
        a
        for a in abuse
        if now - int(a.get("timestamp", 0)) < 24 * 3600
        and (a.get("ip") == ip or (device and a.get("device") == device))
    ]
    if recent_abuse:
        penalty = min(60, len(recent_abuse) * 10)
        score -= penalty
        reasons.append(f"recent_abuse:{len(recent_abuse)}")
    recent_same_address = [
        r
        for r in list(requests) + list(queue)
        if address and r.get("address") == address and now - int(r.get("timestamp", 0)) < 24 * 3600
    ]
    if len(recent_same_address) > 1:
        score -= min(30, (len(recent_same_address) - 1) * 10)
        reasons.append(f"address_reuse_24h:{len(recent_same_address)}")
    risk = "allow"
    if score < 40:
        risk = "block"
    elif score < 70:
        risk = "challenge"
    return {"score": max(0, score), "risk": risk, "reasons": reasons}


def record_abuse_event(
    state: dict[str, Any],
    *,
    ip: str,
    reason: str,
    address: str = "",
    device: str = "",
    now: int | None = None,
    max_log: int = 200,
) -> None:
    now = int(time.time()) if now is None else int(now)
    log = state.setdefault("abuse", [])
    log.append({"ip": ip, "address": address, "device": device, "reason": reason, "timestamp": now})
    state["abuse"] = log[-int(max_log) :]


def daily_spend_report(
    state: dict[str, Any], *, cap_sats: int, amount_sats: int, now: int | None = None
) -> dict[str, Any]:
    now = int(time.time()) if now is None else int(now)
    start = now - 24 * 3600
    total_sats = 0
    sent_count = 0
    for item in state.get("requests", []) or []:
        if int(item.get("timestamp", 0)) < start:
            continue
        try:
            # State stores amount as NET string; callers can pass amount_sats for planned grant.
            amount_text = str(item.get("amount", "0"))
            total_sats += int(float(amount_text) * 100_000_000)
        except (TypeError, ValueError):
            pass
        sent_count += 1
    remaining = max(0, int(cap_sats) - total_sats)
    return {
        "cap_sats": int(cap_sats),
        "spent_sats": total_sats,
        "remaining_sats": remaining,
        "sent_count_24h": sent_count,
        "planned_amount_sats": int(amount_sats),
        "would_exceed": int(cap_sats) > 0 and int(amount_sats) > remaining,
    }


def abuse_summary(state: dict[str, Any], *, now: int | None = None) -> dict[str, Any]:
    now = int(time.time()) if now is None else int(now)
    events = state.get("abuse", []) or []
    recent = [e for e in events if now - int(e.get("timestamp", 0)) < 24 * 3600]
    by_reason: dict[str, int] = {}
    for event in recent:
        reason = str(event.get("reason") or "unknown")
        by_reason[reason] = by_reason.get(reason, 0) + 1
    return {"abuse_events_24h": len(recent), "by_reason": by_reason}
