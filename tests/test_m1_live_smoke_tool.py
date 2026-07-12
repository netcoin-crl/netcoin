from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_live_smoke_tool_is_operator_safe_and_host_header_based() -> None:
    source = read("tools/check_m1_live_smoke.py")
    assert 'DEFAULT_SEED_IP = "18.220.89.128"' in source
    assert 'DEFAULT_HISTORY_DIR = "reports/live_smoke_history"' in source
    assert "curl -sk -H 'Host: {self.host}' https://{seed_ip}{self.path} | head -20" in source
    assert 'headers={"Host": check.host' in source
    assert "wallet_script_expectations" in source
    assert "sha384" in source
    assert "--run" in source
    assert "seed deployment" in source
    assert "mainnet readiness" in source
    for forbidden in ["systemctl", "scp ", "sudo ", "deploy_seed.sh"]:
        assert forbidden not in source


def test_live_smoke_dry_run_writes_plan_without_network(tmp_path: Path) -> None:
    out = tmp_path / "m1-live-smoke-plan.json"
    proc = subprocess.run(
        [
            sys.executable,
            "tools/check_m1_live_smoke.py",
            "--out",
            str(out),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["mode"] == "dry-run"
    assert payload["seed_ip"] == "18.220.89.128"
    assert payload["scope"] == "live testnet smoke plan"
    assert {check["id"] for check in payload["checks"]} == {
        "api-info",
        "api-supply",
        "api-emission",
        "api-fee-estimates",
        "api-p2p-hardening",
        "wallet-home",
        "wallet-sri",
        "faucet-home",
        "explorer-mempool",
        "status-home",
        "docs-journey",
        "api-health",
    }
    for check in payload["checks"]:
        assert check["status"] == "planned"
        assert "curl -sk -H 'Host:" in check["curl"] or check["id"] == "wallet-sri"
    sri = next(check for check in payload["checks"] if check["id"] == "wallet-sri")
    assert any(item["script"] == "wallet-app.js" for item in sri["required_scripts"])


def test_live_smoke_history_path_is_append_only_timestamped() -> None:
    from tools.check_m1_live_smoke import history_path

    path = history_path("reports/live_smoke_history")
    assert path.parent.name == "live_smoke_history"
    assert path.name.endswith("Z.json")
    assert path.name.count("T") == 1


def test_live_smoke_docs_and_make_targets_are_wired() -> None:
    makefile = read("Makefile")
    doc = read("docs/M1_LIVE_SMOKE_CHECK.md")
    runner = read("tools/run_m1_release_candidate.py")
    readiness = read("tools/check_m1_readiness.py")
    workflow = read(".github/workflows/live-smoke.yml")

    assert "m1-live-smoke-plan" in makefile
    assert "m1-live-smoke:" in makefile
    assert "live-testnet-smoke:" in makefile
    assert "tools/check_m1_live_smoke.py --run" in makefile
    assert "M1 live smoke dry-run plan" in runner
    assert "tests/test_m1_live_smoke_tool.py" in runner
    assert "check_m1_live_smoke_tool" in readiness
    assert "reports/live_smoke_history" in workflow
    assert "schedule:" in workflow

    for token in [
        "NetCoin M1 Live Smoke Check",
        "Host-header curl commands",
        "reports/live_smoke_history",
        "wallet HTML SRI",
        "python3 tools/check_m1_live_smoke.py --run",
        "docs/INCIDENT_RESPONSE.md",
        "does not claim seed deployment",
    ]:
        assert token in doc
