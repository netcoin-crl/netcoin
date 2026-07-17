from __future__ import annotations

import subprocess
from pathlib import Path

from netcoin.apps import AppStore, route_app_get, route_app_post
from netcoin.chain import Blockchain
from netcoin.live_product import explorer_address_live, explorer_tx_live
from netcoin.wallet import Wallet

ROOT = Path(__file__).resolve().parents[1]
EXPLORER = ROOT / "sites" / "explorer"


def test_phase3_explorer_static_pages_surface_available_tools() -> None:
    address_html = (EXPLORER / "address.html").read_text(encoding="utf-8")
    tx_html = (EXPLORER / "tx.html").read_text(encoding="utf-8")
    mempool_html = (EXPLORER / "mempool.html").read_text(encoding="utf-8")
    index_html = (EXPLORER / "index.html").read_text(encoding="utf-8")
    js = (EXPLORER / "explorer-pro.js").read_text(encoding="utf-8")
    css = (EXPLORER / "explorer-pro.css").read_text(encoding="utf-8")

    assert "explorer-pro.js?v=20260716-phase3-availability" in address_html
    assert "explorer-pro.css?v=20260716-phase3-availability" in mempool_html
    assert "Transaction risk" in index_html
    for token in [
        "Watch address",
        "UTXO viewer",
        "Transaction risk",
        "Mempool status",
        "postApi('/explorer/watchlist'",
        "data-copy",
    ]:
        assert token in js
    assert "tx-risk-panel" in css
    assert "phase3-watch" in css
    assert "Tx view" in tx_html


def test_phase3_explorer_js_syntax() -> None:
    proc = subprocess.run(
        ["node", "--check", str(EXPLORER / "explorer-pro.js")], cwd=ROOT, text=True, capture_output=True
    )
    assert proc.returncode == 0, proc.stderr


def test_phase3_address_payload_exposes_utxo_view_fields(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)

    payload = explorer_address_live(chain, miner.address)

    assert payload["profile"]["utxo_count"] >= 1
    first = payload["utxos"][0]
    assert first["outpoint"].count(":") == 1
    assert first["amount_sats"] > 0
    assert first["amount"]
    assert first["confirmations"] >= 1
    assert first["spend_status"] in {"immature", "unspent"}


def test_phase3_transaction_payload_exposes_risk_panel_data(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    txid = chain.tip().transactions[0].txid()

    payload = explorer_tx_live(chain, txid)

    assert payload["ok"] is True
    assert payload["confirmations"] == 1
    assert payload["risk"]["status"] == "confirmed"
    assert payload["risk"]["risk_level"] in {"low", "medium", "high", "critical"}
    assert "warnings" in payload["risk"]


def test_phase3_watchlist_api_persists_address_watch(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(tmp_path / "app")
    wallet = Wallet.create()

    status, created = route_app_post(
        store,
        chain,
        "/api/explorer/watchlist",
        {"watch_type": "address", "address": wallet.address, "label": "miner"},
    )
    assert status == 200
    assert created["ok"] is True
    assert created["watch"]["label"] == "miner"

    status, payload, ctype = route_app_get(store, chain, "/api/explorer/watchlist", {}, node=None)
    assert status == 200
    assert ctype == "application/json"
    assert payload["count"] == 1
    assert payload["watchlist"][0]["address"] == wallet.address
    assert payload["watchlist"][0]["label"] == "miner"

    status, removed = route_app_post(
        store,
        chain,
        "/api/explorer/watchlist/remove",
        {"item_id": created["watch"]["item_id"]},
    )
    assert status == 200
    assert removed["watch"]["active"] is False
