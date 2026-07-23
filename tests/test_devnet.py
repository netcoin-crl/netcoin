"""Instant devnet: a fresh chain with pre-funded, spendable wallets in seconds."""

import json
import subprocess
import sys
from pathlib import Path

from netcoin.wallet import Wallet

ROOT = Path(__file__).resolve().parents[1]


def _run_devnet(data_dir: Path, funded: int):
    result = subprocess.run(
        [sys.executable, "-m", "netcoin", "--data", str(data_dir), "devnet", "--funded", str(funded)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def test_devnet_builds_prefunded_spendable_wallets(tmp_path):
    summary = _run_devnet(tmp_path / "dn", 3)
    assert summary["network"] == "devnet"
    assert summary["height"] > summary["coinbase_maturity"]
    assert len(summary["wallets"]) == 3
    for w in summary["wallets"]:
        # Every wallet must have mature, spendable funds immediately.
        assert w["spendable_sats"] > 0
        assert w["spendable_net"] > 0
        assert w["address"].startswith("N") or w["address"].startswith("net1")
        # The saved wallet file exists and loads back to the same address.
        wf = Path(w["wallet_file"])
        assert wf.exists()
        loaded = Wallet.load(wf, passphrase=None)
        assert loaded.address == w["address"]
        assert loaded.private_key_hex == w["private_key_hex"]


def test_devnet_reset_rebuilds_cleanly(tmp_path):
    d = tmp_path / "dn"
    first = _run_devnet(d, 2)
    # A second run with --reset must produce a fresh chain (new wallets).
    result = subprocess.run(
        [sys.executable, "-m", "netcoin", "--data", str(d), "devnet", "--funded", "2", "--reset"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    second = json.loads(result.stdout)
    assert second["height"] > second["coinbase_maturity"]
    assert {w["address"] for w in second["wallets"]} != {w["address"] for w in first["wallets"]}
