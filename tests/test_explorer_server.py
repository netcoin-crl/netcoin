"""API-backed explorer service."""
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

from netcoin.chain import Blockchain
from netcoin.explorer_server import make_handler
from netcoin.wallet import Wallet


class served:
    def __init__(self, chain: Blockchain, rate_limit_per_min: int = 240):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(chain, rate_limit_per_min=rate_limit_per_min))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def get_json(url: str):
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def get_text(url: str):
    with urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def test_explorer_latest_and_home(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(2):
        chain.mine_block(miner.address)
    with served(chain) as s:
        latest = get_json(f"{s.url}/api/latest?n=1")
        home = get_text(f"{s.url}/")
    assert latest["height"] == 2
    assert len(latest["blocks"]) == 1
    assert "NetCoin Explorer" in home
    assert chain.tip_hash() in home


def test_explorer_block_tx_address_and_search(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    block = chain.tip()
    txid = block.transactions[0].txid()
    with served(chain) as s:
        block_json = get_json(f"{s.url}/api/block/{block.hash()}")
        tx_json = get_json(f"{s.url}/api/tx/{txid}")
        address_json = get_json(f"{s.url}/api/address/{miner.address}")
        search_json = get_json(f"{s.url}/api/search?q={miner.address}")
        block_page = get_text(f"{s.url}/block/{block.hash()}")
        tx_page = get_text(f"{s.url}/tx/{txid}")
        address_page = get_text(f"{s.url}/address/{miner.address}")
    assert block_json["hash"] == block.hash()
    assert tx_json["txid"] == txid
    assert address_json["address"] == miner.address
    assert search_json["matches"][0]["type"] == "address"
    assert txid in block_page
    assert "Transaction" in tx_page
    assert miner.address in address_page


def test_explorer_404s_unknown_transaction(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    with served(chain) as s:
        try:
            get_json(f"{s.url}/api/tx/{'0' * 64}")
            assert False, "expected 404"
        except HTTPError as exc:
            assert exc.code == 404


def test_explorer_rate_limits_by_path(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    with served(chain, rate_limit_per_min=2) as s:
        codes = []
        for _ in range(3):
            try:
                get_json(f"{s.url}/api/latest")
                codes.append(200)
            except HTTPError as exc:
                codes.append(exc.code)
    assert codes == [200, 200, 429]
