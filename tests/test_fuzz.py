"""Lightweight fuzz tests for NetCoin parsers and public node endpoints.

These do not look for *correct* output on garbage input — they assert that
malformed input is rejected with an expected exception (or handled), and that the
node keeps serving after a burst of junk. The goal is no crashes, no hangs, and no
unhandled exception types leaking out of the parsing surface.
"""
import json
import random
import string
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netcoin.block import Block, BlockError
from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode, make_handler
from netcoin.script import ScriptContext, classify_script, verify_script
from netcoin.serialization import decode_raw_transaction
from netcoin.tx import Transaction, TransactionError

EXPECTED_PARSE_ERRORS = (TransactionError, BlockError, ValueError, KeyError, TypeError, IndexError)


def rng():
    return random.Random(1234567)


def random_json_value(r, depth=0):
    choice = r.randint(0, 6)
    if depth > 3 or choice == 0:
        return r.choice([None, True, False, 0, -1, r.randint(-10**9, 10**9), "", "x" * r.randint(0, 8)])
    if choice == 1:
        return "".join(r.choice(string.printable) for _ in range(r.randint(0, 12)))
    if choice == 2:
        return [random_json_value(r, depth + 1) for _ in range(r.randint(0, 4))]
    if choice == 3:
        return {str(r.randint(0, 5)): random_json_value(r, depth + 1) for _ in range(r.randint(0, 4))}
    if choice == 4:
        return r.choice(["00" * 32, "ff" * 32, "zz", "", "deadbeef"])
    return r.randint(-(10**18), 10**18)


def test_fuzz_transaction_from_dict_never_crashes():
    r = rng()
    for _ in range(400):
        data = random_json_value(r)
        if not isinstance(data, dict):
            data = {"inputs": data, "outputs": random_json_value(r)}
        try:
            Transaction.from_dict(data)
        except EXPECTED_PARSE_ERRORS:
            pass  # acceptable: rejected cleanly


def test_fuzz_block_from_dict_never_crashes():
    r = rng()
    for _ in range(400):
        data = random_json_value(r)
        if not isinstance(data, dict):
            data = {"header": random_json_value(r), "transactions": random_json_value(r)}
        try:
            Block.from_dict(data)
        except EXPECTED_PARSE_ERRORS:
            pass


def test_fuzz_decode_raw_transaction_never_crashes():
    r = rng()
    alphabet = "0123456789abcdefABCDEFxyzZ "
    for _ in range(400):
        raw = "".join(r.choice(alphabet) for _ in range(r.randint(0, 80)))
        try:
            decode_raw_transaction(raw)
        except EXPECTED_PARSE_ERRORS:
            pass


def test_fuzz_script_parsing_never_crashes():
    r = rng()
    tokens = ["OP_DUP", "OP_HASH160", "OP_EQUAL", "OP_CHECKSIG", "abc", "00", "", "ff" * 20, "OP_0", "1", "OP_CHECKLOCKTIMEVERIFY"]
    context = ScriptContext(sighash=b"\x00" * 32, locktime=0, sequence=0xFFFFFFFF)
    for _ in range(400):
        script_sig = " ".join(r.choice(tokens) for _ in range(r.randint(0, 6)))
        script_pubkey = " ".join(r.choice(tokens) for _ in range(r.randint(0, 6)))
        # classify_script must always return a string and never raise.
        assert isinstance(classify_script(script_pubkey), str)
        try:
            result = verify_script(script_sig, script_pubkey, context)
            assert isinstance(result, bool)
        except EXPECTED_PARSE_ERRORS:
            pass


def test_fuzz_node_endpoints_survive_junk(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    node = NetCoinNode(chain)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(node))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    r = rng()
    try:
        for _ in range(60):
            path = r.choice(["/tx", "/block", "/compact-block", "/peers", "/sync", "/submitblock"])
            if r.random() < 0.5:
                body = bytes(r.randint(0, 255) for _ in range(r.randint(0, 40)))
            else:
                body = json.dumps(random_json_value(r)).encode("utf-8")
            request = Request(f"{base_url}{path}", data=body, headers={"Content-Type": "application/json"}, method="POST")
            try:
                urlopen(request, timeout=5)
            except HTTPError as exc:
                assert exc.code in (400, 404)  # rejected, not a server crash

        # After all the junk, the node still answers /info correctly.
        with urlopen(f"{base_url}/info", timeout=5) as response:
            info = json.loads(response.read().decode("utf-8"))
        assert info["ok"] is True
        assert info["node"]["height"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
