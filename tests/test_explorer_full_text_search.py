"""Explorer search was previously purely client-side: sites/explorer/explorer-app.js's
doSearch guessed a single destination (height/address/txid/block-hash) from the
query's shape and navigated straight there, with no way to search by name/label/
title and no way to see more than one candidate. explorer_search_live (and the
/explorer/search route) does a real lookup: exact resolution for chain
primitives, plus substring matches across usernames, labels, merchants,
bounties, community posts, and prediction markets."""

from __future__ import annotations

from pathlib import Path

from netcoin.apps import AppStore, route_app_get
from netcoin.chain import Blockchain
from netcoin.live_product import explorer_search_live
from netcoin.wallet import Wallet


def _chain_and_store(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    return chain, store


def test_exact_txid_and_block_resolution(tmp_path: Path) -> None:
    chain, store = _chain_and_store(tmp_path)
    miner = Wallet.create()
    block = chain.mine_block(miner.address)
    txid = block.transactions[0].txid()

    tx_result = explorer_search_live(chain, store, txid)
    assert tx_result["exact"] == {"type": "tx", "id": txid}

    height_result = explorer_search_live(chain, store, "0")
    assert height_result["exact"]["type"] == "block"

    hash_result = explorer_search_live(chain, store, block.hash())
    assert hash_result["exact"]["type"] == "block"


def test_exact_address_resolution(tmp_path: Path) -> None:
    chain, store = _chain_and_store(tmp_path)
    miner = Wallet.create()
    chain.mine_block(miner.address)

    result = explorer_search_live(chain, store, miner.address)
    assert result["exact"] == {"type": "address", "id": miner.address}


def test_username_exact_and_substring_match(tmp_path: Path) -> None:
    chain, store = _chain_and_store(tmp_path)
    holder = Wallet.create()
    data = store.load()
    data["usernames"]["alice"] = {"address": holder.address, "claimed_at": 0}
    store.save(data)

    exact = explorer_search_live(chain, store, "@alice")
    assert exact["exact"] == {"type": "address", "id": holder.address, "label": "@alice"}

    substring = explorer_search_live(chain, store, "lic")
    assert any(m["type"] == "username" and m["id"] == holder.address for m in substring["matches"])


def test_label_bounty_merchant_and_market_substring_matches(tmp_path: Path) -> None:
    chain, store = _chain_and_store(tmp_path)
    data = store.load()
    data["known_labels"]["net1somelabeladdressxxxxxxxxxxxxxxxxxxxx"] = {
        "address": "net1somelabeladdressxxxxxxxxxxxxxxxxxxxx",
        "label": "Faucet reserve",
    }
    data["merchants"]["shop-1"] = {"merchant_id": "shop-1", "display_name": "Alice's Coffee Shop"}
    data["bounties"]["bty-1"] = {"bounty_id": "bty-1", "title": "Fix the reorg bug"}
    data["prediction_markets"]["mkt-1"] = {"market_id": "mkt-1", "title": "Will it rain tomorrow?"}
    store.save(data)

    assert any(m["type"] == "label" and "faucet" in m["label"].lower() for m in explorer_search_live(chain, store, "faucet")["matches"])
    assert any(m["type"] == "merchant" and m["id"] == "shop-1" for m in explorer_search_live(chain, store, "coffee")["matches"])
    assert any(m["type"] == "bounty" and m["id"] == "bty-1" for m in explorer_search_live(chain, store, "reorg")["matches"])
    assert any(m["type"] == "market" and m["id"] == "mkt-1" for m in explorer_search_live(chain, store, "rain")["matches"])


def test_no_match_returns_ok_with_empty_results(tmp_path: Path) -> None:
    chain, store = _chain_and_store(tmp_path)
    result = explorer_search_live(chain, store, "nothing-matches-this-xyz")
    assert result["ok"] is True
    assert result["exact"] is None
    assert result["matches"] == []


def test_empty_query_short_circuits(tmp_path: Path) -> None:
    chain, store = _chain_and_store(tmp_path)
    result = explorer_search_live(chain, store, "   ")
    assert result["matches"] == []
    assert result["exact"] is None


def test_route_wires_explorer_search(tmp_path: Path) -> None:
    chain, store = _chain_and_store(tmp_path)
    data = store.load()
    data["bounties"]["bty-2"] = {"bounty_id": "bty-2", "title": "Improve docs"}
    store.save(data)

    status, payload, content_type = route_app_get(store, chain, "/explorer/search", {"q": ["docs"]})
    assert status == 200
    assert content_type == "application/json"
    assert any(m["type"] == "bounty" and m["id"] == "bty-2" for m in payload["matches"])
