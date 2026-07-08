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
from typing import Any

from .tx import SpendableOutput, Transaction, TxInput, TxOutput


class PSBTError(ValueError):
    """Raised when a PSBT cannot be processed."""


@dataclass
class PartiallySignedTransaction:
    tx: Transaction
    prevouts: list[SpendableOutput]

    @classmethod
    def create(
        cls, prevouts: list[SpendableOutput], outputs: list[TxOutput], *, version: int = 1, locktime: int = 0
    ) -> PartiallySignedTransaction:
        """Build an unsigned PSBT from inputs (prevouts) and outputs."""
        if not prevouts:
            raise PSBTError("a PSBT needs at least one input")
        inputs = [TxInput(txid=p.txid, vout=p.vout) for p in prevouts]
        tx = Transaction(inputs=inputs, outputs=list(outputs), version=version, locktime=locktime)
        return cls(tx=tx, prevouts=list(prevouts))

    def to_dict(self) -> dict[str, Any]:
        return {
            "magic": "netcoin-psbt-v1",
            "tx": self.tx.to_dict(include_scripts=True, include_witness=True),
            "prevouts": [prevout.to_dict() for prevout in self.prevouts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PartiallySignedTransaction:
        if data.get("magic") not in {"netcoin-psbt-v1", None} and data.get("format") != "NetCoin PSBT v1":
            raise PSBTError("not a NetCoin PSBT")
        tx_data = data.get("tx", data.get("transaction"))
        prevouts = data.get("prevouts", [])
        return cls(tx=Transaction.from_dict(tx_data), prevouts=[SpendableOutput.from_dict(item) for item in prevouts])

    def to_base64(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    @classmethod
    def from_base64(cls, text: str) -> PartiallySignedTransaction:
        if text.startswith("netpsbt:"):
            text = text[len("netpsbt:") :]
        try:
            return cls.from_dict(json.loads(base64.b64decode(text.encode("ascii")).decode("utf-8")))
        except Exception as exc:
            raise PSBTError("invalid NetCoin PSBT") from exc

    def sign(self, wallet: Any) -> PartiallySignedTransaction:
        for index, prevout in enumerate(self.prevouts):
            if index >= len(self.tx.inputs):
                break
            try:
                self.tx.sign_input(index, wallet.private_key, prevout)
            except Exception:
                continue
        return self

    def _skeleton(self) -> tuple:
        """Identity of the unsigned tx: input outpoints + outputs (no signatures).
        Two PSBTs are combinable iff their skeletons match."""
        inputs = tuple(txin.outpoint() for txin in self.tx.inputs)
        outputs = tuple((o.amount, o.address, o.script_pubkey) for o in self.tx.outputs)
        return (self.tx.version, self.tx.locktime, inputs, outputs)

    def combine(self, other: PartiallySignedTransaction) -> PartiallySignedTransaction:
        """Merge signatures/witnesses from another PSBT of the same unsigned tx.
        Used for multi-party signing where each party signs the inputs it owns."""
        if self._skeleton() != other._skeleton():
            raise PSBTError("cannot combine PSBTs of different transactions")
        for mine, theirs in zip(self.tx.inputs, other.tx.inputs):
            mine_signed = mine.signature or mine.script_sig or mine.witness
            theirs_signed = theirs.signature or theirs.script_sig or theirs.witness
            if not mine_signed and theirs_signed:
                mine.signature = theirs.signature
                mine.public_key = theirs.public_key
                mine.script_sig = theirs.script_sig
                mine.witness = list(theirs.witness)
        return self

    def is_fully_signed(self) -> bool:
        return all(txin.signature or txin.witness or txin.script_sig for txin in self.tx.inputs)

    def finalize(self) -> Transaction:
        """Finalize (signatures are applied inline by sign); same as extract."""
        return self.extract()

    def extract(self) -> Transaction:
        if not self.is_fully_signed():
            raise PSBTError("PSBT is not fully signed")
        return self.tx


def encode_psbt(data: dict[str, Any]) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "netpsbt:" + base64.b64encode(raw).decode("ascii")


def decode_psbt(text: str) -> dict[str, Any]:
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


def combine_psbts(psbt_texts: list[str]) -> str:
    """Combine two or more PSBTs of the same unsigned tx into one, merging
    signatures, and return the netpsbt: base64 string."""
    if not psbt_texts:
        raise PSBTError("nothing to combine")
    combined = PartiallySignedTransaction.from_base64(psbt_texts[0])
    for text in psbt_texts[1:]:
        combined.combine(PartiallySignedTransaction.from_base64(text))
    return "netpsbt:" + combined.to_base64()
