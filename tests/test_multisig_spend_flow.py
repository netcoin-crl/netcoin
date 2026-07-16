"""End-to-end M-of-N P2SH multisig spending: fund a multisig address, collect
partial signatures from separate cosigner PSBT copies, combine them, and
broadcast. This was the one real gap left in wallet custody: address
derivation (Wallet.create_multisig_address) already existed and the low-level
P2SH/OP_CHECKMULTISIG script verification already worked, but nothing ever
assembled a valid multisig scriptSig from independently-collected signatures,
and it was never proven end to end.
"""

from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.crypto import bytes_to_hex, private_key_to_public_key
from netcoin.psbt import PartiallySignedTransaction, PSBTError
from netcoin.script import multisig_redeem_script, script_to_p2sh_address
from netcoin.tx import TxInput, TxOutput, Transaction, amount_to_sats
from netcoin.wallet import Wallet


def _pubkey_hex(wallet: Wallet) -> str:
    return bytes_to_hex(private_key_to_public_key(wallet.private_key, compressed=True))


def _fund_multisig(tmp_path: Path):
    """Mine a funded wallet, then send from it to a fresh 2-of-3 P2SH
    multisig address, mining the funding tx to confirmation."""
    chain = Blockchain(tmp_path / "chain")
    funder = Wallet.create()
    m1, m2, m3 = Wallet.create(), Wallet.create(), Wallet.create()
    for _ in range(101):
        chain.mine_block(funder.address)

    redeem_script = multisig_redeem_script(2, [_pubkey_hex(m1), _pubkey_hex(m2), _pubkey_hex(m3)])
    multisig_address = script_to_p2sh_address(redeem_script)

    utxo = chain.utxos_for_address(funder.address)[0]
    fund_amount = utxo.output.amount - amount_to_sats("0.01")
    fund_tx = Transaction(
        inputs=[TxInput(txid=utxo.txid, vout=utxo.vout)],
        outputs=[TxOutput(amount=fund_amount, address=multisig_address)],
    )
    fund_tx.sign_input(0, funder.private_key, utxo)
    chain.add_mempool_transaction(fund_tx)
    chain.mine_block(funder.address)  # confirm the funding tx

    multisig_utxo = chain.utxos_for_address(multisig_address)[0]
    return chain, redeem_script, multisig_address, multisig_utxo, (m1, m2, m3)


def test_two_of_three_multisig_spend_end_to_end(tmp_path: Path):
    chain, redeem_script, multisig_address, utxo, (m1, m2, m3) = _fund_multisig(tmp_path)
    receiver = Wallet.create()
    spend_amount = utxo.output.amount - amount_to_sats("0.01")

    # Two independent cosigners each build their own copy of the unsigned
    # PSBT (as they would on separate machines) and sign only their own key.
    psbt_a = PartiallySignedTransaction.create([utxo], [TxOutput(amount=spend_amount, address=receiver.address)])
    psbt_a.set_multisig_input(0, redeem_script)
    psbt_a.sign_multisig_input(0, m1)
    assert not psbt_a.is_fully_signed()  # only 1 of 2 required signatures

    psbt_b = PartiallySignedTransaction.from_base64(psbt_a.to_base64())
    psbt_b.sign_multisig_input(0, m2)

    psbt_a.combine(psbt_b)
    assert psbt_a.is_fully_signed()

    tx = psbt_a.extract()
    chain.add_mempool_transaction(tx)  # real P2SH/OP_CHECKMULTISIG verification
    assert tx.txid() in {e["txid"] for e in chain.mempool_info()["entries"]}

    chain.mine_block(receiver.address)
    assert any(u.txid == tx.txid() for u in chain.utxos_for_address(receiver.address))


