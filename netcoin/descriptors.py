"""Output descriptors for NetCoin wallets (an educational subset of BIP380).

Supports single-key descriptors pkh()/wpkh()/tr()/sh(wpkh()) and multisig
sh(multi(m,...)). Descriptors are a compact, watch-only way to describe which
scripts a wallet owns without exposing private keys.

Examples:
  pkh(<pubkey_hex>)            -> legacy P2PKH address
  wpkh(<pubkey_hex>)           -> SegWit P2WPKH address
  tr(<xonly_hex>)              -> Taproot P2TR address
  sh(wpkh(<pubkey_hex>))       -> P2SH-SegWit address
  sh(multi(m,<pub1>,<pub2>...))-> P2SH multisig address
"""
from __future__ import annotations

from typing import Any, Dict, List

from .crypto import (
    hash160,
    public_key_to_address,
    public_key_to_p2wpkh_address,
    public_key_to_taproot_address,
)
from .script import multisig_redeem_script, p2wpkh_script, script_to_p2sh_address


class DescriptorError(ValueError):
    """Raised when a descriptor cannot be parsed or resolved."""


def describe_wallet(wallet: Any) -> Dict[str, str]:
    """Return the standard single-key descriptors for a wallet."""
    pub = wallet.public_key_hex
    return {
        "pkh": f"pkh({pub})",
        "wpkh": f"wpkh({pub})",
        "sh_wpkh": f"sh(wpkh({pub}))",
        "tr": f"tr({wallet.xonly_public_key_hex})",
    }


def multisig_descriptor(required: int, pubkeys_hex: List[str]) -> str:
    return f"sh(multi({required},{','.join(pubkeys_hex)}))"


def _inner(text: str, prefix: str) -> str:
    if not (text.startswith(prefix + "(") and text.endswith(")")):
        raise DescriptorError(f"expected {prefix}(...)")
    return text[len(prefix) + 1 : -1]


def descriptor_to_address(descriptor: str) -> str:
    """Resolve a descriptor to the NetCoin address it describes."""
    d = descriptor.strip()
    if d.startswith("pkh("):
        return public_key_to_address(bytes.fromhex(_inner(d, "pkh")))
    if d.startswith("wpkh("):
        return public_key_to_p2wpkh_address(bytes.fromhex(_inner(d, "wpkh")))
    if d.startswith("tr("):
        return public_key_to_taproot_address(bytes.fromhex(_inner(d, "tr")))
    if d.startswith("sh("):
        inner = _inner(d, "sh")
        if inner.startswith("wpkh("):
            pub = bytes.fromhex(_inner(inner, "wpkh"))
            return script_to_p2sh_address(p2wpkh_script(hash160(pub).hex()))
        if inner.startswith("multi("):
            args = _inner(inner, "multi").split(",")
            if len(args) < 2:
                raise DescriptorError("multi() needs a threshold and at least one key")
            required = int(args[0])
            pubkeys = [k.strip() for k in args[1:]]
            return script_to_p2sh_address(multisig_redeem_script(required, pubkeys))
        raise DescriptorError("unsupported sh() inner descriptor")
    raise DescriptorError(f"unsupported descriptor: {descriptor}")
