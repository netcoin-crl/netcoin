"""Small JSON-RPC server for NetCoin."""

from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from .chain import Blockchain
from .crypto import decode_address, validate_address
from .params import COINBASE_MATURITY, DEFAULT_RPC_PORT, MAX_REQUEST_BODY_BYTES, TICKER
from .block import Block
from .serialization import block_to_raw_hex, decode_raw_transaction, tx_to_raw_hex
from .tx import Transaction, sats_to_amount


class RPCError(ValueError):
    pass


class RPCServer:
    def __init__(self, chain: Blockchain):
        self.chain = chain

    def call(self, method: str, params: list[Any]) -> Any:
        if method == "getblockchaininfo":
            return self.chain.chain_info()
        if method == "getblockcount":
            return self.chain.height()
        if method == "getbestblockhash":
            return self.chain.tip_hash()
        if method == "getrawmempool":
            verbose = bool(params[0]) if params else False
            if not verbose:
                return [tx.txid() for tx in self.chain.mempool]
            fees = self.chain.fee_lookup()
            return {
                tx.txid(): {"vsize": tx.vsize(), "weight": tx.weight(), "fee": fees.get(tx.txid(), 0)}
                for tx in self.chain.mempool
            }
        if method == "getblock":
            block_hash = str(params[0]) if params else self.chain.tip_hash()
            verbosity = int(params[1]) if len(params) > 1 else 1
            block = self.chain.block_by_hash(block_hash)
            if block is None:
                raise RPCError("block not found")
            if verbosity == 0:
                return block_to_raw_hex(block)
            data = block.to_dict()
            data["hash"] = block.hash()
            data["weight"] = block.weight()
            return data
        if method == "getblockheader":
            block_hash = str(params[0]) if params else self.chain.tip_hash()
            block = self.chain.block_by_hash(block_hash)
            if block is None:
                raise RPCError("block not found")
            return block.header.to_dict() | {"hash": block.hash()}
        if method == "getrawtransaction":
            txid = str(params[0])
            verbose = bool(params[1]) if len(params) > 1 else False
            tx = self.find_tx(txid)
            if tx is None:
                raise RPCError("transaction not found")
            raw = tx_to_raw_hex(tx)
            if not verbose:
                return raw
            decoded = decode_raw_transaction(raw)
            decoded.update({"txid": tx.txid(), "wtxid": tx.wtxid(), "weight": tx.weight(), "vsize": tx.vsize()})
            return decoded
        if method == "sendrawtransaction":
            data = params[0]
            if isinstance(data, dict):
                tx = Transaction.from_dict(data)
            else:
                raise RPCError("sendrawtransaction currently accepts NetCoin transaction JSON")
            return self.chain.add_mempool_transaction(tx)
        if method == "estimatesmartfee":
            target = int(params[0]) if params else 1
            sat_vb = self.chain.estimate_fee_rate(target)
            return {"feerate_sat_vb": sat_vb, "feerate_net_kvb": sats_to_amount(sat_vb * 1000), "blocks": target}
        if method == "validateaddress":
            address = str(params[0]) if params else ""
            valid = validate_address(address)
            payload: dict[str, Any] = {"isvalid": valid, "address": address}
            if valid:
                decoded = decode_address(address)
                payload.update({
                    "network": "netcoin",
                    "type": decoded.get("type"),
                    "isscript": decoded.get("type") == "p2sh",
                    "iswitness": str(decoded.get("type", "")).startswith("p2w") or decoded.get("type") == "p2tr",
                })
            return payload
        if method == "getaddressbalance":
            address = str(params[0])
            return self.chain.address_balance_summary(address)
        if method == "getaddresssummary":
            address = str(params[0])
            limit = int(params[1]) if len(params) > 1 else 100
            offset = int(params[2]) if len(params) > 2 else 0
            summary = self.chain.address_summary(address)
            txids = list(summary.get("transaction_ids", []))
            limit = max(1, min(limit, 500))
            offset = max(0, offset)
            summary["transaction_ids_total"] = len(txids)
            summary["transaction_ids_offset"] = offset
            summary["transaction_ids_limit"] = limit
            summary["transaction_ids"] = txids[offset:offset + limit]
            summary["has_next"] = offset + limit < len(txids)
            return summary
        if method == "listaddressutxos":
            address = str(params[0])
            include_immature = bool(params[1]) if len(params) > 1 else False
            include_mempool_spent = bool(params[2]) if len(params) > 2 else False
            utxos = self.chain.utxos_for_address(address, include_immature=include_immature)
            mempool_spent = {txin.outpoint() for tx in self.chain.mempool for txin in tx.inputs}
            available = [utxo for utxo in utxos if include_mempool_spent or utxo.outpoint() not in mempool_spent]
            spend_height = self.chain.height() + 1
            return {
                "address": address,
                "height": self.chain.height(),
                "tip_hash": self.chain.tip_hash(),
                "utxos": [
                    utxo.to_dict() | {
                        "amount_sats": utxo.output.amount,
                        "amount": sats_to_amount(utxo.output.amount),
                        "confirmations": max(0, self.chain.height() - utxo.height + 1),
                        "spendable": not (utxo.coinbase and spend_height - utxo.height < COINBASE_MATURITY),
                    }
                    for utxo in available
                ],
                "excluded_mempool_spent": len(utxos) - len(available),
            }
        if method == "gettransactionstatus":
            txid = str(params[0])
            found = self.chain.get_transaction(txid)
            if found is None:
                raise RPCError("transaction not found")
            tx, block = found
            confirmed = block is not None
            confirmations = max(0, self.chain.height() - block.header.height + 1) if block else 0
            return {
                "txid": tx.txid(),
                "wtxid": tx.wtxid(),
                "confirmed": confirmed,
                "confirmations": confirmations,
                "block_hash": block.hash() if block else None,
                "block_height": block.header.height if block else None,
                "mempool": not confirmed,
                "rbf": tx.signals_rbf,
                "weight": tx.weight(),
                "vsize": tx.vsize(),
                "total_output_sats": tx.total_output(),
                "total_output": sats_to_amount(tx.total_output()),
                "outputs": tx.to_dict(include_scripts=True, include_witness=True)["outputs"],
            }
        if method == "getexchangeinfo":
            info = self.chain.chain_info()
            return {
                "chain": "netcoin",
                "network": info.get("network", "testnet"),
                "ticker": TICKER,
                "height": self.chain.height(),
                "tip_hash": self.chain.tip_hash(),
                "recommended_min_confirmations": 20,
                "coinbase_maturity": COINBASE_MATURITY,
                "deposit_address_types": ["p2wpkh", "p2pkh", "p2sh", "p2tr"],
                "preferred_deposit_address_type": "p2wpkh",
                "withdrawal_broadcast_method": "sendrawtransaction",
                "rpc_auth_recommended": True,
                "notes": [
                    "Keep RPC bound to localhost or behind a private network plus bearer token.",
                    "Treat NetCoin as public testnet/experimental until independent security review.",
                    "Re-scan recent deposits after any tip hash change at the same or lower height.",
                ],
            }
        if method == "getblocktemplate":
            address = str(params[0]) if params else None
            return self.chain.get_block_template(miner_address=address)
        if method == "submitblock":
            if not params:
                raise RPCError("submitblock requires a block JSON object")
            block = Block.from_dict(params[0])
            return self.chain.add_block(block)
        if method == "validatechain":
            self.chain.assert_valid_chain(self.chain.chain)
            return True
        raise RPCError(f"unknown RPC method: {method}")

    def find_tx(self, txid: str) -> Optional[Transaction]:
        for tx in self.chain.mempool:
            if tx.txid() == txid:
                return tx
        for block in self.chain.chain:
            for tx in block.transactions:
                if tx.txid() == txid:
                    return tx
        return None


