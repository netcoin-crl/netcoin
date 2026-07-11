"""Phase 1 proof-evidence bundle helpers.

The proof evidence layer does not make source-only checks magically strict. It
turns all proof outputs into one auditable bundle and explains exactly what is
missing before a release can claim professional readiness.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = ROOT / "architecture" / "proof-evidence-bundle.json"
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
REQUIRED_METADATA = {
    "version",
    "phase",
    "mode",
    "created_at_utc",
    "claim_level",
    "gate_count",
    "artifact_count",
    "blockers",
    "remediation",
}


@dataclass(frozen=True)
class ArtifactRecord:
    """Metadata for one proof artifact."""

    path: str
    exists: bool
    size_bytes: int | None = None
    sha256: str | None = None
    json_ok: bool | None = None
    ok_field: Any | None = None
    mode_field: Any | None = None
    claim_level_field: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "json_ok": self.json_ok,
            "ok_field": self.ok_field,
            "mode_field": self.mode_field,
            "claim_level_field": self.claim_level_field,
        }


def load_proof_evidence_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_proof_evidence_manifest(manifest: dict[str, Any], *, root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    if manifest.get("phase") != "Phase 1 - Proof Evidence Bundle":
        issues.append("phase must be 'Phase 1 - Proof Evidence Bundle'")
    if not str(manifest.get("version", "")).startswith("0.39"):
        issues.append("version must stay on the v0.39 Phase 1 line")
    if manifest.get("inherits_from") != "architecture/strict-proof-execution.json":
        issues.append("proof evidence bundle must inherit architecture/strict-proof-execution.json")
    bundle = manifest.get("bundle")
    if not isinstance(bundle, dict):
        issues.append("bundle must be an object")
    else:
        for key in ["default_path", "default_directory", "hash_algorithm", "claim_levels"]:
            if key not in bundle:
                issues.append(f"bundle missing {key}")
        if bundle.get("hash_algorithm") != "sha256":
            issues.append("bundle.hash_algorithm must be sha256")
        if "source-checked-testnet" not in set(bundle.get("claim_levels", [])):
            issues.append("claim_levels must include source-checked-testnet")
    metadata = set(manifest.get("required_metadata", []))
    missing_metadata = sorted(REQUIRED_METADATA - metadata)
    if missing_metadata:
        issues.append("required_metadata missing: " + ", ".join(missing_metadata))
    gates = manifest.get("gate_artifacts")
    if not isinstance(gates, list) or not gates:
        issues.append("gate_artifacts must be a non-empty list")
        return issues
    gate_ids = {str(gate.get("gate_id")) for gate in gates if isinstance(gate, dict)}
    missing_gates = sorted(REQUIRED_GATE_IDS - gate_ids)
    if missing_gates:
        issues.append("missing gate_artifacts: " + ", ".join(missing_gates))
    for gate in gates:
        if not isinstance(gate, dict):
            issues.append("gate_artifact entry must be an object")
            continue
        gate_id = str(gate.get("gate_id", "<unknown>"))
        if not gate.get("label"):
            issues.append(f"gate {gate_id} missing label")
        if "required_for_strict" not in gate:
            issues.append(f"gate {gate_id} missing required_for_strict")
        paths = gate.get("paths")
        if not isinstance(paths, list) or not paths or not all(isinstance(path, str) and path for path in paths):
            issues.append(f"gate {gate_id} must list artifact paths")
        if not gate.get("remediation"):
            issues.append(f"gate {gate_id} missing remediation")
    blocker_classes = manifest.get("blocker_classes")
    if not isinstance(blocker_classes, list) or len(blocker_classes) < 4:
        issues.append("blocker_classes must define at least four blocker types")
    criteria = manifest.get("phase1_2_exit_criteria")
    if not isinstance(criteria, list) or len(criteria) < 5:
        issues.append("phase1_2_exit_criteria must list concrete exit criteria")
    strict_path = root / "architecture" / "strict-proof-execution.json"
    if not strict_path.exists():
        issues.append("inherited strict-proof-execution manifest is missing")
    return issues


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_artifact(path: str, *, root: Path = ROOT) -> ArtifactRecord:
    artifact_path = root / path
    if not artifact_path.exists():
        return ArtifactRecord(path=path, exists=False)
    size = artifact_path.stat().st_size
    digest = _file_sha256(artifact_path)
    json_ok: bool | None = None
    ok_field: Any | None = None
    mode_field: Any | None = None
    claim_level_field: Any | None = None
    if artifact_path.suffix == ".json":
        try:
            data = json.loads(artifact_path.read_text(encoding="utf-8"))
            json_ok = True
            if isinstance(data, dict):
                ok_field = data.get("ok")
                mode_field = data.get("mode")
                claim_level_field = data.get("claim_level")
        except Exception:
            json_ok = False
    return ArtifactRecord(
        path=path,
        exists=True,
        size_bytes=size,
        sha256=digest,
        json_ok=json_ok,
        ok_field=ok_field,
        mode_field=mode_field,
        claim_level_field=claim_level_field,
    )


def build_evidence_bundle(
    manifest: dict[str, Any],
    *,
    mode: str = "sandbox",
    root: Path = ROOT,
) -> dict[str, Any]:
    """Build an evidence bundle without running external proof commands."""

    gates: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    remediation: list[dict[str, str]] = []
    artifact_count = 0
    existing_artifact_count = 0
    source_only_count = 0

    for gate in manifest.get("gate_artifacts", []):
        gate_id = str(gate.get("gate_id"))
        records = [inspect_artifact(path, root=root).to_dict() for path in gate.get("paths", [])]
        artifact_count += len(records)
        existing = [record for record in records if record["exists"]]
        existing_artifact_count += len(existing)
        missing = [record["path"] for record in records if not record["exists"]]
        source_only = any(
            "source" in str(record.get("mode_field", "")).lower() or "source" in record["path"] for record in existing
        )
        if source_only:
            source_only_count += 1
        failed = [record for record in existing if record.get("ok_field") is False or record.get("json_ok") is False]

        status = "pass"
        if failed:
            status = "fail"
            blockers.append(
                {"gate_id": gate_id, "class": "failed-artifact", "paths": [item["path"] for item in failed]}
            )
        elif mode == "strict" and missing and gate.get("required_for_strict"):
            status = "blocked"
            blockers.append({"gate_id": gate_id, "class": "missing-artifact", "paths": missing})
        elif source_only and mode == "strict" and gate.get("source_only_allowed"):
            status = "source_only"
            blockers.append(
                {"gate_id": gate_id, "class": "source-only-artifact", "paths": [item["path"] for item in existing]}
            )
        elif missing:
            status = "partial"

        if status != "pass":
            remediation.append(
                {"gate_id": gate_id, "action": str(gate.get("remediation", "rerun the gate and capture evidence"))}
            )

        gates.append(
            {
                "gate_id": gate_id,
                "label": gate.get("label"),
                "status": status,
                "required_for_strict": bool(gate.get("required_for_strict")),
                "source_only_allowed": bool(gate.get("source_only_allowed")),
                "artifacts": records,
                "missing_paths": missing,
                "remediation": gate.get("remediation"),
            }
        )

    ok = (
        not blockers if mode == "strict" else not any(blocker.get("class") == "failed-artifact" for blocker in blockers)
    )
    claim_level = "strict-local-candidate" if mode == "strict" and ok else "source-checked-testnet"
    return {
        "version": manifest.get("version"),
        "phase": manifest.get("phase"),
        "mode": mode,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "claim_level": claim_level,
        "ok": ok,
        "gate_count": len(gates),
        "artifact_count": artifact_count,
        "existing_artifact_count": existing_artifact_count,
        "source_only_gate_count": source_only_count,
        "blockers": blockers,
        "remediation": remediation,
        "gates": gates,
        "caveat": (
            None
            if mode == "strict"
            else "Sandbox evidence bundle may include partial or source-only artifacts; strict mode is required for professional-candidate claims."
        ),
    }


def evidence_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bundle.get("ok"),
        "version": bundle.get("version"),
        "phase": bundle.get("phase"),
        "mode": bundle.get("mode"),
        "claim_level": bundle.get("claim_level"),
        "gate_count": bundle.get("gate_count"),
        "artifact_count": bundle.get("artifact_count"),
        "existing_artifact_count": bundle.get("existing_artifact_count"),
        "blocker_count": len(bundle.get("blockers", [])),
        "remediation_count": len(bundle.get("remediation", [])),
    }
