"""Bounties previously only ever produced a generic operator payout_plan on
award -- a sponsor's promised reward had no connection to any real funds, and
nothing stopped a sponsor promising a reward it never intended to pay. A
bounty can now be backed by a real, already-funded 2-of-3 escrow at creation
time; awarding it settles straight from that escrow's actual multisig UTXO to
the winner, the same PSBT construction escrow_action's own release uses."""

from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore
from netcoin.chain import Blockchain
from netcoin.psbt import PartiallySignedTransaction
from netcoin.wallet import Wallet


def _mature_funded_escrow(tmp_path: Path, amount_sats: int = 100_000):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    sponsor, platform_a, platform_b = Wallet.create(), Wallet.create(), Wallet.create()
    miner = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)

    escrow = store.create_escrow(
        chain,
        {
            "buyer_pubkey": sponsor.public_key.hex(),
            "seller_pubkey": platform_a.public_key.hex(),
            "mediator_pubkey": platform_b.public_key.hex(),
            "buyer_address": sponsor.segwit_address,
            "seller_address": platform_a.segwit_address,
            "mediator_address": platform_b.segwit_address,
            "amount_sats": amount_sats,
        },
    )
    fund_tx = miner.create_transaction(chain, escrow["escrow_address"], amount_sats, 10_000)
    chain.add_mempool_transaction(fund_tx)
    chain.mine_block(miner.address)

    data = store.load()
    data["escrows"][escrow["escrow_id"]]["funding_txid"] = fund_tx.txid()
    store.save(data)
    escrow = store.escrow_status(chain, escrow["escrow_id"])
    assert escrow["status"] == "funded"
    return chain, store, escrow, sponsor, platform_a, platform_b, miner


def test_bounty_requires_a_funded_escrow_matching_sponsor_and_amount(tmp_path: Path):
    chain, store, escrow, sponsor, _platform_a, _platform_b, _miner = _mature_funded_escrow(tmp_path, 100_000)

    with pytest.raises(AppError, match="not found"):
        store.create_bounty(
            chain,
            {"title": "unfunded", "reward_sats": 1000, "escrow_id": "does-not-exist"},
        )

    other = Wallet.create()
    with pytest.raises(AppError, match="escrow's buyer"):
        store.create_bounty(
            chain,
            {
                "title": "wrong sponsor",
                "reward_sats": 1000,
                "sponsor_address": other.segwit_address,
                "escrow_id": escrow["escrow_id"],
            },
        )

    with pytest.raises(AppError, match="smaller than the bounty reward"):
        store.create_bounty(
            chain,
            {
                "title": "too big",
                "reward_sats": 200_000,
                "sponsor_address": sponsor.segwit_address,
                "escrow_id": escrow["escrow_id"],
            },
        )

    bounty = store.create_bounty(
        chain,
        {
            "title": "Fix a bug",
            "reward_sats": 100_000,
            "sponsor_address": sponsor.segwit_address,
            "escrow_id": escrow["escrow_id"],
        },
    )
    assert bounty["escrow_backed"] is True

    with pytest.raises(AppError, match="already backs bounty"):
        store.create_bounty(
            chain,
            {
                "title": "double dip",
                "reward_sats": 100_000,
                "sponsor_address": sponsor.segwit_address,
                "escrow_id": escrow["escrow_id"],
            },
        )


def test_awarding_an_escrow_backed_bounty_pays_the_winner_from_the_real_escrow_utxo(tmp_path: Path):
    chain, store, escrow, sponsor, platform_a, platform_b, miner = _mature_funded_escrow(tmp_path, 100_000)
    bounty = store.create_bounty(
        chain,
        {
            "title": "Fix a bug",
            "reward_sats": 100_000,
            "sponsor_address": sponsor.segwit_address,
            "escrow_id": escrow["escrow_id"],
        },
    )
    winner = Wallet.create()
    store.submit_bounty(bounty["bounty_id"], {"submitter": "alice", "address": winner.segwit_address})

    awarded = store.award_bounty(
        chain,
        bounty["bounty_id"],
        {"winner_address": winner.segwit_address, "signer": sponsor.segwit_address},
    )
    assert awarded["status"] == "ready_for_wallet_signing"
    assert awarded["winner_address"] == winner.segwit_address
    assert "payout_plan" not in awarded

    settlement = awarded["settlement"]
    assert settlement is not None

    psbt = PartiallySignedTransaction.from_base64(settlement["unsigned_psbt"])
    psbt.sign_multisig_input(0, sponsor)
    assert not psbt.is_fully_signed()
    psbt.sign_multisig_input(0, platform_a)
    assert psbt.is_fully_signed()

    tx = psbt.extract()
    assert tx.outputs[0].address == winner.segwit_address

    winner_balance_before = chain.balances_for_address(winner.segwit_address)["total"]
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)
    winner_balance_after = chain.balances_for_address(winner.segwit_address)["total"]
    assert winner_balance_after > winner_balance_before

    # The backing escrow itself is now locked -- the sponsor can't separately
    # release/refund the same coin the bounty just settled from.
    escrow_after = store.escrow_status(chain, escrow["escrow_id"])
    assert escrow_after["status"] == "released"
    with pytest.raises(AppError, match="already released"):
        store.escrow_action(chain, escrow["escrow_id"], {"action": "refund", "signer": platform_b.segwit_address})


def test_bounty_cannot_be_awarded_twice(tmp_path: Path):
    chain, store, escrow, sponsor, _platform_a, _platform_b, _miner = _mature_funded_escrow(tmp_path, 100_000)
    bounty = store.create_bounty(
        chain,
        {
            "title": "Fix a bug",
            "reward_sats": 100_000,
            "sponsor_address": sponsor.segwit_address,
            "escrow_id": escrow["escrow_id"],
        },
    )
    winner = Wallet.create()
    store.award_bounty(chain, bounty["bounty_id"], {"winner_address": winner.segwit_address, "signer": sponsor.segwit_address})

    other_winner = Wallet.create()
    with pytest.raises(AppError, match="already been awarded"):
        store.award_bounty(chain, bounty["bounty_id"], {"winner_address": other_winner.segwit_address, "signer": sponsor.segwit_address})


def test_bounty_without_escrow_still_falls_back_to_generic_payout_plan(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    winner = Wallet.create()
    bounty = store.create_bounty(chain, {"title": "no escrow", "reward_sats": 5000})
    assert bounty["escrow_backed"] is False

    awarded = store.award_bounty(chain, bounty["bounty_id"], {"winner_address": winner.segwit_address})
    assert awarded["status"] == "ready_for_wallet_signing"
    assert awarded["payout_plan"]["kind"] == "bounty"
