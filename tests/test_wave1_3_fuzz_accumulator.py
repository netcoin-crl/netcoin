from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.accumulate_fuzz_history import accumulate

ROOT = Path(__file__).resolve().parents[1]


def test_accumulate_fuzz_history_sums_only_real_ok_reports(tmp_path: Path):
    history = tmp_path / "history"
    history.mkdir()
    (history / "ok1.json").write_text(
        json.dumps(
            {
                "ok": True,
                "seed": 1,
                "iterations": 3,
                "duration_seconds": 0.1,
                "total_cases": 6,
                "targets": [
                    {"target": "tx-dict", "cases": 3},
                    {"target": "rawtx", "cases": 3},
                ],
            }
        ),
        encoding="utf-8",
    )
    (history / "failed.json").write_text(json.dumps({"ok": False, "total_cases": 999}), encoding="utf-8")

    report = accumulate(history, goal_cases=100)
    assert report["ok"] is True
    assert report["report_count"] == 1
    assert report["total_cases"] == 6
    assert report["goal_progress"] == 0.06
    assert report["target_totals"] == {"rawtx": 3, "tx-dict": 3}


def test_accumulate_fuzz_history_cli_writes_summary(tmp_path: Path):
    history = tmp_path / "history"
    out = tmp_path / "summary.json"
    history.mkdir()
    (history / "ok.json").write_text(
        json.dumps({"ok": True, "total_cases": 2, "targets": [{"target": "script", "cases": 2}]}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            "tools/accumulate_fuzz_history.py",
            "--history-dir",
            str(history),
            "--out",
            str(out),
            "--goal-cases",
            "10",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["total_cases"] == 2
    assert payload["goal_progress"] == 0.2


def test_nightly_fuzz_accumulator_source_smoke(tmp_path: Path):
    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_nightly_fuzz_accumulator.py",
            "--iterations",
            "2",
            "--max-bytes",
            "16",
            "--history-dir",
            str(tmp_path / "history"),
            "--out",
            str(tmp_path / "nightly.json"),
            "--timeout",
            "120",
            "--allow-missing-cargo",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads((tmp_path / "nightly.json").read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["fuzz_total_cases"] == 2 * 7
    assert payload["history_total_cases"] >= payload["fuzz_total_cases"]
    assert payload["rust_consensus_parity_ok"] is True


def test_nightly_fuzz_workflow_is_wired():
    workflow = (ROOT / ".github" / "workflows" / "nightly-fuzz.yml").read_text(encoding="utf-8")
    assert "schedule:" in workflow
    assert "tools/run_nightly_fuzz_accumulator.py" in workflow
    assert "reports/fuzz_history" in workflow
    assert "actions/cache@0057852bfaa89a56745cba8c7296529d2fc39830 # v4" in workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4" in workflow
    assert "dtolnay/rust-toolchain" in workflow


def test_fuzz_all_includes_p2p_and_psbt_targets():
    from netcoin.fuzz import FuzzConfig, run_fuzz

    report = run_fuzz(FuzzConfig(target="all", iterations=1, max_bytes=16, seed=7))
    targets = {item["target"] for item in report["targets"]}
    assert {"p2p-message", "psbt"}.issubset(targets)
    assert report["total_cases"] == len(report["targets"])
