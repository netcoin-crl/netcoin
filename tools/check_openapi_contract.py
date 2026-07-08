#!/usr/bin/env python3
"""Route/schema parity smoke check for the NetCoin OpenAPI files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_ROUTES = {
    "/markets",
    "/markets/{market_id}/orderbook",
    "/markets/{market_id}/ticker",
    "/markets/{market_id}/trades",
    "/markets/{market_id}/positions",
    "/markets/{market_id}/depth",
    "/markets/{market_id}/candles",
    "/markets/{market_id}/open-interest",
    "/markets/{market_id}/batch-orders",
    "/markets/{market_id}/cancel-all",
    "/markets/{market_id}/pause",
    "/markets/{market_id}/resume",
}
SENSITIVE_WRITE_WORDS = ("signed", "envelope", "signature")


def extract_paths(text: str) -> set[str]:
    return set(re.findall(r"^\s{2}(/[^:]+):\s*$", text, flags=re.MULTILINE))


def main() -> int:
    paths = [Path("docs/openapi.yaml"), Path("sites/api/openapi.yaml")]
    missing_files = [str(p) for p in paths if not p.exists()]
    if missing_files:
        print("missing OpenAPI files: " + ", ".join(missing_files), file=sys.stderr)
        return 2
    failed = False
    for path in paths:
        text = path.read_text()
        found = extract_paths(text)
        missing = sorted(REQUIRED_ROUTES - found)
        if missing:
            failed = True
            print(f"{path}: missing routes {missing}", file=sys.stderr)
        for route in REQUIRED_ROUTES:
            if route not in found:
                continue
            idx = text.find(f"  {route}:")
            next_idx = text.find("\n  /", idx + 1)
            block = text[idx : next_idx if next_idx != -1 else len(text)]
            if any(method in block for method in ("post:", "put:", "patch:", "delete:")):
                lower = block.lower()
                if not any(word in lower for word in SENSITIVE_WRITE_WORDS):
                    failed = True
                    print(
                        f"{path}: sensitive route {route} does not document signed envelope/signature", file=sys.stderr
                    )
            if "responses:" not in block:
                failed = True
                print(f"{path}: route {route} missing responses block", file=sys.stderr)
    if failed:
        return 1
    print("OpenAPI contract smoke check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
