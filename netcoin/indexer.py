"""Production-style explorer indexer for NetCoin.

This module builds normalized explorer/address/mempool tables from the canonical
Blockchain object.  The index is derived state and is designed to be dropped and
rebuilt after upgrades or deep reorgs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .indexer_storage import IndexerStorage
from .serialization import block_weight
from .tx import SpendableOutput, sats_to_amount


class ChainIndexer:
    def __init__(self, path: str | Path):
        self.storage = IndexerStorage(path)

    def rebuild(self, chain: Any, *, include_mempool: bool = True) -> dict[str, Any]:
        self.storage.reset()
        created_outputs: dict[str, SpendableOutput] = {}
        indexed_blocks = 0
        indexed_txs = 0
        indexed_events = 0
        with self.storage.connect() as conn:
            for block in chain.chain:
                block_hash = block.hash()
                conn.execute(
                    "INSERT OR REPLACE INTO blocks(height,block_hash,previous_hash,timestamp,tx_count,weight) VALUES(?,?,?,?,?,?)",
                    (
                        block.header.height,
                        block_hash,
                        block.header.previous_hash,
                        block.header.timestamp,
                        len(block.transactions),
                        block_weight(block),
                    ),
                )
                indexed_blocks += 1
                for position, tx in enumerate(block.transactions):
                    txid = tx.txid()
                    input_sats = 0
                    if not tx.is_coinbase:
                        for txin in tx.inputs:
                            spent = created_outputs.get(txin.outpoint())
                            if not spent:
                                continue
                            input_sats += int(spent.output.amount)
                            if spent.output.address:
                                conn.execute(
                                    "INSERT INTO address_events(address,txid,block_hash,height,vout,direction,amount_sats,timestamp,coinbase,spent_outpoint) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                    (
                                        spent.output.address,
                                        txid,
                                        block_hash,
                                        block.header.height,
                                        spent.vout,
                                        "send",
                                        -int(spent.output.amount),
                                        block.header.timestamp,
                                        int(spent.coinbase),
                                        txin.outpoint(),
                                    ),
                                )
                                indexed_events += 1
                    output_sats = tx.total_output()
                    fee_sats = max(0, input_sats - output_sats) if not tx.is_coinbase else 0
                    conn.execute(
                        "INSERT OR REPLACE INTO transactions(txid,block_hash,height,position,timestamp,input_sats,output_sats,fee_sats,raw_json,mempool) VALUES(?,?,?,?,?,?,?,?,?,0)",
                        (
                            txid,
                            block_hash,
                            block.header.height,
                            position,
                            block.header.timestamp,
                            input_sats,
                            output_sats,
                            fee_sats,
                            json.dumps(tx.to_dict(), sort_keys=True),
                        ),
                    )
                    indexed_txs += 1
                    if not tx.is_coinbase:
                        for txin in tx.inputs:
                            created_outputs.pop(txin.outpoint(), None)
                    for vout, output in enumerate(tx.outputs):
                        if output.amount <= 0:
                            continue
                        spendable = SpendableOutput(
                            txid=txid, vout=vout, output=output, height=block.header.height, coinbase=tx.is_coinbase
                        )
                        created_outputs[spendable.outpoint()] = spendable
                        if output.address:
                            conn.execute(
                                "INSERT INTO address_events(address,txid,block_hash,height,vout,direction,amount_sats,timestamp,coinbase,spent_outpoint) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (
                                    output.address,
                                    txid,
                                    block_hash,
                                    block.header.height,
                                    vout,
                                    "receive",
                                    int(output.amount),
                                    block.header.timestamp,
                                    int(tx.is_coinbase),
                                    "",
                                ),
                            )
                            indexed_events += 1
            conn.execute(
                "INSERT OR REPLACE INTO indexer_meta(key,value) VALUES('tip_height',?)", (json.dumps(chain.height()),)
            )
            conn.execute(
                "INSERT OR REPLACE INTO indexer_meta(key,value) VALUES('tip_hash',?)", (json.dumps(chain.tip_hash()),)
            )
            conn.commit()
        mempool_count = self.index_mempool(chain) if include_mempool else 0
        return {
            "indexed_blocks": indexed_blocks,
            "indexed_transactions": indexed_txs,
            "indexed_address_events": indexed_events,
            "indexed_mempool_transactions": mempool_count,
            "tip_height": chain.height(),
            "tip_hash": chain.tip_hash(),
        }

    def index_mempool(self, chain: Any) -> int:
        with self.storage.connect() as conn:
            conn.execute("DELETE FROM transactions WHERE mempool=1")
            count = 0
            for tx in getattr(chain, "mempool", []):
                txid = tx.txid()
                conn.execute(
                    "INSERT OR REPLACE INTO transactions(txid,block_hash,height,position,timestamp,input_sats,output_sats,fee_sats,raw_json,mempool) VALUES(?,?,?,?,?,?,?,?,?,1)",
                    (
                        txid,
                        None,
                        None,
                        None,
                        int(getattr(chain, "mempool_times", {}).get(txid, 0) or 0),
                        0,
                        tx.total_output(),
                        0,
                        json.dumps(tx.to_dict(), sort_keys=True),
                    ),
                )
                count += 1
            conn.commit()
        return count

    def rollback_to_height(self, height: int) -> None:
        self.storage.rollback_to_height(height)

    def address_history(self, address: str, limit: int = 100) -> dict[str, Any]:
        limit = max(1, min(int(limit), 500))
        rows = self.storage.rows(
            "SELECT * FROM address_events WHERE address=? ORDER BY COALESCE(height, 2147483647) DESC, id DESC LIMIT ?",
            (address, limit),
        )
        running = 0
        chronological = list(reversed(rows))
        for row in chronological:
            running += int(row["amount_sats"])
            row["running_balance_sats"] = running
            row["running_balance"] = sats_to_amount(running)
            row["amount"] = sats_to_amount(int(row["amount_sats"]))
        balance = sum(
            int(row["amount_sats"])
            for row in self.storage.rows("SELECT amount_sats FROM address_events WHERE address=?", (address,))
        )
        return {
            "address": address,
            "events": rows,
            "balance_sats": balance,
            "balance": sats_to_amount(balance),
            "count": len(rows),
        }

    def tx_graph(self, txid: str) -> dict[str, Any]:
        tx_rows = self.storage.rows("SELECT * FROM transactions WHERE txid=?", (txid,))
        if not tx_rows:
            return {"txid": txid, "found": False, "inputs": [], "outputs": []}
        events = self.storage.rows("SELECT * FROM address_events WHERE txid=? ORDER BY id", (txid,))
        return {
            "txid": txid,
            "found": True,
            "transaction": tx_rows[0],
            "inputs": [e for e in events if e["direction"] == "send"],
            "outputs": [e for e in events if e["direction"] == "receive"],
        }

    def summary(self) -> dict[str, Any]:
        stats = self.storage.rows("""SELECT
                (SELECT COUNT(*) FROM blocks) AS blocks,
                (SELECT COUNT(*) FROM transactions WHERE mempool=0) AS transactions,
                (SELECT COUNT(*) FROM transactions WHERE mempool=1) AS mempool_transactions,
                (SELECT COUNT(DISTINCT address) FROM address_events) AS addresses,
                (SELECT COALESCE(SUM(CASE WHEN amount_sats>0 THEN amount_sats ELSE 0 END),0) FROM address_events) AS received_sats
            """)[0]
        stats["tip_height"] = self.storage.get_meta("tip_height", -1)
        stats["tip_hash"] = self.storage.get_meta("tip_hash", "")
        stats["received"] = sats_to_amount(int(stats.get("received_sats", 0)))
        return stats

    def address_profile(self, address: str) -> dict[str, Any]:
        """Return a richer explorer profile for one address.

        This is derived data for UI/explorer use: first/last seen, send/receive
        totals, net balance, activity counts, and lightweight flags that help a
        wallet or explorer call out unusual activity.
        """
        rows = self.storage.rows(
            "SELECT * FROM address_events WHERE address=? ORDER BY COALESCE(height, 2147483647), id",
            (address,),
        )
        received_sats = sum(int(r["amount_sats"]) for r in rows if int(r["amount_sats"]) > 0)
        sent_sats = -sum(int(r["amount_sats"]) for r in rows if int(r["amount_sats"]) < 0)
        heights = [int(r["height"]) for r in rows if r.get("height") is not None]
        timestamps = [int(r["timestamp"]) for r in rows if r.get("timestamp")]
        dust_receives = [r for r in rows if r["direction"] == "receive" and 0 < int(r["amount_sats"]) < 546]
        return {
            "address": address,
            "event_count": len(rows),
            "receive_count": sum(1 for r in rows if r["direction"] == "receive"),
            "send_count": sum(1 for r in rows if r["direction"] == "send"),
            "received_sats": received_sats,
            "sent_sats": sent_sats,
            "balance_sats": received_sats - sent_sats,
            "received": sats_to_amount(received_sats),
            "sent": sats_to_amount(sent_sats),
            "balance": sats_to_amount(received_sats - sent_sats),
            "first_seen_height": min(heights) if heights else None,
            "last_seen_height": max(heights) if heights else None,
            "first_seen_timestamp": min(timestamps) if timestamps else None,
            "last_seen_timestamp": max(timestamps) if timestamps else None,
            "flags": {
                "has_activity": bool(rows),
                "dust_receive_count": len(dust_receives),
                "coinbase_receive_count": sum(
                    1 for r in rows if r["direction"] == "receive" and int(r.get("coinbase") or 0)
                ),
            },
        }

    def top_addresses(self, limit: int = 25) -> dict[str, Any]:
        """Return top active addresses by derived balance and total volume."""
        limit = max(1, min(int(limit), 250))
        rows = self.storage.rows(
            """SELECT address,
                      COUNT(*) AS event_count,
                      SUM(amount_sats) AS balance_sats,
                      SUM(CASE WHEN amount_sats > 0 THEN amount_sats ELSE 0 END) AS received_sats,
                      SUM(CASE WHEN amount_sats < 0 THEN -amount_sats ELSE 0 END) AS sent_sats
               FROM address_events
               GROUP BY address
               ORDER BY balance_sats DESC, received_sats DESC
               LIMIT ?""",
            (limit,),
        )
        for row in rows:
            for key in ("balance_sats", "received_sats", "sent_sats"):
                row[key] = int(row.get(key) or 0)
            row["balance"] = sats_to_amount(row["balance_sats"])
            row["received"] = sats_to_amount(row["received_sats"])
            row["sent"] = sats_to_amount(row["sent_sats"])
        return {"limit": limit, "addresses": rows, "count": len(rows)}

    def mempool_summary(self) -> dict[str, Any]:
        rows = self.storage.rows(
            "SELECT txid, output_sats, fee_sats, timestamp FROM transactions WHERE mempool=1 ORDER BY timestamp DESC"
        )
        total_output = sum(int(r.get("output_sats") or 0) for r in rows)
        total_fee = sum(int(r.get("fee_sats") or 0) for r in rows)
        return {
            "transaction_count": len(rows),
            "total_output_sats": total_output,
            "total_output": sats_to_amount(total_output),
            "total_fee_sats": total_fee,
            "total_fee": sats_to_amount(total_fee),
            "transactions": rows[:100],
        }

    def export_address_history_csv(self, address: str, path: str | Path, limit: int = 1000) -> dict[str, Any]:
        import csv

        history = self.address_history(address, limit=limit)["events"]
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "id",
            "address",
            "txid",
            "height",
            "direction",
            "amount_sats",
            "amount",
            "running_balance_sats",
            "running_balance",
            "timestamp",
        ]
        with out.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for row in history:
                writer.writerow({k: row.get(k, "") for k in fields})
        return {"ok": True, "address": address, "path": str(out), "rows": len(history)}

    def integrity_report(self) -> dict[str, Any]:
        """Check derived explorer tables for common indexing inconsistencies."""
        missing_block_rows = self.storage.rows(
            "SELECT txid, block_hash FROM transactions WHERE mempool=0 AND block_hash IS NOT NULL AND block_hash NOT IN (SELECT block_hash FROM blocks) LIMIT 25"
        )
        orphan_events = self.storage.rows(
            "SELECT txid, address FROM address_events WHERE txid NOT IN (SELECT txid FROM transactions) LIMIT 25"
        )
        duplicate_blocks = self.storage.rows(
            "SELECT block_hash, COUNT(*) count FROM blocks GROUP BY block_hash HAVING COUNT(*) > 1 LIMIT 25"
        )
        ok = not missing_block_rows and not orphan_events and not duplicate_blocks
        return {
            "ok": ok,
            "missing_block_transactions": missing_block_rows,
            "orphan_address_events": orphan_events,
            "duplicate_blocks": duplicate_blocks,
            "tip_height": self.storage.get_meta("tip_height", -1),
            "tip_hash": self.storage.get_meta("tip_hash", ""),
        }
