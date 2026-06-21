"""Static block explorer generator for NetCoin."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Iterable

from .chain import Blockchain
from .tx import sats_to_amount


def esc(value: object) -> str:
    return html.escape(str(value))


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{esc(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 2rem; line-height: 1.45; }}
    code {{ background: #f4f4f4; padding: 0.1rem 0.25rem; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ddd; padding: 0.45rem; text-align: left; vertical-align: top; }}
    th {{ background: #f7f7f7; }}
    .hash {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; word-break: break-all; }}
  </style>
</head>
<body>
{body}
</body>
</html>"""


def build_search_index(chain: Blockchain) -> list[dict]:
    """A compact per-block index used by the client-side explorer search."""
    index = []
    for block in chain.chain:
        bh = block.hash()
        txids = []
        addresses = set()
        for tx in block.transactions:
            txids.append(tx.txid())
            for out in tx.outputs:
                if out.address:
                    addresses.add(out.address)
        index.append(
            {
                "height": block.header.height,
                "hash": bh,
                "timestamp": block.header.timestamp,
                "txids": txids,
                "addresses": sorted(addresses),
            }
        )
    return index


def _embed_json(data: object) -> str:
    # Safe to embed inside a <script> block: prevent a literal </script> or HTML
    # comment opener from terminating the element early.
    return json.dumps(data, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\!--")


SEARCH_SCRIPT = """
<script id="netcoin-index" type="application/json">__INDEX__</script>
<script>
(function () {
  var index = JSON.parse(document.getElementById('netcoin-index').textContent);
  var box = document.getElementById('q');
  var out = document.getElementById('results');
  if (!box) return;
  function link(b, label) {
    return '<a href="block-' + b.hash + '.html">' + label + '</a>';
  }
  function search(qRaw) {
    var q = (qRaw || '').trim().toLowerCase();
    if (!q) { out.innerHTML = ''; return; }
    var hits = [];
    for (var i = 0; i < index.length && hits.length < 50; i++) {
      var b = index[i];
      if (String(b.height) === q) { hits.push(link(b, 'Block ' + b.height + ' (height match)')); continue; }
      if (b.hash.indexOf(q) === 0) { hits.push(link(b, 'Block ' + b.height + ' (hash ' + b.hash.slice(0, 16) + '…)')); continue; }
      var matched = false;
      for (var t = 0; t < b.txids.length; t++) {
        if (b.txids[t].indexOf(q) === 0) { hits.push(link(b, 'tx ' + b.txids[t].slice(0, 16) + '… in block ' + b.height)); matched = true; break; }
      }
      if (matched) continue;
      for (var a = 0; a < b.addresses.length; a++) {
        if (b.addresses[a].toLowerCase().indexOf(q) !== -1) { hits.push(link(b, 'address ' + b.addresses[a] + ' in block ' + b.height)); break; }
      }
    }
    out.innerHTML = hits.length ? '<ul><li>' + hits.join('</li><li>') + '</li></ul>' : '<p>No matches.</p>';
  }
  box.addEventListener('input', function () { search(box.value); });
})();
</script>
"""


def generate_explorer(chain: Blockchain, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    blocks_rows = []
    for block in reversed(chain.chain):
        bh = block.hash()
        blocks_rows.append(
            f"<tr><td>{block.header.height}</td><td class='hash'><a href='block-{bh}.html'>{bh}</a></td>"
            f"<td>{len(block.transactions)}</td><td>{block.weight()}</td><td>{block.header.timestamp}</td></tr>"
        )
        tx_rows = []
        for tx in block.transactions:
            outputs = "<br>".join(f"{esc(o.address)}: {sats_to_amount(o.amount)} NET" for o in tx.outputs) or "none"
            tx_rows.append(
                f"<tr><td class='hash'>{tx.txid()}</td><td>{len(tx.inputs)}</td><td>{len(tx.outputs)}</td>"
                f"<td>{tx.weight()}</td><td>{outputs}</td></tr>"
            )
        block_body = f"""
<h1>NetCoin block {block.header.height}</h1>
<p><a href='index.html'>Back to chain</a></p>
<table>
<tr><th>Hash</th><td class='hash'>{bh}</td></tr>
<tr><th>Previous</th><td class='hash'>{block.header.previous_hash}</td></tr>
<tr><th>Merkle root</th><td class='hash'>{block.header.merkle_root}</td></tr>
<tr><th>Bits</th><td>{block.header.bits}</td></tr>
<tr><th>Nonce</th><td>{block.header.nonce}</td></tr>
<tr><th>Weight</th><td>{block.weight()}</td></tr>
</table>
<h2>Transactions</h2>
<table><tr><th>txid</th><th>inputs</th><th>outputs</th><th>weight</th><th>outputs</th></tr>{''.join(tx_rows)}</table>
"""
        (out / f"block-{bh}.html").write_text(page(f"NetCoin block {block.header.height}", block_body))

    info = chain.chain_info()
    mempool = chain.mempool_info()
    if mempool["entries"]:
        rows = "".join(
            f"<tr><td class='hash'>{esc(e['txid'])}</td><td>{e['vsize']}</td><td>{e['fee']}</td>"
            f"<td>{e['fee_rate_per_kvb']}</td><td>{'yes' if e['rbf'] else 'no'}</td></tr>"
            for e in mempool["entries"]
        )
        mempool_section = (
            f"<h2>Mempool ({mempool['size']} unconfirmed, {mempool['bytes']} vbytes)</h2>"
            "<table><tr><th>txid</th><th>vsize</th><th>fee (sats)</th><th>fee rate /kvB</th><th>rbf</th></tr>"
            f"{rows}</table>"
        )
    else:
        mempool_section = "<h2>Mempool</h2><p>No unconfirmed transactions.</p>"
    search_box = """
<h2>Search</h2>
<p><input id="q" type="search" placeholder="height, block hash, txid, or address" style="width:100%;max-width:560px;padding:.5rem"></p>
<div id="results"></div>
"""
    script = SEARCH_SCRIPT.replace("__INDEX__", _embed_json(build_search_index(chain)))
    index_body = f"""
<h1>NetCoin Explorer</h1>
<p>Height: <strong>{info['height']}</strong> | Tip: <code>{esc(info['tip_hash'])}</code> | Mempool: {info['mempool_transactions']}</p>
{search_box}
{mempool_section}
<table><tr><th>height</th><th>hash</th><th>transactions</th><th>weight</th><th>timestamp</th></tr>{''.join(blocks_rows)}</table>
{script}
"""
    index = out / "index.html"
    index.write_text(page("NetCoin Explorer", index_body))
    return index
