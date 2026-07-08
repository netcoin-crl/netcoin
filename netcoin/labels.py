"""A tiny label / address-book store for NetCoin.

Maps addresses (or any key, e.g. peer URLs, txids) to human labels in a JSON file.
This is wallet-adjacent convenience, never consensus or key material.
"""

from __future__ import annotations

import json
from pathlib import Path


class LabelStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.labels: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text())
        except (FileNotFoundError, ValueError):
            data = {}
        if isinstance(data, dict):
            self.labels = {str(k): str(v) for k, v in data.get("labels", data).items() if isinstance(v, str)}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"labels": self.labels}, indent=2, sort_keys=True))

    def set(self, key: str, label: str) -> None:
        if not key:
            raise ValueError("label key cannot be empty")
        self.labels[key] = label
        self._save()

    def get(self, key: str) -> str | None:
        return self.labels.get(key)

    def remove(self, key: str) -> bool:
        existed = key in self.labels
        self.labels.pop(key, None)
        if existed:
            self._save()
        return existed

    def all(self) -> dict[str, str]:
        return dict(sorted(self.labels.items()))
