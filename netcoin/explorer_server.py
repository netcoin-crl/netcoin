"""Small API-backed explorer service for NetCoin.

The static explorer remains useful for simple hosting. This server gives node
operators a live explorer UI/API backed directly by local chain data without
requiring a separate database.
"""

from __future__ import annotations

import hmac
import html
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .apps import AppError, AppStore, route_app_get, route_app_post
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
    block_height = block.header.height if block else None
    return {
        "txid": tx.txid(),
        "wtxid": tx.wtxid(),
        "confirmed": block is not None,
        "mempool": block is None,
        "block_hash": block.hash() if block else None,
        "block_height": block_height,
        "confirmations": max(0, chain.height() - block_height + 1) if block_height is not None else 0,
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


def latest_transactions_payload(chain: Blockchain, limit: int = 20) -> dict[str, Any]:
    """Newest confirmed transactions plus current mempool entries for explorer feeds."""
    limit = max(1, min(int(limit), 100))
    confirmed: list[dict[str, Any]] = []
    for block in reversed(chain.chain):
        for position, tx in reversed(list(enumerate(block.transactions))):
            confirmed.append(
                {
                    "txid": tx.txid(),
                    "wtxid": tx.wtxid(),
                    "confirmed": True,
                    "block_hash": block.hash(),
                    "block_height": block.header.height,
                    "position": position,
                    "outputs": len(tx.outputs),
                    "total_output_sats": tx.total_output(),
                    "timestamp": block.header.timestamp,
                }
            )
            if len(confirmed) >= limit:
                break
        if len(confirmed) >= limit:
            break
    mempool = [
        {
            "txid": tx.txid(),
            "wtxid": tx.wtxid(),
            "confirmed": False,
            "outputs": len(tx.outputs),
            "total_output_sats": tx.total_output(),
            "timestamp": int(chain.mempool_times.get(tx.txid(), time.time())),
        }
        for tx in reversed(chain.mempool[-limit:])
    ]
    return {"confirmed": confirmed, "mempool": mempool, "limit": limit}


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


def percentile_fee_rate(values: list[int], percentile: int) -> int:
    """Return a nearest-rank fee-rate percentile from sorted or unsorted values."""
    if not values:
        return 0
    ordered = sorted(max(0, int(value)) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    idx = round((max(0, min(100, int(percentile))) / 100) * (len(ordered) - 1))
    return ordered[idx]


def fee_estimates_payload(chain: Blockchain, assumed_vbytes: int = 200) -> dict[str, Any]:
    presets = {
        "slow": 6,
        "normal": 3,
        "fast": 1,
    }
    assumed_vbytes = int(assumed_vbytes)
    mempool = chain.mempool_info()
    min_relay = int(mempool.get("min_relay_fee_per_kvb", 0))
    observed_rates = [
        int(entry.get("fee_rate_per_kvb", 0))
        for entry in mempool.get("entries", [])
        if int(entry.get("fee_rate_per_kvb", 0)) > 0
    ]
    percentile_source = "mempool-fee-rates" if observed_rates else "min-relay-fallback"
    percentile_rates = observed_rates or [min_relay]
    result: dict[str, Any] = {
        "assumed_vbytes": assumed_vbytes,
        "mempool_depth": int(mempool.get("size", 0)),
        "mempool_bytes": int(mempool.get("bytes", 0)),
        "source": percentile_source,
        "fee_rate_percentiles": {},
        "presets": {},
    }
    for key, pct in (("p10", 10), ("p50", 50), ("p90", 90)):
        rate = percentile_fee_rate(percentile_rates, pct)
        result["fee_rate_percentiles"][key] = {
            "label": f"{pct}th percentile",
            "percentile": pct,
            "fee_rate_per_kvb": rate,
            "estimated_fee_sats": max(1, (rate * assumed_vbytes + 999) // 1000),
        }
    for name, target in presets.items():
        estimate = chain.estimate_smart_fee(target)
        rate = int(estimate.get("fee_rate_per_kvb", 0))
        result["presets"][name] = {
            "target_blocks": target,
            "fee_rate_per_kvb": rate,
            "estimated_fee_sats": max(1, (rate * assumed_vbytes + 999) // 1000),
            "method": estimate.get("method", "local-policy"),
        }
    return result


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


def events_payload(chain: Blockchain, limit: int = 50) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    orphan_events = [
        {
            "event": "orphan_candidate",
            "hash": block.hash(),
            "height": block.header.height,
            "previous_hash": block.header.previous_hash,
            "timestamp": block.header.timestamp,
        }
        for block in chain.orphan_blocks.values()
    ]
    return {
        "events": sorted(orphan_events, key=lambda item: int(item.get("timestamp", 0)), reverse=True)[:limit],
        "orphan_candidates": len(chain.orphan_blocks),
        "source": "explorer-server-chain-state",
    }


def make_handler(chain: Blockchain, rate_limit_per_min: int = 240, *, trust_proxy_headers: bool = False):
    app_store = AppStore(chain.data_dir)
    rate_limiter = RateLimiter(max_requests=rate_limit_per_min, window_seconds=60)

    class ExplorerHandler(BaseHTTPRequestHandler):
        server_version = "NetCoinExplorer/0.1"

        def admin_required(self, path: str, method: str) -> bool:
            public_post = path in {"/api/community/posts", "/community/posts", "/app/community/posts"}
            if public_post:
                return False
            if os.environ.get("NETCOIN_APP_REQUIRE_ADMIN", "0") != "1":
                return False
            # Public read pages stay open; app-layer writes and sensitive operator reads require a token.
            sensitive_get = ("/api/admin", "/api/merchant", "/api/wallet", "/api/custody", "/api/security")
            if method.upper() == "GET":
                return path.startswith(sensitive_get)
            return path.startswith(("/api/", "/app/"))

        def require_admin(self, path: str, method: str) -> bool:
            if not self.admin_required(path, method):
                return True
            expected = os.environ.get("NETCOIN_APP_ADMIN_TOKEN", "")
            provided = self.headers.get("X-Netcoin-Admin-Token", "") or self.headers.get("Authorization", "").replace(
                "Bearer ", "", 1
            )
            if expected and hmac.compare_digest(expected, provided):
                return True
            self.send_json({"ok": False, "error": "admin token required"}, status=401)
            return False

        def api_key_from_headers(self) -> str:
            return self.headers.get("X-Netcoin-Api-Key", "") or self.headers.get("X-API-Key", "")

        def log_message(self, format: str, *args: Any) -> None:
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

        def send_text(
            self, text: str | bytes, status: int = 200, content_type: str = "text/plain; charset=utf-8"
        ) -> None:
            data = text if isinstance(text, bytes) else text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def send_event_stream(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            last = None
            for _ in range(30):
                fees = fee_estimates_payload(chain)
                payload = {
                    "height": chain.height(),
                    "tip_hash": chain.tip_hash(),
                    "mempool": len(chain.mempool),
                    "mempool_depth": fees.get("mempool_depth", len(chain.mempool)),
                    "fee_rate_percentiles": fees.get("fee_rate_percentiles", {}),
                    "t": int(time.time()),
                }
                if payload != last:
                    self.wfile.write(
                        ("event: netcoin\n" + "data: " + json.dumps(payload, sort_keys=True) + "\n\n").encode("utf-8")
                    )
                    self.wfile.flush()
                    last = payload
                time.sleep(5)

        def client_ip(self) -> str:
            return client_ip_from_headers(self.headers, self.client_address, trust_proxy_headers=trust_proxy_headers)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if not self.require_admin(parsed.path, "GET"):
                return
            if not rate_limiter.allow((self.client_ip(), parsed.path)):
                self.send_json({"ok": False, "error": "rate limit exceeded"}, status=429)
                return
            try:
                if parsed.path == "/api/events/stream":
                    self.send_event_stream()
                elif parsed.path == "/api/events":
                    query = parse_qs(parsed.query)
                    self.send_json(events_payload(chain, int(query.get("limit", [50])[0])))
                elif parsed.path in ("/api/latest", "/api/blocks"):
                    query = parse_qs(parsed.query)
                    n = int(query.get("n", query.get("limit", [20]))[0])
                    page_num = int(query.get("page", [1])[0])
                    self.send_json(latest_payload(chain, n, page=page_num))
                elif parsed.path == "/api/latest-txs":
                    query = parse_qs(parsed.query)
                    n = int(query.get("n", query.get("limit", [20]))[0])
                    self.send_json(latest_transactions_payload(chain, n))
                elif parsed.path.startswith("/api/block/"):
                    block_hash = parsed.path.split("/", 3)[3]
                    block = chain.get_block_by_hash(block_hash)
                    if block is None:
                        self.send_json({"ok": False, "error": "block not found"}, status=404)
                    else:
                        coinbase_value = block.transactions[0].total_output() if block.transactions else 0
                        subsidy = chain.subsidy(block.header.height)
                        fees = max(0, coinbase_value - subsidy)
                        self.send_json(
                            block.to_dict()
                            | block_summary(block)
                            | {
                                "coinbase_value_sats": coinbase_value,
                                "subsidy_sats": subsidy,
                                "fees_sats": fees,
                            }
                        )
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
                elif parsed.path == "/api/mempool":
                    self.send_json(chain.mempool_info())
                elif parsed.path == "/api/fee-estimates":
                    self.send_json(fee_estimates_payload(chain))
                elif parsed.path == "/api/headers":
                    query = parse_qs(parsed.query)
                    start = int(query.get("start", [0])[0])
                    limit = int(query.get("limit", [200])[0])
                    self.send_json({"headers": chain.header_list(start, limit)})
                elif parsed.path == "/api/peers":
                    self.send_json(
                        {
                            "peers": [],
                            "scores": {},
                            "banned": [],
                            "note": "standalone explorer server has no peer manager",
                        }
                    )
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
                            items.append(
                                f"<li>Address <a href='/address/{match['address']}'>{esc(match['address'])}</a></li>"
                            )
                    self.send_html(
                        "Search",
                        f"<h1>Search</h1><p><a href='/'>Home</a></p><ul>{''.join(items) or '<li>No matches</li>'}</ul>",
                    )
                elif parsed.path.startswith("/block/"):
                    block_hash = parsed.path.split("/", 2)[2]
                    block = chain.get_block_by_hash(block_hash)
                    if block is None:
                        self.send_html("Not found", "<h1>Block not found</h1>", status=404)
                    else:
                        rows = "".join(
                            f"<li><a href='/tx/{tx.txid()}'>{tx.txid()}</a></li>" for tx in block.transactions
                        )
                        self.send_html(
                            "Block",
                            f"<h1>Block {block.header.height}</h1><p><a href='/'>Home</a></p><p class='hash'>{block.hash()}</p><ul>{rows}</ul>",
                        )
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
                        self.send_html(
                            "Transaction",
                            f"<h1>Transaction</h1><p><a href='/'>Home</a></p><p class='hash'>{esc(txid)}</p><ul>{outputs}</ul>",
                        )
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
                    try:
                        status, payload, content_type = route_app_get(
                            app_store, chain, parsed.path, parse_qs(parsed.query)
                        )
                    except AppError as app_exc:
                        if str(app_exc) == "not an app-layer route":
                            self.send_json({"ok": False, "error": "not found"}, status=404)
                        else:
                            self.send_json({"ok": False, "error": str(app_exc)}, status=400)
                    else:
                        if content_type == "application/json":
                            self.send_json(payload, status=status)  # type: ignore[arg-type]
                        else:
                            self.send_text(
                                payload if isinstance(payload, bytes) else str(payload),
                                status=status,
                                content_type=content_type,
                            )
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)

        def read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            if length > 2_000_000:
                raise ValueError("request body too large")
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            operator_verified = self.admin_required(parsed.path, "POST")
            if not self.require_admin(parsed.path, "POST"):
                return
            if not rate_limiter.allow((self.client_ip(), "POST", parsed.path)):
                self.send_json({"ok": False, "error": "rate limit exceeded"}, status=429)
                return
            try:
                data = self.read_json()
                header_api_key = self.api_key_from_headers()
                if header_api_key and "api_key" not in data:
                    data["api_key"] = header_api_key
                data["__netcoin_http_request"] = True
                if operator_verified:
                    data["__netcoin_operator_verified"] = True
                try:
                    status, payload = route_app_post(app_store, chain, parsed.path, data)
                except AppError as app_exc:
                    if str(app_exc) == "not an app-layer route":
                        self.send_json({"ok": False, "error": "not found"}, status=404)
                    else:
                        self.send_json({"ok": False, "error": str(app_exc)}, status=400)
                else:
                    self.send_json(payload, status=status)
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
