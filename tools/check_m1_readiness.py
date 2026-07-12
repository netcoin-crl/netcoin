#!/usr/bin/env python3
"""Offline M1 readiness gate for the strict-tested testnet package.

This is intentionally a source-level gate. It does not claim live node health,
real CAPTCHA credentials, deployed seeds, or Playwright browser execution. Those
remain separate operator checks before a push/deploy.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SITE_WALLET = ROOT / "sites" / "wallet"
WEB_WALLET = ROOT / "webwallet-browser" / "public"
STATUS = ROOT / "sites" / "status"
EXPLORER = ROOT / "sites" / "explorer"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def sri_for(path: Path) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(path.read_bytes()).digest()).decode()


def contains_all(text: str, tokens: Iterable[str]) -> list[str]:
    return [token for token in tokens if token not in text]


def check_json_ignore() -> dict[str, object]:
    path = ROOT / ".gitignore"
    text = read_text(path)
    issues: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "*.json":
            issues.append("blanket *.json ignore is still present")
        if stripped == "!pyproject-example.json":
            issues.append("old pyproject-only JSON exception is still present")
    required = [
        "wallet.json",
        "wallet-*.json",
        "node-state.json",
        "peers.json",
        "mempool.json",
        "chainstate.json",
        "local-*.json",
    ]
    issues.extend(f"missing explicit runtime JSON ignore: {token}" for token in contains_all(text, required))
    return {"ok": not issues, "file": rel(path), "issues": issues}


def check_wallet_polish_and_sri() -> dict[str, object]:
    html_path = SITE_WALLET / "index.html"
    app_path = SITE_WALLET / "wallet-app.js"
    web_html_path = WEB_WALLET / "wallet.html"
    web_app_path = WEB_WALLET / "wallet-app.js"
    html = read_text(html_path)
    app = read_text(app_path)
    web_html = read_text(web_html_path)
    web_app = read_text(web_app_path)
    issues: list[str] = []

    issues.extend(
        f"wallet HTML missing token: {token}"
        for token in contains_all(
            html,
            [
                'class="wallet-page-title"',
                'class="pill testnet-pill" id="netpill"',
                '<details class="balance-explain">',
                "<summary>What this balance means</summary>",
                '<button id="btnCopy">Copy address</button>',
                '<button id="btnRefresh" class="secondary ghost">Refresh</button>',
                "wallet-v043-m1-flaw-pass",
                'class="wallet-page m1-hide-shell-search"',
                "body.m1-hide-shell-search .site-search{display:none!important}",
                "unlockAutoLock",
                "privateKeyAutoLock",
            ],
        )
    )
    if '<h1 style="font-size:' in html:
        issues.append("wallet HTML still contains card-level h1 inline font-size headings")
    for token in [
        'const AUTO_LOCK_STORE = "ncw.autoLockMinutes.v1";',
        "function scheduleAutoLock()",
        "function noteWalletActivity()",
        "Auto-lock disabled for this tab",
    ]:
        if token not in app:
            issues.append(f"wallet app missing auto-lock token: {token}")
    for label, js in [("site", app), ("webwallet", web_app)]:
        if "function ensureWalletTabShell()" not in js:
            issues.append(f"{label} wallet missing ensureWalletTabShell")
            continue
        section = js[js.index("function ensureWalletTabShell()") :]
        end = section.find("function applyWalletMode()")
        if end != -1:
            section = section[:end]
        if "wallet.prepend(tabs);" not in section:
            issues.append(f"{label} wallet tab shell does not prepend tabs deterministically")
        for forbidden in ["insertBefore(tabs", "insertBefore(section", '$("btnLock")']:
            if forbidden in section:
                issues.append(f"{label} wallet tab shell still depends on forbidden token: {forbidden}")
    match = re.search(r'<script src="wallet-app\.js\?v=[^"]+" integrity="([^"]+)"', html)
    expected_sri = sri_for(app_path)
    if not match:
        issues.append("site wallet HTML missing SRI-pinned wallet-app.js script tag")
    elif match.group(1) != expected_sri:
        issues.append(f"site wallet SRI mismatch: expected {expected_sri}, found {match.group(1)}")
    site_src = re.search(r'<script src="(wallet-app\.js\?v=[^"]+)" integrity=', html)
    web_src = re.search(r'<script src="(wallet-app\.js\?v=[^"]+)"', web_html)
    if not site_src or not web_src:
        issues.append("site and webwallet HTML must both reference wallet-app.js with a cache-buster")
    elif site_src.group(1) != web_src.group(1):
        issues.append(f"site/webwallet wallet-app cache-busters differ: {site_src.group(1)} != {web_src.group(1)}")
    return {
        "ok": not issues,
        "files": [rel(html_path), rel(app_path), rel(web_html_path), rel(web_app_path)],
        "wallet_app_sri": expected_sri,
        "issues": issues,
    }


def check_wallet_e2e_wiring() -> dict[str, object]:
    runner = ROOT / "tools" / "run_browser_e2e_matrix.py"
    spec = ROOT / "sites" / "tests" / "e2e" / "m1-wallet-workflow.spec.js"
    issues: list[str] = []
    if not spec.exists():
        issues.append(f"missing {rel(spec)}")
        spec_text = ""
    else:
        spec_text = read_text(spec)
    runner_text = read_text(runner)
    for token in [
        "M1_WALLET_SPEC_PATH",
        "m1-wallet-workflow.spec.js",
        'playwright_cmd() + ["test", str(SPEC_PATH), str(M1_WALLET_SPEC_PATH)]',
    ]:
        if token not in runner_text:
            issues.append(f"browser matrix runner missing token: {token}")
    for token in [
        "create wallet",
        "receive",
        "send",
        "lock",
        "unlock",
        "tab shell",
        "btnConfirmSend",
        "btnLock",
        "walletTabs",
    ]:
        if token not in spec_text:
            issues.append(f"M1 wallet E2E spec missing token: {token}")
    return {"ok": not issues, "files": [rel(runner), rel(spec)], "issues": issues}


def check_status_page() -> dict[str, object]:
    html_path = STATUS / "index.html"
    js_path = STATUS / "status.js"
    css_path = STATUS / "status.css"
    html = read_text(html_path)
    js = read_text(js_path)
    issues: list[str] = []
    for token in ["statusHeight", "statusMempool", "statusPeers", "statusUptime", "networkState"]:
        if token not in html:
            issues.append(f"status HTML missing snapshot token: {token}")
    for endpoint in ["/api/health", "/api/latest?n=1", "/api/mempool?transactions=0", "/api/peers"]:
        if endpoint not in js:
            issues.append(f"status JS missing endpoint: {endpoint}")
    for rel_path in ["api/health", "api/latest", "api/mempool", "api/peers"]:
        path = ROOT / rel_path
        if not path.exists():
            issues.append(f"missing status fallback: {rel_path}")
            continue
        try:
            payload = json.loads(read_text(path))
        except json.JSONDecodeError as exc:
            issues.append(f"invalid JSON fallback {rel_path}: {exc}")
            continue
        if payload.get("status") != "source-fallback":
            issues.append(f"fallback {rel_path} must declare status=source-fallback")
    return {"ok": not issues, "files": [rel(html_path), rel(js_path), rel(css_path)], "issues": issues}


def check_faucet_hardening() -> dict[str, object]:
    env_path = ROOT / ".env.example"
    server_path = ROOT / "tools" / "faucet_server.py"
    provider_path = ROOT / "netcoin" / "captcha_provider.py"
    env_text = read_text(env_path)
    server = read_text(server_path)
    provider = read_text(provider_path)
    issues: list[str] = []
    for token in [
        "NETCOIN_FAUCET_CAPTCHA_PROVIDER=none",
        "NETCOIN_FAUCET_CAPTCHA_SITEKEY=replace-with-provider-site-key",
        "NETCOIN_FAUCET_CAPTCHA_SECRET=replace-with-provider-secret",
        "NETCOIN_FAUCET_ADDRESS_COOLDOWN_SECONDS=3600",
        "NETCOIN_FAUCET_POW_DIFFICULTY=0",
        "NETCOIN_FAUCET_ADMIN_TOKEN=replace-with-long-random-admin-token",
    ]:
        if token not in env_text:
            issues.append(f".env.example missing faucet token: {token}")
    for token in ["load_captcha_config", "NETCOIN_FAUCET_CAPTCHA", "verify_token"]:
        if token not in provider:
            issues.append(f"captcha provider missing token: {token}")
    for token in [
        "def captcha_status_payload()",
        "def verify_captcha(form: dict, remote_ip: str)",
        "ADDRESS_COOLDOWN_SECONDS",
        "captcha_status_payload()",
        'record_abuse(state, ip, f"captcha:{captcha_reason}"',
    ]:
        if token not in server:
            issues.append(f"faucet server missing token: {token}")
    forbidden_secret_patterns = [
        r"NETCOIN_FAUCET_CAPTCHA_SECRET=(?!replace-with-provider-secret)(\S+)",
        r"NETCOIN_FAUCET_ADMIN_TOKEN=(?!replace-with-long-random-admin-token)(\S+)",
    ]
    for pattern in forbidden_secret_patterns:
        if re.search(pattern, env_text):
            issues.append(".env.example appears to contain a non-placeholder secret")
    return {"ok": not issues, "files": [rel(env_path), rel(server_path), rel(provider_path)], "issues": issues}


def check_explorer_mempool() -> dict[str, object]:
    html_path = EXPLORER / "mempool.html"
    js_path = EXPLORER / "explorer-pro.js"
    server_path = ROOT / "netcoin" / "explorer_server.py"
    fallback_path = ROOT / "api" / "fee-estimates"
    html = read_text(html_path)
    js = read_text(js_path)
    server = read_text(server_path)
    issues: list[str] = []
    for token in ["explorer-pro.css?v=20260711-m1-mempool-live", "explorer-pro.js?v=20260711-m1-mempool-live"]:
        if token not in html:
            issues.append(f"mempool HTML missing cache-buster token: {token}")
    for token in [
        "new EventSource('/api/events/stream')",
        "api('/fee-estimates')",
        "fee_rate_percentiles",
        "10th percentile",
        "50th percentile",
        "90th percentile",
    ]:
        if token not in js:
            issues.append(f"explorer JS missing live mempool token: {token}")
    for token in ["def fee_estimates_payload", "def percentile_fee_rate", "fee_rate_percentiles", "mempool_depth"]:
        if token not in server:
            issues.append(f"explorer server missing fee-estimate token: {token}")
    if not fallback_path.exists():
        issues.append("missing api/fee-estimates fallback")
    else:
        payload = json.loads(read_text(fallback_path))
        if sorted(payload.get("fee_rate_percentiles", {})) != ["p10", "p50", "p90"]:
            issues.append("api/fee-estimates fallback missing p10/p50/p90 percentile bands")
    return {
        "ok": not issues,
        "files": [rel(html_path), rel(js_path), rel(server_path), rel(fallback_path)],
        "issues": issues,
    }


def check_ci_source_gate() -> dict[str, object]:
    workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
    runner_path = ROOT / "tools" / "run_m1_release_candidate.py"
    test_path = ROOT / "tests" / "test_m1_ci_gate_wiring.py"
    workflow = read_text(workflow_path)
    runner = read_text(runner_path)
    issues: list[str] = []
    if "fast:" not in workflow or "  full:" not in workflow:
        issues.append("CI workflow missing recognizable fast/full job boundaries")
        fast_block = workflow
    else:
        fast_block = workflow.split("  fast:", 1)[1].split("  full:", 1)[0]
    for token in [
        "Set up Node for source asset checks",
        "M1 source release-candidate gate",
        "python tools/run_m1_release_candidate.py --profile source --out reports/m1_release_candidate_report.json --stop-on-fail",
    ]:
        if token not in fast_block:
            issues.append(f"fast CI job missing M1 gate token: {token}")
    if "tests/test_m1_ci_gate_wiring.py" not in runner:
        issues.append("M1 source runner does not include CI gate wiring tests")
    if not test_path.exists():
        issues.append(f"missing CI gate wiring test: {rel(test_path)}")
    return {"ok": not issues, "files": [rel(workflow_path), rel(runner_path), rel(test_path)], "issues": issues}


def check_incident_response_runbook() -> dict[str, object]:
    doc_path = ROOT / "docs" / "INCIDENT_RESPONSE.md"
    status_html_path = STATUS / "index.html"
    status_css_path = STATUS / "status.css"
    doc = read_text(doc_path)
    status_html = read_text(status_html_path)
    status_css = read_text(status_css_path)
    issues: list[str] = []
    for token in [
        "# NetCoin M1 Incident Response Runbook",
        "Incident owner",
        "Scribe",
        "Operator",
        "Communicator",
        "Reviewer",
        "SEV-1",
        "SEV-2",
        "SEV-3",
        "## First 15 minutes",
        "## Triage commands",
        "## Containment playbooks",
        "### Wallet UI or SRI failure",
        "### Faucet abuse or CAPTCHA failure",
        "### Explorer/API outage",
        "### Seed node issue",
        "### Release artifact or checksum issue",
        "## Public communication templates",
        "## Recovery checklist",
        "## Postmortem template",
        "curl -sk -H 'Host: status.netcoin.online' https://18.220.89.128/ | head -6",
        "Do not run unattended `sudo systemctl` commands on live seeds",
    ]:
        if token not in doc:
            issues.append(f"incident runbook missing token: {token}")
    for token in [
        "incidentResponseTitle",
        "M1 operator runbook",
        "Incident response",
        "https://docs.netcoin.online/INCIDENT_RESPONSE.md",
        "severity levels, owner/scribe assignment",
    ]:
        if token not in status_html:
            issues.append(f"status page missing incident-response token: {token}")
    for token in ["m1-incident-runbook", ".incident-card"]:
        if token not in status_html + status_css:
            issues.append(f"status incident styling/cache-buster missing token: {token}")
    return {"ok": not issues, "files": [rel(doc_path), rel(status_html_path), rel(status_css_path)], "issues": issues}


def check_testnet_user_journey() -> dict[str, object]:
    doc_path = ROOT / "docs" / "TESTNET_USER_JOURNEY.md"
    html_path = ROOT / "sites" / "docs" / "testnet-user-journey.html"
    index_path = ROOT / "sites" / "docs" / "index.html"
    css_path = ROOT / "sites" / "docs" / "docs.css"
    issues: list[str] = []
    if not doc_path.exists():
        issues.append(f"missing testnet user journey doc: {rel(doc_path)}")
        doc = ""
    else:
        doc = read_text(doc_path)
    if not html_path.exists():
        issues.append(f"missing public testnet user journey page: {rel(html_path)}")
        html = ""
    else:
        html = read_text(html_path)
    index_html = read_text(index_path)
    css = read_text(css_path)

    for token in [
        "# NetCoin M1 Testnet User Journey",
        "Open the wallet",
        "Claim faucet NET",
        "Confirm the incoming transaction",
        "Send a small test payment",
        "Lock the wallet",
        "Check the status page",
        "testnet NET has no real-money value",
        "does not claim mainnet readiness",
    ]:
        if token not in doc:
            issues.append(f"testnet user journey doc missing token: {token}")
    for token in [
        "M1 tester path",
        "wallet.netcoin.online",
        "faucet.netcoin.online",
        "explorer.netcoin.online",
        "status.netcoin.online",
        "First-time tester checklist",
        "make m1-rc-check",
        "make m1-rc-strict",
        "Host: wallet.netcoin.online",
        "does not claim mainnet readiness",
    ]:
        if token not in html:
            issues.append(f"testnet user journey page missing token: {token}")
    for forbidden in ["onclick=", "<script>"]:
        if forbidden in html:
            issues.append(f"testnet user journey page contains forbidden inline behavior: {forbidden}")
    for token in [
        "testnet-user-journey.html",
        "M1 tester path: wallet -> faucet -> explorer -> status",
    ]:
        if token not in index_html:
            issues.append(f"docs index missing user journey token: {token}")
    for token in ["M1 user journey: public tester path", ".testnet-journey-page .journey-steps"]:
        if token not in css:
            issues.append(f"docs CSS missing user journey token: {token}")
    return {
        "ok": not issues,
        "files": [rel(doc_path), rel(html_path), rel(index_path), rel(css_path)],
        "issues": issues,
    }


def check_testnet_feedback_intake() -> dict[str, object]:
    doc_path = ROOT / "docs" / "TESTNET_FEEDBACK_LOG.md"
    html_path = ROOT / "sites" / "docs" / "testnet-feedback.html"
    journey_doc_path = ROOT / "docs" / "TESTNET_USER_JOURNEY.md"
    journey_html_path = ROOT / "sites" / "docs" / "testnet-user-journey.html"
    index_path = ROOT / "sites" / "docs" / "index.html"
    css_path = ROOT / "sites" / "docs" / "docs.css"
    issues: list[str] = []
    if not doc_path.exists():
        issues.append(f"missing testnet feedback log: {rel(doc_path)}")
        doc = ""
    else:
        doc = read_text(doc_path)
    if not html_path.exists():
        issues.append(f"missing public testnet feedback page: {rel(html_path)}")
        html = ""
    else:
        html = read_text(html_path)
    journey_doc = read_text(journey_doc_path)
    journey_html = read_text(journey_html_path)
    index_html = read_text(index_path)
    css = read_text(css_path)

    for token in [
        "# NetCoin M1 Testnet Feedback Log",
        "two-week M1 tester loop",
        "no tester should share a seed phrase",
        "Device/browser",
        "Expected | What should have happened",
        "Actual | What happened instead",
        "Status snapshot",
        "P0:",
        "P1:",
        "Retest result:",
        "does not claim live seed deployment",
    ]:
        if token not in doc:
            issues.append(f"testnet feedback log missing token: {token}")
    for token in [
        "M1 feedback loop",
        "Turn tester friction into reproducible bugs.",
        "testnet-user-journey.html",
        "Never collect secrets",
        "Device/browser:",
        "Expected result:",
        "Actual result:",
        "Status snapshot if relevant:",
        "make m1-rc-strict",
        "does not claim mainnet readiness",
    ]:
        if token not in html:
            issues.append(f"testnet feedback page missing token: {token}")
    for forbidden in ["onclick=", "<script>"]:
        if forbidden in html:
            issues.append(f"testnet feedback page contains forbidden inline behavior: {forbidden}")
    for token in [
        "testnet-feedback.html",
        "M1 feedback intake: capture friction without collecting secrets",
    ]:
        if token not in index_html:
            issues.append(f"docs index missing feedback token: {token}")
    for token in ["Report friction", "Use the feedback intake template"]:
        if token not in journey_html:
            issues.append(f"testnet user journey page missing feedback token: {token}")
    for token in ["docs/TESTNET_FEEDBACK_LOG.md", "https://docs.netcoin.online/testnet-feedback.html"]:
        if token not in journey_doc:
            issues.append(f"testnet user journey doc missing feedback token: {token}")
    for token in ["M1 feedback intake: tester issue capture", ".testnet-feedback-page .notice.warn"]:
        if token not in css:
            issues.append(f"docs CSS missing feedback token: {token}")
    return {
        "ok": not issues,
        "files": [
            rel(doc_path),
            rel(html_path),
            rel(journey_doc_path),
            rel(journey_html_path),
            rel(index_path),
            rel(css_path),
        ],
        "issues": issues,
    }


def check_testnet_pilot_plan() -> dict[str, object]:
    doc_path = ROOT / "docs" / "TESTNET_PILOT_PLAN.md"
    html_path = ROOT / "sites" / "docs" / "testnet-pilot.html"
    journey_doc_path = ROOT / "docs" / "TESTNET_USER_JOURNEY.md"
    feedback_doc_path = ROOT / "docs" / "TESTNET_FEEDBACK_LOG.md"
    journey_html_path = ROOT / "sites" / "docs" / "testnet-user-journey.html"
    feedback_html_path = ROOT / "sites" / "docs" / "testnet-feedback.html"
    index_path = ROOT / "sites" / "docs" / "index.html"
    css_path = ROOT / "sites" / "docs" / "docs.css"
    issues: list[str] = []
    if not doc_path.exists():
        issues.append(f"missing testnet pilot plan: {rel(doc_path)}")
        doc = ""
    else:
        doc = read_text(doc_path)
    if not html_path.exists():
        issues.append(f"missing public testnet pilot page: {rel(html_path)}")
        html = ""
    else:
        html = read_text(html_path)
    journey_doc = read_text(journey_doc_path)
    feedback_doc = read_text(feedback_doc_path)
    journey_html = read_text(journey_html_path)
    feedback_html = read_text(feedback_html_path)
    index_html = read_text(index_path)
    css = read_text(css_path)

    for token in [
        "# NetCoin M1 Two-Week Testnet Pilot Plan",
        "5-10 friends actively use the wallet for two weeks",
        "make m1-rc-check",
        "make m1-rc-strict",
        "Start with 5 testers",
        "expand to 10",
        "Required tester loop",
        "Daily operating rhythm",
        "Stop conditions",
        "Closeout report template",
        "does not claim live seed deployment",
        "real CAPTCHA credentials in source control",
    ]:
        if token not in doc:
            issues.append(f"testnet pilot plan doc missing token: {token}")
    for token in [
        "M1 pilot plan",
        "Run the two-week tester loop without losing evidence.",
        "testnet-user-journey.html",
        "testnet-feedback.html",
        "make m1-rc-check",
        "make m1-rc-strict",
        "Start with 5 testers",
        "expand to 10",
        "Stop conditions",
        "Closeout report fields",
        "does not claim mainnet readiness",
    ]:
        if token not in html:
            issues.append(f"testnet pilot page missing token: {token}")
    for forbidden in ["onclick=", "<script>"]:
        if forbidden in html:
            issues.append(f"testnet pilot page contains forbidden inline behavior: {forbidden}")
    for token in [
        "testnet-pilot.html",
        "M1 two-week pilot plan: 5-10 testers with stop conditions",
    ]:
        if token not in index_html:
            issues.append(f"docs index missing pilot token: {token}")
    for token in ["testnet-pilot.html", "Pilot plan", "two-week pilot plan"]:
        if token not in journey_html:
            issues.append(f"testnet user journey page missing pilot token: {token}")
    for token in ["testnet-pilot.html", "Open pilot plan", "pilot plan"]:
        if token not in feedback_html:
            issues.append(f"testnet feedback page missing pilot token: {token}")
    for token in ["docs/TESTNET_PILOT_PLAN.md", "https://docs.netcoin.online/testnet-pilot.html"]:
        if token not in journey_doc:
            issues.append(f"testnet user journey doc missing pilot token: {token}")
    if "docs/TESTNET_PILOT_PLAN.md" not in feedback_doc:
        issues.append("testnet feedback log missing pilot plan reference")
    for token in ["M1 pilot plan: two-week tester loop", ".testnet-pilot-page .pilot-checklist"]:
        if token not in css:
            issues.append(f"docs CSS missing pilot token: {token}")
    return {
        "ok": not issues,
        "files": [
            rel(doc_path),
            rel(html_path),
            rel(journey_doc_path),
            rel(feedback_doc_path),
            rel(journey_html_path),
            rel(feedback_html_path),
            rel(index_path),
            rel(css_path),
        ],
        "issues": issues,
    }


def check_m1_live_smoke_tool() -> dict[str, object]:
    tool_path = ROOT / "tools" / "check_m1_live_smoke.py"
    doc_path = ROOT / "docs" / "M1_LIVE_SMOKE_CHECK.md"
    makefile_path = ROOT / "Makefile"
    runner_path = ROOT / "tools" / "run_m1_release_candidate.py"
    test_path = ROOT / "tests" / "test_m1_live_smoke_tool.py"
    issues: list[str] = []
    tool = read_text(tool_path) if tool_path.exists() else ""
    doc = read_text(doc_path) if doc_path.exists() else ""
    makefile = read_text(makefile_path)
    runner = read_text(runner_path)

    if not tool_path.exists():
        issues.append(f"missing live smoke tool: {rel(tool_path)}")
    if not doc_path.exists():
        issues.append(f"missing live smoke doc: {rel(doc_path)}")
    if not test_path.exists():
        issues.append(f"missing live smoke regression test: {rel(test_path)}")
    for token in [
        'DEFAULT_SEED_IP = "18.220.89.128"',
        'DEFAULT_HISTORY_DIR = "reports/live_smoke_history"',
        "curl -sk -H 'Host: {self.host}' https://{seed_ip}{self.path} | head -20",
        'headers={"Host": check.host',
        "wallet_script_expectations",
        '"--run"',
        '"seed deployment"',
        '"mainnet readiness"',
    ]:
        if token not in tool:
            issues.append(f"live smoke tool missing token: {token}")
    for forbidden in ["systemctl", "scp ", "sudo ", "deploy_seed.sh"]:
        if forbidden in tool:
            issues.append(f"live smoke tool contains forbidden deployment token: {forbidden}")
    for token in [
        "# NetCoin M1 Live Smoke Check",
        "Host-header curl commands",
        "reports/live_smoke_history",
        "wallet HTML SRI",
        "python3 tools/check_m1_live_smoke.py --run",
        "docs/INCIDENT_RESPONSE.md",
        "does not claim seed deployment",
    ]:
        if token not in doc:
            issues.append(f"live smoke doc missing token: {token}")
    for token in ["m1-live-smoke-plan", "m1-live-smoke:", "live-testnet-smoke:", "tools/check_m1_live_smoke.py --run"]:
        if token not in makefile:
            issues.append(f"Makefile missing live smoke token: {token}")
    workflow = ROOT / ".github" / "workflows" / "live-smoke.yml"
    if not workflow.exists():
        issues.append(f"missing live smoke GitHub Actions workflow: {rel(workflow)}")
    else:
        workflow_text = read_text(workflow)
        for token in ["schedule:", "tools/check_m1_live_smoke.py", "reports/live_smoke_history"]:
            if token not in workflow_text:
                issues.append(f"live smoke workflow missing token: {token}")
    for token in ["m1-live-smoke-plan", "M1 live smoke dry-run plan", "tests/test_m1_live_smoke_tool.py"]:
        if token not in runner:
            issues.append(f"M1 source runner missing live smoke token: {token}")
    return {
        "ok": not issues,
        "files": [
            rel(tool_path),
            rel(doc_path),
            rel(makefile_path),
            rel(runner_path),
            rel(test_path),
            rel(ROOT / ".github" / "workflows" / "live-smoke.yml"),
        ],
        "issues": issues,
    }


def run_checks() -> dict[str, object]:
    checks = {
        "json_ignore": check_json_ignore(),
        "wallet_polish_and_sri": check_wallet_polish_and_sri(),
        "wallet_e2e_wiring": check_wallet_e2e_wiring(),
        "status_page_snapshot": check_status_page(),
        "faucet_hardening": check_faucet_hardening(),
        "explorer_mempool_fee_bands": check_explorer_mempool(),
        "ci_m1_source_gate": check_ci_source_gate(),
        "incident_response_runbook": check_incident_response_runbook(),
        "testnet_user_journey": check_testnet_user_journey(),
        "testnet_feedback_intake": check_testnet_feedback_intake(),
        "testnet_pilot_plan": check_testnet_pilot_plan(),
        "m1_live_smoke_tool": check_m1_live_smoke_tool(),
    }
    incomplete = [name for name, result in checks.items() if not result.get("ok")]
    return {
        "ok": not incomplete,
        "scope": "M1 offline source readiness",
        "does_not_claim": [
            "live seed deployment",
            "real CAPTCHA credentials",
            "external audit completion",
            "hardware wallet support",
            "full CI success without local runner output",
        ],
        "checks": checks,
        "incomplete": incomplete,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate offline M1 readiness markers.")
    parser.add_argument("--out", default="", help="Optional JSON report path.")
    args = parser.parse_args()
    result = run_checks()
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
