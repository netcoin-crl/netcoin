#!/usr/bin/env python3
"""Smoke-audit NetCoin public site assets.

Checks that each site has the shared shell assets, no shell drift exists, pages
link their scripts/styles, and JavaScript parses with Node when available.
"""

from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITES = ROOT / "sites"
SKIP = {"shared", "tests"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    issues: list[str] = []
    shared_js = SITES / "shared" / "site-shell.js"
    shared_css = SITES / "shared" / "site-shell.css"
    js_hash = sha(shared_js)
    css_hash = sha(shared_css)
    checked_sites = []
    for site in sorted(p for p in SITES.iterdir() if p.is_dir() and p.name not in SKIP):
        index = site / "index.html"
        if not index.exists():
            continue
        checked_sites.append(site.name)
        html = index.read_text(encoding="utf-8")
        for asset in ("site-shell.js", "site-shell.css"):
            if asset not in html:
                issues.append(f"{site.name}: index.html does not reference {asset}")
            if not (site / asset).exists():
                issues.append(f"{site.name}: missing {asset}")
        if (site / "site-shell.js").exists() and sha(site / "site-shell.js") != js_hash:
            issues.append(f"{site.name}: site-shell.js drifted from shared")
        if (site / "site-shell.css").exists() and sha(site / "site-shell.css") != css_hash:
            issues.append(f"{site.name}: site-shell.css drifted from shared")
        if "feature-dock" not in (site / "site-shell.js").read_text(encoding="utf-8"):
            issues.append(f"{site.name}: feature dock missing from shell")
        for js in sorted(site.glob("*.js")):
            try:
                subprocess.run(
                    ["node", "--check", str(js)],
                    cwd=ROOT,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=20,
                )
            except FileNotFoundError:
                break
            except subprocess.CalledProcessError as exc:
                issues.append(f"{js.relative_to(ROOT)}: node --check failed: {exc.stderr.strip()[:240]}")
            except subprocess.TimeoutExpired:
                issues.append(f"{js.relative_to(ROOT)}: node --check timed out")
    result = {"ok": not issues, "site_count": len(checked_sites), "sites": checked_sites, "issues": issues}
    print(json.dumps(result, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
