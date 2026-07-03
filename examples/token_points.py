"""Loyalty points on the NET-20 style app-layer token ledger.

Creates a POINTS token owned by the shop, mints a reward, transfers it to a
customer, and prints balances. App-layer only — the base chain never sees it.

Usage:
    NETCOIN_API=http://18.220.89.128 python examples/token_points.py net1q<shop> net1q<customer>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk" / "netcoin-python"))
from netcoin_sdk import NetcoinClient  # noqa: E402

API = os.environ.get("NETCOIN_API", "http://18.220.89.128")


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    shop, customer = sys.argv[1], sys.argv[2]
    nc = NetcoinClient(API)

    symbol = os.environ.get("TOKEN_SYMBOL", "POINTS")
    try:
        token = nc.create_token(symbol, shop, name="Store loyalty points", decimals=0, initial_supply="1000")
        print(f"Created {token['symbol']} ({token['token_id']})")
    except RuntimeError as exc:  # already exists on re-runs
        print(f"create_token: {exc}")

    nc.mint_token(symbol, shop, "50")
    nc.transfer_token(symbol, shop, customer, "25")
    for account in (shop, customer):
        bal = nc.token_balance(symbol, account)
        print(f"{account[:16]}…  {bal['amount']} {symbol}")


if __name__ == "__main__":
    main()
