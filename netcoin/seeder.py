"""Stdlib DNS seeder for NetCoin peer discovery."""

from __future__ import annotations

import argparse
import ipaddress
import random
import socket
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Any

from .peerdb import PeerDatabase

DNS_SEEDER_SCHEMA = "netcoin-dns-seeder-v1"
QTYPE_A = 1
QCLASS_IN = 1


class DNSSeederError(ValueError):
    """Raised when a DNS query or seeder configuration is invalid."""


@dataclass
class DNSQuestion:
    qname: str
    qtype: int
    qclass: int
    end_offset: int


@dataclass
class DNSSeederConfig:
    peer_db: Path
    host: str = "127.0.0.1"
    port: int = 5353
    ttl: int = 300
    max_answers: int = 8
    domain: str = "seed.netcoin.local"
    min_score: int = -10
    max_peer_age_seconds: int = 7 * 24 * 3600


@dataclass
class DNSSeeder:
    peer_db: PeerDatabase
    config: DNSSeederConfig
    query_count: int = 0
    answer_count: int = 0
    last_error: str = ""
    _rotation: int = 0
    _rng: random.Random = field(default_factory=lambda: random.Random(20260713))

    def eligible_ipv4_peers(self) -> list[str]:
        now = int(time.time())
        candidates = self.peer_db.candidates(limit=1000, include_banned=False, max_per_group=1000)
        hosts: list[str] = []
        for peer in candidates:
            try:
                if int(peer.get("score") or 0) < int(self.config.min_score):
                    continue
                last_success = int(peer.get("last_success") or 0)
                anchor = bool(peer.get("anchor"))
                if not anchor and last_success and now - last_success > int(self.config.max_peer_age_seconds):
                    continue
                host = str(peer.get("host") or "")
                ip = ipaddress.ip_address(host)
                if ip.version != 4:
                    continue
                hosts.append(ip.compressed)
            except (TypeError, ValueError):
                continue
        return hosts

    def select_answers(self) -> list[str]:
        peers = self.eligible_ipv4_peers()
        if not peers:
            return []
        peers = sorted(dict.fromkeys(peers))
        offset = self._rotation % len(peers)
        self._rotation += 1
        rotated = peers[offset:] + peers[:offset]
        return rotated[: max(0, int(self.config.max_answers))]

    def handle_packet(self, data: bytes) -> bytes:
        self.query_count += 1
        try:
            response = build_dns_response(
                data, self.select_answers(), ttl=self.config.ttl, allowed_domain=self.config.domain
            )
            self.answer_count += parse_answer_count(response)
            return response
        except Exception as exc:
            self.last_error = str(exc)
            return build_error_response(data, rcode=1)

    def status(self) -> dict[str, Any]:
        return {
            "schema": DNS_SEEDER_SCHEMA,
            "domain": self.config.domain,
            "host": self.config.host,
            "port": self.config.port,
            "ttl": self.config.ttl,
            "max_answers": self.config.max_answers,
            "eligible_ipv4_peers": len(self.eligible_ipv4_peers()),
            "queries": self.query_count,
            "answers": self.answer_count,
            "last_error": self.last_error,
            "software_ready": True,
            "ops_ceiling": 6,
            "ops_note": "Independent domains and operators are still required for operational maturity.",
        }


def parse_question(packet: bytes) -> DNSQuestion:
    if len(packet) < 12:
        raise DNSSeederError("DNS packet too short")
    qdcount = struct.unpack("!H", packet[4:6])[0]
    if qdcount != 1:
        raise DNSSeederError("exactly one DNS question is supported")
    labels: list[str] = []
    offset = 12
    while True:
        if offset >= len(packet):
            raise DNSSeederError("truncated qname")
        length = packet[offset]
        offset += 1
        if length == 0:
            break
        if length & 0xC0:
            raise DNSSeederError("compressed qname is not supported in questions")
        if offset + length > len(packet):
            raise DNSSeederError("truncated qname label")
        labels.append(packet[offset : offset + length].decode("ascii").lower())
        offset += length
    if offset + 4 > len(packet):
        raise DNSSeederError("truncated DNS question")
    qtype, qclass = struct.unpack("!HH", packet[offset : offset + 4])
    return DNSQuestion(".".join(labels), qtype, qclass, offset + 4)


