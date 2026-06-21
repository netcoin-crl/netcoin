#!/usr/bin/env python3
"""Small stdlib-only NetCoin testnet faucet.

This is intentionally simple infrastructure glue. It validates a submitted
NetCoin address, rate-limits by client IP, sends a small testnet amount from a
hot wallet, and broadcasts the transaction to a seed node.
"""

from __future__ import annotations

import html
import json
import os
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from netcoin.crypto import validate_address
from netcoin.tx import amount_to_sats


HOST = os.environ.get("NETCOIN_FAUCET_HOST", "127.0.0.1")
PORT = int(os.environ.get("NETCOIN_FAUCET_PORT", "8081"))
PYTHON = os.environ.get("NETCOIN_PYTHON", "/opt/netcoin/netcoin-v2/.venv/bin/python")
DATA_DIR = os.environ.get("NETCOIN_DATA_DIR", "/opt/netcoin/.netcoin-testnet")
WALLET = os.environ.get("NETCOIN_FAUCET_WALLET", "/opt/netcoin/wallets/testnet-miner.json")
BROADCAST_TO = os.environ.get("NETCOIN_BROADCAST_TO", "http://127.0.0.1:28444")
STATE_FILE = Path(os.environ.get("NETCOIN_FAUCET_STATE", "/opt/netcoin/faucet/state.json"))
AMOUNT = os.environ.get("NETCOIN_FAUCET_AMOUNT", "5")
FEE = os.environ.get("NETCOIN_FAUCET_FEE", "0.01")
COOLDOWN_SECONDS = int(os.environ.get("NETCOIN_FAUCET_COOLDOWN_SECONDS", str(24 * 60 * 60)))
# Hardening knobs.
MAX_BODY_BYTES = int(os.environ.get("NETCOIN_FAUCET_MAX_BODY", "4096"))
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("NETCOIN_FAUCET_MAX_PER_MINUTE", "5"))
MAX_ABUSE_LOG = int(os.environ.get("NETCOIN_FAUCET_MAX_ABUSE_LOG", "200"))


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
      <button type="submit">Send test NET</button>
    </form>
  </main>
</body>
</html>
"""


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except FileNotFoundError:
        return {"requests": []}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="state.", suffix=".json", dir=str(STATE_FILE.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    os.replace(tmp_name, STATE_FILE)


def client_ip(handler: BaseHTTPRequestHandler) -> str:
    forwarded = handler.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    host, _port = handler.client_address
    return host


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
    return limited_until > now, max(0, limited_until - now)


def body_too_large(length: int) -> bool:
    return length > MAX_BODY_BYTES


def burst_limited(state: dict, now: int | None = None) -> bool:
    """True if the faucet has served too many requests in the last 60 seconds.

    A global per-minute throttle protects the hot wallet and node from a rapid
    drain even when requests come from many different IPs (the 24h cooldown is
    per-IP and does not bound short bursts)."""
    now = int(time.time()) if now is None else now
    recent = [item for item in state.get("requests", []) if now - int(item.get("timestamp", 0)) < 60]
    return len(recent) >= MAX_REQUESTS_PER_MINUTE


def record_abuse(state: dict, ip: str, reason: str, now: int | None = None) -> None:
    """Append a rejected attempt to a capped in-state abuse log for later review."""
    now = int(time.time()) if now is None else now
    log = state.setdefault("abuse", [])
    log.append({"ip": ip, "reason": reason, "timestamp": now})
    if len(log) > MAX_ABUSE_LOG:
        del log[: len(log) - MAX_ABUSE_LOG]


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
    result = subprocess.run(command, cwd="/opt/netcoin/netcoin-v2", text=True, capture_output=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "faucet send failed")
    return json.loads(result.stdout)


def message_box(message: str, error: bool = False) -> str:
    cls = "msg err" if error else "msg"
    return f'<div class="{cls}">{message}</div>'


class FaucetHandler(BaseHTTPRequestHandler):
    server_version = "NetCoinFaucet/0.1"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def render(self, message: str = "") -> None:
        body = PAGE.format(amount=html.escape(AMOUNT), message=message).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in ("/", "/faucet"):
            self.send_error(404)
            return
        self.render()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/faucet":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        ip = client_ip(self)
        if body_too_large(length):
            state = load_state()
            record_abuse(state, ip, "body-too-large")
            save_state(state)
            self.render(message_box("Request too large.", error=True))
            return
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        address = form.get("address", [""])[0].strip()
        state = load_state()
        if not validate_address(address):
            record_abuse(state, ip, "invalid-address")
            save_state(state)
            self.render(message_box("Invalid NetCoin address.", error=True))
            return
        limited, remaining = rate_limited(ip, state)
        if limited:
            record_abuse(state, ip, "rate-limited")
            save_state(state)
            hours = max(1, (remaining + 3599) // 3600)
            self.render(message_box(f"Rate limit active. Try again in about {hours} hour(s).", error=True))
            return
        if burst_limited(state):
            record_abuse(state, ip, "burst")
            save_state(state)
            self.render(message_box("Faucet is busy. Please wait a minute and try again.", error=True))
            return
        if not sufficient_funds(faucet_spendable_sats(), AMOUNT, FEE):
            self.render(message_box("Faucet is temporarily empty. Please try again later.", error=True))
            return
        try:
            sent = send_faucet(address)
        except Exception as exc:
            self.render(message_box(html.escape(str(exc)), error=True))
            return
        state.setdefault("requests", []).append(
            {
                "ip": ip,
                "address": address,
                "timestamp": int(time.time()),
                "txid": sent.get("txid"),
                "amount": AMOUNT,
            }
        )
        save_state(state)
        txid = html.escape(str(sent.get("txid", "")))
        self.render(message_box(f"Sent {html.escape(AMOUNT)} test NET. Txid: <code>{txid}</code>"))


def main() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), FaucetHandler)
    print(f"NetCoin faucet listening on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
