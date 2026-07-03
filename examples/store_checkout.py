"""Minimal store checkout: create an invoice, show the payment URI, poll status.

Usage:
    NETCOIN_API=http://18.220.89.128 python examples/store_checkout.py net1q<your-address> 1.25
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk" / "netcoin-python"))
from netcoin_sdk import NetcoinClient  # noqa: E402

API = os.environ.get("NETCOIN_API", "http://18.220.89.128")


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    address, amount = sys.argv[1], sys.argv[2]
    nc = NetcoinClient(API)

    invoice = nc.create_invoice(address, amount, memo="Example store order", order_id="order-001")
    print(f"Invoice {invoice['invoice_id']} for {invoice['amount']} NET")
    print(f"Pay with: {invoice['payment_uri']}")
    print(f"Hosted checkout: {API}{invoice['checkout_path']}")

    while True:
        status = nc.get_invoice(invoice["invoice_id"])["status"]
        print(f"status: {status}")
        if status in {"paid", "confirmed", "expired"}:
            break
        time.sleep(10)


if __name__ == "__main__":
    main()
