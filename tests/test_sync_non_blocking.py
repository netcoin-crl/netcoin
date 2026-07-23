"""POST /sync blocked the calling request until every peer had been
contacted sequentially -- fine for callers that read adopted_chains/info
from the response, but the miner's --sync-after (and any --sync-interval
background caller) doesn't use that result at all. ?wait=0 kicks sync off
in a background thread instead."""

import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen

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


def _post(url: str) -> dict:
    req = Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    import json

    return json.loads(urlopen(req, timeout=10).read())


def test_sync_wait_zero_returns_immediately_and_still_syncs(tmp_path: Path):
    miner = Wallet.create()
    remote_chain = Blockchain(tmp_path / "remote")
    for _ in range(5):
        remote_chain.mine_block(miner.address)
    remote = NetCoinNode(remote_chain, persist=False)

    with served(remote) as s:
        local_chain = Blockchain(tmp_path / "local")
        local = NetCoinNode(local_chain, peers=[s.url], persist=False)
        with served(local) as ls:
            result = _post(f"{ls.url}/sync?wait=0")
            assert result == {"ok": True, "started": True}
            for _ in range(50):
                if local_chain.height() == remote_chain.height():
                    break
                time.sleep(0.1)
    assert local_chain.height() == remote_chain.height()


def test_sync_default_still_blocks_and_returns_full_result(tmp_path: Path):
    miner = Wallet.create()
    remote_chain = Blockchain(tmp_path / "remote")
    for _ in range(5):
        remote_chain.mine_block(miner.address)
    remote = NetCoinNode(remote_chain, persist=False)

    with served(remote) as s:
        local_chain = Blockchain(tmp_path / "local")
        local = NetCoinNode(local_chain, peers=[s.url], persist=False)
        with served(local) as ls:
            result = _post(f"{ls.url}/sync")
            assert result["ok"] is True
            assert result["adopted_chains"] == 1
            assert "info" in result

    assert local_chain.height() == remote_chain.height()
