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
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .params import COIN, COINBASE_MATURITY, NETWORK_NAME, NODE_VERSION, TICKER
from .tx import SpendableOutput, Transaction, TxInput, TxOutput, amount_to_sats
from .wallet import Wallet

ADDRESS_TYPES = ["legacy", "segwit", "taproot", "p2sh-segwit"]


# --------------------------------------------------------------------------- #
# Remote node helpers
# --------------------------------------------------------------------------- #

def _node_get(node_url: str, path: str, timeout: int = 15) -> Dict[str, Any]:
    with urlopen(node_url.rstrip("/") + path, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _node_post(node_url: str, path: str, payload: Dict[str, Any], timeout: int = 15) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(node_url.rstrip("/") + path, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wallet_addresses(wallet: Wallet) -> Dict[str, str]:
    return {kind: wallet.address_for(kind) for kind in ADDRESS_TYPES}


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
    spendables.sort(key=lambda s: s.output.amount, reverse=True)
    selected: List[SpendableOutput] = []
    total = 0
    for utxo in spendables:
        selected.append(utxo)
        total += utxo.output.amount
        if total >= needed:
            break
    if total < needed:
        raise ValueError(f"insufficient balance: have {total / COIN:.8f}, need {needed / COIN:.8f} {TICKER}")

    inputs = [TxInput(txid=s.txid, vout=s.vout) for s in selected]
    outputs = [TxOutput(amount=amount_sats, address=to_address)]
    change = total - needed
    if change > 0:
        outputs.append(TxOutput(amount=change, address=from_address))
    tx = Transaction(inputs=inputs, outputs=outputs, locktime=0)
    for index, utxo in enumerate(selected):
        tx.sign_input(index, wallet.private_key, utxo)

    response = _node_post(node_url, "/tx", tx.to_dict())
    return {"txid": response.get("txid") or tx.txid(), "amount": amount_sats / COIN, "fee": fee_sats / COIN, "node_response": response}


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
 .wrap{max-width:880px;margin:0 auto;padding:20px}
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
   </div>
   <div id="loadBox" class="hide">
     <label>Paste wallet JSON</label><input id="loadJson" placeholder='{"network":"NetCoin",...}'>
     <label>Passphrase (if encrypted)</label><input id="loadPass" type="password">
     <button class="act" onclick="loadWallet()">Load</button>
   </div>
  </div>

  <div class="card hide" id="haveWallet">
   <h2>Balance</h2>
   <div class="big" id="balSpendable">—</div>
   <div class="muted" id="balDetail"></div>
   <label>Address (<span id="addrType">legacy</span>)</label>
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
   <label>To address</label><input id="sendTo" placeholder="Nc... / net1...">
   <div class="row">
    <div><label>Amount (NET)</label><input id="sendAmt" type="number" step="0.00000001" placeholder="1.0"></div>
    <div><label>Fee (NET)</label><input id="sendFee" type="number" step="0.00000001" value="0.01"></div>
   </div>
   <button class="act" onclick="send()">Send</button>
   <div id="sendOut" style="margin-top:10px"></div>
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
let CFG={}, ADDRS={}, curType="legacy";
const $=s=>document.querySelector(s);
async function api(p,opt){const r=await fetch(p,opt);const j=await r.json();if(!r.ok&&j.error)throw new Error(j.error);return j;}
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('on'));b.classList.add('on');
  ['wallet','faucet','explorer'].forEach(t=>$('#tab-'+t).classList.toggle('hide',t!==b.dataset.tab));
  if(b.dataset.tab==='explorer')loadLatest();
});
async function boot(){CFG=await api('/api/config');$('#netinfo').textContent=CFG.network+' · node '+CFG.node;
  $('#q').addEventListener('keydown',e=>{if(e.key==='Enter')search();});
  const w=await api('/api/wallet/current');if(w.address)showWallet(w);}
function showWallet(w){ADDRS=w.addresses;const sel=$('#typeSel');sel.innerHTML='';
  Object.keys(ADDRS).forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t;sel.appendChild(o);});
  $('#noWallet').classList.add('hide');$('#haveWallet').classList.remove('hide');$('#sendCard').classList.remove('hide');
  if(w.mnemonic){$('#mnemonicBox').innerHTML='<div class="warn"><b>Recovery phrase (shown once):</b><div class="mono">'+w.mnemonic+'</div>Write it down. <a href="data:application/json,'+encodeURIComponent(JSON.stringify(w.wallet_file))+'" download="wallet.json">Download wallet.json</a></div>';}
  switchType();}
