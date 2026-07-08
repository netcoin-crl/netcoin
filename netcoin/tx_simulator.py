"""Pre-signing transaction simulator for wallet UX."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .tx import Transaction, sats_to_amount
from .wallet_risk import RiskWarning, detect_address_poisoning, output_dust_warning, score_warnings


def simulate_transaction(
    chain: Any,
    tx: Transaction,
    *,
    wallet_addresses: Iterable[str] = (),
    frozen_outpoints: Iterable[str] = (),
    recent_addresses: Iterable[str] = (),
    high_fee_bps: int = 500,
    max_inputs_warning: int = 25,
) -> dict[str, Any]:
    """Return a wallet-friendly transaction preview without changing state."""
    wallet_set = {str(a) for a in wallet_addresses if a}
    frozen_set = {str(op) for op in frozen_outpoints}
    utxos = chain.utxo_set() if hasattr(chain, "utxo_set") else {}
    warnings: list[RiskWarning] = []
    inputs = []
    input_sats = 0
    for txin in tx.inputs:
        outpoint = txin.outpoint()
        utxo = utxos.get(outpoint)
        amount = int(utxo.output.amount) if utxo else 0
        address = getattr(utxo.output, "address", "") if utxo else ""
        input_sats += amount
        entry = {
            "outpoint": outpoint,
            "amount_sats": amount,
            "amount": sats_to_amount(amount),
            "address": address,
            "known": utxo is not None,
            "frozen": outpoint in frozen_set,
        }
        inputs.append(entry)
        if outpoint in frozen_set:
            warnings.append(
                RiskWarning("frozen_coin", "high", "Transaction spends a frozen coin.", {"outpoint": outpoint})
            )
        if utxo is None:
            warnings.append(
                RiskWarning(
                    "unknown_input", "high", "Input is not in the current confirmed UTXO set.", {"outpoint": outpoint}
                )
            )
    outputs = []
    output_sats = 0
    for index, output in enumerate(tx.outputs):
        amount = int(output.amount)
        output_sats += amount
        is_change = bool(output.address and output.address in wallet_set)
        entry = {
            "vout": index,
            "address": output.address,
            "amount_sats": amount,
            "amount": sats_to_amount(amount),
            "is_change": is_change,
        }
        outputs.append(entry)
        dust = output_dust_warning(output.address, amount)
        if dust:
            warnings.append(dust)
        if output.address and not is_change:
            poison = detect_address_poisoning(output.address, recent_addresses)
            if poison["suspicious"]:
                warnings.append(
                    RiskWarning(
                        "address_poisoning",
                        "high",
                        "Destination resembles a recent address but is not identical.",
                        {"address": output.address, **poison},
                    )
                )
            if hasattr(chain, "address_index") and output.address in getattr(chain, "address_index", {}):
                warnings.append(
                    RiskWarning(
                        "address_reuse",
                        "medium",
                        "Destination address already appears on-chain.",
                        {"address": output.address},
                    )
                )
    fee_sats = max(0, input_sats - output_sats)
    if len(tx.inputs) > max_inputs_warning:
        warnings.append(
            RiskWarning(
                "many_inputs",
                "medium",
                "Transaction spends many inputs and may be expensive or hard to relay.",
                {"input_count": len(tx.inputs), "threshold": max_inputs_warning},
            )
        )
    if input_sats and fee_sats * 10_000 // input_sats > int(high_fee_bps):
        warnings.append(
            RiskWarning(
                "high_fee",
                "high",
                "Fee is high relative to the input amount.",
                {"fee_sats": fee_sats, "input_sats": input_sats, "threshold_bps": high_fee_bps},
            )
        )
    fee_rate = fee_sats / max(1, tx.vsize()) if hasattr(tx, "vsize") else 0.0
    risk = score_warnings(warnings)
    return {
        "txid": tx.txid(),
        "input_sats": input_sats,
        "output_sats": output_sats,
        "fee_sats": fee_sats,
        "input": sats_to_amount(input_sats),
        "output": sats_to_amount(output_sats),
        "fee": sats_to_amount(fee_sats),
        "fee_rate_sats_per_vbyte": round(fee_rate, 4),
        "inputs": inputs,
        "outputs": outputs,
        "change_outputs": [o for o in outputs if o["is_change"]],
        "recipient_outputs": [o for o in outputs if not o["is_change"]],
        **risk,
    }
