"""Minimal local web UI: wallet + faucet + explorer over a remote NetCoin node.

Run with ``python -m netcoin web``. It serves a single page on 127.0.0.1 that
wraps the same operations as the CLI — create/load a wallet, check balance, send,
open the faucet, and browse the chain — so a newcomer can use NetCoin from a
browser instead of the command line.

Security model: this is a LOCAL tool. Private keys live only in this process and
the wallet file on your machine; signing happens locally and only the signed
transaction is sent to the node. Bind it to 127.0.0.1 (the default) and never
expose it publicly — it is not a custodial/hosted wallet.
"""
from __future__ import annotations

import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .params import COIN, COINBASE_MATURITY, MAX_WALLET_SEND_INPUTS, MAX_WALLET_SEND_WEIGHT, NETWORK_NAME, NODE_VERSION, TICKER
from .serialization import transaction_weight
from .tx import SpendableOutput, Transaction, TxInput, TxOutput, amount_to_sats
from .wallet import Wallet

# SegWit first and default; legacy/p2sh-segwit kept only so existing coins stay spendable.
ADDRESS_TYPES = ["segwit", "taproot", "legacy", "p2sh-segwit"]


# --------------------------------------------------------------------------- #
# Remote node helpers
# --------------------------------------------------------------------------- #

def _normalize_node_url(node_url: str) -> str:
    """Return a node/API base URL that works with the local web wallet.

    Public users often paste ``https://api.netcoin.online`` while the hosted
    reverse proxy exposes the node under ``/api``. Accept both forms so the
    local wallet does not appear broken because of a missing path segment.
    """
    base = (node_url or "").strip().rstrip("/")
    if base in {"https://api.netcoin.online", "http://api.netcoin.online"}:
        return base + "/api"
    return base


