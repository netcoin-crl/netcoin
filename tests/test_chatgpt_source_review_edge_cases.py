from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from netcoin.addrv2 import AddrV2Error, AddrV2Record, network_id_for_host, normalize_host
from netcoin.bandwidth import relay_plan
from netcoin.genesis_manifest import validate_genesis_manifest
from netcoin.hardware_wallet import stable_hash, validate_hardware_transcript
from netcoin.offline_signing import OfflineSigningError, import_signed_psbt
from netcoin.pex import PEXPolicy, select_pex_records
from netcoin.psbt import PartiallySignedTransaction
from netcoin.tx import SpendableOutput, TxOutput
from netcoin.versionbits import DEFINED, FAILED, LOCKED_IN, STARTED, VersionBitsDeployment, evaluate_period

ROOT = Path(__file__).resolve().parents[1]


def _psbt_text(*, signed: bool = False, output_amount: int = 900) -> str:
    prevout = SpendableOutput(
        txid="a" * 64,
        vout=0,
        output=TxOutput(amount=1000, script_pubkey="OP_TRUE"),
        height=1,
    )
    psbt = PartiallySignedTransaction.create([prevout], [TxOutput(amount=output_amount, script_pubkey="OP_TRUE")])
    if signed:
        psbt.tx.inputs[0].signature = "deadbeef"
    return "netpsbt:" + psbt.to_base64()


def test_versionbits_threshold_boundaries_require_complete_periods():
    deployment = VersionBitsDeployment(
        name="demo", bit=3, start_height=100, timeout_height=1000, period=10, threshold=8
    )
    assert (
        evaluate_period(deployment, period_start_height=100, previous_state=DEFINED, block_versions=[])["state"]
        == STARTED
    )

    just_below = [1 << 3 for _ in range(7)] + [0, 0, 0]
    at_threshold = [1 << 3 for _ in range(8)] + [0, 0]
    above_threshold = [1 << 3 for _ in range(9)] + [0]
    assert (
        evaluate_period(deployment, period_start_height=110, previous_state=STARTED, block_versions=just_below)["state"]
        == STARTED
    )
    assert (
        evaluate_period(deployment, period_start_height=120, previous_state=STARTED, block_versions=at_threshold)[
            "state"
        ]
        == LOCKED_IN
    )
    assert (
        evaluate_period(deployment, period_start_height=130, previous_state=STARTED, block_versions=above_threshold)[
            "state"
        ]
        == LOCKED_IN
    )

    partial = evaluate_period(
        deployment, period_start_height=140, previous_state=STARTED, block_versions=at_threshold[:8]
    )
    assert partial["state"] == FAILED
    assert any("complete signaling period" in issue for issue in partial["issues"])

    invalid = evaluate_period(deployment, period_start_height=150, previous_state="maybe", block_versions=[-1] * 10)
    assert invalid["state"] == FAILED
    assert any("unknown previous_state" in issue for issue in invalid["issues"])
    assert any("non-negative" in issue for issue in invalid["issues"])


def test_genesis_manifest_rejects_malformed_and_unapproved_approved_manifests():
    base = json.loads((ROOT / "config/genesis_manifest.example.json").read_text())
    missing_bucket = {**base, "allocations": [item for item in base["allocations"] if item["category"] != "community"]}
    missing_result = validate_genesis_manifest(missing_bucket)
    assert missing_result["ok"] is False
    assert any("missing required categories" in issue for issue in missing_result["issues"])

    bad_sum = {
        **base,
        "allocations": [{**item, "basis_points": item["basis_points"] + 1} for item in base["allocations"]],
    }
    assert validate_genesis_manifest(bad_sum)["ok"] is False

    malformed_bps = {**base, "allocations": [{**base["allocations"][0], "basis_points": "ten"}]}
    malformed_result = validate_genesis_manifest(malformed_bps)
    assert malformed_result["ok"] is False
    assert any("basis_points must be an integer" in issue for issue in malformed_result["issues"])

    approved_without_final_governance = {**base, "status": "approved"}
    approved_result = validate_genesis_manifest(approved_without_final_governance)
    assert approved_result["ok"] is False
    assert any("approved genesis manifest requires final governance" in issue for issue in approved_result["issues"])


