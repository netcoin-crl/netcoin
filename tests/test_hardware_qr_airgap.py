from __future__ import annotations

from pathlib import Path

import pytest

from netcoin.psbt import PartiallySignedTransaction
from netcoin.signer import HardwareSigner, QrAirgapHardwareTransport, hardware_signer_from_env
from netcoin.tx import SpendableOutput, TxOutput
from netcoin.wallet import Wallet, WalletError


def _sample_psbt(wallet: Wallet) -> PartiallySignedTransaction:
    prevout = SpendableOutput(
        txid="22" * 32,
        vout=0,
        output=TxOutput(amount=100_000, address=wallet.address),
        height=1,
    )
    return PartiallySignedTransaction.create([prevout], [TxOutput(amount=90_000, address=wallet.address)])


def test_qr_airgap_transport_round_trips_signed_psbt(tmp_path: Path):
    wallet = Wallet.create()
    unsigned = _sample_psbt(wallet)
    signed_copy = PartiallySignedTransaction.from_base64(unsigned.to_base64()).sign(wallet)
    request_path = tmp_path / "request.qr"
    transport = QrAirgapHardwareTransport(
        request_path=request_path,
        response_text=QrAirgapHardwareTransport().encode_response(
            {"ok": True, "signed_psbt": signed_copy.to_base64(), "device": "qr-airgap-test"}
        ),
    )
    signer = HardwareSigner("qr-airgap-device", transport=transport, require_real_device=False)

    assert signer.can_sign() is True
    signed = signer.sign_psbt(unsigned)

    assert signed.is_fully_signed()
    request_text = request_path.read_text(encoding="utf-8")
    assert request_text.startswith("netcoin-hw-qr:")
    decoded_request = transport.decode_request(request_text)
    assert decoded_request["protocol"] == "netcoin-hardware-signer-v1"
    assert decoded_request["device_id"] == "qr-airgap-device"
    assert decoded_request["psbt"] == unsigned.to_base64()


def test_qr_airgap_transport_exports_request_until_response_arrives(tmp_path: Path):
    wallet = Wallet.create()
    request_path = tmp_path / "request.qr"
    response_path = tmp_path / "response.qr"
    transport = QrAirgapHardwareTransport(request_path=request_path, response_path=response_path)
    signer = HardwareSigner("qr-airgap-device", transport=transport, require_real_device=False)

    with pytest.raises(WalletError, match="hardware QR request exported"):
        signer.sign_psbt(_sample_psbt(wallet))

    assert request_path.read_text(encoding="utf-8").startswith("netcoin-hw-qr:")


def test_hardware_signer_from_env_accepts_qr_airgap_profile(monkeypatch, tmp_path: Path):
    request_path = tmp_path / "request.qr"
    response_path = tmp_path / "response.qr"
    monkeypatch.setenv("NETCOIN_HARDWARE_SIGNER_DEVICE", "qr-dev-1")
    monkeypatch.setenv("NETCOIN_HARDWARE_SIGNER_QR_REQUEST", str(request_path))
    monkeypatch.setenv("NETCOIN_HARDWARE_SIGNER_QR_RESPONSE", str(response_path))

    signer = hardware_signer_from_env()

    assert signer is not None
    assert signer.device_id == "qr-dev-1"
    assert signer.transport is not None
    assert signer.transport.name == "qr-airgap-hardware-transport"
