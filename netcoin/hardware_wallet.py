"""Hardware-wallet source integration primitives for NetCoin M2.

This module does not pretend to talk to a physical Ledger/Trezor in CI. It
defines the strict request/transcript contract used by WebUSB/WebHID, PSBT
file, and QR-airgap flows, plus deterministic validation helpers for source
tests and operator-supplied physical-device evidence.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from .psbt import PSBTError, PartiallySignedTransaction

TRANSCRIPT_SCHEMA = "netcoin-hardware-device-transcript-v1"
SUPPORTED_DEVICE_FAMILIES = ("ledger", "trezor")
SUPPORTED_TRANSPORTS = ("webusb", "webhid", "file-psbt", "qr-airgap")
SUPPORTED_NETWORKS = ("testnet", "mainnet-dry-run")
DEFAULT_DERIVATION_PATH = "m/84'/0'/0'/0/0"


class HardwareWalletError(ValueError):
    """Raised when hardware-wallet request or transcript data is invalid."""


def stable_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def hardware_challenge(psbt_text: str, *, device_family: str, derivation_path: str) -> str:
    material = {
        "device_family": normalize_device_family(device_family),
        "derivation_path": derivation_path,
        "psbt_sha256": hashlib.sha256(psbt_text.encode("utf-8")).hexdigest(),
    }
    return stable_hash(material)


def normalize_device_family(value: str) -> str:
    family = value.strip().lower()
    aliases = {
        "ledger nano s plus": "ledger",
        "ledger nano x": "ledger",
        "ledger": "ledger",
        "trezor model t": "trezor",
        "trezor safe 3": "trezor",
        "trezor": "trezor",
    }
    if family not in aliases:
        raise HardwareWalletError(f"unsupported hardware-wallet device family: {value}")
    return aliases[family]


def validate_transport(value: str) -> str:
    transport = value.strip().lower()
    if transport not in SUPPORTED_TRANSPORTS:
        raise HardwareWalletError(f"unsupported hardware-wallet transport: {value}")
    return transport


def validate_network(value: str) -> str:
    network = value.strip().lower()
    if network not in SUPPORTED_NETWORKS:
        raise HardwareWalletError(f"unsupported hardware-wallet network: {value}")
    return network


@dataclass(frozen=True)
class HardwareSignRequest:
    """Canonical request passed to a hardware signer.

    The request intentionally carries a PSBT, not private key material. Device
    UX must display at least the network, derivation path, receive/change
    address material, output summary, and fee before returning a signature.
    """

    psbt: str
    device_family: str = "ledger"
    transport: str = "webhid"
    network: str = "testnet"
    derivation_path: str = DEFAULT_DERIVATION_PATH
    created_at: int = 0

    def __post_init__(self) -> None:
        if not self.psbt.startswith("netpsbt:"):
            raise HardwareWalletError("hardware signing request requires a netpsbt: payload")
        object.__setattr__(self, "device_family", normalize_device_family(self.device_family))
        object.__setattr__(self, "transport", validate_transport(self.transport))
        object.__setattr__(self, "network", validate_network(self.network))
        if not self.derivation_path.startswith("m/"):
            raise HardwareWalletError("derivation path must start with m/")
        if not self.created_at:
            object.__setattr__(self, "created_at", int(time.time()))

    @property
    def challenge(self) -> str:
        return hardware_challenge(self.psbt, device_family=self.device_family, derivation_path=self.derivation_path)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": "netcoin-hardware-sign-request-v1",
            "network": self.network,
            "device_family": self.device_family,
            "transport": self.transport,
            "derivation_path": self.derivation_path,
            "psbt": self.psbt,
            "psbt_sha256": hashlib.sha256(self.psbt.encode("utf-8")).hexdigest(),
            "challenge": self.challenge,
            "created_at": self.created_at,
            "private_key_material_included": False,
        }
        payload["request_hash"] = stable_hash(payload)
        return payload


def build_hardware_sign_request(
    psbt_text: str,
    *,
    device_family: str = "ledger",
    transport: str = "webhid",
    network: str = "testnet",
    derivation_path: str = DEFAULT_DERIVATION_PATH,
) -> dict[str, Any]:
    return HardwareSignRequest(
        psbt=psbt_text,
        device_family=device_family,
        transport=transport,
        network=network,
        derivation_path=derivation_path,
    ).to_dict()


REQUIRED_TRANSCRIPT_FIELDS = (
    "schema",
    "device_family",
    "device_model",
    "firmware_version",
    "transport",
    "network",
    "derivation_path",
    "psbt_sha256",
    "challenge",
    "address_reviewed_on_device",
    "tx_reviewed_on_device",
    "fee_reviewed_on_device",
    "change_reviewed_on_device",
    "signed_psbt",
    "operator_attestation",
    "evidence_hash",
)


def _is_sha256_hex(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in text)


def validate_hardware_transcript(transcript: dict[str, Any]) -> list[str]:
    """Return validation issues for a physical-device signing transcript."""

    issues: list[str] = []
    for field in REQUIRED_TRANSCRIPT_FIELDS:
        if transcript.get(field) in (None, "", [], {}):
            issues.append(f"missing transcript field: {field}")
    if transcript.get("schema") != TRANSCRIPT_SCHEMA:
        issues.append(f"schema must be {TRANSCRIPT_SCHEMA}")
    try:
        normalize_device_family(str(transcript.get("device_family", "")))
    except HardwareWalletError as exc:
        issues.append(str(exc))
    try:
        validate_transport(str(transcript.get("transport", "")))
    except HardwareWalletError as exc:
        issues.append(str(exc))
    try:
        validate_network(str(transcript.get("network", "")))
    except HardwareWalletError as exc:
        issues.append(str(exc))
    for field in (
        "address_reviewed_on_device",
        "tx_reviewed_on_device",
        "fee_reviewed_on_device",
        "change_reviewed_on_device",
    ):
        if transcript.get(field) is not True:
            issues.append(f"{field} must be true")
    for field in ("psbt_sha256", "challenge"):
        if transcript.get(field) and not _is_sha256_hex(transcript.get(field)):
            issues.append(f"{field} must be a 64-character hex digest")
    signed = str(transcript.get("signed_psbt", ""))
    if signed and not signed.startswith("netpsbt:"):
        issues.append("signed_psbt must be a netpsbt: payload")
    elif signed:
        try:
            PartiallySignedTransaction.from_base64(signed)
        except PSBTError:
            issues.append("signed_psbt must decode as a NetCoin PSBT")
    body = {k: v for k, v in transcript.items() if k != "evidence_hash"}
    expected = stable_hash(body)
    if transcript.get("evidence_hash") != expected:
        issues.append("evidence_hash mismatch; expected " + expected)
    return issues
