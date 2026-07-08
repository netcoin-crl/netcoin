"""Bitcoin-style P2P message framing for NetCoin.

NetCoin's easy-to-run node still exposes HTTP endpoints, but this module gives
it the binary network envelope Bitcoin uses conceptually: magic bytes, 12-byte
command names, payload length, checksum, and payload. It is used by CLI demos and
is ready to back a socket-based transport later.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from socketserver import BaseRequestHandler, ThreadingTCPServer
from typing import Any

from .crypto import double_sha256
from .params import DEFAULT_P2P_PORT, MAX_REQUEST_BODY_BYTES, NETWORK_NAME, NODE_VERSION, P2P_MAGIC, PROTOCOL_VERSION
from .serialization import block_from_binary, block_to_binary, tx_from_binary, tx_to_binary


class P2PError(ValueError):
    """Raised when a P2P frame is malformed."""


@dataclass(frozen=True)
class Message:
    command: str
    payload: bytes = b""

    def serialize(self) -> bytes:
        command_bytes = self.command.encode("ascii")
        if len(command_bytes) > 12:
            raise P2PError("P2P command is longer than 12 bytes")
        command_field = command_bytes + b"\x00" * (12 - len(command_bytes))
        checksum = double_sha256(self.payload)[:4]
        return P2P_MAGIC + command_field + len(self.payload).to_bytes(4, "little") + checksum + self.payload

    @classmethod
    def parse(cls, data: bytes) -> Message:
        if len(data) < 24:
            raise P2PError("message too short")
        if data[:4] != P2P_MAGIC:
            raise P2PError("message magic does not match NetCoin")
        command = data[4:16].rstrip(b"\x00").decode("ascii")
        length = int.from_bytes(data[16:20], "little")
        checksum = data[20:24]
        payload = data[24 : 24 + length]
        if len(payload) != length:
            raise P2PError("truncated payload")
        if double_sha256(payload)[:4] != checksum:
            raise P2PError("invalid payload checksum")
        return cls(command=command, payload=payload)


def _recv_exact(sock: socket.socket, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = sock.recv(length - len(chunks))
        if not chunk:
            raise P2PError("socket closed before full message was read")
        chunks.extend(chunk)
    return bytes(chunks)


def read_message(sock: socket.socket) -> Message:
    header = _recv_exact(sock, 24)
    if header[:4] != P2P_MAGIC:
        raise P2PError("message magic does not match NetCoin")
    length = int.from_bytes(header[16:20], "little")
    if length > MAX_REQUEST_BODY_BYTES:
        raise P2PError("P2P payload too large")
    payload = _recv_exact(sock, length)
    return Message.parse(header + payload)


def write_message(sock: socket.socket, message: Message) -> None:
    sock.sendall(message.serialize())


def request_message(host: str, port: int, message: Message, timeout: int = 10) -> Message | None:
    with socket.create_connection((host, int(port)), timeout=timeout) as sock:
        sock.settimeout(timeout)
        write_message(sock, message)
        try:
            return read_message(sock)
        except (TimeoutError, P2PError):
            return None


def json_payload(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json(message: Message) -> dict[str, Any]:
    return json.loads(message.payload or b"{}")


def version_message(
    start_height: int, genesis_hash: str = "", user_agent: str = f"/NetCoin:{NODE_VERSION}/"
) -> Message:
    return Message(
        "version",
        json_payload(
            {
                "version": PROTOCOL_VERSION,
                "network": NETWORK_NAME,
                "user_agent": user_agent,
                "start_height": start_height,
                "genesis_hash": genesis_hash,
            }
        ),
    )


def verack_message() -> Message:
    return Message("verack", b"")


def ping_message(nonce: int) -> Message:
    return Message("ping", json_payload({"nonce": int(nonce)}))


def pong_message(nonce: int) -> Message:
    return Message("pong", json_payload({"nonce": int(nonce)}))


def inv_message(items: list[dict[str, str]]) -> Message:
    return Message("inv", json_payload({"inventory": list(items)}))


def getdata_message(items: list[dict[str, str]]) -> Message:
    return Message("getdata", json_payload({"inventory": list(items)}))


def getheaders_message(locator_hash: str, start: int | None = None) -> Message:
    payload = {"locator": locator_hash}
    if start is not None:
        payload["start"] = int(start)
    return Message("getheaders", json_payload(payload))


def headers_message(headers: list[dict[str, Any]]) -> Message:
    return Message("headers", json_payload({"headers": headers}))


def block_message(block: Any) -> Message:
    return Message("block", block_to_binary(block))


def tx_message(tx: Any) -> Message:
    return Message("tx", tx_to_binary(tx))


def read_block_message(message: Message) -> Any:
    return block_from_binary(message.payload)


def read_tx_message(message: Message) -> Any:
    return tx_from_binary(message.payload)[0]


def handle_message(message: Message, chain: Any | None = None) -> Message | None:
    """Process an inbound message and return a response, Bitcoin-flow style:
    version->verack, ping->pong, getheaders->headers, inv->getdata, getdata->block/tx.
    Returns None when no response is warranted (e.g. verack, headers, block, tx)."""
    command = message.command
    if command == "version":
        return verack_message()
    if command == "ping":
        return pong_message(_json(message).get("nonce", 0))
    if command == "getheaders":
        if chain is None:
            return None
        payload = _json(message)
        # Backward-compatible default: no explicit start returns from genesis,
        # matching the original educational p2p-message behavior. Real sync
        # callers pass start=local_height+1.
        start = int(payload.get("start", 0))
        return headers_message(chain.headers(start, 2000))
    if command == "inv":
        return getdata_message(_json(message).get("inventory", []))
    if command == "getdata":
        if chain is None:
            return None
        for item in _json(message).get("inventory", []):
            item_hash, kind = item.get("hash", ""), item.get("type")
            if kind == "block":
                block = chain.get_block_by_hash(item_hash)
                if block is not None:
                    return block_message(block)
            elif kind == "tx":
                found = chain.get_transaction(item_hash)
                if found is not None:
                    return tx_message(found[0])
        return None
    if command == "block":
        if chain is None:
            return None
        block = read_block_message(message)
        chain.add_block(block)
        return inv_message([{"type": "block", "hash": block.hash()}])
    if command == "tx":
        if chain is None:
            return None
        tx = read_tx_message(message)
        txid = chain.add_mempool_transaction(tx)
        return inv_message([{"type": "tx", "hash": txid}])
    return None


def sync_headers_first(host: str, port: int, chain: Any, timeout: int = 10, limit: int = 2000) -> int:
    """Synchronize one TCP P2P peer using headers first and getdata block bodies.

    Returns the number of blocks accepted. This is intentionally small, but it
    exercises a real Bitcoin-shaped flow over the TCP transport: getheaders ->
    headers -> getdata(block) -> block.
    """
    locator = chain.tip_hash() if hasattr(chain, "tip_hash") else "0" * 64
    response = request_message(host, port, getheaders_message(locator, start=chain.height() + 1), timeout=timeout)
    if response is None or response.command != "headers":
        return 0
    remote_headers = json.loads(response.payload or b"{}").get("headers", [])
    if hasattr(chain, "validate_headers_from_tip"):
        remote_headers = chain.validate_headers_from_tip(remote_headers[:limit])
    accepted = 0
    for header in remote_headers[:limit]:
        block_hash = header.get("hash")
        if not block_hash:
            continue
        block_response = request_message(
            host, port, getdata_message([{"type": "block", "hash": block_hash}]), timeout=timeout
        )
        if block_response is None or block_response.command != "block":
            break
        block = read_block_message(block_response)
        chain.add_block(block)
        accepted += 1
    return accepted


class P2PRequestHandler(BaseRequestHandler):
    def handle(self) -> None:
        server = self.server  # type: ignore[assignment]
        try:
            message = read_message(self.request)
            response = handle_message(message, getattr(server, "chain", None))
            if response is not None:
                write_message(self.request, response)
        except Exception:
            # Socket peers should not crash the node. Full structured peer
            # scoring belongs in the HTTP node for now; the transport fails
            # closed by dropping malformed connections.
            return


class NetCoinP2PServer(ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], chain: Any):
        self.chain = chain
        super().__init__(server_address, P2PRequestHandler)


def run_p2p_server(data_dir: str, host: str = "127.0.0.1", port: int = DEFAULT_P2P_PORT) -> None:
    from .chain import Blockchain

    chain = Blockchain(data_dir=data_dir)
    server = NetCoinP2PServer((host, int(port)), chain)
    print(f"NetCoin P2P listening on {host}:{port}")
    print(f"height={chain.height()} tip={chain.tip_hash()}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


# ---------------------------------------------------------------------------
# Professional peer-management primitives
# ---------------------------------------------------------------------------


@dataclass
class PeerState:
    address: str
    direction: str = "outbound"  # inbound/outbound/anchor/feeler
    services: list[str] | None = None
    user_agent: str = ""
    protocol_version: int = PROTOCOL_VERSION
    best_height: int = 0
    score: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    last_seen: int = 0
    banned_until: int = 0
    discourage_until: int = 0
    disconnect_reason: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "direction": self.direction,
            "services": list(self.services or []),
            "user_agent": self.user_agent,
            "protocol_version": self.protocol_version,
            "best_height": self.best_height,
            "score": self.score,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "banned_until": self.banned_until,
            "discourage_until": self.discourage_until,
            "disconnect_reason": self.disconnect_reason,
        }


class PeerManager:
    """Small peer manager with scoring, diversity, ban, and relay-dedup hooks."""

    def __init__(self, *, max_per_prefix: int = 4, ban_score: int = 100, ban_seconds: int = 24 * 3600):
        self.max_per_prefix = int(max_per_prefix)
        self.ban_score = int(ban_score)
        self.ban_seconds = int(ban_seconds)
        self.peers: dict[str, PeerState] = {}
        self.inventory_seen: set[tuple[str, str]] = set()

    @staticmethod
    def _now() -> int:
        import time

        return int(time.time())

    @staticmethod
    def network_prefix(address: str) -> str:
        host = address.rsplit(":", 1)[0]
        parts = host.split(".")
        if len(parts) == 4 and all(p.isdigit() for p in parts):
            return ".".join(parts[:3]) + ".0/24"
        return host.split("%", 1)[0]

    def add_peer(
        self, address: str, *, direction: str = "outbound", services: list[str] | None = None, user_agent: str = ""
    ) -> PeerState:
        peer = self.peers.get(address)
        if peer is None:
            if not self.diversity_allows(address) and direction not in {"anchor", "inbound"}:
                raise P2PError("peer diversity limit reached for network prefix")
            peer = PeerState(
                address=address,
                direction=direction,
                services=services or [],
                user_agent=user_agent,
                last_seen=self._now(),
            )
            self.peers[address] = peer
        else:
            peer.direction = direction or peer.direction
            peer.services = services or peer.services
            peer.user_agent = user_agent or peer.user_agent
            peer.last_seen = self._now()
        return peer

    def diversity_allows(self, address: str) -> bool:
        prefix = self.network_prefix(address)
        count = sum(
            1 for p in self.peers.values() if self.network_prefix(p.address) == prefix and p.banned_until <= self._now()
        )
        return count < self.max_per_prefix

    def report_misbehavior(self, address: str, points: int, reason: str) -> PeerState:
        peer = self.peers.setdefault(address, PeerState(address=address, last_seen=self._now()))
        peer.score += int(points)
        peer.disconnect_reason = reason[:160]
        if peer.score >= self.ban_score:
            peer.banned_until = self._now() + self.ban_seconds
        elif peer.score >= self.ban_score // 2:
            peer.discourage_until = self._now() + min(self.ban_seconds, 3600)
        return peer

    def record_bandwidth(self, address: str, *, bytes_in: int = 0, bytes_out: int = 0) -> None:
        peer = self.peers.setdefault(address, PeerState(address=address, last_seen=self._now()))
        peer.bytes_in += max(0, int(bytes_in))
        peer.bytes_out += max(0, int(bytes_out))
        peer.last_seen = self._now()

    def should_relay_inventory(self, inv_type: str, inv_hash: str) -> bool:
        key = (str(inv_type), str(inv_hash).lower())
        if key in self.inventory_seen:
            return False
        self.inventory_seen.add(key)
        if len(self.inventory_seen) > 50_000:
            self.inventory_seen = set(list(self.inventory_seen)[-25_000:])
        return True

    def disconnect(self, address: str, reason: str) -> None:
        peer = self.peers.get(address)
        if peer:
            peer.disconnect_reason = reason[:160]

    def active_peers(self) -> list[dict[str, Any]]:
        now = self._now()
        return [p.public() for p in self.peers.values() if p.banned_until <= now]

    def banlist(self) -> list[dict[str, Any]]:
        now = self._now()
        return [p.public() for p in self.peers.values() if p.banned_until > now]

    def compatibility_check(
        self, address: str, version: int, network: str, genesis_hash: str, expected_genesis: str = ""
    ) -> tuple[bool, str]:
        if int(version) != PROTOCOL_VERSION:
            return False, f"protocol mismatch: peer={version} local={PROTOCOL_VERSION}"
        if network != NETWORK_NAME:
            return False, f"network mismatch: {network}"
        if expected_genesis and genesis_hash and genesis_hash != expected_genesis:
            return False, "genesis hash mismatch"
        self.add_peer(address)
        return True, "compatible"
