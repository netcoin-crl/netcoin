"""HTTP peer-to-peer node for NetCoin.

The transport is intentionally simple JSON over HTTP, but the exposed concepts are
Bitcoin-like: peer discovery, headers-first sync shape, block/transaction relay,
compact block summaries, mempool exchange, block templates, and orphan handling.
"""

from __future__ import annotations

import hmac
import json
import os
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .apps import AppError, AppStore, route_app_get, route_app_post
from .block import Block
from .chain import Blockchain
from .compact import CompactBlock, CompactBlockError, compact_missing_payload, make_compact_block, missing_transactions, reconstruct_compact_block
from .logsetup import emit
from .params import (
    DEFAULT_NODE_PORT,
    DEFAULT_P2P_PORT,
    MAX_REQUEST_BODY_BYTES,
    NETWORK_NAME,
    NODE_VERSION,
    PROTOCOL_VERSION,
    USER_AGENT,
)
from .tx import Transaction


class NodeError(ValueError):
    """Raised when node-level operations fail."""


class RateLimiter:
    """Simple per-key sliding-window rate limiter (per IP + endpoint)."""

    def __init__(self, max_requests: int = 240, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[Any, List[float]] = {}

    def allow(self, key: Any) -> bool:
        if self.max_requests <= 0:
            return True
        now = time.time()
        cutoff = now - self.window_seconds
        bucket = [t for t in self._hits.get(key, []) if t >= cutoff]
        if len(bucket) >= self.max_requests:
            self._hits[key] = bucket
            return False
        bucket.append(now)
        self._hits[key] = bucket
        return True


def client_ip_from_headers(headers: Any, client_address: Any, *, trust_proxy_headers: bool = False) -> str:
    """Return the request client IP, optionally honoring trusted proxy headers.

    Public nodes must not trust X-Forwarded-For by default: a direct internet
    client can spoof it and bypass per-IP throttles. Operators behind a trusted
    reverse proxy may opt in so rate limits key on the original client address.
    """
    if trust_proxy_headers:
        forwarded = headers.get("X-Forwarded-For", "")
        if forwarded:
            first = forwarded.split(",", 1)[0].strip()
            if first:
                return first
    if client_address:
        return str(client_address[0])
    return "unknown"


@dataclass
class RelayItem:
    kind: str
    path: str
    inventory_id: str
    payload: Dict[str, Any]
    peers: List[str]
    attempts: int = 0
    next_try_at: float = 0.0
    created_at: float = field(default_factory=time.time)


class NetCoinNode:
    def __init__(
        self,
        chain: Blockchain,
        peers: Optional[Iterable[str]] = None,
        peers_path: Optional[str] = None,
        persist: bool = True,
        self_url: Optional[str] = None,
        max_peers: int = 128,
        rate_limit_per_min: int = 240,
        request_timeout: int = 5,
        request_retries: int = 1,
        ban_threshold: int = -5,
        ban_ttl_seconds: int = 3600,
    ):
        self.chain = chain
        self.peers = set()
        self.orphans: Dict[str, Block] = {}
        self.persist = persist
        self.max_peers = max_peers
        self.self_url = self._normalize_peer(self_url) if self_url else None
        # Peer reputation: scores adjust on good/bad behavior; reaching the ban
        # threshold bans the peer. Bans persist to banned_peers.json.
        self.peer_scores: Dict[str, int] = {}
        self.banned: set = set()
        self.ban_threshold = ban_threshold
        # Bans expire after this many seconds (0 = permanent) so a transient
        # outage doesn't partition a peer forever; ban_times records when each
        # ban started.
        self.ban_ttl_seconds = max(0, ban_ttl_seconds)
        self.ban_times: Dict[str, float] = {}
        # Trusted peers (configured via --peer) are never auto-banned and are
        # auto-unbanned at startup, so a routine restart/blip can't permanently
        # self-partition our own seeds.
        self.trusted_peers: set = set()
        for _p in peers or []:
            try:
                self.trusted_peers.add(self._normalize_peer(_p))
            except NodeError:
                continue
        self.banned_path = Path(chain.data_dir) / "banned_peers.json"
        # Per-endpoint, per-IP rate limiting and configurable peer-fetch behavior.
        self.rate_limiter = RateLimiter(max_requests=rate_limit_per_min, window_seconds=60)
        self.request_timeout = request_timeout
        self.request_retries = max(0, request_retries)
        # Bounded event log for block-propagation visibility.
        self.event_log: List[Dict[str, Any]] = []
        self.max_events = 500
        # Bounded memory of recently relayed block hashes so a block is not
        # re-broadcast in a relay loop when peers echo it back.
        self._broadcast_seen: List[str] = []
        self._broadcast_seen_set: set[str] = set()
        # Bounded inventory cache + relay queue. Inventory keeps echoed tx/block
        # announcements from being re-enqueued repeatedly; failed deliveries stay
        # queued with exponential backoff for a later drain.
        self._relay_inventory: List[str] = []
        self._relay_inventory_set: set[str] = set()
        self._relay_queue: List[RelayItem] = []
        self.max_relay_inventory = 2000
        self.max_relay_queue = 1000
        self.max_node_orphans = 200
        self.relay_max_attempts = 3
        self.relay_backoff_seconds = 2.0
        self.started_at = time.time()
        # Tiny in-process response cache for read-heavy public endpoints. This
        # protects the Python node from repeated explorer/status refreshes without
        # changing consensus state or write endpoints.
        self._response_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self.peers_path = Path(peers_path) if peers_path else (Path(chain.data_dir) / "peers.json")
        self._load_banned()
        # Recover trusted peers that a previous run auto-banned during a transient
        # outage, then reconnect: reload discovered peers and merge in --peer ones.
        self._unban_trusted()
        self._load_peers()
        for peer in peers or []:
            self.add_peer(peer)

    def _normalize_peer(self, peer: str) -> str:
        peer = peer.rstrip("/")
        if not peer.startswith(("http://", "https://")):
            raise NodeError("peer must start with http:// or https://")
        return peer

    def add_peer(self, peer: str) -> None:
        normalized = self._normalize_peer(peer)
        # Never add ourselves or a banned peer, and respect the peer cap so gossip
        # cannot grow the peer set without bound (a simple DoS guard).
        if self.self_url and normalized == self.self_url:
            return
        # A trusted (configured) peer is always allowed; otherwise honor bans
        # (after expiring any that have aged out).
        if normalized not in self.trusted_peers:
            self._prune_expired_bans()
            if normalized in self.banned:
                return
        if normalized not in self.peers and len(self.peers) >= self.max_peers:
            return
        self.peers.add(normalized)
        self._save_peers()

    def _load_banned(self) -> None:
        try:
            data = json.loads(self.banned_path.read_text())
        except (FileNotFoundError, ValueError):
            return
        ban_times = data.get("ban_times", {}) if isinstance(data, dict) else {}
        now = time.time()
        for peer in data.get("banned", []):
            try:
                normalized = self._normalize_peer(str(peer))
            except NodeError:
                continue
            self.banned.add(normalized)
            # Old files have no timestamps; treat those bans as starting now so
            # they still expire under the TTL instead of lingering forever.
            try:
                self.ban_times[normalized] = float(ban_times.get(peer, now))
            except (TypeError, ValueError):
                self.ban_times[normalized] = now
        self._prune_expired_bans()

    def _save_banned(self) -> None:
        if not self.persist:
            return
        try:
            self.banned_path.parent.mkdir(parents=True, exist_ok=True)
            self.banned_path.write_text(json.dumps(
                {"banned": sorted(self.banned),
                 "ban_times": {p: self.ban_times[p] for p in sorted(self.banned) if p in self.ban_times}},
                indent=2, sort_keys=True))
        except OSError:
            pass

    def _prune_expired_bans(self) -> bool:
        """Drop bans older than ban_ttl_seconds (0 = permanent). Returns True if any expired."""
        if self.ban_ttl_seconds <= 0:
            return False
        now = time.time()
        expired = [p for p in self.banned if now - self.ban_times.get(p, now) > self.ban_ttl_seconds]
        for p in expired:
            self.banned.discard(p)
            self.ban_times.pop(p, None)
        if expired:
            self._save_banned()
        return bool(expired)

    def _unban_trusted(self) -> None:
        """Clear any ban on a configured/trusted peer so our own seeds recover."""
        changed = False
        for tp in self.trusted_peers:
            if tp in self.banned:
                self.banned.discard(tp)
                self.ban_times.pop(tp, None)
                self.peer_scores.pop(tp, None)
                changed = True
        if changed:
            self._save_banned()

    def is_banned(self, peer: str) -> bool:
        try:
            normalized = self._normalize_peer(peer)
        except NodeError:
            return False
        self._prune_expired_bans()
        return normalized in self.banned

    def ban_peer(self, peer: str, reason: str = "") -> None:
        normalized = self._normalize_peer(peer)
        # Trusted (configured) peers are never banned — a flaky restart of our own
        # seed must not permanently partition the network.
        if normalized in self.trusted_peers:
            return
        self.banned.add(normalized)
        self.ban_times[normalized] = time.time()
        self.peers.discard(normalized)
        self.peer_scores.pop(normalized, None)
        self._save_peers()
        self._save_banned()
        self.log_event("peer_banned", peer=normalized, reason=reason)

    def unban_peer(self, peer: str) -> bool:
        normalized = self._normalize_peer(peer)
        existed = normalized in self.banned
        self.banned.discard(normalized)
        self.ban_times.pop(normalized, None)
        if existed:
            self._save_banned()
        return existed

    def score_peer(self, peer: str, delta: int, reason: str = "") -> int:
        """Adjust a peer's reputation; auto-ban when it hits the threshold."""
        try:
            normalized = self._normalize_peer(peer)
        except NodeError:
            return 0
        score = self.peer_scores.get(normalized, 0) + delta
        self.peer_scores[normalized] = score
        # Scores still track reputation for visibility, but a trusted (configured)
        # peer is never auto-banned — transient failures must not partition us.
        if score <= self.ban_threshold and normalized not in self.trusted_peers:
            self.ban_peer(normalized, reason=reason or "score below threshold")
        return score

    def discover_peers(self) -> int:
        """Gossip pull: ask known peers for their peer lists and merge new ones."""
        learned = 0
        for peer in list(self.peers):
            try:
                data = self.fetch_json(f"{peer}/peers")
            except Exception:
                continue
            for candidate in data.get("peers", []):
                try:
                    normalized = self._normalize_peer(str(candidate))
                except NodeError:
                    continue
                if normalized == self.self_url or normalized in self.peers:
                    continue
                before = len(self.peers)
                self.add_peer(normalized)
                if len(self.peers) > before:
                    learned += 1
        return learned

    def announce_self(self) -> int:
        """Gossip push: tell known peers our advertised URL so they can dial back."""
        if not self.self_url:
            return 0
        delivered = 0
        for peer in list(self.peers):
            try:
                self.post_json(f"{peer}/peers", {"peers": [self.self_url]})
                delivered += 1
            except Exception:
                continue
        return delivered

    def bootstrap(self) -> Dict[str, int]:
        """Announce ourselves, learn new peers, then sync chains."""
        announced = self.announce_self()
        learned = self.discover_peers()
        adopted = self.sync_all()
        return {"announced": announced, "learned": learned, "adopted_chains": adopted}

    def start_background_sync(self, interval_seconds: int) -> tuple[Event, Thread]:
        """Start a lightweight recurring peer discovery + sync loop.

        Returns a stop event and thread so tests and embedding callers can shut
        it down cleanly. An interval <= 0 is intentionally invalid here; callers
        should simply not start the loop in that case.
        """
        interval = int(interval_seconds)
        if interval <= 0:
            raise NodeError("background sync interval must be positive")

        stop = Event()

        def loop() -> None:
            while not stop.wait(interval):
                try:
                    self.bootstrap()
                    self.log_event("background_sync", ok=True)
                except Exception as exc:
                    self.log_event("background_sync", ok=False, reason=str(exc))

        thread = Thread(target=loop, name="netcoin-background-sync", daemon=True)
        thread.start()
        return stop, thread

    def _load_peers(self) -> None:
        if not self.persist:
            return
        try:
            data = json.loads(self.peers_path.read_text())
        except (FileNotFoundError, ValueError):
            return
        for peer in data.get("peers", []):
            try:
                self.peers.add(self._normalize_peer(str(peer)))
            except NodeError:
                continue

    def _save_peers(self) -> None:
        if not self.persist:
            return
        try:
            self.peers_path.parent.mkdir(parents=True, exist_ok=True)
            self.peers_path.write_text(json.dumps({"peers": sorted(self.peers)}, indent=2, sort_keys=True))
        except OSError:
            pass

    SERVICES = ["network", "headers", "compact-blocks", "mempool", "block-template", "explorer-api", "compact-filters"]

    def uptime_seconds(self) -> int:
        return int(time.time() - self.started_at)

    def genesis_hash(self) -> str:
        return self.chain.chain[0].hash()

    def info(self) -> Dict[str, Any]:
        data = self.chain.chain_info()
        # Version-handshake fields let peers check compatibility (genesis, network,
        # protocol) before trusting each other.
        data.update(
            {
                "protocol_version": PROTOCOL_VERSION,
                "version": NODE_VERSION,
                "user_agent": USER_AGENT,
                "network": NETWORK_NAME,
                "genesis_hash": self.genesis_hash(),
                "uptime_seconds": self.uptime_seconds(),
                "peers": sorted(self.peers),
                "banned": len(self.banned),
                "orphans": len(self.orphans),
                "services": self.SERVICES,
            }
        )
        return data

    def health(self) -> Dict[str, Any]:
        chain_info = self.chain.chain_info()
        return {
            "ok": True,
            "version": NODE_VERSION,
            "network": NETWORK_NAME,
            "protocol_version": PROTOCOL_VERSION,
            "genesis_hash": self.genesis_hash(),
            "height": chain_info["height"],
            "tip_hash": chain_info["tip_hash"],
            "mempool": chain_info["mempool_transactions"],
            "peers": len(self.peers),
            "orphans": len(self.orphans),
            "relay_queue": len(self._relay_queue),
            "uptime_seconds": self.uptime_seconds(),
            "services": self.SERVICES,
        }

    def cached_response(self, key: str, ttl_seconds: float, builder: Any) -> Dict[str, Any]:
        now = time.time()
        cached = self._response_cache.get(key)
        if cached and cached[0] >= now:
            return cached[1]
        payload = builder()
        self._response_cache[key] = (now + max(0.0, ttl_seconds), payload)
        return payload

    def invalidate_read_cache(self) -> None:
        self._response_cache.clear()

    def metrics_text(self) -> str:
        """Prometheus text-exposition-format metrics."""
        info = self.chain.chain_info()
        lines = [
            "# HELP netcoin_block_height Current best block height.",
            "# TYPE netcoin_block_height gauge",
            f"netcoin_block_height {info['height']}",
            "# HELP netcoin_mempool_transactions Transactions in the mempool.",
            "# TYPE netcoin_mempool_transactions gauge",
            f"netcoin_mempool_transactions {info['mempool_transactions']}",
            "# HELP netcoin_peers Connected/known peers.",
            "# TYPE netcoin_peers gauge",
            f"netcoin_peers {len(self.peers)}",
            "# HELP netcoin_banned_peers Banned peers.",
            "# TYPE netcoin_banned_peers gauge",
            f"netcoin_banned_peers {len(self.banned)}",
            "# HELP netcoin_orphan_candidates Stored off-tip blocks.",
            "# TYPE netcoin_orphan_candidates gauge",
            f"netcoin_orphan_candidates {info['orphan_candidates']}",
            "# HELP netcoin_relay_queue_items Pending relay queue items.",
            "# TYPE netcoin_relay_queue_items gauge",
            f"netcoin_relay_queue_items {len(self._relay_queue)}",
            "# HELP netcoin_cumulative_work Cumulative chain work.",
            "# TYPE netcoin_cumulative_work gauge",
            f"netcoin_cumulative_work {info['cumulative_work']}",
            "# HELP netcoin_uptime_seconds Node uptime in seconds.",
            "# TYPE netcoin_uptime_seconds counter",
            f"netcoin_uptime_seconds {self.uptime_seconds()}",
        ]
        return "\n".join(lines) + "\n"

    def log_event(self, kind: str, **fields: Any) -> None:
        """Record a propagation/lifecycle event in a bounded in-memory log, and
        emit a structured JSON log line when NETCOIN_LOG_JSON is enabled."""
        event = {"t": round(time.time(), 3), "event": kind, **fields}
        self.event_log.append(event)
        if len(self.event_log) > self.max_events:
            del self.event_log[: len(self.event_log) - self.max_events]
        emit(kind, component="node", **fields)

    def recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.event_log[-limit:][::-1]

    def fetch_json(self, url: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        timeout = self.request_timeout if timeout is None else timeout
        last_exc: Optional[Exception] = None
        for attempt in range(self.request_retries + 1):
            try:
                with urlopen(url, timeout=timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as exc:  # retry transient network failures
                last_exc = exc
        raise last_exc if last_exc else NodeError("fetch failed")

    def post_json(self, url: str, payload: Dict[str, Any], timeout: Optional[int] = None) -> Dict[str, Any]:
        timeout = self.request_timeout if timeout is None else timeout
        body = json.dumps(payload).encode("utf-8")
        last_exc: Optional[Exception] = None
        for attempt in range(self.request_retries + 1):
            try:
                request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request, timeout=timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as exc:
                last_exc = exc
        raise last_exc if last_exc else NodeError("post failed")

    def compatible_peer(self, remote: Dict[str, Any]) -> bool:
        """Reject peers on a different genesis or network before syncing from them.

        Older peers may not report genesis/network; only reject on a clear mismatch."""
        remote_genesis = remote.get("genesis_hash")
        if remote_genesis and remote_genesis != self.genesis_hash():
            return False
        remote_network = remote.get("network")
        if remote_network and remote_network != NETWORK_NAME:
            return False
        remote_protocol = remote.get("protocol_version")
        if remote_protocol is not None and int(remote_protocol) != PROTOCOL_VERSION:
            return False
        return True

    def sync_from_peer(self, peer: str) -> bool:
        """Synchronize from a peer using headers first, then block bodies by hash.

        This keeps the old /chain fallback for compatibility, but the primary path
        now validates a header segment before downloading each missing block.
        """
        peer = peer.rstrip("/")
        remote = self.fetch_json(f"{peer}/info").get("node", {})
        if not self.compatible_peer(remote):
            self.score_peer(peer, -2, reason="incompatible peer")
            return False
        remote_height = int(remote.get("height", 0))
        if remote_height <= self.chain.height():
            return False

        start = self.chain.height() + 1
        try:
            data = self.fetch_json(f"{peer}/headers?start={start}&limit=2000")
            headers = data.get("headers", [])
            self.chain.validate_headers_from_tip(headers)
            adopted = False
            for header in headers:
                block_hash = header["hash"]
                block_data = self.fetch_json(f"{peer}/block/{block_hash}")
                block = Block.from_dict(block_data)
                self.chain.add_block(block)
                adopted = True
            if adopted:
                self.log_event("headers_first_sync", peer=peer, blocks=len(headers), height=self.chain.height())
                return True
        except Exception as exc:
            self.log_event("headers_first_sync_fallback", peer=peer, reason=str(exc))

        # Compatibility fallback for older NetCoin nodes. Fetch pages from peers
        # that support bounded /chain responses; old peers may ignore the query and
        # return their full chain once.
        blocks_payload: List[Dict[str, Any]] = []
        start = 0
        limit = 2000
        while True:
            data = self.fetch_json(f"{peer}/chain?start={start}&limit={limit}")
            page_blocks = data.get("blocks", [])
            blocks_payload.extend(page_blocks)
            if not data.get("has_next"):
                break
            start = int(data.get("next_start", start + len(page_blocks)))
            if not page_blocks:
                break
        blocks = self.chain.import_chain_data({"blocks": blocks_payload})
        return self.chain.replace_chain(blocks)

    def _looks_like_orphan_candidate(self, block: Block, reason: str) -> bool:
        """Only keep rejected blocks in the node orphan queue when they plausibly
        need a missing parent. Malformed/invalid blocks should not consume memory."""
        if "does not connect" not in reason and "previous hash" not in reason:
            return False
        if self.chain.block_by_hash(block.hash()) is not None:
            return False
        if block.header.height <= self.chain.height():
            return False
        return True

    def remember_node_orphan(self, block: Block) -> None:
        self.orphans[block.hash()] = block
        while len(self.orphans) > self.max_node_orphans:
            oldest = next(iter(self.orphans))
            del self.orphans[oldest]

    def sync_all(self) -> int:
        adopted = 0
        for peer in list(self.peers):
            try:
                if self.sync_from_peer(peer):
                    adopted += 1
                self.score_peer(peer, 1)  # reachable + compatible
            except Exception:
                self.score_peer(peer, -1, reason="sync failure")  # unreachable/bad
                continue
        return adopted

    def sync_over_p2p(self, host: str, port: int) -> int:
        """Sync from a peer over the binary TCP P2P transport (getheaders ->
        headers -> getdata(block) -> block). Returns the number of blocks
        accepted; 0 on any failure so the caller can fall back to HTTP."""
        from .p2p import sync_headers_first

        try:
            return sync_headers_first(host, int(port), self.chain)
        except Exception:
            return 0

    def accept_block(self, block: Block) -> str:
        self.log_event("block_received", hash=block.hash(), height=block.header.height)
        try:
            block_hash = self.chain.add_block(block)
        except Exception as exc:
            reason = str(exc)
            if self._looks_like_orphan_candidate(block, reason):
                self.remember_node_orphan(block)
            self.log_event("block_rejected", hash=block.hash(), reason=reason)
            self.sync_all()
            raise
        self.log_event("block_accepted", hash=block_hash, height=self.chain.height())
        progressed = True
        while progressed:
            progressed = False
            for orphan_hash, orphan in list(self.orphans.items()):
                if orphan.header.previous_hash == self.chain.tip_hash():
                    try:
                        self.chain.add_block(orphan)
                        del self.orphans[orphan_hash]
                        self.log_event("orphan_connected", hash=orphan_hash, height=self.chain.height())
                        progressed = True
                    except Exception:
                        pass
        return block_hash

    def broadcast_transaction(self, tx: Transaction) -> int:
        payload = tx.to_dict(include_scripts=True, include_witness=True)
        txid = tx.txid()
        if not self.enqueue_relay("tx", "/tx", txid, payload):
            return 0
        return self.drain_relay_queue()

    def _remember_inventory(self, inventory_key: str) -> bool:
        """Record an inventory key. Returns False if it was already seen."""
        if inventory_key in self._relay_inventory_set:
            return False
        self._relay_inventory_set.add(inventory_key)
        self._relay_inventory.append(inventory_key)
        if len(self._relay_inventory) > self.max_relay_inventory:
            oldest = self._relay_inventory.pop(0)
            self._relay_inventory_set.discard(oldest)
        return True

    def _mark_broadcast(self, block_hash: str) -> bool:
        """Backward-compatible block relay marker used by existing tests."""
        if block_hash in self._broadcast_seen_set:
            return False
        self._broadcast_seen_set.add(block_hash)
        self._broadcast_seen.append(block_hash)
        if len(self._broadcast_seen) > self.max_relay_inventory:
            oldest = self._broadcast_seen.pop(0)
            self._broadcast_seen_set.discard(oldest)
        return self._remember_inventory(f"block:{block_hash}")

    def enqueue_relay(
        self,
        kind: str,
        path: str,
        inventory_id: str,
        payload: Dict[str, Any],
        *,
        peers: Optional[Iterable[str]] = None,
        force: bool = False,
    ) -> bool:
        inventory_key = f"{kind}:{inventory_id}"
        if not force and not self._remember_inventory(inventory_key):
            return False
        targets = [peer for peer in (peers or sorted(self.peers)) if peer not in self.banned]
        if not targets:
            return False
        if len(self._relay_queue) >= self.max_relay_queue:
            dropped = self._relay_queue.pop(0)
            self.log_event("relay_dropped", item_kind=dropped.kind, inventory_id=dropped.inventory_id, reason="queue full")
        self._relay_queue.append(RelayItem(kind=kind, path=path, inventory_id=inventory_id, payload=payload, peers=targets))
        self.log_event("relay_queued", item_kind=kind, inventory_id=inventory_id, peers=len(targets), queue=len(self._relay_queue))
        return True

    def drain_relay_queue(self) -> int:
        now = time.time()
        delivered = 0
        remaining: List[RelayItem] = []
        for item in self._relay_queue:
            if item.next_try_at > now:
                remaining.append(item)
                continue
            item.attempts += 1
            failed: List[str] = []
            for peer in item.peers:
                try:
                    self.post_json(f"{peer}{item.path}", item.payload)
                    delivered += 1
                    self.score_peer(peer, 1)
                except Exception:
                    failed.append(peer)
                    self.score_peer(peer, -1, reason=f"{item.kind} relay failure")
            if failed and item.attempts < self.relay_max_attempts:
                item.peers = failed
                item.next_try_at = now + self.relay_backoff_seconds * (2 ** (item.attempts - 1))
                remaining.append(item)
            elif failed:
                self.log_event(
                    "relay_failed",
                    item_kind=item.kind,
                    inventory_id=item.inventory_id,
                    peers=len(failed),
                    attempts=item.attempts,
                )
            else:
                self.log_event("relay_delivered", item_kind=item.kind, inventory_id=item.inventory_id, attempts=item.attempts)
        self._relay_queue = remaining
        return delivered

    def broadcast_block(self, block: Block, force: bool = False) -> int:
        # Skip blocks we have already relayed so echoed blocks do not loop.
        block_hash = block.hash()
        if not force and not self._mark_broadcast(block_hash):
            return 0
        queued = self.enqueue_relay("block", "/block", block_hash, block.to_dict(), force=True)
        delivered = self.drain_relay_queue() if queued else 0
        self.log_event("block_relayed", hash=block_hash, peers=delivered, queue=len(self._relay_queue))
        return delivered

    def relay_new_blocks(self, received: Block) -> int:
        """Relay the received block and, if accepting it advanced the active
        chain past it (e.g. a reorg connected orphans), the new tip too."""
        delivered = self.broadcast_block(received)
        tip = self.chain.tip()
        if tip.hash() != received.hash():
            delivered += self.broadcast_block(tip)
        return delivered



def fee_estimates_payload(chain: Blockchain, assumed_vbytes: int = 200) -> Dict[str, Any]:
    presets = {"slow": 6, "normal": 3, "fast": 1}
    payload: Dict[str, Any] = {"assumed_vbytes": int(assumed_vbytes), "presets": {}}
    for name, target in presets.items():
        estimate = chain.estimate_smart_fee(target)
        rate = int(estimate.get("fee_rate_per_kvb", 0))
        payload["presets"][name] = {
            "target_blocks": target,
            "fee_rate_per_kvb": rate,
            "estimated_fee_sats": max(1, (rate * int(assumed_vbytes) + 999) // 1000),
            "method": estimate.get("method", "local-policy"),
        }
    return payload

def make_handler(node: NetCoinNode, *, trust_proxy_headers: bool = False):
    app_store = AppStore(node.chain.data_dir)

    class Handler(BaseHTTPRequestHandler):
        server_version = "NetCoinNode/0.2"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - stdlib method name
            return

        def read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_REQUEST_BODY_BYTES:
                raise NodeError("request body too large")
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def end_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            super().end_headers()

        def send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_text(self, text: str | bytes, status: int = 200, content_type: str = "text/plain; version=0.0.4; charset=utf-8") -> None:
            body = text if isinstance(text, bytes) else text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_event_stream(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            last = None
            for _ in range(30):
                payload = {"height": node.chain.height(), "tip_hash": node.chain.tip_hash(), "mempool": len(node.chain.mempool), "peers": len(node.peers), "t": int(time.time())}
                if payload != last:
                    self.wfile.write(("event: netcoin\n" + "data: " + json.dumps(payload, sort_keys=True) + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                    last = payload
                time.sleep(5)

        def send_error_json(self, message: str, status: int = 400) -> None:
            self.send_json({"ok": False, "error": message}, status=status)

        def do_GET(self) -> None:  # noqa: N802 - stdlib method name
            parsed = urlparse(self.path)
            if not node.rate_limiter.allow((self.client_ip(), "GET", parsed.path)):
                self.send_error_json("rate limit exceeded", status=429)
                return
            try:
                if parsed.path == "/events/stream":
                    self.send_event_stream()
                elif parsed.path in ("/", "/info"):
                    self.send_json(node.cached_response("info", 2.0, lambda: {"ok": True, "node": node.info()}))
                elif parsed.path in ("/health", "/status-lite"):
                    self.send_json(node.cached_response("health", 2.0, node.health))
                elif parsed.path == "/metrics":
                    self.send_text(node.metrics_text())
                elif parsed.path == "/relay":
                    self.send_json(
                        {
                            "queue": len(node._relay_queue),
                            "inventory": len(node._relay_inventory),
                            "items": [
                                {
                                    "kind": item.kind,
                                    "inventory_id": item.inventory_id,
                                    "peers": len(item.peers),
                                    "attempts": item.attempts,
                                    "next_try_at": int(item.next_try_at),
                                }
                                for item in node._relay_queue
                            ],
                        }
                    )
                elif parsed.path == "/events":
                    query = parse_qs(parsed.query)
                    limit = max(1, min(int(query.get("limit", [100])[0]), 500))
                    self.send_json({"events": node.recent_events(limit)})
                elif parsed.path == "/chain":
                    query = parse_qs(parsed.query)
                    start = int(query.get("start", [0])[0])
                    limit = int(query.get("limit", [200])[0])
                    self.send_json(node.chain.export_chain(start=start, limit=limit))
                elif parsed.path == "/headers":
                    query = parse_qs(parsed.query)
                    start = int(query.get("start", [0])[0])
                    limit = int(query.get("limit", [2000])[0])
                    self.send_json({"headers": node.chain.header_list(start, limit)})
                elif parsed.path.startswith("/block/"):
                    block_hash = parsed.path.split("/", 2)[2]
                    block = node.chain.block_by_hash(block_hash)
                    if block is None:
                        self.send_error_json("block not found", status=404)
                    else:
                        coinbase_value = block.transactions[0].total_output() if block.transactions else 0
                        subsidy = node.chain.subsidy(block.header.height)
                        self.send_json(block.to_dict() | {
                            "hash": block.hash(),
                            "weight": block.weight(),
                            "coinbase_value_sats": coinbase_value,
                            "subsidy_sats": subsidy,
                            "fees_sats": max(0, coinbase_value - subsidy),
                        })
                elif parsed.path.startswith("/cfilter/"):
                    block_hash = parsed.path.split("/", 2)[2]
                    block = node.chain.block_by_hash(block_hash)
                    if block is None:
                        self.send_error_json("block not found", status=404)
                    else:
                        from .blockfilter import build_block_filter, filter_hash
                        data = build_block_filter(block)
                        self.send_json({
                            "block_hash": block.hash(),
                            "height": block.header.height,
                            "filter": data.hex(),
                            "filter_hash": filter_hash(data),
                        })
                elif parsed.path.startswith("/compact-block-missing/"):
                    block_hash = parsed.path.split("/", 2)[2]
                    block = node.chain.block_by_hash(block_hash)
                    if block is None:
                        self.send_error_json("block not found", status=404)
                    else:
                        query = parse_qs(parsed.query)
                        have = []
                        for value in query.get("have", []):
                            have.extend([item for item in value.split(",") if item])
                        self.send_json(compact_missing_payload(block, have))
                elif parsed.path.startswith("/compact-block/"):
                    block_hash = parsed.path.split("/", 2)[2]
                    block = node.chain.block_by_hash(block_hash)
                    if block is None:
                        self.send_error_json("block not found", status=404)
                    else:
                        self.send_json(make_compact_block(block).to_dict())
                elif parsed.path.startswith("/tx/"):
                    txid = parsed.path.split("/", 2)[2]
                    found = node.chain.get_transaction(txid)
                    if found is None:
                        self.send_error_json("transaction not found", status=404)
                    else:
                        tx, block = found
                        payload = {
                            "txid": tx.txid(),
                            "wtxid": tx.wtxid(),
                            "confirmed": block is not None,
                            "block_hash": block.hash() if block else None,
                            "block_height": block.header.height if block else None,
                            "tx": tx.to_dict(include_scripts=True, include_witness=True),
                        }
                        self.send_json(payload)
                elif parsed.path.startswith("/address/"):
                    address = parsed.path.split("/", 2)[2]
                    query = parse_qs(parsed.query)
                    limit = max(1, min(int(query.get("limit", [100])[0]), 500))
                    offset = max(0, int(query.get("offset", [0])[0]))
                    summary = node.chain.address_summary(address)
                    txids = list(summary.get("transaction_ids", []))
                    summary["transaction_ids_total"] = len(txids)
                    summary["transaction_ids_offset"] = offset
                    summary["transaction_ids_limit"] = limit
                    summary["transaction_ids"] = txids[offset:offset + limit]
                    summary["has_next"] = offset + limit < len(txids)
                    self.send_json(summary)
                elif parsed.path.startswith("/balance/"):
                    address = parsed.path.split("/", 2)[2]
                    self.send_json(node.chain.address_balance_summary(address))
                elif parsed.path == "/latest":
                    query = parse_qs(parsed.query)
                    n = max(1, min(int(query.get("n", [10])[0]), 100))
                    def build_latest() -> Dict[str, Any]:
                        recent = node.chain.chain[-n:][::-1]
                        blocks = [
                            {
                                "height": b.header.height,
                                "hash": b.hash(),
                                "timestamp": b.header.timestamp,
                                "transactions": len(b.transactions),
                                "weight": b.weight(),
                            }
                            for b in recent
                        ]
                        return {"height": node.chain.height(), "tip_hash": node.chain.tip_hash(), "blocks": blocks, "cached_for_seconds": 2}
                    self.send_json(node.cached_response(f"latest:{n}", 2.0, build_latest))
                elif parsed.path == "/latest-txs":
                    query = parse_qs(parsed.query)
                    n = max(1, min(int(query.get("n", [20])[0]), 100))
                    confirmed = []
                    for b in reversed(node.chain.chain):
                        for position, tx in reversed(list(enumerate(b.transactions))):
                            confirmed.append({
                                "txid": tx.txid(),
                                "wtxid": tx.wtxid(),
                                "confirmed": True,
                                "block_hash": b.hash(),
                                "block_height": b.header.height,
                                "position": position,
                                "outputs": len(tx.outputs),
                                "total_output_sats": tx.total_output(),
                                "timestamp": b.header.timestamp,
                            })
                            if len(confirmed) >= n:
                                break
                        if len(confirmed) >= n:
                            break
                    mempool = [{
                        "txid": tx.txid(),
                        "wtxid": tx.wtxid(),
                        "confirmed": False,
                        "outputs": len(tx.outputs),
                        "total_output_sats": tx.total_output(),
                        "timestamp": int(node.chain.mempool_times.get(tx.txid(), time.time())),
                    } for tx in reversed(node.chain.mempool[-n:])]
                    self.send_json({"confirmed": confirmed, "mempool": mempool, "limit": n})
                elif parsed.path == "/supply":
                    self.send_json(node.chain.supply_summary())
                elif parsed.path == "/blocktemplate":
                    query = parse_qs(parsed.query)
                    address = query.get("address", [None])[0]
                    self.send_json(node.chain.get_block_template(miner_address=address))
                elif parsed.path == "/mempool":
                    query = parse_qs(parsed.query)
                    node.chain.evict_expired_mempool(node.chain.mempool_info().get("expiry_seconds", 24 * 60 * 60))
                    payload = node.chain.mempool_info()
                    include_txs = query.get("transactions", ["1"])[0].lower() not in ("0", "false", "no")
                    if include_txs:
                        limit = max(1, min(int(query.get("limit", [100])[0]), 500))
                        payload["transactions"] = node.chain.export_mempool().get("transactions", [])[-limit:]
                    else:
                        payload["transactions"] = []
                    self.send_json(payload)
                elif parsed.path == "/fee-estimates":
                    self.send_json(fee_estimates_payload(node.chain))
                elif parsed.path == "/peers":
                    self.send_json({
                        "peers": sorted(node.peers),
                        "scores": node.peer_scores,
                        "banned": sorted(node.banned),
                    })
                elif parsed.path == "/utxos":
                    query = parse_qs(parsed.query)
                    address = query.get("address", [""])[0]
                    include_mempool_spent = query.get("include_mempool_spent", ["0"])[0].lower() in ("1", "true", "yes")
                    utxos = node.chain.utxos_for_address(address)
                    mempool_spent = {txin.outpoint() for tx in node.chain.mempool for txin in tx.inputs}
                    available = [utxo for utxo in utxos if include_mempool_spent or utxo.outpoint() not in mempool_spent]
                    self.send_json({
                        "address": address,
                        "utxos": [utxo.to_dict() for utxo in available],
                        "excluded_mempool_spent": len(utxos) - len(available),
                    })
                else:
                    if os.environ.get("NETCOIN_APP_REQUIRE_ADMIN", "0") == "1" and parsed.path.startswith(("/admin", "/api/admin", "/merchant", "/api/merchant", "/wallet", "/api/wallet", "/custody", "/api/custody", "/security", "/api/security")):
                        if not self.require_app_admin():
                            return
                    try:
                        status, payload, content_type = route_app_get(app_store, node.chain, parsed.path, parse_qs(parsed.query), node=node)
                    except AppError as app_exc:
                        if str(app_exc) == "not an app-layer route":
                            self.send_error_json("not found", status=404)
                        else:
                            self.send_error_json(str(app_exc), status=400)
                    else:
                        if content_type == "application/json":
                            self.send_json(payload, status=status)  # type: ignore[arg-type]
                        else:
                            self.send_text(payload if isinstance(payload, bytes) else str(payload), status=status, content_type=content_type)
            except Exception as exc:
                self.send_error_json(str(exc), status=400)

        def client_ip(self) -> str:
            return client_ip_from_headers(self.headers, self.client_address, trust_proxy_headers=trust_proxy_headers)

        def require_node_admin(self) -> bool:
            expected = os.environ.get("NETCOIN_APP_ADMIN_TOKEN", "")
            provided = self.headers.get("X-Netcoin-Admin-Token", "") or self.headers.get("Authorization", "").replace("Bearer ", "", 1)
            if expected and hmac.compare_digest(expected, provided):
                return True
            self.send_error_json("operator token required", status=401)
            return False

        def require_app_admin(self) -> bool:
            if os.environ.get("NETCOIN_APP_REQUIRE_ADMIN", "0") != "1":
                return True
            expected = os.environ.get("NETCOIN_APP_ADMIN_TOKEN", "")
            provided = self.headers.get("X-Netcoin-Admin-Token", "") or self.headers.get("Authorization", "").replace("Bearer ", "", 1)
            if expected and hmac.compare_digest(expected, provided):
                return True
            self.send_error_json("admin token required", status=401)
            return False

        def app_api_key_from_headers(self) -> str:
            return self.headers.get("X-Netcoin-Api-Key", "") or self.headers.get("X-API-Key", "")

        def do_POST(self) -> None:  # noqa: N802 - stdlib method name
            parsed = urlparse(self.path)
            # Per-IP, per-endpoint rate limiting for write/relay endpoints.
            if not node.rate_limiter.allow((self.client_ip(), "POST", parsed.path)):
                self.send_error_json("rate limit exceeded", status=429)
                return
            try:
                data = self.read_json()
                if parsed.path == "/tx":
                    tx = Transaction.from_dict(data)
                    txid = node.chain.add_mempool_transaction(tx)
                    node.invalidate_read_cache()
                    node.log_event("tx_received", txid=txid)
                    private = parse_qs(parsed.query).get("private", ["0"])[0].lower() in ("1", "true", "yes")
                    delivered = 0 if private else node.broadcast_transaction(tx)
                    self.send_json({"ok": True, "txid": txid, "relayed_to": delivered, "private": private})
                elif parsed.path == "/package":
                    raw_txs = data.get("transactions", data if isinstance(data, list) else [])
                    if not isinstance(raw_txs, list):
                        raise NodeError("package body must contain a transactions list")
                    txs = [Transaction.from_dict(item) for item in raw_txs]
                    txids = node.chain.add_mempool_package(txs)
                    node.invalidate_read_cache()
                    node.log_event("package_received", txids=txids, count=len(txids))
                    delivered = 0
                    private = parse_qs(parsed.query).get("private", ["0"])[0].lower() in ("1", "true", "yes")
                    if not private:
                        for tx in txs:
                            delivered += node.broadcast_transaction(tx)
                    self.send_json({"ok": True, "txids": txids, "count": len(txids), "relayed_to": delivered, "private": private})
                elif parsed.path in ("/block", "/submitblock"):
                    block = Block.from_dict(data)
                    block_hash = node.accept_block(block)
                    node.invalidate_read_cache()
                    delivered = node.relay_new_blocks(block)
                    self.send_json({"ok": True, "block_hash": block_hash, "relayed_to": delivered})
                elif parsed.path == "/compact-block":
                    if "compact" in data:
                        compact = CompactBlock.from_dict(data["compact"])
                        extra = [Transaction.from_dict(item) for item in data.get("transactions", [])]
                    else:
                        compact = CompactBlock.from_dict(data)
                        extra = []
                    try:
                        block = reconstruct_compact_block(compact, node.chain.mempool, extra_transactions=extra)
                    except CompactBlockError:
                        self.send_json({"ok": False, "missing": missing_transactions(compact, node.chain.mempool)}, status=202)
                        return
                    block_hash = node.accept_block(block)
                    node.invalidate_read_cache()
                    delivered = node.relay_new_blocks(block)
                    self.send_json({"ok": True, "block_hash": block_hash, "relayed_to": delivered})
                elif parsed.path == "/mempool/clear":
                    if not self.require_node_admin():
                        return
                    cleared = node.chain.clear_mempool()
                    node.invalidate_read_cache()
                    self.send_json({"ok": True, "cleared": cleared})
                elif parsed.path == "/mempool/prune":
                    if not self.require_node_admin():
                        return
                    evicted = node.chain.evict_expired_mempool(24 * 60 * 60)
                    node.invalidate_read_cache()
                    self.send_json({"ok": True, "evicted": evicted})
                elif parsed.path == "/peers":
                    for peer in data.get("peers", []):
                        node.add_peer(str(peer))
                    self.send_json({"ok": True, "peers": sorted(node.peers)})
                elif parsed.path == "/sync":
                    adopted = node.sync_all()
                    self.send_json({"ok": True, "adopted_chains": adopted, "info": node.info()})
                elif parsed.path == "/relay":
                    delivered = node.drain_relay_queue()
                    self.send_json({"ok": True, "delivered": delivered, "queue": len(node._relay_queue)})
                else:
                    public_app_write = parsed.path in {
                        "/community/posts", "/api/community/posts", "/app/community/posts",
                        "/community/improvements", "/api/community/improvements", "/app/community/improvements",
                        "/community/reports", "/api/community/reports", "/app/community/reports",
                    } or (parsed.path.startswith(("/community/improvements/", "/api/community/improvements/", "/app/community/improvements/")) and parsed.path.endswith("/vote"))
                    if not public_app_write and not self.require_app_admin():
                        return
                    header_api_key = self.app_api_key_from_headers()
                    if header_api_key and "api_key" not in data:
                        data["api_key"] = header_api_key
                    try:
                        status, payload = route_app_post(app_store, node.chain, parsed.path, data, node=node)
                    except AppError as app_exc:
                        if str(app_exc) == "not an app-layer route":
                            self.send_error_json("not found", status=404)
                        else:
                            self.send_error_json(str(app_exc), status=400)
                    else:
                        self.send_json(payload, status=status)
            except Exception as exc:
                self.send_error_json(str(exc), status=400)

    return Handler


def run_node(
    data_dir: str,
    host: str = "127.0.0.1",
    port: int = DEFAULT_NODE_PORT,
    peers: Optional[List[str]] = None,
    advertise: Optional[str] = None,
    sync_interval: int = 0,
    rate_limit_per_min: int = 240,
    p2p_port: int = DEFAULT_P2P_PORT,
    trust_proxy_headers: bool = False,
) -> None:
    chain = Blockchain(data_dir=data_dir)
    node = NetCoinNode(chain, peers=peers or [], self_url=advertise, rate_limit_per_min=rate_limit_per_min)

    # Bind and serve immediately, then bootstrap (announce + peer discovery +
    # initial sync) in a background thread. A slow or unreachable peer must never
    # delay — or prevent — the node from listening and accepting connections.
    server = ThreadingHTTPServer((host, port), make_handler(node, trust_proxy_headers=trust_proxy_headers))
    print(f"NetCoin node listening on http://{host}:{port}")
    if advertise:
        print(f"advertising as {advertise}")

    # Serve the binary TCP P2P transport alongside HTTP. HTTP stays the API for
    # explorers/faucets/wallets/light clients; binary P2P is the node-to-node path.
    p2p_server = None
    if p2p_port:
        try:
            from .p2p import NetCoinP2PServer

            p2p_server = NetCoinP2PServer((host, int(p2p_port)), chain)
            Thread(target=p2p_server.serve_forever, daemon=True).start()
            print(f"binary P2P listening on {host}:{p2p_port}")
        except OSError as exc:
            print(f"binary P2P not started ({exc})")

    def _bootstrap() -> None:
        result = node.bootstrap()
        # Best-effort: also sync each peer over the binary P2P transport.
        p2p_blocks = 0
        if p2p_port:
            for peer in list(node.peers):
                peer_host = urlparse(peer).hostname
                if peer_host:
                    p2p_blocks += node.sync_over_p2p(peer_host, p2p_port)
        print(
            f"bootstrap: peers={len(node.peers)} learned={result['learned']} "
            f"adopted_chains={result['adopted_chains']} p2p_blocks={p2p_blocks} "
            f"height={chain.height()} tip={chain.tip_hash()}"
        )

    Thread(target=_bootstrap, daemon=True).start()

    sync_stop: Optional[Event] = None
    sync_thread: Optional[Thread] = None
    if sync_interval > 0:
        sync_stop, sync_thread = node.start_background_sync(sync_interval)
        print(f"background sync every {sync_interval}s")

    try:
        server.serve_forever()
    finally:
        if sync_stop is not None:
            sync_stop.set()
        if sync_thread is not None:
            sync_thread.join(timeout=5)
        if p2p_server is not None:
            p2p_server.shutdown()
            p2p_server.server_close()
        server.server_close()
