"""Security hardening, fuzz target, and audit-prep manifest checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECURITY_VECTORS = ROOT / "architecture" / "security-fuzz-audit-vectors.json"

REQUIRED_SECURITY_FILES = [
    "SECURITY.md",
    "tools/mutation_consensus_smoke.py",
    "tools/run_p2p_soak.py",
    "tools/check_indexer_db_integration.py",
    "tools/run_ts_api_contract_enforcement.py",
    "tools/run_browser_e2e_matrix.py",
    "architecture/security-fuzz-audit-vectors.json",
]

REQUIRED_DOCS = [
    "docs/V033_HOSTILE_P2P_SOAK.md",
    "docs/V034_INDEXER_DB_INTEGRATION.md",
    "docs/V035_TYPESCRIPT_API_OPENAPI_ENFORCEMENT.md",
    "docs/V036_BROWSER_E2E_MATRIX.md",
    "docs/V037_SECURITY_FUZZ_AUDIT_PREP.md",
]


def load_security_vectors(path: str | Path = DEFAULT_SECURITY_VECTORS) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def security_audit_manifest(root: Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    vectors = load_security_vectors(base / "architecture" / "security-fuzz-audit-vectors.json")
    missing_files = [rel for rel in REQUIRED_SECURITY_FILES if not (base / rel).exists()]
    missing_docs = [rel for rel in REQUIRED_DOCS if not (base / rel).exists()]
    fuzz_targets = vectors.get("fuzz_targets", [])
    incomplete_fuzz_targets = [
        target.get("name") for target in fuzz_targets if int(target.get("min_iterations", 0)) <= 0
    ]
    audit_gates = vectors.get("audit_gates", [])
    ok = not missing_files and not missing_docs and not incomplete_fuzz_targets and len(audit_gates) >= 6
    return {
        "ok": ok,
        "schema_version": vectors.get("schema_version"),
        "fuzz_target_count": len(fuzz_targets),
        "audit_gate_count": len(audit_gates),
        "missing_files": missing_files,
        "missing_docs": missing_docs,
        "incomplete_fuzz_targets": incomplete_fuzz_targets,
        "threat_model_count": len(vectors.get("threat_model", [])),
    }


__all__ = ["REQUIRED_DOCS", "REQUIRED_SECURITY_FILES", "load_security_vectors", "security_audit_manifest"]
