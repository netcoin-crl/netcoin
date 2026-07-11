"""Phase 1 local proof runner helpers.

The local proof runner executes the Phase 1 gate commands and turns terminal
output into auditable per-gate evidence. It does not make sandbox/source-only
checks equivalent to strict proof; it makes that distinction explicit.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .proof_hardening import load_proof_manifest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = ROOT / "architecture" / "local-proof-runner.json"
ALLOWED_PROFILES = {"sandbox", "strict"}
ALLOWED_STATUSES = {"pass", "fail", "blocked", "source_only", "not_run"}
REQUIRED_GATE_IDS = {
    "python-reference",
    "rust-workspace",
    "rust-parity",
    "typescript-api",
    "browser-e2e",
    "accessibility",
    "security-release",
    "phase0-guardrails",
}


@dataclass(frozen=True)
class CommandResult:
    """Observed result for one command in a proof gate."""

    command: str
    returncode: int | None
    status: str
    stdout_tail: str = ""
    stderr_tail: str = ""
    blocked_reason: str | None = None
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "status": self.status,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "blocked_reason": self.blocked_reason,
            "timed_out": self.timed_out,
        }


def load_local_proof_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_local_proof_manifest(manifest: dict[str, Any], *, root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    if manifest.get("phase") != "Phase 1 - Local Proof Runner":
        issues.append("phase must be 'Phase 1 - Local Proof Runner'")
    if not str(manifest.get("version", "")).startswith("0.39"):
        issues.append("version must stay on the v0.39 Phase 1 line")
    if manifest.get("inherits_from") != "architecture/proof-evidence-bundle.json":
        issues.append("local proof runner must inherit architecture/proof-evidence-bundle.json")
    profiles = manifest.get("profiles")
    if not isinstance(profiles, dict) or not ALLOWED_PROFILES.issubset(profiles):
        issues.append("profiles must include sandbox and strict")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        issues.append("outputs must be an object")
    else:
        for key in ["summary_report", "run_directory", "per_gate_json", "per_gate_log", "evidence_bundle"]:
            if not outputs.get(key):
                issues.append(f"outputs missing {key}")
    gate_ids = set(manifest.get("required_gate_ids", []))
    missing = sorted(REQUIRED_GATE_IDS - gate_ids)
    if missing:
        issues.append("required_gate_ids missing: " + ", ".join(missing))
    source_only = set(manifest.get("source_only_gates", []))
    if not {"rust-parity", "browser-e2e", "accessibility"}.issubset(source_only):
        issues.append("source_only_gates must include rust-parity, browser-e2e, and accessibility")
    rules = manifest.get("runner_rules")
    if not isinstance(rules, list) or len(rules) < 5:
        issues.append("runner_rules must list at least five local proof rules")
    criteria = manifest.get("phase1_3_exit_criteria")
    if not isinstance(criteria, list) or len(criteria) < 5:
        issues.append("phase1_3_exit_criteria must list concrete exit criteria")
    inherited = root / "architecture" / "proof-evidence-bundle.json"
    if not inherited.exists():
        issues.append("inherited proof-evidence-bundle manifest is missing")
    return issues


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _normalize_command(command: str) -> str:
    """Use the current Python interpreter for proof commands.

    macOS often exposes Python as `python3` but not `python`; strict proof
    should test NetCoin, not fail because of a command alias mismatch.
    """
    stripped = command.strip()
    if stripped == "python":
        return f'"{sys.executable}"'
    if stripped.startswith("python "):
        return f'"{sys.executable}" ' + stripped[len("python ") :]
    return command


def _tool_blocker(command: str, *, profile: str) -> str | None:
    """Return a human-readable blocker if a strict external tool is missing."""

    if profile != "strict":
        return None
    checks = {
        "cargo": ["cargo test", "run_all_rust_parity.py --strict"],
        "npm": ["npm ci", "npm run", "npx playwright"],
        "npx": ["npx playwright"],
    }
    for tool, needles in checks.items():
        if any(needle in command for needle in needles) and shutil.which(tool) is None:
            return f"required tool unavailable for strict proof: {tool}"
    return None


def _run_command(command: str, *, profile: str, timeout: int) -> CommandResult:
    command = _normalize_command(command)
    blocker = _tool_blocker(command, profile=profile)
    if blocker:
        return CommandResult(command=command, returncode=None, status="blocked", blocked_reason=blocker)
    try:
        proc = subprocess.run(
            command, cwd=ROOT, shell=True, text=True, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            returncode=None,
            status="fail",
            stdout_tail=(exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            stderr_tail=(exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
            blocked_reason=f"timeout after {timeout}s",
            timed_out=True,
        )
    return CommandResult(
        command=command,
        returncode=proc.returncode,
        status="pass" if proc.returncode == 0 else "fail",
        stdout_tail=proc.stdout[-2000:],
        stderr_tail=proc.stderr[-2000:],
    )


def _gate_commands(gate: dict[str, Any], *, profile: str) -> list[str]:
    key = "strict_commands" if profile == "strict" else "sandbox_commands"
    commands = gate.get(key, [])
    return [str(command) for command in commands]


def _status_for_gate(
    gate_id: str, results: Iterable[CommandResult], *, profile: str, source_only_gates: set[str]
) -> str:
    result_list = list(results)
    if not result_list:
        return "not_run"
    if any(item.status == "blocked" for item in result_list):
        return "blocked"
    if any(item.status == "fail" for item in result_list):
        return "fail"
    if profile != "strict" and gate_id in source_only_gates:
        return "source_only"
    return "pass"


def run_local_proof(
    *,
    profile: str = "sandbox",
    timeout: int = 180,
    out: str = "reports/local_proof_run_report.json",
    write: bool = True,
    continue_on_fail: bool = True,
    gate_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Run local proof gates and optionally write per-gate artifacts."""

    if profile not in ALLOWED_PROFILES:
        raise ValueError(f"profile must be one of {sorted(ALLOWED_PROFILES)}")
    local_manifest = load_local_proof_manifest()
    manifest_issues = validate_local_proof_manifest(local_manifest)
    if manifest_issues:
        return {"ok": False, "profile": profile, "manifest_issues": manifest_issues}

    proof_manifest = load_proof_manifest()
    source_only_gates = set(local_manifest.get("source_only_gates", []))
    run_id = _run_id()
    run_dir = ROOT / str(local_manifest.get("outputs", {}).get("run_directory", "reports/proof_runs")) / run_id
    if write:
        run_dir.mkdir(parents=True, exist_ok=True)

    requested_gate_ids = set(gate_ids or [])
    gate_reports: list[dict[str, Any]] = []
    for gate in proof_manifest.get("gate_groups", []):
        gate_id = str(gate.get("id"))
        if requested_gate_ids and gate_id not in requested_gate_ids:
            continue
        commands = _gate_commands(gate, profile=profile)
        command_results: list[CommandResult] = []
        full_log_parts: list[str] = []
        for command in commands:
            result = _run_command(command, profile=profile, timeout=timeout)
            command_results.append(result)
            full_log_parts.append(f"$ {command}\nstatus={result.status} returncode={result.returncode}\n")
            if result.blocked_reason:
                full_log_parts.append(f"blocked_reason={result.blocked_reason}\n")
            if result.stdout_tail:
                full_log_parts.append("--- stdout tail ---\n" + result.stdout_tail + "\n")
            if result.stderr_tail:
                full_log_parts.append("--- stderr tail ---\n" + result.stderr_tail + "\n")
            if result.status in {"fail", "blocked"} and not continue_on_fail:
                break
        status = _status_for_gate(gate_id, command_results, profile=profile, source_only_gates=source_only_gates)
        report = {
            "gate_id": gate_id,
            "label": gate.get("label", gate_id),
            "owner": gate.get("owner"),
            "profile": profile,
            "status": status,
            "command_count": len(command_results),
            "commands": [item.to_dict() for item in command_results],
            "remediation": gate.get("hard_ceiling_removed"),
        }
        if write:
            gate_json = run_dir / f"{gate_id}.json"
            gate_log = run_dir / f"{gate_id}.log"
            gate_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            gate_log.write_text("\n".join(full_log_parts), encoding="utf-8")
            report["artifacts"] = {
                "json": str(gate_json.relative_to(ROOT)),
                "log": str(gate_log.relative_to(ROOT)),
            }
        gate_reports.append(report)
        if status in {"fail", "blocked"} and not continue_on_fail:
            break

    status_counts = {status: 0 for status in sorted(ALLOWED_STATUSES)}
    for gate in gate_reports:
        status_counts[str(gate.get("status"))] += 1
    blockers = [
        gate
        for gate in gate_reports
        if gate.get("status") in {"fail", "blocked"} or (profile == "strict" and gate.get("status") == "source_only")
    ]
    ok = not blockers if profile == "strict" else not any(gate.get("status") == "fail" for gate in gate_reports)
    summary = {
        "version": local_manifest.get("version"),
        "phase": local_manifest.get("phase"),
        "profile": profile,
        "mode": profile,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "ok": ok,
        "claim_level": "strict-local-candidate" if profile == "strict" and ok else "source-checked-testnet",
        "gate_count": len(gate_reports),
        "requested_gate_ids": sorted(requested_gate_ids),
        "status_counts": status_counts,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "gates": gate_reports,
        "run_directory": str(run_dir.relative_to(ROOT)) if write else None,
        "caveat": (
            None
            if profile == "strict"
            else "Sandbox local proof may include source_only gates and is not professional readiness evidence."
        ),
    }
    if write:
        out_path = ROOT / out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def local_proof_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": report.get("ok"),
        "version": report.get("version"),
        "phase": report.get("phase"),
        "profile": report.get("profile"),
        "claim_level": report.get("claim_level"),
        "gate_count": report.get("gate_count"),
        "status_counts": report.get("status_counts"),
        "blocker_count": report.get("blocker_count"),
        "run_directory": report.get("run_directory"),
    }
