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

# Taproot fixture: same key, key-path spend of a p2tr prevout.
taproot_addr = crypto.public_key_to_taproot_address(crypto.private_key_to_xonly_public_key(priv))
tr_prev = SpendableOutput(txid="bb"*32, vout=0,
                          output=TxOutput(amount=400_000_000, address=taproot_addr), height=1)
tr_tx = Transaction(inputs=[TxInput(txid="bb"*32, vout=0)],
                    outputs=[TxOutput(amount=399_000_000, address=p2wpkh)],
                    version=1, locktime=0)
tr_digest = tr_tx.sighash(0, tr_prev, txmod.SIGHASH_ALL)

# Deterministic seed-phrase fixture (portable derivation crosscheck + e2e).
from netcoin.wallet import private_key_from_seed_phrase
SEED_PHRASE = "net000 net001 net002 net003 net004 net005 net006 net007 net008 net009 net010 net011 net012 net013 net014 net015 net190"
seed_priv = private_key_from_seed_phrase(SEED_PHRASE, 0)
seed_pub = crypto.private_key_to_public_key(seed_priv, compressed=True)

print(json.dumps({
    "priv_hex": f"{priv:064x}",
    "taproot_address": taproot_addr,
    "p2sh_segwit_address": crypto.script_hash_to_p2sh_address(crypto.hash160(f"OP_0 {crypto.hash160(pub).hex()}".encode())),
    "taproot_xonly_hex": crypto.private_key_to_xonly_public_key(priv).hex(),
    "taproot_prevout_script_pubkey": tr_prev.output.effective_script_pubkey(),
    "taproot_sighash_digest_hex": tr_digest.hex(),
    "pubkey_hex": pub.hex(),
    "p2wpkh_address": p2wpkh,
    "legacy_address": legacy,
    "prevout_effective_script_pubkey": prev.output.effective_script_pubkey(),
    "sighash_all_digest_hex": digest.hex(),
    "signed_tx": t.to_dict(include_scripts=True, include_witness=True),
    "seed": {
        "phrase": SEED_PHRASE,
        "index": 0,
        "priv_hex": f"{seed_priv:064x}",
        "p2wpkh_address": crypto.public_key_to_p2wpkh_address(seed_pub),
    },
}, indent=2))
