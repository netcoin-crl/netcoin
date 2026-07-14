#!/usr/bin/env python3
"""Check P9 node API v1/OpenAPI/SDK source coverage."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NODE_GET_ROUTES = [
    "/",
    "/info",
    "/health",
    "/status-lite",
    "/metrics",
    "/relay",
    "/events",
    "/events/stream",
    "/chain",
    "/headers",
    "/block/{hash}",
    "/cfilter/{hash}",
    "/compact-block-missing/{hash}",
    "/compact-block/{hash}",
    "/tx/{txid}",
    "/address/{address}",
    "/balance/{address}",
    "/latest",
    "/latest-txs",
    "/supply",
    "/emission",
    "/p2p-hardening",
    "/blocktemplate",
    "/mempool",
    "/fee-estimates",
    "/peers",
    "/utxos",
]

NODE_POST_ROUTES = [
    "/tx",
    "/package",
    "/block",
    "/submitblock",
    "/compact-block",
    "/mempool/clear",
    "/mempool/prune",
    "/peers",
    "/sync",
    "/relay",
]


def openapi_contains_route(text: str, route: str) -> bool:
    if route == "/":
        return "  /:" in text
    return f"  {route}:" in text


def source_contains_v1_aliasing(node_text: str) -> bool:
    return "versioned_api_path" in node_text and "API-Version" in node_text and "Deprecation" in node_text


def main() -> int:
    issues: list[str] = []
    docs = (ROOT / "docs/openapi.yaml").read_text(encoding="utf-8")
    site_docs = (ROOT / "sites/api/openapi.yaml").read_text(encoding="utf-8")
    paths = NODE_GET_ROUTES + NODE_POST_ROUTES
    for route in sorted(set(paths)):
        if not openapi_contains_route(docs, route):
            issues.append(f"docs/openapi.yaml missing node route {route}")
        if not openapi_contains_route(site_docs, route):
            issues.append(f"sites/api/openapi.yaml missing node route {route}")
    for required in [
        "sdk/netcoin-rs/Cargo.toml",
        "sdk/netcoin-rs/src/lib.rs",
        "sdk/netcoin-rs/tests/local_client.rs",
    ]:
        if not (ROOT / required).exists():
            issues.append(f"missing {required}")
    node_text = (ROOT / "netcoin/node.py").read_text(encoding="utf-8")
    if not source_contains_v1_aliasing(node_text):
        issues.append("netcoin/node.py missing v1 alias/deprecation wiring")
    result = {
        "ok": not issues,
        "issues": issues,
        "node_get_route_count": len(NODE_GET_ROUTES),
        "node_post_route_count": len(NODE_POST_ROUTES),
        "checked_openapi_files": 2,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
