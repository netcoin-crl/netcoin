"""Production PSBT/offline-signing workflow helpers for NetCoin.

These helpers implement the user-visible flow without requiring a live node:
create/export an unsigned NetCoin PSBT, import a signed PSBT, validate that it
matches the same unsigned transaction skeleton, and prepare a deterministic
broadcast package. Nothing here stores private keys or submits transactions by
itself; callers choose the transport and broadcast endpoint.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from .psbt import PartiallySignedTransaction

OFFLINE_WORKFLOW_SCHEMA = "netcoin-offline-signing-workflow-v1"
SIGNED_IMPORT_SCHEMA = "netcoin-signed-psbt-import-v1"
BROADCAST_PACKAGE_SCHEMA = "netcoin-broadcast-package-v1"
TRANSCRIPT_SCHEMA = "netcoin-offline-signing-transcript-v1"


class OfflineSigningError(ValueError):
    """Raised when an offline-signing workflow step is invalid."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _tx_summary(psbt: PartiallySignedTransaction) -> dict[str, Any]:
    return {
        "version": psbt.tx.version,
        "locktime": psbt.tx.locktime,
        "input_count": len(psbt.tx.inputs),
        "output_count": len(psbt.tx.outputs),
        "outputs": [
            {
                "index": index,
                "amount_sats": output.amount,
                "address": output.address,
                "script_pubkey": output.script_pubkey,
            }
            for index, output in enumerate(psbt.tx.outputs)
        ],
        "fully_signed": psbt.is_fully_signed(),
    }


def export_unsigned_psbt_bundle(
    psbt_text: str,
    *,
    network: str = "testnet",
    export_format: str = "file-text-qr",
    created_at: int | None = None,
) -> dict[str, Any]:
    """Return the exact package a wallet should show/export for offline signing."""

    if not psbt_text.startswith("netpsbt:"):
        raise OfflineSigningError("unsigned export requires a netpsbt: payload")
    psbt = PartiallySignedTransaction.from_base64(psbt_text)
    bundle = {
        "schema": OFFLINE_WORKFLOW_SCHEMA,
        "network": network,
        "export_format": export_format,
        "unsigned_psbt": psbt_text,
        "psbt_sha256": _sha256_text(psbt_text),
        "created_at": int(created_at if created_at is not None else time.time()),
        "summary": _tx_summary(psbt),
        "private_key_material_included": False,
        "instructions": [
            "Review outputs, change, and fee on the offline signer or hardware wallet.",
            "Sign the PSBT without exposing private keys to the online wallet.",
            "Import the signed PSBT back into NetCoin Wallet before broadcasting.",
        ],
    }
    bundle["bundle_hash"] = _sha256_text(_canonical(bundle))
    return bundle


def import_signed_psbt(unsigned_psbt_text: str, signed_psbt_text: str) -> dict[str, Any]:
    """Validate a signed PSBT and prepare it for finalization/broadcast."""

    unsigned = PartiallySignedTransaction.from_base64(unsigned_psbt_text)
    signed = PartiallySignedTransaction.from_base64(signed_psbt_text)
    if unsigned._skeleton() != signed._skeleton():
        raise OfflineSigningError("signed PSBT does not match the exported unsigned transaction")
    if not signed.is_fully_signed():
        raise OfflineSigningError("signed PSBT is not fully signed")
    tx = signed.extract()
    result = {
        "schema": SIGNED_IMPORT_SCHEMA,
        "unsigned_psbt_sha256": _sha256_text(unsigned_psbt_text),
        "signed_psbt_sha256": _sha256_text(signed_psbt_text),
        "txid": tx.txid(),
        "tx": tx.to_dict(include_scripts=True, include_witness=True),
        "ready_to_broadcast": True,
        "private_key_material_included": False,
    }
    result["import_hash"] = _sha256_text(_canonical(result))
    return result


def build_broadcast_package(
    signed_psbt_text: str,
    *,
    endpoint: str = "/api/tx/broadcast",
    network: str = "testnet",
) -> dict[str, Any]:
    """Create a deterministic broadcast handoff package without submitting it."""

    signed = PartiallySignedTransaction.from_base64(signed_psbt_text)
    if not signed.is_fully_signed():
        raise OfflineSigningError("cannot broadcast an unsigned PSBT")
    tx = signed.extract()
    package = {
        "schema": BROADCAST_PACKAGE_SCHEMA,
        "network": network,
        "method": "POST",
        "endpoint": endpoint,
        "txid": tx.txid(),
        "tx": tx.to_dict(include_scripts=True, include_witness=True),
        "signed_psbt_sha256": _sha256_text(signed_psbt_text),
        "submit_automatically": False,
    }
    package["broadcast_hash"] = _sha256_text(_canonical(package))
    return package


@dataclass(frozen=True)
class OfflineSigningTranscript:
    unsigned_bundle_hash: str
    signed_psbt_sha256: str
    txid: str
    signer_type: str
    operator_attestation: str
    created_at: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": TRANSCRIPT_SCHEMA,
            "unsigned_bundle_hash": self.unsigned_bundle_hash,
            "signed_psbt_sha256": self.signed_psbt_sha256,
            "txid": self.txid,
            "signer_type": self.signer_type,
            "operator_attestation": self.operator_attestation,
            "created_at": self.created_at or int(time.time()),
            "private_key_material_included": False,
        }
        payload["evidence_hash"] = _sha256_text(_canonical(payload))
        return payload


def validate_offline_signing_transcript(transcript: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required = (
        "schema",
        "unsigned_bundle_hash",
        "signed_psbt_sha256",
        "txid",
        "signer_type",
        "operator_attestation",
        "evidence_hash",
    )
    for field in required:
        if transcript.get(field) in (None, "", [], {}):
            issues.append(f"missing transcript field: {field}")
    if transcript.get("schema") != TRANSCRIPT_SCHEMA:
        issues.append(f"schema must be {TRANSCRIPT_SCHEMA}")
    if transcript.get("signer_type") not in {"software-offline", "ledger", "trezor", "qr-airgap"}:
        issues.append("signer_type must be software-offline, ledger, trezor, or qr-airgap")
    body = {key: value for key, value in transcript.items() if key != "evidence_hash"}
    expected = _sha256_text(_canonical(body))
    if transcript.get("evidence_hash") != expected:
        issues.append("evidence_hash mismatch; expected " + expected)
    return issues
