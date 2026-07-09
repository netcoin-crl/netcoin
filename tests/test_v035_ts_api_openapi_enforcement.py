import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v035_ts_api_contract_source_gate_passes():
    proc = subprocess.run(
        [sys.executable, "tools/run_ts_api_contract_enforcement.py"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert result["checked_files"] >= 5
    assert result["required_route_count"] >= 18
    assert result["client_get_route_count"] >= 8


def test_v035_ts_api_server_exports_enforcement():
    server = (ROOT / "api/src/server.ts").read_text(encoding="utf-8")
    enforce = (ROOT / "api/src/openapi-enforce.ts").read_text(encoding="utf-8")
    assert "createNetCoinApiServer" in server
    assert "implementedApiRoutes" in server
    assert "assertOpenApiContract(requiredApiRoutes, implementedApiRoutes)" in server
    assert "summarizeBundledOpenApiParity" in server
    assert "summarizeOpenApiParity()" not in server
    assert "requiredApiRoutes" in enforce
    assert "signedEnvelopeRequired" in enforce
    assert "missingRoutes" in enforce


def test_v035_ts_client_routes_are_registered_by_server_source():
    server = (ROOT / "api/src/server.ts").read_text(encoding="utf-8")
    for route in [
        "/api/migration-status",
        "/api/parity-status",
        "/api/explorer/address/:address",
        "/api/explorer/tx/:txid",
        "/api/explorer/block/:id",
        "/api/explorer/mempool",
        "/api/operator/diagnostics/bundle",
        "/api/release/verify",
    ]:
        assert route in server


def test_ts_api_contract_source_check_runs_tsc_when_dependencies_are_installed():
    import json
    import shutil
    import subprocess
    import sys

    if not shutil.which("tsc"):
        return
    proc = subprocess.run(
        [sys.executable, "tools/run_ts_api_contract_enforcement.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    if (ROOT / "api" / "node_modules").exists():
        assert result["tsc_checked"] is True
        assert result["tsc_returncode"] == 0
    else:
        assert result["tsc_checked"] is False
        assert "node_modules" in result["tsc_skipped_reason"]
