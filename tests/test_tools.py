"""Tests for generated artifacts: the static explorer and the status dashboard."""

import importlib.util
import json
from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.explorer import generate_explorer
from netcoin.wallet import Wallet


def load_dashboard_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "dashboard.py"
    spec = importlib.util.spec_from_file_location("netcoin_dashboard", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_explorer_generation_produces_index_and_block_pages(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(2):
        chain.mine_block(miner.address)

    out = tmp_path / "explorer"
    index = generate_explorer(chain, out)

    assert index.exists()
    index_html = index.read_text()
    assert "NetCoin Explorer" in index_html
    assert chain.tip_hash() in index_html
    # One detail page per block (genesis + 2 mined = 3).
    block_pages = list(out.glob("block-*.html"))
    assert len(block_pages) == len(chain.chain)
    # Detail page for the tip exists and names the tip hash.
    tip_page = out / f"block-{chain.tip_hash()}.html"
    assert tip_page.exists()
    assert chain.tip_hash() in tip_page.read_text()


def test_explorer_embeds_searchable_index(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)

    out = tmp_path / "explorer"
    generate_explorer(chain, out)
    html = (out / "index.html").read_text()

    # The search UI and embedded index are present.
    assert 'id="q"' in html
    marker = 'id="netcoin-index" type="application/json">'
    start = html.index(marker) + len(marker)
    end = html.index("</script>", start)
    index = json.loads(html[start:end])

    heights = {b["height"] for b in index}
    assert {0, 1} <= heights
    assert any(b["hash"] == chain.tip_hash() for b in index)
    # The coinbase payout address is indexed for address search.
    assert any(miner.address in b["addresses"] for b in index)
    # Every block lists its coinbase txid.
    tip = next(b for b in index if b["hash"] == chain.tip_hash())
    assert chain.tip().transactions[0].txid() in tip["txids"]


def test_dashboard_renders_status_with_badges_and_escaping():
    dashboard = load_dashboard_module()
    status = {
        "ok": True,
        "generated_at": 1718900000,
        "seed_heights": {"seed1": 105, "seed2": 105, "seed3": 105},
        "seed_tips_match": True,
        "targets": {
            "seed1": {"ok": True, "url": "http://seed1.example/info", "height": 105, "tip_hash": "abc123"},
            "faucet": {"ok": False, "url": "http://seed1.example/faucet"},
        },
    }
    html = dashboard.render_dashboard(status)
    assert "NetCoin Testnet Status" in html
    assert "UP" in html and "DOWN" in html
    assert "abc123" in html
    assert "seed1" in html and "faucet" in html


def test_dashboard_escapes_untrusted_target_names():
    dashboard = load_dashboard_module()
    status = {
        "ok": False,
        "targets": {"<script>evil</script>": {"ok": False}},
    }
    html = dashboard.render_dashboard(status)
    # The raw script tag must not appear; it must be HTML-escaped.
    assert "<script>evil</script>" not in html
    assert "&lt;script&gt;evil&lt;/script&gt;" in html


def test_dashboard_handles_minimal_status():
    dashboard = load_dashboard_module()
    html = dashboard.render_dashboard({})
    assert "NetCoin Testnet Status" in html
    assert "DOWN" in html  # overall ok defaults to false


def test_verify_release_checksums(tmp_path: Path):
    spec = importlib.util.spec_from_file_location(
        "verify_release", Path(__file__).resolve().parents[1] / "tools" / "verify_release.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    dist = tmp_path / "dist"
    dist.mkdir()
    artifact = dist / "netcoin-test.zip"
    artifact.write_bytes(b"netcoin")
    digest = module.sha256_file(artifact)
    (dist / "SHA256SUMS").write_text(f"{digest}  {artifact.name}\n")

    assert module.verify_checksums(dist) == [artifact.name]
    assert module.main([str(dist)]) == 0
