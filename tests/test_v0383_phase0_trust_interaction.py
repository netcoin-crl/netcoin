from pathlib import Path

from netcoin.trust_interaction import load_trust_interaction, validate_trust_interaction

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_phase0_trust_interaction_spec_is_valid():
    report = validate_trust_interaction()
    assert report.ok, report.issues
    assert report.version == "0.38.5"
    assert report.trust_state_count == 5
    assert report.surface_count >= 7
    assert report.workflow_count >= 7
    assert report.error_template_count >= 5
    assert report.confirmation_template_count >= 5


def test_phase0_trust_contract_requires_reassurance_and_review():
    spec = load_trust_interaction()
    assert set(spec["canonical_status_terms"]) == {"Healthy", "Warning", "Offline", "Maintenance"}
    assert spec["action_lifecycle"] == [
        "start",
        "input",
        "review",
        "confirm",
        "execute",
        "success",
        "verify",
        "recover",
    ]
    assert any("irreversible action requires a review" in rule for rule in spec["interaction_rules"])
    send = next(item for item in spec["workflow_reassurance_rules"] if item["workflow"] == "send-net")
    assert send["review_required"] is True
    assert "Nothing was broadcast" in send["failure_reassurance"]


def test_phase0_surface_trust_requirements_cover_major_surfaces():
    spec = load_trust_interaction()
    surfaces = {item["surface"]: item for item in spec["surface_trust_requirements"]}
    for required in {"wallet", "explorer", "markets", "faucet", "exchange", "operator", "download"}:
        assert required in surfaces
        assert len(surfaces[required]["must_show"]) >= 3
        assert len(surfaces[required]["reassurance_examples"]) >= 2
    assert "wallet lock state" in surfaces["wallet"]["must_show"]
    assert "active chain" in surfaces["explorer"]["must_show"]
    assert "max loss" in surfaces["markets"]["must_show"]


def test_phase0_error_and_confirmation_templates_are_specific():
    spec = load_trust_interaction()
    send_error = spec["error_templates"]["send_validation_failed"]
    assert send_error["reassurance"] == "Nothing was broadcast."
    assert send_error["primary_recovery"] == "Review transaction"
    release_error = spec["error_templates"]["release_verification_failed"]
    assert "Do not install" in release_error["reassurance"]
    wallet_success = spec["confirmation_templates"]["wallet_send_success"]
    assert wallet_success["title"] == "Transaction sent."
    assert wallet_success["next_action"] == "View in Explorer"


def test_phase0_trust_docs_checker_and_css_exist():
    assert (ROOT / "docs" / "PHASE_0_TRUST_INTERACTION_STANDARDS.md").exists()
    assert (ROOT / "tools" / "check_trust_interaction.py").exists()
    doc = read("docs/PHASE_0_TRUST_INTERACTION_STANDARDS.md")
    assert "Phase 0.4" in doc
    assert "python tools/check_trust_interaction.py" in doc
    css = read("sites/shared/design-system.css")
    for token in [".nc-trust-bar", ".nc-trust-chip", ".nc-review-panel", ".nc-reassurance", ".nc-error-state"]:
        assert token in css
