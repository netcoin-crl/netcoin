"""BIP21-style payment URIs: ``netcoin:<address>?amount=&label=&message=``.

Mirrors Bitcoin's ``bitcoin:`` URI scheme so a wallet can encode a payment
request (address + optional amount/label/message) into a single shareable string,
and a sender can paste it to pre-fill a transaction.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode

from .crypto import validate_address

URI_SCHEME = "netcoin"


def build_uri(
    address: str,
    amount: str | None = None,
    label: str | None = None,
    message: str | None = None,
) -> str:
    if not validate_address(address):
        raise ValueError("invalid NetCoin address")
    params = []
    if amount is not None and str(amount) != "":
        try:
            value = Decimal(str(amount))
        except InvalidOperation as exc:
            raise ValueError("amount must be a number") from exc
        if value < 0:
            raise ValueError("amount cannot be negative")
        params.append(("amount", format(value.normalize(), "f")))
    if label:
        params.append(("label", label))
    if message:
        params.append(("message", message))
    query = urlencode(params, quote_via=quote)
    return f"{URI_SCHEME}:{address}" + (f"?{query}" if query else "")


def parse_uri(uri: str) -> dict[str, Any]:
    text = uri.strip()
    prefix = URI_SCHEME + ":"
    if not text.lower().startswith(prefix):
        raise ValueError(f"not a {URI_SCHEME}: URI")
    body = text[len(prefix) :]
    address, _, query = body.partition("?")
    address = address.strip()
    if not validate_address(address):
        raise ValueError("invalid NetCoin address in URI")
    result: dict[str, Any] = {"address": address}
    for key, value in parse_qsl(query, keep_blank_values=False):
        if key in ("amount", "label", "message"):
            result[key] = value
    if "amount" in result:
        try:
            if Decimal(result["amount"]) < 0:
                raise ValueError
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("invalid amount in URI") from exc
    return result
