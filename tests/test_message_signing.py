"""Bitcoin-style signed messages (signmessage / verifymessage): recoverable
signatures verify against an address without needing the public key."""

from netcoin.crypto import message_digest, sign_message, verify_message
from netcoin.wallet import Wallet

MSG = "NetCoin rocks"


def test_sign_and_verify_roundtrip():
    w = Wallet.create()
    sig = sign_message(w.private_key, MSG)
    assert verify_message(w.address_for("legacy"), MSG, sig) is True
    # the same key's P2WPKH address also verifies
    assert verify_message(w.address_for("segwit"), MSG, sig) is True


def test_wrong_message_or_address_fails():
    w = Wallet.create()
    other = Wallet.create()
    sig = sign_message(w.private_key, MSG)
    assert verify_message(w.address_for("legacy"), "tampered", sig) is False
    assert verify_message(other.address_for("legacy"), MSG, sig) is False


def test_malformed_signature_is_rejected():
    w = Wallet.create()
    assert verify_message(w.address_for("legacy"), MSG, "not-base64!!") is False
    assert verify_message(w.address_for("legacy"), MSG, "AAAA") is False


def test_signature_is_recoverable_format():
    import base64

    w = Wallet.create()
    raw = base64.b64decode(sign_message(w.private_key, MSG))
    assert len(raw) == 65 and 27 <= raw[0] <= 34  # header byte + r || s


def test_message_digest_is_deterministic():
    assert message_digest("a") == message_digest("a")
    assert message_digest("a") != message_digest("b")
