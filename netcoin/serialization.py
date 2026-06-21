"""Bitcoin-style binary serialization helpers for NetCoin.

NetCoin stores blocks as JSON for readability, but this module exports raw
transaction and block bytes with Bitcoin-like framing: little-endian integers,
CompactSize varints, reversed hashes on the wire, SegWit marker/flag, witness
stacks, and scriptPubKey bytes. The script bytecode is an educational text
encoding of NetCoin Script assembly, not byte-for-byte Bitcoin Script.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


class SerializationError(ValueError):
    """Raised when raw data is malformed."""


def ser_uint32(value: int) -> bytes:
    return int(value).to_bytes(4, "little", signed=False)


def ser_int32(value: int) -> bytes:
    return int(value).to_bytes(4, "little", signed=True)


def ser_uint64(value: int) -> bytes:
    return int(value).to_bytes(8, "little", signed=False)


def ser_hash(hex_hash: str) -> bytes:
    return bytes.fromhex(hex_hash)[::-1]


def ser_varint(value: int) -> bytes:
    value = int(value)
    if value < 0:
        raise SerializationError("varint cannot be negative")
    if value < 0xFD:
        return bytes([value])
    if value <= 0xFFFF:
        return b"\xfd" + value.to_bytes(2, "little")
    if value <= 0xFFFFFFFF:
        return b"\xfe" + value.to_bytes(4, "little")
    return b"\xff" + value.to_bytes(8, "little")


def read_varint(data: bytes, offset: int) -> Tuple[int, int]:
    if offset >= len(data):
        raise SerializationError("truncated varint")
    prefix = data[offset]
    offset += 1
    if prefix < 0xFD:
        return prefix, offset
    if prefix == 0xFD:
        return int.from_bytes(data[offset : offset + 2], "little"), offset + 2
    if prefix == 0xFE:
        return int.from_bytes(data[offset : offset + 4], "little"), offset + 4
    return int.from_bytes(data[offset : offset + 8], "little"), offset + 8


def ser_bytes(data: bytes) -> bytes:
    return ser_varint(len(data)) + data


def script_to_wire_bytes(script: str) -> bytes:
    return script.encode("utf-8")


def serialize_tx_input(txin: Any, include_script: bool = True) -> bytes:
    result = ser_hash(txin.txid)
    result += int(txin.vout & 0xFFFFFFFF).to_bytes(4, "little", signed=False)
    if include_script:
        if getattr(txin, "coinbase", ""):
            script = str(txin.coinbase).encode("utf-8")
        else:
            script = script_to_wire_bytes(getattr(txin, "script_sig", ""))
    else:
        script = b""
    result += ser_bytes(script)
    result += ser_uint32(getattr(txin, "sequence", 0xFFFFFFFF))
    return result


def serialize_tx_output(txout: Any) -> bytes:
    from .script import address_to_script_pubkey

    script = getattr(txout, "script_pubkey", "") or (address_to_script_pubkey(txout.address) if getattr(txout, "address", "") else "")
    return ser_uint64(txout.amount) + ser_bytes(script_to_wire_bytes(script))


def serialize_transaction(tx: Any, include_witness: bool = True, include_scripts: bool = True) -> bytes:
    has_witness = include_witness and any(getattr(txin, "witness", []) for txin in tx.inputs)
    result = ser_int32(tx.version)
    if has_witness:
        result += b"\x00\x01"
    result += ser_varint(len(tx.inputs))
    for txin in tx.inputs:
        result += serialize_tx_input(txin, include_script=include_scripts)
    result += ser_varint(len(tx.outputs))
    for txout in tx.outputs:
        result += serialize_tx_output(txout)
    if has_witness:
        for txin in tx.inputs:
            witness = getattr(txin, "witness", [])
            result += ser_varint(len(witness))
            for item in witness:
                result += ser_bytes(bytes.fromhex(item))
    result += ser_uint32(tx.locktime)
    return result


def transaction_weight(tx: Any) -> int:
    stripped = len(serialize_transaction(tx, include_witness=False, include_scripts=True))
    total = len(serialize_transaction(tx, include_witness=True, include_scripts=True))
    return stripped * 3 + total


def transaction_vsize(tx: Any) -> int:
    return (transaction_weight(tx) + 3) // 4


def serialize_header(header: Any) -> bytes:
    result = ser_int32(header.version)
    result += ser_hash(header.previous_hash)
    result += ser_hash(header.merkle_root)
    result += ser_uint32(header.timestamp)
    result += ser_uint32(header.bits)
    result += ser_uint32(header.nonce)
    return result


def serialize_block(block: Any, include_witness: bool = True) -> bytes:
    result = serialize_header(block.header)
    result += ser_varint(len(block.transactions))
    for tx in block.transactions:
        result += serialize_transaction(tx, include_witness=include_witness)
    return result


def block_weight(block: Any) -> int:
    stripped = len(serialize_block(block, include_witness=False))
    total = len(serialize_block(block, include_witness=True))
    return stripped * 3 + total


def tx_to_raw_hex(tx: Any, include_witness: bool = True) -> str:
    return serialize_transaction(tx, include_witness=include_witness).hex()


def block_to_raw_hex(block: Any, include_witness: bool = True) -> str:
    return serialize_block(block, include_witness=include_witness).hex()


# ---------------------------------------------------------------------------
# Lossless binary codec (round-trips full NetCoin objects, preserving txid/hash).
# This is an optional compact binary mode alongside JSON; unlike the Bitcoin-style
# raw hex above, it encodes every field (signatures, coinbase text, witness,
# height) so deserialize(serialize(x)) == x.
# ---------------------------------------------------------------------------

def _ser_str(value: str) -> bytes:
    raw = (value or "").encode("utf-8")
    return ser_varint(len(raw)) + raw


def _read_str(data: bytes, offset: int) -> Tuple[str, int]:
    length, offset = read_varint(data, offset)
    return data[offset : offset + length].decode("utf-8"), offset + length


def tx_to_binary(tx: Any) -> bytes:
    out = ser_int32(tx.version) + ser_uint32(tx.locktime)
    out += ser_varint(len(tx.inputs))
    for txin in tx.inputs:
        out += bytes.fromhex(txin.txid)
        out += int(txin.vout & 0xFFFFFFFF).to_bytes(4, "little")
        out += ser_uint32(txin.sequence)
        out += _ser_str(txin.signature) + _ser_str(txin.public_key)
        out += _ser_str(txin.coinbase) + _ser_str(txin.script_sig)
        out += ser_varint(len(txin.witness))
        for item in txin.witness:
            out += _ser_str(item)
    out += ser_varint(len(tx.outputs))
    for txout in tx.outputs:
        out += ser_uint64(txout.amount)
        out += _ser_str(txout.address) + _ser_str(txout.script_pubkey)
    return out


def tx_from_binary(data: bytes, offset: int = 0) -> Tuple[Any, int]:
    from .tx import Transaction, TxInput, TxOutput

    version = int.from_bytes(data[offset : offset + 4], "little", signed=True)
    offset += 4
    locktime = int.from_bytes(data[offset : offset + 4], "little")
    offset += 4
    vin_count, offset = read_varint(data, offset)
    inputs = []
    for _ in range(vin_count):
        txid = data[offset : offset + 32].hex()
        offset += 32
        vout = int.from_bytes(data[offset : offset + 4], "little")
        if vout == 0xFFFFFFFF:
            vout = -1
        offset += 4
        sequence = int.from_bytes(data[offset : offset + 4], "little")
        offset += 4
        signature, offset = _read_str(data, offset)
        public_key, offset = _read_str(data, offset)
        coinbase, offset = _read_str(data, offset)
        script_sig, offset = _read_str(data, offset)
        wit_count, offset = read_varint(data, offset)
        witness = []
        for _ in range(wit_count):
            item, offset = _read_str(data, offset)
            witness.append(item)
        inputs.append(TxInput(txid=txid, vout=vout, signature=signature, public_key=public_key,
                              coinbase=coinbase, script_sig=script_sig, witness=witness, sequence=sequence))
    vout_count, offset = read_varint(data, offset)
    outputs = []
    for _ in range(vout_count):
        amount = int.from_bytes(data[offset : offset + 8], "little")
        offset += 8
        address, offset = _read_str(data, offset)
        script_pubkey, offset = _read_str(data, offset)
        outputs.append(TxOutput(amount=amount, address=address, script_pubkey=script_pubkey))
    return Transaction(inputs=inputs, outputs=outputs, version=version, locktime=locktime), offset


def block_to_binary(block: Any) -> bytes:
    h = block.header
    out = ser_int32(h.version) + bytes.fromhex(h.previous_hash) + bytes.fromhex(h.merkle_root)
    out += ser_uint32(h.timestamp) + ser_uint32(h.bits) + ser_uint32(h.nonce) + ser_varint(h.height)
    out += ser_varint(len(block.transactions))
    for tx in block.transactions:
        out += tx_to_binary(tx)
    return out


def block_from_binary(data: bytes, offset: int = 0) -> Any:
    from .block import Block, BlockHeader

    version = int.from_bytes(data[offset : offset + 4], "little", signed=True)
    offset += 4
    previous_hash = data[offset : offset + 32].hex()
    offset += 32
    merkle_root = data[offset : offset + 32].hex()
    offset += 32
    timestamp = int.from_bytes(data[offset : offset + 4], "little")
    offset += 4
    bits = int.from_bytes(data[offset : offset + 4], "little")
    offset += 4
    nonce = int.from_bytes(data[offset : offset + 4], "little")
    offset += 4
    height, offset = read_varint(data, offset)
    tx_count, offset = read_varint(data, offset)
    transactions = []
    for _ in range(tx_count):
        tx, offset = tx_from_binary(data, offset)
        transactions.append(tx)
    header = BlockHeader(version=version, previous_hash=previous_hash, merkle_root=merkle_root,
                         timestamp=timestamp, bits=bits, nonce=nonce, height=height)
    return Block(header=header, transactions=transactions)


def decode_raw_transaction(raw_hex: str) -> Dict[str, Any]:
    data = bytes.fromhex(raw_hex)
    offset = 0
    if len(data) < 10:
        raise SerializationError("raw transaction is too short")
    version = int.from_bytes(data[offset : offset + 4], "little", signed=True)
    offset += 4
    has_witness = False
    if offset + 2 <= len(data) and data[offset : offset + 2] == b"\x00\x01":
        has_witness = True
        offset += 2
    vin_count, offset = read_varint(data, offset)
    vin: List[Dict[str, Any]] = []
    for _ in range(vin_count):
        prev_hash = data[offset : offset + 32][::-1].hex()
        offset += 32
        vout = int.from_bytes(data[offset : offset + 4], "little")
        offset += 4
        script_len, offset = read_varint(data, offset)
        script = data[offset : offset + script_len].decode("utf-8", errors="replace")
        offset += script_len
        sequence = int.from_bytes(data[offset : offset + 4], "little")
        offset += 4
        vin.append({"txid": prev_hash, "vout": vout, "scriptSig": script, "sequence": sequence})
    vout_count, offset = read_varint(data, offset)
    vout_items: List[Dict[str, Any]] = []
    for n in range(vout_count):
        amount = int.from_bytes(data[offset : offset + 8], "little")
        offset += 8
        script_len, offset = read_varint(data, offset)
        script = data[offset : offset + script_len].decode("utf-8", errors="replace")
        offset += script_len
        vout_items.append({"n": n, "value_sats": amount, "scriptPubKey": script})
    if has_witness:
        for item in vin:
            count, offset = read_varint(data, offset)
            stack = []
            for _ in range(count):
                size, offset = read_varint(data, offset)
                stack.append(data[offset : offset + size].hex())
                offset += size
            item["txinwitness"] = stack
    locktime = int.from_bytes(data[offset : offset + 4], "little") if offset + 4 <= len(data) else None
    return {"version": version, "vin": vin, "vout": vout_items, "has_witness": has_witness, "locktime": locktime}
