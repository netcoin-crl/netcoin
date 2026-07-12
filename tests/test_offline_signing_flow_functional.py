"""End-to-end proof that the offline-signing workflow is functional.

Unlike the unit tests that check individual helpers, this drives the whole
create -> export -> (software) sign -> import -> broadcast chain with real
crypto and validates the resulting transaction against a real chain. This is
the evidence that netcoin/offline_signing.py is a working feature, not just a
validator.
"""

from pathlib import Path

import pytest

from netcoin.chain import Blockchain
from netcoin.offline_signing import (
    OfflineSigningError,
    OfflineSigningTranscript,
    build_broadcast_package,
    export_unsigned_psbt_bundle,
    import_signed_psbt,
    validate_offline_signing_transcript,
)
from netcoin.psbt import PartiallySignedTransaction
from netcoin.tx import TxOutput, amount_to_sats
from netcoin.wallet import Wallet


def _funded_wallet(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    signer = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):  # mature a coinbase so the wallet has a real spendable UTXO
        chain.mine_block(signer.address)
    return chain, signer, receiver


def test_offline_signing_full_flow_with_real_signature(tmp_path: Path):
    chain, signer, receiver = _funded_wallet(tmp_path)
    utxo = chain.utxos_for_address(signer.address)[0]
    out = TxOutput(amount=utxo.output.amount - amount_to_sats("0.01"), address=receiver.address)

    # 1. Online wallet builds the unsigned PSBT and exports the offline bundle.
    unsigned = PartiallySignedTransaction.create([utxo], [out])
    unsigned_text = "netpsbt:" + unsigned.to_base64()
    bundle = export_unsigned_psbt_bundle(unsigned_text, network="testnet")
    assert bundle["private_key_material_included"] is False
    assert bundle["summary"]["fully_signed"] is False
    assert bundle["summary"]["output_count"] == 1
    assert bundle["bundle_hash"]

    # 2. Offline signer imports the unsigned PSBT and signs with real keys.
    offline = PartiallySignedTransaction.from_base64(unsigned_text)
    assert not offline.is_fully_signed()
    offline.sign(signer)
    assert offline.is_fully_signed()
    signed_text = "netpsbt:" + offline.to_base64()

    # 3. Online wallet imports the signed PSBT; it must match the exported skeleton.
    imported = import_signed_psbt(unsigned_text, signed_text)
    assert imported["ready_to_broadcast"] is True
    assert imported["private_key_material_included"] is False
    txid = imported["txid"]
    assert txid

    # 4. Broadcast package is deterministic and carries the same txid.
    package = build_broadcast_package(signed_text, endpoint="/api/tx/broadcast")
    assert package["txid"] == txid
    assert package["submit_automatically"] is False
    assert package["method"] == "POST"

    # 5. The extracted transaction is actually valid against the chain.
    tx = offline.extract()
    chain.add_mempool_transaction(tx)
    assert tx.txid() == txid
    assert txid in {entry["txid"] for entry in chain.mempool_info()["entries"]}

    # 6. A transcript can be produced and self-verifies.
    transcript = OfflineSigningTranscript(
        unsigned_bundle_hash=bundle["bundle_hash"],
        signed_psbt_sha256=imported["signed_psbt_sha256"],
        txid=txid,
        signer_type="software-offline",
        operator_attestation="functional flow test",
    ).to_dict()
    assert validate_offline_signing_transcript(transcript) == []


def test_offline_signing_rejects_tampered_and_unsigned(tmp_path: Path):
    chain, signer, receiver = _funded_wallet(tmp_path)
    utxo = chain.utxos_for_address(signer.address)[0]
    out = TxOutput(amount=utxo.output.amount - amount_to_sats("0.01"), address=receiver.address)
    unsigned = PartiallySignedTransaction.create([utxo], [out])
    unsigned_text = "netpsbt:" + unsigned.to_base64()

    # Importing an unsigned PSBT as "signed" must fail (not fully signed).
    with pytest.raises(OfflineSigningError):
        import_signed_psbt(unsigned_text, unsigned_text)

    # Signing a DIFFERENT transaction must fail the skeleton match.
    other_out = TxOutput(amount=utxo.output.amount - amount_to_sats("0.05"), address=receiver.address)
    tampered = PartiallySignedTransaction.create([utxo], [other_out])
    tampered.sign(signer)
    tampered_text = "netpsbt:" + tampered.to_base64()
    with pytest.raises(OfflineSigningError, match="does not match"):
        import_signed_psbt(unsigned_text, tampered_text)

    # Broadcasting an unsigned PSBT must be refused.
    with pytest.raises(OfflineSigningError):
        build_broadcast_package(unsigned_text)

    # Exporting something that is not a netpsbt: payload must be refused.
    with pytest.raises(OfflineSigningError):
        export_unsigned_psbt_bundle(unsigned.to_base64())


def test_server_build_unsigned_psbt_uses_node_utxos(tmp_path, monkeypatch):
    """The server helper builds a valid unsigned PSBT from node UTXOs, no keys used."""
    from netcoin import webwallet

    chain = Blockchain(tmp_path / "chain")
    wallet = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(wallet.address)

    tip = {"node": {"height": chain.height()}}
    utxos = {"utxos": [u.to_dict() for u in chain.utxos_for_address(wallet.address)]}

    def fake_get(node_url, path, timeout=15):
        if path == "/info":
            return tip
        if path.startswith("/utxos"):
            return utxos
        raise AssertionError(f"unexpected GET {path}")

    monkeypatch.setattr(webwallet, "_node_get", fake_get)

    psbt = webwallet.build_unsigned_psbt_for_send(
        wallet, receiver.address, amount_to_sats("1.0"), amount_to_sats("0.01"), "segwit", "http://node"
    )
    assert not psbt.is_fully_signed()  # no key touched the export path
    # Sign offline and confirm the whole chain reconciles.
    psbt.sign(wallet)
    assert psbt.is_fully_signed()
    tx = psbt.extract()
    chain.add_mempool_transaction(tx)
    assert tx.txid() in {e["txid"] for e in chain.mempool_info()["entries"]}
