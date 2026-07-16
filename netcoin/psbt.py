"""Very small PSBT-like container for NetCoin.

Bitcoin's Partially Signed Bitcoin Transaction format is large and precise. This
NetCoin version captures the workflow: create an unsigned transaction plus UTXO
metadata, sign it later, then extract the final transaction. It also includes
small encode/decode helpers for CLI workflows.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

from .crypto import bytes_to_hex, ecdsa_sign, private_key_to_public_key
from .script import ScriptError, op_n_value, script_hash160, tokenize
from .tx import SIGHASH_ALL, SpendableOutput, Transaction, TxInput, TxOutput, _append_sighash


class PSBTError(ValueError):
    """Raised when a PSBT cannot be processed."""


@dataclass
class PartiallySignedTransaction:
    tx: Transaction
    prevouts: list[SpendableOutput]
    # Multisig-only bookkeeping, kept entirely at the PSBT layer so it never
    # touches Transaction's consensus-serialized fields. Keyed by input index.
    # redeem_scripts: the P2SH multisig redeem script text for that input.
    # partial_sigs: pubkey_hex -> signature_hex collected so far for that input.
    redeem_scripts: dict[int, str] = field(default_factory=dict)
    partial_sigs: dict[int, dict[str, str]] = field(default_factory=dict)

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
            "redeem_scripts": {str(k): v for k, v in self.redeem_scripts.items()},
            "partial_sigs": {str(k): dict(v) for k, v in self.partial_sigs.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PartiallySignedTransaction:
        if data.get("magic") not in {"netcoin-psbt-v1", None} and data.get("format") != "NetCoin PSBT v1":
            raise PSBTError("not a NetCoin PSBT")
        tx_data = data.get("tx", data.get("transaction"))
        prevouts = data.get("prevouts", [])
        return cls(
            tx=Transaction.from_dict(tx_data),
            prevouts=[SpendableOutput.from_dict(item) for item in prevouts],
            redeem_scripts={int(k): v for k, v in (data.get("redeem_scripts") or {}).items()},
            partial_sigs={int(k): dict(v) for k, v in (data.get("partial_sigs") or {}).items()},
        )

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

    @staticmethod
    def _multisig_pubkeys(redeem_script: str) -> list[str]:
        """Pubkeys in the order they appear in the redeem script. OP_CHECKMULTISIG
        matches signatures against pubkeys in this order, so it's also the order
        finalize() must place signatures in."""
        tokens = tokenize(redeem_script)
        if len(tokens) < 4 or tokens[-1] != "OP_CHECKMULTISIG":
            raise PSBTError("not a multisig redeem script")
        return tokens[1:-2]

    @staticmethod
    def _multisig_required(redeem_script: str) -> int:
        tokens = tokenize(redeem_script)
        try:
            return op_n_value(tokens[0])
        except ScriptError as exc:
            raise PSBTError("not a multisig redeem script") from exc

    def set_multisig_input(self, index: int, redeem_script: str) -> None:
        """Mark input `index` as a P2SH-multisig spend with this redeem
        script. Every cosigner must set the same redeem script (it's what
        `sign_multisig_input` validates their pubkey against and what
        `combine`/`extract` use to assemble the final scriptSig)."""
        if index < 0 or index >= len(self.tx.inputs):
            raise PSBTError("input index out of range")
        self._multisig_pubkeys(redeem_script)  # validates shape
        self.redeem_scripts[index] = redeem_script
        self.partial_sigs.setdefault(index, {})

    def sign_multisig_input(self, index: int, wallet: Any) -> None:
        """Add this signer's signature to a multisig input. Safe to call from
        any number of cosigners on separate copies of the PSBT -- combine()
        merges the per-pubkey signatures rather than overwriting."""
        redeem_script = self.redeem_scripts.get(index)
        if redeem_script is None:
            raise PSBTError(f"input {index} has no redeem script; call set_multisig_input first")
        public_key = bytes_to_hex(private_key_to_public_key(wallet.private_key, compressed=True))
        if public_key not in self._multisig_pubkeys(redeem_script):
            raise PSBTError("this wallet's public key is not part of the multisig redeem script")
        prevout = self.prevouts[index]
        digest = self.tx.sighash(index, prevout, SIGHASH_ALL)
        signature = _append_sighash(ecdsa_sign(wallet.private_key, digest), SIGHASH_ALL)
        self.partial_sigs.setdefault(index, {})[public_key] = bytes_to_hex(signature)

    def is_multisig_input_ready(self, index: int) -> bool:
        redeem_script = self.redeem_scripts.get(index)
        if redeem_script is None:
            return False
        required = self._multisig_required(redeem_script)
        pubkeys = set(self._multisig_pubkeys(redeem_script))
        collected = {pk for pk in self.partial_sigs.get(index, {}) if pk in pubkeys}
        return len(collected) >= required

    def _finalize_multisig_input(self, index: int) -> None:
        redeem_script = self.redeem_scripts[index]
        required = self._multisig_required(redeem_script)
        ordered_pubkeys = self._multisig_pubkeys(redeem_script)
        sigs = self.partial_sigs.get(index, {})
        # OP_CHECKMULTISIG advances through signatures and pubkeys together in
        # a single forward pass, so the signatures must appear in the same
        # relative order as their pubkeys in the redeem script.
        ordered_sigs = [sigs[pk] for pk in ordered_pubkeys if pk in sigs][:required]
        if len(ordered_sigs) < required:
            raise PSBTError(f"multisig input {index} needs {required} signatures, has {len(ordered_sigs)}")
        redeem_hex = redeem_script.encode("utf-8").hex()
        self.tx.inputs[index].script_sig = " ".join([*ordered_sigs, redeem_hex])

    def combine(self, other: PartiallySignedTransaction) -> PartiallySignedTransaction:
        """Merge signatures/witnesses from another PSBT of the same unsigned
        tx. Handles two distinct multi-signer shapes: different cosigners
        each fully signing the inputs they individually own (first-signed
        wins, the original behavior), and multiple cosigners each partially
        signing the *same* multisig input (partial signatures merge by
        pubkey, since a single input needs signatures from more than one
        key)."""
        if self._skeleton() != other._skeleton():
            raise PSBTError("cannot combine PSBTs of different transactions")
        for index, (mine, theirs) in enumerate(zip(self.tx.inputs, other.tx.inputs)):
            mine_signed = mine.signature or mine.script_sig or mine.witness
            theirs_signed = theirs.signature or theirs.script_sig or theirs.witness
            if not mine_signed and theirs_signed:
                mine.signature = theirs.signature
                mine.public_key = theirs.public_key
                mine.script_sig = theirs.script_sig
                mine.witness = list(theirs.witness)
            if index in other.redeem_scripts and index not in self.redeem_scripts:
                self.redeem_scripts[index] = other.redeem_scripts[index]
            if index in other.partial_sigs:
                self.partial_sigs.setdefault(index, {}).update(other.partial_sigs[index])
        return self

    def is_fully_signed(self) -> bool:
        for index, txin in enumerate(self.tx.inputs):
            if index in self.redeem_scripts:
                if not self.is_multisig_input_ready(index):
                    return False
                continue
            if not (txin.signature or txin.witness or txin.script_sig):
                return False
        return True

    def finalize(self) -> Transaction:
        """Finalize: assemble multisig scriptSigs from collected partial
        signatures, then extract."""
        return self.extract()

    def extract(self) -> Transaction:
        if not self.is_fully_signed():
            raise PSBTError("PSBT is not fully signed")
        for index in self.redeem_scripts:
            self._finalize_multisig_input(index)
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
