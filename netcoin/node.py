"""HTTP peer-to-peer node for NetCoin.

The transport is intentionally simple JSON over HTTP, but the exposed concepts are
Bitcoin-like: peer discovery, headers-first sync shape, block/transaction relay,
compact block summaries, mempool exchange, block templates, and orphan handling.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from . import esplora
from .apps import AppError, AppStore, route_app_get, route_app_post
from .bandwidth import TokenBucket, budget_for_mode
from .block import Block
from .chain import Blockchain
from .compact import (
    CompactBlock,
    CompactBlockError,
    compact_missing_payload,
    make_compact_block,
    missing_transactions,
    reconstruct_compact_block,
)
from .crypto import _fast_crypto_enabled, crypto_backend_status, crypto_self_test
from .emission import emission_report
from .logsetup import emit
from .p2p import PeerManager
from .p2p_public_hardening import public_p2p_hardening_plan
from .params import (
    DEFAULT_NODE_PORT,
    DEFAULT_P2P_PORT,
    MAX_REQUEST_BODY_BYTES,
    NETWORK_NAME,
    NODE_VERSION,
    PROTOCOL_VERSION,
    SPACING_V2_ACTIVATION_HEIGHT,
    USER_AGENT,
    target_spacing_at,
)
from .tx import Transaction


class NodeError(ValueError):
    """Raised when node-level operations fail."""


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int = 0


class RateLimiter:
    """Token-bucket rate limiter keyed by caller identity and endpoint."""

    def __init__(self, max_requests: int = 240, window_seconds: int = 60):
        self.max_requests = max(0, int(max_requests))
        self.window_seconds = max(1, int(window_seconds))
        self._buckets: dict[Any, tuple[float, float]] = {}
        self._lock = Lock()

    @property
    def refill_rate(self) -> float:
        return self.max_requests / float(self.window_seconds)

    def check(self, key: Any) -> RateLimitDecision:
        if self.max_requests <= 0:
            return RateLimitDecision(True, 0)
        now = time.time()
        capacity = float(self.max_requests)
        refill_rate = self.refill_rate
        with self._lock:
            tokens, updated_at = self._buckets.get(key, (capacity, now))
            elapsed = max(0.0, now - updated_at)
            tokens = min(capacity, tokens + elapsed * refill_rate)
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return RateLimitDecision(True, 0)
            retry_after = max(1, int((1.0 - tokens) / refill_rate + 0.999))
            self._buckets[key] = (tokens, now)
            return RateLimitDecision(False, retry_after)

    def allow(self, key: Any) -> bool:
        return self.check(key).allowed


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


def api_key_identity_from_headers(headers: Any) -> str:
    """Return a stable, non-secret API-key identity for limiter bucketing."""
    value = headers.get("X-Netcoin-Api-Key", "") or headers.get("X-API-Key", "")
    authorization = headers.get("Authorization", "")
    if not value and authorization.lower().startswith("bearer "):
        value = authorization[7:].strip()
    if not value:
        return "anonymous"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"key:{digest}"


def versioned_api_path(path: str) -> tuple[str, bool]:
    """Return the canonical node path plus whether the request used /v1."""
    if path == "/v1":
        return "/", True
    if path.startswith("/v1/"):
        stripped = path[3:]
        return stripped or "/", True
    return path, False


@dataclass
class RelayItem:
    kind: str
    path: str
    inventory_id: str
    payload: dict[str, Any]
    peers: list[str]
    attempts: int = 0
    next_try_at: float = 0.0
    created_at: float = field(default_factory=time.time)


class NetCoinNode:
    def __init__(
        self,
        chain: Blockchain,
        peers: Iterable[str] | None = None,
        peers_path: str | None = None,
        persist: bool = True,
        self_url: str | None = None,
        max_peers: int = 128,
        rate_limit_per_min: int = 240,
        request_timeout: int = 5,
        request_retries: int = 1,
        ban_threshold: int = -5,
        ban_ttl_seconds: int = 3600,
        bandwidth_mode: str | None = None,
        max_relay_bytes_per_second: int | None = None,
    ):
        self.chain = chain
        self.peers = set()
        self.orphans: dict[str, Block] = {}
        self.persist = persist
        self.max_peers = max_peers
        self.self_url = self._normalize_peer(self_url) if self_url else None
        self.advertise_unreachable = False
        self.advertise_unreachable_error = ""
        self._advertise_reachability_checked = False
        # Peer reputation: scores adjust on good/bad behavior; reaching the ban
        # threshold bans the peer. Bans persist to banned_peers.json.
        self.peer_scores: dict[str, int] = {}
        self.banned: set = set()
        self.ban_threshold = ban_threshold
        self.peer_manager = PeerManager(max_per_prefix=4, ban_score=abs(ban_threshold), ban_seconds=ban_ttl_seconds)
        # Bans expire after this many seconds (0 = permanent) so a transient
        # outage doesn't partition a peer forever; ban_times records when each
        # ban started.
        self.ban_ttl_seconds = max(0, ban_ttl_seconds)
        self.ban_times: dict[str, float] = {}
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
        configured_bandwidth_mode = bandwidth_mode or os.environ.get("NETCOIN_BANDWIDTH_MODE", "normal")
        self.bandwidth_budget = budget_for_mode(configured_bandwidth_mode)
        override_bps = max_relay_bytes_per_second
        if override_bps is None and os.environ.get("NETCOIN_MAX_RELAY_BYTES_PER_SECOND"):
            override_bps = int(os.environ["NETCOIN_MAX_RELAY_BYTES_PER_SECOND"])
        relay_bps = self.bandwidth_budget.max_bytes_per_second if override_bps is None else int(override_bps)
        self.outbound_relay_bucket = TokenBucket(relay_bps)
        # Bounded event log for block-propagation visibility.
        self.event_log: list[dict[str, Any]] = []
        self.max_events = 500
        # Bounded memory of recently relayed block hashes so a block is not
        # re-broadcast in a relay loop when peers echo it back.
        self._broadcast_seen: list[str] = []
        self._broadcast_seen_set: set[str] = set()
        # Bounded inventory cache + relay queue. Inventory keeps echoed tx/block
        # announcements from being re-enqueued repeatedly; failed deliveries stay
        # queued with exponential backoff for a later drain.
        self._relay_inventory: list[str] = []
        self._relay_inventory_set: set[str] = set()
        self._relay_queue: list[RelayItem] = []
        self.max_relay_inventory = 2000
        self.max_relay_queue = 1000
        self.max_node_orphans = 200
        self.relay_max_attempts = 3
        self.relay_backoff_seconds = 2.0
        self.started_at = time.time()
        # Tiny in-process response cache for read-heavy public endpoints. This
        # protects the Python node from repeated explorer/status refreshes without
        # changing consensus state or write endpoints.
        self._response_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self.peers_path = Path(peers_path) if peers_path else (Path(chain.data_dir) / "peers.json")
        self._load_banned()
        # Recover trusted peers that a previous run auto-banned during a transient
        # outage, then reconnect: reload discovered peers and merge in --peer ones.
        self._unban_trusted()
        self._load_peers()
        for peer in peers or []:
            self.add_peer(peer)

    def _peer_manager_address(self, peer: str) -> str:
        parsed = urlparse(peer)
        host = parsed.hostname or peer
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return f"{host}:{port}"

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
        with suppress(Exception):
            self.peer_manager.add_peer(
                self._peer_manager_address(normalized), direction="outbound", user_agent=USER_AGENT
            )
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
            self.banned_path.write_text(
                json.dumps(
                    {
                        "banned": sorted(self.banned),
                        "ban_times": {p: self.ban_times[p] for p in sorted(self.banned) if p in self.ban_times},
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
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
        with suppress(Exception):
            self.peer_manager.report_misbehavior(
                self._peer_manager_address(normalized), abs(self.ban_threshold), reason or "manual ban"
            )
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
        try:
            if delta < 0:
                self.peer_manager.report_misbehavior(
                    self._peer_manager_address(normalized), abs(delta), reason or "node score penalty"
                )
            else:
                self.peer_manager.add_peer(
                    self._peer_manager_address(normalized), direction="outbound", user_agent=USER_AGENT
                )
        except Exception:
            pass
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


    def ensure_advertise_reachable(self) -> bool:
        if not self.self_url:
            return True
        if self._advertise_reachability_checked:
            return not self.advertise_unreachable
        self._advertise_reachability_checked = True
        try:
            self.fetch_json(f"{self.self_url}/peers/echo-addr")
        except Exception as exc:
            self.advertise_unreachable = True
            self.advertise_unreachable_error = str(exc) or exc.__class__.__name__
            self.log_event("advertise_unreachable", self_url=self.self_url, error=self.advertise_unreachable_error)
            return False
        self.advertise_unreachable = False
        self.advertise_unreachable_error = ""
        return True

    def announce_self(self) -> int:
        """Gossip push: tell known peers our advertised URL so they can dial back."""
        if not self.self_url:
            return 0
        # Advisory only: populates advertise_unreachable/_error for /info so an
        # operator can see a problem, but does not block announcing. Many home
        # routers don't support NAT hairpinning, so a node legitimately cannot
        # reach its own forwarded public address from inside its own LAN even
        # though outside peers reach it fine -- blocking on this self-check
        # would silently stop exactly the correctly-configured home seeds it's
        # meant to help. The static --advertise format validation in cli.py
        # (normalize_advertise_url) is the real defense against placeholder or
        # private-range addresses.
        self.ensure_advertise_reachable()
        delivered = 0
        for peer in list(self.peers):
            try:
                self.post_json(f"{peer}/peers", {"peers": [self.self_url]})
                delivered += 1
            except Exception:
                continue
        return delivered

    def bootstrap(self) -> dict[str, int]:
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

    SERVICES: ClassVar[list[str]] = [
        "network",
        "headers",
        "compact-blocks",
        "mempool",
        "block-template",
        "explorer-api",
        "compact-filters",
    ]

    def uptime_seconds(self) -> int:
        return int(time.time() - self.started_at)

    def genesis_hash(self) -> str:
        return self.chain.chain[0].hash()

    def info(self) -> dict[str, Any]:
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
                "target_spacing_seconds": target_spacing_at(self.chain.height() + 1),
                "spacing_v2_activation_height": SPACING_V2_ACTIVATION_HEIGHT,
                "fast_crypto": _fast_crypto_enabled(),
                "crypto_backend": crypto_backend_status(),
                "crypto_self_test": crypto_self_test(),
                "peers": sorted(self.peers),
                "advertise": self.self_url or "",
                "advertise_unreachable": self.advertise_unreachable,
                "advertise_unreachable_error": self.advertise_unreachable_error,
                "peer_manager": {"active": self.peer_manager.active_peers(), "banned": self.peer_manager.banlist()},
                "banned": len(self.banned),
                "orphans": len(self.orphans),
                "services": self.SERVICES,
                "bandwidth": self.bandwidth_status(),
            }
        )
        return data

    def health(self) -> dict[str, Any]:
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
            "bandwidth": self.bandwidth_status(),
        }

    def bandwidth_status(self) -> dict[str, Any]:
        return {
            "schema": "netcoin-bandwidth-runtime-v1",
            "budget": self.bandwidth_budget.to_dict(),
            "outbound_relay": self.outbound_relay_bucket.snapshot(),
        }

    def memory_debug_snapshot(self) -> dict[str, Any]:
        """Diagnostic snapshot for tracking down slow memory growth.

        Reports process RSS, a GC object-count breakdown (the most useful
        generic signal for "what is actually accumulating" when a specific
        structure isn't the obvious culprit), and the size of every bounded
        in-memory collection this node keeps, so a size that keeps climbing
        across repeated snapshots points straight at the leak.
        """
        import gc
        from collections import Counter

        rss_kb: int | None = None
        try:
            with open("/proc/self/status", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        rss_kb = int(line.split()[1])
                        break
        except OSError:
            pass
        if rss_kb is None:
            try:
                import resource

                rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            except Exception:
                rss_kb = None

        objects = gc.get_objects()
        type_counts = Counter(type(obj).__name__ for obj in objects)

        return {
            "schema": "netcoin-memory-debug-v1",
            "uptime_seconds": self.uptime_seconds(),
            "rss_kb": rss_kb,
            "rss_mb": round(rss_kb / 1024, 1) if rss_kb is not None else None,
            "gc_object_count": len(objects),
            "gc_top_types": [{"type": name, "count": count} for name, count in type_counts.most_common(20)],
            "collections": {
                "peers": len(self.peers),
                "banned": len(self.banned),
                "trusted_peers": len(self.trusted_peers),
                "peer_scores": len(self.peer_scores),
                "ban_times": len(self.ban_times),
                "orphans": len(self.orphans),
                "event_log": len(self.event_log),
                "relay_queue": len(self._relay_queue),
                "relay_inventory": len(self._relay_inventory),
                "broadcast_seen": len(self._broadcast_seen),
                "response_cache": len(self._response_cache),
                "mempool_transactions": len(self.chain.mempool),
            },
        }

    def cached_response(self, key: str, ttl_seconds: float, builder: Any) -> dict[str, Any]:
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
        mempool = self.chain.mempool_info()
        lines = [
            "# HELP netcoin_block_height Current best block height.",
            "# TYPE netcoin_block_height gauge",
            f"netcoin_block_height {info['height']}",
            "# HELP netcoin_chain_tip_info Best-chain tip labels; value is always 1.",
            "# TYPE netcoin_chain_tip_info gauge",
            f"netcoin_chain_tip_info{{hash=\"{info['tip_hash']}\",height=\"{info['height']}\"}} 1",
            "# HELP netcoin_mempool_transactions Transactions in the mempool.",
            "# TYPE netcoin_mempool_transactions gauge",
            f"netcoin_mempool_transactions {info['mempool_transactions']}",
            "# HELP netcoin_mempool_bytes Total serialized mempool bytes.",
            "# TYPE netcoin_mempool_bytes gauge",
            f"netcoin_mempool_bytes {mempool.get('bytes', 0)}",
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
            "# HELP netcoin_outbound_relay_bytes_total Outbound JSON relay bytes sent by this node.",
            "# TYPE netcoin_outbound_relay_bytes_total counter",
            f"netcoin_outbound_relay_bytes_total {self.outbound_relay_bucket.total_bytes}",
            "# HELP netcoin_outbound_relay_throttle_events_total Outbound relay throttle sleeps.",
            "# TYPE netcoin_outbound_relay_throttle_events_total counter",
            f"netcoin_outbound_relay_throttle_events_total {self.outbound_relay_bucket.throttle_events}",
            "# HELP netcoin_cumulative_work Cumulative chain work.",
            "# TYPE netcoin_cumulative_work gauge",
            f"netcoin_cumulative_work {info['cumulative_work']}",
            "# HELP netcoin_uptime_seconds Node uptime in seconds.",
            "# TYPE netcoin_uptime_seconds counter",
            f"netcoin_uptime_seconds {self.uptime_seconds()}",
            "# HELP netcoin_build_info Static build labels; value is always 1.",
            "# TYPE netcoin_build_info gauge",
            'netcoin_build_info{implementation="python",network="testnet"} 1',
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

    def recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.event_log[-limit:][::-1]

    def fetch_json(self, url: str, timeout: int | None = None) -> dict[str, Any]:
        timeout = self.request_timeout if timeout is None else timeout
        last_exc: Exception | None = None
        for _attempt in range(self.request_retries + 1):
            try:
                with urlopen(url, timeout=timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as exc:  # retry transient network failures
                last_exc = exc
        raise last_exc if last_exc else NodeError("fetch failed")

    def post_json(self, url: str, payload: dict[str, Any], timeout: int | None = None) -> dict[str, Any]:
        timeout = self.request_timeout if timeout is None else timeout
        body = json.dumps(payload).encode("utf-8")
        self.outbound_relay_bucket.consume(len(body))
        last_exc: Exception | None = None
        for _attempt in range(self.request_retries + 1):
            try:
                request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request, timeout=timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as exc:
                last_exc = exc
        raise last_exc if last_exc else NodeError("post failed")

    def compatible_peer(self, remote: dict[str, Any]) -> bool:
        """Reject peers on a different genesis or network before syncing from them.

        Older peers may not report genesis/network; only reject on a clear mismatch."""
        remote_genesis = remote.get("genesis_hash")
        if remote_genesis and remote_genesis != self.genesis_hash():
            return False
        remote_network = remote.get("network")
        if remote_network and remote_network != NETWORK_NAME:
            return False
        remote_protocol = remote.get("protocol_version")
        return not (remote_protocol is not None and int(remote_protocol) != PROTOCOL_VERSION)

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
        blocks_payload: list[dict[str, Any]] = []
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
        return not block.header.height <= self.chain.height()

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
        payload: dict[str, Any],
        *,
        peers: Iterable[str] | None = None,
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
            self.log_event(
                "relay_dropped", item_kind=dropped.kind, inventory_id=dropped.inventory_id, reason="queue full"
            )
        self._relay_queue.append(
            RelayItem(kind=kind, path=path, inventory_id=inventory_id, payload=payload, peers=targets)
        )
        self.log_event(
            "relay_queued", item_kind=kind, inventory_id=inventory_id, peers=len(targets), queue=len(self._relay_queue)
        )
        return True

    def drain_relay_queue(self) -> int:
        now = time.time()
        delivered = 0
        remaining: list[RelayItem] = []
        for item in self._relay_queue:
            if item.next_try_at > now:
                remaining.append(item)
                continue
            item.attempts += 1
            failed: list[str] = []
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
                self.log_event(
                    "relay_delivered", item_kind=item.kind, inventory_id=item.inventory_id, attempts=item.attempts
                )
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


def _p2p_hardening_snapshot() -> dict[str, Any]:
    """Live public-P2P hardening plan reflecting this node's actual capabilities.

    PEX, AddrV2 and compact-block relay are all wired into the P2P layer, so
    those flags are True. The DNS-seed plan is read from config/dns_seeds.json
    when present. The plan's `ok`/`issues` show what still blocks operational
    M3 (e.g. independent domains/operators), computed by the shared validator.
    """
    seed_config: dict[str, Any] = {}
    config_path = Path(__file__).resolve().parents[1] / "config" / "dns_seeds.json"
    if config_path.exists():
        try:
            seed_config = json.loads(config_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            seed_config = {}
    domains = [
        {"domain": entry.get("domain"), "operator": entry.get("operator")}
        for entry in seed_config.get("seeds", [])
        if isinstance(entry, dict)
    ]
    return public_p2p_hardening_plan(
        dns_seed_plan={"domains": domains},
        operator_manifests=[],
        compact_blocks_enabled=True,
        pex_enabled=True,
        addrv2_enabled=True,
    )


def fee_estimates_payload(chain: Blockchain, assumed_vbytes: int = 200) -> dict[str, Any]:
    presets = {"slow": 6, "normal": 3, "fast": 1}
    payload: dict[str, Any] = {"assumed_vbytes": int(assumed_vbytes), "presets": {}}
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

        def log_message(self, format: str, *args: Any) -> None:
            return

        def read_json(self) -> dict[str, Any]:
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

        def request_version_headers(self) -> dict[str, str]:
            if getattr(self, "_netcoin_v1_request", False):
                return {"API-Version": "v1"}
            raw_path = getattr(self, "_netcoin_raw_path", "")
            successor = "/v1" + (raw_path if raw_path.startswith("/") else "/" + raw_path)
            return {
                "API-Version": "legacy",
                "Deprecation": "true",
                "Link": f'<{successor}>; rel="successor-version"',
            }

        def send_json(self, payload: dict[str, Any], status: int = 200, headers: dict[str, str] | None = None) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for name, value in self.request_version_headers().items():
                self.send_header(name, value)
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def send_text(
            self, text: str | bytes, status: int = 200, content_type: str = "text/plain; version=0.0.4; charset=utf-8"
        ) -> None:
            body = text if isinstance(text, bytes) else text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for name, value in self.request_version_headers().items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def send_event_stream(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            for name, value in self.request_version_headers().items():
                self.send_header(name, value)
            self.end_headers()
            last = None
            for _ in range(30):
                payload = {
                    "height": node.chain.height(),
                    "tip_hash": node.chain.tip_hash(),
                    "mempool": len(node.chain.mempool),
                    "peers": len(node.peers),
                    "t": int(time.time()),
                }
                if payload != last:
                    self.wfile.write(
                        ("event: netcoin\n" + "data: " + json.dumps(payload, sort_keys=True) + "\n\n").encode("utf-8")
                    )
                    self.wfile.flush()
                    last = payload
                time.sleep(5)

        def send_error_json(self, message: str, status: int = 400, headers: dict[str, str] | None = None) -> None:
            self.send_json({"ok": False, "error": message}, status=status, headers=headers)

        def _esplora_status_for_height(self, height: int | None) -> dict[str, Any]:
            if height is None or height < 0 or height > node.chain.height():
                return esplora.esplora_status(confirmed=False, block_height=None, block_hash=None, block_time=None)
            block = node.chain.chain[height]
            return esplora.esplora_status(
                confirmed=True,
                block_height=height,
                block_hash=block.hash(),
                block_time=int(block.header.timestamp),
            )

        def _handle_esplora(self, parsed: Any, node: NetCoinNode) -> None:
            # Blockstream-Esplora-compatible read API so BDK and other Bitcoin
            # tooling can point at a NetCoin node with only a URL change.
            parts = parsed.path.split("/")[2:]  # drop leading "", "esplora"
            chain = node.chain
            try:
                if parts == ["blocks", "tip", "height"]:
                    return self.send_text(str(chain.height()))
                if parts == ["blocks", "tip", "hash"]:
                    return self.send_text(chain.tip_hash())
                if len(parts) == 2 and parts[0] == "block-height":
                    h = int(parts[1])
                    if h < 0 or h > chain.height():
                        return self.send_error_json("block not found", status=404)
                    return self.send_text(chain.chain[h].hash())
                if len(parts) == 2 and parts[0] == "block":
                    block = chain.block_by_hash(parts[1])
                    if block is None:
                        return self.send_error_json("block not found", status=404)
                    return self.send_json(
                        esplora.esplora_block(
                            block.header.to_dict(), block_id=block.hash(), tx_count=len(block.transactions)
                        )
                    )
                if len(parts) == 2 and parts[0] == "tx":
                    found = chain.get_transaction(parts[1])
                    if found is None:
                        return self.send_error_json("transaction not found", status=404)
                    tx, block = found
                    status = self._esplora_status_for_height(block.header.height if block else None)
                    return self.send_json(
                        esplora.esplora_tx(
                            tx.to_dict(include_scripts=True, include_witness=True), txid=tx.txid(), status=status
                        )
                    )
                if len(parts) == 3 and parts[0] == "address" and parts[2] == "utxo":
                    utxos = chain.utxos_for_address(parts[1], include_immature=True)
                    out = []
                    for u in utxos:
                        d = u.to_dict()
                        out.append(esplora.esplora_utxo(d, status=self._esplora_status_for_height(d.get("height"))))
                    return self.send_json(out)
                if len(parts) == 2 and parts[0] == "address":
                    summary = chain.address_summary(parts[1])
                    summary.setdefault("address", parts[1])
                    balance = summary.get("balance", {})
                    funded = int(balance.get("total", 0)) if isinstance(balance, dict) else int(balance)
                    return self.send_json(
                        esplora.esplora_address(
                            summary,
                            funded_sum=funded,
                            spent_sum=0,
                            funded_count=int(summary.get("utxo_count", 0)),
                            spent_count=0,
                        )
                    )
                if parts == ["fee-estimates"]:
                    return self.send_json(esplora.esplora_fee_estimates(fee_estimates_payload(chain)))
                return self.send_error_json("esplora endpoint not found", status=404)
            except (ValueError, KeyError, IndexError) as exc:
                return self.send_error_json(f"bad esplora request: {exc}", status=400)

        def canonical_parsed_url(self):
            parsed = urlparse(self.path)
            canonical_path, is_v1 = versioned_api_path(parsed.path)
            self._netcoin_raw_path = parsed.path
            self._netcoin_v1_request = is_v1
            return parsed._replace(path=canonical_path)

        def rate_limit_key(self, method: str, path: str) -> tuple[str, str, str, str]:
            return (self.client_ip(), api_key_identity_from_headers(self.headers), method, path)

        def enforce_rate_limit(self, method: str, path: str) -> bool:
            decision = node.rate_limiter.check(self.rate_limit_key(method, path))
            if decision.allowed:
                return True
            self.send_error_json(
                "rate limit exceeded",
                status=429,
                headers={"Retry-After": str(max(1, decision.retry_after))},
            )
            return False

        def do_GET(self) -> None:
            parsed = self.canonical_parsed_url()
            if not self.enforce_rate_limit("GET", parsed.path):
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
                elif parsed.path == "/debug/memory":
                    self.send_json(node.memory_debug_snapshot())
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
                        self.send_json(
                            block.to_dict()
                            | {
                                "hash": block.hash(),
                                "weight": block.weight(),
                                "coinbase_value_sats": coinbase_value,
                                "subsidy_sats": subsidy,
                                "fees_sats": max(0, coinbase_value - subsidy),
                            }
                        )
                elif parsed.path.startswith("/cfilter/"):
                    block_hash = parsed.path.split("/", 2)[2]
                    block = node.chain.block_by_hash(block_hash)
                    if block is None:
                        self.send_error_json("block not found", status=404)
                    else:
                        from .blockfilter import build_block_filter, filter_hash

                        data = build_block_filter(block)
                        self.send_json(
                            {
                                "block_hash": block.hash(),
                                "height": block.header.height,
                                "filter": data.hex(),
                                "filter_hash": filter_hash(data),
                            }
                        )
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
                    summary["transaction_ids"] = txids[offset : offset + limit]
                    summary["has_next"] = offset + limit < len(txids)
                    self.send_json(summary)
                elif parsed.path.startswith("/balance/"):
                    address = parsed.path.split("/", 2)[2]
                    self.send_json(node.chain.address_balance_summary(address))
                elif parsed.path == "/latest":
                    query = parse_qs(parsed.query)
                    n = max(1, min(int(query.get("n", [10])[0]), 100))

                    def build_latest() -> dict[str, Any]:
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
                        return {
                            "height": node.chain.height(),
                            "tip_hash": node.chain.tip_hash(),
                            "blocks": blocks,
                            "cached_for_seconds": 2,
                        }

                    self.send_json(node.cached_response(f"latest:{n}", 2.0, build_latest))
                elif parsed.path == "/latest-txs":
                    query = parse_qs(parsed.query)
                    n = max(1, min(int(query.get("n", [20])[0]), 100))
                    confirmed = []
                    for b in reversed(node.chain.chain):
                        for position, tx in reversed(list(enumerate(b.transactions))):
                            confirmed.append(
                                {
                                    "txid": tx.txid(),
                                    "wtxid": tx.wtxid(),
                                    "confirmed": True,
                                    "block_hash": b.hash(),
                                    "block_height": b.header.height,
                                    "position": position,
                                    "outputs": len(tx.outputs),
                                    "total_output_sats": tx.total_output(),
                                    "timestamp": b.header.timestamp,
                                }
                            )
                            if len(confirmed) >= n:
                                break
                        if len(confirmed) >= n:
                            break
                    mempool = [
                        {
                            "txid": tx.txid(),
                            "wtxid": tx.wtxid(),
                            "confirmed": False,
                            "outputs": len(tx.outputs),
                            "total_output_sats": tx.total_output(),
                            "timestamp": int(node.chain.mempool_times.get(tx.txid(), time.time())),
                        }
                        for tx in reversed(node.chain.mempool[-n:])
                    ]
                    self.send_json({"confirmed": confirmed, "mempool": mempool, "limit": n})
                elif parsed.path == "/supply":
                    self.send_json(node.chain.supply_summary())
                elif parsed.path == "/emission":
                    summary = node.chain.supply_summary()
                    self.send_json(emission_report(int(summary["height"]), int(summary["total_minted_sats"])))
                elif parsed.path == "/p2p-hardening":
                    self.send_json(_p2p_hardening_snapshot())
                elif parsed.path.startswith("/esplora/"):
                    self._handle_esplora(parsed, node)
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
                elif parsed.path == "/peers/echo-addr":
                    self.send_json({"ok": True, "observed_ip": self.client_ip()})
                elif parsed.path == "/peers":
                    self.send_json(
                        {
                            "peers": sorted(node.peers),
                            "scores": node.peer_scores,
                            "banned": sorted(node.banned),
                        }
                    )
                elif parsed.path == "/utxos":
                    query = parse_qs(parsed.query)
                    address = query.get("address", [""])[0]
                    include_mempool_spent = query.get("include_mempool_spent", ["0"])[0].lower() in ("1", "true", "yes")
                    utxos = node.chain.utxos_for_address(address)
                    mempool_spent = {txin.outpoint() for tx in node.chain.mempool for txin in tx.inputs}
                    available = [
                        utxo for utxo in utxos if include_mempool_spent or utxo.outpoint() not in mempool_spent
                    ]
                    self.send_json(
                        {
                            "address": address,
                            "utxos": [utxo.to_dict() for utxo in available],
                            "excluded_mempool_spent": len(utxos) - len(available),
                        }
                    )
                else:
                    if (
                        os.environ.get("NETCOIN_APP_REQUIRE_ADMIN", "0") == "1"
                        and parsed.path.startswith(
                            (
                                "/admin",
                                "/api/admin",
                                "/merchant",
                                "/api/merchant",
                                "/wallet",
                                "/api/wallet",
                                "/custody",
                                "/api/custody",
                                "/security",
                                "/api/security",
                            )
                        )
                        and not self.require_app_admin()
                    ):
                        return
                    try:
                        status, payload, content_type = route_app_get(
                            app_store, node.chain, parsed.path, parse_qs(parsed.query), node=node
                        )
                    except AppError as app_exc:
                        if str(app_exc) == "not an app-layer route":
                            self.send_error_json("not found", status=404)
                        else:
                            self.send_error_json(str(app_exc), status=400)
                    else:
                        if content_type == "application/json":
                            self.send_json(payload, status=status)  # type: ignore[arg-type]
                        else:
                            self.send_text(
                                payload if isinstance(payload, bytes) else str(payload),
                                status=status,
                                content_type=content_type,
                            )
            except Exception as exc:
                self.send_error_json(str(exc), status=400)

        def client_ip(self) -> str:
            return client_ip_from_headers(self.headers, self.client_address, trust_proxy_headers=trust_proxy_headers)

        def require_node_admin(self) -> bool:
            expected = os.environ.get("NETCOIN_APP_ADMIN_TOKEN", "")
            provided = self.headers.get("X-Netcoin-Admin-Token", "") or self.headers.get("Authorization", "").replace(
                "Bearer ", "", 1
            )
            if expected and hmac.compare_digest(expected, provided):
                return True
            self.send_error_json("operator token required", status=401)
            return False

        def require_app_admin(self) -> bool:
            if os.environ.get("NETCOIN_APP_REQUIRE_ADMIN", "0") != "1":
                return True
            expected = os.environ.get("NETCOIN_APP_ADMIN_TOKEN", "")
            provided = self.headers.get("X-Netcoin-Admin-Token", "") or self.headers.get("Authorization", "").replace(
                "Bearer ", "", 1
            )
            if expected and hmac.compare_digest(expected, provided):
                return True
            self.send_error_json("admin token required", status=401)
            return False

        def app_api_key_from_headers(self) -> str:
            return self.headers.get("X-Netcoin-Api-Key", "") or self.headers.get("X-API-Key", "")

        def do_POST(self) -> None:
            parsed = self.canonical_parsed_url()
            # Per-IP, per-endpoint rate limiting for write/relay endpoints.
            if not self.enforce_rate_limit("POST", parsed.path):
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
                    self.send_json(
                        {"ok": True, "txids": txids, "count": len(txids), "relayed_to": delivered, "private": private}
                    )
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
                        self.send_json(
                            {"ok": False, "missing": missing_transactions(compact, node.chain.mempool)}, status=202
                        )
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
                        "/community/posts",
                        "/api/community/posts",
                        "/app/community/posts",
                        "/community/improvements",
                        "/api/community/improvements",
                        "/app/community/improvements",
                        "/community/reports",
                        "/api/community/reports",
                        "/app/community/reports",
                    } or (
                        parsed.path.startswith(
                            ("/community/improvements/", "/api/community/improvements/", "/app/community/improvements/")
                        )
                        and parsed.path.endswith("/vote")
                    )
                    if not public_app_write and not self.require_app_admin():
                        return
                    header_api_key = self.app_api_key_from_headers()
                    if header_api_key and "api_key" not in data:
                        data["api_key"] = header_api_key
                    data["__netcoin_http_request"] = True
                    if parsed.path in ("/keys/register", "/api/keys/register", "/app/keys/register"):
                        # Free self-service developer keys (NIP-0004), per-IP capped.
                        try:
                            self.send_json(app_store.register_public_api_key(data, self.client_address[0]))
                        except AppError as app_exc:
                            self.send_error_json(str(app_exc), status=429)
                        return
                    if (
                        os.environ.get("NETCOIN_APP_REQUIRE_API_KEY", "0") == "1"
                        and not public_app_write
                        and not app_store.check_api_key(data.get("api_key"))
                    ):
                        self.send_error_json(
                            "api key required: POST /api/keys/register for a free developer key, then send it as X-Netcoin-Api-Key",
                            status=401,
                        )
                        return
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
    peers: list[str] | None = None,
    advertise: str | None = None,
    sync_interval: int = 0,
    rate_limit_per_min: int = 240,
    p2p_port: int = DEFAULT_P2P_PORT,
    trust_proxy_headers: bool = False,
    bandwidth_mode: str | None = None,
) -> None:
    chain = Blockchain(data_dir=data_dir)
    node = NetCoinNode(
        chain,
        peers=peers or [],
        self_url=advertise,
        rate_limit_per_min=rate_limit_per_min,
        bandwidth_mode=bandwidth_mode,
    )

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

    sync_stop: Event | None = None
    sync_thread: Thread | None = None
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
