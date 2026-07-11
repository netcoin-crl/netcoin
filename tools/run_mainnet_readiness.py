#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.mainnet_readiness import aggregate_results, load_manifest, manifest_gate_map, validate_manifest, GateResult


def run_command(command: str, timeout: int) -> dict[str, Any]:
    command = command.replace("python ", f"{sys.executable} ")
    try:
        proc = subprocess.run(
            command, cwd=ROOT, shell=True, text=True, capture_output=True, timeout=timeout, check=False
        )
        parsed: dict[str, Any] = {}
        stdout = proc.stdout.strip()
        if stdout:
            try:
                parsed = json.loads(stdout)
            except Exception:
                try:
                    start = stdout.find("{")
                    end = stdout.rfind("}")
                    if start >= 0 and end >= start:
                        parsed = json.loads(stdout[start : end + 1])
                except Exception:
                    parsed = {}
        return {
            "command": command,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
            "parsed": parsed,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": 124,
            "stdout_tail": str(exc.stdout or "")[-2000:],
            "stderr_tail": str(exc.stderr or "")[-2000:],
            "timeout": True,
            "parsed": {},
        }


def result_from_run(gate_id: str, mode: str, run: dict[str, Any]) -> GateResult:
    parsed = run.get("parsed") or {}
    issues = []
    if run.get("returncode") != 0:
        issues.append("command failed")
    if isinstance(parsed, dict):
        issues.extend(str(i) for i in parsed.get("issues", []) if i)
    return GateResult(
        gate_id=gate_id,
        ok=run.get("returncode") == 0 and bool(parsed.get("ok", run.get("returncode") == 0)),
        mode=mode,
        status=str(parsed.get("status") or ("pass" if run.get("returncode") == 0 else "fail")),
        issues=tuple(issues),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out", default="reports/mainnet_readiness_report.json")
    parser.add_argument("--quiet", action="store_true", help="print a compact summary instead of full command logs")
    args = parser.parse_args()
    manifest = load_manifest()
    manifest_issues = validate_manifest(manifest)
    if manifest_issues:
        result = {"ok": False, "manifest_issues": manifest_issues}
    else:
        mode = "strict" if args.strict else "source"
        results: list[GateResult] = []
        runs: dict[str, Any] = {}
        for gate_id, gate in manifest_gate_map(manifest).items():
            command = str(gate["strict_command" if args.strict else "source_command"])
            run = run_command(command, args.timeout)
            runs[gate_id] = run
            results.append(result_from_run(gate_id, mode, run))
        result = aggregate_results(results, version=str(manifest.get("version", "0.41.0")))
        result["mode"] = mode
        if mode == "source":
            result["claim_level"] = "source-complete-evidence-required-not-mainnet"
            result["cannot_claim_production_until_strict_evidence_passes"] = True
        result["runs"] = runs
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.quiet:
        compact = {
            k: result.get(k)
            for k in ["ok", "mode", "claim_level", "gate_count", "pass_count", "blocker_count", "version"]
        }
        print(json.dumps(compact, indent=2, sort_keys=True))
    else:
        print(text)
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
