"""Route helper boundary for app-layer HTTP handlers."""

from __future__ import annotations


def strip_app_prefix(path: str) -> str:
    if path.startswith("/api"):
        path = path[4:] or "/"
    if path.startswith("/app"):
        path = path[4:] or "/"
    return path
