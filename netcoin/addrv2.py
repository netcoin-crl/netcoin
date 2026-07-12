"""AddrV2-style peer-address records for decentralized NetCoin testnet.

This module is intentionally transport-neutral. It gives Python and Rust P2P
lanes a stable contract for peer address exchange without changing consensus.
The shape follows the spirit of Bitcoin AddrV2: advertise network id, service
bits, host, port, last-seen time, and source metadata, while keeping JSON as the
wire payload for NetCoin's current educational P2P frame layer.
"""

from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass, field
from typing import Any

ADDRV2_NETWORK_IPV4 = "ipv4"
ADDRV2_NETWORK_IPV6 = "ipv6"
ADDRV2_NETWORK_TORV3 = "torv3"
ADDRV2_NETWORK_DNS = "dns"
ADDRV2_SCHEMA = "netcoin-addrv2-v1"

SERVICE_NODE_NETWORK = "NODE_NETWORK"
SERVICE_NODE_BLOOM = "NODE_BLOOM"
SERVICE_NODE_COMPACT_FILTERS = "NODE_COMPACT_FILTERS"
SERVICE_NODE_WITNESS = "NODE_WITNESS"
SERVICE_NETCOIN_PEX = "NETCOIN_PEX"
SERVICE_NETCOIN_COMPACT_BLOCKS = "NETCOIN_COMPACT_BLOCKS"

DEFAULT_SERVICES = [SERVICE_NODE_NETWORK, SERVICE_NETCOIN_PEX, SERVICE_NETCOIN_COMPACT_BLOCKS]


class AddrV2Error(ValueError):
    """Raised when an AddrV2 record is not safe to relay."""


def network_id_for_host(host: str) -> str:
    """Return a stable AddrV2 network id for a host string."""
    text = str(host).strip().strip("[]").lower()
    if not text:
        raise AddrV2Error("host is required")
    if text.endswith(".onion"):
        return ADDRV2_NETWORK_TORV3
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return ADDRV2_NETWORK_DNS
    return ADDRV2_NETWORK_IPV4 if ip.version == 4 else ADDRV2_NETWORK_IPV6


def normalize_host(host: str) -> str:
    """Normalize a host without resolving DNS or touching the network."""
    text = str(host).strip().strip("[]")
    if not text:
        raise AddrV2Error("host is required")
    try:
        return ipaddress.ip_address(text).compressed
    except ValueError:
        return text.lower()


def diversity_key_for_host(host: str) -> str:
    """Return a coarse privacy-safe diversity bucket for node-map reporting."""
    normalized = normalize_host(host)
    try:
        ip = ipaddress.ip_address(normalized)
        if ip.version == 4:
            return str(ipaddress.ip_network(f"{ip}/24", strict=False))
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    except ValueError:
        labels = normalized.split(".")
        if normalized.endswith(".onion"):
            return "torv3"
        return ".".join(labels[-2:]) if len(labels) >= 2 else normalized


@dataclass(frozen=True)
class AddrV2Record:
    host: str
    port: int = 28444
    services: list[str] = field(default_factory=lambda: list(DEFAULT_SERVICES))
    last_seen: int = 0
    source: str = "pex"
    user_agent: str = ""
    best_height: int = 0
    operator: str = ""
    region: str = ""

    def __post_init__(self) -> None:
        if not 0 < int(self.port) <= 65535:
            raise AddrV2Error("port must be in range 1..65535")
        normalize_host(self.host)

    @property
    def network_id(self) -> str:
        return network_id_for_host(self.host)

    @property
    def diversity_key(self) -> str:
        return diversity_key_for_host(self.host)

    @property
    def endpoint(self) -> str:
        host = normalize_host(self.host)
        if ":" in host and self.network_id == ADDRV2_NETWORK_IPV6:
            return f"[{host}]:{int(self.port)}"
        return f"{host}:{int(self.port)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ADDRV2_SCHEMA,
            "network_id": self.network_id,
            "host": normalize_host(self.host),
            "port": int(self.port),
            "endpoint": self.endpoint,
            "services": sorted(
                {str(service) for service in (self.services or DEFAULT_SERVICES) if str(service).strip()}
            ),
            "last_seen": int(self.last_seen or time.time()),
            "source": self.source,
            "user_agent": self.user_agent,
            "best_height": int(self.best_height),
            "operator": self.operator,
            "region": self.region,
            "diversity_key": self.diversity_key,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AddrV2Record":
        host = payload.get("host") or payload.get("address") or payload.get("endpoint")
        port = int(payload.get("port") or 28444)
        if isinstance(host, str) and host.count(":") == 1 and not host.startswith("["):
            maybe_host, maybe_port = host.rsplit(":", 1)
            if maybe_port.isdigit():
                host = maybe_host
                port = int(maybe_port)
        if isinstance(host, str) and host.startswith("[") and "]:" in host:
            host_part, port_part = host.rsplit(":", 1)
            host = host_part.strip("[]")
            if port_part.isdigit():
                port = int(port_part)
        return cls(
            host=str(host),
            port=port,
            services=[str(item) for item in payload.get("services", DEFAULT_SERVICES)],
            last_seen=int(payload.get("last_seen") or payload.get("last_success") or 0),
            source=str(payload.get("source") or "pex"),
            user_agent=str(payload.get("user_agent") or ""),
            best_height=int(payload.get("best_height") or payload.get("height") or 0),
            operator=str(payload.get("operator") or ""),
            region=str(payload.get("region") or ""),
        )


def records_from_endpoints(endpoints: list[str], *, source: str = "manual") -> list[dict[str, Any]]:
    """Build AddrV2 dictionaries from host[:port] endpoint strings."""
    records = []
    for endpoint in endpoints:
        records.append(AddrV2Record.from_dict({"endpoint": endpoint, "source": source}).to_dict())
    return records


def addr_payload(records: list[AddrV2Record | dict[str, Any]]) -> bytes:
    """Serialize an addr/addrv2 payload for the JSON P2P frame layer."""
    import json

    normalized = []
    for record in records:
        normalized.append(
            record.to_dict() if isinstance(record, AddrV2Record) else AddrV2Record.from_dict(record).to_dict()
        )
    return json.dumps({"schema": ADDRV2_SCHEMA, "addresses": normalized}, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def parse_addr_payload(payload: bytes) -> list[AddrV2Record]:
    """Parse addr/addrv2 JSON payload bytes into validated records."""
    import json

    data = json.loads(payload or b"{}")
    return [AddrV2Record.from_dict(item) for item in data.get("addresses", [])]


def public_node_map(records: list[AddrV2Record | dict[str, Any]]) -> dict[str, Any]:
    """Produce a privacy-safe public node-map payload from AddrV2 records."""
    nodes = []
    groups: dict[str, int] = {}
    operators: dict[str, int] = {}
    for record in records:
        item = record.to_dict() if isinstance(record, AddrV2Record) else AddrV2Record.from_dict(record).to_dict()
        groups[item["diversity_key"]] = groups.get(item["diversity_key"], 0) + 1
        operator = item.get("operator") or "unknown"
        operators[operator] = operators.get(operator, 0) + 1
        nodes.append(
            {
                "endpoint": item["endpoint"],
                "network_id": item["network_id"],
                "services": item["services"],
                "best_height": item["best_height"],
                "region": item.get("region", ""),
                "operator": operator,
                "diversity_key": item["diversity_key"],
            }
        )
    return {
        "schema": "netcoin-public-node-map-v1",
        "node_count": len(nodes),
        "diversity_group_count": len(groups),
        "operator_count": len(operators),
        "groups": groups,
        "operators": operators,
        "nodes": nodes,
    }
