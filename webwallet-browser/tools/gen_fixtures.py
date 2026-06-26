"""Emit ground-truth crypto fixtures from the real netcoin library so the JS
core can be verified byte-for-byte (no guessing)."""
import json, sys
from netcoin import crypto, tx as txmod
from netcoin.tx import Transaction, TxInput, TxOutput, SpendableOutput, canonical_json

# Deterministic key (fixed scalar) so fixtures are stable.
priv = 0x1111111111111111111111111111111111111111111111111111111111111111
pub = crypto.private_key_to_public_key(priv, compressed=True)
p2wpkh = crypto.public_key_to_p2wpkh_address(pub)
legacy = crypto.public_key_to_address(pub)

# A prevout this key controls (p2wpkh), and a tx spending it.
prev = SpendableOutput(txid="aa"*32, vout=0,
                       output=TxOutput(amount=500_000_000, address=p2wpkh), height=1)
t = Transaction(
    inputs=[TxInput(txid="aa"*32, vout=0)],
    outputs=[TxOutput(amount=120_000_000, address=p2wpkh),
             TxOutput(amount=379_000_000, address=legacy)],
    version=1, locktime=0,
)
digest = t.sighash(0, prev, txmod.SIGHASH_ALL)
# Sign it the Python way for an end-to-end reference.
t.sign_input(0, priv, prev, txmod.SIGHASH_ALL)

print(json.dumps({
    "priv_hex": f"{priv:064x}",
    "pubkey_hex": pub.hex(),
    "p2wpkh_address": p2wpkh,
    "legacy_address": legacy,
    "prevout_effective_script_pubkey": prev.output.effective_script_pubkey(),
    "sighash_all_digest_hex": digest.hex(),
    "signed_tx": t.to_dict(include_scripts=True, include_witness=True),
}, indent=2))
