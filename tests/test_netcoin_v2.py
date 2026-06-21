from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.serialization import decode_raw_transaction, tx_to_raw_hex
from netcoin.script import describe_address
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet, new_seed_phrase


def test_v2_addresses_scripts_and_encrypted_wallet(tmp_path: Path):
    phrase = new_seed_phrase()
    wallet = Wallet.create(seed_phrase=phrase)
    encrypted = tmp_path / "encrypted.json"
    wallet.save(encrypted, passphrase="correct horse battery staple")
    loaded = Wallet.load(encrypted, passphrase="correct horse battery staple")
    assert loaded.address == wallet.address
    for kind in ("p2pkh", "p2wpkh", "p2tr"):
        addr = wallet.address_for(kind)
        assert describe_address(addr).kind in {"p2pkh", "p2wpkh", "p2tr"}


def test_v2_segwit_transaction_raw_hex(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    tx = miner.create_transaction(
        chain,
        receiver.segwit_address,
        amount_to_sats("2.5"),
        amount_to_sats("0.01"),
        rbf=True,
    )
    chain.add_mempool_transaction(tx)
    raw = tx_to_raw_hex(tx)
    decoded = decode_raw_transaction(raw)
    assert decoded["vout"][0]["value_sats"] == amount_to_sats("2.5")
    block = chain.mine_block(miner.address)
    assert any(item.txid() == tx.txid() for item in block.transactions)
    assert chain.balances_for_address(receiver.segwit_address)["spendable"] == amount_to_sats("2.5")


def test_v2_taproot_like_spend(tmp_path: Path):
    chain = Blockchain(tmp_path / "taproot-chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.taproot_address)
    tx = miner.create_transaction(
        chain,
        receiver.taproot_address,
        amount_to_sats("1"),
        amount_to_sats("0.01"),
        from_type="taproot",
        change_type="taproot",
    )
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.taproot_address)
    assert chain.balances_for_address(receiver.taproot_address)["spendable"] == amount_to_sats("1")
