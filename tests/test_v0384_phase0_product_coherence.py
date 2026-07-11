from pathlib import Path

from netcoin.product_coherence import load_product_coherence, validate_product_coherence

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_phase0_product_coherence_spec_is_valid():
    report = validate_product_coherence()
    assert report.ok, report.issues
    assert report.version == "0.38.5"
    assert report.lens_count == 3
    assert report.job_count == 5
    assert report.surface_count >= 10
    assert report.workflow_count >= 8
    assert report.no_dead_end_rule_count >= 8


def test_phase0_product_lenses_keep_public_product_focused():
    spec = load_product_coherence()
    lenses = {item["id"]: item for item in spec["product_lenses"]}
    assert set(lenses) == {"netcoin", "netcoin-network", "netcoin-studio"}
    assert lenses["netcoin"]["primary_surfaces"] == ["wallet", "explorer", "markets"]
    assert lenses["netcoin"]["default_mode"] == "user"
    assert "operator" not in lenses["netcoin"]["primary_surfaces"]
    assert "downloads" in lenses["netcoin-studio"]["primary_surfaces"]


def test_phase0_jobs_cover_all_product_work():
    spec = load_product_coherence()
    jobs = {item["id"]: item for item in spec["jobs"]}
    assert set(jobs) == {"manage-money", "understand-chain", "participate", "operate-infrastructure", "build"}
    assert jobs["manage-money"]["surfaces"] == ["wallet"]
    assert "search-chain" in jobs["understand-chain"]["primary_workflows"]
    assert "verify-release" in jobs["build"]["primary_workflows"]


def test_phase0_surface_ownership_prevents_dead_pages():
    spec = load_product_coherence()
    ownership = {item["surface"]: item for item in spec["surface_ownership"]}
    for surface in ["wallet", "explorer", "markets", "faucet", "exchange", "operator", "docs", "api", "downloads"]:
        item = ownership[surface]
        assert item["primary_action"]
        assert item["trust_signal"]
        assert item["next_step"]
        assert item["advanced_destination"]
    assert ownership["wallet"]["job"] == "manage-money"
    assert ownership["markets"]["primary_action"] == "Preview order"
    assert ownership["operator"]["lens"] == "netcoin-network"


def test_phase0_workflow_evidence_has_success_and_failure_paths():
    spec = load_product_coherence()
    workflows = {item["workflow"]: item for item in spec["workflow_evidence"]}
    for workflow in [
        "receive-net",
        "send-net",
        "search-chain",
        "trade-market",
        "claim-faucet-net",
        "withdraw-custody-funds",
        "handle-operator-incident",
        "verify-release",
    ]:
        item = workflows[workflow]
        assert item["must_not_dead_end"] is True
        assert len(item["success_reassurance"].split()) >= 4
        assert len(item["failure_recovery"].split()) >= 4
    assert workflows["send-net"]["failure_recovery"].startswith("Nothing was broadcast")
    assert "Do not install" in workflows["verify-release"]["failure_recovery"]


def test_phase0_page_exit_contract_forbids_vague_exits():
    spec = load_product_coherence()
    contract = spec["page_exit_contract"]
    assert set(contract["forbidden_exit_labels"]) >= {"Done", "Back", "Close", "Submit"}
    assert contract["minimum_reassurance_words"] >= 4
    required = set(contract["required_fields"])
    for field in ["surface", "lens", "job", "primary_action", "trust_signal", "next_step", "advanced_destination"]:
        assert field in required


def test_phase0_product_coherence_docs_checker_and_css_exist():
    assert (ROOT / "docs" / "PHASE_0_PRODUCT_COHERENCE.md").exists()
    assert (ROOT / "tools" / "check_product_coherence.py").exists()
    doc = read("docs/PHASE_0_PRODUCT_COHERENCE.md")
    assert "Phase 0.5" in doc
    assert "python tools/check_product_coherence.py" in doc
    css = read("sites/shared/design-system.css")
    for token in [".nc-lens-shell", ".nc-owner-job", ".nc-primary-action-row", ".nc-next-step", ".nc-no-dead-end"]:
        assert token in css
