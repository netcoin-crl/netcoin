"""Offline signing import/export helpers."""

from __future__ import annotations

from pathlib import Path

from .psbt import PartiallySignedTransaction
from .wallet import Wallet


def export_unsigned_psbt(psbt: PartiallySignedTransaction, path: str | Path) -> dict[str, object]:
    path = Path(path)
    path.write_text(psbt.to_base64())
    return {"ok": True, "unsigned_psbt": str(path)}


def sign_psbt_file(wallet: Wallet, source: str | Path, dest: str | Path) -> dict[str, object]:
    source = Path(source)
    dest = Path(dest)
    psbt = PartiallySignedTransaction.from_base64(source.read_text().strip())
    signed = psbt.sign(wallet)
    dest.write_text(signed.to_base64())
    return {"ok": True, "signed_psbt": str(dest)}
