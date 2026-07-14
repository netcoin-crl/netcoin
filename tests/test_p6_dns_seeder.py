from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path
from threading import Event, Thread

import pytest

from netcoin.peerdb import PeerDatabase
from netcoin.seeder import (
    DNSSeeder,
    DNSSeederConfig,
    build_dns_response,
    make_dns_query,
    parse_a_records,
    query_dns_seed,
    serve_dns,
)
from tools.run_localnet import Localnet, LocalnetConfig

ROOT = Path(__file__).resolve().parents[1]


def reserve_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def seed_db(path: Path) -> PeerDatabase:
    db = PeerDatabase(path)
    db.record_success("http://127.0.0.1:28444", best_height=5, user_agent="NetCoin:test")
    db.record_success("http://127.0.0.2:28444", best_height=6, user_agent="NetCoin:test")
    db.record_failure("http://127.0.0.3:28444", penalty=50, reason="bad peer")
    db.upsert_peer("http://seed.example:28444", anchor=True)
    return db


def test_dns_packet_builder_answers_a_records_from_filtered_ipv4_peers(tmp_path: Path):
    db = seed_db(tmp_path / "peers.sqlite")
    config = DNSSeederConfig(peer_db=tmp_path / "peers.sqlite", domain="seed.netcoin.local", max_answers=4, ttl=120)
    seeder = DNSSeeder(db, config)
    response = build_dns_response(
        make_dns_query("seed.netcoin.local"),
        seeder.select_answers(),
        ttl=config.ttl,
        allowed_domain=config.domain,
    )
    records = parse_a_records(response)
    assert records == ["127.0.0.1", "127.0.0.2"]
    assert "127.0.0.3" not in records
    assert seeder.status()["ops_ceiling"] == 6


def test_dns_seeder_rotates_answers_and_ignores_wrong_domain(tmp_path: Path):
    db = seed_db(tmp_path / "peers.sqlite")
    config = DNSSeederConfig(peer_db=tmp_path / "peers.sqlite", domain="seed.netcoin.local", max_answers=1)
    seeder = DNSSeeder(db, config)
    first = seeder.select_answers()
    second = seeder.select_answers()
    assert first != second
    wrong = build_dns_response(
        make_dns_query("other.netcoin.local"),
        ["127.0.0.1"],
        ttl=config.ttl,
        allowed_domain=config.domain,
    )
    assert parse_a_records(wrong) == []


def test_dns_seeder_serves_real_udp_query(tmp_path: Path):
    db = seed_db(tmp_path / "peers.sqlite")
    port = reserve_udp_port()
    config = DNSSeederConfig(
        peer_db=tmp_path / "peers.sqlite", host="127.0.0.1", port=port, domain="seed.netcoin.local"
    )
    seeder = DNSSeeder(db, config)
    stop = Event()
    thread = Thread(target=serve_dns, args=(seeder,), kwargs={"stop_event": stop}, daemon=True)
    thread.start()
    try:
        records = query_dns_seed("127.0.0.1", port, "seed.netcoin.local")
    finally:
        stop.set()
        thread.join(timeout=5)
    assert records[:2] == ["127.0.0.1", "127.0.0.2"]
    assert seeder.status()["queries"] >= 1


def test_dns_seeder_cli_is_wired():
    proc = subprocess.run(
        [sys.executable, "-m", "netcoin", "seeder", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--peer-db" in proc.stdout
    assert "--domain" in proc.stdout


@pytest.mark.localnet
def test_dns_seeder_answers_from_localnet_peer_database(tmp_path: Path):
    with Localnet(LocalnetConfig(nodes=3, root_dir=tmp_path / "localnet", startup_timeout=30)) as localnet:
        localnet.start_all(topology="line", sync_interval=0)
        db = PeerDatabase(tmp_path / "peers.sqlite")
        for node in localnet.nodes:
            db.record_success(node.url, best_height=localnet.node_info(node)["height"], user_agent="NetCoin:localnet")
        port = reserve_udp_port()
        config = DNSSeederConfig(
            peer_db=tmp_path / "peers.sqlite", host="127.0.0.1", port=port, domain="seed.netcoin.local"
        )
        seeder = DNSSeeder(db, config)
        stop = Event()
        thread = Thread(target=serve_dns, args=(seeder,), kwargs={"stop_event": stop}, daemon=True)
        thread.start()
        try:
            records = query_dns_seed("127.0.0.1", port, "seed.netcoin.local")
        finally:
            stop.set()
            thread.join(timeout=5)
            localnet.stop_all()
            localnet.assert_no_survivors()
    assert records == ["127.0.0.1"]
