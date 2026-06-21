"""Address index + /address endpoint (#7/#42), node config file (#17),
faucet history API (#40)."""
import importlib.util
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

from netcoin.chain import Blockchain
from netcoin.config import load_config
from netcoin.node import NetCoinNode, make_handler
from netcoin.wallet import Wallet


class served:
    def __init__(self, node: NetCoinNode):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(node))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def load_faucet():
    path = Path(__file__).resolve().parents[1] / "tools" / "faucet_server.py"
    spec = importlib.util.spec_from_file_location("netcoin_faucet_hist", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- 7 / 42 address index ---

def test_address_index_tracks_outputs(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(3):
        chain.mine_block(miner.address)
    summary = chain.address_summary(miner.address)
    assert summary["address"] == miner.address
    # 3 coinbase txs paid this address.
    assert summary["transaction_count"] == 3
    assert summary["balance"]["total"] > 0


def test_address_index_rebuilds_after_restart(tmp_path: Path):
    miner = Wallet.create()
    chain = Blockchain(tmp_path / "n")
    for _ in range(2):
        chain.mine_block(miner.address)
    reloaded = Blockchain(tmp_path / "n")
    assert reloaded.address_summary(miner.address)["transaction_count"] == 2


def test_address_endpoint_over_http(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    chain.mine_block(miner.address)
    with served(NetCoinNode(chain, persist=False)) as s:
        with urlopen(f"{s.url}/address/{miner.address}", timeout=5) as r:
            data = json.loads(r.read().decode())
    assert data["address"] == miner.address
    assert data["transaction_count"] == 1


# --- 17 node config file ---

def test_load_config_json(tmp_path: Path):
    p = tmp_path / "netcoin.json"
    p.write_text(json.dumps({"host": "0.0.0.0", "port": 28444, "seeds": True,
                             "peers": ["http://a:28444", "http://b:28444"]}))
    cfg = load_config(p)
    assert cfg["host"] == "0.0.0.0"
    assert cfg["port"] == 28444
    assert cfg["seeds"] is True
    assert cfg["peer"] == ["http://a:28444", "http://b:28444"]


def test_load_config_keyvalue(tmp_path: Path):
    p = tmp_path / "netcoin.conf"
    p.write_text(
        "# sample config\n"
        "host = 0.0.0.0\n"
        "port = 28444\n"
        "seeds = true\n"
        "peer = http://a:28444\n"
        "peer = http://b:28444\n"
    )
    cfg = load_config(p)
    assert cfg["host"] == "0.0.0.0"
    assert cfg["port"] == 28444
    assert cfg["seeds"] is True
    assert cfg["peer"] == ["http://a:28444", "http://b:28444"]


# --- 40 faucet history ---

def test_faucet_public_history_excludes_ips():
    faucet = load_faucet()
    state = {"requests": [
        {"ip": "203.0.113.1", "address": "Na", "amount": "5", "txid": "t1", "timestamp": 100},
        {"ip": "203.0.113.2", "address": "Nb", "amount": "5", "txid": "t2", "timestamp": 200},
    ]}
    history = faucet.public_history(state, limit=10)
    assert history[0]["txid"] == "t2"  # newest first
    assert all("ip" not in g for g in history)
    assert {g["address"] for g in history} == {"Na", "Nb"}
