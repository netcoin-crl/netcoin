#!/usr/bin/env python3
"""Loadtest the public-node HTTP rate limiter against a local in-process node."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.chain import Blockchain  # noqa: E402
from netcoin.node import NetCoinNode, make_handler  # noqa: E402


class ServedNode:
    def __init__(self, rate_limit_per_min: int):
        self.tempdir = tempfile.TemporaryDirectory(prefix="netcoin-rate-limit-")
        chain = Blockchain(Path(self.tempdir.name) / "chain")
        self.node = NetCoinNode(chain, persist=False, rate_limit_per_min=rate_limit_per_min)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.node))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.url = ""

    def __enter__(self) -> "ServedNode":
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tempdir.cleanup()


def request_info(base_url: str, api_key: str) -> dict[str, int]:
    req = Request(f"{base_url}/info", headers={"X-Netcoin-Api-Key": api_key})
    try:
        with urlopen(req, timeout=5) as response:
            response.read()
            return {"status": int(response.status), "retry_after": 0}
    except HTTPError as exc:
        exc.read()
        retry_after = int(exc.headers.get("Retry-After", "0") or 0)
        return {"status": int(exc.code), "retry_after": retry_after}


def run_loadtest(rate_limit_per_min: int, requests: int, workers: int, api_key: str) -> dict[str, object]:
    started = time.time()
    with ServedNode(rate_limit_per_min) as served:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(request_info, served.url, api_key) for _ in range(requests)]
            results = [future.result() for future in as_completed(futures)]
    counts: dict[str, int] = {}
    retry_after_values = []
    for result in results:
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1
        if result["status"] == 429:
            retry_after_values.append(int(result["retry_after"]))
    accepted = counts.get("200", 0)
    rejected = counts.get("429", 0)
    ok = accepted <= rate_limit_per_min and rejected >= max(0, requests - rate_limit_per_min)
    if rejected:
        ok = ok and all(value >= 1 for value in retry_after_values)
    return {
        "ok": ok,
        "rate_limit_per_min": rate_limit_per_min,
        "requests": requests,
        "workers": workers,
        "accepted": accepted,
        "rejected": rejected,
        "status_counts": counts,
        "retry_after_values": retry_after_values,
        "duration_seconds": round(time.time() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Exercise NetCoin node rate limiting with concurrent /info calls")
    parser.add_argument("--rate-limit-per-min", type=int, default=8)
    parser.add_argument("--requests", type=int, default=24)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--api-key", default="loadtest-key")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report = run_loadtest(
        rate_limit_per_min=max(1, args.rate_limit_per_min),
        requests=max(1, args.requests),
        workers=max(1, args.workers),
        api_key=args.api_key,
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
