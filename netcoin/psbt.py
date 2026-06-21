"""Very small PSBT-like container for NetCoin.

Bitcoin's Partially Signed Bitcoin Transaction format is large and precise. This
NetCoin version captures the workflow: create an unsigned transaction plus UTXO
metadata, sign it later, then extract the final transaction. It also includes
small encode/decode helpers for CLI workflows.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, List

from .tx import SpendableOutput, Transaction


class PSBTError(ValueError):
    """Raised when a PSBT cannot be processed."""


@dataclass
class PartiallySignedTransaction:
    tx: Transaction
    prevouts: List[SpendableOutput]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "magic": "netcoin-psbt-v1",
            "tx": self.tx.to_dict(include_scripts=True, include_witness=True),
            "prevouts": [prevout.to_dict() for prevout in self.prevouts],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PartiallySignedTransaction":
        if data.get("magic") not in {"netcoin-psbt-v1", None} and data.get("format") != "NetCoin PSBT v1":
            raise PSBTError("not a NetCoin PSBT")
        tx_data = data.get("tx", data.get("transaction"))
        prevouts = data.get("prevouts", [])
        return cls(tx=Transaction.from_dict(tx_data), prevouts=[SpendableOutput.from_dict(item) for item in prevouts])

    def to_base64(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    @classmethod
    def from_base64(cls, text: str) -> "PartiallySignedTransaction":
        if text.startswith("netpsbt:"):
            text = text[len("netpsbt:") :]
        try:
            return cls.from_dict(json.loads(base64.b64decode(text.encode("ascii")).decode("utf-8")))
        except Exception as exc:
            raise PSBTError("invalid NetCoin PSBT") from exc

    def sign(self, wallet: Any) -> "PartiallySignedTransaction":
        for index, prevout in enumerate(self.prevouts):
            if index >= len(self.tx.inputs):
                break
            try:
                self.tx.sign_input(index, wallet.private_key, prevout)
            except Exception:
                continue
        return self

    def is_fully_signed(self) -> bool:
        return all(txin.signature or txin.witness for txin in self.tx.inputs)

    def extract(self) -> Transaction:
        if not self.is_fully_signed():
            raise PSBTError("PSBT is not fully signed")
        return self.tx


def encode_psbt(data: Dict[str, Any]) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "netpsbt:" + base64.b64encode(raw).decode("ascii")


def decode_psbt(text: str) -> Dict[str, Any]:
    if text.startswith("netpsbt:"):
        text = text[len("netpsbt:") :]
    try:
        return json.loads(base64.b64decode(text).decode("utf-8"))
    except Exception as exc:
        raise PSBTError("invalid NetCoin PSBT") from exc


def sign_psbt(psbt_text: str, wallet: Any) -> str:
    psbt = PartiallySignedTransaction.from_base64(psbt_text)
    psbt.sign(wallet)
    return "netpsbt:" + psbt.to_base64()


def finalize_psbt(psbt_text: str) -> Transaction:
    psbt = PartiallySignedTransaction.from_base64(psbt_text)
    return psbt.extract()
