from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_m1_release_candidate_dry_run_lists_source_gates(tmp_path: Path) -> None:
    out = tmp_path / "m1-rc.json"
    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_m1_release_candidate.py",
            "--dry-run",
            "--out",
            str(out),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["profile"] == "source"
    assert payload["dry_run"] is True
    assert {gate["id"] for gate in payload["gates"]} == {
        "m1-readiness-source",
        "site-ui-polish",
        "m1-source-tests",
        "wallet-js-syntax",
        "explorer-status-js-syntax",
        "m1-live-smoke-plan",
    }
    assert all(gate["status"] == "planned" for gate in payload["gates"])
    assert "live seed deployment" in payload["does_not_claim"]


def test_m1_release_candidate_strict_profile_lists_exact_operator_commands(
    tmp_path: Path,
) -> None:
    out = tmp_path / "m1-rc-strict.json"
    proc = subprocess.run(
        [
            sys.executable,
            "tools/run_m1_release_candidate.py",
            "--profile",
            "strict",
            "--dry-run",
            "--out",
            str(out),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    commands = [gate["command"] for gate in payload["gates"]]
    assert ".venv/bin/python -m pytest tests/ -q" in commands
    assert ".venv/bin/python tools/run_parity_suite.py" in commands
    assert "cargo test --workspace --manifest-path core-rs/Cargo.toml" in commands
    assert "cd api && npm run parity" in commands
    assert "cd api && npm run ci:api" in commands
    assert "python3 tools/run_browser_e2e_matrix.py --run-playwright" in commands
    assert "python3 tools/run_accessibility_matrix.py --strict" in commands
    assert "python3 tools/run_local_proof.py --profile strict --timeout 300" in commands


def test_makefile_exposes_m1_release_candidate_targets() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "m1-readiness-check:" in makefile
    assert "m1-rc-check:" in makefile
    assert "m1-rc-strict:" in makefile
    assert "tools/run_m1_release_candidate.py" in makefile
    assert "m1-live-smoke-plan:" in makefile
    assert "m1-live-smoke:" in makefile
