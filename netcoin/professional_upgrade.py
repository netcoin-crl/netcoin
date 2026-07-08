"""Professional-upgrade manifest validator.

This module does not claim NetCoin is production ready. It gives operators and
CI a concrete way to track whether the code, docs, config, tests, and ops hooks
for the 15 professionalization workstreams exist in the repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path("config/professional_upgrade_manifest.json")
REQUIRED_KEYS = {"id", "title", "status", "anchors", "acceptance"}


def load_upgrade_manifest(root: str | Path = ".", path: str | Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    base = Path(root)
    manifest_path = base / path
    return json.loads(manifest_path.read_text())


def validate_upgrade_manifest(root: str | Path = ".", path: str | Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    base = Path(root)
    manifest = load_upgrade_manifest(base, path)
    workstreams = manifest.get("workstreams", [])
    issues: list[dict[str, Any]] = []
    for idx, item in enumerate(workstreams, start=1):
        missing = sorted(REQUIRED_KEYS - set(item))
        if missing:
            issues.append({"id": item.get("id", idx), "code": "missing_required_keys", "missing": missing})
        anchors = item.get("anchors", {})
        for kind, relpaths in anchors.items():
            if isinstance(relpaths, str):
                relpaths = [relpaths]
            for rel in relpaths or []:
                if not (base / rel).exists():
                    issues.append({"id": item.get("id", idx), "code": "missing_anchor", "kind": kind, "path": rel})
    return {
        "schema": manifest.get("schema"),
        "workstream_count": len(workstreams),
        "minimum_expected": 15,
        "ok": len(workstreams) >= 15 and not issues,
        "issues": issues,
        "production_claim": False,
        "note": "Tracks upgrade coverage only; external audit and testnet evidence are still required before production/mainnet claims.",
    }
