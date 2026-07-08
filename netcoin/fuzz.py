"""Deterministic stdlib fuzz runner for NetCoin parser and endpoint surfaces."""

from __future__ import annotations

import json
import random
import string
import tempfile
import time
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .block import Block, BlockError
from .chain import Blockchain
from .node import NetCoinNode, make_handler
from .script import ScriptContext, classify_script, verify_script
from .serialization import SerializationError, decode_raw_transaction
from .tx import Transaction, TransactionError


class FuzzError(RuntimeError):
    """Raised when a fuzz target sees an unexpected crash or endpoint failure."""


EXPECTED_PARSE_ERRORS = (
    TransactionError,
    BlockError,
    SerializationError,
    ValueError,
    KeyError,
    TypeError,
    IndexError,
    UnicodeDecodeError,
)

TARGETS = ("tx-dict", "block-dict", "rawtx", "script", "node-http")


@dataclass
class FuzzConfig:
    target: str = "all"
    iterations: int = 500
    seed: int = 1234567
    max_bytes: int = 256


def random_json_value(rng: random.Random, depth: int = 0) -> Any:
    choice = rng.randint(0, 6)
    if depth > 3 or choice == 0:
        return rng.choice([None, True, False, 0, -1, rng.randint(-(10**12), 10**12), "", "x" * rng.randint(0, 16)])
    if choice == 1:
        return "".join(rng.choice(string.printable) for _ in range(rng.randint(0, 24)))
    if choice == 2:
        return [random_json_value(rng, depth + 1) for _ in range(rng.randint(0, 5))]
    if choice == 3:
        return {str(rng.randint(0, 7)): random_json_value(rng, depth + 1) for _ in range(rng.randint(0, 5))}
    if choice == 4:
        return rng.choice(["00" * 32, "ff" * 32, "zz", "", "deadbeef"])
    return rng.randint(-(10**24), 10**24)


def _record(result: dict[str, Any], accepted: bool = False, rejected: bool = False) -> None:
    result["cases"] += 1
    if accepted:
        result["accepted"] += 1
    if rejected:
        result["rejected"] += 1


def fuzz_tx_dict(rng: random.Random, iterations: int) -> dict[str, Any]:
    result = {"target": "tx-dict", "cases": 0, "accepted": 0, "rejected": 0}
    for _ in range(iterations):
        data = random_json_value(rng)
        if not isinstance(data, dict):
            data = {"inputs": data, "outputs": random_json_value(rng)}
        try:
            Transaction.from_dict(data)
        except EXPECTED_PARSE_ERRORS:
            _record(result, rejected=True)
        except Exception as exc:
            raise FuzzError(f"unexpected tx-dict crash: {type(exc).__name__}: {exc}") from exc
        else:
            _record(result, accepted=True)
    return result


def fuzz_block_dict(rng: random.Random, iterations: int) -> dict[str, Any]:
    result = {"target": "block-dict", "cases": 0, "accepted": 0, "rejected": 0}
    for _ in range(iterations):
        data = random_json_value(rng)
        if not isinstance(data, dict):
            data = {"header": random_json_value(rng), "transactions": random_json_value(rng)}
        try:
            Block.from_dict(data)
        except EXPECTED_PARSE_ERRORS:
            _record(result, rejected=True)
        except Exception as exc:
            raise FuzzError(f"unexpected block-dict crash: {type(exc).__name__}: {exc}") from exc
        else:
            _record(result, accepted=True)
    return result


def fuzz_rawtx(rng: random.Random, iterations: int, max_bytes: int) -> dict[str, Any]:
    result = {"target": "rawtx", "cases": 0, "accepted": 0, "rejected": 0}
    alphabet = "0123456789abcdefABCDEFxyzZ "
    for _ in range(iterations):
        raw = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, max_bytes * 2)))
        try:
            decode_raw_transaction(raw)
        except EXPECTED_PARSE_ERRORS:
            _record(result, rejected=True)
        except Exception as exc:
            raise FuzzError(f"unexpected rawtx crash: {type(exc).__name__}: {exc}") from exc
        else:
            _record(result, accepted=True)
    return result