def make_handler(rpc: RPCServer, token: Optional[str] = None):
    class Handler(BaseHTTPRequestHandler):
        server_version = "NetCoinRPC/0.2"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def authorized(self) -> bool:
            # When no token is configured the RPC is open (intended only for a
            # localhost bind). When a token is set, require a matching bearer
            # token or X-Auth-Token header, compared in constant time.
            if not token:
                return True
            header = self.headers.get("Authorization", "")
            presented = header[7:] if header.startswith("Bearer ") else self.headers.get("X-Auth-Token", "")
            return bool(presented) and hmac.compare_digest(presented, token)

        def do_POST(self) -> None:  # noqa: N802
            if not self.authorized():
                self.send_json(
                    {"jsonrpc": "2.0", "id": None, "result": None, "error": "unauthorized"},
                    status=401,
                )
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > MAX_REQUEST_BODY_BYTES:
                    raise RPCError("request body too large")
                request = json.loads(self.rfile.read(length).decode("utf-8"))
                result = rpc.call(str(request.get("method")), list(request.get("params", [])))
                payload = {"jsonrpc": "2.0", "id": request.get("id"), "result": result, "error": None}
                self.send_json(payload)
            except Exception as exc:
                self.send_json({"jsonrpc": "2.0", "id": None, "result": None, "error": str(exc)}, status=400)

        def do_GET(self) -> None:  # noqa: N802
            # The discovery page never requires auth and never leaks the token.
            self.send_json({"ok": True, "service": "NetCoin JSON-RPC", "methods": RPC_METHODS, "auth_required": bool(token)})

        def send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


RPC_METHODS = [
    "getblockchaininfo",
    "getblockcount",
    "getbestblockhash",
    "getrawmempool",
    "getblock",
    "getblockheader",
    "getrawtransaction",
    "sendrawtransaction",
    "estimatesmartfee",
    "validateaddress",
    "getaddressbalance",
    "getaddresssummary",
    "listaddressutxos",
    "gettransactionstatus",
    "getexchangeinfo",
    "getblocktemplate",
    "submitblock",
    "validatechain",
]


def run_rpc(
    data_dir: str,
    host: str = "127.0.0.1",
    port: int = DEFAULT_RPC_PORT,
    token: Optional[str] = None,
) -> None:
    chain = Blockchain(data_dir=data_dir)
    rpc = RPCServer(chain)
    # Prefer an explicit token, fall back to the NETCOIN_RPC_TOKEN env var.
    token = token or os.environ.get("NETCOIN_RPC_TOKEN") or None
    server = ThreadingHTTPServer((host, port), make_handler(rpc, token=token))
    print(f"NetCoin RPC listening on http://{host}:{port}")
    if token:
        print("RPC authentication: enabled (send 'Authorization: Bearer <token>')")
    else:
        print("RPC authentication: DISABLED — keep this bound to 127.0.0.1 only")
    if host not in ("127.0.0.1", "localhost", "::1") and not token:
        print("WARNING: RPC is bound to a non-local address without a token. Set NETCOIN_RPC_TOKEN.")
    try:
        server.serve_forever()
    finally:
        server.server_close()
