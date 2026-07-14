"""Stratum-lite educational mining-pool server for NetCoin.

This is not production Stratum software. It exposes the existing HTTP template
API plus a small JSON-lines TCP protocol so local miners can request work,
submit solved blocks, account shares, and inspect payout plans.
"""

from __future__ import annotations

import hashlib
import json
import socketserver
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

from .block import Block, check_proof_of_work
from .chain import Blockchain
from .params import DEFAULT_POOL_PORT, MAX_REQUEST_BODY_BYTES
from .tx import SpendableOutput, Transaction, TxInput, TxOutput

POOL_PROTOCOL = "netcoin-pool-stratum-lite-v1"


@dataclass
class ShareRecord:
    miner: str
    job_id: str
    block_hash: str
    difficulty: int
    accepted_block: bool
    height: int
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "miner": self.miner,
            "job_id": self.job_id,
            "block_hash": self.block_hash,
            "difficulty": self.difficulty,
            "accepted_block": self.accepted_block,
            "height": self.height,
            "created_at": round(self.created_at, 3),
        }


class MiningPool:
    def __init__(self, chain: Blockchain, payout_address: str, *, min_share_zeroes: int = 0):
        self.chain = chain
        self.payout_address = payout_address
        self.min_share_zeroes = max(0, int(min_share_zeroes))
        self.accepted = 0
        self.rejected = 0
        self.jobs: dict[str, dict[str, Any]] = {}
        self.shares: list[ShareRecord] = []
        self.accepted_blocks: list[dict[str, Any]] = []

    def job(self) -> dict[str, Any]:
        template = self.chain.get_block_template(miner_address=self.payout_address)
        job_id = self._job_id(template)
        self.jobs[job_id] = template
        template["job_id"] = job_id
        template["pool"] = {
            "protocol": POOL_PROTOCOL,
            "payout_address": self.payout_address,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "min_share_zeroes": self.min_share_zeroes,
        }
        return template

    def _job_id(self, template: dict[str, Any]) -> str:
        seed = {
            "height": template["height"],
            "previous_hash": template["previous_hash"],
            "bits": template["bits"],
            "coinbase_value": template["coinbase_value"],
            "nonce": uuid.uuid4().hex,
        }
        return hashlib.sha256(json.dumps(seed, sort_keys=True).encode()).hexdigest()[:24]

    @staticmethod
    def share_difficulty(block_hash: str) -> int:
        return len(block_hash) - len(block_hash.lstrip("0"))

    def submit(self, data: dict[str, Any]) -> dict[str, Any]:
        miner = str(data.get("miner") or "unknown")
        job_id = str(data.get("job_id") or "")
        block = Block.from_dict(data["block"])
        block_hash = block.hash()
        difficulty = self.share_difficulty(block_hash)
        if job_id and job_id not in self.jobs:
            self.rejected += 1
            return {"ok": False, "error": "unknown job_id", "job_id": job_id}
        if job_id:
            job = self.jobs[job_id]
            if block.header.height != int(job["height"]) or block.header.previous_hash != str(job["previous_hash"]):
                self.rejected += 1
                return {"ok": False, "error": "submitted block does not match job", "job_id": job_id}
        if difficulty < self.min_share_zeroes and not check_proof_of_work(block.header):
            self.rejected += 1
            return {"ok": False, "error": "share target not met", "difficulty": difficulty}

        share = ShareRecord(
            miner=miner,
            job_id=job_id,
            block_hash=block_hash,
            difficulty=max(1, difficulty),
            accepted_block=False,
            height=block.header.height,
        )
        try:
            block_hash = self.chain.add_block(block)
            share.accepted_block = True
            self.shares.append(share)
            self.accepted += 1
            reward = block.transactions[0].total_output() if block.transactions else 0
            self.accepted_blocks.append({"block_hash": block_hash, "height": block.header.height, "reward": reward})
            return {
                "ok": True,
                "accepted_block": True,
                "block_hash": block_hash,
                "height": block.header.height,
                "share": share.to_dict(),
                "payouts": self.payout_plan(reward=reward),
            }
        except Exception as exc:
            self.shares.append(share)
            self.rejected += 1
            return {
                "ok": False,
                "accepted_share": True,
                "accepted_block": False,
                "error": str(exc),
                "share": share.to_dict(),
            }

    def stats(self) -> dict[str, Any]:
        return {
            "schema": "netcoin-pool-stats-v1",
            "protocol": POOL_PROTOCOL,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "share_count": len(self.shares),
            "accepted_blocks": list(self.accepted_blocks),
            "miners": sorted({share.miner for share in self.shares}),
        }

    def payout_plan(self, *, reward: int | None = None) -> dict[str, Any]:
        total_weight = sum(max(1, share.difficulty) for share in self.shares)
        reward_value = int(
            reward if reward is not None else (self.accepted_blocks[-1]["reward"] if self.accepted_blocks else 0)
        )
        payouts: dict[str, int] = {}
        if total_weight > 0 and reward_value > 0:
            remaining = reward_value
            ordered = sorted(self.shares, key=lambda share: share.miner)
            for index, share in enumerate(ordered):
                if index == len(ordered) - 1:
                    amount = remaining
                else:
                    amount = reward_value * max(1, share.difficulty) // total_weight
                    remaining -= amount
                payouts[share.miner] = payouts.get(share.miner, 0) + amount
        return {
            "schema": "netcoin-pool-payout-plan-v1",
            "reward": reward_value,
            "share_weight_total": total_weight,
            "payouts": payouts,
            "constructs_unsigned_transaction_only": True,
        }

    def construct_payout_transaction(self, reward_utxo: SpendableOutput, payouts: dict[str, int]) -> Transaction:
        outputs = [
            TxOutput(amount=int(amount), address=miner) for miner, amount in sorted(payouts.items()) if int(amount) > 0
        ]
        return Transaction(
            inputs=[TxInput(txid=reward_utxo.txid, vout=reward_utxo.vout)],
            outputs=outputs,
        )

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        method = str(message.get("method") or "").lower()
        if method in {"getwork", "job"}:
            return {"ok": True, "result": self.job()}
        if method == "submit":
            return self.submit(dict(message.get("params") or {}))
        if method == "stats":
            return {"ok": True, "result": self.stats()}
        if method == "payouts":
            return {"ok": True, "result": self.payout_plan()}
        return {"ok": False, "error": f"unknown method: {method}"}


