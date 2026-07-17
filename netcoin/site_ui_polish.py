"""Website UI clarity and copy-reduction checks for NetCoin v0.42."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "architecture" / "site-ui-polish.json"
SHARED_JS = ROOT / "sites" / "shared" / "site-shell.js"
SHARED_CSS = ROOT / "sites" / "shared" / "site-shell.css"


def load_site_ui_polish_manifest(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or MANIFEST).read_text(encoding="utf-8"))


def _string_literals_after(pattern: str, text: str) -> list[str]:
    return re.findall(pattern, text, flags=re.DOTALL)


def audit_site_ui_polish(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    manifest = load_site_ui_polish_manifest(root / "architecture" / "site-ui-polish.json")
    js = (root / "sites" / "shared" / "site-shell.js").read_text(encoding="utf-8")
    css = (root / "sites" / "shared" / "site-shell.css").read_text(encoding="utf-8")

    issues: list[str] = []
    if manifest.get("version") != "0.42.0":
        issues.append("site UI polish manifest version must be 0.42.0")
    if "feature-dock-compact" not in js or "document.createElement('details')" not in js:
        issues.append("feature directory must be collapsed into a details control")
    if "NetCoin product completion layer" in js or "This page follows the Phase 0/1" in js:
        issues.append("old verbose product-completion copy remains")
    for required in ["nc-ui-v042", "feature-dock-compact", "feature-dock-panel"]:
        if required not in css:
            issues.append(f"missing v0.42 CSS marker: {required}")
    # Preserved e2e/accessibility vocabulary must exist somewhere in the real,
    # functional site pages -- not necessarily in the shared shell copy, which
    # dropped its decorative per-surface "trust panels" (Explorer trust, etc.)
    # in favor of pages that actually implement the workflow.
    site_text = "".join(
        p.read_text(encoding="utf-8", errors="ignore").lower()
        for p in (root / "sites").rglob("*")
        if p.is_file() and p.suffix in (".js", ".html")
    )
    for token in manifest["copy_rules"]["preserve_e2e_tokens"]:
        if token.lower() not in site_text:
            issues.append(f"required browser/accessibility token missing from site pages: {token}")

    # Ensure every per-site shell asset matches shared shell assets.
    shared_js = (root / "sites" / "shared" / "site-shell.js").read_text(encoding="utf-8")
    shared_css = (root / "sites" / "shared" / "site-shell.css").read_text(encoding="utf-8")
    drifted: list[str] = []
    for site in sorted((root / "sites").iterdir()):
        if not site.is_dir() or site.name in {"shared", "tests"} or not (site / "index.html").exists():
            continue
        if (site / "site-shell.js").read_text(encoding="utf-8") != shared_js:
            drifted.append(f"{site.name}/site-shell.js")
        if (site / "site-shell.css").read_text(encoding="utf-8") != shared_css:
            drifted.append(f"{site.name}/site-shell.css")
    if drifted:
        issues.append("shared shell drift: " + ", ".join(drifted[:8]))

    intro_limit = int(manifest["copy_rules"]["panel_intro_max_chars"])
    card_limit = int(manifest["copy_rules"]["card_copy_max_chars"])
    intros = _string_literals_after(r"panel\('[^']+',\s*'([^']+)'", js)
    long_intros = [intro for intro in intros if len(intro) > intro_limit]
    if long_intros:
        issues.append("panel intro exceeds copy budget: " + long_intros[0][:80])
    card_copies = _string_literals_after(r"card\('[^']+',\s*'([^']+)'", js)
    long_cards = [copy for copy in card_copies if len(copy) > card_limit]
    if long_cards:
        issues.append("card copy exceeds copy budget: " + long_cards[0][:80])

    return {
        "ok": not issues,
        "version": manifest.get("version"),
        "phase": manifest.get("phase"),
        "audited_surface_count": len(manifest.get("audited_surfaces", [])),
        "design_flaw_count": len(manifest.get("design_flaws_found", [])),
        "implemented_change_count": len(manifest.get("implemented_changes", [])),
        "copy_budget": {
            "panel_intro_max_chars": intro_limit,
            "card_copy_max_chars": card_limit,
            "panel_intro_count": len(intros),
            "card_copy_count": len(card_copies),
        },
        "issues": issues,
    }


def validate_site_ui_polish(root: Path | None = None) -> list[str]:
    return audit_site_ui_polish(root).get("issues", [])
