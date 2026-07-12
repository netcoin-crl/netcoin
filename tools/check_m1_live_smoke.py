#!/usr/bin/env python3
"""Operator-run live smoke checks for the NetCoin M1 public testnet.

The default mode is a dry-run plan. Use --run only when the operator wants to
make outbound HTTPS requests against seed1 through the documented Host-header
path. This tool never deploys, never restarts services, never reads secrets, and
never claims that the live network is mainnet-ready.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import html.parser
import json
import re
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
DEFAULT_HISTORY_DIR = "reports/live_smoke_history"

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
    response_kind: str = "text"

    def curl_command(self, seed_ip: str) -> str:
        return f"curl -sk -H 'Host: {self.host}' https://{seed_ip}{self.path} | head -20"


LIVE_CHECKS: tuple[LiveCheck, ...] = (
    LiveCheck(
        "api-info",
        "api.netcoin.online",
        "/api/info",
        "Node info endpoint responds",
        ("protocol_version", "genesis_hash", "services"),
        response_kind="json",
    ),
    LiveCheck(
        "api-supply",
        "api.netcoin.online",
        "/api/supply",
        "Supply endpoint responds",
        ("total_minted_sats", "height"),
        response_kind="json",
    ),
    LiveCheck(
        "api-emission",
        "api.netcoin.online",
        "/api/emission",
        "Emission endpoint responds",
        ("height", "subsidy"),
        response_kind="json",
    ),
    LiveCheck(
        "api-fee-estimates",
        "api.netcoin.online",
        "/api/fee-estimates",
        "Fee estimate endpoint responds",
        ("presets", "fast", "normal", "slow"),
        response_kind="json",
    ),
    LiveCheck(
        "api-p2p-hardening",
        "api.netcoin.online",
        "/api/p2p-hardening",
        "P2P hardening endpoint responds",
        ("compact", "pex"),
        response_kind="json",
    ),
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
        ("mempool", "Explorer"),
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
        ("ok", "height", "tip_hash"),
        response_kind="json",
    ),
)


class ScriptTagParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        self.scripts.append({key: value or "" for key, value in attrs})


def wallet_script_expectations() -> list[dict[str, str]]:
    expectations: list[dict[str, str]] = []
    html_path = ROOT / "sites" / "wallet" / "index.html"
    parser = ScriptTagParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    for script in parser.scripts:
        src = script.get("src", "")
        if not src or not script.get("integrity"):
            continue
        script_name = src.split("?", 1)[0].split("/")[-1]
        script_path = ROOT / "sites" / "wallet" / script_name
        if not script_path.exists():
            continue
        digest = base64.b64encode(hashlib.sha384(script_path.read_bytes()).digest()).decode("ascii")
        expectations.append(
            {
                "script": script_name,
                "src": src,
                "cache_buster": src.split("?", 1)[1] if "?" in src else "",
                "expected_integrity": "sha384-" + digest,
                "repo_integrity": script["integrity"],
            }
        )
    return expectations


def wallet_sri_check(seed_ip: str, timeout: int) -> dict[str, Any]:
    check = LiveCheck(
        "wallet-sri",
        "wallet.netcoin.online",
        "/",
        "Wallet HTML SRI matches repo scripts",
        ("wallet-app.js", "integrity="),
        max_bytes=96_000,
    )
    result = fetch_check(check, seed_ip=seed_ip, timeout=timeout)
    if result.get("status") == "fail":
        return result

    body = str(result.get("body_preview", ""))
    # fetch_check keeps a preview for reports; fetch the full configured slice so
    # script tags near the end of the wallet HTML are still checked.
    request = urllib.request.Request(
        f"https://{seed_ip}/",
        headers={"Host": check.host, "User-Agent": "netcoin-live-smoke/1.0"},
        method="GET",
    )
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        body = response.read(check.max_bytes).decode("utf-8", errors="replace")

    issues = list(result.get("issues", []))
    checked: list[dict[str, str]] = []
    for expected in wallet_script_expectations():
        script = expected["script"]
        src = re.escape(expected["src"])
        integrity = re.escape(expected["expected_integrity"])
        if expected["repo_integrity"] != expected["expected_integrity"]:
            issues.append(f"repo SRI mismatch for {script}")
        if not re.search(rf'src=["\']{src}["\'][^>]*integrity=["\']{integrity}["\']', body):
            issues.append(f"live wallet HTML missing repo SRI for {script}")
        checked.append(expected)
    result["wallet_sri"] = checked
    result["status"] = "pass" if not issues else "fail"
    if issues:
        result["issues"] = issues
    else:
        result.pop("issues", None)
    return result


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
    validation_body = body
    if check.response_kind == "json":
        try:
            json.loads(validation_body)
        except json.JSONDecodeError as exc:
            issues.append(f"invalid JSON: {exc.msg}")
        for token in check.required_tokens:
            if token not in validation_body:
                issues.append(f"missing token: {token}")
    else:
        normalized_body = validation_body.lower()
        for token in check.required_tokens:
            if token.lower() not in normalized_body:
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
        "response_kind": check.response_kind,
    }


def history_path(history_dir: str | Path, *, now: dt.datetime | None = None) -> Path:
    stamp = (now or dt.datetime.now(dt.UTC)).strftime("%Y-%m-%dT%H%M%SZ")
    return ROOT / history_dir / f"{stamp}.json"


def build_report(*, seed_ip: str, run: bool, timeout: int) -> dict[str, Any]:
    if run:
        checks = [fetch_check(check, seed_ip=seed_ip, timeout=timeout) for check in LIVE_CHECKS]
        checks.append(wallet_sri_check(seed_ip=seed_ip, timeout=timeout))
    else:
        checks = [planned_check(check, seed_ip) for check in LIVE_CHECKS]
        checks.append(
            {
                "id": "wallet-sri",
                "label": "Wallet HTML SRI matches repo scripts",
                "host": "wallet.netcoin.online",
                "path": "/",
                "status": "planned",
                "required_scripts": wallet_script_expectations(),
                "curl": "repo-computed SRI compared with live wallet HTML during --run",
            }
        )
    incomplete = [check["id"] for check in checks if check.get("status") == "fail"]
    return {
        "ok": not incomplete,
        "scope": "live testnet smoke plan" if not run else "live testnet smoke run",
        "seed_ip": seed_ip,
        "mode": "run" if run else "dry-run",
        "history_dir": DEFAULT_HISTORY_DIR,
        "incomplete": incomplete,
        "does_not_claim": list(DOES_NOT_CLAIM),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or run NetCoin M1 live smoke checks.")
    parser.add_argument("--seed-ip", default=DEFAULT_SEED_IP)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--out", default="reports/m1_live_smoke_plan.json")
    parser.add_argument("--history-dir", default=DEFAULT_HISTORY_DIR)
    parser.add_argument("--no-history", action="store_true", help="do not write append-only live smoke history")
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
        if args.run and not args.no_history:
            hist = history_path(args.history_dir)
            hist.parent.mkdir(parents=True, exist_ok=True)
            hist.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
