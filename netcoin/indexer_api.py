"""Convenience functions for exposing indexer data through an API layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .indexer import ChainIndexer


def rebuild_indexer(chain: Any, data_dir: str | Path) -> dict[str, Any]:
    return ChainIndexer(Path(data_dir) / "explorer-index.sqlite").rebuild(chain)


def address_history(data_dir: str | Path, address: str, limit: int = 100) -> dict[str, Any]:
    return ChainIndexer(Path(data_dir) / "explorer-index.sqlite").address_history(address, limit=limit)


def indexer_summary(data_dir: str | Path) -> dict[str, Any]:
    return ChainIndexer(Path(data_dir) / "explorer-index.sqlite").summary()


def address_profile(data_dir: str | Path, address: str) -> dict[str, Any]:
    return ChainIndexer(Path(data_dir) / "explorer-index.sqlite").address_profile(address)


def top_addresses(data_dir: str | Path, limit: int = 25) -> dict[str, Any]:
    return ChainIndexer(Path(data_dir) / "explorer-index.sqlite").top_addresses(limit)


def mempool_summary(data_dir: str | Path) -> dict[str, Any]:
    return ChainIndexer(Path(data_dir) / "explorer-index.sqlite").mempool_summary()


def indexer_integrity(data_dir: str | Path) -> dict[str, Any]:
    return ChainIndexer(Path(data_dir) / "explorer-index.sqlite").integrity_report()
