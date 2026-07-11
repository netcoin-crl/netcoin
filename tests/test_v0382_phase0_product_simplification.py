from pathlib import Path

from netcoin.product_simplification import (
    load_product_simplification,
    validate_product_simplification,
)

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_phase0_product_simplification_spec_is_valid():
    report = validate_product_simplification()
    assert report.ok, report.issues
    assert report.version == "0.38.5"
    assert report.mode_count == 4
    assert report.disclosure_level_count == 5
    assert report.complementary_feature_count >= 10
    assert report.workflow_rule_count >= 6


def test_phase0_simplification_keeps_primary_nav_small_and_mode_aware():
    spec = load_product_simplification()
    assert spec["visibility_model"]["primary_nav"] == ["Wallet", "Explorer", "Markets"]
    user = spec["visibility_model"]["mode_defaults"]["user"]
    assert "wallet" in user["show"]
    assert "operator" in user["hide_until_needed"]
    assert "exchange" in user["hide_until_needed"]
    operator = spec["visibility_model"]["mode_defaults"]["operator"]
    assert "operator" in operator["show"]
    assert "exchange" in operator["show"]


def test_phase0_progressive_disclosure_and_new_page_gate_are_strict():
    spec = load_product_simplification()
    levels = spec["progressive_disclosure_levels"]
    assert "balance" in levels["beginner"]["show"]
    assert "coin control" in levels["advanced"]["show"]
    assert "health center" in levels["operator"]["show"]
    gate = spec["new_page_gate"]
    assert gate["maximum_primary_actions"] == 1
    assert gate["must_reference_existing_component"] is True
    assert gate["must_define_progressive_disclosure_level"] is True
    for field in [
        "owner_job",
        "primary_action",
        "workflow",
        "target_mode",
        "panel_rejected_reason",
        "trust_signal",
        "empty_state",
        "loading_state",
        "error_state",
    ]:
        assert field in gate["required_fields"]


def test_phase0_approved_features_are_complementary_not_sprawl():
    spec = load_product_simplification()
    approved = {item["id"] for item in spec["approved_complementary_features"]}
    assert "release-readiness-scorecard" in approved
    assert "wallet-security-center" in approved
    assert "market-order-preview" in approved
    assert "custody-risk-dashboard" in approved
    avoided = set(spec["avoid_until_after_audit_candidate"])
    assert "cross-chain-bridges" in avoided
    assert "multi-chain-wallet" in avoided
    assert "more-market-types" in avoided


def test_phase0_3_documentation_and_checker_exist():
    assert (ROOT / "docs" / "PHASE_0_PRODUCT_SIMPLIFICATION.md").exists()
    assert (ROOT / "tools" / "check_product_simplification.py").exists()
    doc = read("docs/PHASE_0_PRODUCT_SIMPLIFICATION.md")
    assert "Phase 0.3" in doc
    assert "Progressive disclosure" in doc
    assert "python tools/check_product_simplification.py" in doc
