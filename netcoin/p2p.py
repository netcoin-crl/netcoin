"""Bitcoin-style P2P message framing for NetCoin.

NetCoin's easy-to-run node still exposes HTTP endpoints, but this module gives
it the binary network envelope Bitcoin uses conceptually: magic bytes, 12-byte
command names, payload length, checksum, and payload. It is used by CLI demos and
is ready to back a socket-based transport later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .crypto import double_sha256
from .params import NETWORK_NAME, NODE_VERSION, P2P_MAGIC, PROTOCOL_VERSION
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
    def parse(cls, data: bytes) -> "Message":
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


def json_payload(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json(message: Message) -> Dict[str, Any]:
    return json.loads(message.payload or b"{}")


def version_message(start_height: int, genesis_hash: str = "", user_agent: str = f"/NetCoin:{NODE_VERSION}/") -> Message:
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


def inv_message(items: List[Dict[str, str]]) -> Message:
    return Message("inv", json_payload({"inventory": list(items)}))


def getdata_message(items: List[Dict[str, str]]) -> Message:
    return Message("getdata", json_payload({"inventory": list(items)}))


def getheaders_message(locator_hash: str) -> Message:
    return Message("getheaders", json_payload({"locator": locator_hash}))


def headers_message(headers: List[Dict[str, Any]]) -> Message:
    return Message("headers", json_payload({"headers": headers}))


def block_message(block: Any) -> Message:
    return Message("block", block_to_binary(block))


def tx_message(tx: Any) -> Message:
    return Message("tx", tx_to_binary(tx))


def read_block_message(message: Message) -> Any:
    return block_from_binary(message.payload)


def read_tx_message(message: Message) -> Any:
    return tx_from_binary(message.payload)[0]


def handle_message(message: Message, chain: Optional[Any] = None) -> Optional[Message]:
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
        start = int(_json(message).get("start", 0))
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
    return None
