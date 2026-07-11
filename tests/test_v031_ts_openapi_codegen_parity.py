from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from netcoin.migration_status import migration_status, parity_vectors
from netcoin.parity_suite import api_codegen_summary, run_parity_suite

ROOT = Path(__file__).resolve().parents[1]


def test_v031_parity_suite_and_api_codegen_are_green() -> None:
    report = run_parity_suite(ROOT)
    vectors = parity_vectors(ROOT)
    assert report["ok"] is True
    assert report["schema_version"] >= 12
    assert report["total"] >= 148
    assert report["lanes"]["api"]["passed"] >= 31
    assert vectors["api"]["vector_set"] == "api-openapi-codegen-vectors-v2"
    assert api_codegen_summary(vectors, ROOT) == vectors["api"]["expected_codegen_summary"]


def test_v031_typescript_files_symbols_and_source_gate() -> None:
    schemas = (ROOT / "api/src/schemas.ts").read_text(encoding="utf-8")
    client = (ROOT / "api/src/client.ts").read_text(encoding="utf-8")
    openapi_parity = (ROOT / "api/src/openapi-parity.ts").read_text(encoding="utf-8")
    for symbol in [
        "SignerPolicySchema",
        "P2PSyncSummarySchema",
        "IndexerSnapshotSchema",
        "OpenApiRouteSchema",
        "OpenApiParitySchema",
    ]:
        assert symbol in schemas
    for method in [
        "explorerTransaction",
        "explorerBlock",
        "explorerMempool",
        "operatorDiagnosticsBundle",
        "releaseVerify",
    ]:
        assert method in client
    for symbol in [
        "normalizeOpenApiRoute",
        "requiredOpenApiRoutes",
        "requiredOpenApiSchemas",
        "summarizeOpenApiParity",
        "assertOpenApiParity",
    ]:
        assert symbol in openapi_parity
    proc = subprocess.run(
        [sys.executable, "tools/run_ts_openapi_codegen_parity.py", "--no-write"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["summary"]["codegen_ok"] is True


def test_v031_migration_status_reports_ts_codegen_lane() -> None:
    status = migration_status(ROOT)
    assert status["version"] in {
        "0.31.0",
        "0.37.0",
        "0.37.1",
        "0.37.2",
        "0.37.3",
        "0.37.4",
        "0.38.0",
        "0.38.1",
        "0.38.2",
        "0.38.3",
    }
    lane = next(lane for lane in status["lanes"] if lane["id"] == "typescript-openapi-codegen")
    assert lane["status"] == "source-checked-openapi-schema-client-codegen-parity"
    assert lane["evidence"]["owner_exists"] is True
    assert lane["evidence"]["has_vector_set"] is True


def test_v031_makefile_has_final_gate() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "v031-check" in makefile
    assert "ts-openapi-codegen-check" in makefile
