#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.hostile_p2p_soak import run_hostile_p2p_soak
from netcoin.mainnet_readiness import strict_evidence_gate

REQUIRED_EVIDENCE = [
    "seed_nodes",
    "duration_hours",
    "peer_count_minimum",
    "reorgs_observed",
    "uptime_percent",
    "incident_links",
]


def _probe_seed(seed: str, timeout: float) -> dict[str, object]:
    host, _sep, port_text = seed.partition(":")
    port = int(port_text or "28444")
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ok = True
            error = ""
    except Exception as exc:
        ok = False
        error = str(exc)
    return {"seed": seed, "ok": ok, "seconds": round(time.monotonic() - started, 3), "error": error}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--seeds", nargs="*", default=[])
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--evidence", default="reports/mainnet_evidence/public_p2p_soak_evidence.json")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.strict and not args.seeds:
        result = strict_evidence_gate("public-production-p2p-soak", ROOT / args.evidence, REQUIRED_EVIDENCE).to_dict()
    elif args.strict:
        probes = [_probe_seed(seed, args.timeout) for seed in args.seeds]
        ok_count = len([p for p in probes if p["ok"]])
        result = {
            "gate_id": "public-production-p2p-soak",
            "ok": ok_count == len(probes) and ok_count > 0,
            "mode": "strict-seed-probe",
            "seed_count": len(probes),
            "ok_seed_count": ok_count,
            "probes": probes,
            "note": "connectivity probe is necessary but does not replace long-duration soak evidence",
        }
    else:
        smoke = run_hostile_p2p_soak(ROOT / "architecture" / "hostile-p2p-soak-scenarios.json")
        result = {
            "gate_id": "public-production-p2p-soak",
            "ok": bool(smoke.get("ok")),
            "mode": "source-hostile-p2p-soak",
            "status": "source-complete-evidence-required",
            "scenario_count": smoke.get("scenario_count"),
            "smoke": smoke,
        }
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
