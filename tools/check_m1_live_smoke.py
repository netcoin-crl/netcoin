#!/usr/bin/env python3
"""Operator-run live smoke checks for the NetCoin M1 public testnet.

The default mode is a dry-run plan. Use --run only when the operator wants to
make outbound HTTPS requests against seed1 through the documented Host-header
path. This tool never deploys, never restarts services, never reads secrets, and
never claims that the live network is mainnet-ready.
"""

from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED_IP = "18.220.89.128"
DEFAULT_TIMEOUT_SECONDS = 10

DOES_NOT_CLAIM = (
    "seed deployment",
    "systemd restart",
    "real CAPTCHA credentials",
    "external audit completion",
    "mainnet readiness",
)


@dataclass(frozen=True)
class LiveCheck:
    check_id: str
    host: str
    path: str
    label: str
    required_tokens: tuple[str, ...] = ()
    max_bytes: int = 32_768

    def curl_command(self, seed_ip: str) -> str:
        return f"curl -sk -H 'Host: {self.host}' https://{seed_ip}{self.path} | head -20"


LIVE_CHECKS: tuple[LiveCheck, ...] = (
    LiveCheck(
        "wallet-home",
        "wallet.netcoin.online",
        "/",
        "Wallet public home loads",
        ("NetCoin", "Wallet", "testnet"),
    ),
    LiveCheck(
        "faucet-home",
        "faucet.netcoin.online",
        "/",
        "Faucet public home loads",
        ("Faucet", "testnet"),
    ),
    LiveCheck(
        "explorer-mempool",
        "explorer.netcoin.online",
        "/mempool.html",
        "Explorer mempool page loads",
        ("mempool", "fee", "Explorer"),
    ),
    LiveCheck(
        "status-home",
        "status.netcoin.online",
        "/",
        "Status page exposes M1 snapshot",
        ("Live testnet snapshot", "Incident response"),
    ),
    LiveCheck(
        "docs-journey",
        "docs.netcoin.online",
        "/testnet-user-journey.html",
        "First-time tester journey is public",
        ("M1 tester path", "wallet.netcoin.online", "faucet.netcoin.online"),
    ),
    LiveCheck(
        "api-health",
        "api.netcoin.online",
        "/api/health",
        "API health endpoint responds",
        ("status",),
    ),
)


def fetch_check(check: LiveCheck, *, seed_ip: str, timeout: int) -> dict[str, Any]:
    url = f"https://{seed_ip}{check.path}"
    request = urllib.request.Request(
        url,
        headers={"Host": check.host, "User-Agent": "netcoin-m1-live-smoke/1.0"},
        method="GET",
    )
    context = ssl._create_unverified_context()
    started = time.monotonic()
    result: dict[str, Any] = {
        "id": check.check_id,
        "label": check.label,
        "host": check.host,
        "path": check.path,
        "curl": check.curl_command(seed_ip),
        "status": "pending",
    }
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read(check.max_bytes).decode("utf-8", errors="replace")
            result["http_status"] = response.status
            result["duration_seconds"] = round(time.monotonic() - started, 3)
            result["body_preview"] = body[:800]
    except urllib.error.HTTPError as exc:
        body = exc.read(check.max_bytes).decode("utf-8", errors="replace")
        result.update(
            {
                "status": "fail",
                "http_status": exc.code,
                "duration_seconds": round(time.monotonic() - started, 3),
                "issues": [f"HTTP {exc.code}"],
                "body_preview": body[:800],
            }
        )
        return result
    except Exception as exc:  # pragma: no cover - exercised by operators live.
        result.update(
            {
                "status": "fail",
                "duration_seconds": round(time.monotonic() - started, 3),
                "issues": [f"request failed: {exc.__class__.__name__}: {exc}"],
            }
        )
        return result

    issues: list[str] = []
    status_code = int(result.get("http_status", 0))
    if status_code >= 500:
        issues.append(f"HTTP {status_code}")
    body_preview = str(result.get("body_preview", ""))
    for token in check.required_tokens:
        if token not in body_preview:
            issues.append(f"missing token: {token}")
    result["status"] = "pass" if not issues else "fail"
    if issues:
        result["issues"] = issues
    return result


def planned_check(check: LiveCheck, seed_ip: str) -> dict[str, Any]:
    return {
        "id": check.check_id,
        "label": check.label,
        "host": check.host,
        "path": check.path,
        "required_tokens": list(check.required_tokens),
        "curl": check.curl_command(seed_ip),
        "status": "planned",
    }


def build_report(*, seed_ip: str, run: bool, timeout: int) -> dict[str, Any]:
    if run:
        checks = [fetch_check(check, seed_ip=seed_ip, timeout=timeout) for check in LIVE_CHECKS]
    else:
        checks = [planned_check(check, seed_ip) for check in LIVE_CHECKS]
    incomplete = [check["id"] for check in checks if check.get("status") == "fail"]
    return {
        "ok": not incomplete,
        "scope": "M1 live smoke plan" if not run else "M1 live smoke run",
        "seed_ip": seed_ip,
        "mode": "run" if run else "dry-run",
        "incomplete": incomplete,
        "does_not_claim": list(DOES_NOT_CLAIM),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or run NetCoin M1 live smoke checks.")
    parser.add_argument("--seed-ip", default=DEFAULT_SEED_IP)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--out", default="reports/m1_live_smoke_plan.json")
    parser.add_argument("--run", action="store_true", help="make outbound HTTPS requests")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report = build_report(seed_ip=args.seed_ip, run=args.run, timeout=args.timeout)
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if not args.no_write:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
