from pathlib import Path

from netcoin.design_system import (
    load_design_system,
    load_product_workflows,
    validate_design_system,
)

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_phase0_design_system_spec_is_valid():
    report = validate_design_system()
    assert report.ok, report.issues
    assert report.version == "0.38.5"
    assert report.workflow_count >= 10
    assert report.component_count >= 20
    assert report.css_tokens_present >= 10


def test_design_system_has_canonical_tokens_and_status_language():
    design = load_design_system()
    assert design["tokens"]["spacing_px"] == [4, 8, 12, 16, 24, 32, 48]
    assert set(design["status_vocabulary"].keys()) == {"Healthy", "Warning", "Offline", "Maintenance"}
    assert set(design["components"]["buttons"]) == {"primary", "secondary", "danger", "ghost"}
    assert "Irreversible actions require review" in "\n".join(design["interaction_rules"])
    assert "Status color is never the only indicator." in design["accessibility_baseline"]


def test_workflow_architecture_covers_primary_product_paths():
    workflows = load_product_workflows()["workflows"]
    workflow_ids = {workflow["id"] for workflow in workflows}
    for required in {
        "receive-net",
        "send-net",
        "search-chain",
        "claim-faucet-net",
        "trade-market",
        "withdraw-custody-funds",
        "handle-operator-incident",
        "build-integration",
        "verify-release",
        "prepare-audit",
    }:
        assert required in workflow_ids
    send = next(workflow for workflow in workflows if workflow["id"] == "send-net")
    assert send["primary_action"] == "Review transaction"
    assert "known contact chip" in send["trust_signals"]
    assert "coin control" in send["advanced_hidden_until_needed"]


def test_shared_design_system_css_exposes_foundation_classes():
    css = read("sites/shared/design-system.css")
    for token in [
        "--nc-bg",
        "--nc-primary",
        "--nc-space-1",
        "--nc-type-page",
        ".nc-card",
        ".nc-btn-primary",
        ".nc-status-healthy",
        ".nc-advanced",
    ]:
        assert token in css


def test_phase0_2_documentation_and_checker_exist():
    assert (ROOT / "docs" / "PHASE_0_DESIGN_SYSTEM_WORKFLOW_ARCHITECTURE.md").exists()
    assert (ROOT / "tools" / "check_design_system.py").exists()
    doc = read("docs/PHASE_0_DESIGN_SYSTEM_WORKFLOW_ARCHITECTURE.md")
    assert "Phase 0.2" in doc
    assert "Canonical workflows" in doc
    assert "python tools/check_design_system.py" in doc
