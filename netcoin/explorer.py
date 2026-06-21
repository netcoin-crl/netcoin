"""Static block explorer generator for NetCoin."""

from __future__ import annotations

import html
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
    index_body = f"""
<h1>NetCoin Explorer</h1>
<p>Height: <strong>{info['height']}</strong> | Tip: <code>{esc(info['tip_hash'])}</code> | Mempool: {info['mempool_transactions']}</p>
<table><tr><th>height</th><th>hash</th><th>transactions</th><th>weight</th><th>timestamp</th></tr>{''.join(blocks_rows)}</table>
"""
    index = out / "index.html"
    index.write_text(page("NetCoin Explorer", index_body))
    return index
