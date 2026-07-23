#!/usr/bin/env python3
"""Copy shared shell assets to every public site folder."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITES = ROOT / "sites"
SHARED = SITES / "shared"
ASSETS = ("site-shell.css", "site-shell.js")


def site_dirs() -> list[Path]:
    return sorted(p for p in SITES.iterdir() if p.is_dir() and p.name not in {"shared", "tests"})


def sync() -> list[str]:
    changed: list[str] = []
    for site in site_dirs():
        for name in ASSETS:
            src = SHARED / name
            dst = site / name
            if not src.exists():
                raise SystemExit(f"missing shared asset: {src}")
            before = dst.read_bytes() if dst.exists() else b""
            data = src.read_bytes()
            if before != data:
                dst.write_bytes(data)
                changed.append(str(dst.relative_to(ROOT)))
    return changed


if __name__ == "__main__":
    changed = sync()
    print({"synced": len(changed), "files": changed})
