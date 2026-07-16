"""Reorg-safe deposit crediting: the classic exchange failure mode is deposit,
credit, customer trades/withdraws, then a reorg orphans the deposit block.
This pins that the ledger reversal happens automatically and that an
already-spent credit is flagged rather than silently leaving the books wrong.
"""

from pathlib import Path

from netcoin.chain import Blockchain, ChainError
from netcoin.exchange import ExchangeLedger
from netcoin.exchange_accounting import AccountingLedger
from netcoin.exchange_deposit_watcher import ExchangeDepositWatcher
from netcoin.wallet import Wallet


def mined(tmp_path: Path, name: str, count: int, wallet: Wallet) -> Blockchain:
    chain = Blockchain(tmp_path / name)
    for _ in range(count):
        chain.mine_block(wallet.address)
    return chain


def clone_prefix(tmp_path: Path, name: str, source: Blockchain, upto_height: int) -> Blockchain:
    chain = Blockchain(tmp_path / name)
    for block in source.chain[1 : upto_height + 1]:
        chain.add_block(block)
    return chain


def feed(target: Blockchain, blocks) -> None:
    for block in blocks:
        try:
            target.add_block(block)
        except ChainError:
            pass


def _watcher(tmp_path: Path) -> tuple[ExchangeDepositWatcher, ExchangeLedger, AccountingLedger]:
    exch = ExchangeLedger(tmp_path / "exchange.sqlite")
    acct = AccountingLedger(tmp_path / "accounting.sqlite")
    return ExchangeDepositWatcher(exch, acct), exch, acct


def test_deposit_credits_ledger_exactly_once(tmp_path: Path):
    miner = Wallet.create()
    chain = mined(tmp_path, "chain", 3, miner)
    watcher, exch, acct = _watcher(tmp_path)

    dep = exch.record_deposit(
        txid="a" * 64,
        vout=0,
        address="Ncustomer1",
        amount_sats=50_000,
        height=2,
        block_hash=chain.chain[2].hash(),
        required_confirmations=2,
        current_height=chain.height(),
    )
    assert dep["state"] == "credited"  # 3 - 2 + 1 = 2 confirmations, meets the requirement

    result = watcher.sync(chain)
    assert dep["deposit_id"] in result["credit"]["newly_credited_and_posted"]
    assert acct.customer_liability_sats("Ncustomer1") == 50_000

    # Calling sync again must not double-credit.
    result2 = watcher.sync(chain)
    assert result2["credit"]["newly_credited_and_posted"] == []
    assert acct.customer_liability_sats("Ncustomer1") == 50_000
    assert acct.invariant_check()["ok"]


def test_reorg_reverses_credited_deposit(tmp_path: Path):
    miner_a = Wallet.create()
    miner_b = Wallet.create()
    a = mined(tmp_path, "a", 3, miner_a)
    orphaned_block_hash = a.chain[2].hash()

    watcher, exch, acct = _watcher(tmp_path)
    dep = exch.record_deposit(
        txid="b" * 64,
        vout=0,
        address="Ncustomer2",
        amount_sats=75_000,
        height=2,
        block_hash=orphaned_block_hash,
        required_confirmations=1,
        current_height=a.height(),
    )
    assert dep["state"] == "credited"
    watcher.sync(a)
    assert acct.customer_liability_sats("Ncustomer2") == 75_000

    # Build a heavier competing chain that reorgs height 2 out from under us.
    b = clone_prefix(tmp_path, "b", a, upto_height=1)
    for _ in range(4):
        b.mine_block(miner_b.address)
    feed(a, b.chain[2:])
    assert a.tip_hash() != orphaned_block_hash
    assert a.block_index.get(orphaned_block_hash) is None  # confirms the block was really orphaned

    reorg_result = watcher.check_for_reorgs(a)
    assert dep["deposit_id"] in reorg_result["reversed_deposit_ids"]
    assert exch.get_deposit(dep["deposit_id"])["state"] == "reorged"
    assert acct.customer_liability_sats("Ncustomer2") == 0
    assert acct.invariant_check()["ok"]

    # Re-running the reorg check must be idempotent (no double-reversal).
    reorg_result2 = watcher.check_for_reorgs(a)
    assert reorg_result2["reversed_deposit_ids"] == []
    assert acct.customer_liability_sats("Ncustomer2") == 0


