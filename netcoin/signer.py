"""Signer abstraction for hot, watch-only, offline, hardware, and test wallets."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
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
        Path(self.export_path).write_text(psbt.to_base64())


class HardwareTransport(Protocol):
    """Minimal hardware-signer transport contract.

    A production wallet can implement this protocol with USB/HID, HWI, a vendor
    SDK, or a bridge daemon. The transport receives a JSON-safe request and must
    return a JSON-safe response containing a signed NetCoin PSBT.
    """

    name: str

    def available(self) -> bool: ...

    def sign_psbt(self, request: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class CommandHardwareTransport:
    """Run an external hardware-signer bridge command.

    The command receives a JSON request on stdin and must print JSON on stdout:
    {"ok": true, "signed_psbt": "..."}. This works with vendor CLI wrappers
    and keeps device-specific USB/HID code out of NetCoin core.
    """

    command: list[str]
    name: str = "command-hardware-transport"
    timeout_seconds: int = 30

    def available(self) -> bool:
        return bool(self.command)

    def sign_psbt(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self.available():
            raise WalletError("hardware transport command is not configured")
        try:
            result = subprocess.run(
                self.command,
                input=json.dumps(request, sort_keys=True),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise WalletError(f"hardware signer command not found: {self.command[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise WalletError("hardware signer timed out") from exc
        if result.returncode != 0:
            raise WalletError(result.stderr.strip() or "hardware signer command failed")
        try:
            return json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise WalletError("hardware signer returned invalid JSON") from exc


@dataclass
class FileHardwareTransport:
    """File drop transport for air-gapped or vendor-gui hardware signing.

    `sign_psbt` writes the request to `request_path` and reads a signed response
    from `response_path` if it already exists. This makes a reviewable workflow
    possible without pretending NetCoin has native vendor support.
    """

    request_path: str | Path
    response_path: str | Path
    name: str = "file-hardware-transport"

    def available(self) -> bool:
        return True

    def sign_psbt(self, request: dict[str, Any]) -> dict[str, Any]:
        Path(self.request_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.request_path).write_text(json.dumps(request, indent=2, sort_keys=True))
        response = Path(self.response_path)
        if not response.exists():
            raise WalletError(
                f"hardware request exported to {self.request_path}; place signed response at {self.response_path}"
            )
        try:
            return json.loads(response.read_text())
        except json.JSONDecodeError as exc:
            raise WalletError("hardware response file is not valid JSON") from exc


@dataclass
class SimulatedHardwareTransport:
    """Test/dev transport that delegates signing to a Wallet.

    This is intentionally named simulated so production code can reject it when
    `require_real_device=True` is set.
    """

    wallet: Wallet
    name: str = "simulated-hardware-transport"
    simulated: bool = True

    def available(self) -> bool:
        return True

    def sign_psbt(self, request: dict[str, Any]) -> dict[str, Any]:
        psbt = PartiallySignedTransaction.from_base64(str(request.get("psbt", "")))
        psbt.sign(self.wallet)
        return {"ok": True, "signed_psbt": psbt.to_base64(), "device": "simulated"}


@dataclass
class HardwareSigner:
    device_id: str
    transport: HardwareTransport | None = None
    name: str = "hardware-signer-placeholder"
    derivation_path: str = "m/44'/0'/0'/0/0"
    require_real_device: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def experimental_stub(self) -> bool:
        return self.transport is None

    def can_sign(self) -> bool:
        if self.transport is None or not self.transport.available():
            return False
        if self.require_real_device and bool(getattr(self.transport, "simulated", False)):
            return False
        return True

    def request_payload(self, psbt: PartiallySignedTransaction) -> dict[str, Any]:
        return {
            "protocol": "netcoin-hardware-signer-v1",
            "device_id": self.device_id,
            "derivation_path": self.derivation_path,
            "psbt": psbt.to_base64(),
            "tx_summary": {
                "inputs": len(psbt.tx.inputs),
                "outputs": len(psbt.tx.outputs),
                "txid_preview": psbt.tx.txid()[:16],
            },
            "metadata": dict(self.metadata),
        }

    def sign_psbt(self, psbt: PartiallySignedTransaction) -> PartiallySignedTransaction:
        if self.transport is None:
            raise WalletError(
                "hardware signer transport is not configured; attach CommandHardwareTransport, "
                "FileHardwareTransport, or a vendor adapter"
            )
        if self.require_real_device and bool(getattr(self.transport, "simulated", False)):
            raise WalletError("simulated hardware transport is disabled for this signer")
        response = self.transport.sign_psbt(self.request_payload(psbt))
        if not response.get("ok", True):
            raise WalletError(str(response.get("error") or "hardware signer rejected request"))
        signed = response.get("signed_psbt") or response.get("psbt")
        if not signed:
            raise WalletError("hardware signer did not return signed_psbt")
        return PartiallySignedTransaction.from_base64(str(signed))

    def export_request(self, psbt: PartiallySignedTransaction, path: str | Path | None = None) -> dict[str, Any]:
        payload = self.request_payload(psbt)
        if path:
            Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True))
        return payload


@dataclass
class TestSigner:
    wallet: Wallet
    name: str = "test-signer"

    def can_sign(self) -> bool:
        return True

    def sign_psbt(self, psbt: PartiallySignedTransaction) -> PartiallySignedTransaction:
        return psbt.sign(self.wallet)


def signer_status(signer: Any) -> dict[str, object]:
    transport = getattr(signer, "transport", None)
    return {
        "name": getattr(signer, "name", signer.__class__.__name__),
        "can_sign": bool(signer.can_sign()),
        "experimental_stub": bool(getattr(signer, "experimental_stub", False)),
        "transport": getattr(transport, "name", ""),
        "device_id": getattr(signer, "device_id", ""),
    }


def hardware_signer_from_env(prefix: str = "NETCOIN_HARDWARE_SIGNER") -> HardwareSigner | None:
    """Create a hardware signer from environment configuration.

    Supported forms:
      NETCOIN_HARDWARE_SIGNER_COMMAND='vendor-cli sign-netcoin'
      NETCOIN_HARDWARE_SIGNER_REQUEST=/tmp/netcoin-hw-request.json
      NETCOIN_HARDWARE_SIGNER_RESPONSE=/tmp/netcoin-hw-response.json
    """
    device_id = os.environ.get(f"{prefix}_DEVICE", "default")
    command = os.environ.get(f"{prefix}_COMMAND", "").strip()
    if command:
        import shlex

        return HardwareSigner(device_id=device_id, transport=CommandHardwareTransport(shlex.split(command)))
    request_path = os.environ.get(f"{prefix}_REQUEST", "").strip()
    response_path = os.environ.get(f"{prefix}_RESPONSE", "").strip()
    if request_path and response_path:
        return HardwareSigner(device_id=device_id, transport=FileHardwareTransport(request_path, response_path))
    return None


def hardware_request_roundtrip_file(psbt: PartiallySignedTransaction, *, response_psbt: str) -> dict[str, Path]:
    """Small helper for integration tests and manual demos."""
    tmp = Path(tempfile.mkdtemp(prefix="netcoin-hw-"))
    request = tmp / "request.json"
    response = tmp / "response.json"
    response.write_text(json.dumps({"ok": True, "signed_psbt": response_psbt}, sort_keys=True))
    HardwareSigner("file-demo", FileHardwareTransport(request, response), require_real_device=False).sign_psbt(psbt)
    return {"request": request, "response": response}
