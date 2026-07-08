"""Minimal structured (JSON-line) logging for NetCoin services.

One JSON object per line keeps node/faucet/miner/explorer/RPC logs greppable and
machine-parseable without pulling in a logging framework. Set NETCOIN_LOG_JSON=1 to
emit structured lines; otherwise `emit` is a no-op so existing human output is kept.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any


def structured_log(event: str, component: str = "node", **fields: Any) -> str:
    record = {"ts": round(time.time(), 3), "component": component, "event": event}
    record.update(fields)
    return json.dumps(record, sort_keys=True, default=str)


def json_logging_enabled() -> bool:
    return os.environ.get("NETCOIN_LOG_JSON", "").strip().lower() in ("1", "true", "yes", "on")


def emit(event: str, component: str = "node", **fields: Any) -> None:
    """Print a structured log line to stderr when JSON logging is enabled."""
    if json_logging_enabled():
        print(structured_log(event, component=component, **fields), file=sys.stderr)
