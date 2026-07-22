from pathlib import Path

from netcoin.apps import AppStore
from netcoin.chain import (
    Blockchain,
    parse_username_claim,
    username_claim_script_pubkey,
    username_transfer_script_pubkey,
)
from netcoin.tx import Transaction, TxInput, TxOutput
from netcoin.wallet import Wallet


def _claim_tx(wallet: Wallet, chain: Blockchain, username: str, fee: int = 2000) -> Transaction:
    utxo = chain.utxos_for_address(wallet.segwit_address)[0]
    outputs = [
        TxOutput(amount=utxo.output.amount - fee, address=wallet.segwit_address),
        TxOutput(amount=0, script_pubkey=username_claim_script_pubkey(username)),
    ]
    tx = Transaction(inputs=[TxInput(txid=utxo.txid, vout=utxo.vout)], outputs=outputs)
    tx.sign_input(0, wallet.private_key, utxo)
    return tx


def _transfer_tx(
    current_owner: Wallet, new_owner_address: str, chain: Blockchain, username: str, fee: int = 2000
) -> Transaction:
    utxo = chain.utxos_for_address(current_owner.segwit_address)[0]
    dust = 546
    outputs = [
        TxOutput(amount=dust, address=new_owner_address),
        TxOutput(amount=0, script_pubkey=username_transfer_script_pubkey(username)),
        TxOutput(amount=utxo.output.amount - fee - dust, address=current_owner.segwit_address),
    ]
    tx = Transaction(inputs=[TxInput(txid=utxo.txid, vout=utxo.vout)], outputs=outputs)
    tx.sign_input(0, current_owner.private_key, utxo)
    return tx


def test_username_claim_script_helpers_round_trip():
    assert username_claim_script_pubkey("Alice_01") == "OP_RETURN NETCOIN_USERNAME alice_01"
    assert parse_username_claim("OP_RETURN NETCOIN_USERNAME alice_01") == "alice_01"
    assert parse_username_claim("OP_0 " + "ab" * 20) is None
    assert parse_username_claim("OP_RETURN NETCOIN_USERNAME " + "x" * 33) is None
    assert parse_username_claim("OP_RETURN NETCOIN_USERNAME Bad!Name") is None


def test_confirmed_username_claim_is_indexed_and_resolves(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain", backend="json")
    wallet = Wallet.create()
    for _ in range(105):
        chain.mine_block(wallet.segwit_address)

    tx = _claim_tx(wallet, chain, "alice")
    chain.add_mempool_transaction(tx)
    chain.mine_block(wallet.segwit_address)

    record = chain.resolve_onchain_username("alice")
    assert record is not None
    assert record["address"] == wallet.segwit_address
    assert record["txid"] == tx.txid()
    assert "alice" in chain.list_onchain_usernames()


def test_first_confirmed_claim_wins_over_a_later_squatter(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain", backend="json")
    owner = Wallet.create()
    squatter = Wallet.create()
    for _ in range(105):
        chain.mine_block(owner.segwit_address)
    for _ in range(101):
        chain.mine_block(squatter.segwit_address)

    chain.add_mempool_transaction(_claim_tx(owner, chain, "alice"))
    chain.mine_block(owner.segwit_address)

    chain.add_mempool_transaction(_claim_tx(squatter, chain, "ALICE"))
    chain.mine_block(squatter.segwit_address)

    record = chain.resolve_onchain_username("alice")
    assert record["address"] == owner.segwit_address


def test_username_index_survives_a_full_reindex(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain", backend="json")
    wallet = Wallet.create()
    for _ in range(105):
        chain.mine_block(wallet.segwit_address)
    chain.add_mempool_transaction(_claim_tx(wallet, chain, "bob"))
    chain.mine_block(wallet.segwit_address)

    chain.reindex()

    record = chain.resolve_onchain_username("bob")
    assert record is not None
    assert record["address"] == wallet.segwit_address


def test_store_resolve_username_prefers_onchain_claim_over_offchain_record(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain", backend="json")
    store = AppStore(chain.data_dir)
    onchain_owner = Wallet.create()
    offchain_owner = Wallet.create()
    for _ in range(105):
        chain.mine_block(onchain_owner.segwit_address)

    # The name was registered off-chain first (legacy path)...
    store.upsert_username({"username": "carol", "address": offchain_owner.segwit_address})
    assert store.resolve_username("carol")["address"] == offchain_owner.segwit_address

    # ...but once someone claims it on-chain, that claim is authoritative.
    chain.add_mempool_transaction(_claim_tx(onchain_owner, chain, "carol"))
    chain.mine_block(onchain_owner.segwit_address)

    resolved = store.resolve_username("carol", chain=chain)
    assert resolved["address"] == onchain_owner.segwit_address
    assert resolved["onchain"] is True


def test_reverse_lookup_username_for_address(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain", backend="json")
    wallet = Wallet.create()
    other = Wallet.create()
    for _ in range(105):
        chain.mine_block(wallet.segwit_address)

    assert chain.username_for_address(wallet.segwit_address) is None

    chain.add_mempool_transaction(_claim_tx(wallet, chain, "dana"))
    chain.mine_block(wallet.segwit_address)

    record = chain.username_for_address(wallet.segwit_address)
    assert record is not None
    assert record["username"] == "dana"
    assert chain.username_for_address(other.segwit_address) is None


def test_transfer_moves_ownership_when_authorized_by_current_owner(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain", backend="json")
    owner = Wallet.create()
    new_owner = Wallet.create()
    for _ in range(105):
        chain.mine_block(owner.segwit_address)

    chain.add_mempool_transaction(_claim_tx(owner, chain, "erin"))
    chain.mine_block(owner.segwit_address)
    assert chain.resolve_onchain_username("erin")["address"] == owner.segwit_address

    chain.add_mempool_transaction(_transfer_tx(owner, new_owner.segwit_address, chain, "erin"))
    chain.mine_block(owner.segwit_address)

    record = chain.resolve_onchain_username("erin")
    assert record["address"] == new_owner.segwit_address
    assert record["transferred_from"] == owner.segwit_address


def test_transfer_ignored_if_not_authorized_by_current_owner(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain", backend="json")
    owner = Wallet.create()
    attacker = Wallet.create()
    for _ in range(105):
        chain.mine_block(owner.segwit_address)
    for _ in range(101):
        chain.mine_block(attacker.segwit_address)

    chain.add_mempool_transaction(_claim_tx(owner, chain, "frank"))
    chain.mine_block(owner.segwit_address)

    # Attacker spends their OWN coin (not the owner's), just naming the same
    # username in a transfer output -- must be ignored, no authorization.
    chain.add_mempool_transaction(_transfer_tx(attacker, attacker.segwit_address, chain, "frank"))
    chain.mine_block(attacker.segwit_address)

    record = chain.resolve_onchain_username("frank")
    assert record["address"] == owner.segwit_address