def test_addrv2_rejects_malformed_hosts_and_classifies_safe_hosts():
    assert normalize_host("[2001:db8::1]") == "2001:db8::1"
    assert network_id_for_host("seed.netcoin.online") == "dns"
    torv3 = "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcd.onion"
    assert len(torv3.removesuffix(".onion")) == 56
    assert network_id_for_host(torv3) == "torv3"

    bad_hosts = [
        "",
        "[2001:db8::1",
        "2001:db8::1]",
        "bad host.example",
        "bad/example",
        ".example.com",
        "example..com",
        "short.onion",
        "a" * 254,
    ]
    for host in bad_hosts:
        with pytest.raises(AddrV2Error):
            AddrV2Record(host=host)


def test_pex_empty_and_cap_boundaries_are_enforced():
    peers = [
        {"host": f"198.51.100.{i}", "port": 28444, "score": 10 - i, "services": ["NETCOIN_PEX"]} for i in range(1, 6)
    ]
    assert select_pex_records([], policy=PEXPolicy(max_records=10)) == []
    assert select_pex_records(peers, policy=PEXPolicy(max_records=0)) == []
    assert len(select_pex_records(peers, policy=PEXPolicy(max_records=3, max_per_diversity_group=10))) == 3
    assert len(select_pex_records(peers, policy=PEXPolicy(max_records=5, max_per_diversity_group=10))) == 5
    assert len(select_pex_records(peers, policy=PEXPolicy(max_records=6, max_per_diversity_group=10))) == 5


def test_bandwidth_relay_plan_clamps_negative_inventory():
    plan = relay_plan("home", peer_count=-5, pending_inventory=-100)
    assert plan["selected_outbound_peers"] == 0
    assert plan["inventory_to_relay"] == 0
    assert plan["under_500kbps_home_target"] is True


def test_offline_signing_rejects_malformed_and_mismatched_psbts():
    unsigned = _psbt_text(signed=False, output_amount=900)
    signed = _psbt_text(signed=True, output_amount=800)
    with pytest.raises(OfflineSigningError, match="does not match"):
        import_signed_psbt(unsigned, signed)
    with pytest.raises(Exception):
        import_signed_psbt("netpsbt:not-base64", signed)


def test_hardware_transcript_rejects_wrong_schema_and_bad_psbt():
    body = {
        "schema": "wrong-schema",
        "device_family": "ledger",
        "device_model": "Ledger Nano S Plus",
        "firmware_version": "test-firmware",
        "transport": "webhid",
        "network": "testnet",
        "derivation_path": "m/84'/0'/0'/0/0",
        "psbt_sha256": "a" * 64,
        "challenge": "b" * 64,
        "address_reviewed_on_device": True,
        "tx_reviewed_on_device": True,
        "fee_reviewed_on_device": True,
        "change_reviewed_on_device": True,
        "signed_psbt": "netpsbt:not-base64",
        "operator_attestation": "test transcript",
    }
    body["evidence_hash"] = stable_hash(body)
    issues = validate_hardware_transcript(body)
    assert any("schema must be" in issue for issue in issues)
    assert any("decode as a NetCoin PSBT" in issue for issue in issues)


def test_sbom_is_cyclonedx_and_slsa_provenance_has_core_fields():
    sbom_rel = "dist/netcoin-sbom-edge.json"
    provenance_rel = "dist/netcoin-slsa-provenance-edge.json"
    sbom_path = ROOT / sbom_rel
    provenance_path = ROOT / provenance_rel
    subprocess.run([sys.executable, "tools/generate_sbom.py", "--out", sbom_rel], cwd=ROOT, check=True)
    sbom = json.loads(sbom_path.read_text())
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert sbom["components"]
    first_component = sbom["components"][0]
    assert first_component["type"] == "file"
    assert first_component["hashes"][0]["alg"] == "SHA-256"

    subprocess.run(
        [
            sys.executable,
            "tools/generate_slsa_provenance.py",
            "--subject",
            sbom_rel,
            "--out",
            provenance_rel,
        ],
        cwd=ROOT,
        check=True,
    )
    provenance = json.loads(provenance_path.read_text())
    assert provenance["_type"] == "https://in-toto.io/Statement/v1"
    assert provenance["predicateType"] == "https://slsa.dev/provenance/v1"
    assert provenance["subject"][0]["digest"]["sha256"]
    assert provenance["predicate"]["runDetails"]["builder"]["id"]


def test_reproducible_build_tool_reports_two_identical_digests(tmp_path):
    out_rel = "reports/reproducible_build_edge_report.json"
    subprocess.run([sys.executable, "tools/verify_reproducible_build.py", "--out", out_rel], cwd=ROOT, check=True)
    report = json.loads((ROOT / out_rel).read_text())
    assert report["ok"] is True
    assert report["sha256"] == report["second_sha256"]
    assert report["independent_builder_required_for_strict_m2"] is True
