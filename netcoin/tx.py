"""Transaction primitives for NetCoin."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

from .crypto import (
    address_type,
    bytes_to_hex,
    double_sha256,
    ecdsa_sign,
    ecdsa_verify,
    hex_to_bytes,
    private_key_to_public_key,
    private_key_to_xonly_public_key,
    public_key_to_address,
    public_key_to_p2wpkh_address,
    public_key_to_taproot_address,
    schnorr_sign,
    schnorr_verify,
    validate_address,
)
from .params import COIN, MAX_MONEY, ZERO_HASH
from .script import ScriptContext, address_to_script_pubkey, classify_script, p2pkh_script, verify_script


class TransactionError(ValueError):
    """Raised when a transaction is malformed or invalid."""


@dataclass(frozen=True)
class TxOutput:
    amount: int
    address: str = ""
    script_pubkey: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", int(self.amount))
        if self.amount < 0:
            raise TransactionError("output amount cannot be negative")
        if self.amount > MAX_MONEY:
            raise TransactionError("output amount exceeds MAX_MONEY")
        if self.amount > 0 and not self.address and not self.script_pubkey:
            raise TransactionError("output must have an address or script_pubkey")
        if self.amount > 0 and self.address and not validate_address(self.address):
            raise TransactionError("output address is not a valid NetCoin address")

    def effective_script_pubkey(self) -> str:
        if self.script_pubkey:
            return self.script_pubkey
        if self.address:
            return address_to_script_pubkey(self.address)
        return ""

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"amount": self.amount, "address": self.address}
        # Only include script_pubkey when it was explicitly present. This keeps
        # old NetCoin txids stable for already-mined JSON-chain transactions.
        if self.script_pubkey:
            data["script_pubkey"] = self.script_pubkey
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TxOutput":
        return cls(
            amount=int(data["amount"]),
            address=str(data.get("address", "")),
            script_pubkey=str(data.get("script_pubkey", "")),
        )


@dataclass
class TxInput:
    txid: str
    vout: int
    signature: str = ""
    public_key: str = ""
    coinbase: str = ""
    script_sig: str = ""
    witness: List[str] = field(default_factory=list)
    sequence: int = 0xFFFFFFFF

    def __post_init__(self) -> None:
        if len(self.txid) != 64 or any(c not in "0123456789abcdefABCDEF" for c in self.txid):
            raise TransactionError("input txid must be a 32-byte hex string")
        self.txid = self.txid.lower()
        self.vout = int(self.vout)
        self.sequence = int(self.sequence)
        if not 0 <= self.sequence <= 0xFFFFFFFF:
            raise TransactionError("input sequence must fit uint32")
        self.witness = [str(item).lower() for item in (self.witness or [])]

    def outpoint(self) -> str:
        return f"{self.txid}:{self.vout}"

    def to_dict(self, include_scripts: bool = True, include_witness: bool = True) -> Dict[str, Any]:
        data: Dict[str, Any] = {"txid": self.txid, "vout": self.vout}
        if include_scripts:
            # Preserve original fields unconditionally for backward-compatible
            # txids of v1 NetCoin JSON transactions.
            data.update({"signature": self.signature, "public_key": self.public_key, "coinbase": self.coinbase})
            if self.script_sig:
                data["script_sig"] = self.script_sig
        if include_witness and self.witness:
            data["witness"] = list(self.witness)
        if self.sequence != 0xFFFFFFFF:
            data["sequence"] = self.sequence
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TxInput":
        return cls(
            txid=str(data["txid"]),
            vout=int(data["vout"]),
            signature=str(data.get("signature", "")),
            public_key=str(data.get("public_key", "")),
            coinbase=str(data.get("coinbase", "")),
            script_sig=str(data.get("script_sig", "")),
            witness=[str(item) for item in data.get("witness", [])],
            sequence=int(data.get("sequence", 0xFFFFFFFF)),
        )


@dataclass
class Transaction:
    inputs: List[TxInput]
    outputs: List[TxOutput]
    version: int = 1
    locktime: int = 0

    def __post_init__(self) -> None:
        if not self.inputs:
            raise TransactionError("transaction must have at least one input")
        if not isinstance(self.outputs, list):
            raise TransactionError("transaction outputs must be a list")
        self.version = int(self.version)
        self.locktime = int(self.locktime)
        if self.locktime < 0 or self.locktime > 0xFFFFFFFF:
            raise TransactionError("locktime must fit uint32")

    @property
    def is_coinbase(self) -> bool:
        return (
            len(self.inputs) == 1
            and self.inputs[0].txid == ZERO_HASH
            and self.inputs[0].vout == -1
            and bool(self.inputs[0].coinbase)
        )

    @property
    def has_witness(self) -> bool:
        return any(txin.witness for txin in self.inputs)

    @property
    def signals_rbf(self) -> bool:
        return any(txin.sequence < 0xFFFFFFFE for txin in self.inputs)

    def to_dict(self, include_scripts: bool = True, include_witness: bool = True) -> Dict[str, Any]:
        return {
            "version": self.version,
            "inputs": [txin.to_dict(include_scripts=include_scripts, include_witness=include_witness) for txin in self.inputs],
            "outputs": [txout.to_dict() for txout in self.outputs],
            "locktime": self.locktime,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        return cls(
            version=int(data.get("version", 1)),
            inputs=[TxInput.from_dict(item) for item in data["inputs"]],
            outputs=[TxOutput.from_dict(item) for item in data.get("outputs", [])],
            locktime=int(data.get("locktime", 0)),
        )

    def serialize(self, include_scripts: bool = True, include_witness: bool = False) -> bytes:
        return canonical_json(self.to_dict(include_scripts=include_scripts, include_witness=include_witness))

    def to_bytes(self, include_witness: bool = True, include_scripts: bool = True) -> bytes:
        from .serialization import serialize_transaction

        return serialize_transaction(self, include_witness=include_witness, include_scripts=include_scripts)

    @classmethod
    def from_hex(cls, raw_hex: str) -> "Transaction":
        # NetCoin can encode raw tx hex, but full binary decoding of every script
        # template is intentionally not consensus-critical yet.
        raise TransactionError("raw binary transaction decoding is not implemented; use JSON import/export")

    def raw_hex(self, include_witness: bool = True) -> str:
        return self.to_bytes(include_witness=include_witness).hex()

    def txid(self) -> str:
        # Witness is deliberately excluded, matching the SegWit txid/wtxid split.
        # For legacy v1 NetCoin transactions, this remains the same as before.
        return double_sha256(self.serialize(include_scripts=True, include_witness=False)).hex()

    def wtxid(self) -> str:
        return double_sha256(self.serialize(include_scripts=True, include_witness=True)).hex()

    def stripped_txid(self) -> str:
        return double_sha256(self.serialize(include_scripts=False, include_witness=False)).hex()

    def total_output(self) -> int:
        return sum(output.amount for output in self.outputs)

    def sighash(self, input_index: int, prevout: "SpendableOutput") -> bytes:
        if input_index < 0 or input_index >= len(self.inputs):
            raise TransactionError("input index out of range")
        if self.is_coinbase:
            raise TransactionError("coinbase transactions are not signed")
        payload = {
            "version": self.version,
            "inputs": [txin.to_dict(include_scripts=False, include_witness=False) for txin in self.inputs],
            "outputs": [txout.to_dict() for txout in self.outputs],
            "locktime": self.locktime,
            "signing_input_index": input_index,
            "prevout": {
                "txid": prevout.txid,
                "vout": prevout.vout,
                "amount": prevout.output.amount,
                "address": prevout.output.address,
                "script_pubkey": prevout.output.effective_script_pubkey(),
            },
            "sighash_type": "NETCOIN_ALL",
        }
        return double_sha256(canonical_json(payload))

    def sign_input(self, input_index: int, private_key: int, prevout: "SpendableOutput") -> None:
        public_key = private_key_to_public_key(private_key, compressed=True)
        digest = self.sighash(input_index, prevout)
        script_pubkey = prevout.output.effective_script_pubkey()
        kind = classify_script(script_pubkey)
        txin = self.inputs[input_index]

        if kind == "p2wpkh" or (prevout.output.address and address_type(prevout.output.address) == "p2wpkh"):
            expected_address = public_key_to_p2wpkh_address(public_key)
            if prevout.output.address and expected_address != prevout.output.address:
                raise TransactionError("private key does not control the selected P2WPKH UTXO")
            txin.witness = [bytes_to_hex(ecdsa_sign(private_key, digest)), bytes_to_hex(public_key)]
            txin.signature = ""
            txin.public_key = ""
            return

        if kind == "p2tr" or (prevout.output.address and address_type(prevout.output.address) == "p2tr"):
            xonly = private_key_to_xonly_public_key(private_key)
            expected_address = public_key_to_taproot_address(xonly)
            if prevout.output.address and expected_address != prevout.output.address:
                raise TransactionError("private key does not control the selected Taproot UTXO")
            txin.witness = [bytes_to_hex(schnorr_sign(private_key, digest))]
            txin.signature = ""
            txin.public_key = ""
            return

        # Legacy P2PKH-compatible path. This preserves the original NetCoin fields.
        expected_address = public_key_to_address(public_key)
        if prevout.output.address and expected_address != prevout.output.address:
            raise TransactionError("private key does not control the selected UTXO")
        signature = ecdsa_sign(private_key, digest)
        txin.public_key = bytes_to_hex(public_key)
        txin.signature = bytes_to_hex(signature)
        txin.script_sig = f"{txin.signature} {txin.public_key}"

    def verify_input(self, input_index: int, prevout: "SpendableOutput") -> bool:
        txin = self.inputs[input_index]
        script_pubkey = prevout.output.effective_script_pubkey()
        kind = classify_script(script_pubkey)
        digest = self.sighash(input_index, prevout)
        context = ScriptContext(sighash=digest, locktime=self.locktime, sequence=txin.sequence)

        if kind == "p2wpkh":
            try:
                if len(txin.witness) != 2:
                    return False
                signature = bytes.fromhex(txin.witness[0])
                public_key = bytes.fromhex(txin.witness[1])
                expected_hash = script_pubkey.split()[1]
                if p2pkh_script(expected_hash) != address_to_script_pubkey(public_key_to_address(public_key)):
                    # The line above checks formatting, but the real test is the HASH160 below.
                    pass
                from .crypto import hash160

                if hash160(public_key).hex() != expected_hash:
                    return False
                return ecdsa_verify(public_key, digest, signature)
            except (ValueError, IndexError):
                return False

        if kind == "p2tr":
            try:
                if len(txin.witness) != 1:
                    return False
                signature = bytes.fromhex(txin.witness[0])
                xonly = bytes.fromhex(script_pubkey.split()[1])
                return schnorr_verify(xonly, digest, signature)
            except (ValueError, IndexError):
                return False

        if kind == "p2sh":
            return verify_script(txin.script_sig, script_pubkey, context)

        if txin.script_sig:
            return verify_script(txin.script_sig, script_pubkey, context)

        # Backward-compatible original P2PKH verification path.
        try:
            public_key = hex_to_bytes(txin.public_key)
            signature = hex_to_bytes(txin.signature)
        except ValueError:
            return False
        if public_key_to_address(public_key) != prevout.output.address:
            return False
        return ecdsa_verify(public_key, digest, signature)


@dataclass(frozen=True)
class SpendableOutput:
    txid: str
    vout: int
    output: TxOutput
    height: int
    coinbase: bool = False

    def outpoint(self) -> str:
        return f"{self.txid}:{self.vout}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "txid": self.txid,
            "vout": self.vout,
            "output": self.output.to_dict(),
            "height": self.height,
            "coinbase": self.coinbase,
            "script_type": classify_script(self.output.effective_script_pubkey()) if self.output.effective_script_pubkey() else "unknown",
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpendableOutput":
        return cls(
            txid=str(data["txid"]),
            vout=int(data["vout"]),
            output=TxOutput.from_dict(data["output"]),
            height=int(data["height"]),
            coinbase=bool(data.get("coinbase", False)),
        )


def canonical_json(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def create_coinbase_transaction(height: int, address: str, amount: int, extra_nonce: int = 0) -> Transaction:
    if amount < 0 or amount > MAX_MONEY:
        raise TransactionError("coinbase amount is outside allowed range")
    if amount > 0 and not validate_address(address):
        raise TransactionError("coinbase address is not a valid NetCoin address")
    coinbase_text = f"NetCoin block {height} coinbase {extra_nonce}"
    outputs = [] if amount == 0 else [TxOutput(amount=amount, address=address)]
    return Transaction(inputs=[TxInput(txid=ZERO_HASH, vout=-1, coinbase=coinbase_text)], outputs=outputs)


def amount_to_sats(value: str) -> int:
    try:
        decimal = Decimal(value)
    except InvalidOperation as exc:
        raise TransactionError("amount is not a valid decimal number") from exc
    if decimal < 0:
        raise TransactionError("amount cannot be negative")
    satoshis = decimal * COIN
    if satoshis != satoshis.to_integral_value():
        raise TransactionError("amount has more than 8 decimal places")
    amount = int(satoshis)
    if amount > MAX_MONEY:
        raise TransactionError("amount exceeds MAX_MONEY")
    return amount


def sats_to_amount(satoshis: int) -> str:
    decimal = Decimal(satoshis) / Decimal(COIN)
    return f"{decimal:.8f}"


def ensure_unique_inputs(inputs: Iterable[TxInput]) -> None:
    seen = set()
    for txin in inputs:
        outpoint = txin.outpoint()
        if outpoint in seen:
            raise TransactionError("transaction spends the same outpoint more than once")
        seen.add(outpoint)

# Runtime convenience methods used by RPC/CLI/explorer.
def _tx_weight(self: Transaction) -> int:
    from .serialization import transaction_weight

    return transaction_weight(self)


def _tx_vsize(self: Transaction) -> int:
    from .serialization import transaction_vsize

    return transaction_vsize(self)


Transaction.weight = _tx_weight  # type: ignore[attr-defined]
Transaction.vsize = _tx_vsize  # type: ignore[attr-defined]
