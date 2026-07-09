from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.migration_status import migration_status, parity_vectors
from netcoin.parity_suite import run_parity_suite, signer_digest, signer_envelope_summary, signer_policy_summary

ROOT = Path(__file__).resolve().parents[1]


def test_v028_signer_parity_suite_is_green() -> None:
    report = run_parity_suite(ROOT)
    vectors = parity_vectors(ROOT)
    assert report["ok"] is True
    assert report["schema_version"] >= 9
    assert report["lanes"]["signer"]["passed"] >= 10
    assert vectors["signer"]["vector_set"] == "signer-core-executable-vectors-v1"


def test_v028_python_reference_executes_signer_vectors() -> None:
    vectors = json.loads((ROOT / "architecture/parity-vectors.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in vectors["signer"]["cases"]}
    assert len(signer_digest(cases["signer-digest-basic-transfer"])) == 64
    assert signer_policy_summary(cases["signer-policy-single-hot-allow"])["decision"] == "allow"
    assert signer_policy_summary(cases["signer-policy-missing-threshold-block"])["decision"] == "block"
    assert signer_policy_summary(cases["signer-policy-hardware-large-review"])["decision"] == "review"
    assert signer_envelope_summary(cases["signer-envelope-valid-offline"])["valid"] is True
    assert signer_envelope_summary(cases["signer-envelope-missing-digest"])["valid"] is False


def test_v028_rust_signer_files_symbols_and_source_gate() -> None:
    lib = (ROOT / "core-rs/crates/signer-core/src/lib.rs").read_text(encoding="utf-8")
    binary = (ROOT / "core-rs/crates/signer-core/src/bin/netcoin-signer-parity.rs").read_text(encoding="utf-8")
    for symbol in [
        "signer_digest",
        "signer_policy_summary",
        "signer_envelope_summary",
        "run_signer_case",
        "run_signer_parity_vectors",
    ]:
        assert symbol in lib
    assert "run_signer_parity_vectors" in binary
    proc = subprocess.run(
        [sys.executable, "tools/run_rust_signer_parity.py", "--source-only", "--no-write"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["signer_cases"] >= 10


def test_v028_migration_status_reports_signer_lane() -> None:
    status = migration_status(ROOT)
    lane = next(lane for lane in status["lanes"] if lane["id"] == "rust-signer-core")
    assert lane["status"] == "executable-rust-signer-core-parity-runner"
    assert lane["evidence"]["owner_exists"] is True
    assert lane["evidence"]["has_vector_set"] is True
