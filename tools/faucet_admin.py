#!/usr/bin/env python3
"""Render a private faucet admin dashboard from the faucet state.json.

The faucet (tools/faucet_server.py) records granted requests under "requests"
and rejected attempts under "abuse". This builds a single static HTML page that
shows the hot-wallet balance, recent sent transactions, and the abuse log. It is
admin-only output: serve it behind auth, never publicly.

Usage:
    python tools/faucet_admin.py state.json admin.html [spendable_sats]
"""

from __future__ import annotations

import html
import json
import sys
import time
from typing import Any


def _esc(value: object) -> str:
    return html.escape(str(value))


def _when(ts: object) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(int(ts)))
    except (TypeError, ValueError):
        return "—"


def _rows(items, columns) -> str:
    rows = []
    for item in items:
        cells = "".join(
            f"<td>{_esc(item.get(c, ''))}</td>" if c != "timestamp" else f"<td>{_esc(_when(item.get(c)))}</td>"
            for c in columns
        )
        rows.append(f"<tr>{cells}</tr>")
    return "".join(rows)


def render_faucet_admin(state: dict[str, Any], spendable_sats: int | None = None) -> str:
    requests = list(reversed(state.get("requests", []) or []))
    abuse = list(reversed(state.get("abuse", []) or []))
    now = int(time.time())

    def _recent(record) -> bool:
        try:
            return now - int(record.get("timestamp", 0)) < 24 * 60 * 60
        except (TypeError, ValueError):
            return False

    last_24h = sum(1 for r in (state.get("requests", []) or []) if _recent(r))

    balance = "unknown" if spendable_sats is None else f"{int(spendable_sats) / 100_000_000:.8f} NET"
    summary = (
        f"<p>Hot-wallet spendable: <strong>{_esc(balance)}</strong></p>"
        f"<p>Granted requests: {_esc(len(state.get('requests', []) or []))} total, "
        f"{_esc(last_24h)} in the last 24h &nbsp;|&nbsp; Abuse entries: {_esc(len(abuse))}</p>"
    )

    requests_table = (
        "<h2>Recent granted requests</h2>"
        "<table><tr><th>time</th><th>ip</th><th>address</th><th>amount</th><th>txid</th></tr>"
        + _rows(requests[:200], ["timestamp", "ip", "address", "amount", "txid"])
        + "</table>"
    )
    abuse_table = (
        "<h2>Abuse log (rejected attempts)</h2>"
        "<table><tr><th>time</th><th>ip</th><th>reason</th></tr>"
        + _rows(abuse[:200], ["timestamp", "ip", "reason"])
        + "</table>"
    )

    body = (
        "<h1>NetCoin Faucet Admin</h1>"
        + summary
        + requests_table
        + abuse_table
        + (
            "<p style='color:#8a1f1f;font-size:.85rem'>Admin only. Contains client IPs. Serve behind authentication.</p>"
        )
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>NetCoin Faucet Admin</title><style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:2rem;line-height:1.45}"
        "table{border-collapse:collapse;width:100%;margin:1rem 0}"
        "th,td{border:1px solid #ddd;padding:.4rem;text-align:left;font-size:.9rem}"
        "th{background:#f7f7f7}</style></head><body>" + body + "</body></html>"
    )


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print("usage: python tools/faucet_admin.py <state.json> <out.html> [spendable_sats]", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        state = json.loads(f.read())
    spendable = int(argv[3]) if len(argv) == 4 else None
    with open(argv[2], "w", encoding="utf-8") as f:
        f.write(render_faucet_admin(state, spendable))
    print(f"wrote {argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
