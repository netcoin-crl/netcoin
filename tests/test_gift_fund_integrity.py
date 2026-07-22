from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore
from netcoin.chain import Blockchain
from netcoin.wallet import Wallet


def test_gift_funded_flag_cannot_be_caller_supplied(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    gift = store.create_gift(chain, {"amount": "1", "funded": True})
    assert gift["funded"] is False
    with pytest.raises(AppError, match="not been chain-verified"):
        store.claim_gift({"claim_code": gift["claim_code"], "address": Wallet.create().segwit_address})


def test_gift_funding_txid_must_actually_pay_funding_address(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    unrelated = chain.mine_block(Wallet.create().segwit_address)
    with pytest.raises(AppError, match="does not pay"):
        store.create_gift(
            chain,
            {
                "amount": "1",
                "funding_address": Wallet.create().segwit_address,
                "funding_txid": unrelated.transactions[0].txid(),
            },
        )


def test_chain_verified_gift_can_be_claimed(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    funding_wallet = Wallet.create()
    block = chain.mine_block(funding_wallet.segwit_address)
    gift = store.create_gift(
        chain,
        {
            "amount_sats": 1,
            "funding_address": funding_wallet.segwit_address,
            "funding_txid": block.transactions[0].txid(),
        },
    )
    assert gift["funded"] is True
    claimed = store.claim_gift({"claim_code": gift["claim_code"], "address": Wallet.create().segwit_address})
    assert claimed["status"] == "claimed"
    assert claimed["payout_plan"]["kind"] == "gift"
