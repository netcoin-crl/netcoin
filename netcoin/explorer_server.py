"""Small API-backed explorer service for NetCoin.

The static explorer remains useful for simple hosting. This server gives node
operators a live explorer UI/API backed directly by local chain data without
requiring a separate database.
"""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .chain import Blockchain
from .node import RateLimiter, client_ip_from_headers


def esc(value: object) -> str:
    return html.escape(str(value))


def page(title: str, body: str) -> bytes:
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 2rem; line-height: 1.45; }}
    code, .hash {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; word-break: break-all; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ddd; padding: .45rem; text-align: left; vertical-align: top; }}
    th {{ background: #f7f7f7; }}
    input {{ width: min(100%, 650px); padding: .55rem; }}
  </style>
</head>
<body>
{body}
</body>
</html>"""
    return html_text.encode("utf-8")


def block_summary(block: Any) -> dict[str, Any]:
    return {
        "height": block.header.height,
        "hash": block.hash(),
        "previous_hash": block.header.previous_hash,
        "timestamp": block.header.timestamp,
        "transactions": len(block.transactions),
        "weight": block.weight(),
    }


def transaction_payload(chain: Blockchain, txid: str) -> dict[str, Any] | None:
    found = chain.get_transaction(txid)
    if found is None:
        return None
    tx, block = found
    return {
        "txid": tx.txid(),
        "wtxid": tx.wtxid(),
        "confirmed": block is not None,
        "block_hash": block.hash() if block else None,
        "block_height": block.header.height if block else None,
        "tx": tx.to_dict(include_scripts=True, include_witness=True),
    }


def latest_payload(chain: Blockchain, limit: int = 20, page: int = 1) -> dict[str, Any]:
    limit = max(1, min(int(limit), 100))
    page = max(1, int(page))
    ordered = list(reversed(chain.chain))
    total = len(ordered)
    offset = (page - 1) * limit
    page_blocks = ordered[offset : offset + limit]
    return {
        "height": chain.height(),
        "tip_hash": chain.tip_hash(),
        "page": page,
        "limit": limit,
        "total_blocks": total,
        "has_next": offset + limit < total,
        "blocks": [block_summary(block) for block in page_blocks],
        "mempool": chain.mempool_info(),
    }


def address_payload(chain: Blockchain, address: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    summary = chain.address_summary(address)
    txids = summary.get("transaction_ids", [])
    summary["all_transaction_count"] = len(txids)
    summary["limit"] = limit
    summary["offset"] = offset
    summary["has_next"] = offset + limit < len(txids)
    summary["transaction_ids"] = txids[offset : offset + limit]
    return summary


def search_payload(chain: Blockchain, query: str) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"query": q, "matches": []}
    matches: list[dict[str, Any]] = []
    if q.isdigit():
        height = int(q)
        if 0 <= height <= chain.height():
            block = chain.chain[height]
            matches.append({"type": "block", "height": height, "hash": block.hash()})
    block = chain.get_block_by_hash(q.lower())
    if block is not None:
        matches.append({"type": "block", "height": block.header.height, "hash": block.hash()})
    found = chain.get_transaction(q.lower())
    if found is not None:
        tx, block = found
        matches.append(
            {
                "type": "tx",
                "txid": tx.txid(),
                "confirmed": block is not None,
                "block_height": block.header.height if block else None,
            }
        )
    try:
        summary = chain.address_summary(q)
        matches.append({"type": "address", "address": q, "summary": summary})
    except Exception:
        pass
    return {"query": q, "matches": matches}


def make_handler(chain: Blockchain, rate_limit_per_min: int = 240, *, trust_proxy_headers: bool = False):
    rate_limiter = RateLimiter(max_requests=rate_limit_per_min, window_seconds=60)

    class ExplorerHandler(BaseHTTPRequestHandler):
        server_version = "NetCoinExplorer/0.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_html(self, title: str, body: str, status: int = 200) -> None:
            data = page(title, body)
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def client_ip(self) -> str:
            return client_ip_from_headers(self.headers, self.client_address, trust_proxy_headers=trust_proxy_headers)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if not rate_limiter.allow((self.client_ip(), parsed.path)):
                self.send_json({"ok": False, "error": "rate limit exceeded"}, status=429)
                return
            try:
                if parsed.path in ("/api/latest", "/api/blocks"):
                    query = parse_qs(parsed.query)
                    n = int(query.get("n", query.get("limit", [20]))[0])
                    page_num = int(query.get("page", [1])[0])
                    self.send_json(latest_payload(chain, n, page=page_num))
                elif parsed.path.startswith("/api/block/"):
                    block_hash = parsed.path.split("/", 3)[3]
                    block = chain.get_block_by_hash(block_hash)
                    if block is None:
                        self.send_json({"ok": False, "error": "block not found"}, status=404)
                    else:
                        self.send_json(block.to_dict() | block_summary(block))
                elif parsed.path.startswith("/api/tx/"):
                    txid = parsed.path.split("/", 3)[3]
                    payload = transaction_payload(chain, txid)
                    if payload is None:
                        self.send_json({"ok": False, "error": "transaction not found"}, status=404)
                    else:
                        self.send_json(payload)
                elif parsed.path.startswith("/api/address/"):
                    address = parsed.path.split("/", 3)[3]
                    query = parse_qs(parsed.query)
                    limit = int(query.get("limit", [50])[0])
                    offset = int(query.get("offset", [0])[0])
                    self.send_json(address_payload(chain, address, limit=limit, offset=offset))
                elif parsed.path == "/api/search":
                    q = parse_qs(parsed.query).get("q", [""])[0]
                    self.send_json(search_payload(chain, q))
                elif parsed.path == "/":
                    payload = latest_payload(chain, 20)
                    rows = "".join(
                        f"<tr><td>{b['height']}</td><td class='hash'><a href='/block/{b['hash']}'>{b['hash']}</a></td><td>{b['transactions']}</td><td>{b['timestamp']}</td></tr>"
                        for b in payload["blocks"]
                    )
                    self.send_html(
                        "NetCoin Explorer",
                        f"""
<h1>NetCoin Explorer</h1>
<p>Height: <strong>{payload['height']}</strong> | Tip: <code>{esc(payload['tip_hash'])}</code></p>
<form action="/search" method="get"><input name="q" placeholder="height, block hash, txid, or address"></form>
<table><tr><th>height</th><th>hash</th><th>txs</th><th>timestamp</th></tr>{rows}</table>
""",
                    )
                elif parsed.path == "/search":
                    q = parse_qs(parsed.query).get("q", [""])[0]
                    data = search_payload(chain, q)
                    items = []
                    for match in data["matches"]:
                        if match["type"] == "block":
                            items.append(f"<li>Block <a href='/block/{match['hash']}'>{match['height']}</a></li>")
                        elif match["type"] == "tx":
                            items.append(f"<li>Transaction <a href='/tx/{match['txid']}'>{esc(match['txid'])}</a></li>")
                        elif match["type"] == "address":
                            items.append(f"<li>Address <a href='/address/{match['address']}'>{esc(match['address'])}</a></li>")
                    self.send_html("Search", f"<h1>Search</h1><p><a href='/'>Home</a></p><ul>{''.join(items) or '<li>No matches</li>'}</ul>")
                elif parsed.path.startswith("/block/"):
                    block_hash = parsed.path.split("/", 2)[2]
                    block = chain.get_block_by_hash(block_hash)
                    if block is None:
                        self.send_html("Not found", "<h1>Block not found</h1>", status=404)
                    else:
                        rows = "".join(f"<li><a href='/tx/{tx.txid()}'>{tx.txid()}</a></li>" for tx in block.transactions)
                        self.send_html("Block", f"<h1>Block {block.header.height}</h1><p><a href='/'>Home</a></p><p class='hash'>{block.hash()}</p><ul>{rows}</ul>")
                elif parsed.path.startswith("/tx/"):
                    txid = parsed.path.split("/", 2)[2]
                    payload = transaction_payload(chain, txid)
                    if payload is None:
                        self.send_html("Not found", "<h1>Transaction not found</h1>", status=404)
                    else:
                        outputs = "".join(
                            f"<li>{esc(out.get('address', ''))}: {esc(out.get('amount', ''))} sats</li>"
                            for out in payload["tx"].get("outputs", [])
                        )
                        self.send_html("Transaction", f"<h1>Transaction</h1><p><a href='/'>Home</a></p><p class='hash'>{esc(txid)}</p><ul>{outputs}</ul>")
                elif parsed.path.startswith("/address/"):
                    address = parsed.path.split("/", 2)[2]
                    summary = chain.address_summary(address)
                    txs = "".join(f"<li><a href='/tx/{txid}'>{txid}</a></li>" for txid in summary["transaction_ids"])
                    balance = summary["balance_net"]
                    self.send_html(
                        "Address",
                        f"<h1>Address</h1><p><a href='/'>Home</a></p><p class='hash'>{esc(address)}</p><p>Total {balance['total']} NET, spendable {balance['spendable']} NET, immature {balance['immature']} NET</p><ul>{txs}</ul>",
                    )
                else:
                    self.send_json({"ok": False, "error": "not found"}, status=404)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)

    return ExplorerHandler


def run_explorer_server(
    data_dir: str,
    host: str = "127.0.0.1",
    port: int = 8080,
    rate_limit_per_min: int = 240,
    trust_proxy_headers: bool = False,
) -> None:
    chain = Blockchain(data_dir=data_dir)
    server = ThreadingHTTPServer(
        (host, int(port)),
        make_handler(chain, rate_limit_per_min=rate_limit_per_min, trust_proxy_headers=trust_proxy_headers),
    )
    print(f"NetCoin explorer listening on http://{host}:{port}")
    print(f"height={chain.height()} tip={chain.tip_hash()}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
