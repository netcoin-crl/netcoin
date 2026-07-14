#!/usr/bin/env python3
"""Run source-level NetCoin performance benchmarks.

The benchmark is intentionally deterministic and local: it builds a short chain,
replays those blocks into a fresh chain to time block validation, times restart
replay from disk, samples process memory, and measures mempool admission
throughput. It writes JSON suitable for CI regression gates.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.chain import Blockchain  # noqa: E402
from netcoin.tx import amount_to_sats  # noqa: E402
from netcoin.wallet import Wallet  # noqa: E402


DEFAULT_THRESHOLDS = {
    "block_validation_p50_ms_max": 250.0,
    "block_validation_p99_ms_max": 1000.0,
    "restart_replay_ms_max": 2000.0,
    "memory_rss_mb_max": 300.0,
    "mempool_accept_tps_min": 3.0,
}


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def max_rss_mb() -> float:
    rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return rss / (1024 * 1024)
    return rss / 1024


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_source_chain(root: Path, *, blocks: int) -> tuple[Blockchain, Wallet]:
    chain = Blockchain(root / "source-chain")
    miner = Wallet.create()
    for _ in range(blocks):
        chain.mine_block(miner.address)
    return chain, miner


def benchmark_block_validation(source: Blockchain, root: Path) -> dict[str, Any]:
    target = Blockchain(root / "validation-chain")
    latencies: list[float] = []
    for block in source.chain[1:]:
        started = time.perf_counter()
        target.add_block(block)
        latencies.append((time.perf_counter() - started) * 1000.0)
    return {
        "count": len(latencies),
        "p50_ms": round(percentile(latencies, 50), 3),
        "p99_ms": round(percentile(latencies, 99), 3),
        "max_ms": round(max(latencies) if latencies else 0.0, 3),
        "mean_ms": round(statistics.fmean(latencies) if latencies else 0.0, 3),
    }


def benchmark_restart_replay(source_dir: Path, expected_height: int) -> dict[str, Any]:
    started = time.perf_counter()
    restarted = Blockchain(source_dir)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "elapsed_ms": round(elapsed_ms, 3),
        "height": restarted.height(),
        "expected_height": expected_height,
        "ok": restarted.height() == expected_height,
    }


def benchmark_mempool_accept(chain: Blockchain, miner: Wallet, *, transactions: int) -> dict[str, Any]:
    receivers = [Wallet.create() for _ in range(transactions)]
    accepted = 0
    started = time.perf_counter()
    for receiver in receivers:
        tx = miner.create_transaction(
            chain,
            receiver.address,
            amount_to_sats("0.1"),
            amount_to_sats("0.01"),
            strategy="smallest-first",
        )
        chain.add_mempool_transaction(tx, save=False)
        accepted += 1
    elapsed = time.perf_counter() - started
    return {
        "accepted": accepted,
        "elapsed_ms": round(elapsed * 1000.0, 3),
        "transactions_per_second": round(accepted / max(elapsed, 0.000001), 3),
    }


def evaluate_thresholds(metrics: dict[str, Any], thresholds: dict[str, float]) -> list[str]:
    failures: list[str] = []
    block = metrics["block_validation"]
    restart = metrics["restart_replay"]
    memory = metrics["memory"]
    mempool = metrics["mempool_accept"]
    checks = [
        (block["p50_ms"] <= thresholds["block_validation_p50_ms_max"], "block_validation_p50_ms"),
        (block["p99_ms"] <= thresholds["block_validation_p99_ms_max"], "block_validation_p99_ms"),
        (restart["elapsed_ms"] <= thresholds["restart_replay_ms_max"], "restart_replay_ms"),
        (memory["max_rss_mb"] <= thresholds["memory_rss_mb_max"], "memory_rss_mb"),
        (mempool["transactions_per_second"] >= thresholds["mempool_accept_tps_min"], "mempool_accept_tps"),
        (restart["ok"], "restart_replay_height"),
    ]
    for ok, label in checks:
        if not ok:
            failures.append(label)
    return failures


def run_benchmark(
    *,
    blocks: int,
    bootstrap_blocks: int,
    mempool_transactions: int,
    thresholds: dict[str, float],
    root_dir: Path | None = None,
    keep_artifacts: bool = False,
) -> dict[str, Any]:
    if blocks <= 0:
        raise ValueError("blocks must be positive")
    if bootstrap_blocks < 101:
        raise ValueError("bootstrap_blocks must be at least 101 for mature coinbase spends")
    if mempool_transactions <= 0:
        raise ValueError("mempool_transactions must be positive")

    temp: tempfile.TemporaryDirectory[str] | None = None
    if root_dir is None:
        if keep_artifacts:
            root = Path(tempfile.mkdtemp(prefix="netcoin-perf-"))
        else:
            temp = tempfile.TemporaryDirectory(prefix="netcoin-perf-")
            root = Path(temp.name)
    else:
        root = root_dir
        root.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    try:
        source, miner = build_source_chain(root, blocks=blocks)
        block_validation = benchmark_block_validation(source, root)
        restart_replay = benchmark_restart_replay(source.data_dir, source.height())
        effective_bootstrap_blocks = max(bootstrap_blocks, 100 + mempool_transactions)
        mempool_chain, mempool_miner = build_source_chain(root / "mempool", blocks=effective_bootstrap_blocks)
        mempool_accept = benchmark_mempool_accept(
            mempool_chain,
            mempool_miner,
            transactions=mempool_transactions,
        )
        metrics = {
            "block_validation": block_validation,
            "restart_replay": restart_replay,
            "memory": {"max_rss_mb": round(max_rss_mb(), 3)},
            "mempool_accept": mempool_accept,
        }
        threshold_failures = evaluate_thresholds(metrics, thresholds)
        return {
            "ok": not threshold_failures,
            "schema": "netcoin-perf-benchmark-v1",
            "duration_seconds": round(time.perf_counter() - started, 3),
            "root_dir": display_path(root),
            "parameters": {
                "blocks": blocks,
                "bootstrap_blocks": bootstrap_blocks,
                "effective_bootstrap_blocks": effective_bootstrap_blocks,
                "mempool_transactions": mempool_transactions,
            },
            "thresholds": thresholds,
            "metrics": metrics,
            "threshold_failures": threshold_failures,
            "does_not_claim": [
                "public seed performance",
                "hardware-isolated benchmark",
                "mainnet capacity certification",
            ],
        }
    finally:
        if temp is not None and not keep_artifacts:
            temp.cleanup()


def parse_thresholds(path: Path | None) -> dict[str, float]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    if path is not None:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        for key, value in loaded.items():
            if key in thresholds:
                thresholds[key] = float(value)
    return thresholds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run NetCoin source performance benchmarks")
    parser.add_argument("--blocks", type=int, default=12, help="blocks to validate into a fresh chain")
    parser.add_argument("--bootstrap-blocks", type=int, default=101, help="blocks for mature mempool spend UTXOs")
    parser.add_argument("--mempool-transactions", type=int, default=12, help="transactions to admit into mempool")
    parser.add_argument("--thresholds", type=Path, help="optional JSON threshold override")
    parser.add_argument("--root-dir", type=Path)
    parser.add_argument("--keep-artifacts", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("reports/perf/perf_benchmark_report.json"))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    report = run_benchmark(
        blocks=args.blocks,
        bootstrap_blocks=args.bootstrap_blocks,
        mempool_transactions=args.mempool_transactions,
        thresholds=parse_thresholds(args.thresholds),
        root_dir=args.root_dir,
        keep_artifacts=args.keep_artifacts,
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
