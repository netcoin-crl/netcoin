#!/usr/bin/env python3
"""Run a real multi-node NetCoin localnet.

This harness starts independent ``python -m netcoin node`` subprocesses on
localhost, mines and relays through their public HTTP APIs, and tears every
process down at the end. It is intentionally stdlib-only so it can run in CI,
nightly jobs, and reviewer worktrees without extra services.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]

# When run as a script (`python tools/run_localnet.py`), Python puts tools/ on
# sys.path[0], not the repo root, so `import netcoin` fails. Ensure the repo
# root is importable for the in-process wallet/tx helpers.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class LocalnetError(RuntimeError):
    """Raised when the localnet cannot satisfy an invariant."""


@dataclass
class LocalnetNode:
    index: int
    data_dir: Path
    api_port: int
    p2p_port: int
    process: subprocess.Popen[str] | None = None
    stdout: Path | None = None
    stderr: Path | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.api_port}"


@dataclass
class LocalnetConfig:
    nodes: int = 3
    bootstrap_blocks: int = 101
    relay_timeout: float = 20.0
    startup_timeout: float = 20.0
    keep_artifacts: bool = False
    root_dir: Path | None = None
    python: str = sys.executable


@dataclass
class LocalnetReport:
    ok: bool
    nodes: int
    root_dir: str
    duration_seconds: float
    assertions: dict[str, Any] = field(default_factory=dict)
    node_urls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "nodes": self.nodes,
            "root_dir": self.root_dir,
            "duration_seconds": round(self.duration_seconds, 3),
            "node_urls": self.node_urls,
            "assertions": self.assertions,
            "errors": self.errors,
        }


def _json_request(
    method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 10.0
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str, timeout: float = 10.0) -> dict[str, Any]:
    return _json_request("GET", url, timeout=timeout)


def post_json(url: str, payload: dict[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any]:
    return _json_request("POST", url, payload or {}, timeout=timeout)


def _reserve_local_ports(count: int) -> list[int]:
    """Reserve distinct localhost ports until the caller is ready to launch.

    The sockets are held open while all ports are selected, then closed
    immediately before subprocess startup. That keeps the allocation internally
    collision-free and narrows the usual port-0 race window.
    """
    sockets: list[socket.socket] = []
    try:
        ports: list[int] = []
        for _ in range(count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
            ports.append(int(sock.getsockname()[1]))
        if len(set(ports)) != len(ports):
            raise LocalnetError("local port allocator returned duplicates")
        return ports
    finally:
        for sock in sockets:
            sock.close()


def _wait_until(description: str, deadline: float, predicate: Any, interval: float = 0.25) -> Any:
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:
            last_error = exc
        time.sleep(interval)
    suffix = f": {last_error}" if last_error else ""
    raise LocalnetError(f"timed out waiting for {description}{suffix}")


def _readable_process_tail(path: Path | None, limit: int = 2000) -> str:
    if not path or not path.exists():
        return ""
    data = path.read_text(errors="replace")
    return data[-limit:]


class Localnet:
    def __init__(self, config: LocalnetConfig):
        if not 3 <= config.nodes <= 7:
            raise LocalnetError("localnet requires 3 to 7 nodes")
        if config.bootstrap_blocks < 101:
            raise LocalnetError("bootstrap_blocks must be at least 101 so coinbase funds are mature")
        self.config = config
        self._tmp: tempfile.TemporaryDirectory[str] | None = None
        self.root = Path()
        self.nodes: list[LocalnetNode] = []

    def __enter__(self) -> Localnet:
        if self.config.root_dir is None:
            if self.config.keep_artifacts:
                self.root = Path(tempfile.mkdtemp(prefix="netcoin-localnet-"))
            else:
                self._tmp = tempfile.TemporaryDirectory(prefix="netcoin-localnet-")
                self.root = Path(self._tmp.name)
        else:
            self.root = self.config.root_dir
            self.root.mkdir(parents=True, exist_ok=True)
        ports = _reserve_local_ports(self.config.nodes * 2)
        self.nodes = [
            LocalnetNode(
                index=i,
                data_dir=self.root / f"node-{i}",
                api_port=ports[i * 2],
                p2p_port=ports[i * 2 + 1],
            )
            for i in range(self.config.nodes)
        ]
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.stop_all()
        if self._tmp is not None and not self.config.keep_artifacts:
            self._tmp.cleanup()

    def start_all(self, *, topology: str = "mesh", sync_interval: int = 1) -> None:
        for node in self.nodes:
            self.start_node(node, peers=self._peers_for(node, topology), sync_interval=sync_interval)
        deadline = time.time() + self.config.startup_timeout
        for node in self.nodes:
            self.wait_for_health(node, deadline)

    def start_node(self, node: LocalnetNode, *, peers: list[str], sync_interval: int = 1) -> None:
        node.data_dir.mkdir(parents=True, exist_ok=True)
        node.stdout = self.root / f"node-{node.index}.stdout.log"
        node.stderr = self.root / f"node-{node.index}.stderr.log"
        cmd = [
            self.config.python,
            "-m",
            "netcoin",
            "--data",
            str(node.data_dir),
            "node",
            "--host",
            "127.0.0.1",
            "--port",
            str(node.api_port),
            "--p2p-port",
            str(node.p2p_port),
            "--advertise",
            node.url,
            "--sync-interval",
            str(sync_interval),
            "--rate-limit-per-min",
            "0",
        ]
        for peer in peers:
            cmd.extend(["--peer", peer])
        env = os.environ.copy()
        env["NETCOIN_BACKEND"] = "sqlite"
        env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        with node.stdout.open("w", encoding="utf-8") as stdout, node.stderr.open("w", encoding="utf-8") as stderr:
            node.process = subprocess.Popen(
                cmd,
                cwd=str(REPO_ROOT),
                env=env,
                stdout=stdout,
                stderr=stderr,
                text=True,
                start_new_session=True,
            )

    def restart_node(self, index: int, *, topology: str = "mesh", sync_interval: int = 1) -> None:
        node = self.nodes[index]
        self.stop_node(node, hard=True)
        self.start_node(node, peers=self._peers_for(node, topology), sync_interval=sync_interval)
        self.wait_for_health(node, time.time() + self.config.startup_timeout)

    def stop_node(self, node: LocalnetNode, *, hard: bool = False) -> None:
        process = node.process
        if process is None or process.poll() is not None:
            return
        if hard:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                return
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)

    def stop_all(self) -> None:
        for node in reversed(self.nodes):
            self.stop_node(node)

    def assert_no_survivors(self) -> None:
        survivors = [node.index for node in self.nodes if node.process is not None and node.process.poll() is None]
        if survivors:
            raise LocalnetError(f"node processes still running after cleanup: {survivors}")

    def _peers_for(self, node: LocalnetNode, topology: str) -> list[str]:
        if topology == "mesh":
            return [peer.url for peer in self.nodes if peer.index != node.index]
        if topology == "line":
            peers: list[str] = []
            if node.index > 0:
                peers.append(self.nodes[node.index - 1].url)
            if node.index + 1 < len(self.nodes):
                peers.append(self.nodes[node.index + 1].url)
            return peers
        if topology == "none":
            return []
        raise LocalnetError(f"unknown topology: {topology}")

    def wait_for_health(self, node: LocalnetNode, deadline: float) -> dict[str, Any]:
        def probe() -> dict[str, Any] | None:
            if node.process is not None and node.process.poll() is not None:
                tail = _readable_process_tail(node.stderr) or _readable_process_tail(node.stdout)
                raise LocalnetError(f"node {node.index} exited early with {node.process.returncode}: {tail}")
            payload = get_json(f"{node.url}/health", timeout=2)
            return payload if payload.get("ok") else None

        return _wait_until(f"node {node.index} health", deadline, probe)

    def add_peers(self, topology: str = "mesh") -> None:
        for node in self.nodes:
            peers = self._peers_for(node, topology)
            post_json(f"{node.url}/peers", {"peers": peers}, timeout=5)

    def sync_all(self) -> None:
        for node in self.nodes:
            post_json(f"{node.url}/sync", {}, timeout=15)
            post_json(f"{node.url}/relay", {}, timeout=15)

    def mine_block(self, node: LocalnetNode, address: str) -> dict[str, Any]:
        from netcoin.miner import solve_template

        template = get_json(f"{node.url}/blocktemplate?address={address}", timeout=10)
        block = solve_template(template, address)
        return post_json(f"{node.url}/submitblock", block.to_dict(), timeout=15)

    def mine_blocks(self, node: LocalnetNode, address: str, count: int) -> list[dict[str, Any]]:
        mined = []
        for _ in range(count):
            mined.append(self.mine_block(node, address))
        return mined

    def node_info(self, node: LocalnetNode) -> dict[str, Any]:
        return get_json(f"{node.url}/info", timeout=10)["node"]

    def mempool_txids(self, node: LocalnetNode) -> set[str]:
        payload = get_json(f"{node.url}/mempool?transactions=1&limit=500", timeout=10)
        txids = {item["txid"] for item in payload.get("entries", []) if item.get("txid")}
        for item in payload.get("transactions", []):
            txid = item.get("txid") or item.get("id")
            if txid:
                txids.add(txid)
        return txids

    def compact_block(self, node: LocalnetNode, block_hash: str) -> dict[str, Any]:
        return get_json(f"{node.url}/compact-block/{block_hash}", timeout=10)

    def wait_for_convergence(self, *, height: int | None = None, timeout: float | None = None) -> dict[str, Any]:
        deadline = time.time() + (timeout or self.config.relay_timeout)

        def converged() -> dict[str, Any] | None:
            self.sync_all()
            infos = [self.node_info(node) for node in self.nodes]
            tips = {(info["height"], info["tip_hash"]) for info in infos}
            if len(tips) == 1 and (height is None or infos[0]["height"] >= height):
                return {"infos": infos, "tip": infos[0]["tip_hash"], "height": infos[0]["height"]}
            return None

        return _wait_until("all nodes to converge", deadline, converged, interval=0.5)

    def wait_for_mempool_tx(self, txid: str, *, timeout: float | None = None) -> None:
        deadline = time.time() + (timeout or self.config.relay_timeout)

        def relayed() -> bool:
            self.sync_all()
            return all(txid in self.mempool_txids(node) for node in self.nodes)

        _wait_until(f"transaction {txid} relay", deadline, relayed, interval=0.5)

    def wait_for_pex(self, *, timeout: float | None = None) -> dict[str, Any]:
        deadline = time.time() + (timeout or self.config.relay_timeout)

        def learned() -> dict[str, Any] | None:
            for node in self.nodes:
                post_json(f"{node.url}/sync", {}, timeout=10)
            peers = {node.index: get_json(f"{node.url}/peers", timeout=5).get("peers", []) for node in self.nodes}
            if self.nodes[-1].url in peers.get(0, []) and self.nodes[0].url in peers.get(self.nodes[-1].index, []):
                return peers
            return None

        return _wait_until("PEX propagation across line topology", deadline, learned, interval=0.5)


def _make_transaction_from_node_data(data_dir: Path, sender: Any, receiver: Any) -> Any:
    from netcoin.chain import Blockchain
    from netcoin.tx import amount_to_sats

    chain = Blockchain(data_dir)
    tx = sender.create_transaction(
        chain,
        receiver.address,
        amount_to_sats("1"),
        amount_to_sats("0.01"),
        strategy="smallest-first",
    )
    return tx


def run_localnet(config: LocalnetConfig) -> dict[str, Any]:
    from netcoin.wallet import Wallet

    started = time.time()
    assertions: dict[str, Any] = {}
    errors: list[str] = []
    root = ""

    try:
        with Localnet(config) as localnet:
            root = str(localnet.root)
            miner = Wallet.create()
            receiver = Wallet.create()

            localnet.start_all(topology="line", sync_interval=1)
            assertions["started"] = {"nodes": config.nodes, "urls": [node.url for node in localnet.nodes]}

            pex_peers = localnet.wait_for_pex()
            assertions["pex_propagation"] = {
                "node0_peers": pex_peers[0],
                f"node{config.nodes - 1}_peers": pex_peers[config.nodes - 1],
            }

            mined = localnet.mine_blocks(localnet.nodes[0], miner.address, config.bootstrap_blocks)
            convergence = localnet.wait_for_convergence(height=config.bootstrap_blocks)
            assertions["header_sync"] = {
                "height": convergence["height"],
                "tip_hash": convergence["tip"],
            }
            assertions["block_relay_latency_seconds"] = round(time.time() - started, 3)

            tx = _make_transaction_from_node_data(localnet.nodes[0].data_dir, miner, receiver)
            txid = tx.txid()
            post_json(f"{localnet.nodes[0].url}/tx", tx.to_dict(include_scripts=True, include_witness=True), timeout=15)
            localnet.wait_for_mempool_tx(txid)
            assertions["tx_relay"] = {"txid": txid, "nodes_with_tx": config.nodes}

            localnet.mine_block(localnet.nodes[0], miner.address)
            mined_tip = localnet.wait_for_convergence(height=config.bootstrap_blocks + 1)
            compact = localnet.compact_block(localnet.nodes[-1], mined_tip["tip"])
            missing = get_json(f"{localnet.nodes[-1].url}/compact-block-missing/{mined_tip['tip']}?have=", timeout=10)
            assertions["compact_block_reconstruction"] = {
                "block_hash": compact.get("block_hash") or compact.get("header", {}).get("hash"),
                "shortids": len(compact.get("shortids", [])),
                "missing": len(missing.get("missing", [])),
            }

            localnet.restart_node(1, topology="line", sync_interval=1)
            replay = localnet.wait_for_convergence(height=config.bootstrap_blocks + 1)
            assertions["restart_replay"] = {"height": replay["height"], "tip_hash": replay["tip"]}

            localnet.stop_all()
            localnet.assert_no_survivors()
            assertions["cleanup"] = {"node_processes_stopped": True}

        reorg = run_reorg_scenario(config)
        assertions["reorg_resolution"] = reorg
    except Exception as exc:
        errors.append(str(exc))

    return LocalnetReport(
        ok=not errors,
        nodes=config.nodes,
        root_dir=root,
        duration_seconds=time.time() - started,
        node_urls=assertions.get("started", {}).get("urls", []),
        assertions=assertions,
        errors=errors,
    ).to_dict()


def run_reorg_scenario(config: LocalnetConfig) -> dict[str, Any]:
    from netcoin.wallet import Wallet

    reorg_config = LocalnetConfig(
        nodes=3,
        bootstrap_blocks=101,
        relay_timeout=config.relay_timeout,
        startup_timeout=config.startup_timeout,
        keep_artifacts=config.keep_artifacts,
        root_dir=(config.root_dir / "reorg" if config.root_dir else None),
        python=config.python,
    )
    with Localnet(reorg_config) as localnet:
        miner_a = Wallet.create()
        miner_b = Wallet.create()
        localnet.start_all(topology="none", sync_interval=0)
        localnet.mine_block(localnet.nodes[0], miner_a.address)
        localnet.mine_blocks(localnet.nodes[1], miner_b.address, 2)
        a_before = localnet.node_info(localnet.nodes[0])
        b_before = localnet.node_info(localnet.nodes[1])
        localnet.add_peers("mesh")
        adopted = localnet.wait_for_convergence(height=2)
        localnet.stop_all()
        localnet.assert_no_survivors()
        return {
            "node0_before": {"height": a_before["height"], "tip_hash": a_before["tip_hash"]},
            "node1_before": {"height": b_before["height"], "tip_hash": b_before["tip_hash"]},
            "converged_height": adopted["height"],
            "converged_tip": adopted["tip"],
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a real multi-node NetCoin localnet harness")
    parser.add_argument("--nodes", type=int, default=3, help="number of nodes to spawn (3-7)")
    parser.add_argument("--bootstrap-blocks", type=int, default=101, help="mature funding blocks to mine on node 0")
    parser.add_argument("--relay-timeout", type=float, default=20.0, help="seconds to wait for relay/convergence")
    parser.add_argument("--startup-timeout", type=float, default=20.0, help="seconds to wait for node startup")
    parser.add_argument("--root-dir", type=Path, help="artifact/data root; defaults to a temp directory")
    parser.add_argument("--keep-artifacts", action="store_true", help="do not delete temporary node data/logs")
    parser.add_argument("--json", action="store_true", help="print only the JSON report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_localnet(
        LocalnetConfig(
            nodes=args.nodes,
            bootstrap_blocks=args.bootstrap_blocks,
            relay_timeout=args.relay_timeout,
            startup_timeout=args.startup_timeout,
            keep_artifacts=args.keep_artifacts,
            root_dir=args.root_dir,
        )
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
