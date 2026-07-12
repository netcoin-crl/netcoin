"""WebUSB/WebHID hardware-wallet bridge contracts for NetCoin.

The browser-specific JavaScript talks to Ledger/Trezor devices through WebUSB or
WebHID. This Python module defines the deterministic session payload and the
strict transcript requirements used by tests, docs, and physical-device evidence.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from .hardware_wallet import (
    DEFAULT_DERIVATION_PATH,
    HardwareWalletError,
    build_hardware_sign_request,
    normalize_device_family,
    validate_hardware_transcript,
)

SESSION_SCHEMA = "netcoin-hardware-web-session-v1"
LEDGER_USB_VENDOR_ID = 0x2C97
TREZOR_USB_VENDOR_ID = 0x1209


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def browser_transport_policy(device_family: str) -> dict[str, Any]:
    family = normalize_device_family(device_family)
    if family == "ledger":
        return {
            "preferred_transport": "webhid",
            "fallback_transport": "webusb",
            "hid_filters": [{"vendorId": LEDGER_USB_VENDOR_ID}],
            "usb_filters": [{"vendorId": LEDGER_USB_VENDOR_ID}],
        }
    if family == "trezor":
        return {
            "preferred_transport": "webusb",
            "fallback_transport": "webhid",
            "hid_filters": [{"vendorId": TREZOR_USB_VENDOR_ID}],
            "usb_filters": [{"vendorId": TREZOR_USB_VENDOR_ID}],
        }
    raise HardwareWalletError(f"unsupported hardware-wallet device family: {device_family}")


@dataclass(frozen=True)
class HardwareWebSession:
    psbt: str
    device_family: str = "ledger"
    network: str = "testnet"
    derivation_path: str = DEFAULT_DERIVATION_PATH
    created_at: int = 0

    def to_dict(self) -> dict[str, Any]:
        request = build_hardware_sign_request(
            self.psbt,
            device_family=self.device_family,
            transport=browser_transport_policy(self.device_family)["preferred_transport"],
            network=self.network,
            derivation_path=self.derivation_path,
        )
        payload = {
            "schema": SESSION_SCHEMA,
            "request": request,
            "transport_policy": browser_transport_policy(self.device_family),
            "created_at": self.created_at or int(time.time()),
            "requires_physical_confirmation": True,
            "must_show_on_device": ["network", "outputs", "fee", "change", "derivation_path"],
            "transcript_required": [
                "device_model",
                "firmware_version",
                "transport",
                "address_reviewed_on_device",
                "tx_reviewed_on_device",
                "fee_reviewed_on_device",
                "change_reviewed_on_device",
                "signed_psbt",
                "operator_attestation",
            ],
            "private_key_material_included": False,
        }
        payload["session_hash"] = _hash(payload)
        return payload


def build_hardware_web_session(
    psbt_text: str,
    *,
    device_family: str = "ledger",
    network: str = "testnet",
    derivation_path: str = DEFAULT_DERIVATION_PATH,
) -> dict[str, Any]:
    return HardwareWebSession(
        psbt=psbt_text,
        device_family=device_family,
        network=network,
        derivation_path=derivation_path,
    ).to_dict()


def validate_physical_device_transcript(transcript: dict[str, Any]) -> list[str]:
    """Alias used by tools and tests for real physical evidence validation."""

    return validate_hardware_transcript(transcript)
