"""App-layer services for NetCoin payments, merchants, community tools, and dashboards.

These helpers deliberately live above consensus. They make NetCoin easier to use
without changing block validity rules: invoices, usernames, webhooks, gifts,
bounties, labels, statements, alerts, and dashboards are local operator state
stored next to the node data directory.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import html
import io
import ipaddress
import json
import os
import re
import secrets
import socket
import sqlite3
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import quote, urlencode, urlparse

from ..crypto import decode_address, validate_address, verify_message
from ..descriptors import DescriptorError, descriptor_to_address, multisig_descriptor
from ..emission import next_reduction_height
from ..params import (
    REWARD_REDUCTION_DENOMINATOR,
    REWARD_REDUCTION_INTERVAL,
    REWARD_REDUCTION_NUMERATOR,
    REWARD_SCHEDULE_ACTIVATION_HEIGHT,
)
from ..script import ScriptError, script_to_p2sh_address, timelocked_redeem_script
from ..tx import amount_to_sats, sats_to_amount
from ..feature_catalog import feature_catalog


class AppError(ValueError):
    """Raised when app-layer input is invalid."""


def assert_public_webhook_url(url: str) -> None:
    """SSRF guard: only allow https:// webhooks whose host resolves to public
    addresses. Blocks loopback/private/link-local/reserved targets so the node
    cannot be tricked into calling internal services (faucet, dashboard, other
    localhost apps) or the cloud metadata endpoint.

    Set ``NETCOIN_ALLOW_PRIVATE_WEBHOOKS=1`` to permit http/localhost/private
    targets for local development and tests. This must stay OFF in production."""
    allow_private = os.environ.get("NETCOIN_ALLOW_PRIVATE_WEBHOOKS") == "1"
    parsed = urlparse(str(url).strip())
    if parsed.scheme != "https" and not (allow_private and parsed.scheme == "http"):
        raise AppError("webhook URL must be https://")
    host = parsed.hostname
    if not host:
        raise AppError("webhook URL must include a host")
    if allow_private:
        return
    if host.lower() == "localhost" or host.lower().endswith((".local", ".internal", ".localhost")):
        raise AppError("webhook URL must point to a public host (SSRF blocked)")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise AppError(f"webhook host does not resolve: {exc}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise AppError("webhook URL must point to a public host (SSRF blocked)")


APP_SCHEMA_VERSION = 1
DEFAULT_APP_STATE: dict[str, Any] = {
    "schema_version": APP_SCHEMA_VERSION,
    "invoices": {},
    "payments": {},
    "usernames": {},
    "profiles": {},
    "known_labels": {},
    "merchants": {},
    "api_keys": {},
    "webhooks": {},
    "webhook_events": [],
    "refunds": {},
    "airdrops": {},
    "gifts": {},
    "bounties": {},
    "leaderboard_events": [],
    "wallet_categories": {},
    "wallet_alerts": {},
    "alert_events": [],
    "spending_limits": {},
    "wallet_spend_log": {},
    "team_wallets": {},
    "backup_health": {},
    "address_rotation": {},
    "rewards": {},
    "tip_buttons": {},
    "tokens": {},
    "token_events": [],
    "api_key_registrations": {},
    "api_usage": {},
    "app_idempotency_keys": {},
    "app_nonces": {},
    "immutable_audit_log": [],
    "rbac_roles": {},
    "csrf_sessions": {},
    "treasury_addresses": [],
    "treasury_proposals": {},
    "node_reports": [],
    "contract_templates": {},
    "contracts": {},
    "recurring_agreements": {},
    "escrows": {},
    "polls": {},
    "prediction_markets": {},
    "contract_events": [],
    "payout_signing_policy": {
        "mode": "manual_wallet_signing",
        "hot_wallet_enabled": False,
        "require_operator_review": True,
        "max_auto_broadcast_sats": 0,
        "updated_at": None,
    },
    "security_settings": {
        "prediction_markets_require_ack": False,
        "admin_token_required": False,
        "recommended_storage": "sqlite",
    },
    "admin_events": [],
    "operator_announcements": [],
    "community_posts": [],
    "community_comments": [],
    "community_votes": {},
    "community_improvements": {},
    "community_reports": [],
    "community_mod_actions": [],
}


def now() -> int:
    return int(time.time())


def _copy_default() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_APP_STATE))


def clean_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(9).replace('-', '').replace('_', '')[:12].lower()}"


def looks_like_sensitive_secret(text: str) -> bool:
    """Best-effort public-post guardrail for obvious secrets.

    Community posts are public testnet data. This rejects common accidental leaks
    such as seed phrases, private keys, API tokens, and long hex strings. It is
    not a replacement for moderation, but it prevents the most dangerous copy-
    paste mistakes.
    """
    lower = text.lower()
    dangerous_phrases = (
        "seed phrase",
        "recovery phrase",
        "private key",
        "privkey",
        "secret access key",
        "api key",
        "password:",
        "passphrase",
        "aws_secret_access_key",
        "authorization: bearer",
    )
    if any(phrase in lower for phrase in dangerous_phrases):
        return True
    compact = "".join(ch for ch in text if ch.strip())
    # 64+ hex characters can easily be a private key or token.
    hex_run = 0
    for ch in compact:
        if ch in "0123456789abcdefABCDEF":
            hex_run += 1
            if hex_run >= 64:
                return True
        else:
            hex_run = 0
    return False


def parse_amount_sats(value: Any, field: str = "amount") -> int:
    if isinstance(value, int):
        if value < 0:
            raise AppError(f"{field} must be non-negative")
        return value
    if isinstance(value, float):
        value = format(value, ".8f")
    try:
        sats = amount_to_sats(str(value))
    except Exception as exc:
        raise AppError(f"{field} must be a valid NET amount") from exc
    if sats < 0:
        raise AppError(f"{field} must be non-negative")
    return sats


def normalize_address(address: Any) -> str:
    value = str(address or "").strip()
    if not validate_address(value):
        raise AppError("address is not a valid NetCoin address")
    return value


def normalize_username(name: Any) -> str:
    value = str(name or "").strip().lower()
    if not value:
        raise AppError("username is required")
    if len(value) > 32:
        raise AppError("username is too long")
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    if any(ch not in allowed for ch in value):
        raise AppError("username may contain only letters, numbers, dash, and underscore")
    return value


def normalize_token_account(value: Any) -> str:
    """A token account is a NetCoin address or an @username handle."""
    account = str(value or "").strip()
    if not account:
        raise AppError("token account is required")
    if account.startswith("@"):
        return "@" + normalize_username(account[1:])
    return normalize_address(account)


def parse_token_units(value: Any, decimals: int, field: str = "amount", *, allow_zero: bool = False) -> int:
    """Parse a decimal token amount (whole-token notation) into integer base units."""
    text = str(value if value is not None else "").strip() or "0"
    try:
        whole, _, frac = text.partition(".")
        frac = frac.rstrip("0")
        if len(frac) > decimals:
            raise ValueError(f"more than {decimals} decimal places")
        units = int(whole or "0") * 10**decimals + (int(frac.ljust(decimals, "0")) if frac else 0)
    except ValueError as exc:
        raise AppError(f"invalid token {field}: {exc}") from exc
    if units < 0:
        raise AppError(f"token {field} cannot be negative")
    if not allow_zero and units == 0:
        raise AppError(f"token {field} must be greater than zero")
    if units > 10**24:
        raise AppError(f"token {field} is too large")
    return units


def format_token_amount(units: int, decimals: int) -> str:
    if decimals <= 0:
        return str(units)
    whole, frac = divmod(int(units), 10**decimals)
    return f"{whole}.{str(frac).zfill(decimals)}"


def payment_uri(address: str, amount_sats: int | None = None, label: str = "", message: str = "") -> str:
    query: dict[str, str] = {}
    if amount_sats is not None:
        query["amount"] = sats_to_amount(amount_sats)
    if label:
        query["label"] = label
    if message:
        query["message"] = message
    suffix = "?" + urlencode(query) if query else ""
    return f"netcoin:{address}{suffix}"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


SIGNED_ACTION_EXCLUDE_FIELDS = {"api_key", "signature", "signed_message", "message"}


def canonical_app_action(action: str, payload: dict[str, Any]) -> str:
    """Deterministic message that a wallet can sign for app-layer writes.

    App-layer state is not consensus, so the signature proves "the address owner
    asked this node to do this app action" rather than spending chain coins.
    """
    clean = {str(k): v for k, v in payload.items() if str(k) not in SIGNED_ACTION_EXCLUDE_FIELDS and v is not None}
    body = json.dumps(clean, sort_keys=True, separators=(",", ":"))
    return f"NetCoin app-layer action\nv1\n{action}\n{body}"


def app_signatures_required() -> bool:
    return os.environ.get("NETCOIN_APP_REQUIRE_SIGNATURES", "0").strip().lower() in {"1", "true", "yes", "on"}


def verify_app_action_signature(
    action: str, signer: str, payload: dict[str, Any], *, required: bool | None = None
) -> dict[str, Any]:
    """Verify an optional signed app-layer action.

    When ``required`` is true (or NETCOIN_APP_REQUIRE_SIGNATURES=1), missing or
    invalid signatures reject the write. When false, valid signatures are
    recorded and invalid/missing signatures leave legacy API behavior unchanged.
    """
    required = app_signatures_required() if required is None else required
    if signer.startswith("@"):
        if required:
            raise AppError("signed app-layer writes require a NetCoin address account, not an @username")
        return {"required": required, "verified": False, "reason": "username account"}
    signer = normalize_address(signer)
    expected = canonical_app_action(action, payload)
    message = str(payload.get("signed_message") or payload.get("message") or expected)
    signature = str(payload.get("signature") or "")
    if message != expected:
        if required:
            raise AppError("signed app-layer message does not match the action payload")
        return {"required": required, "verified": False, "reason": "message mismatch", "message": expected}
    if not signature:
        if required:
            raise AppError("signature is required for this app-layer action")
        return {"required": required, "verified": False, "reason": "missing signature", "message": expected}
    if not verify_message(signer, expected, signature):
        if required:
            raise AppError("signature does not verify for the app-layer signer")
        return {"required": required, "verified": False, "reason": "bad signature", "message": expected}
    return {"required": required, "verified": True, "signer": signer, "message": expected}


def app_html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; max-width: 860px; margin: 32px auto; padding: 0 16px; line-height: 1.45; }}
    .card {{ border: 1px solid #ddd; border-radius: 14px; padding: 18px; margin: 14px 0; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; word-break: break-all; }}
    input, textarea, button {{ font: inherit; padding: 10px; margin: 5px 0; }}
    input, textarea {{ width: min(100%, 680px); box-sizing: border-box; }}
    button, .button {{ background:#111; color:white; border:0; border-radius:10px; text-decoration:none; display:inline-block; padding:10px 14px; }}
    .muted {{ color:#666; }} .ok {{ color:#087f23; }} .warn {{ color:#9b5d00; }}
    table {{ width: 100%; border-collapse: collapse; }} th, td {{ border:1px solid #ddd; padding:8px; text-align:left; }}
  </style>
</head>
<body>{body}</body>
</html>"""


def simple_pdf(title: str, lines: list[str]) -> bytes:
    # Minimal single-page PDF generator with built-in Helvetica. Good enough for wallet statements/receipts.
    safe_lines = [str(title)] + [str(x) for x in lines]
    content_lines = ["BT", "/F1 12 Tf", "72 760 Td"]
    for i, line in enumerate(safe_lines[:42]):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if i:
            content_lines.append("0 -16 Td")
        content_lines.append(f"({escaped}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode())
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(out)


@dataclass
class ChainReceipt:
    txid: str
    confirmed: bool
    block_hash: str | None
    block_height: int | None
    confirmations: int
    outputs_to_address_sats: dict[str, int]
    total_output_sats: int
    timestamp: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "txid": self.txid,
            "confirmed": self.confirmed,
            "block_hash": self.block_hash,
            "block_height": self.block_height,
            "confirmations": self.confirmations,
            "outputs_to_address_sats": self.outputs_to_address_sats,
            "outputs_to_address": {k: sats_to_amount(v) for k, v in self.outputs_to_address_sats.items()},
            "total_output_sats": self.total_output_sats,
            "total_output": sats_to_amount(self.total_output_sats),
            "timestamp": self.timestamp,
        }


