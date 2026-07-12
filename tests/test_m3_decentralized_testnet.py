from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_addrv2_classifies_and_exports_node_map():
    from netcoin.addrv2 import AddrV2Record, network_id_for_host, public_node_map

    assert network_id_for_host("18.220.89.128") == "ipv4"
    assert network_id_for_host("2001:db8::1") == "ipv6"
    assert network_id_for_host("seed.netcoin.online") == "dns"
    record = AddrV2Record(host="18.220.89.128", port=28444, operator="netcoin-core", region="us-east-2")
    payload = record.to_dict()
    assert payload["schema"] == "netcoin-addrv2-v1"
    assert payload["endpoint"] == "18.220.89.128:28444"
    node_map = public_node_map([record])
    assert node_map["schema"] == "netcoin-public-node-map-v1"
    assert node_map["operator_count"] == 1


def test_pex_selects_diverse_records_and_ingests_peerdb(tmp_path):
    from netcoin.peerdb import PeerDatabase
    from netcoin.pex import build_pex_response, ingest_pex_records, select_pex_records

    peers = [
        {"host": "18.220.89.128", "port": 28444, "score": 5, "services": ["NETCOIN_PEX"]},
        {"host": "18.220.89.129", "port": 28444, "score": 5, "services": ["NETCOIN_PEX"]},
        {"host": "198.51.100.10", "port": 28444, "score": 10, "services": ["NETCOIN_PEX"]},
    ]
    records = select_pex_records(peers)
    assert len(records) == 3
    db = PeerDatabase(tmp_path / "peers.sqlite")
    result = ingest_pex_records(db, records)
    assert result == {"schema": "netcoin-pex-ingest-v1", "accepted": 3, "rejected": 0}
    response = build_pex_response(db)
    assert response["schema"] == "netcoin-pex-v1"
    assert response["count"] == 3


def test_p2p_addr_and_pex_messages_round_trip():
    from netcoin.addrv2 import parse_addr_payload
    from netcoin.p2p import Message, addr_message, getaddr_message, pex_message

    records = [{"host": "18.220.89.128", "port": 28444, "services": ["NETCOIN_PEX"]}]
    assert getaddr_message().command == "getaddr"
    parsed = Message.parse(addr_message(records).serialize())
    assert parsed.command == "addr"
    decoded = parse_addr_payload(parsed.payload)
    assert decoded[0].endpoint == "18.220.89.128:28444"
    assert Message.parse(pex_message(records).serialize()).command == "pex"


def test_home_bandwidth_mode_stays_under_target():
    from netcoin.bandwidth import relay_plan

    plan = relay_plan("home", peer_count=12, pending_inventory=8000)
    assert plan["under_500kbps_home_target"] is True
    assert plan["selected_outbound_peers"] == 6
    assert plan["compact_block_relay"] is True


def test_m3_source_files_and_public_node_map_exist():
    required = [
        "architecture/m3-decentralized-testnet.json",
        "tools/install_public_node.sh",
        "docker-compose.node.yml",
        "docs/M3_NODE_OPERATOR_GUIDE.md",
        "docs/M3_30_DAY_SOAK_REPORT.md",
        "docs/M3_TESTNET_SOFT_FORK_REHEARSAL.md",
        "docs/M3_MINING_POOL_REFERENCE.md",
        "api/nodes/map",
        "sites/nodes/index.html",
    ]
    for rel in required:
        assert (ROOT / rel).exists(), rel
    node_map = json.loads((ROOT / "api/nodes/map").read_text())
    assert node_map["schema"] == "netcoin-public-node-map-v1"
    assert "static-fallback" in node_map["source"]


def test_m3_readiness_gate_passes_source():
    proc = subprocess.run(
        [sys.executable, "tools/check_m3_readiness.py", "--out", "reports/m3_readiness_source_report.json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads((ROOT / "reports/m3_readiness_source_report.json").read_text())
    assert payload["ok"] is True
    assert payload["claim_level"] == "m3-source-complete-evidence-required"


def test_m3_release_candidate_runner_has_source_commands():
    proc = subprocess.run(
        [sys.executable, "tools/run_m3_release_candidate.py", "--profile", "source", "--dry-run", "--no-write"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert any("check_m3_readiness.py" in command for command in payload["commands"])