class PoolError(ValueError):
    pass


def make_handler(pool: MiningPool):
    class Handler(BaseHTTPRequestHandler):
        server_version = "NetCoinPool/0.2"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_json(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except (TypeError, ValueError) as exc:
                raise PoolError("invalid Content-Length") from exc
            if length > MAX_REQUEST_BODY_BYTES:
                raise PoolError("request body too large")
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self) -> None:
            if self.path in ("/", "/job", "/getblocktemplate"):
                self.send_json(pool.job())
            elif self.path == "/stats":
                self.send_json(pool.stats())
            elif self.path == "/payouts":
                self.send_json(pool.payout_plan())
            else:
                self.send_json({"ok": False, "error": "not found"}, status=404)

        def do_POST(self) -> None:
            try:
                if self.path == "/submit":
                    self.send_json(pool.submit(self.read_json()))
                else:
                    self.send_json({"ok": False, "error": "not found"}, status=404)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=400)

    return Handler


class StratumLiteTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], pool: MiningPool):
        self.pool = pool
        super().__init__(server_address, StratumLiteHandler)


class StratumLiteHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.wfile.write(json.dumps({"ok": True, "protocol": POOL_PROTOCOL}).encode() + b"\n")
        for raw in self.rfile:
            try:
                message = json.loads(raw.decode("utf-8"))
                response = self.server.pool.handle_message(message)  # type: ignore[attr-defined]
            except Exception as exc:
                response = {"ok": False, "error": str(exc)}
            self.wfile.write(json.dumps(response, sort_keys=True).encode("utf-8") + b"\n")


def run_stratum_lite_server(pool: MiningPool, host: str = "127.0.0.1", port: int = DEFAULT_POOL_PORT + 1):
    server = StratumLiteTCPServer((host, int(port)), pool)
    server.serve_forever()


def run_pool(
    data_dir: str,
    payout_address: str,
    host: str = "127.0.0.1",
    port: int = DEFAULT_POOL_PORT,
    stratum_port: int = DEFAULT_POOL_PORT + 1,
) -> None:
    chain = Blockchain(data_dir=data_dir)
    pool = MiningPool(chain, payout_address=payout_address)
    server = ThreadingHTTPServer((host, port), make_handler(pool))
    stratum_server = StratumLiteTCPServer((host, int(stratum_port)), pool)
    stratum_thread = Thread(target=stratum_server.serve_forever, daemon=True)
    stratum_thread.start()
    print(f"NetCoin educational pool listening on http://{host}:{port}")
    print(f"NetCoin stratum-lite pool listening on tcp://{host}:{stratum_port}")
    print(f"payout_address={payout_address}")
    try:
        server.serve_forever()
    finally:
        stratum_server.shutdown()
        stratum_server.server_close()
        stratum_thread.join(timeout=5)
        server.server_close()
