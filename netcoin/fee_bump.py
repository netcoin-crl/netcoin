"""RBF and CPFP fee-bump helpers for NetCoin wallets.

These helpers operate on existing transaction primitives without changing
consensus rules. They build replacement/child transactions that the existing
mempool policy can evaluate.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tx import SpendableOutput, Transaction, TxInput, TxOutput
from .wallet import Wallet, WalletError

DEFAULT_RBF_SEQUENCE = 0xFFFFFFFD


@dataclass(frozen=True)
class FeeBumpPlan:
    method: str
    original_txid: str
    new_fee: int
    replacement: Transaction
    note: str

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "original_txid": self.original_txid,
            "new_fee": self.new_fee,
            "replacement_txid": self.replacement.txid(),
            "signals_rbf": self.replacement.signals_rbf,
            "note": self.note,
        }


def transaction_fee(tx: Transaction, prevouts: list[SpendableOutput]) -> int:
    if len(prevouts) != len(tx.inputs):
        raise WalletError("prevout count must match input count")
    return sum(item.output.amount for item in prevouts) - tx.total_output()


def _copy_output(output: TxOutput) -> TxOutput:
    return TxOutput(amount=output.amount, address=output.address, script_pubkey=output.script_pubkey)


def create_rbf_replacement(
    wallet: Wallet,
    original: Transaction,
    prevouts: list[SpendableOutput],
    *,
    new_fee: int,
    change_address: str | None = None,
) -> FeeBumpPlan:
    """Create a signed opt-in-RBF replacement by reducing change.

    The replacement keeps the same input set and output order. It reduces the
    selected change output by the fee delta, preserving all recipient outputs.
    """

    if not original.signals_rbf:
        raise WalletError("original transaction does not signal RBF")
    old_fee = transaction_fee(original, prevouts)
    if new_fee <= old_fee:
        raise WalletError("new fee must be greater than original fee")
    delta = new_fee - old_fee
    outputs = [_copy_output(output) for output in original.outputs]
    if not outputs:
        raise WalletError("cannot fee-bump a transaction with no outputs")
    change_index = len(outputs) - 1
    if change_address:
        for index in range(len(outputs) - 1, -1, -1):
            if outputs[index].address == change_address:
                change_index = index
                break
        else:
            raise WalletError("change address not found in original outputs")
    if outputs[change_index].amount <= delta:
        raise WalletError("change output is too small for requested fee bump")
    outputs[change_index] = TxOutput(
        amount=outputs[change_index].amount - delta,
        address=outputs[change_index].address,
        script_pubkey=outputs[change_index].script_pubkey,
    )
    inputs = [
        TxInput(txid=txin.txid, vout=txin.vout, sequence=min(txin.sequence, DEFAULT_RBF_SEQUENCE))
        for txin in original.inputs
    ]
    replacement = Transaction(inputs=inputs, outputs=outputs, version=original.version, locktime=original.locktime)
    for index, prevout in enumerate(prevouts):
        replacement.sign_input(index, wallet.private_key, prevout)
    return FeeBumpPlan(
        method="rbf",
        original_txid=original.txid(),
        new_fee=new_fee,
        replacement=replacement,
        note="replacement keeps the same inputs and reduces change to pay a higher fee",
    )


def create_cpfp_child(
    wallet: Wallet,
    parent: Transaction,
    *,
    parent_vout: int,
    fee: int,
    destination_address: str | None = None,
) -> FeeBumpPlan:
    """Create a child transaction that spends a parent output with a high fee."""

    if parent_vout < 0 or parent_vout >= len(parent.outputs):
        raise WalletError("parent_vout out of range")
    output = parent.outputs[parent_vout]
    if fee <= 0:
        raise WalletError("CPFP fee must be positive")
    if output.amount <= fee:
        raise WalletError("parent output does not cover child fee")
    address = destination_address or wallet.address
    prevout = SpendableOutput(parent.txid(), parent_vout, output, height=None, coinbase=False)
    child = Transaction(
        inputs=[TxInput(txid=parent.txid(), vout=parent_vout)],
        outputs=[TxOutput(amount=output.amount - fee, address=address)],
    )
    child.sign_input(0, wallet.private_key, prevout)
    return FeeBumpPlan(
        method="cpfp",
        original_txid=parent.txid(),
        new_fee=fee,
        replacement=child,
        note="child spends an unconfirmed parent output and pays the package fee",
    )
