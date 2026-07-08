"""Binary P2P as a node-to-node transport (#5): a node syncs another peer's
chain over the TCP P2P protocol (getheaders -> headers -> getdata -> block),
independently of the HTTP API."""

import threading
from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode
from netcoin.p2p import NetCoinP2PServer
from netcoin.wallet import Wallet


def test_node_syncs_peer_over_binary_p2p(tmp_path: Path):
    source = Blockchain(tmp_path / "src")
    miner = Wallet.create()
    for _ in range(8):
        source.mine_block(miner.address)

    server = NetCoinP2PServer(("127.0.0.1", 0), source)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        follower = NetCoinNode(Blockchain(tmp_path / "dst"), peers=[])
        assert follower.chain.height() == 0
        accepted = follower.sync_over_p2p("127.0.0.1", port)
        assert accepted == 8
        assert follower.chain.height() == source.height()
        assert follower.chain.tip_hash() == source.tip_hash()
    finally:
        server.shutdown()
        server.server_close()


def test_sync_over_p2p_unreachable_is_graceful(tmp_path: Path):
    node = NetCoinNode(Blockchain(tmp_path / "c"), peers=[])
    # nothing listening here -> returns 0, does not raise
    assert node.sync_over_p2p("127.0.0.1", 1) == 0
