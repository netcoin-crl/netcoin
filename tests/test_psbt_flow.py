"""Full PSBT flow (#27): create, multi-party sign, combine, finalize, extract."""
from pathlib import Path

import pytest

from netcoin.chain import Blockchain
from netcoin.psbt import PartiallySignedTransaction, PSBTError, combine_psbts
from netcoin.tx import TxOutput, amount_to_sats
from netcoin.wallet import Wallet


def two_funded_wallets(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    a, b, receiver = Wallet.create(), Wallet.create(), Wallet.create()
    for _ in range(101):
        chain.mine_block(a.address)
    for _ in range(101):
        chain.mine_block(b.address)
    return chain, a, b, receiver


def test_create_sign_extract_single_party(tmp_path: Path):
    chain, a, _b, receiver = two_funded_wallets(tmp_path)
    utxo = chain.utxos_for_address(a.address)[0]
    out = TxOutput(amount=utxo.output.amount - amount_to_sats("0.01"), address=receiver.address)
    psbt = PartiallySignedTransaction.create([utxo], [out])
    assert not psbt.is_fully_signed()
    psbt.sign(a)
    assert psbt.is_fully_signed()
    tx = psbt.extract()
    chain.add_mempool_transaction(tx)  # valid against the chain
    assert tx.txid() in {e["txid"] for e in chain.mempool_info()["entries"]}


def test_multiparty_combine(tmp_path: Path):
    chain, a, b, receiver = two_funded_wallets(tmp_path)
    utxo_a = chain.utxos_for_address(a.address)[0]
    utxo_b = chain.utxos_for_address(b.address)[0]
    total = utxo_a.output.amount + utxo_b.output.amount
    out = TxOutput(amount=total - amount_to_sats("0.02"), address=receiver.address)

    # Each party builds the same unsigned PSBT and signs only the input it owns.
    psbt_a = PartiallySignedTransaction.create([utxo_a, utxo_b], [out])
    psbt_b = PartiallySignedTransaction.create([utxo_a, utxo_b], [out])
    psbt_a.sign(a)
    psbt_b.sign(b)
    assert not psbt_a.is_fully_signed()  # only input 0 signed
    assert not psbt_b.is_fully_signed()  # only input 1 signed

    psbt_a.combine(psbt_b)
    assert psbt_a.is_fully_signed()
    tx = psbt_a.finalize()
    chain.add_mempool_transaction(tx)  # both inputs validly signed
    assert chain.mempool_info()["size"] == 1


def test_combine_via_base64_helper(tmp_path: Path):
    chain, a, b, receiver = two_funded_wallets(tmp_path)
    utxo_a = chain.utxos_for_address(a.address)[0]
    utxo_b = chain.utxos_for_address(b.address)[0]
    out = TxOutput(amount=utxo_a.output.amount + utxo_b.output.amount - amount_to_sats("0.02"), address=receiver.address)

    pa = PartiallySignedTransaction.create([utxo_a, utxo_b], [out]); pa.sign(a)
    pb = PartiallySignedTransaction.create([utxo_a, utxo_b], [out]); pb.sign(b)
    combined_text = combine_psbts(["netpsbt:" + pa.to_base64(), "netpsbt:" + pb.to_base64()])
    combined = PartiallySignedTransaction.from_base64(combined_text)
    assert combined.is_fully_signed()
    chain.add_mempool_transaction(combined.extract())


def test_combine_rejects_mismatched_tx(tmp_path: Path):
    chain, a, b, receiver = two_funded_wallets(tmp_path)
    utxo_a = chain.utxos_for_address(a.address)[0]
    utxo_b = chain.utxos_for_address(b.address)[0]
    p1 = PartiallySignedTransaction.create([utxo_a], [TxOutput(amount=amount_to_sats("1"), address=receiver.address)])
    p2 = PartiallySignedTransaction.create([utxo_b], [TxOutput(amount=amount_to_sats("2"), address=receiver.address)])
    with pytest.raises(PSBTError, match="different transactions"):
        p1.combine(p2)


def test_extract_requires_full_signing(tmp_path: Path):
    chain, a, b, receiver = two_funded_wallets(tmp_path)
    utxo_a = chain.utxos_for_address(a.address)[0]
    utxo_b = chain.utxos_for_address(b.address)[0]
    out = TxOutput(amount=utxo_a.output.amount + utxo_b.output.amount - amount_to_sats("0.02"), address=receiver.address)
    psbt = PartiallySignedTransaction.create([utxo_a, utxo_b], [out])
    psbt.sign(a)  # only input 0
    with pytest.raises(PSBTError, match="not fully signed"):
        psbt.extract()
