"""Headers-first synchronization scheduler helpers.

The module is deliberately transport-agnostic: TCP/HTTP callers can feed header
segments in, and the scheduler decides whether the headers link correctly,
which blocks should be requested, which peers are unhealthy, and which download
jobs are stalled. This gives NetCoin a hardened sync planning layer without
coupling consensus validation to sockets.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable


class HeaderSyncError(ValueError):
    """Raised when a peer provides an invalid header segment."""


@dataclass
class DownloadJob:
    block_hash: str
    height: int
    peer: str
    attempts: int = 0
    last_attempt_at: int = 0
    status: str = "queued"
    error: str = ""
    priority: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HeaderWorkState:
    height: int
    block_hash: str
    previous_hash: str
    work: int = 1
    cumulative_work: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _header_hash(header: dict[str, Any]) -> str:
    supplied = str(header.get("hash") or "").lower()
    if supplied:
        return supplied
    material = "|".join(
        str(header.get(k, "")) for k in ("height", "previous_hash", "merkle_root", "timestamp", "bits", "nonce")
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _header_prev(header: dict[str, Any]) -> str:
    return str(header.get("previous_hash") or header.get("prev_hash") or header.get("parent_hash") or "").lower()


def _header_height(header: dict[str, Any], fallback: int) -> int:
    try:
        return int(header.get("height", fallback))
    except (TypeError, ValueError):
        return int(fallback)


def _header_work(header: dict[str, Any]) -> int:
    """Estimate work from supplied fields.

    If a caller has real chainwork it can provide `work` or `chainwork`. Without
    that, one header equals one work unit, which is adequate for scheduling and
    adversarial tests and does not replace consensus validation.
    """
    for key in ("work", "chainwork_delta"):
        try:
            value = int(header.get(key, 0))
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 1


def validate_headers_linked(
    headers: list[dict[str, Any]],
    *,
    expected_previous_hash: str = "",
    expected_start_height: int | None = None,
    checkpoints: dict[int, str] | None = None,
    max_headers: int = 2000,
) -> list[HeaderWorkState]:
    """Validate that a header segment is internally linked and checkpoint-safe."""
    if len(headers) > int(max_headers):
        raise HeaderSyncError("too many headers in one segment")
    states: list[HeaderWorkState] = []
    checkpoints = {int(k): str(v).lower() for k, v in (checkpoints or {}).items()}
    prev = str(expected_previous_hash or "").lower()
    cumulative = 0
    for index, header in enumerate(headers):
        height = _header_height(header, (expected_start_height or 0) + index)
        if expected_start_height is not None and height != int(expected_start_height) + index:
            raise HeaderSyncError(f"non-contiguous header height at index {index}: {height}")
        header_prev = _header_prev(header)
        if index == 0 and prev and header_prev and header_prev != prev:
            raise HeaderSyncError("first header does not connect to local tip")
        if index > 0 and header_prev and header_prev != states[-1].block_hash:
            raise HeaderSyncError("header segment is not linked")
        block_hash = _header_hash(header)
        if not block_hash:
            raise HeaderSyncError("header is missing hash")
        if height in checkpoints and checkpoints[height] != block_hash:
            raise HeaderSyncError(f"checkpoint mismatch at height {height}")
        work = _header_work(header)
        cumulative += work
        states.append(
            HeaderWorkState(
                height=height, block_hash=block_hash, previous_hash=header_prev, work=work, cumulative_work=cumulative
            )
        )
    return states


def build_block_locator(tip_hashes: list[str], *, max_hashes: int = 32) -> list[str]:
    """Build a Bitcoin-style sparse block locator from newest to oldest hashes."""
    hashes = [str(h).lower() for h in tip_hashes if h]
    if not hashes:
        return []
    out: list[str] = []
    step = 1
    index = 0
    while index < len(hashes) and len(out) < int(max_hashes):
        out.append(hashes[index])
        if len(out) > 10:
            step *= 2
        index += step
    return out


class HeaderSyncScheduler:
    """Queue missing blocks after validating a header segment."""

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        retry_seconds: int = 30,
        checkpoints: dict[int, str] | None = None,
        peer_penalty: Callable[[str, str], None] | None = None,
    ):
        self.max_attempts = int(max_attempts)
        self.retry_seconds = int(retry_seconds)
        self.jobs: dict[str, DownloadJob] = {}
        self.bad_peers: dict[str, str] = {}
        self.checkpoints = dict(checkpoints or {})
        self.peer_penalty = peer_penalty
        self.peer_chainwork: dict[str, int] = {}

    def _existing_block(self, chain: Any, block_hash: str) -> bool:
        if hasattr(chain, "get_block_by_hash"):
            return bool(chain.get_block_by_hash(block_hash))
        return False

    def _validate_with_chain(self, chain: Any, headers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if hasattr(chain, "validate_headers_from_tip"):
            validated = chain.validate_headers_from_tip(headers)
            # Older test doubles and transport adapters may validate in-place and
            # return None. Treat that as success and continue with the original
            # header segment instead of crashing with TypeError.
            if validated is None:
                return headers
            return list(validated)
        return headers

    def plan_from_headers(self, chain: Any, headers: list[dict[str, Any]], peer: str) -> dict[str, Any]:
        try:
            checked_headers = self._validate_with_chain(chain, headers)
            tip = chain.tip_hash() if hasattr(chain, "tip_hash") else ""
            start = chain.height() + 1 if hasattr(chain, "height") else None
            states = validate_headers_linked(
                checked_headers,
                expected_previous_hash=tip,
                expected_start_height=start,
                checkpoints=self.checkpoints,
            )
        except Exception as exc:
            self.mark_bad_peer(peer, str(exc))
            if self.peer_penalty:
                self.peer_penalty(peer, str(exc))
            raise
        queued = 0
        for state in states:
            h = state.block_hash
            if not h or self._existing_block(chain, h):
                continue
            if h not in self.jobs:
                self.jobs[h] = DownloadJob(block_hash=h, height=state.height, peer=peer, priority=state.height)
                queued += 1
        self.peer_chainwork[str(peer)] = max(
            self.peer_chainwork.get(str(peer), 0), states[-1].cumulative_work if states else 0
        )
        return {"queued": queued, "job_count": len(self.jobs), "peer": peer, "validated_headers": len(states)}

    def ingest_peer_headers(
        self,
        *,
        peer: str,
        headers: list[dict[str, Any]],
        local_tip_hash: str = "",
        local_height: int = 0,
        have_block: Callable[[str], bool] | None = None,
    ) -> dict[str, Any]:
        """Transport-neutral header ingestion for tests/HTTP P2P clients."""
        try:
            states = validate_headers_linked(
                headers,
                expected_previous_hash=local_tip_hash,
                expected_start_height=int(local_height) + 1,
                checkpoints=self.checkpoints,
            )
        except Exception as exc:
            self.mark_bad_peer(peer, str(exc))
            if self.peer_penalty:
                self.peer_penalty(peer, str(exc))
            raise
        queued = 0
        for state in states:
            if have_block and have_block(state.block_hash):
                continue
            if state.block_hash not in self.jobs:
                self.jobs[state.block_hash] = DownloadJob(
                    block_hash=state.block_hash, height=state.height, peer=peer, priority=state.height
                )
                queued += 1
        self.peer_chainwork[str(peer)] = max(
            self.peer_chainwork.get(str(peer), 0), states[-1].cumulative_work if states else 0
        )
        return {
            "peer": peer,
            "validated_headers": len(states),
            "queued": queued,
            "best_height": states[-1].height if states else local_height,
        }

    def next_jobs(self, limit: int = 16) -> list[DownloadJob]:
        current = int(time.time())
        ready = []
        for job in sorted(self.jobs.values(), key=lambda j: (j.priority, j.height, j.attempts)):
            if job.status not in {"queued", "retry"}:
                continue
            if job.last_attempt_at and current - job.last_attempt_at < self.retry_seconds:
                continue
            ready.append(job)
            if len(ready) >= int(limit):
                break
        return ready

    def mark_attempt(self, block_hash: str) -> None:
        job = self.jobs[block_hash]
        job.attempts += 1
        job.last_attempt_at = int(time.time())
        job.status = "downloading"

    def mark_done(self, block_hash: str) -> None:
        if block_hash in self.jobs:
            self.jobs[block_hash].status = "done"

    def mark_failed(self, block_hash: str, reason: str) -> None:
        job = self.jobs[block_hash]
        job.error = str(reason)[:300]
        job.status = "failed" if job.attempts >= self.max_attempts else "retry"

    def mark_bad_peer(self, peer: str, reason: str) -> None:
        self.bad_peers[str(peer)] = str(reason)[:300]
        for job in self.jobs.values():
            if job.peer == peer and job.status not in {"done", "failed"}:
                job.status = "retry"
                job.error = "peer marked bad: " + self.bad_peers[str(peer)]

    def progress(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for job in self.jobs.values():
            counts[job.status] = counts.get(job.status, 0) + 1
        best_peer = None
        if self.peer_chainwork:
            best_peer = max(self.peer_chainwork.items(), key=lambda item: item[1])[0]
        return {
            "job_count": len(self.jobs),
            "status_counts": counts,
            "bad_peers": self.bad_peers,
            "peer_chainwork": dict(self.peer_chainwork),
            "best_peer_by_chainwork": best_peer,
            "jobs": [j.to_dict() for j in sorted(self.jobs.values(), key=lambda j: j.height)],
        }

    def stalled_jobs(self, *, older_than_seconds: int = 120) -> list[dict[str, Any]]:
        current = int(time.time())
        out = []
        for job in self.jobs.values():
            if (
                job.status == "downloading"
                and job.last_attempt_at
                and current - job.last_attempt_at >= int(older_than_seconds)
            ):
                out.append(job.to_dict())
        return out

    def assign_ready_jobs(self, peers: list[str], *, limit: int = 16) -> list[dict[str, Any]]:
        """Assign ready block-download jobs across available peers."""
        healthy_peers = [p for p in peers if str(p) not in self.bad_peers]
        if not healthy_peers:
            return []
        assignments = []
        ready = self.next_jobs(limit=limit)
        for idx, job in enumerate(ready):
            job.peer = healthy_peers[idx % len(healthy_peers)]
            self.mark_attempt(job.block_hash)
            assignments.append(job.to_dict())
        return assignments

    def assign_from_peerdb(self, peerdb: Any, *, target: int = 16, max_per_group: int = 1) -> list[dict[str, Any]]:
        peers = [p["address"] for p in peerdb.select_outbound_peers(target=target, max_per_group=max_per_group)]
        return self.assign_ready_jobs(peers, limit=target)

    def retry_stalled(self, *, older_than_seconds: int = 120, reason: str = "download stalled") -> list[dict[str, Any]]:
        stalled = self.stalled_jobs(older_than_seconds=older_than_seconds)
        for item in stalled:
            block_hash = item["block_hash"]
            job = self.jobs.get(block_hash)
            if job:
                job.status = "retry" if job.attempts < self.max_attempts else "failed"
                job.error = reason
        return stalled

    def health_report(self, *, stale_seconds: int = 120) -> dict[str, Any]:
        progress = self.progress()
        stalled = self.stalled_jobs(older_than_seconds=stale_seconds)
        failed = progress["status_counts"].get("failed", 0)
        queued = progress["status_counts"].get("queued", 0) + progress["status_counts"].get("retry", 0)
        downloading = progress["status_counts"].get("downloading", 0)
        ok = not stalled and failed == 0 and not self.bad_peers
        return {
            "ok": ok,
            "queued_or_retry": queued,
            "downloading": downloading,
            "failed": failed,
            "stalled": stalled,
            **progress,
        }


class PeerSyncCoordinator:
    """Glue between PeerDatabase and HeaderSyncScheduler."""

    def __init__(self, peerdb: Any, scheduler: HeaderSyncScheduler | None = None):
        self.peerdb = peerdb
        self.scheduler = scheduler or HeaderSyncScheduler(peer_penalty=self._penalize)

    def _penalize(self, peer: str, reason: str) -> None:
        if hasattr(self.peerdb, "record_failure"):
            self.peerdb.record_failure(peer, reason=reason, penalty=5)

    def record_headers(
        self,
        peer: str,
        headers: list[dict[str, Any]],
        *,
        local_tip_hash: str = "",
        local_height: int = 0,
    ) -> dict[str, Any]:
        result = self.scheduler.ingest_peer_headers(
            peer=peer, headers=headers, local_tip_hash=local_tip_hash, local_height=local_height
        )
        if hasattr(self.peerdb, "record_success"):
            self.peerdb.record_success(peer, best_height=int(result.get("best_height") or local_height))
        return result

    def assignment_plan(self, *, target: int = 16) -> dict[str, Any]:
        assignments = self.scheduler.assign_from_peerdb(self.peerdb, target=target)
        return {
            "assignments": assignments,
            "sync_health": self.scheduler.health_report(),
            "peer_health": self.peerdb.health_report(),
        }