def _node_get(node_url: str, path: str, timeout: int = 15) -> Dict[str, Any]:
    base = _normalize_node_url(node_url)
    with urlopen(base + path, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _node_post(node_url: str, path: str, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    base = _normalize_node_url(node_url)
    body = json.dumps(payload).encode("utf-8")
    request = Request(base + path, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wallet_addresses(wallet: Wallet) -> Dict[str, str]:
    return {kind: wallet.address_for(kind) for kind in ADDRESS_TYPES}


# Rough per-input weight estimates (weight units) for coin selection without
# signing every trial. Conservative; the real weight is re-checked after signing.
_INPUT_WEIGHT_ESTIMATE = {"segwit": 275, "taproot": 240, "legacy": 600, "p2sh-segwit": 370,
                          "p2wpkh": 275, "p2tr": 240, "p2pkh": 600}
_OUTPUT_WEIGHT_ESTIMATE = 140


def _max_sendable_sats(by_value_desc, fee_sats: int) -> int:
    """Largest amount sendable in one transaction right now: the sum of the
    largest MAX_WALLET_SEND_INPUTS coins minus the fee (>=0)."""
    top = by_value_desc[:MAX_WALLET_SEND_INPUTS]
    return max(0, sum(s.output.amount for s in top) - fee_sats)


def build_and_broadcast(
    wallet: Wallet,
    to_address: str,
    amount_sats: int,
    fee_sats: int,
    from_type: str,
    node_url: str,
) -> Dict[str, Any]:
    """Build, sign locally, and broadcast a transaction using a remote node's UTXOs."""
    if amount_sats <= 0:
        raise ValueError("amount must be positive")
    if fee_sats < 0:
        raise ValueError("fee cannot be negative")
    from_address = wallet.address_for(from_type)

    info = _node_get(node_url, "/info").get("node", {})
    tip_height = int(info.get("height", 0))
    data = _node_get(node_url, f"/utxos?address={from_address}")
    spendables = [SpendableOutput.from_dict(item) for item in data.get("utxos", [])]
    # Drop immature coinbase outputs the node would reject anyway.
    spendables = [
        s for s in spendables
        if not s.coinbase or (tip_height - s.height) >= COINBASE_MATURITY
    ]
    if not spendables:
        raise ValueError("no spendable (mature) coins at this address yet")

    needed = amount_sats + fee_sats
    total_spendable = sum(s.output.amount for s in spendables)
    if total_spendable < needed:
        raise ValueError(
            f"insufficient spendable balance: have {total_spendable / COIN:.8f} {TICKER}, "
            f"need {(needed) / COIN:.8f} {TICKER}. Mining rewards must mature before spending."
        )

    # Consolidating coin selection (Option A): cover the target largest-first,
    # then top up with the smallest coins so every send also shrinks the UTXO
    # set — defragmenting passively instead of letting the coin count grow.
    by_value_desc = sorted(spendables, key=lambda s: s.output.amount, reverse=True)
    core: List[SpendableOutput] = []
    total = 0
    for utxo in by_value_desc:
        core.append(utxo)
        total += utxo.output.amount
        if total >= needed:
            break
    if total < needed:
        raise ValueError(f"insufficient balance: have {total / COIN:.8f}, need {needed / COIN:.8f} {TICKER}")
    if len(core) > MAX_WALLET_SEND_INPUTS:
        affordable = _max_sendable_sats(by_value_desc, fee_sats)
        raise ValueError(
            f"this send needs more than {MAX_WALLET_SEND_INPUTS} coins as inputs. "
            f"You can send up to {affordable / COIN:.8f} {TICKER} right now; "
            f"run `netcoin consolidate` (or send Max to yourself) to combine coins and send more."
        )
    extras = [u for u in sorted(spendables, key=lambda s: s.output.amount)
              if u.outpoint() not in {c.outpoint() for c in core}]

    # Choose how many dust coins to add using a WEIGHT ESTIMATE (per-input
    # weight is ~constant for a single-key wallet), signing only once at the end.
    # Signing per trial would be O(N^2) — the very cost this release fixes.
    per_input_weight = _INPUT_WEIGHT_ESTIMATE.get(from_type, 600)
    overhead = 400 + 2 * _OUTPUT_WEIGHT_ESTIMATE  # version/locktime/counts + up to 2 outputs
    max_by_weight = max(len(core), (MAX_WALLET_SEND_WEIGHT - overhead) // per_input_weight)
    cap = min(MAX_WALLET_SEND_INPUTS, max_by_weight)
    selected = list(core)
    for extra in extras:
        if len(selected) >= cap:
            break
        selected.append(extra)

    sel_total = sum(s.output.amount for s in selected)
    outputs = [TxOutput(amount=amount_sats, address=to_address)]
    change = sel_total - needed
    if change > 0:
        outputs.append(TxOutput(amount=change, address=from_address))
    tx = Transaction(inputs=[TxInput(txid=s.txid, vout=s.vout) for s in selected], outputs=outputs, locktime=0)
    for index, utxo in enumerate(selected):
        tx.sign_input(index, wallet.private_key, utxo)

    weight = transaction_weight(tx)
    if weight > MAX_WALLET_SEND_WEIGHT:
        # Estimate was optimistic: drop dust back to the minimal covering set.
        selected = list(core)
        sel_total = sum(s.output.amount for s in selected)
        outputs = [TxOutput(amount=amount_sats, address=to_address)]
        change = sel_total - needed
        if change > 0:
            outputs.append(TxOutput(amount=change, address=from_address))
        tx = Transaction(inputs=[TxInput(txid=s.txid, vout=s.vout) for s in selected], outputs=outputs, locktime=0)
        for index, utxo in enumerate(selected):
            tx.sign_input(index, wallet.private_key, utxo)
        weight = transaction_weight(tx)
        if weight > MAX_WALLET_SEND_WEIGHT:
            affordable = _max_sendable_sats(by_value_desc, fee_sats)
            raise ValueError(
                f"this send is too large to fit one transaction. You can send up to "
                f"{affordable / COIN:.8f} {TICKER} right now; run `netcoin consolidate` to send more."
            )

    response = _node_post(node_url, "/tx", tx.to_dict(), timeout=30)
    return {
        "txid": response.get("txid") or tx.txid(),
        "amount": amount_sats / COIN,
        "fee": fee_sats / COIN,
        "input_count": len(selected),
        "weight": weight,
        "change": change / COIN,
        "node_response": response,
    }


def consolidate_coins(
    wallet: Wallet,
    from_type: str,
    node_url: str,
    fee_sats: int = 10_000,
    max_inputs: int = MAX_WALLET_SEND_INPUTS,
) -> Dict[str, Any]:
    """Sweep many small UTXOs into one output back to the same address.

    Mining pays 50 NET per block, so a large balance is often hundreds of small
    coins; a big send then needs more inputs than the wallet/node policy allows
    (MAX_WALLET_SEND_INPUTS / MAX_WALLET_SEND_WEIGHT). Consolidation spends up
    to `max_inputs` coins per transaction back to yourself, in as many batches
    as needed. Batch outputs are unconfirmed until mined, so run it again after
    a confirmation if you want to converge further.
    """
    from_address = wallet.address_for(from_type)
    info = _node_get(node_url, "/info").get("node", {})
    tip_height = int(info.get("height", 0))
    data = _node_get(node_url, f"/utxos?address={from_address}")
    spendables = [SpendableOutput.from_dict(item) for item in data.get("utxos", [])]
    spendables = [s for s in spendables if not s.coinbase or (tip_height - s.height) >= COINBASE_MATURITY]
    spendables.sort(key=lambda s: s.output.amount)  # sweep the dust first
    if len(spendables) < 2:
        return {"batches": [], "note": "nothing to consolidate: fewer than two spendable coins", "utxos": len(spendables)}

    max_inputs = max(2, min(max_inputs, MAX_WALLET_SEND_INPUTS))
    batches: List[Dict[str, Any]] = []
    position = 0
    while position + 1 < len(spendables):
        size = min(max_inputs, len(spendables) - position)
        while size >= 2:
            batch = spendables[position:position + size]
            total = sum(s.output.amount for s in batch)
            if total <= fee_sats:
                return {"batches": batches, "note": "remaining coins are smaller than the fee; stopping", "utxos_left": len(spendables) - position}
            tx = Transaction(
                inputs=[TxInput(txid=s.txid, vout=s.vout) for s in batch],
                outputs=[TxOutput(amount=total - fee_sats, address=from_address)],
                locktime=0,
            )
            for index, utxo in enumerate(batch):
                tx.sign_input(index, wallet.private_key, utxo)
            if transaction_weight(tx) <= MAX_WALLET_SEND_WEIGHT:
                response = _node_post(node_url, "/tx", tx.to_dict(), timeout=30)
                batches.append({
                    "txid": response.get("txid") or tx.txid(),
                    "inputs": len(batch),
                    "consolidated": (total - fee_sats) / COIN,
                    "fee": fee_sats / COIN,
                })
                position += size
                break
            size //= 2  # too heavy: halve the batch and retry
        else:
            break
    return {"address": from_address, "batches": batches, "transactions": len(batches), "utxos_left_unbatched": max(0, len(spendables) - position)}


# --------------------------------------------------------------------------- #
# Single-page UI
# --------------------------------------------------------------------------- #

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>NetCoin Wallet</title>
<style>
 :root{--bg:#0e1116;--card:#171c24;--bd:#272e3a;--fg:#e6edf3;--mut:#8b97a7;--acc:#f7931a;--ok:#2ea043;--err:#f85149}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
 header{padding:18px 20px;border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:12px}
 header h1{font-size:18px;margin:0} .tag{color:var(--mut);font-size:13px}
 .wrap{max-width:960px;margin:0 auto;padding:20px}
 .tabs{display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap}
 .tabs button{background:var(--card);color:var(--fg);border:1px solid var(--bd);padding:8px 14px;border-radius:8px;cursor:pointer}
 .tabs button.on{border-color:var(--acc);color:var(--acc)}
 .card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:18px;margin-bottom:16px}
 h2{font-size:15px;margin:0 0 12px} label{display:block;color:var(--mut);font-size:13px;margin:10px 0 4px}
 input,select{width:100%;background:#0e131a;color:var(--fg);border:1px solid var(--bd);border-radius:8px;padding:9px}
 button.act{background:var(--acc);color:#1a1205;border:0;padding:10px 16px;border-radius:8px;font-weight:600;cursor:pointer;margin-top:12px}
 button.ghost{background:transparent;color:var(--fg);border:1px solid var(--bd);padding:8px 12px;border-radius:8px;cursor:pointer}
 .mono{font-family:ui-monospace,Menlo,monospace;word-break:break-all;font-size:13px}
 .row{display:flex;gap:10px;flex-wrap:wrap} .row>*{flex:1;min-width:140px}
 .muted{color:var(--mut)} .big{font-size:26px;font-weight:700} .ok{color:var(--ok)} .err{color:var(--err)}
 .warn{background:#3a2a08;border:1px solid #6b4d12;color:#f0c674;padding:10px;border-radius:8px;font-size:13px;margin-top:10px}
 table{width:100%;border-collapse:collapse;font-size:13px} td,th{text-align:left;padding:6px 4px;border-bottom:1px solid var(--bd)}
 .hide{display:none} a{color:var(--acc)}
 @media (min-width:900px){body{font-size:16px}.wrap{max-width:min(1280px,calc(100vw - 56px));padding:28px}.tabs{gap:10px}.tabs button{padding:10px 16px}.card{border-radius:16px;padding:22px}.row>*{min-width:220px}#tab-wallet{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;align-items:start}#tab-wallet.hide{display:none}#tab-wallet>.card{margin-bottom:0}#noWallet,#haveWallet{grid-column:1/-1}.big{font-size:34px}}
 @media (min-width:1180px){.wrap{max-width:min(1380px,calc(100vw - 72px));padding:36px}#tab-wallet{grid-template-columns:repeat(3,minmax(0,1fr))}#noWallet,#haveWallet{grid-column:span 2}}
 /* Responsive local-wallet desktop layout */
 .rcard{background:#0e131a;border:1px solid var(--bd);border-radius:10px;padding:14px}
 .rtitle{color:var(--acc);font-weight:700;margin-bottom:8px;font-size:15px}
 .sub{margin-bottom:10px;color:var(--mut)}
 .kv{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid var(--bd)}
 .kv:last-child{border-bottom:0}
 .lnk{cursor:pointer;color:var(--acc);padding:3px 0}.lnk:hover{text-decoration:underline}
 #latest th{color:var(--mut);font-weight:600}
</style></head><body>
<header><span class="big" style="color:var(--acc)">◈</span><h1>NetCoin Wallet</h1><span class="tag" id="netinfo">testnet</span></header>
<div class="wrap">
 <div class="tabs">
  <button class="on" data-tab="wallet">Wallet</button>
  <button data-tab="faucet">Faucet</button>
  <button data-tab="explorer">Explorer</button>
 </div>

 <section id="tab-wallet">
  <div class="card" id="noWallet">
   <h2>Get a wallet</h2>
   <p class="muted">Create a fresh testnet wallet, or load one you already have. Testnet NET has no real value.</p>
   <div class="row">
     <button class="act" onclick="newWallet()">Create new wallet</button>
     <button class="ghost" onclick="document.getElementById('loadBox').classList.toggle('hide')">Load existing</button>
     <button class="ghost" onclick="document.getElementById('pkBox').classList.toggle('hide')">Private key</button>
   </div>
   <div id="loadBox" class="hide">
     <label>Paste wallet JSON</label><input id="loadJson" placeholder='{"network":"NetCoin",...}'>
     <label>Passphrase (if encrypted)</label><input id="loadPass" type="password">
     <button class="act" onclick="loadWallet()">Load</button>
   </div>
   <div id="pkBox" class="hide">
     <label>Private key hex</label><input id="privHex" placeholder="64-character private key hex" autocomplete="off">
     <p class="muted">Use this only for single-key testnet wallets. Do not paste private keys into untrusted pages.</p>
     <button class="act" onclick="loadPrivateKey()">Log in with private key</button>
   </div>
  </div>

  <div class="card hide" id="haveWallet">
   <h2>Balance</h2>
   <div class="big" id="balSpendable">—</div>
   <div class="muted" id="balDetail"></div>
   <label>Address (<span id="addrType">segwit</span>)</label>
   <div class="mono" id="addr"></div>
   <div class="row" style="margin-top:8px">
     <button class="ghost" onclick="copyAddr()">Copy address</button>
     <button class="ghost" onclick="refreshBalance()">Refresh</button>
     <select id="typeSel" onchange="switchType()"></select>
   </div>
   <div id="mnemonicBox"></div>
  </div>

  <div class="card hide" id="sendCard">
   <h2>Send</h2>
   <label>Paste a payment link (optional)</label><input id="payLink" placeholder="netcoin:Nc...?amount=..." oninput="applyPayLink()">
   <label>To address</label><input id="sendTo" placeholder="Nc... / net1...">
   <div class="row">
    <div><label>Amount (NET)</label><input id="sendAmt" type="number" step="0.00000001" placeholder="1.0"></div>
    <div><label>Fee (NET)</label><input id="sendFee" type="number" step="0.00000001" value="0.01"></div>
   </div>
   <button class="act" onclick="send()">Send</button>
   <div id="sendOut" style="margin-top:10px"></div>
  </div>

  <div class="card hide" id="receiveCard">
   <h2>Request payment</h2>
   <p class="muted">Create a shareable payment link for your address.</p>
   <div class="row">
    <div><label>Amount (NET, optional)</label><input id="reqAmt" type="number" step="0.00000001" placeholder="any"></div>
    <div><label>Label (optional)</label><input id="reqLabel" placeholder="e.g. Coffee"></div>
   </div>
   <button class="act" onclick="makePayLink()">Create payment link</button>
   <div id="reqOut" style="margin-top:10px"></div>
  </div>

  <div class="card hide" id="historyCard">
   <h2>Recent activity</h2>
   <div id="historyOut" class="muted">—</div>
  </div>
 </section>

 <section id="tab-faucet" class="hide">
  <div class="card"><h2>Faucet</h2>
   <p class="muted">Get free testnet NET sent to your wallet address.</p>
   <div class="mono" id="faucetAddr">Create or load a wallet first.</div>
   <div id="faucetLink" style="margin-top:12px"></div>
  </div>
 </section>

 <section id="tab-explorer" class="hide">
  <div class="card"><h2>Search</h2>
   <div class="row"><input id="q" placeholder="height, block hash, txid, or address">
   <button class="act" style="flex:0 0 auto" onclick="search()">Search</button></div>
   <div id="searchOut" style="margin-top:10px"></div>
  </div>
  <div class="card"><h2>Latest blocks</h2><table id="latest"><tbody></tbody></table></div>
 </section>
</div>
	<script>
	let CFG={}, ADDRS={}, curType="segwit", BAL={};
	const $=s=>document.querySelector(s);
	const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
	const jsq=s=>JSON.stringify(String(s??''));
	function safeUrl(u){try{const x=new URL(String(u),location.href);return ['http:','https:'].includes(x.protocol)?x.href:'';}catch{return '';}}
	async function api(p,opt={},timeoutMs=35000){const ctrl=new AbortController();const timer=setTimeout(()=>ctrl.abort(),timeoutMs);
  try{opt=Object.assign({},opt,{signal:ctrl.signal});const r=await fetch(p,opt);const text=await r.text();let j={};
    try{j=text?JSON.parse(text):{};}catch(e){throw new Error('node returned non-JSON response');}
    if(!r.ok&&j.error)throw new Error(j.error);if(!r.ok)throw new Error('HTTP '+r.status);return j;}
  catch(e){if(e.name==='AbortError')throw new Error('request timed out; check mempool/explorer, then try again');throw e;}
  finally{clearTimeout(timer);}}
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('on'));b.classList.add('on');
  ['wallet','faucet','explorer'].forEach(t=>$('#tab-'+t).classList.toggle('hide',t!==b.dataset.tab));
  if(b.dataset.tab==='explorer')loadLatest();
});
function nodeHelp(msg){return esc(msg)+'<div class="warn"><b>Node connection help</b><br>Use the public API proxy when home Wi-Fi blocks the seed port. If your network blocks api.netcoin.online, use the direct-IP API:<div class="mono">python -m netcoin web --node http://18.220.89.128/api --faucet https://faucet.netcoin.online</div><br>Configured node: <span class="mono">'+esc(CFG.node||'unknown')+'</span></div>';}
async function boot(){CFG=await api('/api/config');$('#netinfo').textContent=CFG.network+' · node '+CFG.node;
  $('#q').addEventListener('keydown',e=>{if(e.key==='Enter')search();});
  const w=await api('/api/wallet/current');if(w.address)showWallet(w);}
function showWallet(w){ADDRS=w.addresses;const sel=$('#typeSel');sel.innerHTML='';
  Object.keys(ADDRS).forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t;sel.appendChild(o);});
  $('#noWallet').classList.add('hide');$('#haveWallet').classList.remove('hide');$('#sendCard').classList.remove('hide');$('#receiveCard').classList.remove('hide');$('#historyCard').classList.remove('hide');
	  if(w.mnemonic){$('#mnemonicBox').innerHTML='<div class="warn"><b>Recovery phrase (shown once):</b><div class="mono">'+esc(w.mnemonic)+'</div>Write it down. <a href="data:application/json,'+encodeURIComponent(JSON.stringify(w.wallet_file))+'" download="wallet.json">Download wallet.json</a></div>';}
	  switchType();}
function switchType(){curType=$('#typeSel').value||'segwit';$('#addrType').textContent=curType;
  $('#addr').textContent=ADDRS[curType];$('#faucetAddr').textContent=ADDRS[curType];
	  const faucet=safeUrl(CFG.faucet);
	  $('#faucetLink').innerHTML=faucet?'<a class="act" style="display:inline-block;text-decoration:none" href="'+esc(faucet)+'" target="_blank" rel="noopener noreferrer">Open faucet ↗</a> <span class="muted">paste the address above</span>':'<span class="muted">No faucet configured.</span>';
	  refreshBalance();loadHistory();}
function openTx(t){document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('on'));
  const eb=document.querySelector('.tabs button[data-tab="explorer"]');eb.classList.add('on');
  ['wallet','faucet','explorer'].forEach(tb=>$('#tab-'+tb).classList.toggle('hide',tb!=='explorer'));
  loadLatest();searchFor(t);}
async function loadHistory(){const out=$('#historyOut');try{
  const d=await api('/api/history?address='+ADDRS[curType]);
  const ids=(d.transaction_ids||[]).slice(-15).reverse();
	  out.innerHTML=ids.length?(`<div class="muted">${esc(d.transaction_count)} total · newest first</div>`+ids.map(t=>`<div class="lnk mono" onclick="openTx(${jsq(t)})">${esc(short(t))}</div>`).join('')):'<span class="muted">No transactions yet for this address.</span>';
	}catch(e){out.innerHTML=nodeHelp(e.message);}}
async function newWallet(){try{const w=await api('/api/wallet/new',{method:'POST'});showWallet(w);}catch(e){alert(e.message)}}
async function loadWallet(){try{const w=await api('/api/wallet/load',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({json:$('#loadJson').value,passphrase:$('#loadPass').value})});showWallet(w);}catch(e){alert(e.message)}}
async function loadPrivateKey(){try{const w=await api('/api/wallet/private-key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({private_key_hex:$('#privHex').value})});showWallet(w);}catch(e){alert(e.message)}}
function copyAddr(){navigator.clipboard.writeText(ADDRS[curType]);}
async function refreshBalance(){try{const b=await api('/api/balance?address='+ADDRS[curType]);BAL=b;
	  $('#balSpendable').innerHTML=esc(b.spendable||'0')+' <span class="muted" style="font-size:14px">'+esc(CFG.ticker)+'</span>';
  $('#balDetail').textContent='immature '+(b.immature||'0')+' · total '+(b.total||'0')+' · '+(b.utxo_count||0)+' UTXOs';}catch(e){$('#balSpendable').textContent='—';$('#balDetail').innerHTML=nodeHelp(e.message);}}
async function makePayLink(){const out=$('#reqOut');try{
  const p=new URLSearchParams({address:ADDRS[curType]});
  if($('#reqAmt').value)p.set('amount',$('#reqAmt').value);
  if($('#reqLabel').value)p.set('label',$('#reqLabel').value);
  const d=await api('/api/payment-uri?'+p.toString());
	  out.innerHTML=`<div class="muted">Share this link:</div><div class="mono" id="payUriOut">${esc(d.uri)}</div><button class="ghost" style="margin-top:8px" onclick="navigator.clipboard.writeText(document.getElementById('payUriOut').textContent)">Copy link</button>`;
	}catch(e){out.innerHTML=nodeHelp(e.message);}}
async function applyPayLink(){const v=$('#payLink').value.trim();if(!v.toLowerCase().startsWith('netcoin:'))return;try{
  const d=await api('/api/parse-uri?uri='+encodeURIComponent(v));
  $('#sendTo').value=d.address;if(d.amount)$('#sendAmt').value=d.amount;
}catch(e){}}
async function send(){const out=$('#sendOut'),btn=$('#sendBtn');
  const amount=parseFloat($('#sendAmt').value||'0'),fee=parseFloat($('#sendFee').value||'0'),spendable=parseFloat(BAL.spendable||'0');
  if(!$('#sendTo').value.trim()){out.innerHTML='<span class="err">Destination address required.</span>';return;}
  if(!(amount>0)){out.innerHTML='<span class="err">Amount must be positive.</span>';return;}
  if((amount+fee)>spendable){out.innerHTML='<span class="err">Amount plus fee exceeds spendable balance. Spendable: '+esc(BAL.spendable||'0')+' '+esc(CFG.ticker)+'</span>';return;}
  if(spendable>0&&(amount+fee)>spendable*0.9&&!confirm('This sends more than 90% of your spendable balance. Continue?'))return;
  if(btn){btn.disabled=true;btn.textContent='Sending…';}out.textContent='Preparing and broadcasting transaction…';try{
  const j=await api('/api/wallet/send',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({to:$('#sendTo').value.trim(),amount:$('#sendAmt').value,fee:$('#sendFee').value,from_type:curType})},45000);
	  out.innerHTML='<span class="ok">Sent!</span> txid <span class="mono">'+esc(j.txid)+'</span><div class="muted">inputs '+esc(j.input_count||'?')+' · weight '+esc(j.weight||'?')+' · change '+esc(j.change||0)+' '+esc(CFG.ticker)+'</div>';refreshBalance();loadHistory();}
	  catch(e){out.innerHTML=nodeHelp(e.message)+'<div class="warn">If this timed out after a large send, check the mempool and mine one block before trying again.</div>';}
  finally{if(btn){btn.disabled=false;btn.textContent='Send';}}}
function fmtTime(ts){return ts?new Date(ts*1000).toLocaleString():'';}
function short(h){return h?(h.length>26?h.slice(0,14)+'…'+h.slice(-8):h):'';}
	function card(t,b){return '<div class="rcard"><div class="rtitle">'+esc(t)+'</div>'+b+'</div>';}
	function kv(k,v){return '<div class="kv"><span class="muted">'+esc(k)+'</span><span>'+v+'</span></div>';}
function searchFor(q){$('#q').value=q;search();$('#searchOut').scrollIntoView({behavior:'smooth',block:'center'});}
function renderResult(d){
	  if(!d||d.error)return '<div class="err">'+esc((d&&d.error)||'no result')+'</div>';
	  if(d.type==='address'){const r=d.result,b=r.balance_net||{};
	    const txs=(r.transaction_ids||[]).slice(0,30).map(t=>`<div class="lnk mono" onclick="searchFor(${jsq(t)})">${esc(short(t))}</div>`).join('');
	    return card('Address','<div class="mono sub">'+esc(r.address)+'</div>'+
	      kv('Spendable','<b>'+esc(b.spendable||'0')+'</b> '+esc(CFG.ticker))+kv('Immature',esc(b.immature||'0')+' '+esc(CFG.ticker))+
	      kv('Total',esc(b.total||'0')+' '+esc(CFG.ticker))+kv('Transactions',esc(r.transaction_count||0))+kv('UTXOs',esc(r.utxo_count||0))+
	      (txs?'<div class="muted" style="margin:10px 0 4px">Transaction IDs</div>'+txs:''));}
	  if(d.type==='transaction'){const r=d.result,tx=r.tx||{};
	    return card('Transaction','<div class="mono sub">'+esc(r.txid||'')+'</div>'+
	      kv('Status',r.confirmed?'confirmed ✓':'unconfirmed')+kv('Block',r.block_height!=null?('#'+esc(r.block_height)):'mempool')+
	      kv('Inputs',esc((tx.inputs||[]).length))+kv('Outputs',esc((tx.outputs||[]).length))+
	      (r.block_hash?`<div class="lnk mono" onclick="searchFor(${jsq(r.block_hash)})">in block ${esc(short(r.block_hash))}</div>`:''));}
	  if(d.type==='block'){const r=d.result,h=r.header||{};
	    return card('Block #'+esc(h.height),'<div class="mono sub">'+esc(r.hash||'')+'</div>'+
	      kv('Time',esc(fmtTime(h.timestamp)))+kv('Transactions',esc((r.transactions||[]).length))+kv('Weight',esc(r.weight||''))+
	      (h.previous_hash?`<div class="lnk mono" onclick="searchFor(${jsq(h.previous_hash)})">↑ previous ${esc(short(h.previous_hash))}</div>`:''));}
	  return '<pre class="mono">'+esc(JSON.stringify(d,null,2))+'</pre>';}
async function search(){const out=$('#searchOut');if(!$('#q').value.trim()){out.innerHTML='';return;}out.innerHTML='<span class="muted">Searching…</span>';
  try{out.innerHTML=renderResult(await api('/api/search?q='+encodeURIComponent($('#q').value.trim())));}
	  catch(e){out.innerHTML=nodeHelp(e.message);}}
	async function loadLatest(){const tb=$('#latest').querySelector('tbody');tb.innerHTML='<tr><td class="muted">Loading…</td></tr>';
	  try{const d=await api('/api/latest?n=15');tb.innerHTML='<tr><th>Height</th><th>Hash</th><th>Txns</th><th>Time</th></tr>'+
	    d.blocks.map(b=>`<tr class="lnk" onclick="searchFor(${jsq(b.hash)})"><td>#${esc(b.height)}</td><td class="mono">${esc(short(b.hash))}</td><td>${esc(b.transactions)}</td><td class="muted">${esc(fmtTime(b.timestamp))}</td></tr>`).join('');}
	  catch(e){tb.innerHTML='<tr><td>'+nodeHelp(e.message)+'</td></tr>';}}
boot();
</script></body></html>"""


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #

def make_handler(node_url: str, faucet_url: str = ""):
    node_url = _normalize_node_url(node_url)
    state: Dict[str, Optional[Wallet]] = {"wallet": None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # quiet
            return

        def _send(self, payload: Dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    data = PAGE.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                elif parsed.path == "/api/config":
                    self._send({"node": node_url, "faucet": faucet_url, "network": NETWORK_NAME, "ticker": TICKER, "version": NODE_VERSION})
                elif parsed.path == "/api/wallet/current":
                    w = state["wallet"]
                    self._send({"address": w.address_for("segwit"), "addresses": _wallet_addresses(w)} if w else {"address": None})
                elif parsed.path == "/api/balance":
                    address = parse_qs(parsed.query).get("address", [""])[0]
                    self._send(_node_get(node_url, f"/balance/{address}"))
                elif parsed.path == "/api/history":
                    address = parse_qs(parsed.query).get("address", [""])[0]
                    self._send(_node_get(node_url, f"/address/{address}"))
                elif parsed.path == "/api/latest":
                    n = parse_qs(parsed.query).get("n", ["15"])[0]
                    self._send(_node_get(node_url, f"/latest?n={int(n)}"))
                elif parsed.path == "/api/search":
                    self._send(self._search(parse_qs(parsed.query).get("q", [""])[0]))
                elif parsed.path == "/api/payment-uri":
                    from .paymenturi import build_uri
                    q = parse_qs(parsed.query)
                    self._send({"uri": build_uri(
                        q.get("address", [""])[0],
                        amount=q.get("amount", [None])[0] or None,
                        label=q.get("label", [None])[0] or None,
                        message=q.get("message", [None])[0] or None,
                    )})
                elif parsed.path == "/api/parse-uri":
                    from .paymenturi import parse_uri
                    self._send(parse_uri(parse_qs(parsed.query).get("uri", [""])[0]))
                else:
                    self._send({"error": "not found"}, status=404)
            except HTTPError as exc:
                self._send({"error": f"node returned HTTP {exc.code} for {parsed.path}"}, status=502)
            except (URLError, OSError) as exc:
                self._send({"error": "cannot reach the node", "node": node_url, "hint": "Use --node https://api.netcoin.online/api, or start a local node and use --node http://127.0.0.1:28444", "detail": str(exc)}, status=502)
            except Exception as exc:  # noqa: BLE001
                self._send({"error": str(exc)}, status=400)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/wallet/new":
                    wallet, mnemonic = Wallet.create_with_mnemonic()
                    state["wallet"] = wallet
                    self._send({
                        "address": wallet.address_for("segwit"),
                        "addresses": _wallet_addresses(wallet),
                        "mnemonic": mnemonic,
                        "wallet_file": wallet.to_dict(passphrase=None),
                    })
                elif parsed.path == "/api/wallet/load":
                    body = self._read()
                    wallet = self._load_wallet(body.get("json", ""), body.get("passphrase") or None)
                    state["wallet"] = wallet
                    self._send({"address": wallet.address_for("segwit"), "addresses": _wallet_addresses(wallet)})
                elif parsed.path == "/api/wallet/private-key":
                    body = self._read()
                    wallet = self._load_private_key(body.get("private_key_hex", ""))
                    state["wallet"] = wallet
                    self._send({"address": wallet.address_for("segwit"), "addresses": _wallet_addresses(wallet)})
                elif parsed.path == "/api/wallet/send":
                    self._send(self._send_tx(self._read()))
                else:
                    self._send({"error": "not found"}, status=404)
            except HTTPError as exc:
                self._send({"error": f"node rejected the request (HTTP {exc.code})"}, status=400)
            except Exception as exc:  # noqa: BLE001
                self._send({"error": str(exc)}, status=400)

        def _load_wallet(self, raw_json: str, passphrase: Optional[str]) -> Wallet:
            if not raw_json.strip():
                raise ValueError("paste your wallet JSON")
            # Validate it parses, then load via the standard (encryption-aware) path.
            try:
                json.loads(raw_json)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"that isn't valid wallet JSON ({exc.msg}). Paste the full contents "
                    f"of your wallet .json file (an address goes in the Explorer, not here)."
                ) from exc
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
                handle.write(raw_json)
                path = handle.name
            try:
                return Wallet.load(path, passphrase=passphrase)
            finally:
                Path(path).unlink(missing_ok=True)

        def _load_private_key(self, private_key_hex: str) -> Wallet:
            clean = str(private_key_hex or "").strip().removeprefix("0x").replace(" ", "").replace("\n", "")
            if len(clean) != 64:
                raise ValueError("private key must be 64 hex characters")
            return Wallet.from_dict({"private_key_hex": clean})

        def _send_tx(self, body: Dict[str, Any]) -> Dict[str, Any]:
            wallet = state["wallet"]
            if wallet is None:
                raise ValueError("no wallet loaded")
            to = str(body.get("to", "")).strip()
            if not to:
                raise ValueError("destination address required")
            amount_sats = amount_to_sats(str(body.get("amount", "")))
            fee_sats = amount_to_sats(str(body.get("fee", "0") or "0"))
            from_type = str(body.get("from_type") or "segwit")
            return build_and_broadcast(wallet, to, amount_sats, fee_sats, from_type, node_url)

        def _search(self, query: str) -> Dict[str, Any]:
            query = query.strip()
            if not query:
                return {"error": "empty query"}
            # Try, in order: height -> block, txid, address.
            if query.isdigit():
                headers = _node_get(node_url, f"/headers?start={int(query)}&limit=1").get("headers", [])
                if headers and int(headers[0].get("height", -1)) == int(query):
                    return {"type": "block", "result": _node_get(node_url, f"/block/{headers[0]['hash']}")}
            for path, kind in ((f"/tx/{query}", "transaction"), (f"/address/{query}", "address"), (f"/block/{query}", "block")):
                try:
                    return {"type": kind, "result": _node_get(node_url, path)}
                except HTTPError:
                    continue
            return {"error": "no block, transaction, or address matched"}

    return Handler


def run_web_wallet(node_url: str, faucet_url: str = "", host: str = "127.0.0.1", port: int = 8088) -> None:
    node_url = _normalize_node_url(node_url)
    server = ThreadingHTTPServer((host, int(port)), make_handler(node_url, faucet_url))
    print(f"NetCoin web wallet on http://{host}:{port}  (node: {node_url})")
    print("Local tool — keys stay on this machine. Do not expose this port publicly.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
