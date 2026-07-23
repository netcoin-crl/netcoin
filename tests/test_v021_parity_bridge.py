from pathlib import Path

from netcoin.migration_status import final_version_readiness, migration_status, parity_bridge_status
from netcoin.params import NODE_VERSION
from netcoin.parity_suite import run_parity_suite
from netcoin.sync import HeaderSyncScheduler

ROOT = Path(__file__).resolve().parents[1]


def test_executable_parity_suite_is_green_and_reports_lanes():
    report = run_parity_suite(ROOT)
    assert report["ok"] is True
    assert report["total"] >= 25
    assert report["lanes"]["consensus"]["failed"] == 0
    assert report["lanes"]["wallet"]["failed"] == 0
    assert report["lanes"]["markets"]["failed"] == 0
    assert report["lanes"]["api"]["failed"] == 0


def test_migration_status_exposes_v021_parity_bridge():
    status = migration_status(ROOT)
    parity = parity_bridge_status(ROOT)
    readiness = final_version_readiness(ROOT)
    assert status["version"] == NODE_VERSION
    assert any(lane["id"] == "parity-reporting" for lane in status["lanes"])
    assert parity["ok"] is True
    assert parity["total"] >= 25
    gates = {item["gate"]: item["complete"] for item in readiness["gates"]}
    assert gates["Executable parity suite green"] is True
    assert readiness["ready"] is False


def test_typescript_and_rust_parity_files_exist():
    required = [
        "api/src/parity.ts",
        "core-rs/fixtures/parity-vectors.json",
        "api/fixtures/parity-vectors.json",
        "tools/run_parity_suite.py",
    ]
    for rel in required:
        assert (ROOT / rel).exists(), rel
    assert "ParityStatusSchema" in (ROOT / "api/src/parity.ts").read_text(encoding="utf-8")
    assert "block_weight_ok" in (ROOT / "core-rs/crates/consensus/src/lib.rs").read_text(encoding="utf-8")


def test_header_sync_accepts_in_place_validating_chains():
    class InPlaceValidationChain:
        def __init__(self):
            self.headers_seen = None

        def validate_headers_from_tip(self, headers):
            self.headers_seen = headers
            return

        def tip_hash(self):
            return "tip"

        def height(self):
            return 10

    chain = InPlaceValidationChain()
    scheduler = HeaderSyncScheduler()
    headers = [{"height": 11, "hash": "next", "previous_hash": "tip"}]
    plan = scheduler.plan_from_headers(chain, headers, "peer-1")
    assert chain.headers_seen == headers
    assert plan["queued"] == 1
    assert plan["validated_headers"] == 1
