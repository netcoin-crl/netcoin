"""Signed request envelopes, scoped API keys, CSRF, and webhook HMAC helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from ..crypto import constant_time_equal, verify_message
from . import AppError, normalize_address

SENSITIVE_WRITE_PREFIXES = (
    "/tokens",
    "/markets",
    "/merchant",
    "/admin",
    "/custody",
    "/treasury",
    "/wallet/team-wallets",
)
PUBLIC_WRITE_PATHS = {
    "/community/posts",
    "/community/improvements",
    "/community/reports",
    "/invoices",
    "/payments",
}
DEFAULT_SCOPE_MAP = {
    "read": {"GET"},
    "write": {"POST", "PUT", "PATCH", "DELETE"},
    "merchant": {"/merchant"},
    "market": {"/markets"},
    "faucet": {"/faucet"},
    "admin": {"/admin", "/custody", "/treasury"},
    "auditor": {"/security", "/professional"},
}


@dataclass(frozen=True)
class SignedEnvelope:
    address: str
    method: str
    path: str
    body_hash: str
    timestamp: int
    nonce: str
    signature: str
    version: str = "netcoin-signed-envelope-v1"

    def message(self) -> str:
        return "\n".join(
            [
                "NetCoin signed request",
                self.version,
                self.address,
                self.method.upper(),
                self.path,
                self.body_hash,
                str(int(self.timestamp)),
                self.nonce,
            ]
        )

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data["message"] = self.message()
        return data


def canonical_body_hash(body: Mapping[str, Any] | bytes | str | None) -> str:
    if body is None:
        raw = b""
    elif isinstance(body, bytes):
        raw = body
    elif isinstance(body, str):
        raw = body.encode("utf-8")
    else:
        filtered = {
            str(k): v
            for k, v in body.items()
            if not str(k).startswith("signature")
            and not str(k).startswith("__netcoin_")
            and k not in {"signed_envelope", "signed_request", "signed_envelope_verified", "api_key", "admin_token"}
        }
        raw = json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def envelope_from_payload(method: str, path: str, body: Mapping[str, Any]) -> SignedEnvelope:
    raw = body.get("signed_envelope") or body.get("signed_request") or {}
    if not isinstance(raw, Mapping):
        raise AppError("signed_envelope must be an object")
    address = normalize_address(str(raw.get("address") or body.get("address") or body.get("trader_address") or ""))
    return SignedEnvelope(
        address=address,
        method=str(raw.get("method") or method).upper(),
        path=str(raw.get("path") or path),
        body_hash=str(raw.get("body_hash") or canonical_body_hash(body)),
        timestamp=int(raw.get("timestamp") or body.get("timestamp") or time.time()),
        nonce=str(raw.get("nonce") or body.get("nonce") or ""),
        signature=str(raw.get("signature") or body.get("signature") or ""),
    )


def verify_signed_envelope(
    method: str, path: str, body: Mapping[str, Any], *, max_age_seconds: int = 300
) -> dict[str, Any]:
    envelope = envelope_from_payload(method, path, body)
    if envelope.method != method.upper():
        raise AppError("signed envelope method mismatch")
    if envelope.path != path:
        raise AppError("signed envelope path mismatch")
    expected_hash = canonical_body_hash(body)
    if not constant_time_equal(envelope.body_hash, expected_hash):
        raise AppError("signed envelope body hash mismatch")
    if abs(int(time.time()) - int(envelope.timestamp)) > max_age_seconds:
        raise AppError("signed envelope timestamp is outside the allowed window")
    if not envelope.nonce:
        raise AppError("signed envelope nonce is required")
    if not envelope.signature:
        raise AppError("signed envelope signature is required")
    if not verify_message(envelope.address, envelope.message(), envelope.signature):
        raise AppError("signed envelope signature does not verify")
    return {"verified": True, "address": envelope.address, "nonce": envelope.nonce, "message": envelope.message()}


def should_require_signed_envelope(method: str, path: str, body: Mapping[str, Any]) -> bool:
    if method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    if bool(body.get("require_signed_envelope")):
        return True
    if os.environ.get("NETCOIN_APP_ALLOW_UNSIGNED_SENSITIVE", "0").lower() in {"1", "true", "yes", "on"}:
        return False
    operator_signature_required = (
        path.startswith("/treasury/proposals/") and path.endswith("/approve")
    ) or (path.startswith("/exchange/withdrawals/") and path.endswith("/approve"))
    if bool(body.get("__netcoin_operator_verified")) and not operator_signature_required:
        return False
    if path in PUBLIC_WRITE_PATHS or (path.startswith("/community/improvements/") and path.endswith("/vote")):
        return False
    sensitive = any(path.startswith(prefix) for prefix in SENSITIVE_WRITE_PREFIXES) or operator_signature_required
    if not sensitive:
        return False
    # Public HTTP writes are strict by default. Direct in-process calls remain
    # compatible unless the operator explicitly forces signed envelopes globally.
    if bool(body.get("__netcoin_http_request")):
        return True
    if os.environ.get("NETCOIN_APP_REQUIRE_SIGNED_ENVELOPES", "0").lower() in {"1", "true", "yes", "on"}:
        return True
    return False


def require_signed_envelope_if_needed(method: str, path: str, body: Mapping[str, Any]) -> dict[str, Any]:
    if should_require_signed_envelope(method, path, body):
        verified = verify_signed_envelope(method, path, body)
        verified["required"] = True
        return verified
    # Not required for this path -- but if the caller voluntarily attached a
    # signed envelope anyway (e.g. a poll vote, escrow action, or bounty
    # submission that wants its actor bound to a real wallet), verify it
    # opportunistically so ownership checks downstream can use it. A missing
    # or invalid envelope on an optional path is not an error: it just means
    # no verified actor is available, and callers fall back to unauthenticated
    # behavior exactly as before this endpoint's signing support existed.
    if body.get("signed_envelope") or body.get("signed_request"):
        try:
            verified = verify_signed_envelope(method, path, body)
            verified["required"] = False
            return verified
        except AppError:
            return {"required": False, "verified": False}
    return {"required": False, "verified": False}


def scope_allows(scopes: list[str], method: str, path: str) -> bool:
    if "*" in scopes:
        return True
    method = method.upper()
    for scope in scopes:
        rule = DEFAULT_SCOPE_MAP.get(scope)
        if not rule:
            continue
        if method in rule or any(path.startswith(str(prefix)) for prefix in rule):
            return True
    return False


def csrf_token(secret: str, session_id: str) -> str:
    return hmac.new(secret.encode(), session_id.encode(), hashlib.sha256).hexdigest()


def verify_csrf_token(secret: str, session_id: str, token: str) -> bool:
    return constant_time_equal(csrf_token(secret, session_id), token)


def webhook_signature(secret: str, body: bytes | str, timestamp: int | None = None) -> str:
    timestamp = int(time.time() if timestamp is None else timestamp)
    raw = body.encode("utf-8") if isinstance(body, str) else body
    payload = str(timestamp).encode() + b"." + raw
    return f"t={timestamp},v1=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_webhook_signature(secret: str, body: bytes | str, header: str, *, max_age_seconds: int = 300) -> bool:
    pieces = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
    timestamp = int(pieces.get("t", "0") or 0)
    if abs(int(time.time()) - timestamp) > max_age_seconds:
        return False
    expected = webhook_signature(secret, body, timestamp).split("v1=", 1)[1]
    return constant_time_equal(pieces.get("v1", ""), expected)