function switchType(){curType=$('#typeSel').value||'legacy';$('#addrType').textContent=curType;
  $('#addr').textContent=ADDRS[curType];$('#faucetAddr').textContent=ADDRS[curType];
  $('#faucetLink').innerHTML=CFG.faucet?'<a class="act" style="display:inline-block;text-decoration:none" href="'+CFG.faucet+'" target="_blank">Open faucet ↗</a> <span class="muted">paste the address above</span>':'<span class="muted">No faucet configured.</span>';
  refreshBalance();}
async function newWallet(){try{const w=await api('/api/wallet/new',{method:'POST'});showWallet(w);}catch(e){alert(e.message)}}
async function loadWallet(){try{const w=await api('/api/wallet/load',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({json:$('#loadJson').value,passphrase:$('#loadPass').value})});showWallet(w);}catch(e){alert(e.message)}}
function copyAddr(){navigator.clipboard.writeText(ADDRS[curType]);}
async function refreshBalance(){try{const b=await api('/api/balance?address='+ADDRS[curType]);
  $('#balSpendable').innerHTML=(b.spendable||'0')+' <span class="muted" style="font-size:14px">'+CFG.ticker+'</span>';
  $('#balDetail').textContent='immature '+(b.immature||'0')+' · total '+(b.total||'0')+' · '+(b.utxo_count||0)+' UTXOs';}catch(e){$('#balDetail').textContent=e.message;}}
async function send(){const out=$('#sendOut');out.textContent='Sending…';try{
  const j=await api('/api/wallet/send',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({to:$('#sendTo').value.trim(),amount:$('#sendAmt').value,fee:$('#sendFee').value,from_type:curType})});
  out.innerHTML='<span class="ok">Sent!</span> txid <span class="mono">'+j.txid+'</span>';refreshBalance();}
  catch(e){out.innerHTML='<span class="err">'+e.message+'</span>';}}
function fmtTime(ts){return ts?new Date(ts*1000).toLocaleString():'';}
function short(h){return h?(h.length>26?h.slice(0,14)+'…'+h.slice(-8):h):'';}
function card(t,b){return '<div class="rcard"><div class="rtitle">'+t+'</div>'+b+'</div>';}
function kv(k,v){return '<div class="kv"><span class="muted">'+k+'</span><span>'+v+'</span></div>';}
function searchFor(q){$('#q').value=q;search();$('#searchOut').scrollIntoView({behavior:'smooth',block:'center'});}
function renderResult(d){
  if(!d||d.error)return '<div class="err">'+((d&&d.error)||'no result')+'</div>';
  if(d.type==='address'){const r=d.result,b=r.balance_net||{};
    const txs=(r.transaction_ids||[]).slice(0,30).map(t=>`<div class="lnk mono" onclick="searchFor('${t}')">${short(t)}</div>`).join('');
    return card('Address','<div class="mono sub">'+r.address+'</div>'+
      kv('Spendable','<b>'+(b.spendable||'0')+'</b> '+CFG.ticker)+kv('Immature',(b.immature||'0')+' '+CFG.ticker)+
      kv('Total',(b.total||'0')+' '+CFG.ticker)+kv('Transactions',r.transaction_count||0)+kv('UTXOs',r.utxo_count||0)+
      (txs?'<div class="muted" style="margin:10px 0 4px">Transaction IDs</div>'+txs:''));}
  if(d.type==='transaction'){const r=d.result,tx=r.tx||{};
    return card('Transaction','<div class="mono sub">'+(r.txid||'')+'</div>'+
      kv('Status',r.confirmed?'confirmed ✓':'unconfirmed')+kv('Block',r.block_height!=null?('#'+r.block_height):'mempool')+
      kv('Inputs',(tx.inputs||[]).length)+kv('Outputs',(tx.outputs||[]).length)+
      (r.block_hash?`<div class="lnk mono" onclick="searchFor('${r.block_hash}')">in block ${short(r.block_hash)}</div>`:''));}
  if(d.type==='block'){const r=d.result,h=r.header||{};
    return card('Block #'+h.height,'<div class="mono sub">'+(r.hash||'')+'</div>'+
      kv('Time',fmtTime(h.timestamp))+kv('Transactions',(r.transactions||[]).length)+kv('Weight',r.weight||'')+
      (h.previous_hash?`<div class="lnk mono" onclick="searchFor('${h.previous_hash}')">↑ previous ${short(h.previous_hash)}</div>`:''));}
  return '<pre class="mono">'+JSON.stringify(d,null,2)+'</pre>';}
