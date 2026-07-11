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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN_SYSTEM = ROOT / "architecture" / "design-system.json"
E2E_MATRIX = ROOT / "architecture" / "browser-e2e-matrix.json"
SHARED_CSS = ROOT / "sites" / "shared" / "design-system.css"
SPEC_PATH = ROOT / "sites" / "tests" / "e2e" / "netcoin-product-matrix.spec.ts"

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
    if not SHARED_CSS.exists():
        issues.append("missing shared design-system CSS")
    if not SPEC_PATH.exists():
        issues.append("missing browser E2E matrix spec")
    text_blob = json.dumps(design).lower() + "\n" + css.lower() + "\n" + spec.lower()
    for token in REQUIRED_A11Y_TOKENS:
        needle = token.replace("_", " ")
        if token not in text_blob and needle not in text_blob and token.replace("_", "-") not in text_blob:
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
        # Future strict gate: route through Playwright when an accessibility spec exists.
        cmd = playwright_cmd() + ["test", str(SPEC_PATH)]
        try:
            proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=240, check=False)
            result["mode"] = "strict-playwright"
            result["playwright_returncode"] = proc.returncode
            result["playwright_stdout_tail"] = proc.stdout[-2000:]
            result["playwright_stderr_tail"] = proc.stderr[-2000:]
            result["ok"] = proc.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            result["mode"] = "strict-blocked"
            result["ok"] = False
            result["issues"] = list(result.get("issues", [])) + [f"strict accessibility runner unavailable: {exc}"]
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
