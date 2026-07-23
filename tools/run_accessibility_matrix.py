#!/usr/bin/env python3
"""Phase 1 accessibility source/strict gate.

The source gate checks that the project has the design-system/accessibility
contracts needed for a later real axe/Playwright run. Strict mode is reserved
for local/CI environments with a browser accessibility runner installed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN_SYSTEM = ROOT / "architecture" / "design-system.json"
E2E_MATRIX = ROOT / "architecture" / "browser-e2e-matrix.json"
SHARED_CSS = ROOT / "sites" / "shared" / "design-system.css"
SPEC_PATH = ROOT / "sites" / "tests" / "e2e" / "netcoin-product-matrix.spec.ts"
PHASE9_SPEC_PATH = ROOT / "sites" / "tests" / "e2e" / "phase9-accessibility.spec.js"
PHASE10_SPEC_PATH = ROOT / "sites" / "tests" / "e2e" / "phase10-mobile-accessibility.spec.js"
BROWSER_SMOKE_PATH = ROOT / "tools" / "run_browser_accessibility_smoke.py"

REQUIRED_A11Y_TOKENS = [
    "keyboard_navigation",
    "screen_reader_labels",
    "focus_visible",
    "contrast",
    "touch_targets",
]


def playwright_cmd() -> list[str]:
    local = ROOT / "node_modules" / ".bin" / ("playwright.cmd" if __import__("os").name == "nt" else "playwright")
    if local.exists():
        return [str(local)]
    return ["npx", "playwright"]


def source_check() -> dict[str, object]:
    issues: list[str] = []
    if not DESIGN_SYSTEM.exists():
        issues.append("missing architecture/design-system.json")
        design = {}
    else:
        design = json.loads(DESIGN_SYSTEM.read_text(encoding="utf-8"))
    if not E2E_MATRIX.exists():
        issues.append("missing architecture/browser-e2e-matrix.json")
        matrix = {}
    else:
        matrix = json.loads(E2E_MATRIX.read_text(encoding="utf-8"))
    css = SHARED_CSS.read_text(encoding="utf-8") if SHARED_CSS.exists() else ""
    spec = SPEC_PATH.read_text(encoding="utf-8") if SPEC_PATH.exists() else ""
    phase9_spec = PHASE9_SPEC_PATH.read_text(encoding="utf-8") if PHASE9_SPEC_PATH.exists() else ""
    phase10_spec = PHASE10_SPEC_PATH.read_text(encoding="utf-8") if PHASE10_SPEC_PATH.exists() else ""
    if not SHARED_CSS.exists():
        issues.append("missing shared design-system CSS")
    if not SPEC_PATH.exists():
        issues.append("missing browser E2E matrix spec")
    if not PHASE9_SPEC_PATH.exists():
        issues.append("missing Phase 9 accessibility E2E spec")
    if not PHASE10_SPEC_PATH.exists():
        issues.append("missing Phase 10 mobile accessibility E2E spec")
    if not BROWSER_SMOKE_PATH.exists():
        issues.append("missing browser accessibility smoke runner")
    text_blob = json.dumps(design).lower() + "\n" + css.lower() + "\n" + spec.lower() + "\n" + phase9_spec.lower() + "\n" + phase10_spec.lower()
    for token in REQUIRED_A11Y_TOKENS:
        needle = token.replace("_", " ")
        if token not in text_blob and needle not in text_blob and token.replace("_", "-") not in text_blob:
            issues.append(f"missing accessibility token {token}")
    for token in ["skip link", "command palette", "aria-live", "role", "focus-visible", "mobile viewport", "touch target"]:
        if token not in text_blob:
            issues.append(f"missing accessibility token {token}")
    surfaces = matrix.get("surfaces", []) if isinstance(matrix, dict) else []
    if len(surfaces) < 6:
        issues.append("browser E2E matrix should cover at least six product surfaces")
    return {
        "ok": not issues,
        "mode": "source-only",
        "surface_count": len(surfaces),
        "required_tokens": REQUIRED_A11Y_TOKENS,
        "issues": issues,
        "caveat": "source-only accessibility checks do not replace axe/Playwright execution",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run NetCoin accessibility source/strict matrix")
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    result = source_check()
    if args.strict and result.get("ok"):
        smoke_cmd = [sys.executable, str(BROWSER_SMOKE_PATH), "--require-browser"]
        try:
            smoke_proc = subprocess.run(smoke_cmd, cwd=ROOT, text=True, capture_output=True, timeout=300, check=False)
            result["mode"] = "strict-browser-smoke"
            result["browser_smoke_returncode"] = smoke_proc.returncode
            result["browser_smoke_stdout_tail"] = smoke_proc.stdout[-3000:]
            result["browser_smoke_stderr_tail"] = smoke_proc.stderr[-2000:]
            result["ok"] = smoke_proc.returncode == 0
            if smoke_proc.returncode != 0:
                result["issues"] = [*result.get("issues", []), "browser accessibility smoke failed or browser was unavailable"]
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            result["mode"] = "strict-blocked"
            result["ok"] = False
            result["issues"] = [*result.get("issues", []), f"strict accessibility runner unavailable: {exc}"]
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