async function search(){const out=$('#searchOut');if(!$('#q').value.trim()){out.innerHTML='';return;}out.innerHTML='<span class="muted">Searching…</span>';
  try{out.innerHTML=renderResult(await api('/api/search?q='+encodeURIComponent($('#q').value.trim())));}
  catch(e){out.innerHTML='<span class="err">'+e.message+'</span>';}}
async function loadLatest(){const tb=$('#latest').querySelector('tbody');tb.innerHTML='<tr><td class="muted">Loading…</td></tr>';
  try{const d=await api('/api/latest?n=15');tb.innerHTML='<tr><th>Height</th><th>Hash</th><th>Txns</th><th>Time</th></tr>'+
    d.blocks.map(b=>`<tr class="lnk" onclick="searchFor('${b.hash}')"><td>#${b.height}</td><td class="mono">${short(b.hash)}</td><td>${b.transactions}</td><td class="muted">${fmtTime(b.timestamp)}</td></tr>`).join('');}
  catch(e){tb.innerHTML='<tr><td class="err">'+e.message+'</td></tr>';}}
boot();
</script></body></html>"""


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #

def make_handler(node_url: str, faucet_url: str = ""):
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
                    self._send({"address": w.address_for("legacy"), "addresses": _wallet_addresses(w)} if w else {"address": None})
                elif parsed.path == "/api/balance":
                    address = parse_qs(parsed.query).get("address", [""])[0]
                    self._send(_node_get(node_url, f"/balance/{address}"))
                elif parsed.path == "/api/latest":
                    n = parse_qs(parsed.query).get("n", ["15"])[0]
                    self._send(_node_get(node_url, f"/latest?n={int(n)}"))
                elif parsed.path == "/api/search":
                    self._send(self._search(parse_qs(parsed.query).get("q", [""])[0]))
                else:
                    self._send({"error": "not found"}, status=404)
            except HTTPError as exc:
                self._send({"error": f"node returned HTTP {exc.code} for {parsed.path}"}, status=502)
            except (URLError, OSError):
                self._send({"error": "cannot reach the node"}, status=502)
            except Exception as exc:  # noqa: BLE001
                self._send({"error": str(exc)}, status=400)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/wallet/new":
                    wallet, mnemonic = Wallet.create_with_mnemonic()
                    state["wallet"] = wallet
                    self._send({
                        "address": wallet.address_for("legacy"),
                        "addresses": _wallet_addresses(wallet),
                        "mnemonic": mnemonic,
                        "wallet_file": wallet.to_dict(passphrase=None),
                    })
                elif parsed.path == "/api/wallet/load":
                    body = self._read()
                    wallet = self._load_wallet(body.get("json", ""), body.get("passphrase") or None)
                    state["wallet"] = wallet
                    self._send({"address": wallet.address_for("legacy"), "addresses": _wallet_addresses(wallet)})
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

        def _send_tx(self, body: Dict[str, Any]) -> Dict[str, Any]:
            wallet = state["wallet"]
            if wallet is None:
                raise ValueError("no wallet loaded")
            to = str(body.get("to", "")).strip()
            if not to:
                raise ValueError("destination address required")
            amount_sats = amount_to_sats(str(body.get("amount", "")))
            fee_sats = amount_to_sats(str(body.get("fee", "0") or "0"))
            from_type = str(body.get("from_type") or "legacy")
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
    server = ThreadingHTTPServer((host, int(port)), make_handler(node_url, faucet_url))
    print(f"NetCoin web wallet on http://{host}:{port}  (node: {node_url})")
    print("Local tool — keys stay on this machine. Do not expose this port publicly.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
