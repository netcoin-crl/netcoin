from pathlib import Path

from netcoin.architecture import architecture_summary
from netcoin.migration_status import final_version_readiness, migration_status, parity_vectors
from netcoin.params import NODE_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_migration_status_has_required_lanes_and_vectors():
    status = migration_status(ROOT)
    vectors = parity_vectors(ROOT)
    assert status["ok"] is True
    assert status["version"] == NODE_VERSION
    assert status["current_live_runtime"] == "python-reference-app"
    assert status["target_runtime"] == "rust-core-typescript-app-python-ops"
    assert len(status["lanes"]) >= 5
    assert vectors["consensus"]["valid_cases"] >= 1
    assert vectors["consensus"]["invalid_cases"] >= 1
    assert len(status["vector_fingerprint"]) == 64


def test_architecture_summary_embeds_migration_status():
    summary = architecture_summary(ROOT)
    assert "migration" in summary
    assert summary["migration"]["status"]["ok"] is True
    assert summary["migration"]["status"]["version"] == NODE_VERSION


def test_final_version_readiness_is_honest_not_ready_by_scaffold_alone():
    readiness = final_version_readiness(ROOT)
    assert readiness["target"] == "v1.0 production-candidate"
    assert readiness["ready"] is False
    assert readiness["complete_gates"] < readiness["total_gates"]


def test_rust_and_typescript_upgrade_spaces_have_real_symbols():
    required_symbols = {
        "core-rs/crates/consensus/src/lib.rs": ["double_sha256_hex", "validate_linked_headers"],
        "core-rs/crates/wallet-core/src/lib.rs": ["WalletPreview", "RiskDecision"],
        "core-rs/crates/markets-core/src/lib.rs": ["settlement_conserves_value", "binary_probability_sum_ok"],
        "api/src/schemas.ts": ["SignedEnvelopeSchema", "MigrationStatusSchema"],
        "api/src/client.ts": ["NetCoinClient", "migrationStatus"],
    }
    for rel, symbols in required_symbols.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for symbol in symbols:
            assert symbol in text
