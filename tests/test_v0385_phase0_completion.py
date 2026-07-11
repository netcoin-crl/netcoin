from pathlib import Path

from netcoin.phase0_completion import load_phase0_completion, validate_phase0_completion

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_phase0_completion_spec_is_valid():
    report = validate_phase0_completion()
    assert report.ok, report.issues
    assert report.version == "0.38.5"
    assert report.completed_layer_count == 6
    assert report.quality_gate_count >= 10
    assert report.acceptance_criteria_count >= 12
    assert report.roadmap_phase_count >= 7
    assert report.complementary_feature_count >= 10


def test_phase0_completion_locks_product_model():
    spec = load_phase0_completion()
    locked = spec["locked_product_decisions"]
    assert locked["primary_navigation"] == ["Wallet", "Explorer", "Markets", "More"]
    assert locked["product_lenses"] == ["NetCoin", "NetCoin Network", "NetCoin Studio"]
    assert locked["user_jobs"] == ["Manage money", "Understand the blockchain", "Participate", "Operate infrastructure", "Build"]
    assert locked["status_vocabulary"] == ["Healthy", "Warning", "Offline", "Maintenance"]
    assert locked["trust_vocabulary"] == ["Fresh", "Stale", "Verified", "Unverified", "Risk"]
    assert "improve an existing workflow" in locked["anti_sprawl_rule"]
    assert "Do not create a new top-level surface" in locked["new_surface_rule"]


def test_phase0_completion_layers_reference_existing_artifacts():
    spec = load_phase0_completion()
    layers = {item["id"]: item for item in spec["completed_layers"]}
    expected = {
        "product-identity",
        "design-system",
        "workflow-architecture",
        "product-simplification",
        "trust-interaction",
        "product-coherence",
    }
    assert set(layers) == expected
    for layer in layers.values():
        assert (ROOT / layer["artifact"]).exists()
        assert layer["checker"].startswith("python tools/check_")
        assert layer["locked_decision"]


def test_phase0_completion_hands_off_to_proof_hardening():
    spec = load_phase0_completion()
    handoff = spec["phase1_handoff"]
    assert handoff["next_phase"] == "Phase 1 - Proof Hardening"
    evidence = set(handoff["required_evidence"])
    for item in [
        "full Python test-suite report",
        "cargo test --workspace report",
        "all Rust parity binary reports",
        "npm ci && npm run ci:api report",
        "real Playwright E2E report",
        "accessibility report",
        "release readiness scorecard",
    ]:
        assert item in evidence
    assert "production ready" in handoff["blocked_claims_until_complete"]
    assert "mainnet ready" in handoff["blocked_claims_until_complete"]


def test_phase0_completion_next_roadmap_stays_focused():
    spec = load_phase0_completion()
    roadmap = spec["approved_next_roadmap"]
    assert roadmap[0]["name"] == "Proof Hardening"
    names = [item["name"] for item in roadmap]
    assert "Wallet Professional UX" in names
    assert "Explorer and Indexer Trust" in names
    assert "Markets Risk and Settlement" in names
    assert "Exchange and Custody Safety" in names
    assert "NFTs" in roadmap[0]["must_not_add"]
    assert "bridges" in roadmap[0]["must_not_add"]


def test_phase0_completion_allows_only_complementary_features():
    spec = load_phase0_completion()
    allowed = set(spec["approved_complementary_features"])
    for feature in [
        "Release Readiness Scorecard",
        "Wallet Security Center",
        "Global command/search palette",
        "Unified notification center",
        "Guided testnet onboarding",
        "Local labels and notes",
        "Market order preview",
        "Custody risk dashboard",
        "E2E screenshot dashboard",
        "Audit bundle generator",
    ]:
        assert feature in allowed
    forbidden = set(spec["forbidden_until_after_audit_candidate"])
    for feature in ["NFTs", "cross-chain bridges", "multi-chain wallet", "mainnet launch marketing page"]:
        assert feature in forbidden


def test_phase0_completion_docs_checker_and_make_target_exist():
    assert (ROOT / "docs" / "PHASE_0_COMPLETION_HANDOFF.md").exists()
    assert (ROOT / "tools" / "check_phase0_complete.py").exists()
    doc = read("docs/PHASE_0_COMPLETION_HANDOFF.md")
    assert "Phase 0 is complete" in doc
    assert "make v0385-check" in doc
    makefile = read("Makefile")
    assert "phase0-complete-check" in makefile
    assert "v0385-check" in makefile


def test_phase0_completion_updates_release_metadata():
    # Phase 0 remains locked at v0.38.5, but later releases may bump
    # project metadata while preserving the Phase 0 completion artifact.
    assert 'version = "' in read("pyproject.toml")
    assert 'NODE_VERSION = "' in read("netcoin/params.py")
    assert "Current release: **v" in read("README.md")
    assert load_phase0_completion()["version"] == "0.38.5"
