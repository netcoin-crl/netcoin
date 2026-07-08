from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.apps import AppStore, route_app_get
from netcoin.chain import Blockchain
from netcoin.migration_status import migration_status, parity_bridge_status, parity_vectors, final_version_readiness
from netcoin.parity_suite import run_parity_suite, merkle_root_hex, subsidy_at_height, tx_fee_ok

ROOT = Path(__file__).resolve().parents[1]


def test_v022_expanded_parity_suite_is_green() -> None:
    report = run_parity_suite(ROOT)
    assert report["ok"] is True
    assert report["schema_version"] == 3
    assert report["total"] >= 50
    assert report["lanes"]["consensus"]["passed"] >= 14
    assert report["lanes"]["wallet"]["passed"] >= 9
    assert report["lanes"]["markets"]["passed"] >= 11
    assert tx_fee_ok(10, 9) is True
    assert tx_fee_ok(9, 10) is False
    assert subsidy_at_height(5_000_000_000, 530_000, 265_000, 9, 10) == 4_050_000_000
    assert len(merkle_root_hex(["00", "11", "22"])) == 64


def test_v022_migration_routes_expose_vectors_and_readiness(tmp_path: Path) -> None:
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(tmp_path / "app")
    for route in ["/api/parity-vectors", "/api/migration-readiness", "/api/parity-status", "/api/migration-status"]:
        status, payload, ctype = route_app_get(store, chain, route, {}, node=None)
        assert status == 200, route
        assert ctype == "application/json"
        assert payload
    vectors = parity_vectors(ROOT)
    readiness = final_version_readiness(ROOT)
    status = migration_status(ROOT)
    parity = parity_bridge_status(ROOT)
    assert vectors["schema_version"] == 3
    assert status["version"] == "0.22.0"
    assert parity["ok"] is True
    assert readiness["ready"] is False


def test_v022_rust_symbols_cover_expanded_parity() -> None:
    consensus = (ROOT / "core-rs/crates/consensus/src/lib.rs").read_text(encoding="utf-8")
    wallet = (ROOT / "core-rs/crates/wallet-core/src/lib.rs").read_text(encoding="utf-8")
    markets = (ROOT / "core-rs/crates/markets-core/src/lib.rs").read_text(encoding="utf-8")
    for symbol in ["tx_fee_ok", "merkle_root_hex", "subsidy_at_height"]:
        assert symbol in consensus
    for symbol in ["WalletPolicyPreview", "policy_decision", "policy_decision_from_parts"]:
        assert symbol in wallet
    for symbol in ["fee_within_cap", "order_notional_ok", "market_accounting_conserves"]:
        assert symbol in markets
    fixture = json.loads((ROOT / "core-rs/fixtures/parity-vectors.json").read_text(encoding="utf-8"))
    assert fixture["schema_version"] == 3


def test_v022_typescript_contracts_cover_expanded_parity() -> None:
    schemas = (ROOT / "api/src/schemas.ts").read_text(encoding="utf-8")
    client = (ROOT / "api/src/client.ts").read_text(encoding="utf-8")
    executor = (ROOT / "api/src/parity-executor.ts").read_text(encoding="utf-8")
    for symbol in ["ExplorerTransactionSchema", "WalletPreviewSchema", "MarketSettlementSchema", "ParityVectorSchema"]:
        assert symbol in schemas
    assert "parityVectors" in client
    assert "migrationReadiness" in client
    for symbol in ["moneyInRange", "walletDecision", "orderNotionalOk"]:
        assert symbol in executor
    proc = subprocess.run(
        [sys.executable, "tools/check_ts_workspace.py"], cwd=ROOT, text=True, capture_output=True, timeout=30
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_v022_openapi_documents_new_migration_routes() -> None:
    spec = (ROOT / "docs/openapi.yaml").read_text(encoding="utf-8")
    assert "/api/parity-vectors" in spec or "/parity-vectors" in spec
    assert "/api/migration-readiness" in spec or "/migration-readiness" in spec
    proc = subprocess.run(
        [sys.executable, "tools/run_parity_suite.py", "--no-write"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
