"""Chain reorganization tests: fork selection by cumulative work, rollback,
out-of-order block connection, and mempool revalidation."""

import time
from pathlib import Path

import pytest

from netcoin.block import Block, BlockHeader, check_proof_of_work, merkle_root
from netcoin.chain import Blockchain, ChainError
from netcoin.tx import amount_to_sats, create_coinbase_transaction
from netcoin.wallet import Wallet


def mined(tmp_path: Path, name: str, count: int, wallet: Wallet) -> Blockchain:
    chain = Blockchain(tmp_path / name)
    for _ in range(count):
        chain.mine_block(wallet.address)
    return chain


def clone_prefix(tmp_path: Path, name: str, source: Blockchain, upto_height: int) -> Blockchain:
    """A new chain that shares source's blocks at heights 1..upto_height."""
    chain = Blockchain(tmp_path / name)
    for block in source.chain[1 : upto_height + 1]:
        chain.add_block(block)
    return chain


def feed(target: Blockchain, blocks) -> None:
    """Submit blocks to target, tolerating not-yet-connecting ones."""
    for block in blocks:
        try:
            target.add_block(block)
        except ChainError:
            pass


def test_reorg_switches_to_heavier_fork(tmp_path: Path):
    miner_a = Wallet.create()
    miner_b = Wallet.create()
    a = mined(tmp_path, "a", 3, miner_a)  # height 3
    original_tip = a.tip_hash()

    # Competing branch shares blocks up to height 2, then grows to height 4.
    b = clone_prefix(tmp_path, "b", a, 2)
    b.mine_block(miner_b.address)
    b.mine_block(miner_b.address)
    assert b.height() == 4

    feed(a, b.chain[3:5])  # the two divergent blocks (heights 3 and 4)

    assert a.height() == 4
    assert a.tip_hash() == b.tip_hash()
    assert a.tip_hash() != original_tip
    # The adopted chain is internally consistent.
    a.assert_valid_chain(a.chain)


def test_equal_work_fork_does_not_reorg(tmp_path: Path):
    miner_a = Wallet.create()
    miner_b = Wallet.create()
    a = mined(tmp_path, "a", 3, miner_a)  # height 3
    original_tip = a.tip_hash()

    # Competing branch of equal length (height 3) forking at height 2.
    b = clone_prefix(tmp_path, "b", a, 2)
    b.mine_block(miner_b.address)
    assert b.height() == 3
    assert b.tip_hash() != original_tip

    feed(a, [b.chain[3]])

    # First-seen tip is kept on a tie.
    assert a.height() == 3
    assert a.tip_hash() == original_tip


def test_out_of_order_blocks_connect(tmp_path: Path):
    miner = Wallet.create()
    a = mined(tmp_path, "a", 1, miner)  # height 1

    # Source extends height 1 with two more blocks.
    source = clone_prefix(tmp_path, "source", a, 1)
    source.mine_block(miner.address)
    source.mine_block(miner.address)
    block2, block3 = source.chain[2], source.chain[3]

    target = clone_prefix(tmp_path, "target", a, 1)  # height 1
    # Child arrives before its parent: stored, no progress yet.
    feed(target, [block3])
    assert target.height() == 1
    # Parent arrives: it connects, and the orphaned child connects on top.
    target.add_block(block2)
    assert target.height() == 3
    assert target.tip_hash() == source.tip_hash()


def test_invalid_heavier_fork_is_not_adopted(tmp_path: Path):
    miner_a = Wallet.create()
    miner_b = Wallet.create()
    a = mined(tmp_path, "a", 2, miner_a)  # height 2
    original_tip = a.tip_hash()

    # Build a longer competing branch (height 4) forking at height 1.
    b = clone_prefix(tmp_path, "b", a, 1)
    for _ in range(3):
        b.mine_block(miner_b.address)
    assert b.height() == 4

    # Corrupt the fork-point block's transactions so its header merkle root no
    # longer matches (proof of work stays valid; the branch is invalid).
    forked = b.chain[2]
    forked.transactions[0].outputs[0] = type(forked.transactions[0].outputs[0])(
        amount=forked.transactions[0].outputs[0].amount,
        address=miner_a.address,
    )

    feed(a, b.chain[2:5])

    # No valid heavier branch exists, so the active chain is unchanged.
    assert a.height() == 2
    assert a.tip_hash() == original_tip


def test_fork_block_with_bad_proof_of_work_is_rejected(tmp_path: Path):
    miner = Wallet.create()
    a = mined(tmp_path, "a", 2, miner)  # height 2

    height = 1
    coinbase = create_coinbase_transaction(height, miner.address, a.subsidy(height))
    header = BlockHeader(
        version=1,
        previous_hash=a.chain[0].hash(),  # forks at genesis
        merkle_root=merkle_root([coinbase]),
        timestamp=int(time.time()),
        bits=a.expected_bits_for_height(height, a.chain),
        nonce=0,
        height=height,
    )
    # Find a nonce that fails proof of work (most do at this difficulty).
    while check_proof_of_work(header):
        header.nonce += 1
    bad_block = Block(header=header, transactions=[coinbase])

    with pytest.raises(ChainError, match="proof of work"):
        a.add_block(bad_block)
    assert a.height() == 2
    assert bad_block.hash() not in a.orphan_blocks


def test_reorg_returns_disconnected_transactions_to_mempool(tmp_path: Path):
    miner = Wallet.create()
    receiver = Wallet.create()
    a = mined(tmp_path, "a", 101, miner)  # mature coinbase available

    # Competing branch shares the full 101-block prefix.
    b = clone_prefix(tmp_path, "b", a, 101)

    # On chain A: spend a mature coinbase and mine it into block 102.
    tx = miner.create_transaction(a, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    a.add_mempool_transaction(tx)
    a.mine_block(miner.address)
    assert a.height() == 102
    assert a.mempool_info()["size"] == 0

    # On chain B: mine two blocks (no such tx) so it outweighs A.
    b.mine_block(miner.address)
    b.mine_block(miner.address)
    assert b.height() == 103

    feed(a, b.chain[102:104])

    # A reorged to B's heavier branch...
    assert a.height() == 103
    assert a.tip_hash() == b.tip_hash()
    # ...and the transaction from the disconnected block 102 is back in the
    # mempool (its spent coinbase still exists in the shared prefix).
    assert tx.txid() in {entry["txid"] for entry in a.mempool_info()["entries"]}
