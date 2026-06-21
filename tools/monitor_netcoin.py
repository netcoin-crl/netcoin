#!/usr/bin/env python3
"""NetCoin public testnet monitor.

Polls the public seed nodes and local web endpoints, then writes a JSON status
file that can be served by Nginx.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


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


def main() -> None:
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
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, indent=2, sort_keys=True))
    tmp.replace(OUTPUT)


if __name__ == "__main__":
    main()