def test_reorg_after_spend_flags_the_deficit(tmp_path: Path):
    """The dangerous case: customer already withdrew against the deposit
    before the reorg landed. The reversal must not silently go negative
    unnoticed -- it must show up as a flagged deficit for an operator/fraud
    case."""
    miner_a = Wallet.create()
    miner_b = Wallet.create()
    a = mined(tmp_path, "a", 3, miner_a)
    orphaned_block_hash = a.chain[2].hash()

    watcher, exch, acct = _watcher(tmp_path)
    dep = exch.record_deposit(
        txid="c" * 64,
        vout=0,
        address="Ncustomer3",
        amount_sats=100_000,
        height=2,
        block_hash=orphaned_block_hash,
        required_confirmations=1,
        current_height=a.height(),
    )
    watcher.sync(a)
    assert acct.customer_liability_sats("Ncustomer3") == 100_000

    # Customer withdraws the full credited amount before the reorg is seen.
    acct.post_customer_withdrawal(customer_id="Ncustomer3", amount_sats=100_000, withdrawal_id="wd_1")
    assert acct.customer_liability_sats("Ncustomer3") == 0

    b = clone_prefix(tmp_path, "b", a, upto_height=1)
    for _ in range(4):
        b.mine_block(miner_b.address)
    feed(a, b.chain[2:])
    assert a.block_index.get(orphaned_block_hash) is None

    reorg_result = watcher.check_for_reorgs(a)
    assert dep["deposit_id"] in reorg_result["reversed_deposit_ids"]
    assert len(reorg_result["frozen_accounts"]) == 1
    flagged = reorg_result["frozen_accounts"][0]
    assert flagged["customer_id"] == "Ncustomer3"
    assert flagged["deficit_sats"] == -100_000
    # The ledger itself is still internally balanced -- the deficit is a real,
    # visible fact about the business, not a bookkeeping error.
    assert acct.invariant_check()["balanced"]
    assert acct.customer_liability_sats("Ncustomer3") == -100_000


def test_invariant_check_catches_negative_liability_directly(tmp_path: Path):
    acct = AccountingLedger(tmp_path / "acct.sqlite")
    acct.post_customer_deposit(customer_id="Nx", amount_sats=1_000, deposit_id="d1")
    assert acct.invariant_check()["ok"]
    acct.post_customer_withdrawal(customer_id="Nx", amount_sats=1_000, withdrawal_id="w1")
    assert acct.invariant_check()["ok"]
    acct.post_customer_withdrawal(customer_id="Nx", amount_sats=500, withdrawal_id="w2")
    check = acct.invariant_check()
    assert check["ok"] is False
    assert check["negative_customer_liabilities"] == [{"account": "liability:customer:Nx", "balance_sats": -500}]


def test_reverse_reference_is_idempotent_and_rejects_unknown_reference(tmp_path: Path):
    acct = AccountingLedger(tmp_path / "acct.sqlite")
    acct.post_customer_deposit(customer_id="Ny", amount_sats=2_000, deposit_id="dep_y")
    first = acct.reverse_reference("dep_y", reason="test")
    assert first["ok"] is True
    assert acct.customer_liability_sats("Ny") == 0
    second = acct.reverse_reference("dep_y", reason="test")
    assert second.get("already_reversed") is True
    assert acct.customer_liability_sats("Ny") == 0  # not double-reversed

    try:
        acct.reverse_reference("does-not-exist")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_post_rejects_unbalanced_postings_and_leaves_ledger_consistent(tmp_path: Path):
    acct = AccountingLedger(tmp_path / "acct.sqlite")
    acct.post_customer_deposit(customer_id="Nz", amount_sats=10_000, deposit_id="dep_z")
    try:
        acct.post(
            [{"account": "asset:hot_wallet", "debit_sats": 500}, {"account": "liability:customer:Nz", "credit_sats": 400}],
            reference="bad",
        )
        assert False, "expected ValueError for unbalanced postings"
    except ValueError:
        pass
    # The failed attempt must not have written anything.
    assert acct.has_reference("bad") is False
    assert acct.customer_liability_sats("Nz") == 10_000
    assert acct.invariant_check()["ok"]
