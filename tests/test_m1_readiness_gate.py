from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_m1_readiness_gate_reports_all_current_m1_tracks() -> None:
    from tools.check_m1_readiness import run_checks

    result = run_checks()
    assert result["ok"], result["incomplete"]
    assert set(result["checks"]) == {
        "json_ignore",
        "wallet_polish_and_sri",
        "wallet_e2e_wiring",
        "status_page_snapshot",
        "faucet_hardening",
        "explorer_mempool_fee_bands",
        "ci_m1_source_gate",
        "incident_response_runbook",
        "testnet_user_journey",
        "testnet_feedback_intake",
        "testnet_pilot_plan",
        "m1_live_smoke_tool",
    }
    for check in result["checks"].values():
        assert check["ok"], check.get("issues")
    assert "real CAPTCHA credentials" in result["does_not_claim"]
    assert "live seed deployment" in result["does_not_claim"]


def test_m1_readiness_gate_can_write_json_report(tmp_path: Path) -> None:
    out = tmp_path / "m1-readiness.json"
    proc = subprocess.run(
        [sys.executable, "tools/check_m1_readiness.py", "--out", str(out)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["scope"] == "M1 offline source readiness"
    assert payload["incomplete"] == []
