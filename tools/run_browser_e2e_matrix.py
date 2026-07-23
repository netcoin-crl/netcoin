#!/usr/bin/env python3
"""Source-check or execute the v0.36 browser E2E product matrix."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "architecture" / "browser-e2e-matrix.json"
SPEC_PATH = ROOT / "sites" / "tests" / "e2e" / "netcoin-product-matrix.spec.ts"
M1_WALLET_SPEC_PATH = ROOT / "sites" / "tests" / "e2e" / "m1-wallet-workflow.spec.js"
PHASE10_SPEC_PATH = ROOT / "sites" / "tests" / "e2e" / "phase10-mobile-accessibility.spec.js"


def playwright_cmd() -> list[str]:
    exe = "playwright.cmd" if __import__("os").name == "nt" else "playwright"
    local = ROOT / "node_modules" / ".bin" / exe
    if local.exists():
        return [str(local)]
    return ["npx", "playwright"]


def source_check() -> dict[str, object]:
    issues: list[str] = []
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    spec = SPEC_PATH.read_text(encoding="utf-8") if SPEC_PATH.exists() else ""
    m1_wallet_spec = M1_WALLET_SPEC_PATH.read_text(encoding="utf-8") if M1_WALLET_SPEC_PATH.exists() else ""
    phase10_spec = PHASE10_SPEC_PATH.read_text(encoding="utf-8") if PHASE10_SPEC_PATH.exists() else ""
    if not SPEC_PATH.exists():
        issues.append(f"missing {SPEC_PATH.relative_to(ROOT)}")
    if not M1_WALLET_SPEC_PATH.exists():
        issues.append(f"missing {M1_WALLET_SPEC_PATH.relative_to(ROOT)}")
    if not PHASE10_SPEC_PATH.exists():
        issues.append(f"missing {PHASE10_SPEC_PATH.relative_to(ROOT)}")
    for surface in matrix.get("surfaces", []):
        name = str(surface.get("surface", ""))
        path = ROOT / str(surface.get("path", ""))
        if not path.exists():
            issues.append(f"missing surface file {surface.get('path')}")
        if name not in spec:
            issues.append(f"spec missing surface {name}")
        for check in surface.get("required_checks", []):
            if str(check) not in spec:
                issues.append(f"spec missing check token {name}:{check}")
    required_wallet_tokens = [
        "create wallet",
        "receive",
        "send",
        "lock",
        "unlock",
        "tab shell",
        "btnQuizSkip",
        "btnConfirmSend",
        "btnLock",
        "walletTabs",
        "walletFlowGuide",
        "sendChecklist",
        "feePresetCards",
        "speedUpCard",
        "psbtToolsCard",
        "multisigToolsCard",
        "Confirm testnet send",
    ]
    for token in required_wallet_tokens:
        if token not in m1_wallet_spec:
            issues.append(f"M1 wallet workflow spec missing token: {token}")
    for token in ["Phase 10 mobile", "expectNoHorizontalOverflow", "wallet mobile surface", "operator and localnet", "featureSearch"]:
        if token not in phase10_spec:
            issues.append(f"Phase 10 mobile spec missing token: {token}")
    return {
        "ok": not issues,
        "mode": "source",
        "surface_count": len(matrix.get("surfaces", [])),
        "m1_wallet_workflow_spec": M1_WALLET_SPEC_PATH.exists(),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-playwright", action="store_true")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    result = source_check()
    if args.run_playwright and result["ok"]:
        try:
            proc = subprocess.run(
                playwright_cmd() + ["test", str(SPEC_PATH), str(M1_WALLET_SPEC_PATH), str(PHASE10_SPEC_PATH)],  # noqa: RUF005
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            result["mode"] = "playwright"
            result["playwright_returncode"] = proc.returncode
            result["playwright_stdout_tail"] = proc.stdout[-2000:]
            result["playwright_stderr_tail"] = proc.stderr[-2000:]
            result["ok"] = proc.returncode == 0
        except FileNotFoundError:
            result["mode"] = "source-playwright-missing"
            result["playwright_missing"] = True
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
