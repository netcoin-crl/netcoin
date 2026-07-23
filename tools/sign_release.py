#!/usr/bin/env python3
"""Sign a release checksum/provenance file with a NetCoin wallet key.

This is lightweight project-native signing for testnet releases. Operators can
also use GPG/Sigstore externally; this tool gives the repository a deterministic
verification workflow using NetCoin's signmessage format.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from netcoin.crypto import sign_message
from netcoin.wallet import Wallet


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign a NetCoin release artifact or checksum file")
    parser.add_argument("artifact")
    parser.add_argument("--wallet", required=True)
    parser.add_argument("--passphrase", default=None)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    artifact = Path(args.artifact)
    wallet = Wallet.load(args.wallet, passphrase=args.passphrase)
    digest = file_sha256(artifact)
    message = f"NetCoin release artifact\n{artifact.name}\nsha256:{digest}"
    signature = sign_message(wallet.private_key, message)
    payload = {
        "artifact": artifact.name,
        "sha256": digest,
        "address": wallet.address,
        "message": message,
        "signature": signature,
        "signature_type": "netcoin-signmessage-v1",
    }
    out = Path(args.out) if args.out else artifact.with_suffix(artifact.suffix + ".netsig")
    out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
