"""Lock the fuzz harness as a real regression gate.

The harness raises FuzzError if any parser/endpoint crashes unexpectedly under
random input. Running it here (bounded, deterministic seed) turns "the fuzz
plan exists" into "the parsers provably survive fuzzing in CI".
"""

import json

from netcoin.fuzz import TARGETS, FuzzConfig, run_fuzz


def test_all_fuzz_targets_run_without_unexpected_crash():
    report = run_fuzz(FuzzConfig(target="all", iterations=200, seed=99, max_bytes=192))
    assert report["ok"] is True
    seen = {item["target"] for item in report["targets"]}
    assert seen == set(TARGETS)
    for item in report["targets"]:
        # Every case must be accounted for as accepted or rejected — a crash
        # would have raised FuzzError before we got here.
        assert item["accepted"] + item["rejected"] == item["cases"]
        assert item["cases"] > 0


def test_fuzz_is_deterministic_for_a_fixed_seed():
    a = run_fuzz(FuzzConfig(target="tx-dict", iterations=150, seed=7, max_bytes=128))
    b = run_fuzz(FuzzConfig(target="tx-dict", iterations=150, seed=7, max_bytes=128))
    assert a["targets"][0]["cases"] == b["targets"][0]["cases"]
    assert a["targets"][0]["accepted"] == b["targets"][0]["accepted"]


def test_fuzz_cli_writes_evidence_report(tmp_path):
    from netcoin.cli import cmd_fuzz

    class Args:
        target = "tx-dict"
        iterations = 50
        seed = 1
        max_bytes = 64
        out = str(tmp_path / "fuzz_report.json")

    cmd_fuzz(Args())
    written = json.loads((tmp_path / "fuzz_report.json").read_text())
    assert written["ok"] is True
    assert written["total_cases"] == 50
