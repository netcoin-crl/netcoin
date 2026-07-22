from pathlib import Path

from netcoin.apps import AppStore
from netcoin.chain import Blockchain
from netcoin.crypto import sign_message
from netcoin.wallet import Wallet


def test_phase7_templates_recurring_escrow_polls_and_markets(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    buyer = Wallet.create()
    seller = Wallet.create()
    mediator = Wallet.create()
    chain.mine_block(buyer.address)
    store = AppStore(chain.data_dir)

    templates = store.list_contract_templates()["templates"]
    assert {"recurring_payment", "escrow_2_of_3", "poll", "prediction_market"}.issubset(templates)

    # Generic contract templates.
    timelock = store.create_contract(
        {"type": "timelock", "public_key": buyer.public_key_hex, "unlock_height": 50, "amount": "1"}
    )
    assert timelock["derived"]["address"]
    multisig = store.create_contract(
        {
            "type": "multisig",
            "required_signatures": 2,
            "public_keys": [buyer.public_key_hex, seller.public_key_hex, mediator.public_key_hex],
        }
    )
    assert multisig["derived"]["descriptor"].startswith("sh(multi(2,")

    # Recurring payment agreements create invoice cycles and advance on payment record.
    recurring = store.create_recurring_agreement(
        {
            "payer_address": buyer.address,
            "recipient_address": seller.address,
            "amount": "0.5",
            "interval": "weekly",
            "memo": "hosting",
        }
    )
    invoice = store.create_recurring_invoice(chain, recurring["agreement_id"])
    assert invoice["agreement_id"] == recurring["agreement_id"]
    paid = store.record_recurring_payment(recurring["agreement_id"], {"txid": "aa" * 32})
    assert paid["last_payment_txid"] == "aa" * 32
    assert paid["next_due_at"] > recurring["next_due_at"]

    # Escrow generates a 2-of-3 multisig address and payout plan after two approvals.
    escrow = store.create_escrow(
        chain,
        {
            "buyer_pubkey": buyer.public_key_hex,
            "seller_pubkey": seller.public_key_hex,
            "mediator_pubkey": mediator.public_key_hex,
            "buyer_address": buyer.address,
            "seller_address": seller.address,
            "mediator_address": mediator.address,
            "amount": "1",
            "terms": "ship the item",
        }
    )
    assert escrow["escrow_address"]
    escrow_fund_block = chain.mine_block(escrow["escrow_address"])
    edata = store.load()
    edata["escrows"][escrow["escrow_id"]]["funding_txid"] = escrow_fund_block.transactions[0].txid()
    store.save(edata)
    escrow = store.escrow_status(chain, escrow["escrow_id"])
    assert escrow["status"] == "funded"
    first = store.escrow_action(
        escrow["escrow_id"], {"action": "release", "signer": "buyer", "to_address": seller.address}
    )
    assert first["status"] == "pending_release"
    second = store.escrow_action(
        escrow["escrow_id"], {"action": "release", "signer": "seller", "to_address": seller.address}
    )
    assert second["status"] == "released"
    assert second["payout_plan"]["kind"] == "escrow_release"

    # Polls verify wallet signatures and tally results.
    poll = store.create_poll({"title": "Build prediction markets?", "options": ["yes", "no"]})
    option_id = poll["options"][0]["option_id"]
    msg = store.poll_vote_message(poll["poll_id"], option_id)
    sig = sign_message(buyer.private_key, msg)
    result = store.cast_poll_vote(
        poll["poll_id"], {"voter_address": buyer.address, "option_id": option_id, "signature": sig}
    )
    assert result["vote_count"] == 1
    assert result["winner_option_id"] == option_id

    # Prediction markets are testnet/play-money only, with orders, trades, and resolution payout plans.
    market = store.create_prediction_market(
        {"question": "Will NetCoin mine 10 blocks today?", "outcomes": ["YES", "NO"], "oracle": "manual"}
    )
    yes = market["outcomes"][0]["outcome_id"]
    store.place_market_order(
        market["market_id"],
        {"trader_address": seller.address, "outcome_id": yes, "side": "sell", "quantity": 3, "price_bps": 4000},
    )
    matched = store.place_market_order(
        market["market_id"],
        {"trader_address": buyer.address, "outcome_id": yes, "side": "buy", "quantity": 2, "price_bps": 5000},
    )
    assert matched["trades"]
    resolved = store.resolve_prediction_market(
        market["market_id"], {"winning_outcome_id": yes, "payout_per_share": "1"}
    )
    assert resolved["status"] == "resolved"
    assert resolved["payout_plan"]["kind"] == "prediction_market"
