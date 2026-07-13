"""Esplora-compatible response mapping for NetCoin.

Blockstream's Esplora HTTP API is the de-facto standard consumed by BDK and a
large amount of Bitcoin tooling. Exposing NetCoin data in Esplora's response
shapes lets that tooling point at a NetCoin node with only a URL change.

These are pure mapping functions: they take NetCoin chain objects/dicts and
return Esplora-shaped dicts. The thin HTTP dispatch lives in node.py. Amounts
are satoshis in both systems, so ``value`` fields pass through directly.

Scope: the core read endpoints tooling relies on (tip, block, tx, address,
utxo, fee-estimates). Script-level fields that NetCoin does not model (raw
scriptpubkey hex/asm) are omitted rather than faked; ``scriptpubkey_address``
and ``value`` — the fields wallets actually use — are always present.
"""

from __future__ import annotations

from typing import Any

ESPLORA_SCHEMA_NOTE = "netcoin-esplora-compat-v1"


def _tx_is_coinbase(tx_dict: dict[str, Any]) -> bool:
    inputs = tx_dict.get("inputs") or []
    return bool(inputs) and ("coinbase" in inputs[0])


def esplora_status(
    *, confirmed: bool, block_height: int | None, block_hash: str | None, block_time: int | None
) -> dict[str, Any]:
    status: dict[str, Any] = {"confirmed": bool(confirmed)}
    if confirmed:
        status["block_height"] = block_height
        status["block_hash"] = block_hash
        if block_time is not None:
            status["block_time"] = block_time
    return status


def esplora_vin(input_dict: dict[str, Any]) -> dict[str, Any]:
    is_coinbase = "coinbase" in input_dict
    return {
        "txid": input_dict.get("txid", "0" * 64),
        "vout": int(input_dict.get("vout", -1)),
        "is_coinbase": is_coinbase,
        "sequence": int(input_dict.get("sequence", 0xFFFFFFFF)),
        "scriptsig": input_dict.get("signature", ""),
        "witness": [w for w in [input_dict.get("public_key")] if w],
    }


def esplora_vout(index: int, output_dict: dict[str, Any]) -> dict[str, Any]:
    return {
        "scriptpubkey_address": output_dict.get("address"),
        "value": int(output_dict.get("amount", 0)),
        "n": index,
    }


def esplora_tx(tx_dict: dict[str, Any], *, txid: str, status: dict[str, Any], fee: int | None = None) -> dict[str, Any]:
    vout = [esplora_vout(i, o) for i, o in enumerate(tx_dict.get("outputs") or [])]
    payload: dict[str, Any] = {
        "txid": txid,
        "version": int(tx_dict.get("version", 1)),
        "locktime": int(tx_dict.get("locktime", 0)),
        "vin": [esplora_vin(i) for i in (tx_dict.get("inputs") or [])],
        "vout": vout,
        "value": sum(v["value"] for v in vout),
        "status": status,
    }
    if fee is not None:
        payload["fee"] = int(fee)
    return payload


def esplora_block(header: dict[str, Any], *, block_id: str, tx_count: int) -> dict[str, Any]:
    return {
        "id": block_id,
        "height": int(header.get("height", 0)),
        "version": int(header.get("version", 1)),
        "timestamp": int(header.get("timestamp", 0)),
        "tx_count": int(tx_count),
        "merkle_root": header.get("merkle_root"),
        "previousblockhash": header.get("previous_hash"),
        "nonce": int(header.get("nonce", 0)),
        "bits": header.get("bits"),
    }


def esplora_address(
    summary: dict[str, Any], *, funded_sum: int, spent_sum: int, funded_count: int, spent_count: int
) -> dict[str, Any]:
    return {
        "address": summary.get("address"),
        "chain_stats": {
            "funded_txo_count": int(funded_count),
            "funded_txo_sum": int(funded_sum),
            "spent_txo_count": int(spent_count),
            "spent_txo_sum": int(spent_sum),
            "tx_count": int(summary.get("transaction_count", 0)),
        },
        # NetCoin's address summary does not separate mempool stats yet; report
        # zeros honestly rather than inventing per-mempool accounting.
        "mempool_stats": {
            "funded_txo_count": 0,
            "funded_txo_sum": 0,
            "spent_txo_count": 0,
            "spent_txo_sum": 0,
            "tx_count": 0,
        },
    }


def esplora_utxo(utxo_dict: dict[str, Any], *, status: dict[str, Any]) -> dict[str, Any]:
    output = utxo_dict.get("output") or {}
    return {
        "txid": utxo_dict.get("txid"),
        "vout": int(utxo_dict.get("vout", 0)),
        "value": int(output.get("amount", utxo_dict.get("amount", 0))),
        "status": status,
    }


def esplora_fee_estimates(fee_payload: dict[str, Any]) -> dict[str, Any]:
    """Map NetCoin's slow/normal/fast presets to Esplora's target->rate map."""
    presets = fee_payload.get("presets", {})

    def rate(name: str) -> float:
        kvb = int(presets.get(name, {}).get("fee_rate_per_kvb", 1000))
        return round(max(1.0, kvb / 1000.0), 3)  # sat/vB

    fast, normal, slow = rate("fast"), rate("normal"), rate("slow")
    # Esplora returns a confirmation-target -> sat/vB map.
    return {"1": fast, "2": fast, "3": normal, "6": normal, "10": slow, "25": slow, "144": slow}
