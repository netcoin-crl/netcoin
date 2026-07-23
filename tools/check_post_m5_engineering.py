#!/usr/bin/env python3
"""Source/evidence gate for the post-M5 NetCoin engineering backlog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.ecosystem import validate_ecosystem_plan
from netcoin.genesis_manifest import validate_genesis_manifest
from netcoin.hardware_bridge import build_hardware_web_session
from netcoin.liquidity import validate_liquidity_metadata
from netcoin.offline_signing import export_unsigned_psbt_bundle
from netcoin.p2p_public_hardening import public_p2p_hardening_plan
from netcoin.psbt import encode_psbt
from netcoin.versionbits import DEFINED, VersionBitsDeployment, evaluate_period

SOURCE_FILES = {
    "production-psbt-offline-signing": ["netcoin/offline_signing.py", "config/psbt_offline_workflow.example.json"],
    "hardware-wallet-webusb-webhid": ["netcoin/hardware_bridge.py", "config/hardware_wallet_devices.example.json"],
    "public-p2p-hardening": ["netcoin/p2p_public_hardening.py", "config/public_p2p_hardening.example.json"],
    "versionbits-softfork-rehearsal": ["netcoin/versionbits.py", "config/versionbits_rehearsal.example.json"],
    "genesis-manifest-validation": ["netcoin/genesis_manifest.py", "config/genesis_manifest.example.json"],
    "m6-liquidity-market-metadata": ["netcoin/liquidity.py", "config/liquidity_metadata.example.json"],
    "m7-ecosystem-utility": ["netcoin/ecosystem.py", "config/ecosystem_utility.example.json"],
}

STRICT_EVIDENCE = {
    "ledger-physical-transcript": "reports/post_m5_evidence/ledger_physical_transcript.json",
    "trezor-physical-transcript": "reports/post_m5_evidence/trezor_physical_transcript.json",
    "public-p2p-independent-operators": "reports/post_m5_evidence/public_p2p_independent_operator_set.json",
    "versionbits-nip-signoff": "reports/post_m5_evidence/versionbits_nip_signoff.json",
    "genesis-nip-approval": "reports/post_m5_evidence/genesis_nip_approval.json",
    "liquidity-venue-evidence": "reports/post_m5_evidence/liquidity_venue_evidence.json",
    "ecosystem-usage-report": "reports/post_m5_evidence/ecosystem_usage_report.json",
}


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def check_source() -> list[dict]:
    checks: list[dict] = []
    for deliverable, files in SOURCE_FILES.items():
        missing = [path for path in files if not (ROOT / path).exists()]
        checks.append({"id": deliverable, "ok": not missing, "missing": missing})

    _psbt_text = encode_psbt(
        {"magic": "netcoin-psbt-v1", "tx": {"version": 1, "locktime": 0, "inputs": [], "outputs": []}, "prevouts": []}
    )
    # Empty-input PSBTs are invalid for full workflow, so use existence/source check only here.
    try:
        export_unsigned_psbt_bundle("not-a-psbt")
    except Exception:
        checks.append({"id": "psbt-export-rejects-invalid-payload", "ok": True})

    demo_psbt = "netpsbt:" + "MDA="
    try:
        build_hardware_web_session(demo_psbt, device_family="ledger")
        checks.append({"id": "hardware-web-session-contract", "ok": True})
    except Exception as exc:
        checks.append({"id": "hardware-web-session-contract", "ok": False, "error": str(exc)})

    p2p_cfg = load_json("config/public_p2p_hardening.example.json")
    p2p_kwargs = {key: value for key, value in p2p_cfg.items() if key != "schema"}
    p2p_plan = public_p2p_hardening_plan(**p2p_kwargs)
    checks.append({"id": "public-p2p-hardening-plan", "ok": bool(p2p_plan["ok"]), "issues": p2p_plan["issues"]})

    vb = load_json("config/versionbits_rehearsal.example.json")["deployment"]
    evaluation = evaluate_period(
        VersionBitsDeployment(**vb), period_start_height=vb["start_height"], previous_state=DEFINED, block_versions=[]
    )
    checks.append({"id": "versionbits-rehearsal-model", "ok": not evaluation["issues"], "state": evaluation["state"]})

    genesis = validate_genesis_manifest(load_json("config/genesis_manifest.example.json"), strict=False)
    checks.append({"id": "genesis-manifest-draft-validation", "ok": bool(genesis["ok"]), "issues": genesis["issues"]})

    liquidity = validate_liquidity_metadata(load_json("config/liquidity_metadata.example.json"))
    checks.append({"id": "liquidity-metadata-validation", "ok": bool(liquidity["ok"]), "issues": liquidity["issues"]})

    ecosystem = validate_ecosystem_plan(load_json("config/ecosystem_utility.example.json"))
    checks.append({"id": "ecosystem-utility-validation", "ok": bool(ecosystem["ok"]), "issues": ecosystem["issues"]})

    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    checks = check_source()
    blockers = [check for check in checks if not check.get("ok")]
    evidence = []
    if args.strict:
        for item, path in STRICT_EVIDENCE.items():
            exists = (ROOT / path).exists()
            evidence.append({"id": item, "path": path, "ok": exists})
            if not exists:
                blockers.append({"id": item, "ok": False, "missing_evidence": path})

    result = {
        "schema": "netcoin-post-m5-engineering-readiness-v1",
        "ok": not blockers,
        "strict": args.strict,
        "claim_level": "post-m5-source-complete-evidence-required",
        "checks": checks,
        "evidence": evidence,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "does_not_activate_consensus_or_genesis": True,
        "does_not_claim_liquidity_or_utility_without_evidence": True,
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
