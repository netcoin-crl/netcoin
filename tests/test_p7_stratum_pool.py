from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from threading import Thread

import pytest

from netcoin.chain import Blockchain
from netcoin.miner import solve_template
from netcoin.pool import POOL_PROTOCOL, MiningPool, ShareRecord, StratumLiteTCPServer
from netcoin.wallet import Wallet
from tools.run_pool_mining_probe import pool_rpc, run_probe

ROOT = Path(__file__).resolve().parents[1]


def start_pool(pool: MiningPool):
    server = StratumLiteTCPServer(("127.0.0.1", 0), pool)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, int(server.server_address[1])


def test_stratum_lite_getwork_and_submit_mines_block(tmp_path: Path):
    pool_wallet = Wallet.create()
    chain = Blockchain(tmp_path / "chain")
    pool = MiningPool(chain, payout_address=pool_wallet.address)
    server, thread, port = start_pool(pool)
    try:
        greeting, work = pool_rpc("127.0.0.1", port, [{"method": "getwork"}])
        assert greeting["protocol"] == POOL_PROTOCOL
        template = work["result"]
        block = solve_template(template, pool_wallet.address)
        submit = pool_rpc(
            "127.0.0.1",
            port,
            [
                {
                    "method": "submit",
                    "params": {"miner": pool_wallet.address, "job_id": template["job_id"], "block": block.to_dict()},
                }
            ],
        )[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert submit["ok"] is True, submit
    assert submit["accepted_block"] is True
    assert chain.height() == 1
    assert pool.stats()["accepted"] == 1
    assert pool.payout_plan()["payouts"][pool_wallet.address] == block.transactions[0].total_output()


def test_pool_rejects_unknown_job_id(tmp_path: Path):
    pool_wallet = Wallet.create()
    chain = Blockchain(tmp_path / "chain")
    pool = MiningPool(chain, payout_address=pool_wallet.address)
    template = pool.job()
    block = solve_template(template, pool_wallet.address)
    result = pool.submit({"miner": pool_wallet.address, "job_id": "missing", "block": block.to_dict()})
    assert result["ok"] is False
    assert "unknown job_id" in result["error"]


def test_pool_payout_plan_splits_by_share_weight(tmp_path: Path):
    wallet_a = Wallet.create()
    wallet_b = Wallet.create()
    pool = MiningPool(Blockchain(tmp_path / "chain"), payout_address=wallet_a.address)
    pool.shares.append(ShareRecord(wallet_a.address, "a", "00aa", 2, False, 1))
    pool.shares.append(ShareRecord(wallet_b.address, "b", "0bbb", 1, False, 1))
    payouts = pool.payout_plan(reward=300)
    assert payouts["payouts"][wallet_a.address] == 200
    assert payouts["payouts"][wallet_b.address] == 100


def test_pool_cli_exposes_stratum_port():
    proc = subprocess.run(
        [sys.executable, "-m", "netcoin", "pool", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--stratum-port" in proc.stdout


@pytest.mark.localnet
def test_pool_mining_probe_mines_block_through_tcp_pool(tmp_path: Path):
    report = run_probe(data_dir=tmp_path / "pool-chain")
    assert report["ok"] is True, report
    assert report["height"] == 1
    assert report["submit"]["accepted_block"] is True
    assert report["stats"]["accepted"] == 1
