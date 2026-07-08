"""Signer abstraction for hot, watch-only, offline, hardware, and test wallets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .psbt import PartiallySignedTransaction
from .wallet import Wallet, WalletError


class Signer(Protocol):
    name: str

    def can_sign(self) -> bool: ...

    def sign_psbt(self, psbt: PartiallySignedTransaction) -> PartiallySignedTransaction: ...


@dataclass
class LocalHotWalletSigner:
    wallet: Wallet
    name: str = "local-hot-wallet"

    def can_sign(self) -> bool:
        return True

    def sign_psbt(self, psbt: PartiallySignedTransaction) -> PartiallySignedTransaction:
        return psbt.sign(self.wallet)


@dataclass
class WatchOnlySigner:
    address: str
    name: str = "watch-only"

    def can_sign(self) -> bool:
        return False

    def sign_psbt(self, psbt: PartiallySignedTransaction) -> PartiallySignedTransaction:
        raise WalletError("watch-only signer cannot sign transactions")


@dataclass
class OfflineSigner:
    export_path: str
    name: str = "offline-export"

    def can_sign(self) -> bool:
        return False

    def sign_psbt(self, psbt: PartiallySignedTransaction) -> PartiallySignedTransaction:
        self.write_unsigned(psbt)
        raise WalletError("PSBT exported for offline signing; import a signed PSBT to continue")

    def write_unsigned(self, psbt: PartiallySignedTransaction) -> None:
        from pathlib import Path

        Path(self.export_path).write_text(psbt.to_base64())


@dataclass
class HardwareSigner:
    device_id: str
    name: str = "hardware-signer-placeholder"
    experimental_stub: bool = True

    def can_sign(self) -> bool:
        return False

    def sign_psbt(self, psbt: PartiallySignedTransaction) -> PartiallySignedTransaction:
        raise WalletError(
            "hardware signer is an explicit placeholder; add a real transport adapter "
            "(USB/HID/HWI/vendor SDK) before enabling production hardware signing"
        )


@dataclass
class TestSigner:
    wallet: Wallet
    name: str = "test-signer"

    def can_sign(self) -> bool:
        return True

    def sign_psbt(self, psbt: PartiallySignedTransaction) -> PartiallySignedTransaction:
        return psbt.sign(self.wallet)


def signer_status(signer: Any) -> dict[str, object]:
    return {
        "name": getattr(signer, "name", signer.__class__.__name__),
        "can_sign": bool(signer.can_sign()),
        "experimental_stub": bool(getattr(signer, "experimental_stub", False)),
    }
