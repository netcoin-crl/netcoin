"""HTTP peer-to-peer node for NetCoin.

The transport is intentionally simple JSON over HTTP, but the exposed concepts are
Bitcoin-like: peer discovery, headers-first sync shape, block/transaction relay,
compact block summaries, mempool exchange, block templates, and orphan handling.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .block import Block
from .chain import Blockchain
from .compact import CompactBlock, make_compact_block, reconstruct_compact_block
from .logsetup import emit
from .params import (
    DEFAULT_NODE_PORT,
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
        self.relay_max_attempts = 3
        self.relay_backoff_seconds = 2.0
        self.started_at = time.time()
        self.peers_path = Path(peers_path) if peers_path else (Path(chain.data_dir) / "peers.json")
        self._load_banned()
        # Reload peers discovered on previous runs, then merge in any provided
        # via --peer so the node reconnects to known peers across restarts.
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
        for peer in data.get("banned", []):
            try:
                self.banned.add(self._normalize_peer(str(peer)))
            except NodeError:
                continue

    def _save_banned(self) -> None:
        if not self.persist:
            return
        try:
            self.banned_path.parent.mkdir(parents=True, exist_ok=True)
            self.banned_path.write_text(json.dumps({"banned": sorted(self.banned)}, indent=2, sort_keys=True))
        except OSError:
            pass

    def is_banned(self, peer: str) -> bool:
        try:
            return self._normalize_peer(peer) in self.banned
        except NodeError:
            return False

    def ban_peer(self, peer: str, reason: str = "") -> None:
        normalized = self._normalize_peer(peer)
        self.banned.add(normalized)
        self.peers.discard(normalized)
        self.peer_scores.pop(normalized, None)
        self._save_peers()
        self._save_banned()
        self.log_event("peer_banned", peer=normalized, reason=reason)

    def unban_peer(self, peer: str) -> bool:
        normalized = self._normalize_peer(peer)
        existed = normalized in self.banned
        self.banned.discard(normalized)
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
        if score <= self.ban_threshold:
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

    SERVICES = ["network", "headers", "compact-blocks", "mempool", "block-template", "explorer-api"]

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
        peer = peer.rstrip("/")
        try:
            remote = self.fetch_json(f"{peer}/info").get("node", {})
            if not self.compatible_peer(remote):
                return False
            if int(remote.get("height", 0)) <= self.chain.height():
                return False
            # Headers-first shape: inspect remote headers before full block download.
            self.fetch_json(f"{peer}/headers?start=0&limit=5000")
        except Exception:
            pass
        data = self.fetch_json(f"{peer}/chain")
        blocks = self.chain.import_chain_data(data)
        return self.chain.replace_chain(blocks)

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

    def accept_block(self, block: Block) -> str:
        self.log_event("block_received", hash=block.hash(), height=block.header.height)
        try:
            block_hash = self.chain.add_block(block)
        except Exception as exc:
            self.orphans[block.hash()] = block
            self.log_event("block_rejected", hash=block.hash(), reason=str(exc))
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


def make_handler(node: NetCoinNode):
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

        def send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_text(self, text: str, status: int = 200) -> None:
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_error_json(self, message: str, status: int = 400) -> None:
            self.send_json({"ok": False, "error": message}, status=status)

        def do_GET(self) -> None:  # noqa: N802 - stdlib method name
            parsed = urlparse(self.path)
            if not node.rate_limiter.allow((self.client_ip(), "GET", parsed.path)):
                self.send_error_json("rate limit exceeded", status=429)
                return
            try:
                if parsed.path in ("/", "/info"):
                    self.send_json({"ok": True, "node": node.info()})
                elif parsed.path == "/health":
                    self.send_json(node.health())
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
                    self.send_json(node.chain.export_chain())
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
                        self.send_json(block.to_dict() | {"hash": block.hash(), "weight": block.weight()})
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
                    self.send_json(node.chain.address_summary(address))
                elif parsed.path.startswith("/balance/"):
                    address = parsed.path.split("/", 2)[2]
                    self.send_json(node.chain.address_balance_summary(address))
                elif parsed.path == "/latest":
                    query = parse_qs(parsed.query)
                    n = max(1, min(int(query.get("n", [10])[0]), 100))
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
                    self.send_json({"height": node.chain.height(), "tip_hash": node.chain.tip_hash(), "blocks": blocks})
                elif parsed.path == "/blocktemplate":
                    query = parse_qs(parsed.query)
                    address = query.get("address", [None])[0]
                    self.send_json(node.chain.get_block_template(miner_address=address))
                elif parsed.path == "/mempool":
                    self.send_json(node.chain.export_mempool())
                elif parsed.path == "/peers":
                    self.send_json({
                        "peers": sorted(node.peers),
                        "scores": node.peer_scores,
                        "banned": sorted(node.banned),
                    })
                elif parsed.path == "/utxos":
                    query = parse_qs(parsed.query)
                    address = query.get("address", [""])[0]
                    utxos = [utxo.to_dict() for utxo in node.chain.utxos_for_address(address)]
                    self.send_json({"address": address, "utxos": utxos})
                else:
                    self.send_error_json("not found", status=404)
            except Exception as exc:
                self.send_error_json(str(exc), status=400)

        def client_ip(self) -> str:
            forwarded = self.headers.get("X-Forwarded-For", "")
            if forwarded:
                return forwarded.split(",", 1)[0].strip()
            return self.client_address[0] if self.client_address else "unknown"

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
                    node.log_event("tx_received", txid=txid)
                    delivered = node.broadcast_transaction(tx)
                    self.send_json({"ok": True, "txid": txid, "relayed_to": delivered})
                elif parsed.path in ("/block", "/submitblock"):
                    block = Block.from_dict(data)
                    block_hash = node.accept_block(block)
                    delivered = node.relay_new_blocks(block)
                    self.send_json({"ok": True, "block_hash": block_hash, "relayed_to": delivered})
                elif parsed.path == "/compact-block":
                    compact = CompactBlock.from_dict(data)
                    block = reconstruct_compact_block(compact, node.chain.mempool)
                    block_hash = node.accept_block(block)
                    delivered = node.relay_new_blocks(block)
                    self.send_json({"ok": True, "block_hash": block_hash, "relayed_to": delivered})
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
                    self.send_error_json("not found", status=404)
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
) -> None:
    chain = Blockchain(data_dir=data_dir)
    node = NetCoinNode(chain, peers=peers or [], self_url=advertise, rate_limit_per_min=rate_limit_per_min)
    result = node.bootstrap()
    sync_stop: Optional[Event] = None
    sync_thread: Optional[Thread] = None
    if sync_interval > 0:
        sync_stop, sync_thread = node.start_background_sync(sync_interval)
    server = ThreadingHTTPServer((host, port), make_handler(node))
    print(f"NetCoin node listening on http://{host}:{port}")
    if advertise:
        print(f"advertising as {advertise}")
    if sync_interval > 0:
        print(f"background sync every {sync_interval}s")
    print(f"peers={len(node.peers)} learned={result['learned']} adopted_chains={result['adopted_chains']}")
    print(f"height={chain.height()} tip={chain.tip_hash()}")
    try:
        server.serve_forever()
    finally:
        if sync_stop is not None:
            sync_stop.set()
        if sync_thread is not None:
            sync_thread.join(timeout=5)
        server.server_close()
