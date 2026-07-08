"""Explorer insight helpers built on top of the derived indexer database.

These helpers keep the explorer UI fast without making the indexer consensus
critical. They provide search suggestions, address relationship summaries, and
exportable explorer bundles that are safe to rebuild at any time.
"""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from typing import Any

from .tx import sats_to_amount


def _storage(indexer: Any) -> Any:
    return getattr(indexer, "storage", indexer)


def search_suggestions(indexer: Any, query: str, *, limit: int = 10) -> dict[str, Any]:
    """Return explorer search suggestions for blocks, transactions, and addresses."""
    storage = _storage(indexer)
    text = str(query or "").strip()
    if not text:
        return {"query": text, "suggestions": []}
    limit = max(1, min(int(limit), 50))
    suggestions: list[dict[str, Any]] = []
    if text.isdigit():
        for row in storage.rows(
            "SELECT height, block_hash, timestamp, tx_count FROM blocks WHERE height=? LIMIT 1", (int(text),)
        ):
            suggestions.append(
                {
                    "type": "block",
                    "score": 100,
                    "id": row["block_hash"],
                    "height": row["height"],
                    "label": f"Block {row['height']}",
                }
            )
    like = f"{text}%"
    for row in storage.rows(
        "SELECT height, block_hash, timestamp, tx_count FROM blocks WHERE block_hash LIKE ? ORDER BY height DESC LIMIT ?",
        (like, limit),
    ):
        suggestions.append(
            {
                "type": "block",
                "score": 95,
                "id": row["block_hash"],
                "height": row["height"],
                "label": f"Block {row['height']}",
            }
        )
    for row in storage.rows(
        "SELECT txid, height, mempool, fee_sats FROM transactions WHERE txid LIKE ? ORDER BY COALESCE(height, 2147483647) DESC LIMIT ?",
        (like, limit),
    ):
        suggestions.append(
            {
                "type": "transaction",
                "score": 90 if not row["mempool"] else 80,
                "id": row["txid"],
                "height": row["height"],
                "mempool": bool(row["mempool"]),
                "label": f"Transaction {row['txid'][:12]}",
            }
        )
    for row in storage.rows(
        "SELECT address, COUNT(*) AS events, COALESCE(SUM(amount_sats),0) AS balance_sats FROM address_events WHERE address LIKE ? GROUP BY address ORDER BY events DESC LIMIT ?",
        (like, limit),
    ):
        suggestions.append(
            {
                "type": "address",
                "score": 85,
                "id": row["address"],
                "label": row["address"],
                "event_count": row["events"],
                "balance_sats": row["balance_sats"],
                "balance": sats_to_amount(int(row["balance_sats"])),
            }
        )
    suggestions.sort(key=lambda item: (-int(item.get("score", 0)), str(item.get("type")), str(item.get("id"))))
    return {"query": text, "suggestions": suggestions[:limit], "count": min(len(suggestions), limit)}


def address_activity_heatmap(indexer: Any, address: str) -> dict[str, Any]:
    """Summarize an address by day-of-week and hour-of-day buckets."""
    import datetime as _dt

    storage = _storage(indexer)
    rows = storage.rows("SELECT timestamp, amount_sats, direction FROM address_events WHERE address=?", (address,))
    by_hour: Counter[int] = Counter()
    by_weekday: Counter[int] = Counter()
    net_by_hour: defaultdict[int, int] = defaultdict(int)
    for row in rows:
        ts = int(row.get("timestamp") or 0)
        if ts <= 0:
            continue
        dt = _dt.datetime.fromtimestamp(ts, _dt.timezone.utc)
        by_hour[dt.hour] += 1
        by_weekday[dt.weekday()] += 1
        net_by_hour[dt.hour] += int(row.get("amount_sats") or 0)
    return {
        "address": address,
        "event_count": len(rows),
        "by_hour_utc": {str(hour): by_hour.get(hour, 0) for hour in range(24)},
        "net_sats_by_hour_utc": {str(hour): net_by_hour.get(hour, 0) for hour in range(24)},
        "by_weekday_utc": {str(day): by_weekday.get(day, 0) for day in range(7)},
    }


def address_counterparties(indexer: Any, address: str, *, limit: int = 25) -> dict[str, Any]:
    """Infer likely counterparties from transactions shared with an address."""
    storage = _storage(indexer)
    limit = max(1, min(int(limit), 100))
    own_events = storage.rows("SELECT txid, direction, amount_sats FROM address_events WHERE address=?", (address,))
    txids = [row["txid"] for row in own_events]
    stats: dict[str, dict[str, Any]] = {}
    for txid in txids:
        rows = storage.rows(
            "SELECT address, direction, amount_sats FROM address_events WHERE txid=? AND address<>?", (txid, address)
        )
        for row in rows:
            cp = row["address"]
            item = stats.setdefault(
                cp, {"address": cp, "shared_transactions": 0, "sent_to_sats": 0, "received_from_sats": 0, "net_sats": 0}
            )
            item["shared_transactions"] += 1
            amount = int(row.get("amount_sats") or 0)
            item["net_sats"] += amount
            if amount > 0:
                item["sent_to_sats"] += amount
            else:
                item["received_from_sats"] += abs(amount)
    counterparties = list(stats.values())
    counterparties.sort(key=lambda item: (-item["shared_transactions"], -abs(int(item["net_sats"])), item["address"]))
    for item in counterparties:
        item["sent_to"] = sats_to_amount(int(item["sent_to_sats"]))
        item["received_from"] = sats_to_amount(int(item["received_from_sats"]))
        item["net"] = sats_to_amount(int(item["net_sats"]))
    return {"address": address, "counterparties": counterparties[:limit], "count": min(len(counterparties), limit)}


def address_profile_bundle(indexer: Any, address: str, *, history_limit: int = 100) -> dict[str, Any]:
    """Return all explorer data a wallet/address details page typically needs."""
    return {
        "address": address,
        "profile": indexer.address_profile(address) if hasattr(indexer, "address_profile") else {},
        "history": indexer.address_history(address, limit=history_limit) if hasattr(indexer, "address_history") else {},
        "heatmap": address_activity_heatmap(indexer, address),
        "counterparties": address_counterparties(indexer, address),
    }


def export_address_history_csv(indexer: Any, address: str, *, limit: int = 1000) -> str:
    """Export address history as CSV text for support/debug downloads."""
    history = indexer.address_history(address, limit=limit) if hasattr(indexer, "address_history") else {"events": []}
    out = io.StringIO()
    fields = ["height", "timestamp", "txid", "direction", "amount_sats", "amount", "vout", "coinbase", "spent_outpoint"]
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for event in history.get("events", []):
        writer.writerow({key: event.get(key, "") for key in fields})
    return out.getvalue()
