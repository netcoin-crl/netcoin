from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _fast_job_block() -> str:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "  fast:" in workflow
    assert "  full:" in workflow
    return workflow.split("  fast:", 1)[1].split("  full:", 1)[0]


def test_fast_ci_job_runs_m1_source_gate() -> None:
    fast = _fast_job_block()
    assert "Set up Node for source asset checks" in fast
    assert "uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4" in fast
    assert 'node-version: "22"' in fast
    assert "M1 source release-candidate gate" in fast
    assert (
        "python tools/run_m1_release_candidate.py --profile source "
        "--out reports/m1_release_candidate_report.json --stop-on-fail"
    ) in fast
    assert "timeout-minutes: 8" in fast


def test_m1_source_runner_includes_ci_gate_wiring_test() -> None:
    runner = (ROOT / "tools" / "run_m1_release_candidate.py").read_text(encoding="utf-8")
    assert "tests/test_m1_ci_gate_wiring.py" in runner
    assert "m1-source-tests" in runner


def test_m1_readiness_gate_checks_ci_wiring() -> None:
    readiness = (ROOT / "tools" / "check_m1_readiness.py").read_text(encoding="utf-8")
    assert "def check_ci_source_gate()" in readiness
    assert "ci_m1_source_gate" in readiness
    assert "M1 source release-candidate gate" in readiness
