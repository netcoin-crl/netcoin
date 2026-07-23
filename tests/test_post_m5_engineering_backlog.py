import json
import subprocess
import sys
from pathlib import Path

from netcoin.chain import Blockchain
from netcoin.ecosystem import validate_ecosystem_plan
from netcoin.genesis_manifest import validate_genesis_manifest
from netcoin.hardware_bridge import browser_transport_policy, build_hardware_web_session
from netcoin.liquidity import coingecko_asset_metadata, validate_liquidity_metadata
from netcoin.offline_signing import (
    OfflineSigningTranscript,
    build_broadcast_package,
    export_unsigned_psbt_bundle,
    import_signed_psbt,
    validate_offline_signing_transcript,
)
from netcoin.p2p_public_hardening import public_p2p_hardening_plan
from netcoin.psbt import PartiallySignedTransaction
from netcoin.tx import TxOutput, amount_to_sats
from netcoin.versionbits import DEFINED, LOCKED_IN, STARTED, VersionBitsDeployment, evaluate_period
from netcoin.wallet import Wallet

ROOT = Path(__file__).resolve().parents[1]


def funded_chain(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    wallet = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(wallet.address)
    return chain, wallet, receiver


def test_production_psbt_offline_signing_round_trip(tmp_path: Path):
    chain, wallet, receiver = funded_chain(tmp_path)
    spendable = next(iter(chain.utxo_set().values()))
    output = TxOutput(amount=amount_to_sats("1"), address=receiver.address)
    psbt = PartiallySignedTransaction.create([spendable], [output])
    unsigned = "netpsbt:" + psbt.to_base64()

    bundle = export_unsigned_psbt_bundle(unsigned, network="testnet", created_at=1)
    assert bundle["private_key_material_included"] is False
    assert bundle["summary"]["input_count"] == 1
    assert bundle["summary"]["output_count"] == 1

    signed_psbt = psbt.sign(wallet)
    signed = "netpsbt:" + signed_psbt.to_base64()
    imported = import_signed_psbt(unsigned, signed)
    assert imported["ready_to_broadcast"] is True
    assert imported["txid"]

    broadcast = build_broadcast_package(signed)
    assert broadcast["endpoint"] == "/api/tx/broadcast"
    assert broadcast["submit_automatically"] is False

    transcript = OfflineSigningTranscript(
        unsigned_bundle_hash=bundle["bundle_hash"],
        signed_psbt_sha256=imported["signed_psbt_sha256"],
        txid=imported["txid"],
        signer_type="software-offline",
        operator_attestation="test transcript",
        created_at=1,
    ).to_dict()
    assert validate_offline_signing_transcript(transcript) == []


def test_hardware_wallet_webusb_webhid_session_contract():
    psbt_text = "netpsbt:" + "MDA="
    ledger = build_hardware_web_session(psbt_text, device_family="Ledger Nano S Plus")
    trezor = build_hardware_web_session(psbt_text, device_family="Trezor Model T")
    assert ledger["schema"] == "netcoin-hardware-web-session-v1"
    assert ledger["transport_policy"]["preferred_transport"] == "webhid"
    assert trezor["transport_policy"]["preferred_transport"] == "webusb"
    assert ledger["private_key_material_included"] is False
    assert browser_transport_policy("ledger")["hid_filters"]


def test_public_p2p_hardening_plan_accepts_diverse_seed_and_operator_contracts():
    cfg = json.loads((ROOT / "config/public_p2p_hardening.example.json").read_text())
    plan = public_p2p_hardening_plan(**{key: value for key, value in cfg.items() if key != "schema"})
    assert plan["ok"] is True
    assert plan["compact_blocks_enabled"] is True
    assert plan["pex_enabled"] is True
    assert plan["addrv2_enabled"] is True
    assert plan["home_bandwidth_kbps"] <= 500


def test_versionbits_rehearsal_locks_in_without_consensus_integration():
    deployment = VersionBitsDeployment(
        name="test", bit=2, start_height=100, timeout_height=1000, period=10, threshold=8
    )
    started = evaluate_period(deployment, period_start_height=100, previous_state=DEFINED, block_versions=[])
    assert started["state"] == STARTED
    versions = [1 << 2 for _ in range(8)] + [0, 0]
    locked = evaluate_period(deployment, period_start_height=110, previous_state=STARTED, block_versions=versions)
    assert locked["state"] == LOCKED_IN
    assert locked["consensus_integrated"] is False
    assert locked["requires_nip_before_activation"] is True


def test_genesis_manifest_draft_validates_but_strict_requires_governance():
    manifest = json.loads((ROOT / "config/genesis_manifest.example.json").read_text())
    source = validate_genesis_manifest(manifest, strict=False)
    strict = validate_genesis_manifest(manifest, strict=True)
    assert source["ok"] is True
    assert source["does_not_generate_or_mine_genesis"] is True
    assert strict["ok"] is False
    assert any("governance" in issue or "status" in issue for issue in strict["issues"])


def test_m6_liquidity_metadata_and_coingecko_projection():
    metadata = json.loads((ROOT / "config/liquidity_metadata.example.json").read_text())
    validation = validate_liquidity_metadata(metadata)
    assert validation["ok"] is True
    gecko = coingecko_asset_metadata(metadata)
    assert gecko["symbol"] == "NET"
    assert gecko["public_notice"].startswith("NetCoin market data is draft-only")


def test_m7_ecosystem_utility_plan():
    plan = json.loads((ROOT / "config/ecosystem_utility.example.json").read_text())
    validation = validate_ecosystem_plan(plan)
    assert validation["ok"] is True
    assert validation["utility_focus"] == "dev-first-bitcoin-family-sandbox"


def test_post_m5_source_gate_and_runner_pass():
    for command in (
        [
            sys.executable,
            "tools/check_post_m5_engineering.py",
            "--out",
            "reports/post_m5_engineering_source_report.json",
        ],
        [
            sys.executable,
            "tools/run_post_m5_release_candidate.py",
            "--profile",
            "source",
            "--timeout",
            "120",
            "--out",
            "reports/post_m5_release_candidate_report.json",
        ],
    ):
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        assert proc.returncode == 0, proc.stdout + proc.stderr


def test_post_m5_strict_gate_requires_real_evidence():
    proc = subprocess.run(
        [
            sys.executable,
            "tools/check_post_m5_engineering.py",
            "--strict",
            "--out",
            "reports/post_m5_engineering_strict_report.json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 1
    report = json.loads((ROOT / "reports/post_m5_engineering_strict_report.json").read_text())
    assert report["ok"] is False
    assert report["blocker_count"] >= 7
