"""CLI-level multisig flow: `multisig-address` to derive the address,
`psbt-sign --redeem-script` per cosigner, `psbt-combine --extract` to finish.
The underlying signing/combine correctness is proven in
test_multisig_spend_flow.py; this proves the CLI plumbing itself works.
"""

import argparse
import json
from pathlib import Path

from netcoin import cli
from netcoin.chain import Blockchain
from netcoin.crypto import bytes_to_hex, private_key_to_public_key
from netcoin.psbt import PartiallySignedTransaction
from netcoin.script import multisig_redeem_script, script_to_p2sh_address
from netcoin.tx import Transaction, TxInput, TxOutput, amount_to_sats
from netcoin.wallet import Wallet


def test_multisig_address_cli_matches_library(tmp_path: Path, capsys):
    m1, m2, m3 = Wallet.create(), Wallet.create(), Wallet.create()
    pk1 = bytes_to_hex(private_key_to_public_key(m1.private_key))
    pk2 = bytes_to_hex(private_key_to_public_key(m2.private_key))
    pk3 = bytes_to_hex(private_key_to_public_key(m3.private_key))

    cli.cmd_multisig_address(argparse.Namespace(required=2, pubkey=[pk1, pk2, pk3]))
    result = json.loads(capsys.readouterr().out)
    expected_redeem = multisig_redeem_script(2, [pk1, pk2, pk3])
    assert result["redeem_script"] == expected_redeem
    assert result["address"] == script_to_p2sh_address(expected_redeem)


def test_psbt_sign_and_combine_cli_flow(tmp_path: Path, capsys):
    chain = Blockchain(tmp_path / "chain")
    funder = Wallet.create()
    m1, m2, m3 = Wallet.create(), Wallet.create(), Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(funder.address)

    pk1 = bytes_to_hex(private_key_to_public_key(m1.private_key))
    pk2 = bytes_to_hex(private_key_to_public_key(m2.private_key))
    pk3 = bytes_to_hex(private_key_to_public_key(m3.private_key))
    redeem_script = multisig_redeem_script(2, [pk1, pk2, pk3])
    multisig_address = script_to_p2sh_address(redeem_script)

    utxo = chain.utxos_for_address(funder.address)[0]
    fund_amount = utxo.output.amount - amount_to_sats("0.01")
    fund_tx = Transaction(
        inputs=[TxInput(txid=utxo.txid, vout=utxo.vout)],
        outputs=[TxOutput(amount=fund_amount, address=multisig_address)],
    )
    fund_tx.sign_input(0, funder.private_key, utxo)
    chain.add_mempool_transaction(fund_tx)
    chain.mine_block(funder.address)

    ms_utxo = chain.utxos_for_address(multisig_address)[0]
    spend_amount = ms_utxo.output.amount - amount_to_sats("0.01")
    psbt = PartiallySignedTransaction.create([ms_utxo], [TxOutput(amount=spend_amount, address=receiver.address)])
    unsigned_path = tmp_path / "unsigned.psbt"
    unsigned_path.write_text(psbt.to_base64())

    w1_path, w2_path = tmp_path / "m1.json", tmp_path / "m2.json"
    m1.save(w1_path)
    m2.save(w2_path)

    signed1_path = tmp_path / "signed1.psbt"
    cli.cmd_psbt_sign(
        argparse.Namespace(
            wallet=str(w1_path),
            passphrase=None,
            psbt=str(unsigned_path),
            out=str(signed1_path),
            redeem_script=redeem_script,
            input_index=0,
        )
    )
    capsys.readouterr()

    signed2_path = tmp_path / "signed2.psbt"
    cli.cmd_psbt_sign(
        argparse.Namespace(
            wallet=str(w2_path),
            passphrase=None,
            psbt=str(unsigned_path),  # each cosigner starts from the same unsigned PSBT
            out=str(signed2_path),
            redeem_script=redeem_script,
            input_index=0,
        )
    )
    capsys.readouterr()

    out_path = tmp_path / "final.psbt"
    cli.cmd_psbt_combine(
        argparse.Namespace(psbt=[str(signed1_path), str(signed2_path)], out=str(out_path), extract=True)
    )
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["fully_signed"] is True
    assert "txid" in result and "raw_tx" in result

    # raw_tx is a hex summary for display; NetCoin's script templates aren't
    # binary-round-trippable (from_hex intentionally refuses), so re-extract
    # the actual Transaction object from the combined PSBT file instead.
    combined_psbt = PartiallySignedTransaction.from_base64(out_path.read_text())
    tx = combined_psbt.extract()
    assert tx.txid() == result["txid"]
    chain.add_mempool_transaction(tx)
    assert tx.txid() in {e["txid"] for e in chain.mempool_info()["entries"]}
