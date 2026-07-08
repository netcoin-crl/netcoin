#!/usr/bin/env python3
"""NetCoin public testnet monitor.

Polls the public seed nodes and local web endpoints, then writes a JSON status
file that can be served by Nginx.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

OUTPUT = Path("/opt/netcoin/monitor/status.json")
TARGETS = {
    "seed1": "http://seed1.netcoin.online:28444/info",
    "seed2": "http://seed2.netcoin.online:28444/info",
    "seed3": "http://seed3.netcoin.online:28444/info",
    "explorer": "http://127.0.0.1/",
    "faucet": "http://127.0.0.1/faucet",
}


def fetch(name: str, url: str) -> dict:
    started = time.time()
    try:
        with urlopen(url, timeout=8) as response:
            body = response.read()
            elapsed_ms = round((time.time() - started) * 1000)
            result = {
                "ok": 200 <= response.status < 400,
                "status": response.status,
                "latency_ms": elapsed_ms,
                "url": url,
            }
            if name.startswith("seed"):
                data = json.loads(body.decode("utf-8"))
                node = data.get("node", {})
                result.update(
                    {
                        "height": node.get("height"),
                        "tip_hash": node.get("tip_hash"),
                        "peers": node.get("peers", []),
                    }
                )
            return result
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def compute_alerts(status: dict, prev: dict | None) -> list[str]:
    """Alert only on state transitions so a persistent outage is not re-sent every
    run. A target with no prior record is treated as previously healthy, so the
    first run only alerts on something that is actually down right now."""
    alerts: list[str] = []
    prev_targets = (prev or {}).get("targets", {})
    for name, item in status.get("targets", {}).items():
        was_ok = prev_targets.get(name, {}).get("ok", True)
        now_ok = bool(item.get("ok"))
        if was_ok and not now_ok:
            detail = item.get("error") or item.get("status") or "unreachable"
            alerts.append(f"DOWN: {name} ({item.get('url')}) - {detail}")
        elif not was_ok and now_ok:
            alerts.append(f"RECOVERED: {name}")
    prev_match = (prev or {}).get("seed_tips_match", True)
    now_match = status.get("seed_tips_match", True)
    if prev_match and not now_match:
        alerts.append("WARN: seed tip hashes diverged")
    elif not prev_match and now_match:
        alerts.append("RECOVERED: seed tips back in sync")
    return alerts


def send_alerts(messages: list[str], webhook: str | None = None) -> int:
    """Best-effort POST to a Discord/Slack-style incoming webhook. No-op without a
    webhook URL or messages. Returns the number of messages sent."""
    webhook = webhook or os.environ.get("NETCOIN_ALERT_WEBHOOK")
    if not webhook or not messages:
        return 0
    text = "NetCoin monitor alerts:\n" + "\n".join(messages)
    payload = json.dumps({"content": text, "text": text}).encode("utf-8")
    request = Request(webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        urlopen(request, timeout=8)
        return len(messages)
    except Exception:
        return 0


def main() -> None:
    prev = None
    if OUTPUT.exists():
        try:
            prev = json.loads(OUTPUT.read_text())
        except (OSError, json.JSONDecodeError):
            prev = None

    status = {
        "generated_at": int(time.time()),
        "targets": {name: fetch(name, url) for name, url in TARGETS.items()},
    }
    status["ok"] = all(item.get("ok") for item in status["targets"].values())
    seed_heights = {
        name: item.get("height")
        for name, item in status["targets"].items()
        if name.startswith("seed") and item.get("ok")
    }
    seed_tips = {
        name: item.get("tip_hash")
        for name, item in status["targets"].items()
        if name.startswith("seed") and item.get("ok")
    }
    status["seed_heights"] = seed_heights
    status["seed_tips_match"] = len(set(seed_tips.values())) == 1 if seed_tips else False

    alerts = compute_alerts(status, prev)
    send_alerts(alerts)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, indent=2, sort_keys=True))
    tmp.replace(OUTPUT)


if __name__ == "__main__":
    main()
