#!/usr/bin/env python3
"""Check the public NetCoin seed nodes from an operator laptop.

This is intentionally read-only. It does not need SSH access, node data files,
wallet files, private keys, or admin tokens.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

DEFAULT_SEEDS = [
    "http://18.220.89.128:28444",
    "http://18.220.197.20:28444",
    "http://18.226.74.252:28444",
]


@dataclass
class SeedCheck:
    url: str
    ok: bool
    detail: dict[str, Any]


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_seed(seed: str, timeout: float) -> SeedCheck:
    base = seed.rstrip("/")
    try:
        info = fetch_json(base + "/info", timeout=timeout).get("node", {})
        health = fetch_json(base + "/health", timeout=timeout)
        return SeedCheck(
            url=base,
            ok=bool(info and health.get("ok")),
            detail={
                "version": info.get("version"),
                "height": info.get("height"),
                "tip_hash": info.get("tip_hash"),
                "peers": len(info.get("peers") or []),
                "mempool": info.get("mempool_transactions"),
                "fast_crypto": info.get("fast_crypto"),
                "crypto_backend": (info.get("crypto_backend") or {}).get("ecdsa_verify"),
                "uptime_seconds": info.get("uptime_seconds"),
                "health_ok": health.get("ok"),
                "services": info.get("services") or [],
            },
        )
    except (OSError, TimeoutError, URLError, ValueError, json.JSONDecodeError) as exc:
        return SeedCheck(url=base, ok=False, detail={"error": str(exc)})


def summarize(checks: list[SeedCheck]) -> dict[str, Any]:
    heights = [int(c.detail.get("height")) for c in checks if c.ok and c.detail.get("height") is not None]
    versions = sorted({str(c.detail.get("version")) for c in checks if c.ok and c.detail.get("version")})
    tips = sorted({str(c.detail.get("tip_hash")) for c in checks if c.ok and c.detail.get("tip_hash")})
    return {
        "ok": all(c.ok for c in checks) and len(set(heights)) <= 1 and len(tips) <= 1 and len(versions) <= 1,
        "healthy": sum(1 for c in checks if c.ok),
        "total": len(checks),
        "versions": versions,
        "heights": heights,
        "height_spread": (max(heights) - min(heights)) if heights else None,
        "tips": tips,
        "seeds": [{"url": c.url, "ok": c.ok, **c.detail} for c in checks],
    }


def print_table(report: dict[str, Any]) -> None:
    print(f"NetCoin public network: {report['healthy']}/{report['total']} healthy")
    print(f"versions={', '.join(report['versions']) or '-'} height_spread={report['height_spread']}")
    print("")
    print(f"{'seed':<30} {'ok':<3} {'version':<8} {'height':<8} {'peers':<5} {'crypto':<22} tip")
    for seed in report["seeds"]:
        tip = str(seed.get("tip_hash") or seed.get("error") or "-")
        print(
            f"{seed['url']:<30} {seed['ok']!s:<3} "
            f"{seed.get('version') or '-'!s:<8} {seed.get('height') or '-'!s:<8} "
            f"{seed.get('peers') or '-'!s:<5} {seed.get('crypto_backend') or '-'!s:<22} "
            f"{tip[:24]}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only public NetCoin seed health check")
    parser.add_argument(
        "seeds", nargs="*", default=DEFAULT_SEEDS, help="seed base URLs; default checks the three public seeds"
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="per-request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args(argv)
    report = summarize([check_seed(seed, args.timeout) for seed in args.seeds])
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_table(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
