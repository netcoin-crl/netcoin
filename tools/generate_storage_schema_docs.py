#!/usr/bin/env python3
"""Generate storage schema docs from the SQLite migration code."""

from __future__ import annotations

# Allow `python tools/<script>.py` from the repository root or elsewhere.
import sys as _sys
from pathlib import Path as _Path

_repo_root = _Path(__file__).resolve().parents[1]
if str(_repo_root) not in _sys.path:
    _sys.path.insert(0, str(_repo_root))

import argparse
import sqlite3
from pathlib import Path

from netcoin.storage_migrations import run_migrations, schema_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/STORAGE_SCHEMA.md")
    args = parser.parse_args()
    conn = sqlite3.connect(":memory:")
    run_migrations(conn)
    report = schema_report(conn)
    lines = ["# NetCoin Storage Schema", "", "Generated from `netcoin/storage_migrations.py`.", ""]
    for table in report["tables"]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        lines.append(f"## `{table}`")
        lines.append("")
        lines.append("| Column | Type | Not null | Default | Primary key |")
        lines.append("|---|---|---:|---|---:|")
        for _, name, typ, notnull, default, pk in rows:
            lines.append(f"| `{name}` | `{typ}` | {int(notnull)} | `{default}` | {int(pk)} |")
        lines.append("")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
