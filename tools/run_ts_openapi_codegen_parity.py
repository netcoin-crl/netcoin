#!/usr/bin/env python3
"""Validate TypeScript OpenAPI/schema/client codegen parity against frozen vectors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.parity_suite import api_codegen_summary, vector_fingerprint

VECTOR_PATH = ROOT / "architecture" / "parity-vectors.json"


def _load_vectors() -> dict[str, Any]:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def _source_checks(vectors: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required = [
        "api/src/schemas.ts",
        "api/src/client.ts",
        "api/src/openapi-parity.ts",
        "api/src/parity-executor.ts",
        "docs/openapi.yaml",
    ]
    for rel in required:
        if not (ROOT / rel).exists():
            issues.append(f"missing {rel}")
    api = vectors.get("api", {})
    if api.get("vector_set") != "api-openapi-codegen-vectors-v2":
        issues.append("api vector_set is not api-openapi-codegen-vectors-v2")
    if (ROOT / "api/src/openapi-parity.ts").exists():
        text = (ROOT / "api/src/openapi-parity.ts").read_text(encoding="utf-8")
        for symbol in api.get("required_codegen_symbols", []):
            if str(symbol) not in text:
                issues.append(f"api/src/openapi-parity.ts missing {symbol}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TypeScript OpenAPI/schema codegen parity source checks")
    parser.add_argument("--out", default="reports/ts_openapi_codegen_parity_report.json")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    vectors = _load_vectors()
    source_issues = _source_checks(vectors)
    summary = api_codegen_summary(vectors, ROOT)
    expected = vectors.get("api", {}).get("expected_codegen_summary", {})
    comparison_issues = [] if summary == expected else [f"summary mismatch: expected={expected!r} actual={summary!r}"]
    report = {
        "ok": not source_issues and not comparison_issues,
        "schema_version": vectors.get("schema_version"),
        "vector_fingerprint": vector_fingerprint(vectors),
        "summary": summary,
        "expected": expected,
        "source_issues": source_issues,
        "comparison_issues": comparison_issues,
    }
    if not args.no_write:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ok", "schema_version", "vector_fingerprint", "summary")}, indent=2))
    if source_issues or comparison_issues:
        print(json.dumps({"source_issues": source_issues, "comparison_issues": comparison_issues}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