def fuzz_script(rng: random.Random, iterations: int) -> dict[str, Any]:
    result = {"target": "script", "cases": 0, "accepted": 0, "rejected": 0}
    tokens = [
        "OP_DUP",
        "OP_HASH160",
        "OP_EQUAL",
        "OP_CHECKSIG",
        "OP_CHECKMULTISIG",
        "OP_IF",
        "OP_ELSE",
        "OP_ENDIF",
        "OP_RETURN",
        "abc",
        "00",
        "",
        "ff" * 20,
        "OP_0",
        "1",
        "OP_CHECKLOCKTIMEVERIFY",
    ]
    context = ScriptContext(sighash=b"\x00" * 32, locktime=0, sequence=0xFFFFFFFF)
    for _ in range(iterations):
        script_sig = " ".join(rng.choice(tokens) for _ in range(rng.randint(0, 8)))
        script_pubkey = " ".join(rng.choice(tokens) for _ in range(rng.randint(0, 8)))
        try:
            if not isinstance(classify_script(script_pubkey), str):
                raise FuzzError("classify_script returned non-string")
            if not isinstance(verify_script(script_sig, script_pubkey, context), bool):
                raise FuzzError("verify_script returned non-bool")
        except EXPECTED_PARSE_ERRORS:
            _record(result, rejected=True)
        except Exception as exc:
            raise FuzzError(f"unexpected script crash: {type(exc).__name__}: {exc}") from exc
        else:
            _record(result, accepted=True)
    return result


def fuzz_node_http(rng: random.Random, iterations: int, max_bytes: int) -> dict[str, Any]:
    result = {"target": "node-http", "cases": 0, "accepted": 0, "rejected": 0}
    with tempfile.TemporaryDirectory(prefix="netcoin-fuzz-node-") as tmp:
        chain = Blockchain(Path(tmp) / "chain")
        node = NetCoinNode(chain, persist=False, rate_limit_per_min=0)
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(node))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            for _ in range(iterations):
                path = rng.choice(["/tx", "/block", "/compact-block", "/peers", "/sync", "/submitblock", "/relay"])
                if rng.random() < 0.5:
                    body = bytes(rng.randint(0, 255) for _ in range(rng.randint(0, max_bytes)))
                else:
                    body = json.dumps(random_json_value(rng)).encode("utf-8")
                request = Request(
                    f"{base_url}{path}", data=body, headers={"Content-Type": "application/json"}, method="POST"
                )
                try:
                    urlopen(request, timeout=5)
                except HTTPError as exc:
                    if exc.code not in (400, 404):
                        raise FuzzError(f"unexpected HTTP status {exc.code} for {path}") from exc
                    _record(result, rejected=True)
                else:
                    _record(result, accepted=True)

            with urlopen(f"{base_url}/info", timeout=5) as response:
                info = json.loads(response.read().decode("utf-8"))
            if not info.get("ok"):
                raise FuzzError("node did not answer /info after fuzzing")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    return result


def run_fuzz(config: FuzzConfig) -> dict[str, Any]:
    if config.iterations < 0:
        raise FuzzError("iterations must be non-negative")
    if config.max_bytes < 0:
        raise FuzzError("max-bytes must be non-negative")
    targets = list(TARGETS) if config.target == "all" else [config.target]
    unknown = [target for target in targets if target not in TARGETS]
    if unknown:
        raise FuzzError(f"unknown fuzz target: {', '.join(unknown)}")

    started = time.time()
    results: list[dict[str, Any]] = []
    for index, target in enumerate(targets):
        rng = random.Random(config.seed + index)
        if target == "tx-dict":
            results.append(fuzz_tx_dict(rng, config.iterations))
        elif target == "block-dict":
            results.append(fuzz_block_dict(rng, config.iterations))
        elif target == "rawtx":
            results.append(fuzz_rawtx(rng, config.iterations, config.max_bytes))
        elif target == "script":
            results.append(fuzz_script(rng, config.iterations))
        elif target == "node-http":
            results.append(fuzz_node_http(rng, config.iterations, config.max_bytes))

    total_cases = sum(item["cases"] for item in results)
    return {
        "ok": True,
        "seed": config.seed,
        "iterations": config.iterations,
        "max_bytes": config.max_bytes,
        "targets": results,
        "total_cases": total_cases,
        "duration_seconds": round(time.time() - started, 3),
    }
