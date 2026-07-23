"""A node joining (or reconnecting to) a peer must pull that peer's existing
mempool contents -- gossip only relays a transaction at the moment it's
broadcast, so without a backfill step a newly-connected node's mempool
silently diverges and it can mine empty blocks forever while real pending
transactions sit unconfirmed on every peer that was already up."""

from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from netcoin.chain import Blockchain
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


def test_sync_all_pulls_peer_mempool_contents(tmp_path: Path):
    miner = Wallet.create()
    recipient = Wallet.create()
    remote_chain = Blockchain(tmp_path / "remote")
    for _ in range(100):
        remote_chain.mine_block(miner.address)
    tx = miner.create_transaction(remote_chain, recipient.address, 1_000_000, 10_000)
    remote_chain.add_mempool_transaction(tx)
    remote = NetCoinNode(remote_chain, persist=False)

    with served(remote) as s:
        local_chain = Blockchain(tmp_path / "local")
        local = NetCoinNode(local_chain, peers=[s.url], persist=False)
        local.sync_all()

    assert local_chain.height() == remote_chain.height()
    assert tx.txid() in {t.txid() for t in local_chain.mempool}


def test_sync_mempool_from_peer_does_not_duplicate_already_known_transactions(tmp_path: Path):
    miner = Wallet.create()
    recipient = Wallet.create()
    remote_chain = Blockchain(tmp_path / "remote")
    for _ in range(100):
        remote_chain.mine_block(miner.address)
    tx = miner.create_transaction(remote_chain, recipient.address, 1_000_000, 10_000)
    remote_chain.add_mempool_transaction(tx)
    remote = NetCoinNode(remote_chain, persist=False)

    with served(remote) as s:
        local_chain = Blockchain(tmp_path / "local")
        local = NetCoinNode(local_chain, peers=[s.url], persist=False)
        local.sync_all()
        # add_mempool_transaction is itself idempotent for a duplicate txid,
        # so re-syncing must not create a second copy in the mempool.
        local.sync_mempool_from_peer(s.url)

    matching = [t for t in local_chain.mempool if t.txid() == tx.txid()]
    assert len(matching) == 1
