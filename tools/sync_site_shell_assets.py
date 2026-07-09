#!/usr/bin/env python3
"""Rebuild per-site shell assets from the shared shell source.

All public microsites keep local ``site-shell.css`` / ``site-shell.js`` files so
their strict ``script-src 'self'`` CSP and one-root-per-subdomain Nginx layout
continue to work.  Edit ``sites/shared/`` first, then run this script to copy the
canonical assets into each site.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITES = ROOT / "sites"
SHARED_CSS = SITES / "shared" / "site-shell.css"
SHARED_JS = SITES / "shared" / "site-shell.js"


def main() -> None:
    css = SHARED_CSS.read_text()
    js = SHARED_JS.read_text()
    for site in SITES.iterdir():
        if not site.is_dir() or site.name == "shared":
            continue
        if (site / "index.html").exists():
            (site / "site-shell.css").write_text(css)
            (site / "site-shell.js").write_text(js)


if __name__ == "__main__":
    main()
