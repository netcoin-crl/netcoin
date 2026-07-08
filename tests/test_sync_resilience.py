"""Peer-sync resilience: unreachable peers, restart persistence, catch-up after
downtime, peer loss mid-sync, and delayed (out-of-order) block delivery."""

import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from netcoin.block import Block
from netcoin.chain import Blockchain
from netcoin.miner import solve_template
from netcoin.node import NetCoinNode, make_handler
from netcoin.wallet import Wallet


class served:
    def __init__(self, node: NetCoinNode):
        self.node = node
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(node))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def test_sync_from_unreachable_peer_is_safe(tmp_path: Path):
    chain = Blockchain(tmp_path / "a")
    # Port 1 is not listening; sync must fail gracefully, not raise.
    node = NetCoinNode(chain, peers=["http://127.0.0.1:1"], persist=False)
    assert node.sync_all() == 0
    assert chain.height() == 0


def test_node_reloads_chain_and_peers_after_restart(tmp_path: Path):
    miner = Wallet.create()
    chain = Blockchain(tmp_path / "node")
    node = NetCoinNode(chain, peers=["http://seed1.example:28444"])
    for _ in range(3):
        chain.mine_block(miner.address)
    tip = chain.tip_hash()

    # Simulate a restart: fresh Blockchain + NetCoinNode on the same data dir.
    rechain = Blockchain(tmp_path / "node")
    renode = NetCoinNode(rechain)
    assert rechain.height() == 3
    assert rechain.tip_hash() == tip
    assert "http://seed1.example:28444" in renode.peers


def test_sync_after_downtime_catches_up(tmp_path: Path):
    miner = Wallet.create()
    remote_chain = Blockchain(tmp_path / "remote")
    for _ in range(6):
        remote_chain.mine_block(miner.address)
    remote = NetCoinNode(remote_chain, persist=False)

    with served(remote) as s:
        # Local node was "down" and is now far behind.
        local_chain = Blockchain(tmp_path / "local")
        local = NetCoinNode(local_chain, peers=[s.url], persist=False)
        adopted = local.sync_all()

    assert adopted == 1
    assert local_chain.height() == 6
    assert local_chain.tip_hash() == remote_chain.tip_hash()


def test_sync_continues_when_one_peer_is_down(tmp_path: Path):
    miner = Wallet.create()
    good_chain = Blockchain(tmp_path / "good")
    for _ in range(4):
        good_chain.mine_block(miner.address)
    good = NetCoinNode(good_chain, persist=False)

    with served(good) as s:
        local_chain = Blockchain(tmp_path / "local")
        # One dead peer, one good peer with a longer chain.
        local = NetCoinNode(local_chain, peers=["http://127.0.0.1:1", s.url], persist=False)
        adopted = local.sync_all()

    assert adopted == 1
    assert local_chain.height() == 4
    assert local_chain.tip_hash() == good_chain.tip_hash()


def test_delayed_block_then_parent_connects(tmp_path: Path):
    miner = Wallet.create()
    # Source builds blocks 1, 2, 3 on top of a shared height-1 prefix.
    base = Blockchain(tmp_path / "base")
    base.mine_block(miner.address)  # height 1

    source = Blockchain(tmp_path / "source")
    source.add_block(base.chain[1])  # share block 1
    source.mine_block(miner.address)  # block 2
    source.mine_block(miner.address)  # block 3
    block2, block3 = source.chain[2], source.chain[3]

    target_chain = Blockchain(tmp_path / "target")
    target_chain.add_block(base.chain[1])  # height 1
    node = NetCoinNode(target_chain, persist=False)

    # Block 3 arrives before its parent: held as a node orphan, no progress.
    try:
        node.accept_block(block3)
    except Exception:
        pass
    assert target_chain.height() == 1

    # Parent (block 2) arrives: it connects, and the delayed block 3 connects too.
    node.accept_block(block2)
    assert target_chain.height() == 3
    assert target_chain.tip_hash() == source.tip_hash()


def test_invalid_rejected_block_is_not_held_as_node_orphan(tmp_path: Path):
    miner = Wallet.create()
    chain = Blockchain(tmp_path / "chain")
    node = NetCoinNode(chain, persist=False)
    block = solve_template(chain.get_block_template(miner_address=miner.address), miner.address)
    bad = Block(block.header, [chain.tip().transactions[0]])  # valid PoW header, bad merkle/contents

    try:
        node.accept_block(bad)
    except Exception:
        pass

    assert len(node.orphans) == 0


def test_node_orphan_queue_is_capped(tmp_path: Path):
    miner = Wallet.create()
    source = Blockchain(tmp_path / "source")
    for _ in range(5):
        source.mine_block(miner.address)

    target = Blockchain(tmp_path / "target")
    node = NetCoinNode(target, persist=False)
    node.max_node_orphans = 2

    for block in source.chain[2:5]:
        try:
            node.accept_block(block)
        except Exception:
            pass

    assert len(node.orphans) == 2


def test_background_sync_loop_catches_up(tmp_path: Path):
    miner = Wallet.create()
    remote_chain = Blockchain(tmp_path / "remote")
    for _ in range(2):
        remote_chain.mine_block(miner.address)
    remote = NetCoinNode(remote_chain, persist=False)

    with served(remote) as s:
        local_chain = Blockchain(tmp_path / "local")
        local = NetCoinNode(local_chain, peers=[s.url], persist=False)
        stop, thread = local.start_background_sync(1)
        try:
            deadline = time.time() + 5
            while time.time() < deadline and local_chain.height() < 2:
                time.sleep(0.1)
        finally:
            stop.set()
            thread.join(timeout=5)

    assert local_chain.height() == 2
    assert local_chain.tip_hash() == remote_chain.tip_hash()
