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
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        address = form.get("address", [""])[0].strip()
        ip = client_ip(self)
        if not validate_address(address):
            self.render(message_box("Invalid NetCoin address.", error=True))
            return
        state = load_state()
        limited, remaining = rate_limited(ip, state)
        if limited:
            hours = max(1, (remaining + 3599) // 3600)
            self.render(message_box(f"Rate limit active. Try again in about {hours} hour(s).", error=True))
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