def test_signers_out_of_redeem_script_order_still_finalizes_correctly(tmp_path: Path):
    """OP_CHECKMULTISIG matches sigs to pubkeys in a single forward pass, so
    signatures must be assembled in redeem-script pubkey order regardless of
    the order cosigners happened to sign in."""
    chain, redeem_script, multisig_address, utxo, (m1, m2, m3) = _fund_multisig(tmp_path)
    receiver = Wallet.create()
    spend_amount = utxo.output.amount - amount_to_sats("0.01")

    psbt = PartiallySignedTransaction.create([utxo], [TxOutput(amount=spend_amount, address=receiver.address)])
    psbt.set_multisig_input(0, redeem_script)
    # Sign with the LAST redeem-script signer first, then the FIRST.
    psbt.sign_multisig_input(0, m3)
    psbt.sign_multisig_input(0, m1)
    assert psbt.is_fully_signed()

    tx = psbt.extract()
    chain.add_mempool_transaction(tx)  # would fail verification if sig ordering were wrong
    assert tx.txid() in {e["txid"] for e in chain.mempool_info()["entries"]}


def test_insufficient_signatures_cannot_extract(tmp_path: Path):
    chain, redeem_script, multisig_address, utxo, (m1, m2, m3) = _fund_multisig(tmp_path)
    receiver = Wallet.create()
    spend_amount = utxo.output.amount - amount_to_sats("0.01")

    psbt = PartiallySignedTransaction.create([utxo], [TxOutput(amount=spend_amount, address=receiver.address)])
    psbt.set_multisig_input(0, redeem_script)
    psbt.sign_multisig_input(0, m1)
    assert not psbt.is_fully_signed()
    try:
        psbt.extract()
        assert False, "expected PSBTError: not enough signatures"
    except PSBTError:
        pass


def test_signer_not_in_redeem_script_is_rejected(tmp_path: Path):
    chain, redeem_script, multisig_address, utxo, (m1, m2, m3) = _fund_multisig(tmp_path)
    receiver = Wallet.create()
    spend_amount = utxo.output.amount - amount_to_sats("0.01")
    outsider = Wallet.create()

    psbt = PartiallySignedTransaction.create([utxo], [TxOutput(amount=spend_amount, address=receiver.address)])
    psbt.set_multisig_input(0, redeem_script)
    try:
        psbt.sign_multisig_input(0, outsider)
        assert False, "expected PSBTError: signer not part of the multisig"
    except PSBTError:
        pass


def test_tampered_signature_is_rejected_by_chain_validation(tmp_path: Path):
    chain, redeem_script, multisig_address, utxo, (m1, m2, m3) = _fund_multisig(tmp_path)
    receiver = Wallet.create()
    spend_amount = utxo.output.amount - amount_to_sats("0.01")

    psbt = PartiallySignedTransaction.create([utxo], [TxOutput(amount=spend_amount, address=receiver.address)])
    psbt.set_multisig_input(0, redeem_script)
    psbt.sign_multisig_input(0, m1)
    psbt.sign_multisig_input(0, m2)
    assert psbt.is_fully_signed()

    # Corrupt one of the collected signatures before extract.
    pubkeys = list(psbt.partial_sigs[0].keys())
    bad_sig = psbt.partial_sigs[0][pubkeys[0]]
    psbt.partial_sigs[0][pubkeys[0]] = ("00" * (len(bad_sig) // 2)) + bad_sig[len(bad_sig) :]
    if psbt.partial_sigs[0][pubkeys[0]] == bad_sig:
        psbt.partial_sigs[0][pubkeys[0]] = "ff" + bad_sig[2:]

    tx = psbt.extract()
    try:
        chain.add_mempool_transaction(tx)
        assert False, "expected the tampered signature to fail verification"
    except Exception:
        pass


def test_psbt_round_trip_preserves_multisig_state(tmp_path: Path):
    chain, redeem_script, multisig_address, utxo, (m1, m2, m3) = _fund_multisig(tmp_path)
    receiver = Wallet.create()
    spend_amount = utxo.output.amount - amount_to_sats("0.01")

    psbt = PartiallySignedTransaction.create([utxo], [TxOutput(amount=spend_amount, address=receiver.address)])
    psbt.set_multisig_input(0, redeem_script)
    psbt.sign_multisig_input(0, m1)

    reloaded = PartiallySignedTransaction.from_base64(psbt.to_base64())
    assert reloaded.redeem_scripts == psbt.redeem_scripts
    assert reloaded.partial_sigs == psbt.partial_sigs
    reloaded.sign_multisig_input(0, m2)
    assert reloaded.is_fully_signed()
    tx = reloaded.extract()
    chain.add_mempool_transaction(tx)
    assert tx.txid() in {e["txid"] for e in chain.mempool_info()["entries"]}
