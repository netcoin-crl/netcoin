import os
from pathlib import Path

from tools.deployment_qa import run_qa


def test_deployment_qa_flow_passes(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("NETCOIN_APP_STORAGE", raising=False)
    monkeypatch.delenv("NETCOIN_APP_REQUIRE_ADMIN", raising=False)
    monkeypatch.delenv("NETCOIN_APP_ADMIN_TOKEN", raising=False)
    report = run_qa(tmp_path)
    payload = report.to_dict()
    assert payload["ok"] is True
    assert payload["count"] >= 20
    assert any(item["name"].startswith("20.") for item in payload["checks"])
    assert os.environ.get("NETCOIN_APP_REQUIRE_ADMIN") is None
