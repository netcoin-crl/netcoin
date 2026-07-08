"""Professional architecture manifest helpers for NetCoin.

This module documents the long-term hybrid language layout without changing the
current runnable Python reference app. It gives dashboards, docs, and CI checks a
single source of truth for where future Rust/TypeScript/Python upgrades belong.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "architecture" / "final-system-manifest.json"

REQUIRED_UPGRADE_DIRS = (
    "core-rs",
    "node-rs",
    "indexer-rs",
    "api",
    "web",
    "desktop",
    "mobile",
    "ops/python",
    "architecture",
)


def architecture_manifest(root: Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    path = base / "architecture" / "final-system-manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["upgrade_spaces"] = architecture_status(base)["spaces"]
    return data


def architecture_status(root: Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else ROOT
    spaces: list[dict[str, Any]] = []
    for rel in REQUIRED_UPGRADE_DIRS:
        path = base / rel
        spaces.append(
            {
                "path": rel,
                "exists": path.exists(),
                "kind": "directory" if path.is_dir() else "missing",
                "file_count": sum(1 for p in path.rglob("*") if p.is_file()) if path.exists() else 0,
            }
        )
    missing = [item["path"] for item in spaces if not item["exists"]]
    return {
        "ok": not missing,
        "spaces": spaces,
        "missing": missing,
        "final_version_target": "v1.0 production-candidate",
        "current_role": "Python reference app + hybrid migration spaces",
    }


def final_version_gates(root: Path | None = None) -> list[dict[str, Any]]:
    manifest = architecture_manifest(root)
    gates = manifest.get("final_version_gates", [])
    return [{"gate": str(gate), "required_for": manifest.get("final_version_target", "v1.0")} for gate in gates]


def architecture_summary(root: Path | None = None) -> dict[str, Any]:
    manifest = architecture_manifest(root)
    status = architecture_status(root)
    migration = None
    try:
        from .migration_status import (
            migration_status,
            final_version_readiness,
            parity_bridge_status,
            rust_typescript_parity_expansion,
        )

        migration = {
            "status": migration_status(root),
            "readiness": final_version_readiness(root),
            "parity": parity_bridge_status(root),
            "expansion": rust_typescript_parity_expansion(root),
        }
    except Exception as exc:  # pragma: no cover - dashboard fallback
        migration = {"error": str(exc)}
    return {
        "version": manifest.get("version"),
        "codename": manifest.get("codename"),
        "principle": manifest.get("principle"),
        "current_status": manifest.get("current_status"),
        "final_version_target": manifest.get("final_version_target"),
        "status": status,
        "layers": manifest.get("layers", []),
        "upgrade_lanes": manifest.get("upgrade_lanes", []),
        "final_version_gates": final_version_gates(root),
        "migration": migration,
    }
