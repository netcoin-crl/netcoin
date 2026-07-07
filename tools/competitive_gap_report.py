#!/usr/bin/env python3
"""Generate NetCoin competitive-feature scaffold or 5/10 midlevel reports."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.competitive import build_competitive_gap_report, build_level5_report, validate_level5, all_area_smokes


def to_markdown(report: dict) -> str:
    title = "NetCoin Competitive Level-5 Report" if report.get("schema") == "netcoin-competitive-level5-v1" else "NetCoin Competitive Feature Report"
    lines = [
        f"# {title}\n\n",
        f"- Area count: {report['area_count']}\n",
        f"- Feature count: {report['feature_count']}\n",
        f"- Production claim: {report['production_claim']}\n",
        f"- Warning: {report['warning']}\n",
    ]
    if "minimum_feature_score" in report:
        lines.append(f"- Minimum feature score: {report['minimum_feature_score']}/10\n")
    lines.append("\n")
    for area in report["areas"]:
        lines.append(f"## {area['title']}\n\n")
        lines.append(f"Purpose: {area['purpose']}\n\n")
        if "module" in area:
            lines.append(f"Module: `{area['module']}`  \n")
        if "doc_path" in area:
            lines.append(f"Docs: `{area['doc_path']}`  \n")
        if "config_path" in area:
            lines.append(f"Config: `{area['config_path']}`\n\n")
        for feature in area["features"]:
            score = feature.get("maturity_score", "?")
            lines.append(f"- `{feature['status']}` ({score}/10) — {feature['title']}\n")
        lines.append("\n")
    return "".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write JSON instead of Markdown")
    parser.add_argument("--out", default="", help="optional output file")
    parser.add_argument("--area", default="", help="limit report to one area slug")
    parser.add_argument("--level5", action="store_true", help="write the 5/10 midlevel report")
    parser.add_argument("--validate", action="store_true", help="validate the 5/10 report")
    parser.add_argument("--smoke", action="store_true", help="run deterministic midlevel smoke checks")
    args = parser.parse_args()
    area = args.area or None
    if args.validate:
        report = validate_level5(area)
    elif args.smoke:
        report = all_area_smokes()
        if area:
            report = {"ok": report["areas"][area]["ok"], "area": area, "result": report["areas"][area]}
    elif args.level5:
        report = build_level5_report(area)
    else:
        report = build_competitive_gap_report()
        if area:
            matches = [a for a in report["areas"] if a["slug"] == area]
            if not matches:
                raise SystemExit(f"unknown area: {area}")
            report = {**report, "areas": matches, "area_count": 1, "feature_count": matches[0]["feature_count"]}
    text = json.dumps(report, indent=2, sort_keys=True) + "\n" if args.json or args.validate or args.smoke else to_markdown(report)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
