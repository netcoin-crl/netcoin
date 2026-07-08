"""Resolution workflow helpers."""

from __future__ import annotations

import hashlib
import time
from typing import Any


def evidence_object(payload: dict[str, Any]) -> dict[str, Any]:
    raw = "|".join(
        str(payload.get(k, "")) for k in ("url", "title", "timestamp", "submitter", "source_type", "comments")
    )
    return {
        "url": str(payload.get("url") or payload.get("evidence_url") or "")[:500],
        "title": str(payload.get("title") or "")[:200],
        "timestamp": int(payload.get("timestamp") or time.time()),
        "submitter": str(payload.get("submitter") or payload.get("actor") or "operator")[:120],
        "source_type": str(payload.get("source_type") or "url")[:40],
        "sha256": str(payload.get("sha256") or hashlib.sha256(raw.encode()).hexdigest()),
        "comments": str(payload.get("comments") or payload.get("resolution_note") or "")[:1000],
    }
