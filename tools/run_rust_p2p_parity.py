#!/usr/bin/env python3
"""Run/compare the Rust p2p-sync parity executable against Python reference vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from netcoin.parity_suite import run_p2p_vectors, vector_fingerprint

VECTOR_PATH = ROOT / "architecture" / "parity-vectors.json"
RUST_FIXTURE_PATH = ROOT / "core-rs" / "fixtures" / "parity-vectors.json"
RUST_CRATE_PATH = ROOT / "core-rs/crates/node"
RUST_BIN_PATH = RUST_CRATE_PATH / "src" / "bin" / "netcoin-p2p-parity.rs"
RUST_LIB_PATH = RUST_CRATE_PATH / "src" / "lib.rs"


def _load_vectors() -> dict[str, Any]:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def _source_checks(vectors: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required = [VECTOR_PATH, RUST_FIXTURE_PATH, RUST_CRATE_PATH / "Cargo.toml", RUST_BIN_PATH, RUST_LIB_PATH]
    for path in required:
        if not path.exists():
            issues.append(f"missing {path.relative_to(ROOT)}")
    if (
        RUST_FIXTURE_PATH.exists()
        and VECTOR_PATH.exists()
        and json.loads(RUST_FIXTURE_PATH.read_text(encoding="utf-8")) != vectors
    ):
        issues.append(
            "core-rs/fixtures/parity-vectors.json is not synchronized with architecture/parity-vectors.json"
        )
    lib_text = RUST_LIB_PATH.read_text(encoding="utf-8") if RUST_LIB_PATH.exists() else ""
    bin_text = RUST_BIN_PATH.read_text(encoding="utf-8") if RUST_BIN_PATH.exists() else ""
    workspace_text = (
        (ROOT / "core-rs/Cargo.toml").read_text(encoding="utf-8") if (ROOT / "core-rs/Cargo.toml").exists() else ""
    )
    for symbol in [
        "run_p2p_case",
        "run_p2p_parity_vectors",
        "p2p_best_peer_summary",
        "p2p_header_sync_summary",
        "p2p_ban_score_summary",
    ]:
        if symbol not in lib_text:
            issues.append(f"Rust p2p-sync lib missing {symbol}")
    for symbol in ["run_p2p_parity_vectors", "serde_json::to_string_pretty", "process::exit"]:
        if symbol not in bin_text:
            issues.append(f"Rust p2p-sync binary missing {symbol}")
    if "crates/node" not in workspace_text:
        issues.append("core-rs workspace does not include crates/node")
    if vectors.get("p2p", {}).get("vector_set") != "p2p-header-sync-vectors-v1":
        issues.append("p2p vector_set is not p2p-header-sync-vectors-v1")
    return issues


def _python_reference(vectors: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = [item.to_dict() for item in run_p2p_vectors(vectors)]
    return {item["case_id"]: item for item in results}


def _run_cargo(timeout: int) -> tuple[int, str, str]:
    cmd = [
        "cargo",
        "run",
        "-q",
        "-p",
        "netcoin-node",
        "--bin",
        "netcoin-p2p-parity",
        "--",
        "../architecture/parity-vectors.json",
    ]
    proc = subprocess.run(cmd, cwd=ROOT / "core-rs", text=True, capture_output=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def _compare_with_rust(vectors: dict[str, Any], rust_report: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    python_by_id = _python_reference(vectors)
    rust_by_id = {str(item.get("case_id")): item for item in rust_report.get("results", []) if isinstance(item, dict)}
    if set(python_by_id) != set(rust_by_id):
        missing = sorted(set(python_by_id) - set(rust_by_id))
        extra = sorted(set(rust_by_id) - set(python_by_id))
        if missing:
            issues.append(f"Rust report missing cases: {', '.join(missing)}")
        if extra:
            issues.append(f"Rust report returned extra cases: {', '.join(extra)}")
    for case_id, py_item in sorted(python_by_id.items()):
        rust_item = rust_by_id.get(case_id)
        if not rust_item:
            continue
        if rust_item.get("actual") != py_item.get("actual"):
            issues.append(
                f"case {case_id} actual mismatch: python={py_item.get('actual')!r} rust={rust_item.get('actual')!r}"
            )
        if rust_item.get("expected") != py_item.get("expected"):
            issues.append(
                f"case {case_id} expected mismatch: python={py_item.get('expected')!r} rust={rust_item.get('expected')!r}"
            )
        if rust_item.get("passed") is not True:
            issues.append(f"case {case_id} failed in Rust report")
    if rust_report.get("ok") is not True:
        issues.append("Rust executable reported ok=false")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NetCoin Rust p2p-sync parity executable and compare with Python")
    parser.add_argument("--out", default="reports/rust_p2p_parity_report.json")
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--allow-missing-cargo", action="store_true")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    vectors = _load_vectors()
    source_issues = _source_checks(vectors)
    cargo_path = shutil.which("cargo")
    vector_bytes = VECTOR_PATH.read_bytes()
    report: dict[str, Any] = {
        "ok": False,
        "mode": "source-only" if args.source_only else "cargo",
        "cargo_available": bool(cargo_path),
        "schema_version": vectors.get("schema_version"),
        "vector_fingerprint": vector_fingerprint(vectors),
        "input_file_sha256": hashlib.sha256(vector_bytes).hexdigest(),
        "p2p_cases": len(vectors.get("p2p", {}).get("cases", [])),
        "source_issues": source_issues,
        "comparison_issues": [],
    }
    if source_issues:
        report["ok"] = False
    elif args.source_only or (not cargo_path and args.allow_missing_cargo):
        report["ok"] = True
        report["mode"] = "source-only" if args.source_only else "source-only-missing-cargo"
        report["note"] = (
            "Cargo was not executed; run without --allow-missing-cargo on a Rust-enabled machine for live comparison."
        )
    elif not cargo_path:
        report["comparison_issues"] = [
            "cargo not found; install Rust/Cargo or rerun with --allow-missing-cargo for source-only sandbox validation"
        ]
    else:
        try:
            code, stdout, stderr = _run_cargo(args.timeout)
        except subprocess.TimeoutExpired as exc:
            report["comparison_issues"] = [f"cargo run timed out after {args.timeout}s"]
            report["cargo_stdout"] = exc.stdout or ""
            report["cargo_stderr"] = exc.stderr or ""
        else:
            report["cargo_returncode"] = code
            report["cargo_stderr"] = stderr
            try:
                rust_report = json.loads(stdout)
            except json.JSONDecodeError as exc:
                report["comparison_issues"] = [f"could not parse Rust parity JSON: {exc}"]
                report["cargo_stdout"] = stdout
            else:
                issues = [] if code == 0 else [f"cargo run exited with {code}"]
                issues.extend(_compare_with_rust(vectors, rust_report))
                report["rust_report"] = rust_report
                report["comparison_issues"] = issues
                report["ok"] = not issues

    if not args.no_write:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary_keys = ["ok", "mode", "cargo_available", "schema_version", "p2p_cases", "vector_fingerprint"]
    print(json.dumps({key: report.get(key) for key in summary_keys}, indent=2))
    if report.get("source_issues") or report.get("comparison_issues"):
        print(
            json.dumps(
                {"source_issues": report.get("source_issues"), "comparison_issues": report.get("comparison_issues")},
                indent=2,
            )
        )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
