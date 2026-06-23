"""BIP32 HD key derivation (#hd): validated against the official BIP32 test
vectors, plus watch-only (xpub) derivation, round-trips, and NetCoin addresses."""
import pytest

from netcoin.crypto import validate_address
from netcoin.hd import HARDENED, HDError, HDKey, mnemonic_to_seed
from netcoin.wallet import Wallet

VECTOR1_SEED = bytes.fromhex("000102030405060708090a0b0c0d0e0f")


def test_bip32_official_vector1():
    m = HDKey.from_seed(VECTOR1_SEED)
    assert m.extended_private_key() == (
        "xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvvNKmPGJxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHi"
    )
    assert m.neuter().extended_public_key() == (
        "xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJoCu1Rupje8YtGqsefD265TMg7usUDFdp6W1EGMcet8"
    )
    assert m.derive_path("m/0'").extended_private_key() == (
        "xprv9uHRZZhk6KAJC1avXpDAp4MDc3sQKNxDiPvvkX8Br5ngLNv1TxvUxt4cV1rGL5hj6KCesnDYUhd7oWgT11eZG7XnxHrnYeSvkzY7d2bhkJ7"
    )
    assert m.derive_path("m/0'/1").extended_public_key() == (
        "xpub6ASuArnXKPbfEwhqN6e3mwBcDTgzisQN1wXN9BJcM47sSikHjJf3UFHKkNAWbWMiGj7Wf5uMash7SyYq527Hqck2AxYysAA7xmALppuCkwQ"
    )


def test_watch_only_xpub_derivation_matches_private():
    m = HDKey.from_seed(VECTOR1_SEED)
    account = m.derive_path("m/0'")
    # a non-hardened child derived from the public branch == from the private branch
    from_priv = account.derive(5).neuter().extended_public_key()
    from_pub = account.neuter().derive(5).extended_public_key()
    assert from_priv == from_pub


def test_hardened_derivation_from_xpub_is_rejected():
    pub = HDKey.from_seed(VECTOR1_SEED).neuter()
    with pytest.raises(HDError):
        pub.derive(HARDENED)


def test_extended_key_round_trip():
    m = HDKey.from_seed(VECTOR1_SEED).derive_path("m/0'/1")
    assert HDKey.from_extended_key(m.extended_private_key()).extended_private_key() == m.extended_private_key()
    assert HDKey.from_extended_key(m.extended_public_key()).extended_public_key() == m.extended_public_key()


def test_mnemonic_seed_is_deterministic_and_passphrase_sensitive():
    s1 = mnemonic_to_seed("net001 net002 net003")
    s2 = mnemonic_to_seed("net001 net002 net003")
    s3 = mnemonic_to_seed("net001 net002 net003", passphrase="extra")
    assert s1 == s2 and len(s1) == 64
    assert s1 != s3


def test_hd_leaf_produces_valid_netcoin_addresses():
    leaf = HDKey.from_mnemonic("net010 net020 net030").derive_path("m/44'/0'/0'/0/0")
    wallet = Wallet(private_key=leaf.key)
    for kind in ("legacy", "segwit", "taproot", "p2sh-segwit"):
        assert validate_address(wallet.address_for(kind))
    # different indexes give different addresses from one seed
    other = Wallet(private_key=HDKey.from_mnemonic("net010 net020 net030").derive_path("m/44'/0'/0'/0/1").key)
    assert wallet.address_for("legacy") != other.address_for("legacy")
