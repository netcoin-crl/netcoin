#!/usr/bin/env python3
"""Run a localnet-only versionbits rehearsal."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.miner import solve_template  # noqa: E402
from netcoin.versionbits import (  # noqa: E402
    ACTIVE,
    ENV_ENABLE_REHEARSAL,
    VersionBitsRehearsalConfig,
    evaluate_rehearsal_chain,
    extract_block_versions,
    load_rehearsal_config,
)
from netcoin.wallet import Wallet  # noqa: E402
from tools.run_localnet import Localnet, LocalnetConfig, get_json, post_json  # noqa: E402


def mine_signaling_block(localnet: Localnet, node_index: int, address: str, bit: int) -> dict[str, Any]:
    node = localnet.nodes[node_index]
    template = get_json(f"{node.url}/blocktemplate?address={address}", timeout=10)
    template["version"] = int(template.get("version", 1)) | (1 << bit)
    block = solve_template(template, address)
    post_json(f"{node.url}/submitblock", block.to_dict(), timeout=15)
    return block.to_dict()


def run_localnet_rehearsal(
    config: VersionBitsRehearsalConfig,
    *,
    root_dir: Path | None = None,
    keep_artifacts: bool = False,
    startup_timeout: float = 20.0,
    relay_timeout: float = 20.0,
) -> dict[str, Any]:
    config.require_safe()
    if not config.enabled:
        raise ValueError(f"{ENV_ENABLE_REHEARSAL} must be enabled or config.enabled must be true")
    if config.network not in {"regtest", "testnet-rehearsal", "testnet"}:
        raise ValueError("versionbits rehearsal is localnet/testnet only")

    temp: tempfile.TemporaryDirectory[str] | None = None
    if root_dir is None:
        if keep_artifacts:
            root = Path(tempfile.mkdtemp(prefix="netcoin-versionbits-"))
        else:
            temp = tempfile.TemporaryDirectory(prefix="netcoin-versionbits-")
            root = Path(temp.name)
    else:
        root = root_dir

    started = time.time()
    try:
        with Localnet(
            LocalnetConfig(
                nodes=3,
                bootstrap_blocks=101,
                relay_timeout=relay_timeout,
                startup_timeout=startup_timeout,
                keep_artifacts=keep_artifacts,
                root_dir=root,
            )
        ) as localnet:
            miner = Wallet.create()
            localnet.start_all(topology="line", sync_interval=1)
            target_blocks = config.deployment.period * 3
            mined_blocks = [
                mine_signaling_block(localnet, 0, miner.address, config.deployment.bit) for _ in range(target_blocks)
            ]
            convergence = localnet.wait_for_convergence(height=target_blocks, timeout=relay_timeout)
            versions = extract_block_versions(mined_blocks)
            evaluation = evaluate_rehearsal_chain(config, versions)
            localnet.stop_all()
            localnet.assert_no_survivors()
    finally:
        if temp is not None and not keep_artifacts:
            temp.cleanup()

    return {
        "ok": bool(evaluation["ok"]) and evaluation["final_state"] == ACTIVE,
        "schema": "netcoin-versionbits-localnet-rehearsal-v1",
        "duration_seconds": round(time.time() - started, 3),
        "root_dir": str(root),
        "node_count": 3,
        "mined_versions": versions,
        "convergence": convergence,
        "evaluation": evaluation,
        "does_not_claim": [
            "mainnet activation",
            "mainnet versionbits wiring",
            "public testnet activation without operator signoff",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NetCoin versionbits localnet rehearsal")
    parser.add_argument("--config", type=Path, default=Path("config/versionbits_rehearsal.example.json"))
    parser.add_argument("--root-dir", type=Path)
    parser.add_argument("--keep-artifacts", action="store_true")
    parser.add_argument("--startup-timeout", type=float, default=20.0)
    parser.add_argument("--relay-timeout", type=float, default=20.0)
    parser.add_argument("--out", type=Path, default=Path("reports/versionbits_rehearsal_report.json"))
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    env = dict(os.environ)
    env.setdefault(ENV_ENABLE_REHEARSAL, "1")
    config = load_rehearsal_config(args.config, env=env)
    report = run_localnet_rehearsal(
        config,
        root_dir=args.root_dir,
        keep_artifacts=args.keep_artifacts,
        startup_timeout=args.startup_timeout,
        relay_timeout=args.relay_timeout,
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
