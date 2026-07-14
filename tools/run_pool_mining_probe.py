#!/usr/bin/env python3
"""Mine a NetCoin block through the Stratum-lite pool protocol."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path
from threading import Thread
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.chain import Blockchain  # noqa: E402
from netcoin.miner import solve_template  # noqa: E402
from netcoin.pool import MiningPool, StratumLiteTCPServer  # noqa: E402
from netcoin.wallet import Wallet  # noqa: E402


def pool_rpc(host: str, port: int, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with socket.create_connection((host, int(port)), timeout=10) as sock:
        reader = sock.makefile("rb")
        writer = sock.makefile("wb")
        responses = [json.loads(reader.readline().decode("utf-8"))]
        for message in messages:
            writer.write(json.dumps(message).encode("utf-8") + b"\n")
            writer.flush()
            responses.append(json.loads(reader.readline().decode("utf-8")))
        return responses


def run_probe(*, data_dir: Path, host: str = "127.0.0.1", port: int = 0, miner_id: str | None = None) -> dict[str, Any]:
    pool_wallet = Wallet.create()
    chain = Blockchain(data_dir)
    pool = MiningPool(chain, payout_address=pool_wallet.address)
    server = StratumLiteTCPServer((host, int(port)), pool)
    actual_port = int(server.server_address[1])
    thread = Thread(target=server.serve_forever, daemon=True)
    started = time.time()
    thread.start()
    try:
        greeting, work_response = pool_rpc(host, actual_port, [{"method": "getwork"}])
        template = work_response["result"]
        block = solve_template(template, pool_wallet.address)
        miner = miner_id or Wallet.create().address
        submit = {
            "method": "submit",
            "params": {
                "miner": miner,
                "job_id": template["job_id"],
                "block": block.to_dict(),
            },
        }
        submit_response = pool_rpc(host, actual_port, [submit])[1]
        stats = pool_rpc(host, actual_port, [{"method": "stats"}])[1]["result"]
        payouts = pool_rpc(host, actual_port, [{"method": "payouts"}])[1]["result"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    return {
        "schema": "netcoin-pool-mining-probe-v1",
        "ok": bool(submit_response.get("ok")) and chain.height() >= 1,
        "duration_seconds": round(time.time() - started, 3),
        "greeting": greeting,
        "submit": submit_response,
        "stats": stats,
        "payouts": payouts,
        "height": chain.height(),
        "tip_hash": chain.tip_hash(),
        "stratum_port": actual_port,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mine one block through the NetCoin Stratum-lite pool")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--miner-id")
    parser.add_argument("--out", type=Path, default=Path("reports/pool_mining_probe.json"))
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_probe(data_dir=args.data_dir, host=args.host, port=args.port, miner_id=args.miner_id)
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if not args.no_write:
        out = ROOT / args.out if not args.out.is_absolute() else args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
