from __future__ import annotations

import importlib
import json
from pathlib import Path

from netcoin.competitive import COMPETITIVE_AREAS, build_competitive_gap_report, feature_count

ROOT = Path(__file__).resolve().parents[1]


def test_competitive_registry_is_broad_enough():
    assert len(COMPETITIVE_AREAS) >= 19
    assert feature_count() >= 170
    report = build_competitive_gap_report()
    assert report["production_claim"] is False
    assert report["area_count"] == len(COMPETITIVE_AREAS)
    assert report["feature_count"] == feature_count()


def test_each_competitive_area_has_module_doc_and_config():
    for area in COMPETITIVE_AREAS:
        module = importlib.import_module(f"netcoin.competitive.{area.module}")
        controls = module.default_controls()
        assert controls["production_ready"] is False
        assert controls["requires_external_audit"] is True
        assert len(module.readiness_gates()) >= 8
        doc_path = ROOT / area.doc_path
        config_path = ROOT / area.config_path
        assert doc_path.exists(), area.doc_path
        assert config_path.exists(), area.config_path
        cfg = json.loads(config_path.read_text())
        assert cfg["area"] == area.slug
        assert cfg["production_ready"] is False
        assert len(cfg["features"]) == len(area.features)


def test_competitive_docs_index_covers_every_area():
    index = (ROOT / "docs/competitive/README.md").read_text()
    for area in COMPETITIVE_AREAS:
        assert area.title in index
        assert f"{area.slug}.md" in index


def test_gap_report_tool_json(tmp_path):
    import subprocess
    import sys

    out = tmp_path / "competitive.json"
    subprocess.check_call([sys.executable, "tools/competitive_gap_report.py", "--json", "--out", str(out)], cwd=ROOT)
    data = json.loads(out.read_text())
    assert data["schema"] == "netcoin-competitive-scaffold-v1"
    assert data["feature_count"] >= 170
