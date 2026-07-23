#!/usr/bin/env python3
"""Render a public NetCoin testnet status dashboard from monitor status.json.

The monitor (tools/monitor_netcoin.py) writes a status.json with this shape:

    {
      "ok": true,
      "generated_at": 1718900000,            # optional
      "seed_heights": {"seed1": 105, ...},
      "seed_tips_match": true,
      "targets": {
        "seed1": {"ok": true, "url": "...", "height": 105, "tip_hash": "..."},
        "explorer": {"ok": true, "url": "..."},
        "faucet": {"ok": true, "url": "..."}
      }
    }

This module turns that into a single static HTML page (no server needed) that can
be served next to the explorer. `render_dashboard` is pure and unit-tested.

Usage:
    python tools/dashboard.py status.json status.html
"""

from __future__ import annotations

import html
import json
import sys
import time
from typing import Any


def _esc(value: object) -> str:
    return html.escape(str(value))


def _badge(ok: bool) -> str:
    color = "#1a7f37" if ok else "#cf222e"
    label = "UP" if ok else "DOWN"
    return f"<span style='background:{color};color:#fff;padding:2px 8px;border-radius:10px;font-size:0.8rem'>{label}</span>"


def render_dashboard(status: dict[str, Any]) -> str:
    """Return a complete HTML page string for the given status dict."""
    overall_ok = bool(status.get("ok"))
    targets = status.get("targets", {}) or {}
    generated = status.get("generated_at")
    when = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(generated)) if generated else "unknown"

    rows = []
    for name in sorted(targets):
        item = targets.get(name, {}) or {}
        ok = bool(item.get("ok"))
        height = item.get("height")
        tip = item.get("tip_hash")
        url = item.get("url", "")
        rows.append(
            "<tr>"
            f"<td>{_esc(name)}</td>"
            f"<td>{_badge(ok)}</td>"
            f"<td>{_esc(height) if height is not None else '&mdash;'}</td>"
            f"<td class='hash'>{_esc(tip) if tip else '&mdash;'}</td>"
            f"<td>{('<a href=' + chr(34) + _esc(url) + chr(34) + '>link</a>') if url else '&mdash;'}</td>"
            "</tr>"
        )

    seed_heights = status.get("seed_heights", {}) or {}
    tips_match = status.get("seed_tips_match")
    summary = (
        f"<p>Overall: {_badge(overall_ok)} &nbsp;|&nbsp; "
        f"Seed tips match: {_badge(bool(tips_match))} &nbsp;|&nbsp; "
        f"Heights: {_esc(seed_heights) if seed_heights else '&mdash;'}</p>"
        f"<p>Last checked: {_esc(when)}</p>"
    )

    body = (
        "<h1>NetCoin Testnet Status</h1>"
        f"{summary}"
        "<table><tr><th>service</th><th>status</th><th>height</th><th>tip hash</th><th>url</th></tr>"
        f"{''.join(rows)}</table>"
        "<p style='color:#57606a;font-size:0.85rem'>Educational testnet. NET has no real-money value. "
        "Auto-generated from monitor status.json.</p>"
    )

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta http-equiv='refresh' content='120'>"
        "<title>NetCoin Testnet Status</title><style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:2rem;line-height:1.45}"
        "table{border-collapse:collapse;width:100%;margin:1rem 0}"
        "th,td{border:1px solid #ddd;padding:.45rem;text-align:left}"
        "th{background:#f7f7f7}.hash{font-family:ui-monospace,Menlo,monospace;word-break:break-all}"
        "</style></head><body>" + body + "</body></html>"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python tools/dashboard.py <status.json> <out.html>", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        status = json.loads(f.read())
    with open(argv[2], "w", encoding="utf-8") as f:
        f.write(render_dashboard(status))
    print(f"wrote {argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
