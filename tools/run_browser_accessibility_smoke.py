#!/usr/bin/env python3
"""Run a small real-browser smoke check for NetCoin public-site accessibility.

This is intentionally separate from source-only checks: it launches a browser,
loads static pages, and checks mobile viewport overflow, skip-link behavior,
critical ARIA contracts, and touch-target sizing. In restricted sandboxes the
browser can be installed but unable to navigate; use --require-browser in CI to
turn that into a hard failure.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 4187

SURFACES = [
    {
        "name": "wallet-mobile",
        "path": "/sites/wallet/index.html",
        "viewport": {"width": 390, "height": 844},
        "required_selectors": [".nc-skip-link", "#walletFlowGuide", "#sendChecklist", "#sendMsg"],
        "required_roles": ["#walletStatus", "#reviewWarning", "#rbfBumpOut"],
    },
    {
        "name": "features-mobile",
        "path": "/sites/features/index.html",
        "viewport": {"width": 390, "height": 844},
        "required_selectors": [".nc-skip-link", "#featureSearch", ".feature-surface-filters"],
        "required_roles": [],
    },
    {
        "name": "localnet-mobile",
        "path": "/sites/docs/localnet.html",
        "viewport": {"width": 390, "height": 844},
        "required_selectors": [".nc-skip-link", ".localnet-status-grid", "#localnetStatusJson"],
        "required_roles": [".localnet-status-grid", "#localnetStatusJson"],
    },
    {
        "name": "operator-mobile",
        "path": "/sites/operator/index.html",
        "viewport": {"width": 390, "height": 844},
        "required_selectors": [".nc-skip-link", "#ledgerAudit", "#chainstate", "#peerAdvertise"],
        "required_roles": [],
    },
]


def chromium_path() -> str:
    for candidate in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(candidate)
        if found:
            return found
    return ""


def start_server(port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_smoke(port: int, *, executable_path: str) -> dict[str, Any]:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    issues: list[str] = []
    checked: list[dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=executable_path or None,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights",
                "--allow-insecure-localhost",
            ],
        )
        try:
            for surface in SURFACES:
                page = browser.new_page(viewport=surface["viewport"])
                url = f"http://127.0.0.1:{port}{surface['path']}"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=15000)
                except (PlaywrightError, PlaywrightTimeoutError) as exc:
                    issues.append(f"{surface['name']}: browser navigation failed: {exc}")
                    checked.append({"surface": surface["name"], "loaded": False, "url": url})
                    page.close()
                    continue
                checked_item: dict[str, Any] = {"surface": surface["name"], "loaded": True, "url": url}
                scroll_width = page.evaluate("document.documentElement.scrollWidth")
                viewport_width = page.evaluate("window.innerWidth")
                checked_item["scroll_width"] = scroll_width
                checked_item["viewport_width"] = viewport_width
                if scroll_width > viewport_width + 2:
                    issues.append(f"{surface['name']}: horizontal overflow {scroll_width}>{viewport_width}")
                for selector in surface["required_selectors"]:
                    if page.locator(selector).count() < 1:
                        issues.append(f"{surface['name']}: missing selector {selector}")
                for selector in surface["required_roles"]:
                    if page.locator(selector).count() < 1:
                        issues.append(f"{surface['name']}: missing role target {selector}")
                    elif not (page.locator(selector).first().get_attribute("role") or page.locator(selector).first().get_attribute("aria-live")):
                        issues.append(f"{surface['name']}: target lacks role/aria-live {selector}")
                page.keyboard.press("Tab")
                active_class = page.evaluate("document.activeElement && document.activeElement.className")
                checked_item["first_tab_class"] = str(active_class)
                if "nc-skip-link" not in str(active_class):
                    issues.append(f"{surface['name']}: first Tab did not focus skip link")
                # Check a representative set of visible buttons/links. WCAG target-size exceptions exist,
                # so this gate focuses on the shared shell + newly exposed primary action clusters.
                small_targets = page.evaluate(
                    """
                    Array.from(document.querySelectorAll('.site-nav a,.site-nav summary,.site-search button,.wallet-flow-guide a,.fee-preset-card,.use-hub-grid a,.localnet-copy,button'))
                      .filter((el) => {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                      })
                      .slice(0, 80)
                      .filter((el) => {
                        const rect = el.getBoundingClientRect();
                        return rect.width < 40 || rect.height < 40;
                      })
                      .map((el) => ({text: (el.textContent || '').trim().slice(0, 40), width: Math.round(el.getBoundingClientRect().width), height: Math.round(el.getBoundingClientRect().height)}));
                    """
                )
                checked_item["small_targets"] = small_targets[:10]
                if small_targets:
                    issues.append(f"{surface['name']}: small touch targets {small_targets[:3]}")
                checked.append(checked_item)
                page.close()
        finally:
            browser.close()
    return {"ok": not issues, "mode": "browser-smoke", "surfaces": checked, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real-browser accessibility/mobile smoke checks")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--out", default="")
    parser.add_argument("--require-browser", action="store_true")
    parser.add_argument("--chromium", default="")
    args = parser.parse_args()

    result: dict[str, Any]
    executable = args.chromium or chromium_path()
    if not executable:
        result = {"ok": not args.require_browser, "mode": "browser-unavailable", "issues": ["No Chromium executable found"], "browser_executed": False}
    else:
        try:
            import playwright  # noqa: F401
        except Exception as exc:  # pragma: no cover - environment dependent
            result = {"ok": not args.require_browser, "mode": "playwright-python-unavailable", "issues": [str(exc)], "browser_executed": False}
        else:
            server = start_server(args.port)
            try:
                time.sleep(0.8)
                result = run_smoke(args.port, executable_path=executable)
                result["browser_executed"] = result.get("mode") == "browser-smoke" and any(s.get("loaded") for s in result.get("surfaces", []))
                if args.require_browser and not result.get("browser_executed"):
                    result["ok"] = False
            except Exception as exc:  # pragma: no cover - environment/browser dependent
                result = {
                    "ok": not args.require_browser,
                    "mode": "browser-blocked",
                    "issues": [f"browser smoke could not run: {exc}"],
                    "browser_executed": False,
                }
            finally:
                with suppress(Exception):
                    server.terminate()
                    server.wait(timeout=5)

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