def encode_qname(name: str) -> bytes:
    labels = [label for label in name.rstrip(".").split(".") if label]
    if not labels:
        return b"\x00"
    out = b""
    for label in labels:
        raw = label.encode("ascii")
        if len(raw) > 63:
            raise DNSSeederError("DNS label too long")
        out += bytes([len(raw)]) + raw
    return out + b"\x00"


def make_dns_query(name: str, *, qtype: int = QTYPE_A, query_id: int = 0x1234) -> bytes:
    header = struct.pack("!HHHHHH", query_id, 0x0100, 1, 0, 0, 0)
    return header + encode_qname(name) + struct.pack("!HH", qtype, QCLASS_IN)


def build_dns_response(packet: bytes, answers: list[str], *, ttl: int, allowed_domain: str) -> bytes:
    question = parse_question(packet)
    txid = packet[:2]
    question_wire = packet[12 : question.end_offset]
    allowed = question.qname.rstrip(".") == allowed_domain.rstrip(".").lower()
    answer_ips = answers if allowed and question.qtype == QTYPE_A and question.qclass == QCLASS_IN else []
    flags = 0x8180
    header = txid + struct.pack("!HHHHH", flags, 1, len(answer_ips), 0, 0)
    records = b""
    for ip_text in answer_ips:
        ip = ipaddress.ip_address(ip_text)
        records += b"\xc0\x0c"
        records += struct.pack("!HHIH", QTYPE_A, QCLASS_IN, max(0, int(ttl)), 4)
        records += ip.packed
    return header + question_wire + records


def build_error_response(packet: bytes, *, rcode: int = 1) -> bytes:
    txid = packet[:2] if len(packet) >= 2 else b"\x00\x00"
    return txid + struct.pack("!HHHHH", 0x8180 | (rcode & 0xF), 0, 0, 0, 0)


def parse_answer_count(packet: bytes) -> int:
    if len(packet) < 8:
        return 0
    return struct.unpack("!H", packet[6:8])[0]


def parse_a_records(packet: bytes) -> list[str]:
    question = parse_question(packet)
    ancount = parse_answer_count(packet)
    offset = question.end_offset
    records: list[str] = []
    for _ in range(ancount):
        if offset + 12 > len(packet):
            raise DNSSeederError("truncated answer")
        if packet[offset] & 0xC0:
            offset += 2
        else:
            while offset < len(packet) and packet[offset] != 0:
                offset += 1 + packet[offset]
            offset += 1
        rtype, rclass, _ttl, rdlength = struct.unpack("!HHIH", packet[offset : offset + 10])
        offset += 10
        rdata = packet[offset : offset + rdlength]
        offset += rdlength
        if rtype == QTYPE_A and rclass == QCLASS_IN and rdlength == 4:
            records.append(str(ipaddress.ip_address(rdata)))
    return records


def query_dns_seed(host: str, port: int, name: str, *, timeout: float = 2.0) -> list[str]:
    query = make_dns_query(name)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(query, (host, int(port)))
        data, _addr = sock.recvfrom(2048)
    return parse_a_records(data)


def serve_dns(seeder: DNSSeeder, *, stop_event: Event | None = None) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((seeder.config.host, int(seeder.config.port)))
        sock.settimeout(0.25)
        while stop_event is None or not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(2048)
            except TimeoutError:
                continue
            response = seeder.handle_packet(data)
            sock.sendto(response, addr)


def run_dns_seeder(config: DNSSeederConfig, *, stop_event: Event | None = None) -> None:
    serve_dns(DNSSeeder(PeerDatabase(config.peer_db), config), stop_event=stop_event)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a NetCoin DNS seed UDP responder")
    parser.add_argument("--peer-db", type=Path, required=True, help="PeerDatabase sqlite path")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5353)
    parser.add_argument("--domain", default="seed.netcoin.local")
    parser.add_argument("--ttl", type=int, default=300)
    parser.add_argument("--max-answers", type=int, default=8)
    parser.add_argument("--min-score", type=int, default=-10)
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> DNSSeederConfig:
    return DNSSeederConfig(
        peer_db=args.peer_db,
        host=args.host,
        port=args.port,
        domain=args.domain,
        ttl=args.ttl,
        max_answers=args.max_answers,
        min_score=args.min_score,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = config_from_args(args)
    run_dns_seeder(config)
    return 0
