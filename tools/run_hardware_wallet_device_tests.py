#!/usr/bin/env python3
"""Validate hardware-wallet test evidence.

Source mode confirms that the project ships a real evidence schema and strict
validator. Strict mode validates an operator-supplied transcript from a physical
device. It does not pretend that a physical Ledger/Trezor/Coldcard exists in a
sandbox.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.mainnet_readiness import source_gate, strict_evidence_gate

REQUIRED = [
    "device_model",
    "firmware_version",
    "transport",
    "address_reviewed_on_device",
    "tx_reviewed_on_device",
    "challenge_signature_verified",
    "operator_attestation",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--evidence", default=os.environ.get("NETCOIN_HARDWARE_WALLET_EVIDENCE", ""))
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.strict:
        if not args.evidence:
            result = strict_evidence_gate("hardware-wallet-device-testing", "reports/mainnet_evidence/hardware_wallet_device_evidence.json", REQUIRED).to_dict()
        else:
            result = strict_evidence_gate("hardware-wallet-device-testing", args.evidence, REQUIRED).to_dict()
    else:
        result = source_gate(
            "hardware-wallet-device-testing",
            {
                "schema": REQUIRED,
                "supported_transports": ["usb-hid", "webhid", "qr-airgap", "file-psbt"],
                "strict_note": "requires a physical device transcript; source mode is not production proof",
            },
        ).to_dict()
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
