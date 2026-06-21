"""Bitcoin-style P2P message framing for NetCoin.

NetCoin's easy-to-run node still exposes HTTP endpoints, but this module gives
it the binary network envelope Bitcoin uses conceptually: magic bytes, 12-byte
command names, payload length, checksum, and payload. It is used by CLI demos and
is ready to back a socket-based transport later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

from .crypto import double_sha256
from .params import P2P_MAGIC, PROTOCOL_VERSION


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


def version_message(start_height: int, user_agent: str = "/NetCoin:0.2.0/") -> Message:
    return Message(
        "version",
        json_payload({"version": PROTOCOL_VERSION, "user_agent": user_agent, "start_height": start_height}),
    )


def inv_message(kind: str, item_hash: str) -> Message:
    return Message("inv", json_payload({"inventory": [{"type": kind, "hash": item_hash}]}))


def getheaders_message(locator_hash: str) -> Message:
    return Message("getheaders", json_payload({"locator": locator_hash}))


def headers_message(headers: list[dict]) -> Message:
    return Message("headers", json_payload({"headers": headers}))
