#!/usr/bin/env python3
"""Run local-only NetCoin chaos drills against a subprocess localnet."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.run_localnet import Localnet, LocalnetConfig, post_json


class ChaosDrillError(RuntimeError):
    """Raised when a local chaos drill invariant fails."""


@dataclass
class ChaosConfig:
    nodes: int = 3
    startup_timeout: float = 20.0
    recovery_timeout: float = 30.0
    keep_artifacts: bool = False
    root_dir: Path | None = None


@dataclass
class ChaosReport:
    ok: bool
    root_dir: str
    duration_seconds: float
    drills: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    does_not_claim: list[str] = field(
        default_factory=lambda: [
            "production chaos drill",
            "public seed recovery evidence",
            "external audit completion",
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "schema": "netcoin-chaos-drill-v1",
            "root_dir": self.root_dir,
            "duration_seconds": round(self.duration_seconds, 3),
            "drills": self.drills,
            "errors": self.errors,
            "does_not_claim": self.does_not_claim,
        }


def _assert_localhost(localnet: Localnet) -> None:
    for node in localnet.nodes:
        if not node.url.startswith("http://127.0.0.1:"):
            raise ChaosDrillError(f"refusing non-local node URL: {node.url}")


def _tips(localnet: Localnet) -> list[dict[str, Any]]:
    infos = [localnet.node_info(node) for node in localnet.nodes]
    return [{"node": idx, "height": info["height"], "tip_hash": info["tip_hash"]} for idx, info in enumerate(infos)]


def _mine_and_converge(localnet: Localnet, node_index: int, address: str, blocks: int) -> dict[str, Any]:
    before = localnet.node_info(localnet.nodes[node_index])
    localnet.mine_blocks(localnet.nodes[node_index], address, blocks)
    after = localnet.wait_for_convergence(height=int(before["height"]) + blocks)
    return {
        "before_height": before["height"],
        "after_height": after["height"],
        "tip_hash": after["tip"],
    }


def drill_kill_restart_resync(localnet: Localnet, miner: Any, config: ChaosConfig) -> dict[str, Any]:
    before = _mine_and_converge(localnet, 0, miner.address, 2)
    localnet.stop_node(localnet.nodes[-1], hard=True)
    localnet.mine_blocks(localnet.nodes[0], miner.address, 2)
    offline_height = localnet.node_info(localnet.nodes[0])["height"]
    localnet.restart_node(localnet.nodes[-1].index, topology="line", sync_interval=1)
    recovered = localnet.wait_for_convergence(height=offline_height, timeout=config.recovery_timeout)
    return {
        "id": "kill-restart-resync",
        "ok": True,
        "before": before,
        "offline_tip_height": offline_height,
        "recovered_height": recovered["height"],
        "recovered_tip": recovered["tip"],
    }


def drill_mempool_file_corruption(localnet: Localnet, config: ChaosConfig) -> dict[str, Any]:
    node = localnet.nodes[1]
    localnet.stop_node(node, hard=True)
    corrupt = node.data_dir / "mempool.json"
    corrupt.write_text("{not valid json", encoding="utf-8")
    localnet.restart_node(node.index, topology="line", sync_interval=1)
    health = localnet.wait_for_health(node, time.time() + config.startup_timeout)
    recovered = localnet.wait_for_convergence(timeout=config.recovery_timeout)
    return {
        "id": "mempool-file-corruption",
        "ok": True,
        "corrupt_file": str(corrupt),
        "health_ok": bool(health.get("ok")),
        "recovered_height": recovered["height"],
        "recovered_tip": recovered["tip"],
    }


def drill_partition_rejoin(localnet: Localnet, miner_a: Any, miner_b: Any, config: ChaosConfig) -> dict[str, Any]:
    localnet.stop_all()

    partition_config = LocalnetConfig(
        nodes=config.nodes,
        bootstrap_blocks=101,
        relay_timeout=config.recovery_timeout,
        startup_timeout=config.startup_timeout,
        keep_artifacts=config.keep_artifacts,
        root_dir=localnet.root / "partition-rejoin",
    )
    with Localnet(partition_config) as partition_net:
        partition_net.start_all(topology="none", sync_interval=0)
        partition_net.mine_block(partition_net.nodes[0], miner_a.address)
        partition_net.mine_blocks(partition_net.nodes[1], miner_b.address, 2)
        partitioned = _tips(partition_net)
        partitioned_tips = {item["tip_hash"] for item in partitioned}
        if len(partitioned_tips) < 2:
            raise ChaosDrillError("partition drill did not create competing isolated tips")
        partition_net.add_peers("mesh")
        recovered = partition_net.wait_for_convergence(height=2, timeout=config.recovery_timeout)
        partition_net.stop_all()
        partition_net.assert_no_survivors()
    return {
        "id": "partition-rejoin",
        "ok": True,
        "partitioned_tips": partitioned,
        "competing_tips": len(partitioned_tips),
        "recovered_height": recovered["height"],
        "recovered_tip": recovered["tip"],
    }


def drill_relay_queue_recovery(localnet: Localnet) -> dict[str, Any]:
    dead_peer = "http://127.0.0.1:1"
    peers_before = post_json(f"{localnet.nodes[0].url}/peers", {"peers": [dead_peer]}, timeout=5)
    relay = post_json(f"{localnet.nodes[0].url}/relay", {}, timeout=10)
    localnet.add_peers("line")
    recovered = localnet.wait_for_convergence(timeout=20)
    return {
        "id": "dead-peer-relay-drain",
        "ok": True,
        "dead_peer_added": dead_peer in peers_before.get("peers", []),
        "relay_queue": relay.get("queue"),
        "recovered_height": recovered["height"],
        "recovered_tip": recovered["tip"],
    }


def run_chaos_drill(config: ChaosConfig) -> dict[str, Any]:
    if not 3 <= config.nodes <= 7:
        raise ChaosDrillError("chaos drill requires 3 to 7 local nodes")
    from netcoin.wallet import Wallet

    started = time.time()
    root = ""
    drills: list[dict[str, Any]] = []
    errors: list[str] = []
    root_dir = config.root_dir
    if root_dir is None and config.keep_artifacts:
        root_dir = Path(tempfile.mkdtemp(prefix="netcoin-chaos-"))
    try:
        with Localnet(
            LocalnetConfig(
                nodes=config.nodes,
                bootstrap_blocks=101,
                startup_timeout=config.startup_timeout,
                relay_timeout=config.recovery_timeout,
                keep_artifacts=config.keep_artifacts,
                root_dir=root_dir,
            )
        ) as localnet:
            root = str(localnet.root)
            _assert_localhost(localnet)
            miner_a = Wallet.create()
            miner_b = Wallet.create()
            localnet.start_all(topology="line", sync_interval=1)
            drills.append(drill_kill_restart_resync(localnet, miner_a, config))
            drills.append(drill_mempool_file_corruption(localnet, config))
            drills.append(drill_relay_queue_recovery(localnet))
            drills.append(drill_partition_rejoin(localnet, miner_a, miner_b, config))
            localnet.stop_all()
            localnet.assert_no_survivors()
    except Exception as exc:
        errors.append(f"{exc.__class__.__name__}: {exc}")
    return ChaosReport(
        ok=not errors and all(item.get("ok") for item in drills),
        root_dir=root,
        duration_seconds=time.time() - started,
        drills=drills,
        errors=errors,
    ).to_dict()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local-only NetCoin chaos drills")
    parser.add_argument("--nodes", type=int, default=3, help="number of local nodes to spawn (3-7)")
    parser.add_argument("--startup-timeout", type=float, default=20.0)
    parser.add_argument("--recovery-timeout", type=float, default=30.0)
    parser.add_argument("--root-dir", type=Path)
    parser.add_argument("--keep-artifacts", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true", help="print JSON report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_chaos_drill(
        ChaosConfig(
            nodes=args.nodes,
            startup_timeout=args.startup_timeout,
            recovery_timeout=args.recovery_timeout,
            keep_artifacts=args.keep_artifacts,
            root_dir=args.root_dir,
        )
    )
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
