"""Educational Lightning-style payment channels for NetCoin.

Two parties lock funds in a 2-of-2 multisig output (the *funding* output, on
chain), then make unlimited **off-chain** payments by re-agreeing the balance
split. Only opening and the cooperative close touch the chain — everything in
between is instant and free.

This deliberately omits the hard parts of real Lightning (revocation/penalty for
old states, HTLCs, routing, unilateral close). It demonstrates the core idea:
settle on-chain rarely, transact off-chain freely, secured by a 2-of-2 multisig.
"""

from __future__ import annotations

from dataclasses import dataclass

from .crypto import ecdsa_sign
from .script import multisig_redeem_script, script_to_p2sh_address
from .tx import SpendableOutput, Transaction, TxInput, TxOutput


@dataclass
class PaymentChannel:
    pubkey_a: str
    pubkey_b: str
    capacity: int
    balance_a: int
    balance_b: int
    version: int = 0
    funding_txid: str | None = None
    funding_vout: int = 0

    @property
    def redeem_script(self) -> str:
        return multisig_redeem_script(2, [self.pubkey_a, self.pubkey_b])

    @property
    def address(self) -> str:
        """The 2-of-2 funding address — send the channel capacity here to open."""
        return script_to_p2sh_address(self.redeem_script)

    @classmethod
    def open(cls, pubkey_a: str, pubkey_b: str, capacity: int, balance_a: int | None = None) -> PaymentChannel:
        a = capacity if balance_a is None else balance_a
        if not 0 <= a <= capacity:
            raise ValueError("balance_a out of range")
        return cls(pubkey_a=pubkey_a, pubkey_b=pubkey_b, capacity=capacity, balance_a=a, balance_b=capacity - a)

    def set_funding(self, txid: str, vout: int, amount: int | None = None) -> None:
        self.funding_txid = txid
        self.funding_vout = vout
        if amount is not None:
            self.capacity = amount
            if self.balance_a + self.balance_b != amount:
                # All capacity starts on the funder's (A's) side by default.
                self.balance_a, self.balance_b = amount, 0

    def pay(self, sender: str, amount: int) -> dict:
        """Move `amount` across the channel off-chain. sender is 'a' or 'b'."""
        if amount <= 0:
            raise ValueError("amount must be positive")
        if sender == "a":
            if amount > self.balance_a:
                raise ValueError("insufficient channel balance on A's side")
            self.balance_a -= amount
            self.balance_b += amount
        elif sender == "b":
            if amount > self.balance_b:
                raise ValueError("insufficient channel balance on B's side")
            self.balance_b -= amount
            self.balance_a += amount
        else:
            raise ValueError("sender must be 'a' or 'b'")
        self.version += 1
        return {"balance_a": self.balance_a, "balance_b": self.balance_b, "version": self.version}

    def funding_prevout(self) -> SpendableOutput:
        if self.funding_txid is None:
            raise ValueError("channel is not funded yet")
        return SpendableOutput(
            txid=self.funding_txid,
            vout=self.funding_vout,
            output=TxOutput(amount=self.capacity, address=self.address),
            height=0,
            coinbase=False,
        )

    def settlement_tx(self, addr_a: str, addr_b: str, fee: int = 0) -> Transaction:
        """Build the cooperative-close transaction paying out the final balances."""
        if self.funding_txid is None:
            raise ValueError("channel is not funded yet")
        out_a = self.balance_a - fee  # the funder (A) covers the close fee
        if out_a < 0:
            raise ValueError("A's balance is too low to cover the fee")
        outputs: list[TxOutput] = []
        if out_a > 0:
            outputs.append(TxOutput(amount=out_a, address=addr_a))
        if self.balance_b > 0:
            outputs.append(TxOutput(amount=self.balance_b, address=addr_b))
        if not outputs:
            raise ValueError("nothing to settle")
        return Transaction(
            inputs=[TxInput(txid=self.funding_txid, vout=self.funding_vout)], outputs=outputs, locktime=0
        )

    def cosign(self, tx: Transaction, privkey_a: int, privkey_b: int) -> Transaction:
        """Both parties sign the close tx's 2-of-2 input (cooperative close)."""
        digest = tx.sighash(0, self.funding_prevout())
        sig_a = ecdsa_sign(privkey_a, digest).hex()
        sig_b = ecdsa_sign(privkey_b, digest).hex()
        tx.inputs[0].script_sig = f"OP_0 {sig_a} {sig_b} {self.redeem_script.encode('utf-8').hex()}"
        return tx
