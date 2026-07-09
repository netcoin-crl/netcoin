import json
import subprocess
import sys
from pathlib import Path

from netcoin.security_hardening import security_audit_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_v037_security_manifest_passes():
    result = security_audit_manifest()
    assert result["ok"] is True
    assert result["fuzz_target_count"] >= 4
    assert result["audit_gate_count"] >= 6
    assert result["threat_model_count"] >= 5


def test_v037_security_tool_passes():
    proc = subprocess.run(
        [sys.executable, "tools/run_security_audit_prep.py"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    result = json.loads(proc.stdout)
    assert result["ok"] is True
