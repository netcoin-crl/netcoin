from __future__ import annotations

import json
from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.explorer_server import fee_estimates_payload, percentile_fee_rate

ROOT = Path(__file__).resolve().parents[1]
EXPLORER = ROOT / "sites" / "explorer"


def test_mempool_page_uses_live_asset_versions() -> None:
    html = (EXPLORER / "mempool.html").read_text(encoding="utf-8")
    assert "explorer-pro.css?v=20260711-m1-mempool-live" in html
    assert "explorer-pro.js?v=20260711-m1-mempool-live" in html
    assert "Content-Security-Policy" in html
    assert "connect-src 'self'" in html


def test_explorer_pro_js_wires_sse_and_fee_percentiles() -> None:
    js = (EXPLORER / "explorer-pro.js").read_text(encoding="utf-8")
    for token in [
        "new EventSource('/api/events/stream')",
        "api('/fee-estimates')",
        "fee_rate_percentiles",
        "10th percentile",
        "50th percentile",
        "90th percentile",
        "renderMempool({ wireStream: false })",
    ]:
        assert token in js
    assert "/api/explorer/mempool" not in js


def test_fee_estimates_fallback_file_matches_m1_contract() -> None:
    payload = json.loads((ROOT / "api" / "fee-estimates").read_text(encoding="utf-8"))
    assert payload["status"] == "source-fallback"
    assert payload["assumed_vbytes"] == 200
    assert sorted(payload["fee_rate_percentiles"]) == ["p10", "p50", "p90"]
    assert payload["fee_rate_percentiles"]["p90"]["label"] == "90th percentile"


def test_fee_estimates_payload_exposes_m1_percentile_bands(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    payload = fee_estimates_payload(chain)
    assert payload["mempool_depth"] == 0
    assert payload["source"] == "min-relay-fallback"
    assert sorted(payload["fee_rate_percentiles"]) == ["p10", "p50", "p90"]
    for key in ["p10", "p50", "p90"]:
        band = payload["fee_rate_percentiles"][key]
        assert band["fee_rate_per_kvb"] >= 1000
        assert band["estimated_fee_sats"] >= 1


def test_percentile_fee_rate_nearest_rank() -> None:
    assert percentile_fee_rate([1000, 2000, 3000, 4000, 5000], 10) == 1000
    assert percentile_fee_rate([1000, 2000, 3000, 4000, 5000], 50) == 3000
    assert percentile_fee_rate([1000, 2000, 3000, 4000, 5000], 90) == 5000
