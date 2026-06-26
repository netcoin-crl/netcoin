"""Node configuration file support (netcoin.conf).

Supports either JSON or a simple `key = value` / `key value` line format. Keys map
to node options: data_dir, host, port, peer (repeatable), seeds (bool), advertise,
rate_limit_per_min, rpc_token, network. Lines starting with # are comments. Unknown
keys are ignored. This is convenience config, never consensus.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


_LIST_KEYS = {"peer", "peers"}
_BOOL_KEYS = {"seeds", "trust_proxy_headers"}
_INT_KEYS = {"port", "rate_limit_per_min", "request_timeout", "request_retries", "sync_interval"}


def _coerce(key: str, value: Any) -> Any:
    if key in _BOOL_KEYS:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if key in _INT_KEYS:
        return int(value)
    return value


def load_config(path: str | Path) -> Dict[str, Any]:
    text = Path(path).read_text()
    stripped = text.strip()
    if stripped.startswith("{"):
        raw = json.loads(stripped)
        config: Dict[str, Any] = {}
        for key, value in raw.items():
            if key in _LIST_KEYS:
                config.setdefault("peer", [])
                config["peer"].extend(value if isinstance(value, list) else [value])
            else:
                config[key] = _coerce(key, value)
        return config

    config = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
        else:
            key, _, value = line.partition(" ")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if key in _LIST_KEYS:
            config.setdefault("peer", []).append(value)
        else:
            config[key] = _coerce(key, value)
    return config
