from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.crypto import ecdsa_sign, ecdsa_verify, generate_private_key, private_key_to_public_key, validate_address
from netcoin.tx import amount_to_sats
from netcoin.wallet import Wallet


def test_key_address_and_signature():
    private_key = generate_private_key()
    public_key = private_key_to_public_key(private_key)
    assert validate_address(
        __import__("netcoin.crypto", fromlist=["public_key_to_address"]).public_key_to_address(public_key)
    )
    digest = b"\x01" * 32
    sig = ecdsa_sign(private_key, digest)
    assert ecdsa_verify(public_key, digest, sig)


def test_mine_and_send(tmp_path: Path):
    data = tmp_path / "chain"
    chain = Blockchain(data)
    miner = Wallet.create()
    receiver = Wallet.create()

    for _ in range(101):
        chain.mine_block(miner.address)

    balances = chain.balances_for_address(miner.address)
    assert balances["spendable"] >= amount_to_sats("50")

    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("12.5"), amount_to_sats("0.01"))
    txid = chain.add_mempool_transaction(tx)
    assert txid == tx.txid()
    block = chain.mine_block(miner.address)
    assert any(item.txid() == txid for item in block.transactions)
    assert chain.balances_for_address(receiver.address)["total"] == amount_to_sats("12.5")
    chain.assert_valid_chain(chain.chain)
