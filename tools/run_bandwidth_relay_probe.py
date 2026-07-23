#!/usr/bin/env python3
"""Probe outbound relay bandwidth enforcement against localnet peer processes."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.bandwidth import budget_for_mode
from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode
from tools.run_localnet import Localnet, LocalnetConfig


def make_flood_payload(target_bytes: int) -> dict[str, Any]:
    peers: list[str] = []
    index = 0
    while len(json.dumps({"peers": peers}).encode("utf-8")) < target_bytes:
        peers.append(f"http://127.0.0.1:{20000 + (index % 2000)}")
        index += 1
    return {"peers": peers}


def run_probe(
    *,
    mode: str = "home",
    nodes: int = 3,
    payload_bytes: int = 900_000,
    root_dir: Path | None = None,
    keep_artifacts: bool = False,
    startup_timeout: float = 20.0,
) -> dict[str, Any]:
    budget = budget_for_mode(mode)
    if budget.max_bytes_per_second <= 0:
        raise ValueError("bandwidth relay probe requires a capped mode")
    with Localnet(
        LocalnetConfig(
            nodes=nodes,
            startup_timeout=startup_timeout,
            keep_artifacts=keep_artifacts,
            root_dir=root_dir,
        )
    ) as localnet:
        localnet.start_all(topology="none", sync_interval=0)
        chain = Blockchain(localnet.root / "probe-source-chain")
        source = NetCoinNode(
            chain,
            peers=[node.url for node in localnet.nodes],
            persist=False,
            request_retries=0,
            bandwidth_mode=mode,
        )
        payload = make_flood_payload(payload_bytes)
        body_bytes = len(json.dumps(payload).encode("utf-8"))
        source.enqueue_relay("bandwidth-probe", "/peers", "flood", payload, force=True)
        started = time.monotonic()
        delivered = source.drain_relay_queue()
        duration = max(0.001, time.monotonic() - started)
        status = source.bandwidth_status()
        relay = status["outbound_relay"]
        bytes_sent = int(relay["bytes"])
        burst_bytes = int(relay["capacity"])
        sustained_bps = max(0, bytes_sent - burst_bytes) / duration
        localnet.stop_all()
        localnet.assert_no_survivors()

    return {
        "schema": "netcoin-bandwidth-relay-probe-v1",
        "ok": delivered == nodes and sustained_bps <= budget.max_bytes_per_second,
        "mode": mode,
        "nodes": nodes,
        "delivered": delivered,
        "payload_bytes": body_bytes,
        "bytes_sent": bytes_sent,
        "duration_seconds": round(duration, 3),
        "burst_bytes": burst_bytes,
        "sustained_bytes_per_second": round(sustained_bps, 3),
        "max_bytes_per_second": budget.max_bytes_per_second,
        "throttle_events": int(relay["throttle_events"]),
        "wait_seconds": relay["wait_seconds"],
        "root_dir": str(root_dir) if root_dir else "",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe NetCoin relay bandwidth limits on localnet")
    parser.add_argument("--mode", choices=["home", "low"], default="home")
    parser.add_argument("--nodes", type=int, default=3)
    parser.add_argument("--payload-bytes", type=int, default=900_000)
    parser.add_argument("--root-dir", type=Path)
    parser.add_argument("--keep-artifacts", action="store_true")
    parser.add_argument("--startup-timeout", type=float, default=20.0)
    parser.add_argument("--out", type=Path, default=Path("reports/bandwidth_relay_probe.json"))
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_probe(
        mode=args.mode,
        nodes=args.nodes,
        payload_bytes=args.payload_bytes,
        root_dir=args.root_dir,
        keep_artifacts=args.keep_artifacts,
        startup_timeout=args.startup_timeout,
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if not args.no_write:
        out = ROOT / args.out if not args.out.is_absolute() else args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
