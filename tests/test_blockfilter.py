"""BIP158-style compact block filters (#12): GCS correctness, block filters,
header chaining, and serving filters over the node /cfilter endpoint."""
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import netcoin.blockfilter as bf
from netcoin.chain import Blockchain
from netcoin.node import NetCoinNode, make_handler
from netcoin.script import address_to_script_pubkey
from netcoin.wallet import Wallet


def test_gcs_no_false_negatives_and_low_false_positive():
    key = b"\x11" * 16
    elements = [f"script-{i}".encode() for i in range(200)]
    filt = bf.build_filter(elements, key)
    # every member must match
    assert all(bf.filter_match(filt, key, e) for e in elements)
    # non-members almost never match (rate ~1/M)
    fp = sum(bf.filter_match(filt, key, f"absent-{i}".encode()) for i in range(10000))
    assert fp <= 2, fp


def test_empty_block_filter_matches_nothing():
    filt = bf.build_filter([], b"\x00" * 16)
    assert bf.filter_match(filt, b"\x00" * 16, b"anything") is False


def test_block_filter_matches_paid_address_only(tmp_path: Path):
    chain = Blockchain(tmp_path / "c")
    paid = Wallet.create()
    other = Wallet.create()
    chain.mine_block(paid.address)
    block = chain.chain[-1]
    filt = bf.build_block_filter(block)
    assert bf.block_filter_match(filt, block.hash(), address_to_script_pubkey(paid.address)) is True
    assert bf.block_filter_match(filt, block.hash(), address_to_script_pubkey(other.address)) is False


def test_filter_header_chain_is_deterministic_and_linked():
    f0 = bf.build_filter([b"a", b"b"], b"\x01" * 16)
    f1 = bf.build_filter([b"c"], b"\x02" * 16)
    h0 = bf.compute_filter_header(f0, "")
    h1 = bf.compute_filter_header(f1, h0)
    assert len(h0) == 64 and len(h1) == 64
    assert bf.compute_filter_header(f0, "") == h0  # deterministic
    assert bf.compute_filter_header(f1, "") != h1  # depends on the previous header


def test_node_serves_cfilter_and_light_scan_finds_payments(tmp_path: Path):
    chain = Blockchain(tmp_path / "c")
    me = Wallet.create()
    stranger = Wallet.create()
    funded_heights = []
    for _ in range(5):
        chain.mine_block(me.address)
        funded_heights.append(chain.height())

    node = NetCoinNode(chain, peers=[])
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(node))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        my_spk = address_to_script_pubkey(me.address)
        stranger_spk = address_to_script_pubkey(stranger.address)
        hits = []
        for height in funded_heights:
            block_hash = chain.chain[height].hash()
            cf = json.loads(urlopen(f"{base}/cfilter/{block_hash}").read())
            assert cf["height"] == height
            raw = bytes.fromhex(cf["filter"])
            assert bf.block_filter_match(raw, block_hash, my_spk) is True
            assert bf.block_filter_match(raw, block_hash, stranger_spk) is False
            hits.append(height)
        assert hits == funded_heights
    finally:
        server.shutdown()
