from pathlib import Path

from netcoin.apps import AppStore
from netcoin.chain import Blockchain
from netcoin.wallet import Wallet


def _make_escrow(store: AppStore, chain: Blockchain, **overrides):
    buyer, seller, mediator = Wallet.create(), Wallet.create(), Wallet.create()
    payload = {
        "buyer_pubkey": buyer.public_key.hex(),
        "seller_pubkey": seller.public_key.hex(),
        "mediator_pubkey": mediator.public_key.hex(),
        "amount_sats": 1_000_000,
    }
    payload.update(overrides)
    return store.create_escrow(chain, payload)


def test_unfunded_escrow_expires_and_auto_cancels(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    escrow = _make_escrow(store, chain, funding_expiry_seconds=1)

    import time

    time.sleep(1.1)
    result = store.escrow_status(chain, escrow["escrow_id"])
    assert result["status"] == "canceled"
    assert "expired" in result["canceled_reason"]


def test_funded_escrow_never_expires_even_past_the_window(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    escrow = _make_escrow(store, chain, funding_expiry_seconds=1)

    data = store.load()
    data["escrows"][escrow["escrow_id"]]["status"] = "funded"
    store.save(data)

    import time

    time.sleep(1.1)
    result = store.escrow_status(chain, escrow["escrow_id"])
    assert result["status"] == "funded"


def test_default_expiry_window_is_generous_and_does_not_expire_immediately(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    escrow = _make_escrow(store, chain)
    result = store.escrow_status(chain, escrow["escrow_id"])
    assert result["status"] == "funding_ready"


def test_expire_stale_escrows_sweeps_all_at_once(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    _make_escrow(store, chain, funding_expiry_seconds=1)
    _make_escrow(store, chain, funding_expiry_seconds=1)
    _make_escrow(store, chain)  # not expired

    import time

    time.sleep(1.1)
    changed = store.expire_stale_escrows()
    assert changed == 2
