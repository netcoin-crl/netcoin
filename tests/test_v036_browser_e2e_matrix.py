import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v036_browser_e2e_matrix_source_gate_passes():
    proc = subprocess.run(
        [sys.executable, "tools/run_browser_e2e_matrix.py"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["surface_count"] == 6


def test_v036_playwright_spec_mentions_all_product_surfaces():
    spec = (ROOT / "sites/tests/e2e/netcoin-product-matrix.spec.ts").read_text(encoding="utf-8")
    for surface in ["wallet", "explorer", "markets", "faucet", "operator", "exchange"]:
        assert surface in spec
