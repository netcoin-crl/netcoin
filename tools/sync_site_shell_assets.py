#!/usr/bin/env python3
"""Rebuild per-site shell wrappers from the shared shell assets.

All public microsites keep local ``site-shell.css`` / ``site-shell.js`` files so
older deployment configs and CSPs continue to work.  The real implementation now
lives in ``sites/shared/`` to avoid maintaining 19 duplicated copies.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITES = ROOT / "sites"
CSS_WRAPPER = '@import url("../shared/site-shell.css?v=20260706-shared-shell");\n'
JS_WRAPPER = '''(function(){
  "use strict";
  var script = document.createElement("script");
  script.src = "../shared/site-shell.js?v=20260706-shared-shell";
  script.defer = true;
  document.head.appendChild(script);
})();
'''


def main() -> None:
    for site in SITES.iterdir():
        if not site.is_dir() or site.name == "shared":
            continue
        if (site / "index.html").exists():
            (site / "site-shell.css").write_text(CSS_WRAPPER)
            (site / "site-shell.js").write_text(JS_WRAPPER)


if __name__ == "__main__":
    main()
