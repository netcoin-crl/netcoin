#!/usr/bin/env python3
"""Check that NetCoin's product surface is wired end-to-end.

This is stricter than a syntax check but intentionally lightweight: it verifies
that major public sites exist, share the common shell, expose the feature dock,
and that documented high-value API routes are present in OpenAPI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SITES = [
    "www",
    "wallet",
    "explorer",
    "markets",
    "community",
    "features",
    "architecture",
    "operator",
    "exchange",
    "faucet",
    "merchant",
    "pay",
    "api",
    "docs",
    "learn",
    "download",
    "security",
    "status",
    "nodes",
]
REQUIRED_OPENAPI = [
    "/health-center",
    "/product/status",
    "/feature-status",
    "/architecture",
    "/migration-status",
    "/parity-status",
    "/markets",
    "/community/posts",
    "/tokens",
    "/wallet/statement",
    "/explorer/address/{address}",
    "/explorer/tx/{txid}",
    "/explorer/block/{id}",
    "/explorer/mempool",
    "/wallet/workflow",
    "/wallet/drafts",
    "/operator/live",
    "/exchange/live",
    "/release/verify",
]
REQUIRED_PAGES = {
    "explorer": ["address.html", "tx.html", "block.html", "mempool.html"],
    "markets": ["trade.html", "portfolio.html", "disputes.html", "settlement.html"],
    "faucet": ["admin.html"],
    "download": ["verify.html"],
}


def node_check(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        subprocess.run(["node", "--check", str(path)], cwd=ROOT, check=True, capture_output=True, text=True)
        return "ok"
    except FileNotFoundError:
        return "node-missing"
    except subprocess.CalledProcessError as exc:
        return "syntax-error: " + (exc.stderr or exc.stdout).strip().splitlines()[-1]


def main() -> int:
    issues: list[str] = []
    sites = []
    for name in REQUIRED_SITES:
        folder = ROOT / "sites" / name
        index = folder / "index.html"
        shell_js = folder / "site-shell.js"
        shell_css = folder / "site-shell.css"
        js_files = sorted(p for p in folder.glob("*.js") if p.name != "site-shell.js")
        html = index.read_text(encoding="utf-8", errors="ignore") if index.exists() else ""
        rec = {
            "site": name,
            "index": index.exists(),
            "shared_shell": shell_js.exists() and shell_css.exists(),
            "feature_dock_source": "site-shell.js" in html or "site-nav" in html,
            "js": {p.name: node_check(p) for p in js_files},
        }
        sites.append(rec)
        if not rec["index"]:
            issues.append(f"missing site index: {name}")
        if not rec["shared_shell"]:
            issues.append(f"missing shared shell: {name}")
        if not rec["feature_dock_source"]:
            issues.append(f"site does not reference shell/dock: {name}")
        for page in REQUIRED_PAGES.get(name, []):
            if not (folder / page).exists():
                issues.append(f"missing product page: {name}/{page}")
        for js_name, status in rec["js"].items():
            if status not in {"ok", "node-missing"}:
                issues.append(f"JS check failed for {name}/{js_name}: {status}")
    openapi = (ROOT / "docs" / "openapi.yaml").read_text(encoding="utf-8", errors="ignore")
    for route in REQUIRED_OPENAPI:
        if f"  {route}:" not in openapi:
            issues.append(f"OpenAPI route missing: {route}")
    result = {"ok": not issues, "issues": issues, "sites": sites, "required_routes": REQUIRED_OPENAPI}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
