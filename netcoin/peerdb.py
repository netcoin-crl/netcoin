"""Persistent peer database for NetCoin nodes."""

from __future__ import annotations

import ipaddress
import json
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class PeerDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS peers(
                    address TEXT PRIMARY KEY,
                    host TEXT NOT NULL,
                    port INTEGER,
                    source TEXT DEFAULT '',
                    user_agent TEXT DEFAULT '',
                    services_json TEXT DEFAULT '[]',
                    last_seen INTEGER DEFAULT 0,
                    last_success INTEGER DEFAULT 0,
                    last_failure INTEGER DEFAULT 0,
                    best_height INTEGER DEFAULT 0,
                    latency_ms INTEGER DEFAULT 0,
                    score INTEGER DEFAULT 0,
                    banned_until INTEGER DEFAULT 0,
                    ban_reason TEXT DEFAULT '',
                    anchor INTEGER DEFAULT 0,
                    feeler_attempts INTEGER DEFAULT 0,
                    failures INTEGER DEFAULT 0,
                    successes INTEGER DEFAULT 0
                )""")
            conn.commit()

    @staticmethod
    def normalize(address: str) -> tuple[str, str, int | None]:
        text = str(address).strip().rstrip("/")
        parsed = urlparse(text if "://" in text else "http://" + text)
        host = parsed.hostname or text
        port = parsed.port
        normalized = f"{parsed.scheme or 'http'}://{host}" + (f":{port}" if port else "")
        return normalized.rstrip("/"), host, port

    @staticmethod
    def diversity_key(host: str) -> str:
        try:
            ip = ipaddress.ip_address(host)
            if ip.version == 4:
                net = ipaddress.ip_network(f"{ip}/24", strict=False)
            else:
                net = ipaddress.ip_network(f"{ip}/64", strict=False)
            return str(net)
        except ValueError:
            labels = host.lower().split(".")
            return ".".join(labels[-2:]) if len(labels) >= 2 else host.lower()

    def upsert_peer(
        self,
        address: str,
        *,
        source: str = "manual",
        user_agent: str = "",
        services: list[str] | None = None,
        anchor: bool = False,
        best_height: int | None = None,
    ) -> dict[str, Any]:
        normalized, host, port = self.normalize(address)
        current = int(time.time())
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO peers(address,host,port,source,user_agent,services_json,last_seen,anchor,best_height)
                   VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(address) DO UPDATE SET
                       host=excluded.host, port=excluded.port, source=excluded.source,
                       user_agent=COALESCE(NULLIF(excluded.user_agent,''), peers.user_agent),
                       services_json=excluded.services_json,
                       last_seen=excluded.last_seen,
                       anchor=MAX(peers.anchor, excluded.anchor),
                       best_height=MAX(peers.best_height, excluded.best_height)""",
                (
                    normalized,
                    host,
                    port,
                    source,
                    user_agent,
                    json.dumps(services or []),
                    current,
                    int(anchor),
                    int(best_height or 0),
                ),
            )
            conn.commit()
        return self.get_peer(normalized)

    def record_success(
        self, address: str, *, latency_ms: int = 0, best_height: int = 0, user_agent: str = ""
    ) -> dict[str, Any]:
        normalized, _, _ = self.normalize(address)
        current = int(time.time())
        self.upsert_peer(normalized, user_agent=user_agent, best_height=best_height)
        with self.connect() as conn:
            conn.execute(
                "UPDATE peers SET last_success=?, last_seen=?, latency_ms=?, best_height=MAX(best_height,?), successes=successes+1, score=MIN(score+1,100) WHERE address=?",
                (current, current, int(latency_ms), int(best_height), normalized),
            )
            conn.commit()
        return self.get_peer(normalized)

    def record_failure(
        self, address: str, *, reason: str = "", penalty: int = 1, ban_threshold: int = -20, ban_seconds: int = 3600
    ) -> dict[str, Any]:
        normalized, _, _ = self.normalize(address)
        self.upsert_peer(normalized)
        current = int(time.time())
        with self.connect() as conn:
            row = conn.execute("SELECT score FROM peers WHERE address=?", (normalized,)).fetchone()
            next_score = int(row["score"] if row else 0) - abs(int(penalty))
            banned_until = current + int(ban_seconds) if next_score <= int(ban_threshold) else 0
            conn.execute(
                "UPDATE peers SET last_failure=?, failures=failures+1, score=?, banned_until=MAX(banned_until,?), ban_reason=CASE WHEN ? > 0 THEN ? ELSE ban_reason END WHERE address=?",
                (current, next_score, banned_until, banned_until, reason, normalized),
            )
            conn.commit()
        return self.get_peer(normalized)

    def mark_feeler(self, address: str) -> None:
        normalized, _, _ = self.normalize(address)
        self.upsert_peer(normalized)
        with self.connect() as conn:
            conn.execute("UPDATE peers SET feeler_attempts=feeler_attempts+1 WHERE address=?", (normalized,))
            conn.commit()

    def get_peer(self, address: str) -> dict[str, Any]:
        normalized, _, _ = self.normalize(address)
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM peers WHERE address=?", (normalized,)).fetchone()
        if not row:
            return {}
        data = dict(row)
        data["services"] = json.loads(data.pop("services_json") or "[]")
        data["diversity_key"] = self.diversity_key(data["host"])
        data["banned"] = int(data.get("banned_until") or 0) > int(time.time())
        return data

    def candidates(
        self, *, limit: int = 32, include_banned: bool = False, max_per_group: int = 2
    ) -> list[dict[str, Any]]:
        current = int(time.time())
        with self.connect() as conn:
            rows = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM peers ORDER BY anchor DESC, score DESC, last_success DESC, last_seen DESC"
                ).fetchall()
            ]
        out = []
        groups: dict[str, int] = {}
        for row in rows:
            row["services"] = json.loads(row.pop("services_json") or "[]")
            row["diversity_key"] = self.diversity_key(row["host"])
            row["banned"] = int(row.get("banned_until") or 0) > current
            if row["banned"] and not include_banned:
                continue
            if groups.get(row["diversity_key"], 0) >= int(max_per_group) and not row.get("anchor"):
                continue
            groups[row["diversity_key"]] = groups.get(row["diversity_key"], 0) + 1
            out.append(row)
            if len(out) >= int(limit):
                break
        return out

    def export_node_map(self) -> dict[str, Any]:
        peers = self.candidates(limit=1000, include_banned=True, max_per_group=1000)
        groups: dict[str, int] = {}
        for peer in peers:
            groups[peer["diversity_key"]] = groups.get(peer["diversity_key"], 0) + 1
        return {"peer_count": len(peers), "groups": groups, "peers": peers}

    def select_outbound_peers(self, *, target: int = 8, max_per_group: int = 1) -> list[dict[str, Any]]:
        """Choose a diverse outbound set biased toward anchors and good scores."""
        return self.candidates(limit=target, include_banned=False, max_per_group=max_per_group)

    def prune_stale(self, *, older_than_seconds: int = 30 * 24 * 3600, keep_anchors: bool = True) -> dict[str, Any]:
        cutoff = int(time.time()) - int(older_than_seconds)
        with self.connect() as conn:
            if keep_anchors:
                cur = conn.execute("DELETE FROM peers WHERE last_seen < ? AND anchor=0", (cutoff,))
            else:
                cur = conn.execute("DELETE FROM peers WHERE last_seen < ?", (cutoff,))
            deleted = cur.rowcount
            conn.commit()
        return {"deleted": int(deleted or 0), "cutoff": cutoff, "keep_anchors": bool(keep_anchors)}

    def health_report(self) -> dict[str, Any]:
        peers = self.candidates(limit=10000, include_banned=True, max_per_group=10000)
        banned = [p for p in peers if p.get("banned")]
        active = [p for p in peers if not p.get("banned")]
        groups: dict[str, int] = {}
        best_height = 0
        for peer in peers:
            groups[peer["diversity_key"]] = groups.get(peer["diversity_key"], 0) + 1
            best_height = max(best_height, int(peer.get("best_height") or 0))
        score = 100
        if not active:
            score -= 70
        if len(groups) < max(1, min(3, len(active))):
            score -= 15
        if banned and len(banned) > len(active):
            score -= 15
        return {
            "ok": bool(active) and score >= 50,
            "health_score": max(0, score),
            "peer_count": len(peers),
            "active_peer_count": len(active),
            "banned_peer_count": len(banned),
            "diversity_group_count": len(groups),
            "best_height": best_height,
            "recommended_outbound": self.select_outbound_peers(target=8),
        }
