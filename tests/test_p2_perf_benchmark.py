from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.run_perf_benchmark import DEFAULT_THRESHOLDS, evaluate_thresholds, run_benchmark

ROOT = Path(__file__).resolve().parents[1]


def test_perf_threshold_evaluation_reports_expected_failures():
    metrics = {
        "block_validation": {"p50_ms": 1, "p99_ms": 2},
        "restart_replay": {"elapsed_ms": 3, "ok": True},
        "memory": {"max_rss_mb": 4},
        "mempool_accept": {"transactions_per_second": 5},
    }
    thresholds = {
        "block_validation_p50_ms_max": 0.5,
        "block_validation_p99_ms_max": 3,
        "restart_replay_ms_max": 4,
        "memory_rss_mb_max": 5,
        "mempool_accept_tps_min": 6,
    }
    assert evaluate_thresholds(metrics, thresholds) == [
        "block_validation_p50_ms",
        "mempool_accept_tps",
    ]


def test_perf_benchmark_source_smoke(tmp_path: Path):
    report = run_benchmark(
        blocks=2,
        bootstrap_blocks=101,
        mempool_transactions=2,
        thresholds=dict(DEFAULT_THRESHOLDS),
        root_dir=tmp_path / "perf",
        keep_artifacts=True,
    )
    assert report["ok"] is True, report
    assert report["schema"] == "netcoin-perf-benchmark-v1"
    assert report["parameters"]["effective_bootstrap_blocks"] >= 102
    assert report["metrics"]["block_validation"]["count"] == 2
    assert report["metrics"]["restart_replay"]["ok"] is True
    assert report["metrics"]["mempool_accept"]["accepted"] == 2
    assert report["metrics"]["memory"]["max_rss_mb"] > 0


def test_perf_benchmark_cli_writes_json(tmp_path: Path):
    out = tmp_path / "perf.json"
    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_perf_benchmark.py",
            "--blocks",
            "1",
            "--bootstrap-blocks",
            "101",
            "--mempool-transactions",
            "1",
            "--root-dir",
            str(tmp_path / "cli-perf"),
            "--keep-artifacts",
            "--out",
            str(out),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["parameters"]["effective_bootstrap_blocks"] >= 101
    assert payload["metrics"]["block_validation"]["count"] == 1


def test_perf_benchmark_rejects_too_small_bootstrap():
    with pytest.raises(ValueError, match="bootstrap_blocks"):
        run_benchmark(
            blocks=1,
            bootstrap_blocks=1,
            mempool_transactions=1,
            thresholds=dict(DEFAULT_THRESHOLDS),
        )


def test_perf_workflow_and_docs_are_wired():
    workflow = (ROOT / ".github" / "workflows" / "perf-benchmark.yml").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "PERFORMANCE_BENCHMARKS.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "tools/run_perf_benchmark.py" in workflow
    assert "reports/perf/perf_benchmark_report.json" in workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4" in workflow
    assert "netcoin-perf-benchmark-v1" in docs
    assert "perf-benchmark-check" in makefile
