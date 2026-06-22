"""Output descriptors (#28): describe a wallet and resolve descriptors to addresses."""
import pytest

from netcoin.descriptors import (
    DescriptorError,
    describe_wallet,
    descriptor_to_address,
    multisig_descriptor,
)
from netcoin.script import multisig_redeem_script, script_to_p2sh_address
from netcoin.wallet import Wallet


def test_single_key_descriptors_resolve_to_wallet_addresses():
    w = Wallet.create()
    desc = describe_wallet(w)
    assert descriptor_to_address(desc["pkh"]) == w.address
    assert descriptor_to_address(desc["wpkh"]) == w.segwit_address
    assert descriptor_to_address(desc["tr"]) == w.taproot_address
    assert descriptor_to_address(desc["sh_wpkh"]) == w.p2sh_segwit_address


def test_multisig_descriptor_matches_redeem_address():
    keys = [Wallet.create().public_key_hex for _ in range(3)]
    desc = multisig_descriptor(2, keys)
    expected = script_to_p2sh_address(multisig_redeem_script(2, keys))
    assert descriptor_to_address(desc) == expected
    assert desc == f"sh(multi(2,{keys[0]},{keys[1]},{keys[2]}))"


def test_invalid_descriptors_raise():
    with pytest.raises(DescriptorError):
        descriptor_to_address("nope(abcd)")
    with pytest.raises(DescriptorError):
        descriptor_to_address("sh(weird(00))")
    with pytest.raises(DescriptorError):
        descriptor_to_address("pkh(deadbeef")  # unbalanced


def test_descriptors_are_watch_only_no_private_key():
    w = Wallet.create()
    blob = " ".join(describe_wallet(w).values())
    assert w.private_key_hex not in blob
