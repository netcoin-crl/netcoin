"""Explorer-style node JSON API: /tx/<txid>, /latest, /utxos, and 404s."""
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode, make_handler
from netcoin.wallet import Wallet


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


def get(url):
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_tx_endpoint_returns_confirmed_transaction(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    coinbase_txid = chain.tip().transactions[0].txid()

    with served(NetCoinNode(chain, persist=False)) as s:
        data = get(f"{s.url}/tx/{coinbase_txid}")
    assert data["txid"] == coinbase_txid
    assert data["confirmed"] is True
    assert data["block_height"] == 1
    assert data["block_hash"] == chain.tip_hash()


def test_tx_endpoint_404_for_unknown(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    with served(NetCoinNode(chain, persist=False)) as s:
        try:
            get(f"{s.url}/tx/{'0' * 64}")
            assert False, "expected 404"
        except HTTPError as exc:
            assert exc.code == 404


def test_latest_endpoint_lists_recent_blocks(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(5):
        chain.mine_block(miner.address)

    with served(NetCoinNode(chain, persist=False)) as s:
        data = get(f"{s.url}/latest?n=3")
    assert data["height"] == 5
    assert data["tip_hash"] == chain.tip_hash()
    assert [b["height"] for b in data["blocks"]] == [5, 4, 3]  # newest first


def test_latest_endpoint_clamps_n(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(3):
        chain.mine_block(miner.address)

    with served(NetCoinNode(chain, persist=False)) as s:
        data = get(f"{s.url}/latest?n=100000")
    # Only 4 blocks exist (genesis + 3); the cap does not invent blocks.
    assert len(data["blocks"]) == 4


def test_chain_endpoint_is_paginated_by_default(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(5):
        chain.mine_block(miner.address)

    with served(NetCoinNode(chain, persist=False)) as s:
        first = get(f"{s.url}/chain?limit=2")
        second = get(f"{s.url}/chain?start={first['next_start']}&limit=2")

    assert first["height"] == 5
    assert len(first["blocks"]) == 2
    assert first["start"] == 0
    assert first["has_next"] is True
    assert second["start"] == 2
    assert len(second["blocks"]) == 2


def test_balance_summary_reports_maturity_countdown(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.segwit_address)

    with served(NetCoinNode(chain, persist=False)) as s:
        data = get(f"{s.url}/balance/{miner.segwit_address}")
    # One immature coinbase mined at height 1, spend height 2: 99 blocks left.
    assert data["immature_sats"] > 0
    assert data["immature_next_mature_in_blocks"] == 99
    assert data["immature_all_mature_in_blocks"] == 99

    for _ in range(99):
        chain.mine_block(Wallet.create().segwit_address)
    summary = chain.address_balance_summary(miner.segwit_address)
    assert summary["immature_sats"] == 0
    assert summary["immature_next_mature_in_blocks"] == 0
    assert summary["immature_all_mature_in_blocks"] == 0


def test_utxos_endpoint_for_address(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)

    with served(NetCoinNode(chain, persist=False)) as s:
        data = get(f"{s.url}/utxos?address={miner.address}")
    assert data["address"] == miner.address
    # Coinbase is immature at height 1, so utxos_for_address returns none yet.
    assert isinstance(data["utxos"], list)


def test_utxos_endpoint_excludes_mempool_spent_outputs(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(102):
        chain.mine_block(miner.segwit_address)

    spendable = chain.utxos_for_address(miner.segwit_address)[0]
    dest = Wallet.create()
    tx = miner.create_transaction(
        chain,
        dest.segwit_address,
        amount=100_000_000,
        fee=1_000,
        from_address=miner.segwit_address,
        change_address=miner.segwit_address,
    )
    chain.add_mempool_transaction(tx)

    with served(NetCoinNode(chain, persist=False)) as s:
        data = get(f"{s.url}/utxos?address={miner.segwit_address}")
        raw = get(f"{s.url}/utxos?address={miner.segwit_address}&include_mempool_spent=1")

    outpoints = {f"{u['txid']}:{u['vout']}" for u in data["utxos"]}
    raw_outpoints = {f"{u['txid']}:{u['vout']}" for u in raw["utxos"]}
    assert spendable.outpoint() not in outpoints
    assert spendable.outpoint() in raw_outpoints
    assert data["excluded_mempool_spent"] == 1
    assert raw["excluded_mempool_spent"] == 0


def test_balance_endpoint_for_address(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)

    with served(NetCoinNode(chain, persist=False)) as s:
        data = get(f"{s.url}/balance/{miner.address}")
    assert data["address"] == miner.address
    assert data["height"] == 1
    assert data["total_sats"] > 0
    assert data["total"] == "50.00000000"
    assert data["spendable"] == "0.00000000"


def test_supply_endpoint_reports_exact_coinbase_totals(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    chain.mine_block(miner.address)

    expected_total = sum(block.transactions[0].total_output() for block in chain.chain)
    with served(NetCoinNode(chain, persist=False)) as s:
        data = get(f"{s.url}/supply")

    assert data["height"] == 2
    assert data["tip_hash"] == chain.tip_hash()
    assert data["total_minted_sats"] == expected_total
    assert data["total_minted"] == "100.00000000"
    assert data["tip_coinbase_sats"] == chain.tip().transactions[0].total_output()
    assert data["next_height"] == 3
    assert data["next_subsidy_sats"] == chain.subsidy(3)


def test_mempool_and_fee_estimates_endpoints(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    with served(NetCoinNode(chain, persist=False)) as s:
        mempool = get(f"{s.url}/mempool")
        fees = get(f"{s.url}/fee-estimates")
    assert mempool["size"] == 0
    assert mempool["transactions"] == []
    assert set(fees["presets"]) == {"slow", "normal", "fast"}
    assert fees["presets"]["fast"]["target_blocks"] == 1


def test_latest_txs_and_block_fee_breakdown_endpoints(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    block = chain.tip()
    coinbase_txid = block.transactions[0].txid()
    with served(NetCoinNode(chain, persist=False)) as s:
        latest_txs = get(f"{s.url}/latest-txs?n=5")
        block_json = get(f"{s.url}/block/{block.hash()}")
    assert latest_txs["confirmed"][0]["txid"] == coinbase_txid
    assert latest_txs["confirmed"][0]["block_height"] == block.header.height
    assert block_json["coinbase_value_sats"] == block.transactions[0].total_output()
    assert block_json["subsidy_sats"] == chain.subsidy(block.header.height)
    assert block_json["fees_sats"] == 0