class AppStore:
    """Small app-layer database.

    SQLite is the default backend for safer app-layer state durability. JSON remains available with NETCOIN_APP_STORAGE=json for local demos and migration debugging.
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "app_layer.json"
        self.sqlite_path = self.data_dir / "app_layer.sqlite3"
        from .storage import normalize_storage_backend

        self.storage_backend = normalize_storage_backend(os.environ.get("NETCOIN_APP_STORAGE"))
        self.lock = RLock()

    def _sqlite_conn(self) -> sqlite3.Connection:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.sqlite_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at INTEGER NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL, payload TEXT NOT NULL, created_at INTEGER NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS app_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO app_migrations(version, name, applied_at) VALUES (?, ?, ?)",
            (APP_SCHEMA_VERSION, "initial_app_state_json_blob", now()),
        )
        return conn

    def _load_sqlite(self) -> dict[str, Any]:
        with self._sqlite_conn() as conn:
            row = conn.execute("SELECT value FROM app_state WHERE key = ?", ("state",)).fetchone()
            if row:
                return json.loads(row[0])
            # One-time JSON -> SQLite migration when a node operator flips NETCOIN_APP_STORAGE=sqlite.
            try:
                data = json.loads(self.path.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                data = _copy_default()
            conn.execute(
                "INSERT OR REPLACE INTO app_state(key, value, updated_at) VALUES (?, ?, ?)",
                ("state", json.dumps(data, sort_keys=True), now()),
            )
            conn.commit()
            return data

    def load(self) -> dict[str, Any]:
        with self.lock:
            if self.storage_backend in {"sqlite", "sqlite3"}:
                data = self._load_sqlite()
            else:
                try:
                    data = json.loads(self.path.read_text())
                except (FileNotFoundError, json.JSONDecodeError):
                    data = _copy_default()
            changed = False
            for key, value in DEFAULT_APP_STATE.items():
                if key not in data:
                    data[key] = json.loads(json.dumps(value))
                    changed = True
            if data.get("schema_version") != APP_SCHEMA_VERSION:
                data["schema_version"] = APP_SCHEMA_VERSION
                changed = True
            if changed:
                self.save(data)
            return data

    def save(self, data: dict[str, Any]) -> None:
        with self.lock:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            if self.storage_backend in {"sqlite", "sqlite3"}:
                with self._sqlite_conn() as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO app_state(key, value, updated_at) VALUES (?, ?, ?)",
                        ("state", json.dumps(data, indent=2, sort_keys=True), now()),
                    )
                    conn.commit()
                return
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
            tmp.replace(self.path)

    def audit(self, event: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        data = self.load()
        rec = {"event_id": clean_id("adm"), "event": event, "payload": payload, "created_at": now()}
        data.setdefault("admin_events", []).append(rec)
        data["admin_events"] = data.get("admin_events", [])[-1000:]
        self.save(data)
        if self.storage_backend in {"sqlite", "sqlite3"}:
            with self._sqlite_conn() as conn:
                conn.execute(
                    "INSERT INTO app_audit(event, payload, created_at) VALUES (?, ?, ?)",
                    (event, json.dumps(payload, sort_keys=True), rec["created_at"]),
                )
                conn.commit()

    # ----- security / custody policy -----
    def security_status(self) -> dict[str, Any]:
        data = self.load()
        security_settings = data.get("security_settings", DEFAULT_APP_STATE["security_settings"])
        return {
            "storage_backend": "sqlite" if self.storage_backend in {"sqlite", "sqlite3"} else "json",
            "storage_path": str(self.sqlite_path if self.storage_backend in {"sqlite", "sqlite3"} else self.path),
            "recommended_storage": security_settings.get("recommended_storage", "sqlite"),
            "admin_token_required": os.environ.get("NETCOIN_APP_REQUIRE_ADMIN", "0") == "1",
            "app_action_signatures_required": app_signatures_required(),
            "app_action_signature_mode": "required" if app_signatures_required() else "optional",
            "prediction_markets_require_ack": os.environ.get("NETCOIN_REQUIRE_MARKET_LEGAL_ACK", "0") == "1",
            "payout_signing_policy": data.get("payout_signing_policy", DEFAULT_APP_STATE["payout_signing_policy"]),
            "admin_event_count": len(data.get("admin_events", [])),
            "webhook_dead_letters": sum(1 for e in data.get("webhook_events", []) if e.get("dead_letter")),
            "idempotency_keys": len(data.get("app_idempotency_keys", {})),
            "app_nonce_scopes": len(data.get("app_nonces", {})),
            "migration_table": "app_migrations" if self.storage_backend in {"sqlite", "sqlite3"} else "json_mode",
        }

    def set_payout_signing_policy(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = str(payload.get("mode") or "manual_wallet_signing")[:80]
        hot_wallet = bool(payload.get("hot_wallet_enabled", False))
        if hot_wallet and not bool(payload.get("acknowledge_hot_wallet_risk", False)):
            raise AppError("hot-wallet signing requires acknowledge_hot_wallet_risk=true")
        data = self.load()
        policy = data.get("payout_signing_policy", DEFAULT_APP_STATE["payout_signing_policy"]).copy()
        policy.update(
            {
                "mode": mode,
                "hot_wallet_enabled": hot_wallet,
                "require_operator_review": bool(payload.get("require_operator_review", True)),
                "max_auto_broadcast_sats": parse_amount_sats(
                    payload.get("max_auto_broadcast_sats", payload.get("max_auto_broadcast", 0)), "max auto broadcast"
                ),
                "updated_at": now(),
                "notes": str(payload.get("notes") or "")[:500],
            }
        )
        data["payout_signing_policy"] = policy
        self.save(data)
        self.audit("security.payout_policy_updated", {"mode": mode, "hot_wallet_enabled": hot_wallet})
        return policy

    # ----- chain scans -----
    def receipts_for_txids(self, chain: Any, txids: Iterable[str]) -> list[ChainReceipt]:
        out: list[ChainReceipt] = []
        for txid in txids:
            found = chain.get_transaction(txid)
            if found is None:
                continue
            tx, block = found
            by_addr: dict[str, int] = {}
            for o in tx.outputs:
                if getattr(o, "address", ""):
                    by_addr[o.address] = by_addr.get(o.address, 0) + int(o.amount)
            height = block.header.height if block else None
            out.append(
                ChainReceipt(
                    txid=tx.txid(),
                    confirmed=block is not None,
                    block_hash=block.hash() if block else None,
                    block_height=height,
                    confirmations=max(0, chain.height() - int(height) + 1) if height is not None else 0,
                    outputs_to_address_sats=by_addr,
                    total_output_sats=tx.total_output(),
                    timestamp=(
                        block.header.timestamp
                        if block
                        else int(getattr(chain, "mempool_times", {}).get(tx.txid(), now()))
                    ),
                )
            )
        return out

    def scan_address_payments(self, chain: Any, address: str) -> list[ChainReceipt]:
        summary = chain.address_summary(address)
        txids = summary.get("transaction_ids", [])
        receipts = self.receipts_for_txids(chain, txids)
        mempool_ids: list[str] = []
        for tx in getattr(chain, "mempool", []):
            for o in tx.outputs:
                if getattr(o, "address", "") == address:
                    mempool_ids.append(tx.txid())
                    break
        receipts.extend(self.receipts_for_txids(chain, mempool_ids))
        # Deduplicate while preserving newest-ish order.
        seen: set[str] = set()
        uniq: list[ChainReceipt] = []
        for receipt in receipts:
            if receipt.txid in seen:
                continue
            seen.add(receipt.txid)
            uniq.append(receipt)
        return sorted(uniq, key=lambda item: (item.timestamp or 0, item.txid), reverse=True)

    # ----- payments / invoices -----
    def create_invoice(self, chain: Any, payload: dict[str, Any]) -> dict[str, Any]:
        address = normalize_address(
            payload.get("recipient_address") or payload.get("address") or payload.get("recipient")
        )
        amount_sats = parse_amount_sats(payload.get("amount_sats", payload.get("amount", 0)), "amount")
        if amount_sats <= 0:
            raise AppError("invoice amount must be greater than zero")
        created = now()
        expires_in = int(payload.get("expires_in_seconds", payload.get("expires_in", 3600)) or 3600)
        invoice_id = str(payload.get("invoice_id") or clean_id("inv"))
        memo = str(payload.get("memo") or payload.get("message") or "").strip()[:500]
        label = str(payload.get("label") or payload.get("customer") or "").strip()[:120]
        merchant_id = str(payload.get("merchant_id") or "default")[:80]
        invoice = {
            "invoice_id": invoice_id,
            "recipient_address": address,
            "amount_sats": amount_sats,
            "amount": sats_to_amount(amount_sats),
            "memo": memo,
            "label": label,
            "merchant_id": merchant_id,
            "order_id": str(payload.get("order_id") or "")[:120],
            "customer_note": str(payload.get("customer_note") or "")[:500],
            "status": "unpaid",
            "created_at": created,
            "created_height": int(chain.height()),
            "watch_from_height": int(chain.height()) + 1,
            "expires_at": created + max(60, expires_in),
            "confirmations_required": int(payload.get("confirmations_required", 1) or 1),
            "payment_uri": payment_uri(address, amount_sats, label=label or merchant_id, message=memo),
            "checkout_path": f"/checkout/{quote(invoice_id)}",
            "receipt_txid": None,
        }
        data = self.load()
        data["invoices"][invoice_id] = invoice
        data["payments"][invoice_id] = invoice
        data["leaderboard_events"].append(
            {
                "type": "invoice_created",
                "invoice_id": invoice_id,
                "merchant_id": merchant_id,
                "amount_sats": amount_sats,
                "t": created,
            }
        )
        self.save(data)
        return self.invoice_status(chain, invoice_id)

    def invoice_status(self, chain: Any, invoice_id: str) -> dict[str, Any]:
        data = self.load()
        invoice = data["invoices"].get(invoice_id)
        if not invoice:
            raise AppError("invoice not found")
        amount = int(invoice["amount_sats"])
        address = invoice["recipient_address"]
        receipts = self.scan_address_payments(chain, address)
        paid_confirmed = 0
        paid_pending = 0
        matching: list[dict[str, Any]] = []
        best_txid = None
        required = int(invoice.get("confirmations_required", 1) or 1)
        invoice_created_at = int(invoice.get("created_at", 0) or 0)
        invoice_created_height = int(invoice.get("created_height", invoice.get("watch_from_height", 0) - 1) or -1)
        for receipt in receipts:
            value = receipt.outputs_to_address_sats.get(address, 0)
            if value <= 0:
                continue
            # Only payments observed after invoice creation count toward this invoice.
            # Without this guard, a merchant reusing an address could have a new invoice
            # incorrectly marked paid by older deposits already present on-chain.
            if receipt.confirmed:
                if receipt.block_height is not None and receipt.block_height <= invoice_created_height:
                    continue
            elif receipt.timestamp is not None and receipt.timestamp < invoice_created_at:
                continue
            item = receipt.to_dict() | {"amount_to_invoice_sats": value, "amount_to_invoice": sats_to_amount(value)}
            matching.append(item)
            if receipt.confirmations >= required:
                paid_confirmed += value
            else:
                paid_pending += value
            if best_txid is None:
                best_txid = receipt.txid
        total_seen = paid_confirmed + paid_pending
        expired = now() > int(invoice.get("expires_at", 0) or 0)
        if paid_confirmed >= amount:
            status = "confirmed"
        elif total_seen >= amount:
            status = "pending"
        elif total_seen > 0:
            status = "underpaid"
        elif expired:
            status = "expired"
        else:
            status = "unpaid"
        overpaid_sats = max(0, total_seen - amount)
        underpaid_sats = max(0, amount - total_seen)
        invoice = invoice | {
            "status": status,
            "paid_confirmed_sats": paid_confirmed,
            "paid_pending_sats": paid_pending,
            "paid_total_sats": total_seen,
            "paid_total": sats_to_amount(total_seen),
            "underpaid_sats": underpaid_sats,
            "underpaid": sats_to_amount(underpaid_sats),
            "overpaid_sats": overpaid_sats,
            "overpaid": sats_to_amount(overpaid_sats),
            "receipt_txid": best_txid,
            "matching_transactions": matching,
        }
        previous_status = data["invoices"][invoice_id].get("status")
        data["invoices"][invoice_id].update({"status": status, "receipt_txid": best_txid})
        data["payments"][invoice_id] = data["invoices"][invoice_id]
        if previous_status != status:
            data["webhook_events"].append(
                {
                    "event_id": clean_id("evt"),
                    "event": "payment." + status,
                    "merchant_id": invoice.get("merchant_id", "default"),
                    "payload": {
                        "invoice_id": invoice_id,
                        "status": status,
                        "receipt_txid": best_txid,
                        "paid_total_sats": total_seen,
                    },
                    "created_at": now(),
                    "delivered": False,
                }
            )
            data["webhook_events"] = data["webhook_events"][-500:]
        self.save(data)
        return invoice

    def list_invoices(self, chain: Any, limit: int = 50, merchant_id: str | None = None) -> dict[str, Any]:
        data = self.load()
        items = list(data["invoices"].values())
        if merchant_id:
            items = [item for item in items if item.get("merchant_id") == merchant_id]
        items.sort(key=lambda item: int(item.get("created_at", 0)), reverse=True)
        invoices = []
        for item in items[: max(1, min(limit, 200))]:
            try:
                invoices.append(self.invoice_status(chain, item["invoice_id"]))
            except Exception:
                invoices.append(item)
        return {"invoices": invoices, "count": len(invoices), "total": len(items)}

    def receipt(self, chain: Any, txid: str) -> dict[str, Any]:
        receipts = self.receipts_for_txids(chain, [txid])
        if not receipts:
            raise AppError("transaction not found")
        data = self.load()
        linked = [inv for inv in data["invoices"].values() if inv.get("receipt_txid") == txid]
        return receipts[0].to_dict() | {"linked_invoices": linked}

    # ----- identity -----
    def upsert_username(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = normalize_username(payload.get("username") or payload.get("name"))
        address = normalize_address(payload.get("address"))
        data = self.load()
        existing = data["usernames"].get(name, {})
        record = existing | {
            "username": name,
            "address": address,
            "display_name": str(payload.get("display_name") or existing.get("display_name") or name)[:120],
            "bio": str(payload.get("bio") or existing.get("bio") or "")[:500],
            "verified": bool(payload.get("verified", existing.get("verified", False))),
            "merchant_id": str(payload.get("merchant_id") or existing.get("merchant_id") or "")[:80],
            "updated_at": now(),
            "created_at": existing.get("created_at", now()),
        }
        data["usernames"][name] = record
        data["profiles"][name] = data["profiles"].get(name, {}) | record
        self.save(data)
        return record

    def resolve_username(self, name: str) -> dict[str, Any]:
        record = self.load()["usernames"].get(normalize_username(name))
        if not record:
            raise AppError("username not found")
        return record

    # ----- merchant / webhooks -----
    def create_api_key(self, payload: dict[str, Any]) -> dict[str, Any]:
        merchant_id = str(payload.get("merchant_id") or "default")[:80]
        raw = "nck_" + secrets.token_urlsafe(24)
        key_id = clean_id("key")
        data = self.load()
        data["api_keys"][key_id] = {
            "key_id": key_id,
            "merchant_id": merchant_id,
            "key_hash": hashlib.sha256(raw.encode()).hexdigest(),
            "permissions": payload.get(
                "permissions", ["payments:create", "payments:read", "merchant:write", "webhooks:deliver"]
            ),
            "scopes": payload.get("scopes", ["merchant", "write"]),
            "created_at": now(),
            "last_used_at": None,
        }
        data["merchants"].setdefault(merchant_id, {"merchant_id": merchant_id, "created_at": now()})
        self.save(data)
        return {
            "key_id": key_id,
            "merchant_id": merchant_id,
            "api_key": raw,
            "warning": "Store this API key now. Only its hash is saved.",
        }

    def register_public_api_key(self, payload: dict[str, Any], client_ip: str) -> dict[str, Any]:
        """Free self-service developer key (NIP-0004 auth). Public reads stay
        open; writes need a key when NETCOIN_APP_REQUIRE_API_KEY=1. A per-IP
        daily cap keeps the open registration endpoint from minting unlimited
        spam identities."""
        app_name = str(payload.get("app") or payload.get("name") or "public")[:80]
        ip = str(client_ip or "unknown")[:64]
        data = self.load()
        regs = data.setdefault("api_key_registrations", {})
        cutoff = now() - 24 * 3600
        recent = [t for t in regs.get(ip, []) if t > cutoff]
        if len(recent) >= 10:
            raise AppError("API key registration limit reached for today; reuse the key you already have")
        raw = "nck_" + secrets.token_urlsafe(24)
        key_id = clean_id("key")
        data["api_keys"][key_id] = {
            "key_id": key_id,
            "merchant_id": app_name,
            "key_hash": hashlib.sha256(raw.encode()).hexdigest(),
            "permissions": ["app:write"],
            "self_service": True,
            "registered_ip": ip,
            "created_at": now(),
            "last_used_at": None,
        }
        regs[ip] = recent + [now()]
        # Bound the registration log so it cannot grow without limit.
        if len(regs) > 10_000:
            data["api_key_registrations"] = dict(sorted(regs.items(), key=lambda kv: max(kv[1] or [0]))[-5_000:])
        self.save(data)
        return {
            "key_id": key_id,
            "app": app_name,
            "api_key": raw,
            "warning": "Store this API key now. Only its hash is saved. Send it as the X-Netcoin-Api-Key header on write requests.",
        }

    def check_api_key(self, raw: Any) -> bool:
        """True if the presented key matches any stored key hash (self-service
        or merchant). Does not persist last-used to avoid a disk write per request."""
        candidate = str(raw or "")
        if not candidate:
            return False
        digest = hashlib.sha256(candidate.encode()).hexdigest()
        return any(hmac.compare_digest(rec.get("key_hash", ""), digest) for rec in self.load()["api_keys"].values())

    def _hash_idempotent_payload(self, action: str, payload: dict[str, Any]) -> str:
        clean = {
            str(k): v for k, v in payload.items() if str(k) not in {"api_key", "_idempotency_key", "idempotency_key"}
        }
        body = json.dumps({"action": action, "payload": clean}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode()).hexdigest()

    def idempotency_lookup(self, action: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Return a stored response for a repeated write with the same idempotency key.

        Clients may send `idempotency_key` in JSON or `Idempotency-Key` at the
        HTTP layer (the explorer server maps the header into `_idempotency_key`).
        A reused key with a different body is rejected to prevent accidental
        replay of a different action.
        """
        key = str(payload.get("_idempotency_key") or payload.get("idempotency_key") or "").strip()
        if not key:
            return None
        if len(key) > 120:
            raise AppError("idempotency key is too long")
        data = self.load()
        records = data.setdefault("app_idempotency_keys", {})
        rec = records.get(key)
        if not rec:
            return None
        request_hash = self._hash_idempotent_payload(action, payload)
        if not hmac.compare_digest(str(rec.get("request_hash", "")), request_hash):
            raise AppError("idempotency key was already used with a different request body")
        return {
            "status": int(rec.get("status", 200)),
            "response": rec.get("response", {}),
            "idempotent_replay": True,
            "idempotency_key": key,
        }

    def idempotency_store(self, action: str, payload: dict[str, Any], status: int, response: dict[str, Any]) -> None:
        key = str(payload.get("_idempotency_key") or payload.get("idempotency_key") or "").strip()
        if not key:
            return
        data = self.load()
        records = data.setdefault("app_idempotency_keys", {})
        records[key] = {
            "idempotency_key": key,
            "action": action,
            "request_hash": self._hash_idempotent_payload(action, payload),
            "status": int(status),
            "response": response,
            "created_at": now(),
        }
        # Retain recent keys only. Idempotency is an operational protection, not
        # an immutable audit log.
        if len(records) > 5000:
            data["app_idempotency_keys"] = dict(
                sorted(records.items(), key=lambda kv: kv[1].get("created_at", 0))[-2500:]
            )
        self.save(data)

    def enforce_app_nonce(self, action: str, payload: dict[str, Any]) -> None:
        """Optional replay protection for signed app-layer writes.

        Set NETCOIN_APP_REQUIRE_NONCE=1 to require a per-signer monotonic nonce.
        The signer is detected from common account fields. Clients may also send
        require_nonce=true during testing to enforce it for one request.
        """
        require = os.environ.get("NETCOIN_APP_REQUIRE_NONCE", "0").lower() in {"1", "true", "yes", "on"} or bool(
            payload.get("require_nonce")
        )
        nonce_value = payload.get("app_nonce", payload.get("nonce"))
        signer = str(
            payload.get("signer")
            or payload.get("address")
            or payload.get("creator")
            or payload.get("from")
            or payload.get("sender")
            or payload.get("trader_address")
            or payload.get("trader")
            or payload.get("merchant_id")
            or ""
        ).strip()
        if not require and nonce_value in (None, ""):
            return
        if not signer:
            raise AppError("app nonce requires a signer/account field")
        try:
            nonce = int(nonce_value)
        except (TypeError, ValueError) as exc:
            raise AppError("app nonce must be an integer") from exc
        if nonce <= 0:
            raise AppError("app nonce must be positive")
        data = self.load()
        nonces = data.setdefault("app_nonces", {})
        scoped = f"{signer}:{action}"
        last = int(nonces.get(scoped, 0) or 0)
        if nonce <= last:
            raise AppError("app nonce was already used or is not greater than the last nonce")
        nonces[scoped] = nonce
        self.save(data)

    def record_api_usage(self, payload: dict[str, Any], action: str, status: int) -> None:
        raw = str(payload.get("api_key") or "")
        if not raw:
            return
        digest = hashlib.sha256(raw.encode()).hexdigest()
        data = self.load()
        matched_id = None
        for key_id, rec in data.get("api_keys", {}).items():
            if hmac.compare_digest(str(rec.get("key_hash", "")), digest):
                matched_id = key_id
                break
        if not matched_id:
            return
        usage = data.setdefault("api_usage", {}).setdefault(
            matched_id, {"key_id": matched_id, "total": 0, "by_action": {}, "last_used_at": None}
        )
        usage["total"] = int(usage.get("total", 0) or 0) + 1
        usage["last_used_at"] = now()
        action_row = usage.setdefault("by_action", {}).setdefault(
            action, {"count": 0, "last_status": None, "last_used_at": None}
        )
        action_row["count"] = int(action_row.get("count", 0) or 0) + 1
        action_row["last_status"] = int(status)
        action_row["last_used_at"] = now()
        self.save(data)

    def api_usage_report(self) -> dict[str, Any]:
        data = self.load()
        rows = []
        for key_id, usage in data.get("api_usage", {}).items():
            rec = data.get("api_keys", {}).get(key_id, {})
            rows.append(
                {
                    "key_id": key_id,
                    "merchant_id": rec.get("merchant_id"),
                    "total": int(usage.get("total", 0) or 0),
                    "last_used_at": usage.get("last_used_at"),
                    "by_action": usage.get("by_action", {}),
                }
            )
        rows.sort(key=lambda r: (-(r.get("total") or 0), str(r.get("key_id"))))
        return {"api_usage": rows, "count": len(rows)}

    def append_immutable_audit(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        previous = (
            data.setdefault("immutable_audit_log", [])[-1]["hash"] if data.get("immutable_audit_log") else "0" * 64
        )
        rec = {"event": event, "payload": payload, "created_at": now(), "previous_hash": previous}
        rec_hash = hashlib.sha256(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        rec["hash"] = rec_hash
        data.setdefault("immutable_audit_log", []).append(rec)
        data["immutable_audit_log"] = data["immutable_audit_log"][-5000:]
        self.save(data)
        return rec

    def assign_role(self, payload: dict[str, Any]) -> dict[str, Any]:
        principal = str(payload.get("principal") or payload.get("address") or "").strip()
        role = str(payload.get("role") or "auditor").strip()
        if not principal:
            raise AppError("principal is required")
        data = self.load()
        roles = data.setdefault("rbac_roles", {}).setdefault(principal, [])
        if role not in roles:
            roles.append(role)
        self.save(data)
        return {"principal": principal, "roles": roles}

    def require_role(self, principal: str, allowed: set[str]) -> bool:
        roles = set(self.load().get("rbac_roles", {}).get(principal, []))
        return bool(roles & allowed or "admin" in roles)

    def register_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        merchant_id = str(payload.get("merchant_id") or "default")[:80]
        url = str(payload.get("url") or payload.get("webhook_url") or "").strip()
        assert_public_webhook_url(url)  # SSRF guard: public https hosts only
        secret = str(payload.get("secret") or secrets.token_urlsafe(24))
        hook_id = str(payload.get("webhook_id") or clean_id("wh"))
        record = {
            "webhook_id": hook_id,
            "merchant_id": merchant_id,
            "url": url,
            "events": payload.get("events", ["payment.confirmed", "payment.pending", "payment.expired"]),
            "secret_hash": hashlib.sha256(secret.encode()).hexdigest(),
            "secret": secret,
            "created_at": now(),
            "active": bool(payload.get("active", True)),
            "max_attempts": int(payload.get("max_attempts", 8) or 8),
            "backoff_seconds": int(payload.get("backoff_seconds", 60) or 60),
        }
        data = self.load()
        data["webhooks"][hook_id] = record
        self.save(data)
        self.audit("merchant.webhook_registered", {"merchant_id": merchant_id, "webhook_id": hook_id})
        return record | {
            "secret": secret,
            "warning": "Store and protect this webhook secret. It is retained locally so NetCoin can sign webhook deliveries.",
        }

    def queue_webhook_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        event = {
            "event_id": clean_id("evt"),
            "event": str(payload.get("event") or "payment.updated"),
            "merchant_id": str(payload.get("merchant_id") or "default")[:80],
            "payload": payload.get("payload", {}),
            "created_at": now(),
            "delivered": False,
        }
        body = json.dumps(event["payload"], sort_keys=True, separators=(",", ":"))
        event["signature_preview"] = hmac.new(b"webhook-secret", body.encode(), hashlib.sha256).hexdigest()
        data["webhook_events"].append(event)
        data["webhook_events"] = data["webhook_events"][-500:]
        self.save(data)
        return event

    def record_refund(self, payload: dict[str, Any]) -> dict[str, Any]:
        refund_id = str(payload.get("refund_id") or clean_id("ref"))
        amount_sats = parse_amount_sats(payload.get("amount_sats", payload.get("amount", 0)), "refund amount")
        to_address = normalize_address(payload.get("to_address") or payload.get("address"))
        record = {
            "refund_id": refund_id,
            "invoice_id": str(payload.get("invoice_id") or ""),
            "original_txid": str(payload.get("txid") or payload.get("original_txid") or ""),
            "to_address": to_address,
            "amount_sats": amount_sats,
            "amount": sats_to_amount(amount_sats),
            "reason": str(payload.get("reason") or "")[:250],
            "status": str(payload.get("status") or "recorded"),
            "refund_txid": str(payload.get("refund_txid") or ""),
            "created_at": now(),
        }
        data = self.load()
        data["refunds"][refund_id] = record
        self.save(data)
        return record

    def invoices_csv(self, chain: Any, merchant_id: str | None = None) -> str:
        invoices = self.list_invoices(chain, limit=200, merchant_id=merchant_id)["invoices"]
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "invoice_id",
                "created_at",
                "expires_at",
                "merchant_id",
                "order_id",
                "amount",
                "status",
                "paid_total",
                "receipt_txid",
                "memo",
            ],
        )
        writer.writeheader()
        for inv in invoices:
            writer.writerow({k: inv.get(k, "") for k in writer.fieldnames})
        return buf.getvalue()

    def merchant_requires_api_key(self, merchant_id: str) -> bool:
        merchant = self.load().get("merchants", {}).get(merchant_id, {})
        return bool(merchant.get("api_key_required", False))

    def set_api_key_enforcement(self, payload: dict[str, Any]) -> dict[str, Any]:
        merchant_id = str(payload.get("merchant_id") or "default")[:80]
        data = self.load()
        merchant = data["merchants"].setdefault(merchant_id, {"merchant_id": merchant_id, "created_at": now()})
        merchant["api_key_required"] = bool(payload.get("required", True))
        merchant["updated_at"] = now()
        self.save(data)
        return {"merchant_id": merchant_id, "api_key_required": merchant["api_key_required"]}

    def verify_api_key(
        self, raw_key: str, merchant_id: str | None = None, permission: str | None = None
    ) -> dict[str, Any]:
        if not raw_key:
            raise AppError("merchant API key is required")
        digest = hashlib.sha256(raw_key.encode()).hexdigest()
        data = self.load()
        for rec in data.get("api_keys", {}).values():
            if not hmac.compare_digest(str(rec.get("key_hash", "")), digest):
                continue
            if merchant_id and rec.get("merchant_id") != merchant_id:
                raise AppError("merchant API key does not match merchant")
            if (
                permission
                and permission not in set(rec.get("permissions", []))
                and "*" not in set(rec.get("permissions", []))
            ):
                raise AppError("merchant API key is missing permission")
            rec["last_used_at"] = now()
            self.save(data)
            return {k: v for k, v in rec.items() if k != "key_hash"}
        raise AppError("merchant API key is invalid")

    def maybe_require_api_key(self, payload: dict[str, Any], merchant_id: str, permission: str | None = None) -> None:
        if self.merchant_requires_api_key(merchant_id):
            self.verify_api_key(str(payload.get("api_key") or ""), merchant_id=merchant_id, permission=permission)

    def deliver_webhook_events(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        max_events = max(1, min(int(payload.get("max_events", 20) or 20), 200))
        data = self.load()
        delivered = 0
        failed = 0
        skipped = 0
        attempts: list[dict[str, Any]] = []
        hooks = [h for h in data.get("webhooks", {}).values() if h.get("active", True)]
        current = now()
        for event in data.get("webhook_events", []):
            if delivered + failed >= max_events:
                break
            if event.get("delivered") and not payload.get("redeliver"):
                skipped += 1
                continue
            if event.get("dead_letter") and not payload.get("redeliver"):
                skipped += 1
                continue
            if int(event.get("next_attempt_at", 0) or 0) > current and not payload.get("force"):
                skipped += 1
                continue
            for hook in hooks:
                if delivered + failed >= max_events:
                    break
                if hook.get("merchant_id") != event.get("merchant_id"):
                    continue
                if event.get("event") not in set(hook.get("events", [])) and "*" not in set(hook.get("events", [])):
                    continue
                max_attempts = int(hook.get("max_attempts", 8) or 8)
                if int(event.get("attempt_count", 0) or 0) >= max_attempts and not payload.get("redeliver"):
                    event["dead_letter"] = True
                    event["dead_letter_at"] = current
                    skipped += 1
                    continue
                body = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
                secret = str(hook.get("secret") or "webhook-secret")
                sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
                req = urllib.request.Request(
                    str(hook["url"]),
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Netcoin-Event": str(event.get("event", "")),
                        "X-Netcoin-Delivery": str(event.get("event_id", "")),
                        "X-Netcoin-Signature": "sha256=" + sig,
                    },
                    method="POST",
                )
                attempt = {
                    "event_id": event.get("event_id"),
                    "webhook_id": hook.get("webhook_id"),
                    "url": hook.get("url"),
                    "attempted_at": current,
                }
                try:
                    # Re-check at delivery time so a stored hook (or DNS rebinding)
                    # can never reach an internal/private target.
                    assert_public_webhook_url(hook.get("url", ""))
                    with urllib.request.urlopen(req, timeout=float(payload.get("timeout", 3) or 3)) as resp:
                        attempt["status"] = int(resp.status)
                        attempt["ok"] = 200 <= int(resp.status) < 300
                except Exception as exc:
                    attempt["status"] = 0
                    attempt["ok"] = False
                    attempt["error"] = str(exc)[:300]
                event.setdefault("attempts", []).append(attempt)
                event["attempt_count"] = int(event.get("attempt_count", 0) or 0) + 1
                event["last_attempt_at"] = current
                attempts.append(attempt)
                if attempt["ok"]:
                    event["delivered"] = True
                    event["delivered_at"] = now()
                    event.pop("next_attempt_at", None)
                    delivered += 1
                else:
                    failed += 1
                    backoff = int(hook.get("backoff_seconds", 60) or 60)
                    event["next_attempt_at"] = current + min(
                        86400, backoff * (2 ** min(8, int(event.get("attempt_count", 1) - 1)))
                    )
                    if int(event.get("attempt_count", 0) or 0) >= max_attempts:
                        event["dead_letter"] = True
                        event["dead_letter_at"] = now()
        self.save(data)
        if attempts:
            self.audit(
                "merchant.webhook_delivery_batch", {"delivered": delivered, "failed": failed, "skipped": skipped}
            )
        return {"delivered": delivered, "failed": failed, "skipped": skipped, "attempts": attempts}

    def checkout_html(self, chain: Any, invoice_id: str) -> str:
        inv = self.invoice_status(chain, invoice_id)
        status_class = (
            "ok"
            if inv.get("status") == "confirmed"
            else "warn" if inv.get("status") in {"pending", "underpaid"} else "muted"
        )
        tx_link = (
            f"<p>Receipt: <a href='/receipt/{esc(inv.get('receipt_txid'))}'>{esc(inv.get('receipt_txid'))}</a></p>"
            if inv.get("receipt_txid")
            else ""
        )
        body = f"""<h1>NetCoin checkout</h1><div class=card>
<p>Status: <strong class='{status_class}'>{esc(inv.get('status'))}</strong></p>
<p>Amount due: <strong>{esc(inv.get('amount'))} NET</strong></p>
<p>Paid seen: <strong>{esc(inv.get('paid_total', '0'))} NET</strong></p>
<p>Memo: {esc(inv.get('memo',''))}</p>
<p>Pay to:</p><p class=mono>{esc(inv.get('recipient_address'))}</p>
<p><a class=button href='{esc(inv.get('payment_uri'))}'>Open wallet payment link</a></p>
<p class=mono>{esc(inv.get('payment_uri'))}</p>{tx_link}
</div><p class=muted>This page refreshes when reopened. API status is available at /api/checkout/{esc(invoice_id)}.</p>"""
        return app_html_page("NetCoin checkout", body)

    def profile_html(self, name: str) -> str:
        profile = self.resolve_username(name)
        uri = payment_uri(profile["address"], label=profile.get("display_name") or profile["username"])
        body = f"""<h1>{esc(profile.get('display_name') or profile['username'])}</h1>
<div class=card><p>{esc(profile.get('bio',''))}</p><p>Address:</p><p class=mono>{esc(profile['address'])}</p>
<p><a class=button href='{esc(uri)}'>Pay with NetCoin</a></p><p class=mono>{esc(uri)}</p>
<p class=muted>Verified: {esc(profile.get('verified', False))}</p></div>"""
        return app_html_page("NetCoin profile", body)

    def tip_html(self, name: str) -> str:
        profile = self.resolve_username(name)
        amt = ""
        uri = payment_uri(
            profile["address"],
            label="Tip " + (profile.get("display_name") or profile["username"]),
            message="NetCoin tip",
        )
        button = esc(
            self.tip_button(
                {
                    "username": profile["username"],
                    "address": profile["address"],
                    "label": "Tip " + (profile.get("display_name") or profile["username"]),
                }
            )["html"]
        )
        body = f"""<h1>Tip {esc(profile.get('display_name') or profile['username'])}</h1>
<div class=card><p>Send a NetCoin tip to:</p><p class=mono>{esc(profile['address'])}</p>
<p><a class=button href='{esc(uri)}'>Open payment link</a></p><p class=mono>{esc(uri)}</p></div>
<div class=card><h2>Embed button</h2><pre>{button}</pre></div>"""
        return app_html_page("Tip with NetCoin", body)

    def receipt_html(self, chain: Any, txid: str) -> str:
        rec = self.receipt(chain, txid)
        lines = "".join(
            f"<li>{esc(addr)}: {esc(amount)} NET</li>" for addr, amount in rec.get("outputs_to_address", {}).items()
        )
        body = f"""<h1>NetCoin receipt</h1><div class=card><p>Transaction:</p><p class=mono>{esc(txid)}</p>
<p>Confirmed: <strong>{esc(rec.get('confirmed'))}</strong></p><p>Confirmations: {esc(rec.get('confirmations'))}</p>
<p>Total output: {esc(rec.get('total_output'))} NET</p><ul>{lines}</ul>
<p><a class=button href='/api/receipt/{esc(txid)}'>View JSON receipt</a> <a class=button href='/api/receipt/{esc(txid)}.pdf'>Download PDF</a></p></div>"""
        return app_html_page("NetCoin receipt", body)

    def receipt_pdf(self, chain: Any, txid: str) -> bytes:
        rec = self.receipt(chain, txid)
        lines = [
            f"Transaction: {txid}",
            f"Confirmed: {rec.get('confirmed')}",
            f"Confirmations: {rec.get('confirmations')}",
            f"Block height: {rec.get('block_height')}",
            f"Total output: {rec.get('total_output')} NET",
        ]
        for addr, amount in rec.get("outputs_to_address", {}).items():
            lines.append(f"Output {addr}: {amount} NET")
        return simple_pdf("NetCoin transaction receipt", lines)

    def plan_payout(self, kind: str, outputs: list[dict[str, Any]], memo: str = "") -> dict[str, Any]:
        clean_outputs = []
        total = 0
        for out in outputs:
            address = normalize_address(out.get("address"))
            amount_sats = parse_amount_sats(out.get("amount_sats", out.get("amount", 0)), "payout amount")
            if amount_sats <= 0:
                raise AppError("payout amount must be greater than zero")
            total += amount_sats
            clean_outputs.append(
                {"address": address, "amount_sats": amount_sats, "amount": sats_to_amount(amount_sats)}
            )
        policy = self.load().get("payout_signing_policy", DEFAULT_APP_STATE["payout_signing_policy"])
        requires_review = bool(policy.get("require_operator_review", True)) or total > int(
            policy.get("max_auto_broadcast_sats", 0) or 0
        )
        return {
            "payout_id": clean_id("pay"),
            "kind": kind,
            "outputs": clean_outputs,
            "total_sats": total,
            "total": sats_to_amount(total),
            "memo": memo[:500],
            "status": "pending_operator_review" if requires_review else "ready_for_wallet_signing",
            "created_at": now(),
            "signing_policy": policy,
            "requires_operator_review": requires_review,
            "reviewed_by": None,
            "reviewed_at": None,
            "signed_at": None,
            "broadcast_txid": None,
            "operator_notes": [],
            "instructions": "Import this payout plan into a NetCoin wallet, review outputs, sign, and broadcast. Hot-wallet auto-broadcast is disabled unless an operator explicitly enables it in the signing policy.",
        }

    # ----- admin/operator dashboard and manual payout signing -----
    def _payout_plan_rows_from_data(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        def add(source_type: str, source_id: str, record: dict[str, Any], plan: dict[str, Any], path: str) -> None:
            if not isinstance(plan, dict) or not plan.get("payout_id"):
                return
            public_record = {
                k: v for k, v in record.items() if k not in {"payout_plan", "rows", "secret", "secret_hash", "key_hash"}
            }
            if len(json.dumps(public_record, default=str)) > 3000:
                public_record = {"summary": str(public_record)[:3000]}
            rows.append(
                {
                    **plan,
                    "source_type": source_type,
                    "source_id": source_id,
                    "source_status": record.get("status", ""),
                    "source_path": path,
                    "source_record": public_record,
                }
            )

        for rid, rec in data.get("refunds", {}).items():
            add("refund", rid, rec, rec.get("payout_plan", {}), f"refunds.{rid}.payout_plan")
        for aid, rec in data.get("airdrops", {}).items():
            add("airdrop", aid, rec, rec.get("payout_plan", {}), f"airdrops.{aid}.payout_plan")
        for gid, rec in data.get("gifts", {}).items():
            add("gift", gid, rec, rec.get("payout_plan", {}), f"gifts.{gid}.payout_plan")
        for bid, rec in data.get("bounties", {}).items():
            add("bounty", bid, rec, rec.get("payout_plan", {}), f"bounties.{bid}.payout_plan")
        for rid, rec in data.get("rewards", {}).items():
            add("reward", rid, rec, rec.get("payout_plan", {}), f"rewards.{rid}.payout_plan")
        for eid, rec in data.get("escrows", {}).items():
            add("escrow", eid, rec, rec.get("payout_plan", {}), f"escrows.{eid}.payout_plan")
        for mid, rec in data.get("prediction_markets", {}).items():
            add("prediction_market", mid, rec, rec.get("payout_plan", {}), f"prediction_markets.{mid}.payout_plan")
        for wid, wallet in data.get("team_wallets", {}).items():
            proposals = wallet.get("proposals", {})
            if isinstance(proposals, dict):
                proposal_items = proposals.items()
            else:
                proposal_items = (
                    (str(proposal.get("proposal_id") or index), proposal)
                    for index, proposal in enumerate(proposals or [])
                    if isinstance(proposal, dict)
                )
            for pid, proposal in proposal_items:
                add(
                    "team_wallet",
                    pid,
                    proposal,
                    proposal.get("payout_plan", {}),
                    f"team_wallets.{wid}.proposals.{pid}.payout_plan",
                )
        rows.sort(key=lambda x: int(x.get("created_at", 0) or 0), reverse=True)
        return rows

    def list_payout_plans(self, status: str | None = None) -> dict[str, Any]:
        rows = self._payout_plan_rows_from_data(self.load())
        if status:
            rows = [r for r in rows if r.get("status") == status]
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.get("status", "unknown")] = counts.get(row.get("status", "unknown"), 0) + 1
        return {"payout_plans": rows, "count": len(rows), "status_counts": counts}

    def get_payout_plan(self, payout_id: str) -> dict[str, Any]:
        for plan in self._payout_plan_rows_from_data(self.load()):
            if plan.get("payout_id") == payout_id:
                return plan
        raise AppError("payout plan not found")

    def _update_payout_plan(self, payout_id: str, updater: Any) -> dict[str, Any]:
        data = self.load()
        updated: dict[str, Any] | None = None

        def maybe_update(record: dict[str, Any]) -> bool:
            nonlocal updated
            plan = record.get("payout_plan")
            if isinstance(plan, dict) and plan.get("payout_id") == payout_id:
                updated_plan = updater(dict(plan))
                record["payout_plan"] = updated_plan
                updated = updated_plan
                return True
            return False

        for collection in ("refunds", "airdrops", "gifts", "bounties", "rewards", "escrows", "prediction_markets"):
            for record in data.get(collection, {}).values():
                if maybe_update(record):
                    self.save(data)
                    return self.get_payout_plan(payout_id)
        for wallet in data.get("team_wallets", {}).values():
            proposals = wallet.get("proposals", {})
            proposal_items = proposals.values() if isinstance(proposals, dict) else (proposals or [])
            for proposal in proposal_items:
                if isinstance(proposal, dict) and maybe_update(proposal):
                    self.save(data)
                    return self.get_payout_plan(payout_id)
        raise AppError("payout plan not found")

    def review_payout_plan(self, payout_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        approved = bool(payload.get("approved", True))
        reviewer = str(payload.get("reviewer") or payload.get("operator") or "operator")[:120]
        note = str(payload.get("notes") or payload.get("note") or "")[:500]

        def updater(plan: dict[str, Any]) -> dict[str, Any]:
            plan["reviewed_by"] = reviewer
            plan["reviewed_at"] = now()
            plan.setdefault("operator_notes", []).append(
                {"type": "review", "operator": reviewer, "note": note, "created_at": now(), "approved": approved}
            )
            plan["status"] = "ready_for_wallet_signing" if approved else "rejected"
            return plan

        updated = self._update_payout_plan(payout_id, updater)
        self.audit("payout.reviewed", {"payout_id": payout_id, "approved": approved, "reviewer": reviewer})
        return updated

    def reject_payout_plan(self, payout_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        payload["approved"] = False
        return self.review_payout_plan(payout_id, payload)

    def payout_signer_bundle(self, payout_id: str) -> dict[str, Any]:
        plan = self.get_payout_plan(payout_id)
        if plan.get("status") == "rejected":
            raise AppError("rejected payout plans cannot be exported for signing")
        bundle = {
            "bundle_version": 1,
            "created_at": now(),
            "network": os.environ.get("NETCOIN_NETWORK", "testnet"),
            "payout_plan": plan,
            "operator_checklist": [
                "Confirm every output address and amount against the source record.",
                "Confirm the total matches the approved payout amount.",
                "Import outputs into a trusted NetCoin wallet or offline signer.",
                "Sign only after review and keep the signed transaction artifact.",
                "Broadcast through your own node, then record the txid in the admin dashboard.",
            ],
            "wallet_import": {
                "outputs": plan.get("outputs", []),
                "memo": plan.get("memo", ""),
                "total_sats": plan.get("total_sats", 0),
                "total": plan.get("total", "0"),
            },
        }
        return bundle

    def record_signed_payout(self, payout_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        signer = str(payload.get("signer") or payload.get("operator") or "operator")[:120]
        signed_tx = str(payload.get("signed_tx") or payload.get("raw_tx") or "")
        signed_txid = str(payload.get("txid") or payload.get("signed_txid") or "")[:160]
        if not signed_tx and not signed_txid:
            raise AppError("signed_tx or txid is required")

        def updater(plan: dict[str, Any]) -> dict[str, Any]:
            if plan.get("status") == "rejected":
                raise AppError("cannot sign a rejected payout plan")
            plan["status"] = "signed_ready_to_broadcast"
            plan["signed_at"] = now()
            plan["signed_by"] = signer
            if signed_txid:
                plan["signed_txid"] = signed_txid
            if signed_tx:
                plan["signed_tx_sha256"] = hashlib.sha256(signed_tx.encode()).hexdigest()
                plan["signed_tx_preview"] = signed_tx[:80] + ("..." if len(signed_tx) > 80 else "")
            plan.setdefault("operator_notes", []).append(
                {"type": "signed", "operator": signer, "created_at": now(), "txid": signed_txid}
            )
            return plan

        updated = self._update_payout_plan(payout_id, updater)
        self.audit("payout.signed", {"payout_id": payout_id, "signer": signer, "txid": signed_txid})
        return updated

    def record_broadcasted_payout(self, payout_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        operator = str(payload.get("operator") or "operator")[:120]
        txid = str(payload.get("txid") or payload.get("broadcast_txid") or "").strip()
        if not txid:
            raise AppError("txid is required")

        def updater(plan: dict[str, Any]) -> dict[str, Any]:
            if plan.get("status") == "rejected":
                raise AppError("cannot broadcast a rejected payout plan")
            plan["status"] = "broadcast_recorded"
            plan["broadcast_txid"] = txid
            plan["broadcast_recorded_at"] = now()
            plan["broadcast_recorded_by"] = operator
            plan.setdefault("operator_notes", []).append(
                {"type": "broadcast", "operator": operator, "created_at": now(), "txid": txid}
            )
            return plan

        updated = self._update_payout_plan(payout_id, updater)
        self.audit("payout.broadcast_recorded", {"payout_id": payout_id, "operator": operator, "txid": txid})
        return updated

    def admin_summary(self, chain: Any, node: Any | None = None) -> dict[str, Any]:
        data = self.load()
        invoice_counts: dict[str, int] = {}
        for inv in data.get("invoices", {}).values():
            invoice_counts[inv.get("status", "unknown")] = invoice_counts.get(inv.get("status", "unknown"), 0) + 1
        payouts = self.list_payout_plans()
        webhook_events = data.get("webhook_events", [])
        alerts = data.get("alert_events", [])
        return {
            "node": {
                "height": chain.height(),
                "tip_hash": chain.tip_hash(),
                "mempool_size": len(getattr(chain, "mempool", [])),
                "peers": len(getattr(node, "peers", [])) if node is not None else 0,
            },
            "counts": {
                "invoices": len(data.get("invoices", {})),
                "invoice_statuses": invoice_counts,
                "webhooks": len(data.get("webhooks", {})),
                "webhook_events": len(webhook_events),
                "webhook_dead_letters": sum(1 for e in webhook_events if e.get("dead_letter")),
                "payout_plans": payouts["count"],
                "payout_statuses": payouts["status_counts"],
                "escrows": len(data.get("escrows", {})),
                "recurring_agreements": len(data.get("recurring_agreements", {})),
                "polls": len(data.get("polls", {})),
                "prediction_markets": len(data.get("prediction_markets", {})),
                "alerts_triggered": len(alerts),
                "admin_events": len(data.get("admin_events", [])),
            },
            "security": self.security_status(),
            "recent_admin_events": data.get("admin_events", [])[-20:],
            "recent_webhook_events": webhook_events[-20:],
        }

    def admin_dashboard_html(self) -> str:
        body = """<h1>NetCoin Admin Operator Dashboard</h1>
<div class=card><p>This protected dashboard uses the JSON APIs under <code>/api/admin/*</code>. Set <code>NETCOIN_APP_REQUIRE_ADMIN=1</code> and pass your token as <code>X-Netcoin-Admin-Token</code>.</p>
<p><a class=button href='/api/admin/summary'>Admin summary JSON</a> <a class=button href='/api/admin/payouts'>Payout plans JSON</a> <a class=button href='/api/security/status'>Security status</a></p></div>
<div class=card><h2>Manual payout signer flow</h2><ol><li>Review pending payout plans.</li><li>Export a signer bundle.</li><li>Sign with an offline or trusted NetCoin wallet.</li><li>Broadcast through your own node.</li><li>Record the txid back in the dashboard.</li></ol></div>
<p class=muted>For the full browser dashboard, deploy <code>webexplorer/public/admin.html</code> next to the explorer static app.</p>"""
        return app_html_page("NetCoin Admin", body)

    def create_refund_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = self.record_refund(payload)
        plan = self.plan_payout(
            "refund",
            [{"address": record["to_address"], "amount_sats": record["amount_sats"]}],
            memo=record.get("reason", ""),
        )
        data = self.load()
        data["refunds"][record["refund_id"]]["payout_plan"] = plan
        data["refunds"][record["refund_id"]]["status"] = "ready_for_wallet_signing"
        self.save(data)
        return data["refunds"][record["refund_id"]]

    # ----- community -----
    def airdrop(self, payload: dict[str, Any]) -> dict[str, Any]:
        addresses = payload.get("addresses") or []
        if isinstance(addresses, str):
            addresses = [a.strip() for a in addresses.replace("\n", ",").split(",") if a.strip()]
        amount_sats = parse_amount_sats(payload.get("amount_sats", payload.get("amount", 0)), "airdrop amount")
        rows = []
        seen: set[str] = set()
        for addr in addresses:
            valid = validate_address(str(addr).strip())
            duplicate = str(addr).strip() in seen
            seen.add(str(addr).strip())
            rows.append(
                {
                    "address": str(addr).strip(),
                    "valid": valid,
                    "duplicate": duplicate,
                    "amount_sats": amount_sats,
                    "amount": sats_to_amount(amount_sats),
                }
            )
        valid_rows = [r for r in rows if r["valid"] and not r["duplicate"]]
        dry_run = bool(payload.get("dry_run", True))
        record = {
            "airdrop_id": clean_id("air"),
            "dry_run": dry_run,
            "rows": rows,
            "valid_count": len(valid_rows),
            "invalid_count": len([r for r in rows if not r["valid"]]),
            "duplicate_count": len([r for r in rows if r["duplicate"]]),
            "total_sats": len(valid_rows) * amount_sats,
            "total": sats_to_amount(len(valid_rows) * amount_sats),
            "created_at": now(),
        }
        if not dry_run:
            record["payout_plan"] = self.plan_payout(
                "airdrop", valid_rows, memo=str(payload.get("memo") or "NetCoin airdrop")
            )
            record["status"] = "ready_for_wallet_signing"
        data = self.load()
        data["airdrops"][record["airdrop_id"]] = record
        self.save(data)
        return record

    # ----- app-layer tokens (NET-20 style indexed ledger, NOT a consensus change) -----
    # Tokens live entirely in the app-layer store: an indexed ledger keyed by
    # NetCoin address or @username. The base chain never validates them.

    def _find_token(self, data: dict[str, Any], token_ref: str) -> dict[str, Any]:
        ref = str(token_ref or "").strip()
        token = data["tokens"].get(ref)
        if token:
            return token
        for candidate in data["tokens"].values():
            if candidate["symbol"].lower() == ref.lower():
                return candidate
        raise AppError("token not found")

    def _token_event(self, data: dict[str, Any], token: dict[str, Any], kind: str, detail: dict[str, Any]) -> None:
        data["token_events"].append(
            {
                "event_id": clean_id("tev"),
                "token_id": token["token_id"],
                "symbol": token["symbol"],
                "kind": kind,
                "detail": detail,
                "created_at": now(),
            }
        )
        data["token_events"] = data["token_events"][-500:]

    def create_token(self, payload: dict[str, Any]) -> dict[str, Any]:
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{2,8}", symbol):
            raise AppError("token symbol must be 2-8 letters/digits")
        name = str(payload.get("name") or symbol).strip()[:80]
        decimals = int(payload.get("decimals", 8) or 0)
        if not 0 <= decimals <= 8:
            raise AppError("token decimals must be between 0 and 8")
        creator = normalize_token_account(payload.get("creator") or payload.get("creator_address"))
        initial_units = parse_token_units(payload.get("initial_supply", 0), decimals, "initial supply", allow_zero=True)
        max_units = parse_token_units(payload.get("max_supply", 0), decimals, "max supply", allow_zero=True)
        if max_units and initial_units > max_units:
            raise AppError("initial supply exceeds max supply")
        signature_status = verify_app_action_signature("tokens.create", creator, payload)
        data = self.load()
        for existing in data["tokens"].values():
            if existing["symbol"] == symbol:
                raise AppError("token symbol already exists")
        token = {
            "token_id": clean_id("tok"),
            "standard": "NET-20",
            "symbol": symbol,
            "name": name,
            "decimals": decimals,
            "creator": creator,
            "mintable": bool(payload.get("mintable", True)),
            "supply_units": initial_units,
            "max_supply_units": max_units,
            "balances": {creator: initial_units} if initial_units else {},
            "created_at": now(),
            "note": "App-layer indexed ledger. Not enforced by NetCoin consensus.",
        }
        data["tokens"][token["token_id"]] = token
        self._token_event(
            data,
            token,
            "create",
            {"creator": creator, "initial_units": initial_units, "signature_verified": signature_status["verified"]},
        )
        self.save(data)
        return token | {"signature": signature_status}

    def token_info(self, token_ref: str) -> dict[str, Any]:
        token = dict(self._find_token(self.load(), token_ref))
        token["holder_count"] = sum(1 for units in token["balances"].values() if units > 0)
        return token

    def list_tokens(self) -> dict[str, Any]:
        tokens = []
        for token in self.load()["tokens"].values():
            item = {k: v for k, v in token.items() if k != "balances"}
            item["holder_count"] = sum(1 for units in token["balances"].values() if units > 0)
            tokens.append(item)
        tokens.sort(key=lambda t: t["created_at"])
        return {"tokens": tokens, "count": len(tokens)}

    def token_balances(self, token_ref: str) -> dict[str, Any]:
        token = self._find_token(self.load(), token_ref)
        holders = sorted(
            (
                {"account": account, "units": units, "amount": format_token_amount(units, token["decimals"])}
                for account, units in token["balances"].items()
                if units > 0
            ),
            key=lambda h: (-h["units"], h["account"]),
        )
        return {
            "token_id": token["token_id"],
            "symbol": token["symbol"],
            "decimals": token["decimals"],
            "holders": holders,
            "holder_count": len(holders),
        }

    def token_balance_of(self, token_ref: str, account: str) -> dict[str, Any]:
        token = self._find_token(self.load(), token_ref)
        clean = normalize_token_account(account)
        units = int(token["balances"].get(clean, 0))
        return {
            "token_id": token["token_id"],
            "symbol": token["symbol"],
            "account": clean,
            "units": units,
            "amount": format_token_amount(units, token["decimals"]),
        }

    def token_events(self, token_ref: str | None = None, limit: int = 100) -> dict[str, Any]:
        events = self.load()["token_events"]
        if token_ref:
            token = self._find_token(self.load(), token_ref)
            events = [e for e in events if e["token_id"] == token["token_id"]]
        return {"events": events[-max(1, min(limit, 500)) :][::-1]}

    def mint_token(self, token_ref: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        token = self._find_token(data, token_ref)
        if not token.get("mintable"):
            raise AppError("token is not mintable")
        minter = normalize_token_account(payload.get("minter") or payload.get("creator"))
        if minter != token["creator"]:
            raise AppError("only the token creator may mint")
        signature_status = verify_app_action_signature("tokens.mint", minter, payload)
        to_account = normalize_token_account(payload.get("to") or minter)
        units = parse_token_units(payload.get("amount"), token["decimals"], "mint amount")
        if token["max_supply_units"] and token["supply_units"] + units > token["max_supply_units"]:
            raise AppError("mint would exceed max supply")
        token["supply_units"] += units
        token["balances"][to_account] = int(token["balances"].get(to_account, 0)) + units
        self._token_event(
            data, token, "mint", {"to": to_account, "units": units, "signature_verified": signature_status["verified"]}
        )
        self.save(data)
        return self.token_balance_of(token["token_id"], to_account) | {"signature": signature_status}

    def transfer_token(self, token_ref: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        token = self._find_token(data, token_ref)
        sender = normalize_token_account(payload.get("from") or payload.get("sender"))
        recipient = normalize_token_account(payload.get("to") or payload.get("recipient"))
        if sender == recipient:
            raise AppError("cannot transfer a token to the same account")
        signature_status = verify_app_action_signature("tokens.transfer", sender, payload)
        units = parse_token_units(payload.get("amount"), token["decimals"], "transfer amount")
        balance = int(token["balances"].get(sender, 0))
        if balance < units:
            raise AppError("insufficient token balance")
        token["balances"][sender] = balance - units
        token["balances"][recipient] = int(token["balances"].get(recipient, 0)) + units
        self._token_event(
            data,
            token,
            "transfer",
            {"from": sender, "to": recipient, "units": units, "signature_verified": signature_status["verified"]},
        )
        self.save(data)
        return {
            "token_id": token["token_id"],
            "symbol": token["symbol"],
            "from": self.token_balance_of(token["token_id"], sender),
            "to": self.token_balance_of(token["token_id"], recipient),
            "signature": signature_status,
        }

    def burn_token(self, token_ref: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        token = self._find_token(data, token_ref)
        account = normalize_token_account(payload.get("from") or payload.get("account"))
        signature_status = verify_app_action_signature("tokens.burn", account, payload)
        units = parse_token_units(payload.get("amount"), token["decimals"], "burn amount")
        balance = int(token["balances"].get(account, 0))
        if balance < units:
            raise AppError("insufficient token balance")
        token["balances"][account] = balance - units
        token["supply_units"] -= units
        self._token_event(
            data, token, "burn", {"from": account, "units": units, "signature_verified": signature_status["verified"]}
        )
        self.save(data)
        return self.token_balance_of(token["token_id"], account) | {"signature": signature_status}

    def create_gift(self, payload: dict[str, Any]) -> dict[str, Any]:
        amount_sats = parse_amount_sats(payload.get("amount_sats", payload.get("amount", 0)), "gift amount")
        code = str(payload.get("claim_code") or secrets.token_urlsafe(16))
        gift_id = clean_id("gift")
        record = {
            "gift_id": gift_id,
            "claim_code_hash": hashlib.sha256(code.encode()).hexdigest(),
            "amount_sats": amount_sats,
            "amount": sats_to_amount(amount_sats),
            "status": "unclaimed",
            "memo": str(payload.get("memo") or "")[:250],
            "created_at": now(),
            "expires_at": now() + int(payload.get("expires_in", 86400) or 86400),
            "claimed_by_address": None,
            "claim_txid": None,
            "funding_txid": str(payload.get("funding_txid") or ""),
            "funding_address": str(payload.get("funding_address") or ""),
            "funded": bool(payload.get("funded", bool(payload.get("funding_txid")))),
        }
        data = self.load()
        data["gifts"][gift_id] = record
        self.save(data)
        return record | {"claim_code": code, "claim_path": f"/gift/{quote(code)}"}

    def claim_gift(self, payload: dict[str, Any]) -> dict[str, Any]:
        code = str(payload.get("claim_code") or "")
        address = normalize_address(payload.get("address"))
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        data = self.load()
        for gift in data["gifts"].values():
            if gift.get("claim_code_hash") == code_hash:
                if gift.get("status") != "unclaimed":
                    raise AppError("gift already claimed or closed")
                if now() > int(gift.get("expires_at", 0)):
                    gift["status"] = "expired"
                    self.save(data)
                    raise AppError("gift expired")
                gift.update({"status": "claimed", "claimed_by_address": address, "claimed_at": now()})
                gift["payout_plan"] = self.plan_payout(
                    "gift",
                    [{"address": address, "amount_sats": gift["amount_sats"]}],
                    memo=gift.get("memo", "NetCoin gift"),
                )
                data["leaderboard_events"].append(
                    {"type": "gift_claimed", "address": address, "amount_sats": gift["amount_sats"], "t": now()}
                )
                self.save(data)
                return gift
        raise AppError("gift not found")

    def create_bounty(self, payload: dict[str, Any]) -> dict[str, Any]:
        bounty_id = str(payload.get("bounty_id") or clean_id("bty"))
        reward_sats = parse_amount_sats(
            payload.get("reward_sats", payload.get("reward", payload.get("amount", 0))), "bounty reward"
        )
        record = {
            "bounty_id": bounty_id,
            "title": str(payload.get("title") or "Untitled bounty")[:140],
            "description": str(payload.get("description") or "")[:2000],
            "reward_sats": reward_sats,
            "reward": sats_to_amount(reward_sats),
            "sponsor_address": str(payload.get("sponsor_address") or ""),
            "status": "open",
            "submissions": [],
            "winner_address": None,
            "payout_txid": None,
            "created_at": now(),
        }
        data = self.load()
        data["bounties"][bounty_id] = record
        self.save(data)
        return record

    def submit_bounty(self, bounty_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        bounty = data["bounties"].get(bounty_id)
        if not bounty:
            raise AppError("bounty not found")
        submission = {
            "submission_id": clean_id("sub"),
            "submitter": str(payload.get("submitter") or "")[:120],
            "address": str(payload.get("address") or "")[:140],
            "url": str(payload.get("url") or "")[:500],
            "note": str(payload.get("note") or "")[:1000],
            "created_at": now(),
        }
        bounty.setdefault("submissions", []).append(submission)
        self.save(data)
        return submission

    def award_bounty(self, bounty_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        bounty = data["bounties"].get(bounty_id)
        if not bounty:
            raise AppError("bounty not found")
        winner = normalize_address(payload.get("winner_address") or payload.get("address"))
        bounty.update(
            {
                "status": "awarded",
                "winner_address": winner,
                "payout_txid": str(payload.get("payout_txid") or ""),
                "awarded_at": now(),
            }
        )
        if not bounty.get("payout_txid"):
            bounty["payout_plan"] = self.plan_payout(
                "bounty",
                [{"address": winner, "amount_sats": bounty["reward_sats"]}],
                memo="Bounty payout: " + str(bounty.get("title", "")),
            )
            bounty["status"] = "ready_for_wallet_signing"
        data["leaderboard_events"].append(
            {"type": "bounty_awarded", "address": winner, "amount_sats": bounty["reward_sats"], "t": now()}
        )
        self.save(data)
        return bounty

    def leaderboards(self, chain: Any) -> dict[str, Any]:
        data = self.load()
        donors: dict[str, int] = {}
        earners: dict[str, int] = {}
        for event in data.get("leaderboard_events", []):
            address = event.get("address") or event.get("merchant_id") or event.get("invoice_id")
            if not address:
                continue
            amount = int(event.get("amount_sats", 0) or 0)
            if event.get("type") in {"gift_claimed", "bounty_awarded", "community_reward"}:
                earners[address] = earners.get(address, 0) + amount
            else:
                donors[address] = donors.get(address, 0) + amount
        miners: dict[str, int] = {}
        for block in chain.chain:
            if not block.transactions:
                continue
            for out in block.transactions[0].outputs:
                if out.address:
                    miners[out.address] = miners.get(out.address, 0) + int(out.amount)

        def top(mapping: dict[str, int], n: int = 20) -> list[dict[str, Any]]:
            rows = []
            for rank, (key, value) in enumerate(
                sorted(mapping.items(), key=lambda kv: kv[1], reverse=True)[:n], start=1
            ):
                rows.append(
                    {
                        "rank": rank,
                        "id": key,
                        "amount_sats": value,
                        "amount": sats_to_amount(value),
                        "short_id": key[:10] + "…" + key[-6:] if len(str(key)) > 18 else key,
                    }
                )
            return rows

        return {
            "top_miners": top(miners),
            "top_earners": top(earners),
            "top_donors": top(donors),
            "summary": {
                "miner_count": len(miners),
                "earner_count": len(earners),
                "donor_count": len(donors),
                "mined_sats": sum(miners.values()),
                "earned_sats": sum(earners.values()),
                "donated_sats": sum(donors.values()),
                "mined": sats_to_amount(sum(miners.values())),
                "earned": sats_to_amount(sum(earners.values())),
                "donated": sats_to_amount(sum(donors.values())),
            },
        }

    def create_reward(self, payload: dict[str, Any]) -> dict[str, Any]:
        reward_id = str(payload.get("reward_id") or clean_id("rew"))
        address = normalize_address(payload.get("address"))
        amount_sats = parse_amount_sats(payload.get("amount_sats", payload.get("amount", 0)), "reward amount")
        record = {
            "reward_id": reward_id,
            "address": address,
            "amount_sats": amount_sats,
            "amount": sats_to_amount(amount_sats),
            "reason": str(payload.get("reason") or "community reward")[:250],
            "status": str(payload.get("status") or "ready_for_wallet_signing"),
            "created_at": now(),
            "payout_txid": str(payload.get("payout_txid") or ""),
        }
        if not record["payout_txid"]:
            record["payout_plan"] = self.plan_payout(
                "reward", [{"address": address, "amount_sats": amount_sats}], memo=record["reason"]
            )
        data = self.load()
        data["rewards"][reward_id] = record
        data["leaderboard_events"].append(
            {"type": "community_reward", "address": address, "amount_sats": amount_sats, "t": now()}
        )
        self.save(data)
        return record

    def list_community_posts(self, limit: int = 50, sort: str = "hot") -> dict[str, Any]:
        return self.community_feed(sort=sort, limit=limit)

    def create_community_post(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "Anonymous")[:80].strip() or "Anonymous"
        message = str(payload.get("message") or "")[:1200].strip()
        if not message:
            raise AppError("message is required")
        if looks_like_sensitive_secret(message) or looks_like_sensitive_secret(name):
            raise AppError("public posts must not include private keys, seed phrases, passwords, or API secrets")
        category = str(payload.get("category") or "general")[:40].lower()
        if category not in {"general", "help", "mining", "wallet", "merchant", "ideas"}:
            category = "general"
        rec = {
            "post_id": clean_id("post"),
            "name": name,
            "message": message,
            "category": category,
            "address": str(payload.get("address") or "")[:140],
            "created_at": now(),
            "status": "visible",
        }
        data = self.load()
        data.setdefault("community_posts", []).append(rec)
        data["community_posts"] = data["community_posts"][-500:]
        self.save(data)
        return rec

    def vote_community_post(self, post_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        direction_raw = str(payload.get("direction") or payload.get("vote") or "up").lower()
        delta = -1 if direction_raw in {"down", "downvote", "-1", "negative"} else 1
        voter = str(payload.get("voter") or payload.get("address") or payload.get("session") or "anonymous")[:160]
        data = self.load()
        rec = next((p for p in data.get("community_posts", []) if p.get("post_id") == post_id), None)
        if not rec:
            raise AppError("community post not found")
        votes = data.setdefault("community_votes", {})
        key = f"post:{post_id}:{voter}"
        previous = int(votes.get(key, 0) or 0)
        score_delta = 0 if previous == delta else delta - previous
        if previous != delta:
            votes[key] = delta
        rec["score"] = int(rec.get("score", 0) or 0) + score_delta
        rec["upvotes"] = int(rec.get("upvotes", 0) or 0) + (1 if score_delta > 0 else 0)
        rec["downvotes"] = int(rec.get("downvotes", 0) or 0) + (1 if score_delta < 0 else 0)
        rec["updated_at"] = now()
        self.save(data)
        return rec

    def list_community_comments(self, post_id: str, limit: int = 100) -> dict[str, Any]:
        data = self.load()
        comments = [
            c
            for c in data.get("community_comments", [])
            if c.get("post_id") == post_id and c.get("status", "visible") == "visible"
        ]
        comments = comments[-max(1, min(int(limit), 300)) :]
        return {"post_id": post_id, "comments": comments, "count": len(comments)}

    def create_community_comment(self, post_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or payload.get("author") or "Anonymous")[:80].strip() or "Anonymous"
        message = str(payload.get("message") or payload.get("body") or "")[:1200].strip()
        if not message:
            raise AppError("comment is required")
        if looks_like_sensitive_secret(message) or looks_like_sensitive_secret(name):
            raise AppError("comments must not include private keys, seed phrases, passwords, or API secrets")
        data = self.load()
        if not any(p.get("post_id") == post_id for p in data.get("community_posts", [])):
            raise AppError("community post not found")
        rec = {
            "comment_id": clean_id("comment"),
            "post_id": post_id,
            "name": name,
            "message": message,
            "created_at": now(),
            "status": "visible",
        }
        data.setdefault("community_comments", []).append(rec)
        data["community_comments"] = data["community_comments"][-2000:]
        for post in data.get("community_posts", []):
            if post.get("post_id") == post_id:
                post["comment_count"] = int(post.get("comment_count", 0) or 0) + 1
                post["updated_at"] = now()
                break
        self.save(data)
        return rec

    def community_feed(self, sort: str = "hot", limit: int = 80) -> dict[str, Any]:
        data = self.load()
        posts = [p for p in data.get("community_posts", []) if p.get("status", "visible") == "visible"]
        counts: dict[str, int] = {}
        for comment in data.get("community_comments", []):
            if comment.get("status", "visible") == "visible":
                pid = str(comment.get("post_id") or "")
                counts[pid] = counts.get(pid, 0) + 1
        enriched = []
        current = now()
        for post in posts:
            item = dict(post)
            pid = str(item.get("post_id") or "")
            item["comment_count"] = counts.get(pid, int(item.get("comment_count", 0) or 0))
            age_hours = max(1.0, (current - int(item.get("created_at", current) or current)) / 3600)
            item["hot_score"] = round(
                (int(item.get("score", 0) or 0) + item["comment_count"] * 1.5) / (age_hours**0.35), 4
            )
            enriched.append(item)
        sort = (sort or "hot").lower()
        if sort == "new":
            enriched.sort(key=lambda x: int(x.get("created_at", 0) or 0), reverse=True)
        elif sort == "top":
            enriched.sort(
                key=lambda x: (int(x.get("score", 0) or 0), int(x.get("comment_count", 0) or 0)), reverse=True
            )
        else:
            enriched.sort(
                key=lambda x: (float(x.get("hot_score", 0) or 0), int(x.get("created_at", 0) or 0)), reverse=True
            )
        limit = max(1, min(int(limit), 200))
        return {"posts": enriched[:limit], "count": len(enriched), "sort": sort}

    def community_moderation_queue(self, limit: int = 100) -> dict[str, Any]:
        data = self.load()
        reports = list(data.get("community_reports", []))[-max(1, min(int(limit), 500)) :][::-1]
        posts = {p.get("post_id"): p for p in data.get("community_posts", [])}
        queue = []
        for report in reports:
            queue.append(
                {
                    "report": report,
                    "post": posts.get(report.get("post_id")),
                    "needs_review": report.get("status", "open") == "open",
                }
            )
        return {"queue": queue, "count": len(queue), "open_count": sum(1 for item in queue if item["needs_review"])}

    def moderate_community_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        target = str(payload.get("post_id") or payload.get("target") or "")[:160]
        action = str(payload.get("action") or "reviewed").lower()[:40]
        if action not in {"reviewed", "hide", "restore", "close_report"}:
            raise AppError("unsupported moderation action")
        data = self.load()
        changed = False
        for post in data.get("community_posts", []):
            if post.get("post_id") == target:
                if action == "hide":
                    post["status"] = "hidden"
                elif action == "restore":
                    post["status"] = "visible"
                changed = True
        for report in data.get("community_reports", []):
            if report.get("post_id") == target or report.get("report_id") == target:
                if action in {"reviewed", "close_report"}:
                    report["status"] = "closed"
                    changed = True
        if not changed:
            raise AppError("moderation target not found")
        rec = {
            "action_id": clean_id("mod"),
            "target": target,
            "action": action,
            "note": str(payload.get("note") or "")[:500],
            "created_at": now(),
        }
        data.setdefault("community_mod_actions", []).append(rec)
        data["community_mod_actions"] = data["community_mod_actions"][-1000:]
        self.save(data)
        return rec

    def list_community_reports(self, limit: int = 100) -> dict[str, Any]:
        data = self.load()
        reports = list(data.get("community_reports", []))[-max(1, min(int(limit), 500)) :]
        return {"reports": reports[::-1], "count": len(data.get("community_reports", []))}

    def create_community_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        reason = str(payload.get("reason") or "")[:800].strip()
        if not reason:
            raise AppError("reason is required")
        if looks_like_sensitive_secret(reason):
            raise AppError("reports must not include private keys, seed phrases, passwords, or API secrets")
        rec = {
            "report_id": clean_id("report"),
            "post_id": str(payload.get("post_id") or payload.get("target") or "")[:160],
            "reason": reason,
            "created_at": now(),
            "status": "open",
        }
        data = self.load()
        data.setdefault("community_reports", []).append(rec)
        data["community_reports"] = data["community_reports"][-1000:]
        self.save(data)
        return rec

    def list_improvements(self) -> dict[str, Any]:
        data = self.load()
        ideas = sorted(
            data.get("community_improvements", {}).values(),
            key=lambda x: (int(x.get("votes", 0)), int(x.get("created_at", 0))),
            reverse=True,
        )
        return {"improvements": ideas, "count": len(ideas)}

    def create_improvement(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title") or "")[:140].strip()
        if not title:
            raise AppError("title is required")
        description = str(payload.get("description") or payload.get("details") or "")[:2000].strip()
        author = str(payload.get("name") or payload.get("author") or "Anonymous")[:80].strip() or "Anonymous"
        if (
            looks_like_sensitive_secret(title)
            or looks_like_sensitive_secret(description)
            or looks_like_sensitive_secret(author)
        ):
            raise AppError("improvement ideas must not include private keys, seed phrases, passwords, or API secrets")
        rec = {
            "idea_id": clean_id("idea"),
            "title": title,
            "description": description,
            "name": author,
            "category": str(payload.get("category") or "general")[:50].strip() or "general",
            "status": "open",
            "votes": 0,
            "created_at": now(),
        }
        data = self.load()
        data.setdefault("community_improvements", {})[rec["idea_id"]] = rec
        self.save(data)
        return rec

    def vote_improvement(self, idea_id: str) -> dict[str, Any]:
        data = self.load()
        rec = data.get("community_improvements", {}).get(idea_id)
        if not rec:
            raise AppError("improvement idea not found")
        rec["votes"] = int(rec.get("votes", 0)) + 1
        self.save(data)
        return rec

    def tip_button(self, payload: dict[str, Any]) -> dict[str, Any]:
        address = normalize_address(payload.get("address"))
        label = str(payload.get("label") or payload.get("username") or "Tip with NetCoin")[:80]
        amount_sats = None
        if payload.get("amount") or payload.get("amount_sats"):
            amount_sats = parse_amount_sats(payload.get("amount_sats", payload.get("amount")), "tip amount")
        uri = payment_uri(
            address, amount_sats=amount_sats, label=label, message=str(payload.get("message") or "NetCoin tip")[:120]
        )
        html_snippet = f'<a href="{esc(uri)}" rel="noopener" style="display:inline-block;padding:10px 14px;border-radius:10px;background:#111;color:#fff;text-decoration:none">{esc(label)}</a>'
        button_id = str(payload.get("button_id") or clean_id("tip"))
        record = {
            "button_id": button_id,
            "address": address,
            "label": label,
            "payment_uri": uri,
            "html": html_snippet,
            "created_at": now(),
        }
        data = self.load()
        data["tip_buttons"][button_id] = record
        self.save(data)
        return record

    # ----- wallet support -----
    def set_category(self, payload: dict[str, Any]) -> dict[str, Any]:
        txid = str(payload.get("txid") or "")
        if not txid:
            raise AppError("txid is required")
        record = {
            "txid": txid,
            "category": str(payload.get("category") or "uncategorized")[:60],
            "note": str(payload.get("note") or "")[:500],
            "contact": str(payload.get("contact") or "")[:120],
            "updated_at": now(),
        }
        data = self.load()
        data["wallet_categories"][txid] = record
        self.save(data)
        return record

    def wallet_statement(self, chain: Any, address: str, month: str | None = None) -> dict[str, Any]:
        address = normalize_address(address)
        receipts = self.scan_address_payments(chain, address)
        data = self.load()
        rows = []
        incoming = 0
        for receipt in receipts:
            ts = receipt.timestamp or 0
            if month:
                import datetime as _dt

                m = _dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m") if ts else ""
                if m != month:
                    continue
            amount = receipt.outputs_to_address_sats.get(address, 0)
            incoming += amount
            rows.append(
                receipt.to_dict()
                | {
                    "amount_sats": amount,
                    "amount": sats_to_amount(amount),
                    "category": data["wallet_categories"].get(receipt.txid, {}).get("category", ""),
                }
            )
        bal = chain.address_balance_summary(address)
        return {
            "address": address,
            "month": month,
            "incoming_sats": incoming,
            "incoming": sats_to_amount(incoming),
            "closing_balance_sats": bal["total_sats"],
            "closing_balance": bal["total"],
            "transaction_count": len(rows),
            "transactions": rows,
        }

    def wallet_statement_csv(self, chain: Any, address: str, month: str | None = None) -> str:
        statement = self.wallet_statement(chain, address, month)
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf, fieldnames=["txid", "timestamp", "confirmed", "block_height", "amount", "confirmations", "category"]
        )
        writer.writeheader()
        for tx in statement["transactions"]:
            writer.writerow({k: tx.get(k, "") for k in writer.fieldnames})
        return buf.getvalue()

    def wallet_statement_pdf(self, chain: Any, address: str, month: str | None = None) -> bytes:
        st = self.wallet_statement(chain, address, month)
        lines = [
            f"Address: {st['address']}",
            f"Month: {st.get('month') or 'all'}",
            f"Incoming: {st['incoming']} NET",
            f"Closing balance: {st['closing_balance']} NET",
            f"Transactions: {st['transaction_count']}",
        ]
        for tx in st["transactions"][:30]:
            lines.append(
                f"{tx.get('txid')}  {tx.get('amount')} NET  conf={tx.get('confirmations')}  {tx.get('category','')}"
            )
        return simple_pdf("NetCoin wallet statement", lines)

    def upsert_alert(self, payload: dict[str, Any]) -> dict[str, Any]:
        alert_id = str(payload.get("alert_id") or clean_id("alrt"))
        address = normalize_address(payload.get("address"))
        record = {
            "alert_id": alert_id,
            "address": address,
            "kind": str(payload.get("kind") or "balance_changed")[:80],
            "threshold_sats": parse_amount_sats(
                payload.get("threshold_sats", payload.get("threshold", 0)), "threshold"
            ),
            "channel": str(payload.get("channel") or "local")[:80],
            "target": str(payload.get("target") or "")[:300],
            "active": bool(payload.get("active", True)),
            "created_at": now(),
        }
        data = self.load()
        data["wallet_alerts"][alert_id] = record
        self.save(data)
        return record

    def set_spending_limits(self, payload: dict[str, Any]) -> dict[str, Any]:
        wallet_id = str(payload.get("wallet_id") or payload.get("address") or "default")[:140]
        record = {
            "wallet_id": wallet_id,
            "single_tx_limit_sats": parse_amount_sats(
                payload.get("single_tx_limit_sats", payload.get("single_tx_limit", 0)), "single tx limit"
            ),
            "daily_limit_sats": parse_amount_sats(
                payload.get("daily_limit_sats", payload.get("daily_limit", 0)), "daily limit"
            ),
            "mode": str(payload.get("mode") or "daily")[:60],
            "require_backup": bool(payload.get("require_backup", False)),
            "require_typed_confirm": bool(
                payload.get("require_typed_confirm", str(payload.get("mode") or "daily") == "savings")
            ),
            "updated_at": now(),
        }
        record["single_tx_limit"] = sats_to_amount(record["single_tx_limit_sats"])
        record["daily_limit"] = sats_to_amount(record["daily_limit_sats"])
        data = self.load()
        data["spending_limits"][wallet_id] = record
        self.save(data)
        return record

    def check_spending_limits(self, payload: dict[str, Any]) -> dict[str, Any]:
        wallet_id = str(payload.get("wallet_id") or payload.get("address") or "default")[:140]
        amount_sats = parse_amount_sats(payload.get("amount_sats", payload.get("amount", 0)), "spend amount")
        fee_sats = parse_amount_sats(payload.get("fee_sats", payload.get("fee", 0)), "fee")
        total = amount_sats + fee_sats
        data = self.load()
        limits = (
            data.get("spending_limits", {}).get(wallet_id)
            or data.get("spending_limits", {}).get(str(payload.get("address") or ""))
            or {}
        )
        ok = True
        reasons: list[str] = []
        single = int(limits.get("single_tx_limit_sats", 0) or 0)
        if single and total > single:
            ok = False
            reasons.append("transaction exceeds single-transaction limit")
        day = time.strftime("%Y-%m-%d", time.gmtime())
        log_key = wallet_id + ":" + day
        spent_today = int(data.get("wallet_spend_log", {}).get(log_key, 0) or 0)
        daily = int(limits.get("daily_limit_sats", 0) or 0)
        if daily and spent_today + total > daily:
            ok = False
            reasons.append("transaction exceeds daily spending limit")
        if limits.get("require_backup"):
            backup = data.get("backup_health", {}).get(wallet_id, {})
            if not (backup.get("seed_verified") and backup.get("encrypted_export_saved")):
                ok = False
                reasons.append("backup must be verified before spending")
        return {
            "ok": ok,
            "reasons": reasons,
            "wallet_id": wallet_id,
            "total_sats": total,
            "total": sats_to_amount(total),
            "limits": limits,
            "spent_today_sats": spent_today,
            "spent_today": sats_to_amount(spent_today),
        }

    def record_wallet_spend(self, payload: dict[str, Any]) -> dict[str, Any]:
        wallet_id = str(payload.get("wallet_id") or payload.get("address") or "default")[:140]
        amount_sats = parse_amount_sats(payload.get("amount_sats", payload.get("amount", 0)), "spend amount")
        fee_sats = parse_amount_sats(payload.get("fee_sats", payload.get("fee", 0)), "fee")
        day = time.strftime("%Y-%m-%d", time.gmtime())
        log_key = wallet_id + ":" + day
        data = self.load()
        data.setdefault("wallet_spend_log", {})[log_key] = (
            int(data.setdefault("wallet_spend_log", {}).get(log_key, 0) or 0) + amount_sats + fee_sats
        )
        self.save(data)
        return {
            "wallet_id": wallet_id,
            "date": day,
            "spent_today_sats": data["wallet_spend_log"][log_key],
            "spent_today": sats_to_amount(data["wallet_spend_log"][log_key]),
        }

    def evaluate_alerts(self, chain: Any, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        data = self.load()
        events = []
        for alert in data.get("wallet_alerts", {}).values():
            if not alert.get("active", True):
                continue
            try:
                bal = chain.address_balance_summary(alert["address"])
            except Exception:
                continue
            balance = int(bal.get("total_sats", 0) or 0)
            threshold = int(alert.get("threshold_sats", 0) or 0)
            triggered = False
            if alert.get("kind") == "balance_below" and balance < threshold:
                triggered = True
            if alert.get("kind") == "balance_above" and balance > threshold:
                triggered = True
            if alert.get("kind") == "balance_changed":
                last = alert.get("last_balance_sats")
                triggered = last is not None and int(last) != balance
            alert["last_balance_sats"] = balance
            alert["last_checked_at"] = now()
            if triggered:
                event = {
                    "alert_id": alert["alert_id"],
                    "address": alert["address"],
                    "balance_sats": balance,
                    "balance": sats_to_amount(balance),
                    "kind": alert.get("kind"),
                    "created_at": now(),
                    "channel": alert.get("channel"),
                    "target": alert.get("target"),
                }
                data.setdefault("alert_events", []).append(event)
                events.append(event)
        data["alert_events"] = data.get("alert_events", [])[-500:]
        self.save(data)
        return {"triggered": len(events), "events": events, "all_events": data.get("alert_events", [])[-100:]}

    def set_backup_health(self, payload: dict[str, Any]) -> dict[str, Any]:
        wallet_id = str(payload.get("wallet_id") or payload.get("address") or "default")[:140]
        record = {
            "wallet_id": wallet_id,
            "last_backup_at": int(payload.get("last_backup_at", now()) or now()),
            "seed_verified": bool(payload.get("seed_verified", False)),
            "encrypted_export_saved": bool(payload.get("encrypted_export_saved", False)),
            "updated_at": now(),
        }
        data = self.load()
        data["backup_health"][wallet_id] = record
        self.save(data)
        return record

    def create_team_wallet(self, payload: dict[str, Any]) -> dict[str, Any]:
        wallet_id = str(payload.get("wallet_id") or clean_id("team"))
        record = {
            "wallet_id": wallet_id,
            "name": str(payload.get("name") or "Team wallet")[:120],
            "addresses": payload.get("addresses", []),
            "members": payload.get("members", []),
            "required_approvals": int(payload.get("required_approvals", 1) or 1),
            "proposals": [],
            "created_at": now(),
        }
        data = self.load()
        data["team_wallets"][wallet_id] = record
        self.save(data)
        return record

    def create_team_proposal(self, wallet_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        wallet = data.get("team_wallets", {}).get(wallet_id)
        if not wallet:
            raise AppError("team wallet not found")
        outputs = payload.get("outputs") or []
        if not outputs and payload.get("to_address"):
            outputs = [{"address": payload.get("to_address"), "amount": payload.get("amount", 0)}]
        plan = self.plan_payout("team_wallet", outputs, memo=str(payload.get("memo") or "team wallet proposal"))
        proposal = {
            "proposal_id": str(payload.get("proposal_id") or clean_id("prop")),
            "payout_plan": plan,
            "created_by": str(payload.get("created_by") or "")[:120],
            "approvals": [],
            "status": "pending_approval",
            "created_at": now(),
        }
        wallet.setdefault("proposals", []).append(proposal)
        self.save(data)
        return proposal

    def approve_team_proposal(self, wallet_id: str, proposal_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        wallet = data.get("team_wallets", {}).get(wallet_id)
        if not wallet:
            raise AppError("team wallet not found")
        signer = str(payload.get("member") or payload.get("signer") or "")[:120]
        if not signer:
            raise AppError("member/signer is required")
        for proposal in wallet.get("proposals", []):
            if proposal.get("proposal_id") != proposal_id:
                continue
            if signer not in proposal.setdefault("approvals", []):
                proposal["approvals"].append(signer)
            if len(proposal["approvals"]) >= int(wallet.get("required_approvals", 1) or 1):
                proposal["status"] = "approved_ready_for_signing"
            proposal["updated_at"] = now()
            self.save(data)
            return proposal
        raise AppError("proposal not found")

    def address_rotation_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        wallet_id = str(payload.get("wallet_id") or "default")[:140]
        address = normalize_address(payload.get("address"))
        data = self.load()
        bucket = data.setdefault("address_rotation", {}).setdefault(
            wallet_id, {"wallet_id": wallet_id, "addresses": []}
        )
        existing = next((x for x in bucket["addresses"] if x.get("address") == address), None)
        if existing:
            existing.update(
                {
                    "label": str(payload.get("label") or existing.get("label") or "")[:120],
                    "used": bool(payload.get("used", existing.get("used", False))),
                    "updated_at": now(),
                }
            )
            rec = existing
        else:
            rec = {
                "address": address,
                "label": str(payload.get("label") or "")[:120],
                "used": bool(payload.get("used", False)),
                "created_at": now(),
            }
            bucket["addresses"].append(rec)
        self.save(data)
        return rec | {"wallet_id": wallet_id}

    def next_receive_address(self, wallet_id: str) -> dict[str, Any]:
        bucket = self.load().get("address_rotation", {}).get(wallet_id, {"addresses": []})
        for rec in bucket.get("addresses", []):
            if not rec.get("used"):
                return rec | {"wallet_id": wallet_id}
        raise AppError("no unused receive address registered for this wallet")

    # ----- phase 7: contract templates, recurring payments, escrow, polls, markets -----
    def default_contract_templates(self) -> dict[str, Any]:
        return {
            "timelock": {
                "type": "timelock",
                "title": "Timelock",
                "description": "Lock NET until a block height, then allow the beneficiary key to spend.",
                "required_fields": ["public_key", "unlock_height", "amount"],
                "states": ["draft", "funding_ready", "funded", "unlockable", "settled", "canceled"],
            },
            "vesting": {
                "type": "vesting",
                "title": "Vesting schedule",
                "description": "Track scheduled releases over time for teams, grants, or treasury funds.",
                "required_fields": [
                    "beneficiary_address",
                    "total_amount",
                    "start_time",
                    "interval_seconds",
                    "installments",
                ],
                "states": ["draft", "active", "completed", "canceled"],
            },
            "multisig": {
                "type": "multisig",
                "title": "M-of-N multisig",
                "description": "Generate a descriptor, redeem script reference, and P2SH address requiring M signatures.",
                "required_fields": ["required_signatures", "public_keys"],
                "states": ["draft", "funding_ready", "funded", "settled", "canceled"],
            },
            "escrow_2_of_3": {
                "type": "escrow_2_of_3",
                "title": "2-of-3 escrow",
                "description": "Buyer, seller, and mediator hold funds in a 2-of-3 multisig deal.",
                "required_fields": ["buyer_pubkey", "seller_pubkey", "mediator_pubkey", "amount"],
                "states": ["created", "funding_ready", "funded", "disputed", "released", "refunded", "canceled"],
            },
            "recurring_payment": {
                "type": "recurring_payment",
                "title": "Recurring payment agreement",
                "description": "Non-custodial recurring invoice reminders that the payer approves each cycle.",
                "required_fields": ["payer_address", "recipient_address", "amount", "interval"],
                "states": ["active", "paused", "canceled", "completed"],
            },
            "poll": {
                "type": "poll",
                "title": "Signed-message poll",
                "description": "Community governance polls using signed wallet messages or optional on-chain anchoring.",
                "required_fields": ["title", "options"],
                "states": ["draft", "open", "closed", "finalized"],
            },
            "prediction_market": {
                "type": "prediction_market",
                "title": "Prediction market demo",
                "description": "Testnet/play-money YES/NO event markets with orders, positions, manual resolution, and payout plans.",
                "required_fields": ["question", "outcomes", "oracle"],
                "states": ["open", "closed", "resolved", "canceled"],
            },
        }

    def list_contract_templates(self) -> dict[str, Any]:
        data = self.load()
        templates = self.default_contract_templates()
        templates.update(data.get("contract_templates", {}))
        return {"templates": templates, "count": len(templates)}

    def _record_contract_event(self, data: dict[str, Any], event_type: str, payload: dict[str, Any]) -> None:
        data.setdefault("contract_events", []).append(
            {"event_id": clean_id("cevt"), "event": event_type, "payload": payload, "created_at": now()}
        )
        data["contract_events"] = data.get("contract_events", [])[-1000:]

    def _valid_pubkey_hex(self, value: Any, field: str = "public_key") -> str:
        text = str(value or "").strip()
        try:
            raw = bytes.fromhex(text)
        except ValueError as exc:
            raise AppError(f"{field} must be a hex public key") from exc
        if len(raw) not in (33, 65):
            raise AppError(f"{field} must be a compressed or uncompressed public key")
        return text

    def create_contract(self, payload: dict[str, Any]) -> dict[str, Any]:
        contract_type = str(payload.get("contract_type") or payload.get("type") or "").strip().lower()
        templates = self.default_contract_templates() | self.load().get("contract_templates", {})
        if contract_type not in templates:
            raise AppError("unknown contract template")
        contract_id = str(payload.get("contract_id") or clean_id("ctr"))
        terms = dict(payload.get("terms") or {})
        derived: dict[str, Any] = {}
        status = str(payload.get("status") or "draft")
        if contract_type == "timelock":
            pub = self._valid_pubkey_hex(payload.get("public_key") or terms.get("public_key"))
            unlock_height = int(payload.get("unlock_height", terms.get("unlock_height", 0)) or 0)
            if unlock_height <= 0:
                raise AppError("unlock_height must be positive")
            amount_sats = parse_amount_sats(
                payload.get("amount_sats", payload.get("amount", terms.get("amount", 0))), "amount"
            )
            redeem_script = timelocked_redeem_script(unlock_height, pub)
            derived = {
                "amount_sats": amount_sats,
                "amount": sats_to_amount(amount_sats),
                "redeem_script": redeem_script,
                "address": script_to_p2sh_address(redeem_script),
            }
            terms |= {"public_key": pub, "unlock_height": unlock_height}
            status = "funding_ready"
        elif contract_type == "multisig":
            pubs = [
                self._valid_pubkey_hex(x, "public_key")
                for x in (payload.get("public_keys") or terms.get("public_keys") or [])
            ]
            required = int(payload.get("required_signatures", terms.get("required_signatures", 0)) or 0)
            if not pubs or required <= 0:
                raise AppError("multisig requires public_keys and required_signatures")
            descriptor = multisig_descriptor(required, pubs)
            try:
                address = descriptor_to_address(descriptor)
            except (DescriptorError, ScriptError, ValueError) as exc:
                raise AppError(str(exc)) from exc
            derived = {"descriptor": descriptor, "address": address}
            terms |= {"public_keys": pubs, "required_signatures": required}
            status = "funding_ready"
        record = {
            "contract_id": contract_id,
            "contract_type": contract_type,
            "template": templates[contract_type],
            "creator_address": str(payload.get("creator_address") or "")[:140],
            "participants": payload.get("participants", []),
            "terms": terms,
            "derived": derived,
            "state": payload.get("state", {}),
            "status": status,
            "created_at": now(),
            "updated_at": now(),
        }
        data = self.load()
        data["contracts"][contract_id] = record
        self._record_contract_event(
            data, "contract.created", {"contract_id": contract_id, "contract_type": contract_type}
        )
        self.save(data)
        return record

    def transition_contract(self, contract_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        record = data.get("contracts", {}).get(contract_id)
        if not record:
            raise AppError("contract not found")
        next_status = str(payload.get("status") or payload.get("next_status") or "").strip()
        allowed = set(record.get("template", {}).get("states", [])) | {
            "draft",
            "active",
            "funded",
            "settled",
            "canceled",
        }
        if not next_status or next_status not in allowed:
            raise AppError("invalid contract status transition")
        record["status"] = next_status
        record["updated_at"] = now()
        record.setdefault("history", []).append(
            {"status": next_status, "note": str(payload.get("note") or "")[:300], "created_at": now()}
        )
        self._record_contract_event(data, "contract.transition", {"contract_id": contract_id, "status": next_status})
        self.save(data)
        return record

    def create_recurring_agreement(self, payload: dict[str, Any]) -> dict[str, Any]:
        payer = normalize_address(payload.get("payer_address") or payload.get("payer"))
        recipient = normalize_address(
            payload.get("recipient_address") or payload.get("recipient") or payload.get("address")
        )
        amount_sats = parse_amount_sats(payload.get("amount_sats", payload.get("amount", 0)), "amount")
        if amount_sats <= 0:
            raise AppError("recurring amount must be greater than zero")
        interval = str(payload.get("interval") or "monthly").lower()
        seconds_map = {"daily": 86400, "weekly": 604800, "monthly": 2592000, "quarterly": 7776000, "yearly": 31536000}
        interval_seconds = int(payload.get("interval_seconds", seconds_map.get(interval, 0)) or 0)
        if interval_seconds <= 0:
            raise AppError("interval must be daily, weekly, monthly, quarterly, yearly, or interval_seconds")
        start = int(payload.get("start_time", now()) or now())
        agreement_id = str(payload.get("agreement_id") or clean_id("rpa"))
        record = {
            "agreement_id": agreement_id,
            "payer_address": payer,
            "recipient_address": recipient,
            "amount_sats": amount_sats,
            "amount": sats_to_amount(amount_sats),
            "interval": interval,
            "interval_seconds": interval_seconds,
            "memo": str(payload.get("memo") or "")[:500],
            "label": str(payload.get("label") or "Recurring payment")[:120],
            "start_time": start,
            "next_due_at": int(payload.get("next_due_at", start) or start),
            "end_time": int(payload.get("end_time", 0) or 0) or None,
            "status": "active",
            "created_at": now(),
            "payments": [],
        }
        data = self.load()
        data["recurring_agreements"][agreement_id] = record
        self._record_contract_event(data, "recurring.created", {"agreement_id": agreement_id})
        self.save(data)
        return record

    def list_recurring_agreements(self) -> dict[str, Any]:
        items = list(self.load().get("recurring_agreements", {}).values())
        items.sort(key=lambda x: int(x.get("next_due_at", 0) or 0))
        return {
            "agreements": items,
            "count": len(items),
            "due": [x for x in items if x.get("status") == "active" and int(x.get("next_due_at", 0) or 0) <= now()],
        }

    def update_recurring_agreement(self, agreement_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        rec = data.get("recurring_agreements", {}).get(agreement_id)
        if not rec:
            raise AppError("recurring agreement not found")
        action = str(payload.get("action") or "").lower()
        if action in {"pause", "paused"}:
            rec["status"] = "paused"
        elif action in {"resume", "active"}:
            rec["status"] = "active"
        elif action in {"cancel", "canceled"}:
            rec["status"] = "canceled"
        elif action == "skip":
            rec["next_due_at"] = int(rec.get("next_due_at", now()) or now()) + int(rec.get("interval_seconds", 0) or 0)
        else:
            raise AppError("unknown recurring action")
        rec["updated_at"] = now()
        self._record_contract_event(data, "recurring.updated", {"agreement_id": agreement_id, "action": action})
        self.save(data)
        return rec

    def create_recurring_invoice(
        self, chain: Any, agreement_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        payload = payload or {}
        data = self.load()
        rec = data.get("recurring_agreements", {}).get(agreement_id)
        if not rec:
            raise AppError("recurring agreement not found")
        if rec.get("status") != "active":
            raise AppError("recurring agreement is not active")
        invoice = self.create_invoice(
            chain,
            {
                "address": rec["recipient_address"],
                "amount_sats": rec["amount_sats"],
                "memo": payload.get("memo") or rec.get("memo") or f"Recurring payment {agreement_id}",
                "label": rec.get("label") or "Recurring payment",
                "merchant_id": payload.get("merchant_id") or "recurring",
                "order_id": agreement_id,
                "expires_in_seconds": payload.get("expires_in_seconds", 86400),
            },
        )
        data = self.load()
        rec = data["recurring_agreements"][agreement_id]
        rec.setdefault("invoices", []).append(invoice["invoice_id"])
        rec["last_invoice_id"] = invoice["invoice_id"]
        rec["updated_at"] = now()
        self._record_contract_event(
            data, "recurring.invoice_created", {"agreement_id": agreement_id, "invoice_id": invoice["invoice_id"]}
        )
        self.save(data)
        return invoice | {"agreement_id": agreement_id}

    def record_recurring_payment(self, agreement_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        rec = data.get("recurring_agreements", {}).get(agreement_id)
        if not rec:
            raise AppError("recurring agreement not found")
        txid = str(payload.get("txid") or payload.get("payment_txid") or "").strip()
        if not txid:
            raise AppError("txid is required")
        item = {
            "txid": txid,
            "paid_at": int(payload.get("paid_at", now()) or now()),
            "amount_sats": int(payload.get("amount_sats", rec.get("amount_sats", 0)) or 0),
        }
        rec.setdefault("payments", []).append(item)
        rec["last_payment_txid"] = txid
        rec["next_due_at"] = int(rec.get("next_due_at", now()) or now()) + int(rec.get("interval_seconds", 0) or 0)
        if rec.get("end_time") and rec["next_due_at"] > int(rec["end_time"]):
            rec["status"] = "completed"
        rec["updated_at"] = now()
        self._record_contract_event(data, "recurring.payment_recorded", {"agreement_id": agreement_id, "txid": txid})
        self.save(data)
        return rec

    def create_escrow(self, payload: dict[str, Any]) -> dict[str, Any]:
        buyer_pub = self._valid_pubkey_hex(payload.get("buyer_pubkey"), "buyer_pubkey")
        seller_pub = self._valid_pubkey_hex(payload.get("seller_pubkey"), "seller_pubkey")
        mediator_pub = self._valid_pubkey_hex(payload.get("mediator_pubkey"), "mediator_pubkey")
        amount_sats = parse_amount_sats(payload.get("amount_sats", payload.get("amount", 0)), "escrow amount")
        if amount_sats <= 0:
            raise AppError("escrow amount must be greater than zero")
        descriptor = multisig_descriptor(2, [buyer_pub, seller_pub, mediator_pub])
        address = descriptor_to_address(descriptor)
        escrow_id = str(payload.get("escrow_id") or clean_id("esc"))
        record = {
            "escrow_id": escrow_id,
            "amount_sats": amount_sats,
            "amount": sats_to_amount(amount_sats),
            "buyer_address": str(payload.get("buyer_address") or "")[:140],
            "seller_address": str(payload.get("seller_address") or "")[:140],
            "mediator_address": str(payload.get("mediator_address") or "")[:140],
            "buyer_pubkey": buyer_pub,
            "seller_pubkey": seller_pub,
            "mediator_pubkey": mediator_pub,
            "descriptor": descriptor,
            "escrow_address": address,
            "terms": str(payload.get("terms") or "")[:2000],
            "status": "funding_ready",
            "funding_txid": str(payload.get("funding_txid") or ""),
            "approvals": [],
            "created_at": now(),
        }
        if record["funding_txid"]:
            record["status"] = "funded"
        data = self.load()
        data["escrows"][escrow_id] = record
        data["contracts"][escrow_id] = {
            "contract_id": escrow_id,
            "contract_type": "escrow_2_of_3",
            "status": record["status"],
            "terms": record,
            "derived": {"address": address, "descriptor": descriptor},
            "created_at": now(),
            "updated_at": now(),
        }
        self._record_contract_event(data, "escrow.created", {"escrow_id": escrow_id, "address": address})
        self.save(data)
        return record

    def escrow_status(self, chain: Any, escrow_id: str) -> dict[str, Any]:
        data = self.load()
        esc_rec = data.get("escrows", {}).get(escrow_id)
        if not esc_rec:
            raise AppError("escrow not found")
        try:
            bal = chain.address_balance_summary(esc_rec["escrow_address"])
            esc_rec["funded_seen_sats"] = int(bal.get("total_sats", 0) or 0)
            esc_rec["funded_seen"] = sats_to_amount(esc_rec["funded_seen_sats"])
            if esc_rec.get("status") == "funding_ready" and esc_rec["funded_seen_sats"] >= int(
                esc_rec.get("amount_sats", 0)
            ):
                esc_rec["status"] = "funded"
                data["escrows"][escrow_id] = esc_rec
                self.save(data)
        except Exception:
            pass
        return esc_rec

    def escrow_action(self, escrow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        rec = data.get("escrows", {}).get(escrow_id)
        if not rec:
            raise AppError("escrow not found")
        action = str(payload.get("action") or "").lower()
        signer = str(payload.get("signer") or payload.get("participant") or "")[:120]
        if action not in {"release", "refund", "dispute", "cancel"}:
            raise AppError("escrow action must be release, refund, dispute, or cancel")
        if action == "dispute":
            rec["status"] = "disputed"
        elif action == "cancel":
            rec["status"] = "canceled"
        else:
            if not signer:
                raise AppError("signer is required")
            approval = {
                "action": action,
                "signer": signer,
                "created_at": now(),
                "signature": str(payload.get("signature") or "")[:300],
            }
            if approval not in rec.setdefault("approvals", []):
                rec["approvals"].append(approval)
            signers = {a.get("signer") for a in rec.get("approvals", []) if a.get("action") == action}
            if len(signers) >= 2:
                to_addr = normalize_address(
                    payload.get("to_address")
                    or (rec.get("seller_address") if action == "release" else rec.get("buyer_address"))
                )
                rec["payout_plan"] = self.plan_payout(
                    "escrow_" + action,
                    [{"address": to_addr, "amount_sats": int(rec["amount_sats"])}],
                    memo=f"Escrow {action} {escrow_id}",
                )
                rec["status"] = "released" if action == "release" else "refunded"
            else:
                rec["status"] = "pending_" + action
        rec["updated_at"] = now()
        self._record_contract_event(
            data, "escrow.action", {"escrow_id": escrow_id, "action": action, "status": rec["status"]}
        )
        self.save(data)
        return rec

    def create_poll(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title") or "").strip()
        if not title:
            raise AppError("poll title is required")
        options = [str(x).strip() for x in (payload.get("options") or []) if str(x).strip()]
        if len(options) < 2:
            raise AppError("poll requires at least two options")
        poll_id = str(payload.get("poll_id") or clean_id("poll"))
        record = {
            "poll_id": poll_id,
            "title": title[:200],
            "description": str(payload.get("description") or "")[:2000],
            "options": [{"option_id": f"opt{i+1}", "label": opt[:120]} for i, opt in enumerate(options)],
            "creator_address": str(payload.get("creator_address") or "")[:140],
            "voting_method": str(payload.get("voting_method") or "signed_message"),
            "weighting": str(payload.get("weighting") or "one_address_one_vote"),
            "status": str(payload.get("status") or "open"),
            "start_time": int(payload.get("start_time", now()) or now()),
            "end_time": int(payload.get("end_time", now() + 604800) or now() + 604800),
            "votes": {},
            "created_at": now(),
        }
        data = self.load()
        data["polls"][poll_id] = record
        data["contracts"][poll_id] = {
            "contract_id": poll_id,
            "contract_type": "poll",
            "status": record["status"],
            "terms": record,
            "created_at": now(),
            "updated_at": now(),
        }
        self._record_contract_event(data, "poll.created", {"poll_id": poll_id})
        self.save(data)
        return self.poll_results(poll_id)

    def poll_vote_message(self, poll_id: str, option_id: str) -> str:
        return f"NetCoin poll:{poll_id}:vote:{option_id}"

    def cast_poll_vote(self, poll_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        poll = data.get("polls", {}).get(poll_id)
        if not poll:
            raise AppError("poll not found")
        if poll.get("status") != "open" or now() > int(poll.get("end_time", 0) or 0):
            poll["status"] = "closed"
            self.save(data)
            raise AppError("poll is closed")
        voter = normalize_address(payload.get("voter_address") or payload.get("address"))
        option_id = str(payload.get("option_id") or payload.get("option") or "").strip()
        if option_id not in {o["option_id"] for o in poll.get("options", [])}:
            raise AppError("invalid poll option")
        message = self.poll_vote_message(poll_id, option_id)
        signature = str(payload.get("signature") or "")
        verified = False
        if signature:
            verified = verify_message(voter, message, signature)
            if not verified:
                raise AppError("vote signature is invalid")
        elif not bool(payload.get("allow_unverified_demo", False)):
            raise AppError("signature is required for signed-message polls")
        weight = int(payload.get("weight", 1) or 1)
        poll.setdefault("votes", {})[voter] = {
            "voter_address": voter,
            "option_id": option_id,
            "signature": signature,
            "verified": verified,
            "weight": max(1, weight),
            "message": message,
            "created_at": now(),
        }
        self._record_contract_event(
            data, "poll.vote", {"poll_id": poll_id, "voter_address": voter, "option_id": option_id}
        )
        self.save(data)
        return self.poll_results(poll_id)

    def poll_results(self, poll_id: str) -> dict[str, Any]:
        poll = self.load().get("polls", {}).get(poll_id)
        if not poll:
            raise AppError("poll not found")
        totals = {o["option_id"]: {"label": o["label"], "votes": 0, "weight": 0} for o in poll.get("options", [])}
        for vote in poll.get("votes", {}).values():
            if vote.get("option_id") in totals:
                totals[vote["option_id"]]["votes"] += 1
                totals[vote["option_id"]]["weight"] += int(vote.get("weight", 1) or 1)
        winner = None
        if totals:
            winner = max(totals, key=lambda k: (totals[k]["weight"], totals[k]["votes"]))
        return poll | {"results": totals, "winner_option_id": winner, "vote_count": len(poll.get("votes", {}))}

    def close_poll(self, poll_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = self.load()
        poll = data.get("polls", {}).get(poll_id)
        if not poll:
            raise AppError("poll not found")
        poll["status"] = str((payload or {}).get("status") or "closed")
        poll["closed_at"] = now()
        self._record_contract_event(data, "poll.closed", {"poll_id": poll_id})
        self.save(data)
        return self.poll_results(poll_id)

    def create_prediction_market(self, payload: dict[str, Any]) -> dict[str, Any]:
        from .markets import create_prediction_market_impl

        return create_prediction_market_impl(self, payload)

    def prediction_market(self, market_id: str) -> dict[str, Any]:
        from .markets import prediction_market_impl

        return prediction_market_impl(self, market_id)

    def list_prediction_markets(self) -> dict[str, Any]:
        from .markets import list_prediction_markets_impl

        return list_prediction_markets_impl(self)

    def place_market_order(self, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from .markets import place_market_order_impl

        return place_market_order_impl(self, market_id, payload)

    def cancel_market_order(
        self, market_id: str, order_id: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        from .markets import cancel_market_order_impl

        return cancel_market_order_impl(self, market_id, order_id, payload)

    def request_market_resolution(self, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from .markets import request_market_resolution_impl

        return request_market_resolution_impl(self, market_id, payload)

    def resolve_prediction_market(self, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from .markets import resolve_prediction_market_impl

        return resolve_prediction_market_impl(self, market_id, payload)

    def dispute_market_resolution(self, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from .markets import dispute_market_resolution_impl

        return dispute_market_resolution_impl(self, market_id, payload)

    def market_surveillance(self, market_id: str | None = None) -> dict[str, Any]:
        from .markets import market_surveillance_impl

        return market_surveillance_impl(self, market_id)

    def market_orderbook(self, market_id: str, depth: int = 25) -> dict[str, Any]:
        from .markets import market_orderbook_impl

        return market_orderbook_impl(self, market_id, depth)

    def market_ticker(self, market_id: str) -> dict[str, Any]:
        from .markets import market_ticker_impl

        return market_ticker_impl(self, market_id)

    def market_trades(self, market_id: str, limit: int = 100) -> dict[str, Any]:
        from .markets import market_trades_impl

        return market_trades_impl(self, market_id, limit)

    def market_positions(self, market_id: str, trader: str | None = None) -> dict[str, Any]:
        from .markets import market_positions_impl

        return market_positions_impl(self, market_id, trader)

    def polymarket_markets(self, query: dict[str, list[str]] | None = None) -> dict[str, Any]:
        from .markets import polymarket_markets_impl

        return polymarket_markets_impl(self, query)

    def market_depth(self, market_id: str, depth: int = 25) -> dict[str, Any]:
        from .markets import market_depth_impl

        return market_depth_impl(self, market_id, depth)

    def market_candles(self, market_id: str, interval_seconds: int = 3600, limit: int = 168) -> dict[str, Any]:
        from .markets import market_candles_impl

        return market_candles_impl(self, market_id, interval_seconds, limit)

    def market_open_interest(self, market_id: str) -> dict[str, Any]:
        from .markets import market_open_interest_impl

        return market_open_interest_impl(self, market_id)

    def market_volume(self, market_id: str) -> dict[str, Any]:
        from .markets import market_volume_impl

        return market_volume_impl(self, market_id)

    def market_portfolio(self, trader: str) -> dict[str, Any]:
        from .markets import portfolio_all_markets_impl

        return portfolio_all_markets_impl(self, trader)

    def cancel_all_market_orders(self, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from .markets import cancel_all_market_orders_impl

        return cancel_all_market_orders_impl(self, market_id, payload)

    def batch_market_orders(self, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from .markets import batch_market_orders_impl

        return batch_market_orders_impl(self, market_id, payload)

    def transition_market_state(
        self, market_id: str, state: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        from .markets import transition_market_state_impl

        return transition_market_state_impl(self, market_id, state, payload or {})

    def market_oracle_dossier(self, market_id: str) -> dict[str, Any]:
        from .markets.oracles import OracleRegistry

        data = self.load()
        return OracleRegistry(data.setdefault("market_oracles", {})).dossier(market_id)

    def register_market_oracle(self, payload: dict[str, Any]) -> dict[str, Any]:
        from .markets.oracles import OracleRegistry

        data = self.load()
        registry = OracleRegistry(data.setdefault("market_oracles", {}))
        rec = registry.register_oracle(
            str(payload.get("oracle_id") or payload.get("id") or "manual"),
            str(payload.get("name") or payload.get("oracle_id") or "Manual operator"),
            source_type=str(payload.get("source_type") or "manual"),
            url=str(payload.get("url") or ""),
            public_key=str(payload.get("public_key") or ""),
            reputation=int(payload.get("reputation", 0) or 0),
            active=bool(payload.get("active", True)),
        )
        self.save(data)
        self.audit("markets.oracle_registered", {"oracle_id": rec["oracle_id"]})
        return rec

    def submit_market_evidence(self, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from .markets.oracles import OracleRegistry

        data = self.load()
        registry = OracleRegistry(data.setdefault("market_oracles", {}))
        evidence = registry.submit_evidence(
            market_id,
            oracle_id=str(payload.get("oracle_id") or "manual"),
            url=str(payload.get("url") or payload.get("evidence_url") or ""),
            title=str(payload.get("title") or ""),
            source_type=str(payload.get("source_type") or "url"),
            submitter=str(payload.get("submitter") or payload.get("operator") or "operator"),
            statement=str(payload.get("statement") or payload.get("note") or ""),
            payload=dict(payload.get("payload") or {}),
        )
        market = data.get("prediction_markets", {}).get(market_id)
        if market is not None:
            market.setdefault("resolution_evidence", []).append(evidence)
            market["updated_at"] = now()
        self.save(data)
        self.audit("markets.evidence_submitted", {"market_id": market_id, "evidence_id": evidence["evidence_id"]})
        return evidence

    def dispute_market_evidence(self, market_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from .markets.oracles import OracleRegistry

        data = self.load()
        registry = OracleRegistry(data.setdefault("market_oracles", {}))
        dispute = registry.dispute(
            market_id,
            commenter=str(payload.get("commenter") or payload.get("operator") or "operator"),
            comment=str(payload.get("comment") or payload.get("note") or ""),
            evidence_id=str(payload.get("evidence_id") or ""),
        )
        market = data.get("prediction_markets", {}).get(market_id)
        if market is not None:
            market.setdefault("dispute_comments", []).append(dispute)
            market["status"] = "disputed"
            market["updated_at"] = now()
        self.save(data)
        self.audit("markets.evidence_disputed", {"market_id": market_id, "dispute_id": dispute["dispute_id"]})
        return dispute

    def market_maker_quote_plan(self, market_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        from .markets.mm import plan_quotes, quote_orders_from_plan

        payload = payload or {}
        market = self.prediction_market(market_id)
        plan = plan_quotes(
            market,
            fair_values_bps={str(k): int(v) for k, v in dict(payload.get("fair_values_bps") or {}).items()},
            spread_bps=int(payload.get("spread_bps", 200) or 200),
            quantity=int(payload.get("quantity", 10) or 10),
            max_exposure=int(payload.get("max_exposure", 1000) or 1000),
        )
        trader = str(payload.get("trader") or payload.get("trader_address") or "demo:market-maker")
        plan["orders"] = quote_orders_from_plan(plan, trader)
        return plan

    def market_settlement_reconciliation(self, market_id: str) -> dict[str, Any]:
        from .markets.reconciliation import settlement_reconciliation

        return settlement_reconciliation(self.prediction_market(market_id))

    # ----- explorer / network -----
    def upsert_known_label(self, payload: dict[str, Any]) -> dict[str, Any]:
        address = normalize_address(payload.get("address"))
        record = {
            "address": address,
            "label": str(payload.get("label") or "")[:120],
            "category": str(payload.get("category") or "user")[:80],
            "verified": bool(payload.get("verified", False)),
            "source": str(payload.get("source") or "local")[:120],
            "updated_at": now(),
        }
        data = self.load()
        data["known_labels"][address] = record
        self.save(data)
        return record

    def network_health(self, chain: Any, node: Any | None = None) -> dict[str, Any]:
        intervals = []
        last = None
        for block in chain.chain[-30:]:
            if last is not None:
                intervals.append(max(0, block.header.timestamp - last))
            last = block.header.timestamp
        return {
            "height": chain.height(),
            "tip_hash": chain.tip_hash(),
            "mempool_transactions": len(getattr(chain, "mempool", [])),
            "peer_count": len(getattr(node, "peers", [])) if node is not None else 0,
            "peers": sorted(getattr(node, "peers", [])) if node is not None else [],
            "difficulty_bits": getattr(chain.tip().header, "bits", None),
            "average_block_interval_seconds": int(sum(intervals) / len(intervals)) if intervals else 0,
            "node_version": getattr(node, "info", dict)().get("version") if node is not None else None,
            "sync_status": "ready",
        }

    def mining_dashboard(self, chain: Any) -> dict[str, Any]:
        rewards: dict[str, int] = {}
        blocks: dict[str, int] = {}
        recent = []
        for block in chain.chain:
            if not block.transactions:
                continue
            coinbase = block.transactions[0]
            for out in coinbase.outputs:
                if not out.address:
                    continue
                rewards[out.address] = rewards.get(out.address, 0) + int(out.amount)
                blocks[out.address] = blocks.get(out.address, 0) + 1
                recent.append(
                    {
                        "height": block.header.height,
                        "address": out.address,
                        "reward_sats": int(out.amount),
                        "reward": sats_to_amount(int(out.amount)),
                        "timestamp": block.header.timestamp,
                    }
                )
        top = sorted(rewards, key=lambda a: rewards[a], reverse=True)[:20]
        return {
            "top_miners": [
                {
                    "address": a,
                    "blocks": blocks.get(a, 0),
                    "reward_sats": rewards[a],
                    "reward": sats_to_amount(rewards[a]),
                }
                for a in top
            ],
            "recent_rewards": recent[-30:][::-1],
        }

    def mining_calculator(self, chain: Any, hashrate: float = 1.0) -> dict[str, Any]:
        # Educational estimate: assumes local hashrate share against a bits-derived
        # target proxy. This is approximate until NetCoin exposes global hashrate.
        subsidy = chain.subsidy(chain.height() + 1)
        avg_interval = self.network_health(chain)["average_block_interval_seconds"] or 600
        blocks_per_day = 86400 / avg_interval
        return {
            "hashrate": hashrate,
            "estimated_blocks_per_day_network": blocks_per_day,
            "next_reward_sats": subsidy,
            "next_reward": sats_to_amount(subsidy),
            "note": "Provide network hashrate externally for a precise personal reward estimate.",
        }

    def node_map(self, node: Any | None = None) -> dict[str, Any]:
        peers = sorted(getattr(node, "peers", [])) if node is not None else []
        reports = self.load().get("node_reports", [])
        return {"peers": [{"url": p, "region": "unknown"} for p in peers], "reports": reports[-100:]}

    def reward_countdown(self, chain: Any) -> dict[str, Any]:
        current = chain.height()
        activation = REWARD_SCHEDULE_ACTIVATION_HEIGHT
        if current < activation:
            event = activation
            event_name = "10_percent_reward_schedule_activation"
        else:
            event = next_reduction_height(current)
            event_name = "10_percent_reward_reduction"
        subsidy = chain.subsidy(current + 1)
        return {
            "height": current,
            "next_event": event_name,
            "event_height": event,
            "blocks_remaining": max(0, event - current),
            "interval_blocks": REWARD_REDUCTION_INTERVAL,
            "reduction_percent": int(
                (REWARD_REDUCTION_DENOMINATOR - REWARD_REDUCTION_NUMERATOR) * 100 / REWARD_REDUCTION_DENOMINATOR
            ),
            "current_subsidy_sats": subsidy,
            "current_subsidy": sats_to_amount(subsidy),
        }

    def treasury(self, chain: Any) -> dict[str, Any]:
        data = self.load()
        result = []
        total = 0
        for entry in data.get("treasury_addresses", []):
            address = entry["address"] if isinstance(entry, dict) else str(entry)
            try:
                bal = chain.address_balance_summary(address)
                total += int(bal["total_sats"])
                result.append(
                    {
                        "address": address,
                        "label": entry.get("label", "Treasury") if isinstance(entry, dict) else "Treasury",
                        "balance_sats": bal["total_sats"],
                        "balance": bal["total"],
                    }
                )
            except Exception as exc:
                result.append({"address": address, "error": str(exc)})
        return {"addresses": result, "total_sats": total, "total": sats_to_amount(total)}


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def validate_address_payload(address: str) -> dict[str, Any]:
    valid = validate_address(address)
    details: dict[str, Any] | None = None
    error = None
    if valid:
        try:
            details = _json_safe(decode_address(address))
        except Exception as exc:  # pragma: no cover - validate_address already passed
            error = str(exc)
    return {
        "address": address,
        "valid": valid,
        "network": "netcoin" if valid else None,
        "details": details,
        "error": error,
    }

    # -------- small routing helpers used by node.py and explorer_server.py --------

    # ----- professional treasury governance -----
    def create_treasury_proposal(self, payload: dict[str, Any]) -> dict[str, Any]:
        proposal_id = str(payload.get("proposal_id") or clean_id("tpr"))[:80]
        title = str(payload.get("title") or "Treasury spend")[:120]
        amount_sats = parse_amount_sats(
            payload.get("amount_sats", payload.get("amount", 0)), "treasury proposal amount"
        )
        to_address = normalize_address(payload.get("to_address") or payload.get("address"))
        required = max(1, int(payload.get("required_approvals", 2) or 2))
        record = {
            "proposal_id": proposal_id,
            "title": title,
            "to_address": to_address,
            "amount_sats": amount_sats,
            "amount": sats_to_amount(amount_sats),
            "memo": str(payload.get("memo") or "")[:500],
            "status": "pending_approval",
            "required_approvals": required,
            "approvals": [],
            "created_at": now(),
            "updated_at": now(),
        }
        data = self.load()
        data.setdefault("treasury_proposals", {})[proposal_id] = record
        self.save(data)
        self.audit("treasury.proposal_created", {"proposal_id": proposal_id, "amount_sats": amount_sats})
        return record

    def approve_treasury_proposal(self, proposal_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        signer = str(payload.get("signer") or payload.get("operator") or payload.get("address") or "").strip()
        if not signer:
            raise AppError("approval signer is required")
        data = self.load()
        proposal = data.setdefault("treasury_proposals", {}).get(proposal_id)
        if not proposal:
            raise AppError("treasury proposal not found")
        approvals = proposal.setdefault("approvals", [])
        if not any(a.get("signer") == signer for a in approvals):
            approvals.append({"signer": signer, "note": str(payload.get("note") or "")[:250], "created_at": now()})
        if (
            len(approvals) >= int(proposal.get("required_approvals", 2) or 2)
            and proposal.get("status") == "pending_approval"
        ):
            plan = self.plan_payout(
                "treasury",
                [{"address": proposal["to_address"], "amount_sats": proposal["amount_sats"]}],
                memo=proposal.get("memo", ""),
            )
            proposal["payout_plan"] = plan
            proposal["status"] = "ready_for_wallet_signing"
        proposal["updated_at"] = now()
        self.save(data)
        self.audit(
            "treasury.proposal_approved",
            {"proposal_id": proposal_id, "signer": signer, "approval_count": len(approvals)},
        )
        return proposal

    def treasury_governance(self) -> dict[str, Any]:
        data = self.load()
        proposals = list(data.get("treasury_proposals", {}).values())
        proposals.sort(key=lambda x: -int(x.get("created_at", 0) or 0))
        return {
            "treasury_addresses": data.get("treasury_addresses", []),
            "proposal_count": len(proposals),
            "pending": sum(1 for p in proposals if p.get("status") == "pending_approval"),
            "ready_for_signing": sum(1 for p in proposals if p.get("status") == "ready_for_wallet_signing"),
            "proposals": proposals,
            "policy": data.get("payout_signing_policy", DEFAULT_APP_STATE["payout_signing_policy"]),
        }


def route_app_get(
    store: AppStore, chain: Any, path: str, query: dict[str, list[str]], node: Any | None = None
) -> tuple[int, dict[str, Any] | str | bytes, str]:
    def q(name: str, default: str = "") -> str:
        return query.get(name, [default])[0]

    is_api_route = path.startswith("/api")
    is_app_route = path.startswith("/app")
    if is_api_route:
        path = path[4:] or "/"
    if is_app_route:
        path = path[4:] or "/"

    # Public HTML pages are intentionally kept separate from /api JSON routes.
    # In particular, /api/receipt/<txid> must stay machine-readable while
    # /receipt/<txid> remains the public receipt page.
    if not is_api_route and path.startswith("/pay/"):
        return 200, store.checkout_html(chain, path.split("/", 2)[2]), "text/html; charset=utf-8"
    if not is_api_route and (path.startswith("/tip/") or path.startswith("/donate/")):
        return 200, store.tip_html(path.split("/", 2)[2]), "text/html; charset=utf-8"
    if not is_api_route and (path.startswith("/u/") or path.startswith("/profile/")):
        return 200, store.profile_html(path.split("/", 2)[2]), "text/html; charset=utf-8"
    if path.startswith("/receipt/") and path.endswith(".pdf"):
        txid = path.split("/", 2)[2][:-4]
        return 200, store.receipt_pdf(chain, txid), "application/pdf"
    if not is_api_route and path.startswith("/receipt/"):
        return 200, store.receipt_html(chain, path.split("/", 2)[2]), "text/html; charset=utf-8"
    if not is_api_route and path.startswith("/gift/"):
        code = path.split("/", 2)[2]
        body = app_html_page(
            "Claim NetCoin gift",
            f"<h1>Claim NetCoin gift</h1><div class=card><p>Claim code:</p><p class=mono>{esc(code)}</p><form><input name=address placeholder='your NetCoin address'><p class=muted>Submit this code and address to /api/community/gifts/claim.</p></form></div>",
        )
        return 200, body, "text/html; charset=utf-8"
    if path == "/admin" or path == "/operator":
        return 200, store.admin_dashboard_html(), "text/html; charset=utf-8"
    if path.startswith("/validate-address/"):
        return 200, validate_address_payload(path.split("/", 2)[2]), "application/json"
    if path == "/validate-address":
        return 200, validate_address_payload(q("address")), "application/json"
    if path in ("/payments", "/invoices"):
        return (
            200,
            store.list_invoices(chain, int(q("limit", "50") or 50), merchant_id=q("merchant_id") or None),
            "application/json",
        )
    if path.startswith("/payments/") or path.startswith("/invoices/"):
        invoice_id = path.split("/", 2)[2]
        return 200, store.invoice_status(chain, invoice_id), "application/json"
    if path.startswith("/payment/invoices/") and path.endswith("/status"):
        invoice_id = path.split("/")[3]
        return 200, store.invoice_status(chain, invoice_id), "application/json"
    if path.startswith("/checkout/"):
        invoice_id = path.split("/", 2)[2]
        return 200, {"checkout": store.invoice_status(chain, invoice_id)}, "application/json"
    if path.startswith("/receipt/") or path.startswith("/receipts/"):
        txid = path.split("/", 2)[2]
        return 200, store.receipt(chain, txid), "application/json"
    if path == "/usernames":
        return 200, {"usernames": list(store.load()["usernames"].values())}, "application/json"
    if path.startswith("/usernames/"):
        return 200, store.resolve_username(path.split("/", 2)[2]), "application/json"
    if path.startswith("/profiles/") or path.startswith("/u/"):
        name = path.split("/", 2)[2]
        return 200, store.resolve_username(name), "application/json"
    if path == "/labels":
        return 200, {"labels": store.load()["known_labels"]}, "application/json"
    if path.startswith("/labels/"):
        addr = path.split("/", 2)[2]
        return 200, store.load()["known_labels"].get(addr, {"address": addr, "label": ""}), "application/json"
    if path == "/merchant/export.csv":
        return 200, store.invoices_csv(chain, merchant_id=q("merchant_id") or None), "text/csv"
    if path == "/merchant/webhooks":
        return (
            200,
            {"webhooks": list(store.load()["webhooks"].values()), "events": store.load()["webhook_events"][-100:]},
            "application/json",
        )
    if path == "/merchant/refunds":
        return 200, {"refunds": list(store.load()["refunds"].values())}, "application/json"
    if path == "/merchant/api-keys":
        keys = [{k: v for k, v in item.items() if k != "key_hash"} for item in store.load()["api_keys"].values()]
        return 200, {"api_keys": keys}, "application/json"
    if path == "/merchant/api-usage":
        return 200, store.api_usage_report(), "application/json"
    if path == "/community/gifts":
        return 200, {"gifts": list(store.load()["gifts"].values())}, "application/json"
    if path == "/community/airdrops":
        return 200, {"airdrops": list(store.load()["airdrops"].values())}, "application/json"
    if path == "/community/rewards":
        return 200, {"rewards": list(store.load()["rewards"].values())}, "application/json"
    if path == "/community/tip-buttons":
        return 200, {"tip_buttons": list(store.load()["tip_buttons"].values())}, "application/json"
    if path == "/community/bounties":
        return 200, {"bounties": list(store.load()["bounties"].values())}, "application/json"
    if path == "/tokens":
        return 200, store.list_tokens(), "application/json"
    if path == "/tokens/events":
        return 200, store.token_events(limit=int(q("limit", "100") or 100)), "application/json"
    if path.startswith("/tokens/") and path.endswith("/balances"):
        return 200, store.token_balances(path.split("/")[2]), "application/json"
    if path.startswith("/tokens/") and path.endswith("/events"):
        return 200, store.token_events(path.split("/")[2], limit=int(q("limit", "100") or 100)), "application/json"
    if path.startswith("/tokens/") and "/balance/" in path:
        parts = path.split("/")
        return 200, store.token_balance_of(parts[2], parts[4]), "application/json"
    if path.startswith("/tokens/"):
        return 200, store.token_info(path.split("/", 2)[2]), "application/json"
    if path.startswith("/community/bounties/"):
        b = store.load()["bounties"].get(path.split("/", 3)[3])
        if not b:
            raise AppError("bounty not found")
        return 200, b, "application/json"

    # v0.18 live product wiring: rich explorer endpoints for polished pages.
    if path.startswith("/explorer/address/") and path.endswith("/csv"):
        from ..live_product import explorer_address_csv

        address = path.split("/")[3]
        return 200, explorer_address_csv(chain, address), "text/csv"
    if path.startswith("/explorer/address/"):
        from ..live_product import explorer_address_live

        address = path.split("/", 3)[3]
        return 200, explorer_address_live(chain, address, limit=int(q("limit", "100") or 100)), "application/json"
    if path.startswith("/explorer/tx/"):
        from ..live_product import explorer_tx_live

        return 200, explorer_tx_live(chain, path.split("/", 3)[3]), "application/json"
    if path.startswith("/explorer/block/"):
        from ..live_product import explorer_block_live

        return 200, explorer_block_live(chain, path.split("/", 3)[3]), "application/json"
    if path == "/explorer/mempool":
        from ..live_product import explorer_mempool_live

        return 200, explorer_mempool_live(chain, limit=int(q("limit", "200") or 200)), "application/json"
    if path == "/explorer/watchlist":
        from ..live_product import explorer_watchlist_live

        return 200, explorer_watchlist_live(store, chain, query), "application/json"
    if path == "/wallet/workflow":
        from ..live_product import wallet_workflow_status

        return 200, wallet_workflow_status(store), "application/json"
    if path == "/operator/live":
        from ..live_product import operator_live_controls

        return 200, operator_live_controls(chain, node=node), "application/json"

    if path == "/operator/diagnostics/bundle":
        from ..health_center import build_health_center
        from ..live_product import operator_live_controls, digest_payload

        payload = {
            "health": build_health_center(
                root=Path(__file__).resolve().parents[2], chain=chain, node=node, store=store
            ),
            "operator": operator_live_controls(chain, node=node),
            "generated_at": now(),
        }
        payload["bundle_hash"] = digest_payload(payload)
        return 200, payload, "application/json"
    if path == "/faucet/status":
        from ..live_product import faucet_admin_status

        data = store.load()
        state = data.get(
            "faucet_state",
            {"requests": [], "abuse": [], "reputation": {}, "daily_cap_sats": 0, "difficulty": 0, "paused": False},
        )
        return 200, faucet_admin_status(state), "application/json"
    if path == "/exchange/live":
        from ..live_product import exchange_live_status

        return 200, exchange_live_status(store), "application/json"
    if path == "/release/verify":
        from ..live_product import release_verify_payload

        return (
            200,
            release_verify_payload(
                Path(__file__).resolve().parents[2], {"sha256": q("sha256"), "expected_sha256": q("expected_sha256")}
            ),
            "application/json",
        )

    if path == "/architecture":
        from ..architecture import architecture_summary

        return 200, architecture_summary(Path(__file__).resolve().parents[2]), "application/json"
    if path == "/migration-status":
        from ..migration_status import migration_status, parity_vectors, final_version_readiness, parity_bridge_status

        root = Path(__file__).resolve().parents[2]
        return (
            200,
            {
                "status": migration_status(root),
                "vectors": parity_vectors(root),
                "readiness": final_version_readiness(root),
                "parity": parity_bridge_status(root),
            },
            "application/json",
        )
    if path == "/parity-status":
        from ..migration_status import parity_bridge_status

        return 200, parity_bridge_status(Path(__file__).resolve().parents[2]), "application/json"
    if path == "/parity-vectors":
        from ..migration_status import parity_vectors

        return 200, parity_vectors(Path(__file__).resolve().parents[2]), "application/json"
    if path == "/migration-readiness":
        from ..migration_status import final_version_readiness, migration_status, parity_bridge_status

        root = Path(__file__).resolve().parents[2]
        return (
            200,
            {
                "migration": migration_status(root),
                "parity": parity_bridge_status(root),
                "readiness": final_version_readiness(root),
            },
            "application/json",
        )
    if path == "/features":
        return 200, feature_catalog(), "application/json"
    if path == "/feature-status":
        from ..feature_status import live_feature_status

        return 200, live_feature_status(root=Path(__file__).resolve().parents[2]), "application/json"
    if path in ("/health-center", "/product/status"):
        from ..health_center import build_health_center

        return (
            200,
            build_health_center(root=Path(__file__).resolve().parents[2], chain=chain, node=node, store=store),
            "application/json",
        )
    if path == "/community/leaderboards":
        return 200, store.leaderboards(chain), "application/json"
    if path == "/community/posts":
        limit = int(q("limit", "50") or 50)
        return 200, store.list_community_posts(limit=limit, sort=q("sort", "hot") or "hot"), "application/json"
    if path.startswith("/community/posts/") and path.endswith("/comments"):
        return (
            200,
            store.list_community_comments(path.split("/")[3], limit=int(q("limit", "100") or 100)),
            "application/json",
        )
    if path == "/community/improvements":
        return 200, store.list_improvements(), "application/json"
    if path == "/community/moderation":
        limit = int(q("limit", "100") or 100)
        return 200, store.community_moderation_queue(limit=limit), "application/json"
    if path == "/community/reports":
        limit = int(q("limit", "100") or 100)
        return 200, store.list_community_reports(limit=limit), "application/json"
    if path == "/wallet/statement":
        return 200, store.wallet_statement(chain, q("address"), q("month") or None), "application/json"
    if path == "/wallet/statement.csv":
        return 200, store.wallet_statement_csv(chain, q("address"), q("month") or None), "text/csv"
    if path == "/wallet/statement.pdf":
        return 200, store.wallet_statement_pdf(chain, q("address"), q("month") or None), "application/pdf"
    if path == "/wallet/alerts":
        return (
            200,
            {
                "alerts": list(store.load()["wallet_alerts"].values()),
                "events": store.load().get("alert_events", [])[-100:],
            },
            "application/json",
        )
    if path == "/wallet/alerts/evaluate":
        return 200, store.evaluate_alerts(chain), "application/json"
    if path == "/wallet/limits":
        return 200, {"spending_limits": store.load()["spending_limits"]}, "application/json"
    if path == "/wallet/limits/check":
        return (
            200,
            store.check_spending_limits(
                {"wallet_id": q("wallet_id"), "address": q("address"), "amount": q("amount"), "fee": q("fee")}
            ),
            "application/json",
        )
    if path == "/wallet/team-wallets":
        return 200, {"team_wallets": list(store.load()["team_wallets"].values())}, "application/json"
    if path.startswith("/wallet/receive/next/"):
        return 200, store.next_receive_address(path.split("/", 4)[4]), "application/json"
    if path == "/wallet/receive-addresses":
        return 200, {"address_rotation": store.load().get("address_rotation", {})}, "application/json"
    if path == "/wallet/backup-health":
        return 200, {"backup_health": store.load()["backup_health"]}, "application/json"
    if path == "/security/status":
        return 200, store.security_status(), "application/json"
    if path in ("/professional-readiness", "/readiness/professional"):
        from ..professional import professional_readiness

        return 200, professional_readiness(Path(__file__).resolve().parents[2]), "application/json"
    if path == "/professional-issues":
        from ..professional import issue_report

        return 200, issue_report(Path(__file__).resolve().parents[2]), "application/json"
    if path == "/security/audit":
        return 200, {"admin_events": store.load().get("admin_events", [])[-200:]}, "application/json"
    if path == "/admin/summary":
        return 200, store.admin_summary(chain, node=node), "application/json"
    if path == "/admin/payouts":
        return 200, store.list_payout_plans(status=q("status") or None), "application/json"
    if path.startswith("/admin/payouts/") and path.endswith("/bundle"):
        payout_id = path.split("/")[3]
        return 200, store.payout_signer_bundle(payout_id), "application/json"
    if path.startswith("/admin/payouts/"):
        payout_id = path.split("/")[3]
        return 200, store.get_payout_plan(payout_id), "application/json"
    if path == "/custody/policy":
        return (
            200,
            store.load().get("payout_signing_policy", DEFAULT_APP_STATE["payout_signing_policy"]),
            "application/json",
        )
    if path == "/contracts/templates":
        return 200, store.list_contract_templates(), "application/json"
    if path == "/contracts/events":
        return 200, {"events": store.load().get("contract_events", [])[-200:]}, "application/json"
    if path == "/contracts":
        return 200, {"contracts": list(store.load().get("contracts", {}).values())}, "application/json"
    if path.startswith("/contracts/"):
        cid = path.split("/", 2)[2]
        rec = store.load().get("contracts", {}).get(cid)
        if not rec:
            raise AppError("contract not found")
        return 200, rec, "application/json"
    if path == "/recurring":
        return 200, store.list_recurring_agreements(), "application/json"
    if path.startswith("/recurring/"):
        aid = path.split("/", 2)[2].split("/")[0]
        rec = store.load().get("recurring_agreements", {}).get(aid)
        if not rec:
            raise AppError("recurring agreement not found")
        return 200, rec, "application/json"
    if path == "/escrows":
        return (
            200,
            {"escrows": [store.escrow_status(chain, x["escrow_id"]) for x in store.load().get("escrows", {}).values()]},
            "application/json",
        )
    if path.startswith("/escrows/"):
        return 200, store.escrow_status(chain, path.split("/", 2)[2]), "application/json"
    if path == "/polls":
        polls = []
        for p in store.load().get("polls", {}).values():
            polls.append(store.poll_results(p["poll_id"]))
        return 200, {"polls": polls}, "application/json"
    if path.startswith("/polls/"):
        return 200, store.poll_results(path.split("/", 2)[2]), "application/json"
    if path == "/markets":
        return 200, store.list_prediction_markets(), "application/json"
    if path == "/markets/external/polymarket":
        return 200, store.polymarket_markets(query), "application/json"
    if path == "/markets/surveillance":
        return 200, store.market_surveillance(), "application/json"
    if path.startswith("/markets/") and path.endswith("/surveillance"):
        return 200, store.market_surveillance(path.split("/")[2]), "application/json"
    if path.startswith("/markets/") and path.endswith("/orderbook"):
        depth_raw = q("depth", "25") or "25"
        try:
            depth = int(depth_raw)
        except ValueError:
            depth = 25
        return 200, store.market_orderbook(path.split("/")[2], depth), "application/json"
    if path.startswith("/markets/") and path.endswith("/ticker"):
        return 200, store.market_ticker(path.split("/")[2]), "application/json"
    if path.startswith("/markets/") and path.endswith("/trades"):
        limit_raw = q("limit", "100") or "100"
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 100
        return 200, store.market_trades(path.split("/")[2], limit), "application/json"
    if path.startswith("/markets/") and path.endswith("/positions"):
        return 200, store.market_positions(path.split("/")[2], q("trader") or None), "application/json"
    if path == "/markets/portfolio":
        return 200, store.market_portfolio(q("trader") or "demo:trader"), "application/json"
    if path.startswith("/markets/") and path.endswith("/depth"):
        return 200, store.market_depth(path.split("/")[2], int(q("depth", "25") or 25)), "application/json"
    if path.startswith("/markets/") and path.endswith("/candles"):
        return (
            200,
            store.market_candles(path.split("/")[2], int(q("interval", "3600") or 3600), int(q("limit", "168") or 168)),
            "application/json",
        )
    if path.startswith("/markets/") and path.endswith("/open-interest"):
        return 200, store.market_open_interest(path.split("/")[2]), "application/json"
    if path.startswith("/markets/") and path.endswith("/volume"):
        return 200, store.market_volume(path.split("/")[2]), "application/json"
    if path.startswith("/markets/") and path.endswith("/oracles"):
        return 200, store.market_oracle_dossier(path.split("/")[2]), "application/json"
    if path.startswith("/markets/") and path.endswith("/reconciliation"):
        return 200, store.market_settlement_reconciliation(path.split("/")[2]), "application/json"
    if path.startswith("/markets/") and path.endswith("/maker-plan"):
        return (
            200,
            store.market_maker_quote_plan(path.split("/")[2], {"trader": q("trader") or "demo:market-maker"}),
            "application/json",
        )
    if path.startswith("/markets/"):
        return 200, store.prediction_market(path.split("/", 2)[2]), "application/json"
    if path == "/network":
        return 200, store.network_health(chain, node=node), "application/json"
    if path == "/mining/dashboard":
        return 200, store.mining_dashboard(chain), "application/json"
    if path == "/mining/calculator":
        return 200, store.mining_calculator(chain, float(q("hashrate", "1") or 1)), "application/json"
    if path == "/node-map":
        return 200, store.node_map(node), "application/json"
    if path == "/reward-countdown":
        return 200, store.reward_countdown(chain), "application/json"
    if path == "/treasury/governance":
        return 200, store.treasury_governance(), "application/json"
    if path == "/treasury":
        return 200, store.treasury(chain), "application/json"
    raise AppError("not an app-layer route")


def _route_app_post_uncached(
    store: AppStore, chain: Any, path: str, body: dict[str, Any], node: Any | None = None
) -> tuple[int, dict[str, Any]]:
    if path.startswith("/api"):
        path = path[4:] or "/"
    if path.startswith("/app"):
        path = path[4:] or "/"

    # v0.18 live product write helpers.
    if path == "/wallet/drafts":
        from ..live_product import save_wallet_draft

        return 200, save_wallet_draft(store, body)
    if path == "/release/verify":
        from ..live_product import release_verify_payload

        return 200, release_verify_payload(Path(__file__).resolve().parents[2], body)

    if path in ("/payments", "/invoices", "/payment/invoices/create"):
        return 200, store.create_invoice(chain, body)
    if path == "/usernames" or path == "/profiles":
        return 200, store.upsert_username(body)
    if path == "/merchant/api-keys":
        return 200, store.create_api_key(body)
    if path == "/merchant/api-keys/enforce":
        return 200, store.set_api_key_enforcement(body)
    if path == "/merchant/webhooks":
        merchant_id = str(body.get("merchant_id") or "default")[:80]
        store.maybe_require_api_key(body, merchant_id, "merchant:write")
        return 200, store.register_webhook(body)
    if path == "/merchant/webhook-events":
        return 200, store.queue_webhook_event(body)
    if path == "/merchant/webhook-events/deliver":
        return 200, store.deliver_webhook_events(body)
    if path == "/merchant/refunds":
        merchant_id = str(body.get("merchant_id") or "default")[:80]
        store.maybe_require_api_key(body, merchant_id, "merchant:write")
        return 200, store.record_refund(body)
    if path == "/merchant/refunds/plan":
        merchant_id = str(body.get("merchant_id") or "default")[:80]
        store.maybe_require_api_key(body, merchant_id, "merchant:write")
        return 200, store.create_refund_plan(body)
    if path == "/tokens":
        return 200, store.create_token(body)
    if path.startswith("/tokens/") and path.endswith("/mint"):
        return 200, store.mint_token(path.split("/")[2], body)
    if path.startswith("/tokens/") and path.endswith("/transfer"):
        return 200, store.transfer_token(path.split("/")[2], body)
    if path.startswith("/tokens/") and path.endswith("/burn"):
        return 200, store.burn_token(path.split("/")[2], body)
    if path == "/community/airdrops":
        return 200, store.airdrop(body)
    if path == "/community/gifts":
        return 200, store.create_gift(body)
    if path == "/community/rewards":
        return 200, store.create_reward(body)
    if path == "/community/tip-buttons":
        return 200, store.tip_button(body)
    if path == "/community/gifts/claim":
        return 200, store.claim_gift(body)
    if path == "/community/posts":
        return 200, store.create_community_post(body)
    if path.startswith("/community/posts/") and path.endswith("/vote"):
        return 200, store.vote_community_post(path.split("/")[3], body)
    if path.startswith("/community/posts/") and path.endswith("/comments"):
        return 200, store.create_community_comment(path.split("/")[3], body)
    if path == "/community/moderation":
        return 200, store.moderate_community_item(body)
    if path == "/community/improvements":
        return 200, store.create_improvement(body)
    if path == "/community/reports":
        return 200, store.create_community_report(body)
    if path.startswith("/community/improvements/") and path.endswith("/vote"):
        return 200, store.vote_improvement(path.split("/")[3])
    if path == "/community/bounties":
        return 200, store.create_bounty(body)
    if path.startswith("/community/bounties/") and path.endswith("/submit"):
        bounty_id = path.split("/")[3]
        return 200, store.submit_bounty(bounty_id, body)
    if path.startswith("/community/bounties/") and path.endswith("/award"):
        bounty_id = path.split("/")[3]
        return 200, store.award_bounty(bounty_id, body)
    if path == "/custody/policy":
        return 200, store.set_payout_signing_policy(body)
    if path.startswith("/admin/payouts/") and path.endswith("/review"):
        return 200, store.review_payout_plan(path.split("/")[3], body)
    if path.startswith("/admin/payouts/") and path.endswith("/reject"):
        return 200, store.reject_payout_plan(path.split("/")[3], body)
    if path.startswith("/admin/payouts/") and path.endswith("/signed"):
        return 200, store.record_signed_payout(path.split("/")[3], body)
    if path.startswith("/admin/payouts/") and path.endswith("/broadcasted"):
        return 200, store.record_broadcasted_payout(path.split("/")[3], body)
    if path == "/contracts":
        return 200, store.create_contract(body)
    if path.startswith("/contracts/") and path.endswith("/transition"):
        return 200, store.transition_contract(path.split("/")[2], body)
    if path == "/recurring":
        return 200, store.create_recurring_agreement(body)
    if path.startswith("/recurring/") and path.endswith("/invoice"):
        return 200, store.create_recurring_invoice(chain, path.split("/")[2], body)
    if path.startswith("/recurring/") and path.endswith("/payment"):
        return 200, store.record_recurring_payment(path.split("/")[2], body)
    if path.startswith("/recurring/") and path.endswith("/action"):
        return 200, store.update_recurring_agreement(path.split("/")[2], body)
    if path == "/escrows":
        return 200, store.create_escrow(body)
    if path.startswith("/escrows/") and path.endswith("/action"):
        return 200, store.escrow_action(path.split("/")[2], body)
    if path == "/polls":
        return 200, store.create_poll(body)
    if path.startswith("/polls/") and path.endswith("/vote"):
        return 200, store.cast_poll_vote(path.split("/")[2], body)
    if path.startswith("/polls/") and path.endswith("/close"):
        return 200, store.close_poll(path.split("/")[2], body)
    if path == "/markets":
        return 200, store.create_prediction_market(body)
    if path.startswith("/markets/") and path.endswith("/order"):
        return 200, store.place_market_order(path.split("/")[2], body)
    if path.startswith("/markets/") and path.endswith("/batch-orders"):
        return 200, store.batch_market_orders(path.split("/")[2], body)
    if path.startswith("/markets/") and path.endswith("/cancel-all"):
        return 200, store.cancel_all_market_orders(path.split("/")[2], body)
    if path.startswith("/markets/") and path.endswith("/pause"):
        return 200, store.transition_market_state(path.split("/")[2], "paused", body)
    if path.startswith("/markets/") and path.endswith("/resume"):
        return 200, store.transition_market_state(path.split("/")[2], "open", body)
    if path.startswith("/markets/") and path.endswith("/close"):
        return 200, store.transition_market_state(path.split("/")[2], "closed", body)
    if path.startswith("/markets/") and "/orders/" in path and path.endswith("/cancel"):
        parts = path.split("/")
        return 200, store.cancel_market_order(parts[2], parts[4], body)
    if path.startswith("/markets/") and path.endswith("/cancel"):
        parts = path.split("/")
        return 200, store.cancel_market_order(parts[2], str(body.get("order_id") or ""), body)
    if path.startswith("/markets/") and path.endswith("/resolution-request"):
        return 200, store.request_market_resolution(path.split("/")[2], body)
    if path.startswith("/markets/") and path.endswith("/dispute"):
        return 200, store.dispute_market_resolution(path.split("/")[2], body)
    if path.startswith("/markets/") and path.endswith("/resolve"):
        return 200, store.resolve_prediction_market(path.split("/")[2], body)
    if path == "/markets/oracles":
        return 200, store.register_market_oracle(body)
    if path.startswith("/markets/") and path.endswith("/evidence"):
        return 200, store.submit_market_evidence(path.split("/")[2], body)
    if path.startswith("/markets/") and path.endswith("/evidence-dispute"):
        return 200, store.dispute_market_evidence(path.split("/")[2], body)
    if path.startswith("/markets/") and path.endswith("/maker-plan"):
        return 200, store.market_maker_quote_plan(path.split("/")[2], body)
    if path == "/wallet/categories":
        return 200, store.set_category(body)
    if path == "/wallet/alerts":
        return 200, store.upsert_alert(body)
    if path == "/wallet/limits":
        return 200, store.set_spending_limits(body)
    if path == "/wallet/limits/check":
        return 200, store.check_spending_limits(body)
    if path == "/wallet/spend-log":
        return 200, store.record_wallet_spend(body)
    if path == "/wallet/alerts/evaluate":
        return 200, store.evaluate_alerts(chain, body)
    if path == "/wallet/backup-health":
        return 200, store.set_backup_health(body)
    if path == "/wallet/team-wallets":
        return 200, store.create_team_wallet(body)
    if path.startswith("/wallet/team-wallets/") and path.endswith("/proposals"):
        wallet_id = path.split("/")[3]
        return 200, store.create_team_proposal(wallet_id, body)
    if path.startswith("/wallet/team-wallets/") and "/proposals/" in path and path.endswith("/approve"):
        parts = path.split("/")
        return 200, store.approve_team_proposal(parts[3], parts[5], body)
    if path == "/wallet/receive-addresses":
        return 200, store.address_rotation_record(body)
    if path == "/labels":
        return 200, store.upsert_known_label(body)
    if path == "/treasury/proposals":
        return 200, store.create_treasury_proposal(body)
    if path.startswith("/treasury/proposals/") and path.endswith("/approve"):
        return 200, store.approve_treasury_proposal(path.split("/")[3], body)
    if path == "/treasury":
        data = store.load()
        entries = body.get("addresses", [])
        if isinstance(entries, str):
            entries = [{"address": a.strip(), "label": "Treasury"} for a in entries.split(",") if a.strip()]
        for entry in entries:
            normalize_address(entry.get("address") if isinstance(entry, dict) else entry)
        data["treasury_addresses"] = entries
        store.save(data)
        return 200, store.treasury(chain)
    raise AppError("not an app-layer route")


def route_app_post(
    store: AppStore, chain: Any, path: str, body: dict[str, Any], node: Any | None = None
) -> tuple[int, dict[str, Any]]:
    """Route an app-layer write with optional idempotency and nonce protection."""
    action = path[4:] if path.startswith("/api") else path
    action = action[4:] if action.startswith("/app") else action
    from .auth import require_signed_envelope_if_needed

    envelope_status = require_signed_envelope_if_needed("POST", action, body)
    if envelope_status.get("verified"):
        body = dict(body)
        body["signed_envelope_verified"] = envelope_status
    replay = store.idempotency_lookup(action, body)
    if replay is not None:
        response = (
            dict(replay["response"])
            if isinstance(replay.get("response"), dict)
            else {"response": replay.get("response")}
        )
        response["idempotent_replay"] = True
        response["idempotency_key"] = replay.get("idempotency_key")
        return int(replay.get("status", 200)), response
    store.enforce_app_nonce(action, body)
    status, payload = _route_app_post_uncached(store, chain, path, body, node=node)
    if isinstance(payload, dict):
        store.idempotency_store(action, body, status, payload)
        store.record_api_usage(body, action, status)
        if action.startswith(("/markets", "/merchant", "/admin", "/custody", "/treasury")):
            store.append_immutable_audit(action, {"status": status, "keys": sorted(str(k) for k in body.keys())})
    return status, payload
