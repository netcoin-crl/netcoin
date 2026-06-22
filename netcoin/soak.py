"""Local multi-node soak/stress harness for NetCoin.

The harness is intentionally stdlib-only and runs nodes in-process behind their
real HTTP handlers. It is not a substitute for a days-long public testnet soak,
but it gives developers a repeatable way to exercise relay, mining, mempool, and
sync convergence before deploying a build.
"""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, Dict, List

from .chain import Blockchain
from .node import NetCoinNode, make_handler
from .tx import amount_to_sats
from .wallet import Wallet


class SoakError(RuntimeError):
    """Raised when a soak run cannot complete safely."""


@dataclass
class SoakConfig:
    nodes: int = 3
    rounds: int = 3
    transactions_per_round: int = 1
    bootstrap_blocks: int = 101
    amount: str = "1"
    fee: str = "0.01"


class ServedNode:
    def __init__(self, node: NetCoinNode):
        self.node = node
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(node))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.url = ""

    def start(self) -> None:
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _validate_config(config: SoakConfig) -> None:
    if config.nodes < 2:
        raise SoakError("soak requires at least two nodes")
    if config.rounds < 0:
        raise SoakError("rounds must be non-negative")
    if config.transactions_per_round < 0:
        raise SoakError("transactions per round must be non-negative")
    if config.bootstrap_blocks < 101:
        raise SoakError("bootstrap blocks must be at least 101 so coinbase funds are mature")
    amount_to_sats(config.amount)
    amount_to_sats(config.fee)


def _all_tips(chains: List[Blockchain]) -> List[Dict[str, Any]]:
    return [{"height": chain.height(), "tip_hash": chain.tip_hash()} for chain in chains]


def _tips_converged(chains: List[Blockchain]) -> bool:
    tips = {(chain.height(), chain.tip_hash()) for chain in chains}
    return len(tips) == 1


def run_soak(config: SoakConfig, base_dir: str | Path | None = None) -> Dict[str, Any]:
    """Run a bounded local multi-node stress/soak scenario.

    The scenario:
    1. start N HTTP nodes
    2. fully connect them as peers
    3. mine mature bootstrap funds on node 0
    4. sync every other node from node 0
    5. repeatedly relay transactions, mine blocks, relay blocks, and sync all
    6. assert every node converged to the same tip
    """
    _validate_config(config)
    started = time.time()
    owns_tmp = base_dir is None
    tmp = tempfile.TemporaryDirectory(prefix="netcoin-soak-") if owns_tmp else None
    root = Path(tmp.name if tmp else str(base_dir))
    root.mkdir(parents=True, exist_ok=True)

    chains = [Blockchain(root / f"node-{i}") for i in range(config.nodes)]
    nodes = [NetCoinNode(chain, persist=False, rate_limit_per_min=0, request_retries=0) for chain in chains]
    servers = [ServedNode(node) for node in nodes]
    miner = Wallet.create()

    errors: List[Dict[str, Any]] = []
    txs_created = 0
    blocks_mined = 0
    tx_relays = 0
    block_relays = 0
    sync_adoptions = 0

    try:
        for server in servers:
            server.start()
        urls = [server.url for server in servers]
        for i, node in enumerate(nodes):
            for j, url in enumerate(urls):
                if i != j:
                    node.add_peer(url)

        for _ in range(config.bootstrap_blocks):
            chains[0].mine_block(miner.address)
            blocks_mined += 1
        for node in nodes[1:]:
            if node.sync_from_peer(urls[0]):
                sync_adoptions += 1

        if not _tips_converged(chains):
            raise SoakError("nodes did not converge after bootstrap sync")

        for round_index in range(config.rounds):
            source_index = round_index % config.nodes
            source_chain = chains[source_index]
            source_node = nodes[source_index]
            for _ in range(config.transactions_per_round):
                receiver = Wallet.create()
                tx = miner.create_transaction(
                    source_chain,
                    receiver.address,
                    amount_to_sats(config.amount),
                    amount_to_sats(config.fee),
                    strategy="smallest-first",
                )
                source_chain.add_mempool_transaction(tx)
                txs_created += 1
                tx_relays += source_node.broadcast_transaction(tx)

            block = source_chain.mine_block(miner.address)
            blocks_mined += 1
            block_relays += source_node.broadcast_block(block, force=True)

            for node in nodes:
                try:
                    sync_adoptions += node.sync_all()
                except Exception as exc:  # keep the report useful for long soaks
                    errors.append({"round": round_index, "error": str(exc)})

            if not _tips_converged(chains):
                for node in nodes:
                    try:
                        sync_adoptions += node.sync_all()
                    except Exception as exc:
                        errors.append({"round": round_index, "retry_error": str(exc)})
            if not _tips_converged(chains):
                raise SoakError(f"nodes diverged after round {round_index}")

        relay_queues = [len(node._relay_queue) for node in nodes]
        report = {
            "ok": not errors and _tips_converged(chains),
            "nodes": config.nodes,
            "rounds": config.rounds,
            "transactions_per_round": config.transactions_per_round,
            "transactions_created": txs_created,
            "blocks_mined": blocks_mined,
            "tx_relays": tx_relays,
            "block_relays": block_relays,
            "sync_adoptions": sync_adoptions,
            "relay_queues": relay_queues,
            "tips": _all_tips(chains),
            "duration_seconds": round(time.time() - started, 3),
            "errors": errors,
        }
        if not report["ok"]:
            raise SoakError(f"soak completed with errors: {errors}")
        return report
    finally:
        for server in servers:
            server.close()
        if tmp is not None:
            tmp.cleanup()
