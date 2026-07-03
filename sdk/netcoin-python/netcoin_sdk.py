"""Minimal NetCoin app-layer SDK using only the Python standard library."""
from __future__ import annotations

import json
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class NetcoinClient:
    def __init__(self, base_url: str = ""):
        self.base_url = base_url.rstrip("/")

    def _request(self, path: str, method: str = "GET", payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        req = Request(self.base_url + path, data=body, headers=headers, method=method)
        with urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode("utf-8"))
        if data.get("error"):
            raise RuntimeError(data["error"])
        return data

    def get(self, path: str) -> dict:
        return self._request(path)

    def post(self, path: str, payload: dict) -> dict:
        return self._request(path, "POST", payload)

    def validate_address(self, address: str) -> dict:
        return self.get(f"/api/validate-address?{urlencode({'address': address})}")

    def create_invoice(self, address: str, amount: str, memo: str = "", label: str = "", order_id: str = "") -> dict:
        return self.post("/api/invoices", {"address": address, "amount": amount, "memo": memo, "label": label, "order_id": order_id})

    def get_invoice(self, invoice_id: str) -> dict:
        return self.get(f"/api/invoices/{quote(invoice_id)}")

    def receipt(self, txid: str) -> dict:
        return self.get(f"/api/receipt/{quote(txid)}")

    def resolve_username(self, username: str) -> dict:
        return self.get(f"/api/usernames/{quote(username)}")

    # ----- NET-20 style app-layer tokens -----

    def list_tokens(self) -> dict:
        return self.get("/api/tokens")

    def create_token(self, symbol: str, creator: str, *, name: str = "", decimals: int = 8, initial_supply: str = "0", max_supply: str = "0", mintable: bool = True) -> dict:
        return self.post("/api/tokens", {"symbol": symbol, "creator": creator, "name": name or symbol, "decimals": decimals, "initial_supply": initial_supply, "max_supply": max_supply, "mintable": mintable})

    def token_info(self, token: str) -> dict:
        return self.get(f"/api/tokens/{quote(token)}")

    def token_balance(self, token: str, account: str) -> dict:
        return self.get(f"/api/tokens/{quote(token)}/balance/{quote(account)}")

    def mint_token(self, token: str, minter: str, amount: str, to: str = "") -> dict:
        return self.post(f"/api/tokens/{quote(token)}/mint", {"minter": minter, "amount": amount, "to": to or minter})

    def transfer_token(self, token: str, sender: str, recipient: str, amount: str) -> dict:
        return self.post(f"/api/tokens/{quote(token)}/transfer", {"from": sender, "to": recipient, "amount": amount})

    def burn_token(self, token: str, account: str, amount: str) -> dict:
        return self.post(f"/api/tokens/{quote(token)}/burn", {"from": account, "amount": amount})


def payment_uri(address: str, amount: str = "", label: str = "", message: str = "") -> str:
    qs = {k: v for k, v in {"amount": amount, "label": label, "message": message}.items() if v}
    return f"netcoin:{address}" + ("?" + urlencode(qs) if qs else "")
