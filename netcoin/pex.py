"""Peer-exchange helpers for the decentralized NetCoin testnet milestone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .addrv2 import DEFAULT_SERVICES, AddrV2Record, public_node_map


@dataclass(frozen=True)
class PEXPolicy:
    max_records: int = 1000
    max_per_diversity_group: int = 4
    min_score: int = -10
    include_anchor_peers: bool = True


def _as_record(peer: dict[str, Any], source: str) -> AddrV2Record | None:
    host = peer.get("host") or peer.get("address") or peer.get("endpoint")
    if not host:
        return None
    try:
        return AddrV2Record(
            host=str(host),
            port=int(peer.get("port") or 28444),
            services=[str(item) for item in peer.get("services", [])] or list(DEFAULT_SERVICES),
            last_seen=int(peer.get("last_seen") or peer.get("last_success") or 0),
            source=source,
            user_agent=str(peer.get("user_agent") or ""),
            best_height=int(peer.get("best_height") or peer.get("height") or 0),
            operator=str(peer.get("operator") or ""),
            region=str(peer.get("region") or ""),
        )
    except Exception:
        return None


def select_pex_records(peers: Iterable[dict[str, Any]], *, policy: PEXPolicy | None = None) -> list[dict[str, Any]]:
    """Select a bounded, diversity-aware AddrV2 set for peer exchange."""
    active_policy = policy or PEXPolicy()
    selected = []
    groups: dict[str, int] = {}
    for peer in sorted(
        peers,
        key=lambda item: (
            int(item.get("anchor") or 0),
            int(item.get("score") or 0),
            int(item.get("last_success") or item.get("last_seen") or 0),
        ),
        reverse=True,
    ):
        if peer.get("banned") or int(peer.get("score") or 0) < active_policy.min_score:
            continue
        record = _as_record(peer, source="pex")
        if record is None:
            continue
        key = record.diversity_key
        if groups.get(key, 0) >= active_policy.max_per_diversity_group and not peer.get("anchor"):
            continue
        groups[key] = groups.get(key, 0) + 1
        selected.append(record.to_dict())
        if len(selected) >= active_policy.max_records:
            break
    return selected


def build_pex_response(peer_database: Any, *, limit: int = 1000) -> dict[str, Any]:
    """Build a public peer-exchange response from a PeerDatabase-like object."""
    if hasattr(peer_database, "candidates"):
        peers = peer_database.candidates(limit=limit, include_banned=False, max_per_group=1000)
    else:
        peers = list(peer_database)
    records = select_pex_records(peers, policy=PEXPolicy(max_records=limit))
    return {"schema": "netcoin-pex-v1", "count": len(records), "addresses": records}


def ingest_pex_records(peer_database: Any, records: Iterable[dict[str, Any]], *, source: str = "pex") -> dict[str, Any]:
    """Validate and add peer-exchange records into a PeerDatabase-like object."""
    accepted = 0
    rejected = 0
    for record_payload in records:
        try:
            record = AddrV2Record.from_dict(record_payload)
            if hasattr(peer_database, "upsert_peer"):
                peer_database.upsert_peer(
                    record.endpoint,
                    source=source,
                    user_agent=record.user_agent,
                    services=record.services,
                    best_height=record.best_height,
                )
            accepted += 1
        except Exception:
            rejected += 1
    return {"schema": "netcoin-pex-ingest-v1", "accepted": accepted, "rejected": rejected}


def node_map_from_peer_database(peer_database: Any) -> dict[str, Any]:
    """Export a public node-map payload from a PeerDatabase-like object."""
    if hasattr(peer_database, "candidates"):
        peers = peer_database.candidates(limit=10000, include_banned=False, max_per_group=10000)
    else:
        peers = list(peer_database)
    records = [record for record in (_as_record(peer, source="node-map") for peer in peers) if record is not None]
    return public_node_map(records)
