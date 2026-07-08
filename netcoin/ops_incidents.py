"""Incident tracking and runbook helpers for NetCoin operators."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

RUNBOOKS: dict[str, list[str]] = {
    "NetCoinStuckChain": [
        "check local node height",
        "compare seed node tips",
        "inspect miner health",
        "pause exchange withdrawals if divergence is confirmed",
    ],
    "NetCoinNoPeers": [
        "check network reachability",
        "refresh peer database",
        "verify seed nodes",
        "inspect firewall and p2p port",
    ],
    "NetCoinWebhookDeadLetters": [
        "open webhook dead-letter queue",
        "verify merchant endpoint health",
        "replay safe events",
        "notify affected merchant",
    ],
    "NetCoinHighMempool": [
        "inspect fee distribution",
        "check spam indicators",
        "raise faucet difficulty if faucet-driven",
        "publish fee guidance",
    ],
}


class IncidentStore:
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
            conn.execute("""CREATE TABLE IF NOT EXISTS incidents(
                    incident_id TEXT PRIMARY KEY,
                    alert TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    first_seen INTEGER NOT NULL,
                    last_seen INTEGER NOT NULL,
                    acknowledged_by TEXT DEFAULT '',
                    resolved_at INTEGER DEFAULT 0,
                    payload_json TEXT NOT NULL
                )""")
            conn.commit()

    @staticmethod
    def incident_id(alert: dict[str, Any]) -> str:
        import hashlib

        key = f"{alert.get('alert')}|{alert.get('message','')}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def ingest_alerts(self, alerts: list[dict[str, Any]]) -> dict[str, Any]:
        current = int(time.time())
        opened = 0
        updated = 0
        with self.connect() as conn:
            for alert in alerts:
                incident_id = self.incident_id(alert)
                existing = conn.execute(
                    "SELECT incident_id FROM incidents WHERE incident_id=?", (incident_id,)
                ).fetchone()
                payload = json.dumps(alert, sort_keys=True)
                if existing:
                    conn.execute(
                        "UPDATE incidents SET last_seen=?, payload_json=?, status=CASE WHEN status='resolved' THEN 'open' ELSE status END WHERE incident_id=?",
                        (current, payload, incident_id),
                    )
                    updated += 1
                else:
                    conn.execute(
                        "INSERT INTO incidents(incident_id,alert,severity,status,message,first_seen,last_seen,payload_json) VALUES(?,?,?,?,?,?,?,?)",
                        (
                            incident_id,
                            str(alert.get("alert", "UnknownAlert")),
                            str(alert.get("severity", "warning")),
                            "open",
                            str(alert.get("message", "")),
                            current,
                            current,
                            payload,
                        ),
                    )
                    opened += 1
            conn.commit()
        return {"opened": opened, "updated": updated, "total_ingested": len(alerts)}

    def acknowledge(self, incident_id: str, operator: str) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                "UPDATE incidents SET status='acknowledged', acknowledged_by=? WHERE incident_id=? AND status<>'resolved'",
                (operator, incident_id),
            )
            conn.commit()
        return self.get(incident_id)

    def resolve(self, incident_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                "UPDATE incidents SET status='resolved', resolved_at=? WHERE incident_id=?",
                (int(time.time()), incident_id),
            )
            conn.commit()
        return self.get(incident_id)

    def list(self, *, include_resolved: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM incidents" if include_resolved else "SELECT * FROM incidents WHERE status<>'resolved'"
        with self.connect() as conn:
            rows = [dict(row) for row in conn.execute(sql + " ORDER BY severity DESC, last_seen DESC").fetchall()]
        for row in rows:
            row["payload"] = json.loads(row.pop("payload_json") or "{}")
            row["runbook"] = RUNBOOKS.get(
                row["alert"], ["inspect service logs", "collect diagnostics", "escalate to maintainer"]
            )
        return rows

    def get(self, incident_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
        if not row:
            return {}
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json") or "{}")
        data["runbook"] = RUNBOOKS.get(
            data["alert"], ["inspect service logs", "collect diagnostics", "escalate to maintainer"]
        )
        return data


def runbook_for_alert(alert: str) -> dict[str, Any]:
    return {
        "alert": alert,
        "steps": RUNBOOKS.get(alert, ["inspect service logs", "collect diagnostics", "escalate to maintainer"]),
    }
