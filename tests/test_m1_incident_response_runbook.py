from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_m1_incident_response_runbook_has_operator_communication_and_recovery_markers() -> None:
    text = read("docs/INCIDENT_RESPONSE.md")
    required_tokens = [
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
    ]
    missing = [token for token in required_tokens if token not in text]
    assert not missing


def test_status_page_surfaces_incident_response_runbook() -> None:
    html = read("sites/status/index.html")
    css = read("sites/status/status.css")
    assert "incidentResponseTitle" in html
    assert "M1 operator runbook" in html
    assert "https://docs.netcoin.online/INCIDENT_RESPONSE.md" in html
    assert "severity levels, owner/scribe assignment" in html
    assert "m1-incident-runbook" in html
    assert ".incident-card" in css
