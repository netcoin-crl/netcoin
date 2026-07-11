"""v0.40 product completion validation.

This module validates that the user-facing completion layer is implemented as
real shared UI assets and that the implementation stays honest about external
proof gates that cannot be faked in a sandbox.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "architecture" / "product-completion.json"
REQUIRED_SURFACES = {"wallet", "explorer", "markets", "faucet", "community", "exchange", "operator", "security", "global"}
REQUIRED_JS = {"NetCoinProductCompletion", "buildCommandPalette", "buildNotificationCenter", "mountSurfaceCompletion", "recordLocalNote"}
REQUIRED_CSS = {"nc-command-palette", "nc-notification-center", "nc-upgrade-panel", "nc-timeline", "nc-status-badge", "nc-mobile-table"}
EXTERNAL_GATES = {"cargo test --workspace", "all Rust parity binaries", "real Playwright E2E", "real CAPTCHA provider", "hardware signer device tests", "external security audit"}

@dataclass(frozen=True)
class CompletionSummary:
    ok: bool
    issue_count: int
    surface_count: int
    external_gate_count: int

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def load_product_completion_manifest(path: str | Path = MANIFEST) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_product_completion(manifest: dict[str, Any], *, root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    if manifest.get("version") != "0.40.1":
        issues.append("product completion manifest version must be 0.40.1")
    if manifest.get("phase") != "Phase 2 - Product Completion Implementation Pass":
        issues.append("manifest phase must describe product completion implementation")
    if "does not claim" not in str(manifest.get("honesty_note", "")):
        issues.append("honesty_note must explicitly avoid unsupported production claims")
    shared = manifest.get("shared_assets", {})
    css_path = root / str(shared.get("css", ""))
    js_path = root / str(shared.get("js", ""))
    if not css_path.exists():
        issues.append(f"missing shared CSS: {css_path}")
        css_text = ""
    else:
        css_text = css_path.read_text(encoding="utf-8")
    if not js_path.exists():
        issues.append(f"missing shared JS: {js_path}")
        js_text = ""
    else:
        js_text = js_path.read_text(encoding="utf-8")
    for marker in REQUIRED_CSS:
        if marker not in css_text:
            issues.append(f"shared CSS missing marker: {marker}")
    for marker in REQUIRED_JS:
        if marker not in js_text:
            issues.append(f"shared JS missing marker: {marker}")
    surfaces = manifest.get("implemented_surfaces")
    if not isinstance(surfaces, list):
        issues.append("implemented_surfaces must be a list")
        surface_names: set[str] = set()
    else:
        surface_names = {str(item.get("surface")) for item in surfaces if isinstance(item, dict)}
        missing = sorted(REQUIRED_SURFACES - surface_names)
        if missing:
            issues.append("implemented_surfaces missing: " + ", ".join(missing))
        for item in surfaces:
            if not isinstance(item, dict):
                issues.append("surface entry must be an object")
                continue
            features = item.get("features")
            if not isinstance(features, list) or len(features) < 2:
                issues.append(f"surface {item.get('surface')} must list multiple implemented features")
    external = manifest.get("strict_external_gates")
    if not isinstance(external, list):
        issues.append("strict_external_gates must be a list")
    else:
        gates = {str(item.get("gate")) for item in external if isinstance(item, dict)}
        missing = sorted(EXTERNAL_GATES - gates)
        if missing:
            issues.append("strict external gates missing: " + ", ".join(missing))
        for item in external:
            if not isinstance(item, dict):
                continue
            if item.get("cannot_fake") is not True:
                issues.append(f"external gate {item.get('gate')} must be marked cannot_fake")
            if not str(item.get("status", "")).startswith("requires-"):
                issues.append(f"external gate {item.get('gate')} must have requires-* status")
    # Verify shared shell copied to every first-class site.
    shared_css = (root / "sites" / "shared" / "site-shell.css").read_text(encoding="utf-8")
    shared_js = (root / "sites" / "shared" / "site-shell.js").read_text(encoding="utf-8")
    for site in sorted((root / "sites").iterdir()):
        if not site.is_dir() or site.name in {"shared", "tests"} or not (site / "index.html").exists():
            continue
        html = (site / "index.html").read_text(encoding="utf-8")
        if "site-shell.css" not in html:
            issues.append(f"{site.name}: missing site-shell.css reference")
        if "site-shell.js" not in html:
            issues.append(f"{site.name}: missing site-shell.js reference")
        if not (site / "site-shell.css").exists() or (site / "site-shell.css").read_text(encoding="utf-8") != shared_css:
            issues.append(f"{site.name}: site-shell.css is not synced with shared")
        if not (site / "site-shell.js").exists() or (site / "site-shell.js").read_text(encoding="utf-8") != shared_js:
            issues.append(f"{site.name}: site-shell.js is not synced with shared")
    return issues


def summarize_product_completion(manifest: dict[str, Any], issues: list[str]) -> CompletionSummary:
    return CompletionSummary(
        ok=not issues,
        issue_count=len(issues),
        surface_count=len(manifest.get("implemented_surfaces", [])),
        external_gate_count=len(manifest.get("strict_external_gates", [])),
    )
