import importlib.util
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

import netcoin.chain as chain_module
import netcoin.node as node_module
from netcoin.block import Block, BlockHeader, make_block, merkle_root, mine_header
from netcoin.chain import Blockchain, ChainError
from netcoin.miner import solve_template
from netcoin.node import NetCoinNode, make_handler
from netcoin.params import HALVING_INTERVAL, INITIAL_SUBSIDY, ZERO_HASH
from netcoin.rpc import RPCServer
from netcoin.rpc import make_handler as make_rpc_handler
from netcoin.tx import (
    Transaction,
    TransactionError,
    TxInput,
    TxOutput,
    amount_to_sats,
    create_coinbase_transaction,
)
from netcoin.wallet import Wallet


def load_faucet_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "faucet_server.py"
    spec = importlib.util.spec_from_file_location("netcoin_faucet_server", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def funded_chain(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    receiver = Wallet.create()
    for _ in range(101):
        chain.mine_block(miner.address)
    return chain, miner, receiver


def flip_hex(value: str) -> str:
    """Return a same-length hex string with its first nibble changed."""
    if not value:
        return value
    head = "1" if value[0] in "0gG" else "0"
    return head + value[1:]


def coinbase_block_at_tip(chain: Blockchain, miner_address: str, extra_txs=(), timestamp=None) -> Block:
    """Build and proof-of-work a block extending the current tip.

    Unlike chain.mine_block this does not pre-validate, so tests can construct
    deliberately invalid blocks (double spends, bad timestamps) that still carry
    valid proof of work and a correct merkle root.
    """
    height = chain.height() + 1
    bits = chain.expected_bits_for_height(height, chain.chain)
    coinbase = create_coinbase_transaction(height, miner_address, chain.subsidy(height))
    transactions = [coinbase, *extra_txs]
    if timestamp is None:
        return make_block(chain.tip_hash(), height, bits, transactions)
    header = BlockHeader(
        version=1,
        previous_hash=chain.tip_hash(),
        merkle_root=merkle_root(transactions),
        timestamp=timestamp,
        bits=bits,
        nonce=0,
        height=height,
    )
    return Block(header=mine_header(header), transactions=transactions)


class served_node:
    """Run a NetCoinNode HTTP server for a chain and yield its base URL."""

    def __init__(self, chain: Blockchain, peers=None):
        self.node = NetCoinNode(chain, peers=peers or [])
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.node))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def serve_static_peer(responses):
    """Start a tiny HTTP server returning canned JSON keyed by URL path."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            body = json.dumps(responses.get(path, {})).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_address[1]}"


def test_rejects_malformed_block_merkle_root(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    block = solve_template(chain.get_block_template(miner_address=miner.address), miner.address)
    block.header.merkle_root = ZERO_HASH

    with pytest.raises(ChainError, match="merkle root"):
        chain.add_block(block)
    assert chain.height() == 0


def test_rejects_block_with_wrong_previous_hash(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    block = solve_template(chain.get_block_template(miner_address=miner.address), miner.address)
    block.header.previous_hash = "f" * 64
    # Re-establish valid proof of work for the tampered header so this exercises
    # the "does not connect" path rather than being rejected for bad PoW first.
    mine_header(block.header)

    with pytest.raises(ChainError, match="does not connect|previous hash"):
        chain.add_block(block)
    assert chain.height() == 0
    assert chain.tip().header.height == 0


def test_rejects_bad_transaction_that_changes_outputs_after_signing(tmp_path: Path):
    chain, miner, receiver = funded_chain(tmp_path)
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    tampered = Transaction(
        inputs=tx.inputs,
        outputs=[TxOutput(amount=amount_to_sats("2"), address=receiver.address)],
        version=tx.version,
        locktime=tx.locktime,
    )

    with pytest.raises(ChainError, match="signature|spends more"):
        chain.add_mempool_transaction(tampered)
    assert chain.mempool_info()["size"] == 0


def test_rejects_replayed_transaction_after_it_is_mined(tmp_path: Path):
    chain, miner, receiver = funded_chain(tmp_path)
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    chain.add_mempool_transaction(tx)
    chain.mine_block(miner.address)

    with pytest.raises(ChainError, match="missing or already-spent UTXO"):
        chain.add_mempool_transaction(tx)


def test_duplicate_block_submission_is_idempotent(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    block = solve_template(chain.get_block_template(miner_address=miner.address), miner.address)

    assert chain.add_block(block) == block.hash()
    assert chain.add_block(Block.from_dict(block.to_dict())) == block.hash()
    assert chain.height() == 1


def test_headers_limit_is_clamped(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(3):
        chain.mine_block(miner.address)

    assert len(chain.headers(start_height=0, limit=999_999)) <= 2000


def test_node_returns_json_error_for_malformed_post_without_crashing(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    node = NetCoinNode(chain)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(node))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        request = Request(f"{base_url}/tx", data=b"{not-json", headers={"Content-Type": "application/json"}, method="POST")
        with pytest.raises(HTTPError) as excinfo:
            urlopen(request, timeout=5)
        assert excinfo.value.code == 400
        error = json.loads(excinfo.value.read().decode("utf-8"))
        assert error["ok"] is False

        with urlopen(f"{base_url}/info", timeout=5) as response:
            info = json.loads(response.read().decode("utf-8"))
        assert info["ok"] is True
        assert info["node"]["height"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_faucet_rejects_invalid_addresses_and_rate_limits_by_ip(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "COOLDOWN_SECONDS", 24 * 60 * 60)
    state = {
        "requests": [
            {
                "ip": "203.0.113.10",
                "address": "Ntest",
                "timestamp": int(faucet.time.time()),
                "txid": "abc",
                "amount": "5",
            }
        ]
    }

    assert faucet.validate_address("not-a-netcoin-address") is False
    limited, remaining = faucet.rate_limited("203.0.113.10", state)
    assert limited is True
    assert remaining > 0
    other_limited, _remaining = faucet.rate_limited("203.0.113.11", state)
    assert other_limited is False


# ----------------------------------------------------------------------
# Invalid-signature tests
# ----------------------------------------------------------------------

def test_rejects_transaction_with_forged_signature(tmp_path: Path):
    chain, miner, receiver = funded_chain(tmp_path)
    tx = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))

    tampered = Transaction.from_dict(tx.to_dict())
    txin = tampered.inputs[0]
    # The legacy P2PKH path verifies through script_sig, so corrupt the signature
    # token there (and the mirrored signature field) to forge a spend.
    sig, _, pub = txin.script_sig.partition(" ")
    txin.script_sig = f"{flip_hex(sig)} {pub}"
    txin.signature = flip_hex(txin.signature)

    with pytest.raises(ChainError, match="signature"):
        chain.add_mempool_transaction(tampered)
    assert chain.mempool_info()["size"] == 0


def test_rejects_input_signed_by_wrong_key(tmp_path: Path):
    chain, miner, receiver = funded_chain(tmp_path)
    attacker = Wallet.create()
    utxo = chain.utxos_for_address(miner.address)[0]
    tx = Transaction(
        inputs=[TxInput(txid=utxo.txid, vout=utxo.vout)],
        outputs=[TxOutput(amount=amount_to_sats("1"), address=receiver.address)],
    )

    # The signing guard must refuse to sign a UTXO the key does not control.
    with pytest.raises(TransactionError, match="does not control"):
        tx.sign_input(0, attacker.private_key, utxo)


# ----------------------------------------------------------------------
# Double-spend tests
# ----------------------------------------------------------------------

def test_mempool_rejects_conflicting_double_spend(tmp_path: Path):
    chain, miner, receiver = funded_chain(tmp_path)
    spend_a = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    spend_b = miner.create_transaction(chain, receiver.address, amount_to_sats("2"), amount_to_sats("0.01"))
    assert spend_a.inputs[0].outpoint() == spend_b.inputs[0].outpoint()

    chain.add_mempool_transaction(spend_a)
    with pytest.raises(ChainError, match="non-replaceable"):
        chain.add_mempool_transaction(spend_b)
    assert chain.mempool_info()["size"] == 1


def test_rejects_double_spend_of_already_mined_utxo(tmp_path: Path):
    chain, miner, receiver = funded_chain(tmp_path)
    spend_a = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    spend_b = miner.create_transaction(chain, receiver.address, amount_to_sats("2"), amount_to_sats("0.01"))
    assert spend_a.inputs[0].outpoint() == spend_b.inputs[0].outpoint()

    chain.add_mempool_transaction(spend_a)
    chain.mine_block(miner.address)

    with pytest.raises(ChainError, match="missing or already-spent UTXO"):
        chain.add_mempool_transaction(spend_b)


def test_rejects_block_with_internal_double_spend(tmp_path: Path):
    chain, miner, receiver = funded_chain(tmp_path)
    spend_a = miner.create_transaction(chain, receiver.address, amount_to_sats("1"), amount_to_sats("0.01"))
    spend_b = miner.create_transaction(chain, receiver.address, amount_to_sats("2"), amount_to_sats("0.01"))
    assert spend_a.inputs[0].outpoint() == spend_b.inputs[0].outpoint()

    block = coinbase_block_at_tip(chain, miner.address, extra_txs=[spend_a, spend_b])
    with pytest.raises(ChainError, match="missing or already-spent UTXO"):
        chain.add_block(block)
    assert chain.height() == 101


# ----------------------------------------------------------------------
# Consensus / DoS-shaped block tests
# ----------------------------------------------------------------------

def test_rejects_block_with_far_future_timestamp(tmp_path: Path):
    chain, miner, _ = funded_chain(tmp_path)
    future = int(time.time()) + 3 * 60 * 60  # node tolerance is 2h
    block = coinbase_block_at_tip(chain, miner.address, timestamp=future)

    with pytest.raises(ChainError, match="future"):
        chain.add_block(block)
    assert chain.height() == 101


def test_block_weight_limit_is_enforced(tmp_path: Path, monkeypatch):
    chain, miner, _ = funded_chain(tmp_path)
    block = coinbase_block_at_tip(chain, miner.address)
    # Shrink the consensus weight budget so any real block trips the guard.
    monkeypatch.setattr(chain_module, "MAX_BLOCK_WEIGHT", 1)

    with pytest.raises(ChainError, match="maximum weight"):
        chain.add_block(block)
    assert chain.height() == 101


# ----------------------------------------------------------------------
# Peer-sync tests
# ----------------------------------------------------------------------

def test_replace_chain_ignores_equal_or_lesser_work(tmp_path: Path):
    main = Blockchain(tmp_path / "main")
    miner = Wallet.create()
    for _ in range(3):
        main.mine_block(miner.address)
    original_tip = main.tip_hash()

    shorter = Blockchain(tmp_path / "shorter")
    shorter.mine_block(miner.address)

    assert main.replace_chain(shorter.chain) is False
    assert main.height() == 3
    assert main.tip_hash() == original_tip


def test_replace_chain_adopts_greater_work(tmp_path: Path):
    short = Blockchain(tmp_path / "short")
    miner = Wallet.create()
    short.mine_block(miner.address)

    longer = Blockchain(tmp_path / "longer")
    for _ in range(4):
        longer.mine_block(miner.address)

    assert short.replace_chain(longer.chain) is True
    assert short.height() == 4
    assert short.tip_hash() == longer.tip_hash()


def test_node_persists_and_reloads_peers(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    node = NetCoinNode(chain, peers=["http://seed1.example:28444/"])
    node.add_peer("http://seed2.example:28444")

    # A fresh node on the same data directory reloads peers from disk.
    reloaded = NetCoinNode(Blockchain(tmp_path / "chain"))
    assert reloaded.peers == {"http://seed1.example:28444", "http://seed2.example:28444"}


def test_node_peer_persistence_can_be_disabled(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    NetCoinNode(chain, peers=["http://seed1.example:28444"], persist=False)
    reloaded = NetCoinNode(Blockchain(tmp_path / "chain"))
    assert reloaded.peers == set()


def test_sync_adopts_longer_valid_chain_from_peer(tmp_path: Path):
    remote = Blockchain(tmp_path / "remote")
    miner = Wallet.create()
    for _ in range(5):
        remote.mine_block(miner.address)

    local = Blockchain(tmp_path / "local")
    with served_node(remote) as peer:
        local_node = NetCoinNode(local, peers=[peer.base_url])
        adopted = local_node.sync_all()

    assert adopted == 1
    assert local.height() == 5
    assert local.tip_hash() == remote.tip_hash()


def test_sync_rejects_invalid_chain_from_peer(tmp_path: Path):
    # Build a real 2-block chain, then tamper the served JSON so block 1 has a
    # bad merkle root. A node must keep its own chain rather than adopt it.
    source = Blockchain(tmp_path / "source")
    miner = Wallet.create()
    source.mine_block(miner.address)
    export = source.export_chain()
    export["blocks"][1]["header"]["merkle_root"] = ZERO_HASH

    responses = {
        "/info": {"ok": True, "node": {"height": 99}},
        "/headers": {"headers": []},
        "/chain": export,
    }
    server, thread, base_url = serve_static_peer(responses)

    local = Blockchain(tmp_path / "local")
    try:
        local_node = NetCoinNode(local, peers=[base_url])
        adopted = local_node.sync_all()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert adopted == 0
    assert local.height() == 0


# ----------------------------------------------------------------------
# Node-endpoint DoS-resistance tests
# ----------------------------------------------------------------------

def test_node_headers_endpoint_caps_response(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(3):
        chain.mine_block(miner.address)

    with served_node(chain) as peer:
        with urlopen(f"{peer.base_url}/headers?start=0&limit=10000000", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))

    assert len(payload["headers"]) <= 2000


def test_node_survives_garbage_block_post(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    with served_node(chain) as peer:
        request = Request(
            f"{peer.base_url}/block",
            data=b'{"not": "a block"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as excinfo:
            urlopen(request, timeout=5)
        assert excinfo.value.code == 400

        with urlopen(f"{peer.base_url}/info", timeout=5) as response:
            info = json.loads(response.read().decode("utf-8"))
        assert info["ok"] is True
        assert info["node"]["height"] == 0


def test_node_rejects_oversized_request_body(tmp_path: Path, monkeypatch):
    chain = Blockchain(tmp_path / "chain")
    monkeypatch.setattr(node_module, "MAX_REQUEST_BODY_BYTES", 16)
    with served_node(chain) as peer:
        request = Request(
            f"{peer.base_url}/tx",
            data=b'{"padding":"this body is definitely longer than sixteen bytes"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as excinfo:
            urlopen(request, timeout=5)
        assert excinfo.value.code == 400
        error = json.loads(excinfo.value.read().decode("utf-8"))
        assert "too large" in error["error"]

        with urlopen(f"{peer.base_url}/info", timeout=5) as response:
            assert json.loads(response.read().decode("utf-8"))["ok"] is True


# ----------------------------------------------------------------------
# Consensus: halving schedule
# ----------------------------------------------------------------------

def test_subsidy_halving_schedule(tmp_path: Path):
    # The legacy halving schedule governs only BELOW EMISSION_ACTIVATION_HEIGHT.
    # At/after activation the random-emission schedule supersedes halvings (see
    # docs/ECONOMICS_PLAN.md and test_emission.py); the change is additive because
    # the activation height is far ahead of any mined block.
    from netcoin.emission import is_active
    from netcoin.params import EMISSION_ACTIVATION_HEIGHT

    chain = Blockchain(tmp_path / "chain")
    # Below activation the legacy schedule applies. With the testnet activation
    # height (5_000) sitting below the first halving (210_000), every pre-activation
    # block simply pays INITIAL_SUBSIDY — the halving is superseded by emission
    # before it would ever trigger.
    assert EMISSION_ACTIVATION_HEIGHT < HALVING_INTERVAL
    assert chain.subsidy(0) == INITIAL_SUBSIDY
    assert chain.subsidy(EMISSION_ACTIVATION_HEIGHT - 1) == INITIAL_SUBSIDY
    # The negative-height guard is unchanged.
    with pytest.raises(ChainError):
        chain.subsidy(-1)
    # At/after activation, emission (not halving) governs — sanity-check the gate.
    assert is_active(EMISSION_ACTIVATION_HEIGHT)
    assert not is_active(EMISSION_ACTIVATION_HEIGHT - 1)


# ----------------------------------------------------------------------
# RPC authentication (#17)
# ----------------------------------------------------------------------

def _rpc_call(base_url, method, params=None, token=None):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return Request(base_url, data=body, headers=headers, method="POST")


def test_rpc_requires_token_when_configured(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    rpc = RPCServer(chain)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_rpc_handler(rpc, token="s3cret"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        # No token -> 401
        with pytest.raises(HTTPError) as excinfo:
            urlopen(_rpc_call(base_url, "getblockcount"), timeout=5)
        assert excinfo.value.code == 401

        # Wrong token -> 401
        with pytest.raises(HTTPError) as excinfo:
            urlopen(_rpc_call(base_url, "getblockcount", token="nope"), timeout=5)
        assert excinfo.value.code == 401

        # Correct token -> 200 with result
        with urlopen(_rpc_call(base_url, "getblockcount", token="s3cret"), timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["error"] is None
        assert payload["result"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_rpc_open_when_no_token(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    rpc = RPCServer(chain)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_rpc_handler(rpc, token=None))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urlopen(_rpc_call(base_url, "getblockcount"), timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["result"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

