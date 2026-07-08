"""Headers-first synchronization scheduler helpers."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class DownloadJob:
    block_hash: str
    height: int
    peer: str
    attempts: int = 0
    last_attempt_at: int = 0
    status: str = "queued"
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HeaderSyncScheduler:
    """Queue missing blocks after validating a header segment."""

    def __init__(self, *, max_attempts: int = 3, retry_seconds: int = 30):
        self.max_attempts = int(max_attempts)
        self.retry_seconds = int(retry_seconds)
        self.jobs: dict[str, DownloadJob] = {}
        self.bad_peers: dict[str, str] = {}

    def plan_from_headers(self, chain: Any, headers: list[dict[str, Any]], peer: str) -> dict[str, Any]:
        chain.validate_headers_from_tip(headers)
        queued = 0
        for header in headers:
            h = str(header.get("hash") or "")
            if not h or chain.get_block_by_hash(h):
                continue
            if h not in self.jobs:
                self.jobs[h] = DownloadJob(block_hash=h, height=int(header.get("height", 0)), peer=peer)
                queued += 1
        return {"queued": queued, "job_count": len(self.jobs), "peer": peer}

    def next_jobs(self, limit: int = 16) -> list[DownloadJob]:
        current = int(time.time())
        ready = []
        for job in sorted(self.jobs.values(), key=lambda j: (j.height, j.attempts)):
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
        return {
            "job_count": len(self.jobs),
            "status_counts": counts,
            "bad_peers": self.bad_peers,
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
        if not peers:
            return []
        assignments = []
        ready = self.next_jobs(limit=limit)
        for idx, job in enumerate(ready):
            job.peer = peers[idx % len(peers)]
            self.mark_attempt(job.block_hash)
            assignments.append(job.to_dict())
        return assignments

    def health_report(self, *, stale_seconds: int = 120) -> dict[str, Any]:
        progress = self.progress()
        stalled = self.stalled_jobs(older_than_seconds=stale_seconds)
        failed = progress["status_counts"].get("failed", 0)
        queued = progress["status_counts"].get("queued", 0) + progress["status_counts"].get("retry", 0)
        ok = not stalled and failed == 0
        return {"ok": ok, "queued_or_retry": queued, "failed": failed, "stalled": stalled, **progress}
