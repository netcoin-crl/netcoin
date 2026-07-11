#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.captcha_provider import load_captcha_config, source_validation, verify_token
from netcoin.mainnet_readiness import strict_evidence_gate

REQUIRED_EVIDENCE = [
    "NETCOIN_CAPTCHA_PROVIDER",
    "provider_secret",
    "siteverify_response_success",
    "invalid_token_rejected",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--token", default=os.environ.get("NETCOIN_CAPTCHA_TEST_TOKEN", ""))
    parser.add_argument("--invalid-token", default="netcoin-invalid-token")
    parser.add_argument("--evidence", default=os.environ.get("NETCOIN_CAPTCHA_EVIDENCE", ""))
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.strict:
        if args.evidence:
            result = strict_evidence_gate("captcha-provider-integration", args.evidence, REQUIRED_EVIDENCE).to_dict()
        else:
            cfg = load_captcha_config()
            issues = []
            if not cfg.configured:
                issues.append("NETCOIN_CAPTCHA_PROVIDER and NETCOIN_CAPTCHA_SECRET must be configured")
            valid = (
                verify_token(args.token, config=cfg)
                if cfg.configured and args.token
                else {"ok": False, "error": "no valid test token supplied"}
            )
            invalid = (
                verify_token(args.invalid_token, config=cfg)
                if cfg.configured
                else {"ok": False, "error": "provider not configured"}
            )
            if valid.get("ok") is not True:
                issues.append("valid provider token was not accepted")
            if invalid.get("ok") is not False:
                issues.append("invalid provider token was not rejected")
            result = {
                "gate_id": "captcha-provider-integration",
                "ok": not issues,
                "mode": "strict-provider",
                "provider": cfg.provider,
                "issues": issues,
                "valid_result": valid,
                "invalid_result": invalid,
            }
    else:
        result = source_validation()
        result["gate_id"] = "captcha-provider-integration"
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
