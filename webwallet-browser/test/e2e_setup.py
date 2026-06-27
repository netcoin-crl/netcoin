"""Phase A: build a local chain, mine matured funds to a JS-derived address,
dump the wallet + UTXOs for the JS builder."""
import json, sys, tempfile, pathlib
from netcoin.chain import Blockchain
from netcoin import crypto
sys.path.insert(0, str(pathlib.Path(__file__).parent))

fx = json.load(open("webwallet-browser/test/fixtures.json"))
priv = int(fx["seed"]["priv_hex"], 16)
addr = fx["seed"]["p2wpkh_address"]

data_dir = tempfile.mkdtemp(prefix="netcoin-e2e-")
chain = Blockchain(data_dir)
for _ in range(101):           # 101 blocks -> block-1 coinbase is mature (>=100 confs)
    chain.mine_block(addr)

utxos = []
for u in chain.utxos_for_address(addr, include_immature=False):
    utxos.append({
        "txid": u.txid, "vout": u.vout, "amount": u.output.amount,
        "address": u.output.address,
        "script_pubkey": u.output.effective_script_pubkey(),
    })
# recipient = same seed, index 1 (a different address)
from netcoin.wallet import private_key_from_seed_phrase
rpriv = private_key_from_seed_phrase(fx["seed"]["phrase"], index=1)
raddr = crypto.public_key_to_p2wpkh_address(crypto.private_key_to_public_key(rpriv))

out = {"data_dir": data_dir, "priv_hex": fx["seed"]["priv_hex"], "address": addr,
       "change_address": addr, "recipient_address": raddr,
       "height": chain.height(), "spendable_utxos": utxos[:5]}
json.dump(out, open("/tmp/e2e_state.json", "w"))
print("mined to height", chain.height(), "| spendable utxos:", len(utxos),
      "| first utxo amount:", utxos[0]["amount"] if utxos else None)
print("recipient:", raddr)
