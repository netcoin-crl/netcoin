"""Testnet v2 real-difficulty params: 2-min/30-block retarget that adjusts the
right direction, plus the lone-miner min-difficulty rule."""
from pathlib import Path

from netcoin.block import Block, BlockHeader, bits_to_target, target_to_bits
from netcoin.chain import Blockchain
from netcoin.params import (
    COIN,
    DIFFICULTY_ADJUSTMENT_INTERVAL,
    MIN_DIFFICULTY_GAP_SECONDS,
    POW_LIMIT_BITS,
    TARGET_SPACING_SECONDS,
    TARGET_TIMESPAN_SECONDS,
)
from netcoin.tx import create_coinbase_transaction
from netcoin.wallet import Wallet

ADDR = Wallet.create().address


def _block(height: int, ts: int, bits: int) -> Block:
    coinbase = create_coinbase_transaction(height, ADDR, COIN)
    header = BlockHeader(version=1, previous_hash="0" * 64, merkle_root="0" * 64,
                         timestamp=ts, bits=bits, nonce=0, height=height)
    return Block(header=header, transactions=[coinbase])


def test_params_are_testnet_v2():
    assert TARGET_SPACING_SECONDS == 120
    assert DIFFICULTY_ADJUSTMENT_INTERVAL == 30


def test_retarget_adjusts_in_the_right_direction(tmp_path: Path):
    chain = Blockchain(tmp_path / "c")
    start_bits = target_to_bits(bits_to_target(POW_LIMIT_BITS) // 100)  # harder than the floor
    n = DIFFICULTY_ADJUSTMENT_INTERVAL

    # blocks arrived FAST (window = 1/4 of target) -> difficulty should rise (target shrinks)
    fast = [_block(i, i * (TARGET_SPACING_SECONDS // 4), start_bits) for i in range(n)]
    fast_bits = chain.expected_bits_for_height(n, fast)
    assert bits_to_target(fast_bits) < bits_to_target(start_bits)

    # blocks arrived SLOW (window = 4x target) -> difficulty should fall (target grows)
    slow = [_block(i, i * (TARGET_SPACING_SECONDS * 4), start_bits) for i in range(n)]
    slow_bits = chain.expected_bits_for_height(n, slow)
    assert bits_to_target(slow_bits) > bits_to_target(start_bits)


def test_lone_miner_min_difficulty_rule(tmp_path: Path):
    chain = Blockchain(tmp_path / "c")
    start_bits = target_to_bits(bits_to_target(POW_LIMIT_BITS) // 100)
    # a short prefix whose next height is NOT a retarget boundary
    prefix = [_block(i, i * 30, start_bits) for i in range(5)]
    parent_ts = prefix[-1].header.timestamp
    height = 5
    expected = chain.expected_bits_for_height(height, prefix)
    assert expected == start_bits  # between retargets difficulty is fixed

    # on-time block: must use the expected difficulty
    assert chain._bits_acceptable(height, prefix, expected, parent_ts + 10) is True
    assert chain._bits_acceptable(height, prefix, POW_LIMIT_BITS, parent_ts + 10) is False

    # late block (> 2x spacing after parent): may use the PoW floor
    late_ts = parent_ts + MIN_DIFFICULTY_GAP_SECONDS + 5
    assert chain._bits_acceptable(height, prefix, POW_LIMIT_BITS, late_ts) is True
    # ...but still not an arbitrary wrong difficulty
    wrong = target_to_bits(bits_to_target(POW_LIMIT_BITS) // 7)
    assert chain._bits_acceptable(height, prefix, wrong, late_ts) is False


def test_new_genesis_differs_from_v1():
    # the v1 genesis message was the original; v2 must be a different chain
    from netcoin.params import GENESIS_MESSAGE

    assert "v2" in GENESIS_MESSAGE
