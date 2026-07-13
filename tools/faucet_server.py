#!/usr/bin/env python3
"""Small stdlib-only NetCoin testnet faucet.

This is intentionally simple infrastructure glue. It validates a submitted
NetCoin address, rate-limits by client IP, sends a small testnet amount from a
hot wallet, and broadcasts the transaction to a seed node.
"""

from __future__ import annotations

# Allow `python tools/<script>.py` from the repository root or elsewhere.
import sys as _sys
from pathlib import Path as _Path

_repo_root = _Path(__file__).resolve().parents[1]
if str(_repo_root) not in _sys.path:
    _sys.path.insert(0, str(_repo_root))

import html
import json
import os
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from netcoin.captcha_provider import CaptchaConfig, verify_token
from netcoin.crypto import validate_address
from netcoin.faucet_abuse import (
    abuse_summary,
    daily_spend_report,
    issue_challenge,
    record_abuse_event,
    reputation_score,
    verify_pow,
)
from netcoin.node import client_ip_from_headers
from netcoin.tx import amount_to_sats

HOST = os.environ.get("NETCOIN_FAUCET_HOST", "127.0.0.1")
PORT = int(os.environ.get("NETCOIN_FAUCET_PORT", "8081"))
NETCOIN_PREFIX = Path(os.environ.get("NETCOIN_PREFIX", "/opt/netcoin"))
NETCOIN_SOURCE_DIR = Path(os.environ.get("NETCOIN_SOURCE_DIR", str(NETCOIN_PREFIX / "netcoin-v2")))
PYTHON = os.environ.get("NETCOIN_PYTHON", str(NETCOIN_SOURCE_DIR / ".venv/bin/python"))
DATA_DIR = os.environ.get("NETCOIN_DATA_DIR", "/opt/netcoin/.netcoin-testnet")
WALLET = os.environ.get("NETCOIN_FAUCET_WALLET", "/opt/netcoin/wallets/testnet-miner.json")
BROADCAST_TO = os.environ.get("NETCOIN_BROADCAST_TO", "http://127.0.0.1:28444")
STATE_FILE = Path(os.environ.get("NETCOIN_FAUCET_STATE", "/opt/netcoin/faucet/state.json"))
AMOUNT = os.environ.get("NETCOIN_FAUCET_AMOUNT", "5")
FEE = os.environ.get("NETCOIN_FAUCET_FEE", "0.01")
COOLDOWN_SECONDS = int(os.environ.get("NETCOIN_FAUCET_COOLDOWN_SECONDS", str(60 * 60)))  # 1h between claims
ADDRESS_COOLDOWN_SECONDS = int(os.environ.get("NETCOIN_FAUCET_ADDRESS_COOLDOWN_SECONDS", str(COOLDOWN_SECONDS)))
# Hardening knobs.
MAX_BODY_BYTES = int(os.environ.get("NETCOIN_FAUCET_MAX_BODY", "4096"))
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("NETCOIN_FAUCET_MAX_PER_MINUTE", "5"))
MAX_ABUSE_LOG = int(os.environ.get("NETCOIN_FAUCET_MAX_ABUSE_LOG", "200"))
QUEUE_MODE = os.environ.get("NETCOIN_FAUCET_QUEUE_MODE", "sync").strip().lower()
MAX_QUEUE_ITEMS = int(os.environ.get("NETCOIN_FAUCET_MAX_QUEUE", "100"))
ADMIN_TOKEN = os.environ.get("NETCOIN_FAUCET_ADMIN_TOKEN", "")
MIN_SPENDABLE_SATS = int(os.environ.get("NETCOIN_FAUCET_MIN_SPENDABLE_SATS", "1000000000"))
REFILL_ADDRESS = os.environ.get("NETCOIN_FAUCET_REFILL_ADDRESS", "")
# CAPTCHA integration. Provider choices:
#   none       disabled (default)
#   simple     local text challenge for private beta / offline tests
#   turnstile  Cloudflare Turnstile siteverify
#   hcaptcha   hCaptcha siteverify
CAPTCHA_PROVIDER = os.environ.get("NETCOIN_FAUCET_CAPTCHA_PROVIDER", "none").strip().lower()
CAPTCHA_SITEKEY = os.environ.get("NETCOIN_FAUCET_CAPTCHA_SITEKEY", "")
CAPTCHA_SECRET = os.environ.get("NETCOIN_FAUCET_CAPTCHA_SECRET", "")
CAPTCHA_VERIFY_URL = os.environ.get("NETCOIN_FAUCET_CAPTCHA_VERIFY_URL", "")
CAPTCHA_SIMPLE_QUESTION = os.environ.get("NETCOIN_FAUCET_CAPTCHA_QUESTION", "Type netcoin")
CAPTCHA_SIMPLE_ANSWER = os.environ.get("NETCOIN_FAUCET_CAPTCHA_ANSWER", "netcoin").strip().lower()
POW_DIFFICULTY = int(os.environ.get("NETCOIN_FAUCET_POW_DIFFICULTY", "0"))
POW_SECRET = os.environ.get("NETCOIN_FAUCET_POW_SECRET", "netcoin-faucet-local-secret")
POW_TTL_SECONDS = int(os.environ.get("NETCOIN_FAUCET_POW_TTL", "300"))
DAILY_SPEND_CAP_SATS = int(os.environ.get("NETCOIN_FAUCET_DAILY_CAP_SATS", "0"))
DEVICE_REPUTATION_ENABLED = os.environ.get("NETCOIN_FAUCET_DEVICE_REPUTATION", "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
TRUST_PROXY_HEADERS = os.environ.get("NETCOIN_FAUCET_TRUST_PROXY_HEADERS", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NetCoin Testnet Faucet</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      max-width: 760px;
      margin: 48px auto;
      padding: 0 20px;
      color: #122034;
      background: #f7f9fc;
    }}
    main {{ background: white; border: 1px solid #d8e0ea; padding: 28px; border-radius: 8px; }}
    h1 {{ margin-top: 0; font-size: 28px; }}
    input {{ width: 100%; box-sizing: border-box; padding: 12px; font-size: 15px; border: 1px solid #b7c2d0; border-radius: 6px; }}
    button {{ margin-top: 14px; padding: 11px 18px; border: 0; border-radius: 6px; background: #164ea6; color: white; font-weight: 700; }}
    .msg {{ margin: 16px 0; padding: 12px; border-radius: 6px; background: #eef5ff; }}
    .err {{ background: #fff1f1; color: #8a1f1f; }}
    code {{ word-break: break-all; }}
    p {{ line-height: 1.5; }}
  </style>
</head>
<body>
  <main>
    <h1>NetCoin Testnet Faucet</h1>
    <p>Request {amount} test NET. Testnet coins have no real-money value.</p>
    {message}
    <form method="post" action="/faucet">
      <label for="address">NetCoin address</label>
      <input id="address" name="address" autocomplete="off" required placeholder="N... or net1...">
      {captcha}
      <button type="submit">Send test NET</button>
    </form>
  </main>
</body>
</html>
"""


def load_state() -> dict:
    try:
        state = json.loads(STATE_FILE.read_text())
    except FileNotFoundError:
        state = {}
    state.setdefault("requests", [])
    state.setdefault("queue", [])
    state.setdefault("abuse", [])
    state.setdefault("paused", False)
    state.setdefault("difficulty", POW_DIFFICULTY)
    state.setdefault("daily_cap_sats", DAILY_SPEND_CAP_SATS)
    state.setdefault("reputation", {})
    return state


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="state.", suffix=".json", dir=str(STATE_FILE.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    os.replace(tmp_name, STATE_FILE)


def client_ip(handler: BaseHTTPRequestHandler) -> str:
    return client_ip_from_headers(handler.headers, handler.client_address, trust_proxy_headers=TRUST_PROXY_HEADERS)


def request_content_length(handler: BaseHTTPRequestHandler) -> int:
    try:
        return int(handler.headers.get("Content-Length", "0"))
    except (TypeError, ValueError):
        return -1


def rate_limited(ip: str, state: dict) -> tuple[bool, int]:
    now = int(time.time())
    recent = []
    limited_until = 0
    for item in state.get("requests", []):
        ts = int(item.get("timestamp", 0))
        if now - ts < COOLDOWN_SECONDS:
            recent.append(item)
            if item.get("ip") == ip:
                limited_until = max(limited_until, ts + COOLDOWN_SECONDS)
    state["requests"] = recent
    for item in state.get("queue", []):
        if item.get("status") != "queued":
            continue
        ts = int(item.get("timestamp", 0))
        if now - ts < COOLDOWN_SECONDS and item.get("ip") == ip:
            limited_until = max(limited_until, ts + COOLDOWN_SECONDS)
    return limited_until > now, max(0, limited_until - now)


def address_rate_limited(address: str, state: dict) -> tuple[bool, int]:
    """Rate-limit repeated claims to the same address across IPs/devices."""
    if not address or ADDRESS_COOLDOWN_SECONDS <= 0:
        return False, 0
    now = int(time.time())
    limited_until = 0
    for item in state.get("requests", []):
        ts = int(item.get("timestamp", 0))
        if now - ts < ADDRESS_COOLDOWN_SECONDS and item.get("address") == address:
            limited_until = max(limited_until, ts + ADDRESS_COOLDOWN_SECONDS)
    for item in state.get("queue", []):
        if item.get("status") != "queued":
            continue
        ts = int(item.get("timestamp", 0))
        if now - ts < ADDRESS_COOLDOWN_SECONDS and item.get("address") == address:
            limited_until = max(limited_until, ts + ADDRESS_COOLDOWN_SECONDS)
    return limited_until > now, max(0, limited_until - now)


def api_key_quotas() -> dict[str, int]:
    """Programmatic faucet keys from env: ``NETCOIN_FAUCET_API_KEYS=key:quota,...``.

    The key string before ``:`` is the shared secret (operator-provided via env,
    never committed); the integer after ``:`` is the per-key claims-per-24h
    quota. Empty/unset means the programmatic API is disabled.
    """
    raw = os.environ.get("NETCOIN_FAUCET_API_KEYS", "").strip()
    quotas: dict[str, int] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, _, quota = part.partition(":")
        key = key.strip()
        try:
            quotas[key] = max(0, int(quota.strip()))
        except ValueError:
            continue
    return quotas


def authorize_api_claim(api_key: str, state: dict, now: int | None = None) -> tuple[bool, str, int]:
    """Validate a programmatic faucet key and enforce its rolling-24h quota.

    Returns (ok, reason, remaining). Quota usage is tracked per key in state so
    it holds across IPs/devices (a CI pipeline gets a predictable budget).
    """
    now = int(time.time()) if now is None else now
    quotas = api_key_quotas()
    key = str(api_key or "").strip()
    if not key:
        return False, "missing X-Faucet-Key", 0
    if key not in quotas:
        return False, "invalid faucet API key", 0
    window_start = now - 24 * 3600
    usage = state.setdefault("api_claims", {})
    stamps = [t for t in usage.get(key, []) if t >= window_start]
    limit = quotas[key]
    if len(stamps) >= limit:
        return False, "daily quota exhausted for this key", 0
    return True, "ok", limit - len(stamps)


def record_api_claim(api_key: str, state: dict, now: int | None = None) -> None:
    now = int(time.time()) if now is None else now
    window_start = now - 24 * 3600
    usage = state.setdefault("api_claims", {})
    stamps = [t for t in usage.get(str(api_key).strip(), []) if t >= window_start]
    stamps.append(now)
    usage[str(api_key).strip()] = stamps


def public_history(state: dict, limit: int = 50) -> list:
    """Recent faucet grants for a public JSON endpoint. Excludes client IPs."""
    grants = state.get("requests", []) or []
    recent = list(reversed(grants))[:limit]
    return [
        {"address": g.get("address"), "amount": g.get("amount"), "txid": g.get("txid"), "timestamp": g.get("timestamp")}
        for g in recent
    ]


def public_queue(state: dict, limit: int = 50) -> list:
    """Queued faucet grants for public JSON. Excludes client IPs."""
    queue = state.get("queue", []) or []
    recent = list(reversed(queue))[:limit]
    return [
        {
            "id": item.get("id"),
            "address": item.get("address"),
            "amount": item.get("amount"),
            "status": item.get("status"),
            "txid": item.get("txid"),
            "timestamp": item.get("timestamp"),
            "updated_at": item.get("updated_at"),
        }
        for item in recent
    ]


def body_too_large(length: int) -> bool:
    return length > MAX_BODY_BYTES


def burst_limited(state: dict, now: int | None = None) -> bool:
    """True if the faucet has served too many requests in the last 60 seconds.

    A global per-minute throttle protects the hot wallet and node from a rapid
    drain even when requests come from many different IPs (the hourly cooldown is
    per-IP and does not bound short bursts)."""
    now = int(time.time()) if now is None else now
    recent = [item for item in state.get("requests", []) if now - int(item.get("timestamp", 0)) < 60]
    return len(recent) >= MAX_REQUESTS_PER_MINUTE


def queue_full(state: dict) -> bool:
    pending = [item for item in state.get("queue", []) if item.get("status") == "queued"]
    return len(pending) >= MAX_QUEUE_ITEMS


def queue_grant(state: dict, ip: str, address: str, now: int | None = None) -> dict:
    now = int(time.time()) if now is None else now
    queue = state.setdefault("queue", [])
    grant = {
        "id": f"{now}-{len(queue) + 1}",
        "ip": ip,
        "address": address,
        "amount": AMOUNT,
        "status": "queued",
        "timestamp": now,
        "updated_at": now,
    }
    queue.append(grant)
    return grant


def mark_grant_sent(state: dict, grant: dict, sent: dict, now: int | None = None) -> None:
    now = int(time.time()) if now is None else now
    txid = sent.get("txid")
    grant.update({"status": "sent", "txid": txid, "updated_at": now})
    state.setdefault("requests", []).append(
        {
            "ip": grant.get("ip"),
            "address": grant.get("address"),
            "timestamp": now,
            "txid": txid,
            "amount": grant.get("amount", AMOUNT),
        }
    )


def mark_grant_failed(grant: dict, error: str, now: int | None = None) -> None:
    now = int(time.time()) if now is None else now
    grant.update({"status": "failed", "error": error[:500], "updated_at": now})


def process_queue(state: dict, limit: int = 1) -> dict:
    processed = 0
    sent_count = 0
    failed_count = 0
    errors = []
    for grant in state.get("queue", []):
        if processed >= limit:
            break
        if grant.get("status") != "queued":
            continue
        processed += 1
        if not sufficient_funds(faucet_spendable_sats(), AMOUNT, FEE):
            errors.append({"id": grant.get("id"), "error": "insufficient-funds"})
            break
        try:
            sent = send_faucet(str(grant.get("address", "")))
        except Exception as exc:
            failed_count += 1
            mark_grant_failed(grant, str(exc))
            errors.append({"id": grant.get("id"), "error": str(exc)})
            continue
        sent_count += 1
        mark_grant_sent(state, grant, sent)
    return {"processed": processed, "sent": sent_count, "failed": failed_count, "errors": errors}


def record_abuse(
    state: dict, ip: str, reason: str, now: int | None = None, address: str = "", device: str = ""
) -> None:
    """Append a rejected attempt to a capped in-state abuse log for later review."""
    record_abuse_event(state, ip=ip, address=address, device=device, reason=reason, now=now, max_log=MAX_ABUSE_LOG)


def sufficient_funds(spendable_sats: int | None, amount: str, fee: str) -> bool:
    """True if the faucet wallet can cover amount+fee. Unknown balance -> True
    (best-effort: never block legitimate users just because the balance query
    failed)."""
    if spendable_sats is None:
        return True
    try:
        return int(spendable_sats) >= amount_to_sats(amount) + amount_to_sats(fee)
    except (TypeError, ValueError):
        return True


def hot_wallet_status(spendable_sats: int | None) -> dict:
    if spendable_sats is None:
        state = "unknown"
    elif spendable_sats < MIN_SPENDABLE_SATS:
        state = "needs_refill"
    else:
        state = "ok"
    return {
        "state": state,
        "spendable_sats": spendable_sats,
        "min_spendable_sats": MIN_SPENDABLE_SATS,
        "refill_address": REFILL_ADDRESS,
    }


def faucet_spendable_sats() -> int | None:
    """Best-effort query of the faucet wallet's spendable balance, in sats.

    Returns None if the balance cannot be determined (so the caller does not
    block on a transient failure)."""
    try:
        result = subprocess.run(
            [PYTHON, "-m", "netcoin", "--data", DATA_DIR, "balance", "--wallet", WALLET],
            text=True,
            capture_output=True,
            timeout=20,
        )
        if result.returncode != 0:
            return None
        return int(json.loads(result.stdout)["spendable_sats"])
    except Exception:
        return None


def send_faucet(address: str) -> dict:
    command = [
        PYTHON,
        "-m",
        "netcoin",
        "--data",
        DATA_DIR,
        "send",
        "--wallet",
        WALLET,
        "--to",
        address,
        "--amount",
        AMOUNT,
        "--fee",
        FEE,
        "--broadcast-to",
        BROADCAST_TO,
    ]
    result = subprocess.run(command, cwd=str(NETCOIN_SOURCE_DIR), text=True, capture_output=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "faucet send failed")
    return json.loads(result.stdout)


def captcha_enabled() -> bool:
    return CAPTCHA_PROVIDER not in ("", "none", "off", "disabled")


def captcha_html() -> str:
    if not captcha_enabled():
        return ""
    if CAPTCHA_PROVIDER == "simple":
        return (
            f'<label for="captcha">{html.escape(CAPTCHA_SIMPLE_QUESTION)}</label>'
            '<input id="captcha" name="captcha" autocomplete="off" required>'
        )
    if CAPTCHA_PROVIDER == "turnstile" and CAPTCHA_SITEKEY:
        return (
            '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>'
            f'<div class="cf-turnstile" data-sitekey="{html.escape(CAPTCHA_SITEKEY)}"></div>'
        )
    if CAPTCHA_PROVIDER == "hcaptcha" and CAPTCHA_SITEKEY:
        return (
            '<script src="https://js.hcaptcha.com/1/api.js" async defer></script>'
            f'<div class="h-captcha" data-sitekey="{html.escape(CAPTCHA_SITEKEY)}"></div>'
        )
    return '<p class="err">CAPTCHA is configured but missing a site key.</p>'


def captcha_token_from_form(form: dict) -> str:
    """Return a CAPTCHA response token without binding callers to one provider."""
    fields = ("cf-turnstile-response", "h-captcha-response", "captcha_token", "captcha-response")
    for field in fields:
        token = (form.get(field, [""])[0] or "").strip()
        if token:
            return token
    return ""


def captcha_status_payload() -> dict:
    return {
        "enabled": captcha_enabled(),
        "provider": CAPTCHA_PROVIDER,
        "sitekey_present": bool(CAPTCHA_SITEKEY),
        "secret_configured": bool(CAPTCHA_SECRET),
        "supported_providers": ["turnstile", "hcaptcha", "simple"],
        "token_fields": ["cf-turnstile-response", "h-captcha-response", "captcha_token"],
    }


def verify_captcha(form: dict, remote_ip: str) -> tuple[bool, str]:
    """Validate CAPTCHA token through the configured provider adapter."""
    if not captcha_enabled():
        return True, "disabled"
    if CAPTCHA_PROVIDER == "simple":
        answer = (form.get("captcha", [""])[0] or "").strip().lower()
        return (answer == CAPTCHA_SIMPLE_ANSWER, "simple")

    token = captcha_token_from_form(form)
    config = CaptchaConfig(provider=CAPTCHA_PROVIDER, secret=CAPTCHA_SECRET, verify_url=CAPTCHA_VERIFY_URL)
    result = verify_token(token, remote_ip=remote_ip, config=config)
    if result.get("ok") is True:
        return True, CAPTCHA_PROVIDER
    return False, str(result.get("error") or CAPTCHA_PROVIDER)


def message_box(message: str, error: bool = False) -> str:
    cls = "msg err" if error else "msg"
    return f'<div class="{cls}">{message}</div>'


class FaucetHandler(BaseHTTPRequestHandler):
    server_version = "NetCoinFaucet/0.1"

    def log_message(self, format: str, *args) -> None:
        return

    def render(self, message: str = "") -> None:
        body = PAGE.format(amount=html.escape(AMOUNT), message=message, captcha=captcha_html()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def admin_allowed(self) -> bool:
        if not ADMIN_TOKEN:
            return False
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {ADMIN_TOKEN}"

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/history":
            self.write_json({"grants": public_history(load_state())})
            return
        if path == "/queue":
            self.write_json({"queue": public_queue(load_state())})
            return
        if path == "/challenge":
            challenge = issue_challenge(
                client_ip(self), secret=POW_SECRET, difficulty=POW_DIFFICULTY, ttl_seconds=POW_TTL_SECONDS
            )
            self.write_json({"ok": True, "enabled": POW_DIFFICULTY > 0, **challenge.to_dict()})
            return
        if path == "/admin/status":
            if not self.admin_allowed():
                self.write_json({"ok": False, "error": "unauthorized"}, status=401)
                return
            path = "/status"
        if path == "/status":
            state = load_state()
            queued = sum(1 for item in state.get("queue", []) if item.get("status") == "queued")
            spend = daily_spend_report(state, cap_sats=DAILY_SPEND_CAP_SATS, amount_sats=amount_to_sats(AMOUNT))
            self.write_json(
                {
                    "ok": True,
                    "queue_mode": QUEUE_MODE,
                    "captcha": captcha_status_payload(),
                    "proof_of_work": {
                        "enabled": POW_DIFFICULTY > 0,
                        "difficulty": POW_DIFFICULTY,
                        "ttl_seconds": POW_TTL_SECONDS,
                    },
                    "daily_cap": spend,
                    "abuse": abuse_summary(state),
                    "queued": queued,
                    "hot_wallet": hot_wallet_status(faucet_spendable_sats()),
                    "paused": bool(state.get("paused", False)),
                    "daily_spend_sats": spend.get("spent_sats", 0),
                    "daily_cap_sats": state.get("daily_cap_sats", DAILY_SPEND_CAP_SATS),
                    "challenge_bits": state.get("difficulty", POW_DIFFICULTY),
                    "reputation": state.get("reputation", {}),
                    "recent_requests": public_history(state, 100),
                    "blocked_requests": list(reversed(state.get("abuse", []) or []))[:100],
                }
            )
            return
        if path not in ("/", "/faucet"):
            self.send_error(404)
            return
        self.render()

    def do_POST(self) -> None:
        if self.path == "/admin/pause":
            if not self.admin_allowed():
                self.write_json({"ok": False, "error": "unauthorized"}, status=401)
                return
            state = load_state()
            state["paused"] = True
            save_state(state)
            self.write_json({"ok": True, "paused": True})
            return
        if self.path == "/admin/resume":
            if not self.admin_allowed():
                self.write_json({"ok": False, "error": "unauthorized"}, status=401)
                return
            state = load_state()
            state["paused"] = False
            save_state(state)
            self.write_json({"ok": True, "paused": False})
            return
        if self.path == "/admin/config":
            if not self.admin_allowed():
                self.write_json({"ok": False, "error": "unauthorized"}, status=401)
                return
            length = request_content_length(self)
            body = self.rfile.read(max(0, min(length, MAX_BODY_BYTES))).decode("utf-8", "replace")
            form = parse_qs(body)
            state = load_state()
            if form.get("difficulty", [""])[0]:
                state["difficulty"] = max(0, int(form.get("difficulty", ["0"])[0]))
            if form.get("daily_cap_sats", [""])[0]:
                state["daily_cap_sats"] = max(0, int(form.get("daily_cap_sats", ["0"])[0]))
            save_state(state)
            self.write_json(
                {"ok": True, "difficulty": state.get("difficulty"), "daily_cap_sats": state.get("daily_cap_sats")}
            )
            return
        if self.path == "/admin/process-queue":
            if not self.admin_allowed():
                self.write_json({"ok": False, "error": "unauthorized"}, status=401)
                return
            state = load_state()
            result = process_queue(state, limit=MAX_REQUESTS_PER_MINUTE)
            save_state(state)
            self.write_json({"ok": True, **result})
            return
        if self.path == "/api/claim":
            # Programmatic faucet: key-authorized JSON claim for CI/dev pipelines.
            # Bypasses CAPTCHA and IP cooldown but is bounded by the key's quota.
            length = request_content_length(self)
            body = self.rfile.read(max(0, min(length, MAX_BODY_BYTES))).decode("utf-8", "replace")
            try:
                payload = json.loads(body) if body.strip() else {}
            except json.JSONDecodeError:
                self.write_json({"ok": False, "error": "invalid JSON body"}, status=400)
                return
            address = str(payload.get("address", "")).strip()
            if not address:
                self.write_json({"ok": False, "error": "address required"}, status=400)
                return
            api_key = self.headers.get("X-Faucet-Key", "")
            state = load_state()
            if state.get("paused"):
                self.write_json({"ok": False, "error": "faucet paused"}, status=503)
                return
            ok, reason, remaining = authorize_api_claim(api_key, state)
            if not ok:
                self.write_json({"ok": False, "error": reason}, status=401 if "key" in reason else 429)
                return
            grant = queue_grant(state, client_ip(self), address)
            record_api_claim(api_key, state, grant["timestamp"])
            save_state(state)
            self.write_json({"ok": True, "grant": grant, "quota_remaining": remaining - 1})
            return
        if self.path != "/faucet":
            self.send_error(404)
            return
        length = request_content_length(self)
        if length < 0:
            self.render(message_box("Bad request.", error=True))
            return
        ip = client_ip(self)
        if body_too_large(length):
            state = load_state()
            record_abuse(state, ip, "body-too-large")
            save_state(state)
            self.render(message_box("Request too large.", error=True))
            return
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        address = form.get("address", [""])[0].strip()
        device = (
            form.get("device", [self.headers.get("User-Agent", "")[:80]])[0].strip()
            if DEVICE_REPUTATION_ENABLED
            else ""
        )
        state = load_state()
        if not validate_address(address):
            record_abuse(state, ip, "invalid-address", address=address, device=device)
            save_state(state)
            self.render(message_box("Invalid NetCoin address.", error=True))
            return
        rep = reputation_score(state, ip=ip, address=address, device=device)
        if rep["risk"] == "block":
            record_abuse(state, ip, "reputation-block", address=address, device=device)
            save_state(state)
            self.render(
                message_box("Faucet risk controls blocked this request. Try later or contact an operator.", error=True)
            )
            return
        spend = daily_spend_report(state, cap_sats=DAILY_SPEND_CAP_SATS, amount_sats=amount_to_sats(AMOUNT))
        if spend["would_exceed"]:
            record_abuse(state, ip, "daily-cap", address=address, device=device)
            save_state(state)
            self.render(message_box("Faucet daily spend cap reached. Try again tomorrow.", error=True))
            return
        if POW_DIFFICULTY > 0 or rep["risk"] == "challenge":
            challenge = form.get("pow_challenge", [""])[0]
            nonce = form.get("pow_nonce", [""])[0]
            expected = issue_challenge(ip, secret=POW_SECRET, difficulty=POW_DIFFICULTY, ttl_seconds=POW_TTL_SECONDS)
            difficulty = POW_DIFFICULTY or 3
            if challenge != expected.challenge or not verify_pow(challenge, nonce, difficulty=difficulty):
                record_abuse(state, ip, "pow-failed", address=address, device=device)
                save_state(state)
                self.render(message_box("Proof-of-work challenge failed. Refresh and try again.", error=True))
                return
        captcha_ok, captcha_reason = verify_captcha(form, ip)
        if not captcha_ok:
            record_abuse(state, ip, f"captcha:{captcha_reason}", address=address, device=device)
            save_state(state)
            self.render(message_box("CAPTCHA verification failed. Please try again.", error=True))
            return
        limited, remaining = rate_limited(ip, state)
        if limited:
            record_abuse(state, ip, "rate-limited", address=address, device=device)
            save_state(state)
            hours = max(1, (remaining + 3599) // 3600)
            self.render(message_box(f"Rate limit active. Try again in about {hours} hour(s).", error=True))
            return
        address_limited, address_remaining = address_rate_limited(address, state)
        if address_limited:
            record_abuse(state, ip, "address-rate-limited", address=address, device=device)
            save_state(state)
            hours = max(1, (address_remaining + 3599) // 3600)
            self.render(
                message_box(f"This address already claimed recently. Try again in about {hours} hour(s).", error=True)
            )
            return
        if burst_limited(state):
            record_abuse(state, ip, "burst", address=address, device=device)
            save_state(state)
            self.render(message_box("Faucet is busy. Please wait a minute and try again.", error=True))
            return
        if queue_full(state):
            record_abuse(state, ip, "queue-full", address=address, device=device)
            save_state(state)
            self.render(message_box("Faucet queue is full. Please try again later.", error=True))
            return
        if not sufficient_funds(faucet_spendable_sats(), AMOUNT, FEE):
            self.render(message_box("Faucet is temporarily empty. Please try again later.", error=True))
            return
        grant = queue_grant(state, ip, address)
        if QUEUE_MODE == "sync":
            result = process_queue(state, limit=1)
            if result["failed"]:
                save_state(state)
                error = result["errors"][0]["error"] if result["errors"] else "faucet send failed"
                self.render(message_box(html.escape(error), error=True))
                return
            if result["sent"] < 1:
                save_state(state)
                self.render(message_box("Faucet is temporarily empty. Please try again later.", error=True))
                return
            txid = html.escape(str(grant.get("txid", "")))
            save_state(state)
            self.render(message_box(f"Sent {html.escape(AMOUNT)} test NET. Txid: <code>{txid}</code>"))
            return
        save_state(state)
        grant_id = html.escape(str(grant.get("id", "")))
        self.render(message_box(f"Request queued. Grant id: <code>{grant_id}</code>"))


def main() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), FaucetHandler)
    print(f"NetCoin faucet listening on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
