"""Coin consolidation: sweep many small UTXOs so large sends stop failing."""

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

from netcoin.chain import Blockchain
from netcoin.cli import _maybe_harvest_miner_rewards
from netcoin.node import NetCoinNode, make_handler
from netcoin.wallet import Wallet
from netcoin.webwallet import consolidate_coins, consolidation_status


class served:
    def __init__(self, node: NetCoinNode):
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


def test_consolidate_sweeps_small_coins(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    other = Wallet.create()
    for _ in range(3):
        chain.mine_block(miner.segwit_address)
    for _ in range(100):  # mature the three coinbases
        chain.mine_block(other.segwit_address)

    with served(NetCoinNode(chain, persist=False)) as s:
        result = consolidate_coins(miner, "segwit", s.url, fee_sats=10_000, max_inputs=120)
        assert result["transactions"] == 1
        assert result["batches"][0]["inputs"] == 3
        # The consolidation tx landed in the mempool.
        with urlopen(s.url + "/info", timeout=5) as r:
            info = json.loads(r.read().decode())["node"]
        assert info["mempool_transactions"] == 1

    # Mine it and confirm the wallet now holds a single spendable coin.
    chain.mine_block(other.segwit_address)
    utxos = chain.utxos_for_address(miner.segwit_address)
    assert len(utxos) == 1
    assert utxos[0].output.amount == 3 * 50 * 100_000_000 - 10_000


def test_consolidate_with_nothing_to_do(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    lone = Wallet.create()
    chain.mine_block(lone.segwit_address)
    with served(NetCoinNode(chain, persist=False)) as s:
        result = consolidate_coins(lone, "segwit", s.url)
    assert result["batches"] == []


def test_consolidation_status_reports_one_send_capacity(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    other = Wallet.create()
    for _ in range(3):
        chain.mine_block(miner.segwit_address)
    for _ in range(100):
        chain.mine_block(other.segwit_address)

    with served(NetCoinNode(chain, persist=False)) as s:
        status = consolidation_status(miner, "segwit", s.url, fee_sats=10_000, max_inputs=2)

    assert status["spendable_utxos"] == 3
    assert status["max_sendable_sats"] == 2 * 50 * 100_000_000 - 10_000
    assert status["needs_consolidation"] is True
    assert status["stranded_until_consolidated_sats"] == 50 * 100_000_000


def test_miner_auto_harvest_helper_consolidates_above_threshold(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    other = Wallet.create()
    for _ in range(4):
        chain.mine_block(miner.segwit_address)
    for _ in range(100):
        chain.mine_block(other.segwit_address)

    with served(NetCoinNode(chain, persist=False)) as s:
        harvest = _maybe_harvest_miner_rewards(
            wallet=miner,
            from_type="segwit",
            node=s.url,
            fee_sats=10_000,
            min_utxos=4,
            max_inputs=200,
        )
        with urlopen(s.url + "/info", timeout=5) as r:
            info = json.loads(r.read().decode())["node"]

    assert harvest["ok"] is True
    assert harvest["result"]["transactions"] == 1
    assert harvest["result"]["batches"][0]["inputs"] == 4
    assert info["mempool_transactions"] == 1
