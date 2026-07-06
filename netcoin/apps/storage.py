"""Storage helpers for the app-layer package.

The public AppStore API remains exported from ``netcoin.apps`` for backward
compatibility.  This module holds shared storage constants/helpers used by the
package split so market, routing, security, and payout code can continue moving
out of the legacy monolith incrementally.
"""

from __future__ import annotations

DEFAULT_STORAGE_BACKEND = "sqlite"
VALID_STORAGE_BACKENDS = {"json", "sqlite", "sqlite3"}


def normalize_storage_backend(value: str | None) -> str:
    """Return a supported storage backend name.

    SQLite is the production-safe default for app-layer state because it gives
    atomic writes and safer durability for market/order/wallet records.  JSON is
    still available by explicitly setting ``NETCOIN_APP_STORAGE=json`` for very
    small local demos or migration/debugging.
    """
    backend = (value or DEFAULT_STORAGE_BACKEND).strip().lower()
    if backend not in VALID_STORAGE_BACKENDS:
        return DEFAULT_STORAGE_BACKEND
    return backend
