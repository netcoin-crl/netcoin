"""Minimal local web UI: wallet + faucet + explorer over a remote NetCoin node.

Run with ``python -m netcoin web``. It serves a single page on 127.0.0.1 that
wraps the same operations as the CLI — create/load a wallet, check balance, send,
open the faucet, and browse the chain — so a newcomer can use NetCoin from a
browser instead of the command line.

Security model: this is a LOCAL tool. Private keys live only in this process and
the wallet file on your machine; signing happens locally and only the signed
transaction is sent to the node. Bind it to 127.0.0.1 (the default) and never
expose it publicly — it is not a custodial/hosted wallet.
"""

from __future__ import annotations

import atexit
import json
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from .params import (
    COIN,
    COINBASE_MATURITY,
    DEFAULT_NODE_PORT,
    MAX_WALLET_SEND_INPUTS,
    MAX_WALLET_SEND_WEIGHT,
    NETWORK_NAME,
    NODE_VERSION,
    TICKER,
)
from .offline_signing import (
    build_broadcast_package,
    export_unsigned_psbt_bundle,
    import_signed_psbt,
)
from .fee_bump import DEFAULT_RBF_SEQUENCE, create_rbf_replacement, transaction_fee
from .psbt import PartiallySignedTransaction
from .script import script_to_p2sh_address
from .serialization import transaction_weight
from .tx import SpendableOutput, Transaction, TxInput, TxOutput, amount_to_sats
from .wallet import Wallet

# SegWit first and default; legacy/p2sh-segwit kept only so existing coins stay spendable.
ADDRESS_TYPES = ["segwit", "taproot", "legacy", "p2sh-segwit"]
LOCAL_NODE_HOSTS = {"127.0.0.1", "localhost", "::1"}


class LocalNodeController:
    """Process supervisor for a node launched by the desktop web wallet.

    Two instances are used: a loopback-only "convenience node" (bind_host
    127.0.0.1, the original "Node" tab) and an optional public "seed" node
    (bind_host 0.0.0.0, reachable from the internet if the operator forwards
    the port). Both are only ever controllable through this wallet's own
    API when the wallet itself is bound to loopback — see allow_node_control
    in run_web_wallet. Binding the *node* publicly is fine and intended
    (that is the point of a seed); letting anyone reach the *control* API
    would not be.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        port: int = DEFAULT_NODE_PORT,
        data_dir: Path | None = None,
        bind_host: str = "127.0.0.1",
        advertise: str = "",
        bandwidth_mode: str = "",
        p2p_port: int | None = None,
    ) -> None:
        self.enabled = enabled
        self.port = int(port)
        self.data_dir = data_dir or (Path.home() / ".netcoin-local-node")
        self.log_path = self.data_dir / "node.log"
        self.process: subprocess.Popen[str] | None = None
        self.bind_host = bind_host
        self.advertise = advertise
        self.bandwidth_mode = bandwidth_mode
        self.p2p_port = p2p_port
        # The web wallet serves requests on a thread pool (ThreadingHTTPServer);
        # without this, two overlapping start() calls (an impatient double
        # click, a retried request) can both see "not running yet" and each
        # spawn a subprocess. The second one fails at the OS level with
        # "Address already in use" and overwrites self.process, so the request
        # that actually launched the working node gets reported as a failure.
        self._lock = threading.Lock()

    @property
    def url(self) -> str:
        # Always check via loopback even for a 0.0.0.0-bound seed — a node
        # bound to 0.0.0.0 still answers on 127.0.0.1, and checking that way
        # means status works the same regardless of any firewall/NAT state
        # between this machine and the outside world.
        return f"http://127.0.0.1:{self.port}"

    def _external_info(self) -> dict[str, Any] | None:
        try:
            return _node_get(self.url, "/info", timeout=2).get("node", {})
        except Exception:
            return None

    def status(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "running": False, "reason": "local node control is available only on loopback"}
        if self.process and self.process.poll() is not None:
            self.process = None
        info = self._external_info()
        running = bool(info)
        owned = bool(self.process and self.process.poll() is None)
        return {
            "enabled": True,
            "running": running,
            "owned": owned,
            "external": running and not owned,
            "url": self.url,
            "bind_host": self.bind_host,
            "port": self.port,
            "public": self.bind_host not in LOCAL_NODE_HOSTS,
            "advertise": self.advertise,
            "pid": self.process.pid if owned else None,
            "height": info.get("height") if info else None,
            "peers": info.get("peers") if info else None,
            "version": info.get("version") if info else None,
            "advertise_unreachable": bool(info.get("advertise_unreachable")) if info else False,
            "advertise_unreachable_error": info.get("advertise_unreachable_error", "") if info else "",
            "log": str(self.log_path),
        }

    def start(self) -> dict[str, Any]:
        if not self.enabled:
            raise ValueError("local node control is available only when the web wallet is bound to 127.0.0.1")
        with self._lock:
            status = self.status()
            if status["running"]:
                return status | {"message": "node already running on this port"}
            self.data_dir.mkdir(parents=True, exist_ok=True)
            log = self.log_path.open("a", encoding="utf-8")
            cmd = [
                sys.executable,
                "-m",
                "netcoin",
                "--data",
                str(self.data_dir),
                "node",
                "--host",
                self.bind_host,
                "--port",
                str(self.port),
                "--seeds",
            ]
            if self.advertise:
                cmd += ["--advertise", self.advertise]
            if self.bandwidth_mode:
                cmd += ["--bandwidth-mode", self.bandwidth_mode]
            if self.p2p_port is not None:
                cmd += ["--p2p-port", str(self.p2p_port)]
            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    close_fds=True,
                )
            finally:
                # Popen dup()s this fd into the child; our own handle on it
                # must be closed here or it leaks one descriptor per start().
                log.close()
            deadline = time.time() + 8
            while time.time() < deadline:
                info = self._external_info()
                if info:
                    break
                if self.process.poll() is not None:
                    raise ValueError(f"node exited early; check {self.log_path}")
                time.sleep(0.25)
            return self.status() | {"message": "node started"}

    def stop(self) -> dict[str, Any]:
        if not self.enabled:
            raise ValueError("local node control is available only when the web wallet is bound to 127.0.0.1")
        with self._lock:
            if not self.process or self.process.poll() is not None:
                self.process = None
                return self.status() | {"message": "no web-wallet-started node to stop"}
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
            self.process = None
            return self.status() | {"message": "node stopped"}


# --------------------------------------------------------------------------- #
# Remote node helpers
# --------------------------------------------------------------------------- #


def _normalize_node_url(node_url: str) -> str:
    """Return a node/API base URL that works with the local web wallet.

    Public users often paste ``https://api.netcoin.online`` while the hosted
    reverse proxy exposes the node under ``/api``. Accept both forms so the
    local wallet does not appear broken because of a missing path segment.
    """
    base = (node_url or "").strip().rstrip("/")
    if base in {"https://api.netcoin.online", "http://api.netcoin.online"}:
        return base + "/api"
    return base


def _node_get(node_url: str, path: str, timeout: int = 15) -> dict[str, Any]:
    base = _normalize_node_url(node_url)
    with urlopen(base + path, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _node_post(node_url: str, path: str, payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    base = _normalize_node_url(node_url)
    body = json.dumps(payload).encode("utf-8")
    request = Request(base + path, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wallet_addresses(wallet: Wallet) -> dict[str, str]:
    return {kind: wallet.address_for(kind) for kind in ADDRESS_TYPES}


# Rough per-input weight estimates (weight units) for coin selection without
# signing every trial. Conservative; the real weight is re-checked after signing.
_INPUT_WEIGHT_ESTIMATE = {
    "segwit": 275,
    "taproot": 240,
    "legacy": 600,
    "p2sh-segwit": 370,
    "p2wpkh": 275,
    "p2tr": 240,
    "p2pkh": 600,
}
_OUTPUT_WEIGHT_ESTIMATE = 140


def _max_sendable_sats(by_value_desc, fee_sats: int) -> int:
    """Largest amount sendable in one transaction right now: the sum of the
    largest MAX_WALLET_SEND_INPUTS coins minus the fee (>=0)."""
    top = by_value_desc[:MAX_WALLET_SEND_INPUTS]
    return max(0, sum(s.output.amount for s in top) - fee_sats)


def consolidation_status(
    wallet: Wallet,
    from_type: str,
    node_url: str,
    fee_sats: int = 10_000,
    max_inputs: int = MAX_WALLET_SEND_INPUTS,
) -> dict[str, Any]:
    """Return the wallet's current one-transaction send capacity.

    This is intentionally read-only: it lets CLIs and UIs warn users before a
    fragmented mining wallet hits the input cap.
    """
    from_address = wallet.address_for(from_type)
    info = _node_get(node_url, "/info").get("node", {})
    tip_height = int(info.get("height", 0))
    data = _node_get(node_url, f"/utxos?address={from_address}")
    spendables = [SpendableOutput.from_dict(item) for item in data.get("utxos", [])]
    spendables = [s for s in spendables if not s.coinbase or (tip_height - s.height) >= COINBASE_MATURITY]
    spendables_by_value = sorted(spendables, key=lambda s: s.output.amount, reverse=True)
    max_inputs = max(1, min(max_inputs, MAX_WALLET_SEND_INPUTS))
    total_sats = sum(s.output.amount for s in spendables)
    max_sendable_sats = max(0, sum(s.output.amount for s in spendables_by_value[:max_inputs]) - fee_sats)
    full_after_fee = max(0, total_sats - fee_sats)
    stranded_sats = max(0, full_after_fee - max_sendable_sats)
    return {
        "address": from_address,
        "spendable_utxos": len(spendables),
        "spendable_sats": total_sats,
        "spendable": total_sats / COIN,
        "max_inputs": max_inputs,
        "max_sendable_sats": max_sendable_sats,
        "max_sendable": max_sendable_sats / COIN,
        "stranded_until_consolidated_sats": stranded_sats,
        "stranded_until_consolidated": stranded_sats / COIN,
        "needs_consolidation": len(spendables) > max_inputs or stranded_sats > 0,
    }


def build_and_broadcast(
    wallet: Wallet,
    to_address: str,
    amount_sats: int,
    fee_sats: int,
    from_type: str,
    node_url: str,
    *,
    rbf: bool = False,
) -> dict[str, Any]:
    """Build, sign locally, and broadcast a transaction using a remote node's UTXOs."""
    if amount_sats <= 0:
        raise ValueError("amount must be positive")
    if fee_sats < 0:
        raise ValueError("fee cannot be negative")
    from_address = wallet.address_for(from_type)

    info = _node_get(node_url, "/info").get("node", {})
    tip_height = int(info.get("height", 0))
    data = _node_get(node_url, f"/utxos?address={from_address}")
    spendables = [SpendableOutput.from_dict(item) for item in data.get("utxos", [])]
    # Drop immature coinbase outputs the node would reject anyway.
    spendables = [s for s in spendables if not s.coinbase or (tip_height - s.height) >= COINBASE_MATURITY]
    if not spendables:
        raise ValueError("no spendable (mature) coins at this address yet")

    needed = amount_sats + fee_sats
    total_spendable = sum(s.output.amount for s in spendables)
    if total_spendable < needed:
        raise ValueError(
            f"insufficient spendable balance: have {total_spendable / COIN:.8f} {TICKER}, "
            f"need {(needed) / COIN:.8f} {TICKER}. Mining rewards must mature before spending."
        )

    # Consolidating coin selection (Option A): cover the target largest-first,
    # then top up with the smallest coins so every send also shrinks the UTXO
    # set — defragmenting passively instead of letting the coin count grow.
    by_value_desc = sorted(spendables, key=lambda s: s.output.amount, reverse=True)
    core: list[SpendableOutput] = []
    total = 0
    for utxo in by_value_desc:
        core.append(utxo)
        total += utxo.output.amount
        if total >= needed:
            break
    if total < needed:
        raise ValueError(f"insufficient balance: have {total / COIN:.8f}, need {needed / COIN:.8f} {TICKER}")
    if len(core) > MAX_WALLET_SEND_INPUTS:
        affordable = _max_sendable_sats(by_value_desc, fee_sats)
        raise ValueError(
            f"this send needs more than {MAX_WALLET_SEND_INPUTS} coins as inputs. "
            f"You can send up to {affordable / COIN:.8f} {TICKER} right now; "
            f"run `netcoin consolidate` (or send Max to yourself) to combine coins and send more."
        )
    extras = [
        u for u in sorted(spendables, key=lambda s: s.output.amount) if u.outpoint() not in {c.outpoint() for c in core}
    ]

    # Choose how many dust coins to add using a WEIGHT ESTIMATE (per-input
    # weight is ~constant for a single-key wallet), signing only once at the end.
    # Signing per trial would be O(N^2) — the very cost this release fixes.
    per_input_weight = _INPUT_WEIGHT_ESTIMATE.get(from_type, 600)
    overhead = 400 + 2 * _OUTPUT_WEIGHT_ESTIMATE  # version/locktime/counts + up to 2 outputs
    max_by_weight = max(len(core), (MAX_WALLET_SEND_WEIGHT - overhead) // per_input_weight)
    cap = min(MAX_WALLET_SEND_INPUTS, max_by_weight)
    selected = list(core)
    for extra in extras:
        if len(selected) >= cap:
            break
        selected.append(extra)

    sel_total = sum(s.output.amount for s in selected)
    outputs = [TxOutput(amount=amount_sats, address=to_address)]
    change = sel_total - needed
    if change > 0:
        outputs.append(TxOutput(amount=change, address=from_address))
    sequence = DEFAULT_RBF_SEQUENCE if rbf else 0xFFFFFFFF
    tx = Transaction(
        inputs=[TxInput(txid=s.txid, vout=s.vout, sequence=sequence) for s in selected], outputs=outputs, locktime=0
    )
    for index, utxo in enumerate(selected):
        tx.sign_input(index, wallet.private_key, utxo)

    weight = transaction_weight(tx)
    if weight > MAX_WALLET_SEND_WEIGHT:
        # Estimate was optimistic: drop dust back to the minimal covering set.
        selected = list(core)
        sel_total = sum(s.output.amount for s in selected)
        outputs = [TxOutput(amount=amount_sats, address=to_address)]
        change = sel_total - needed
        if change > 0:
            outputs.append(TxOutput(amount=change, address=from_address))
        tx = Transaction(
            inputs=[TxInput(txid=s.txid, vout=s.vout, sequence=sequence) for s in selected], outputs=outputs, locktime=0
        )
        for index, utxo in enumerate(selected):
            tx.sign_input(index, wallet.private_key, utxo)
        weight = transaction_weight(tx)
        if weight > MAX_WALLET_SEND_WEIGHT:
            affordable = _max_sendable_sats(by_value_desc, fee_sats)
            raise ValueError(
                f"this send is too large to fit one transaction. You can send up to "
                f"{affordable / COIN:.8f} {TICKER} right now; run `netcoin consolidate` to send more."
            )

    response = _node_post(node_url, "/tx", tx.to_dict(), timeout=30)
    return {
        "txid": response.get("txid") or tx.txid(),
        "amount": amount_sats / COIN,
        "fee": fee_sats / COIN,
        "input_count": len(selected),
        "weight": weight,
        "change": change / COIN,
        "signals_rbf": tx.signals_rbf,
        "tx": tx.to_dict(),
        "prevouts": [item.to_dict() for item in selected],
        "node_response": response,
    }


def build_unsigned_multisig_psbt(
    redeem_script: str,
    to_address: str,
    amount_sats: int,
    fee_sats: int,
    node_url: str,
) -> PartiallySignedTransaction:
    if amount_sats <= 0:
        raise ValueError("amount must be positive")
    if fee_sats < 0:
        raise ValueError("fee cannot be negative")
    from_address = script_to_p2sh_address(redeem_script)
    data = _node_get(node_url, f"/utxos?address={from_address}")
    spendables = [SpendableOutput.from_dict(item) for item in data.get("utxos", [])]
    if not spendables:
        raise ValueError("no spendable coins at this multisig address yet")
    needed = amount_sats + fee_sats
    selected: list[SpendableOutput] = []
    total = 0
    for utxo in sorted(spendables, key=lambda s: s.output.amount, reverse=True):
        selected.append(utxo)
        total += utxo.output.amount
        if total >= needed:
            break
    if total < needed:
        raise ValueError(f"insufficient multisig balance: have {total / COIN:.8f}, need {needed / COIN:.8f} {TICKER}")
    outputs = [TxOutput(amount=amount_sats, address=to_address)]
    change = total - needed
    if change > 0:
        outputs.append(TxOutput(amount=change, address=from_address))
    psbt = PartiallySignedTransaction.create(selected, outputs)
    for index in range(len(selected)):
        psbt.set_multisig_input(index, redeem_script)
    return psbt


def multisig_psbt_progress(psbt: PartiallySignedTransaction) -> dict[str, Any]:
    inputs = []
    ready = True
    total_required = 0
    total_collected = 0
    for index in range(len(psbt.tx.inputs)):
        redeem_script = psbt.redeem_scripts.get(index)
        if not redeem_script:
            inputs.append({"index": index, "multisig": False, "ready": bool(psbt.tx.inputs[index].script_sig)})
            continue
        required = PartiallySignedTransaction._multisig_required(redeem_script)
        pubkeys = set(PartiallySignedTransaction._multisig_pubkeys(redeem_script))
        collected = sorted(pk for pk in psbt.partial_sigs.get(index, {}) if pk in pubkeys)
        input_ready = len(collected) >= required
        ready = ready and input_ready
        total_required += required
        total_collected += min(len(collected), required)
        inputs.append(
            {
                "index": index,
                "multisig": True,
                "required": required,
                "collected": len(collected),
                "ready": input_ready,
                "signers": collected,
            }
        )
    return {"ready": ready, "required": total_required, "collected": total_collected, "inputs": inputs}


def build_unsigned_psbt_for_send(
    wallet: Wallet,
    to_address: str,
    amount_sats: int,
    fee_sats: int,
    from_type: str,
    node_url: str,
) -> PartiallySignedTransaction:
    """Select coins and build an UNSIGNED PSBT for offline/hardware signing.

    Mirrors build_and_broadcast's covering coin selection but stops at the
    unsigned PSBT: no key ever touches this path, so the returned bundle is
    safe to hand to an offline signer or hardware wallet.
    """
    if amount_sats <= 0:
        raise ValueError("amount must be positive")
    if fee_sats < 0:
        raise ValueError("fee cannot be negative")
    from_address = wallet.address_for(from_type)

    info = _node_get(node_url, "/info").get("node", {})
    tip_height = int(info.get("height", 0))
    data = _node_get(node_url, f"/utxos?address={from_address}")
    spendables = [SpendableOutput.from_dict(item) for item in data.get("utxos", [])]
    spendables = [s for s in spendables if not s.coinbase or (tip_height - s.height) >= COINBASE_MATURITY]
    if not spendables:
        raise ValueError("no spendable (mature) coins at this address yet")

    needed = amount_sats + fee_sats
    by_value_desc = sorted(spendables, key=lambda s: s.output.amount, reverse=True)
    selected: list[SpendableOutput] = []
    total = 0
    for utxo in by_value_desc:
        selected.append(utxo)
        total += utxo.output.amount
        if total >= needed:
            break
    if total < needed:
        raise ValueError(f"insufficient spendable balance: have {total / COIN:.8f}, need {needed / COIN:.8f} {TICKER}")
    if len(selected) > MAX_WALLET_SEND_INPUTS:
        raise ValueError(
            f"this send needs more than {MAX_WALLET_SEND_INPUTS} coins as inputs; "
            f"run `netcoin consolidate` to combine coins first."
        )

    outputs = [TxOutput(amount=amount_sats, address=to_address)]
    change = total - needed
    if change > 0:
        outputs.append(TxOutput(amount=change, address=from_address))
    return PartiallySignedTransaction.create(selected, outputs)


def consolidate_coins(
    wallet: Wallet,
    from_type: str,
    node_url: str,
    fee_sats: int = 10_000,
    max_inputs: int = MAX_WALLET_SEND_INPUTS,
) -> dict[str, Any]:
    """Sweep many small UTXOs into one output back to the same address.

    Mining pays 50 NET per block, so a large balance is often hundreds of small
    coins; a big send then needs more inputs than the wallet/node policy allows
    (MAX_WALLET_SEND_INPUTS / MAX_WALLET_SEND_WEIGHT). Consolidation spends up
    to `max_inputs` coins per transaction back to yourself, in as many batches
    as needed. Batch outputs are unconfirmed until mined, so run it again after
    a confirmation if you want to converge further.
    """
    from_address = wallet.address_for(from_type)
    info = _node_get(node_url, "/info").get("node", {})
    tip_height = int(info.get("height", 0))
    data = _node_get(node_url, f"/utxos?address={from_address}")
    spendables = [SpendableOutput.from_dict(item) for item in data.get("utxos", [])]
    spendables = [s for s in spendables if not s.coinbase or (tip_height - s.height) >= COINBASE_MATURITY]
    spendables.sort(key=lambda s: s.output.amount)  # sweep the dust first
    if len(spendables) < 2:
        return {
            "batches": [],
            "note": "nothing to consolidate: fewer than two spendable coins",
            "utxos": len(spendables),
        }

    max_inputs = max(2, min(max_inputs, MAX_WALLET_SEND_INPUTS))
    batches: list[dict[str, Any]] = []
    position = 0
    while position + 1 < len(spendables):
        size = min(max_inputs, len(spendables) - position)
        while size >= 2:
            batch = spendables[position : position + size]
            total = sum(s.output.amount for s in batch)
            if total <= fee_sats:
                return {
                    "batches": batches,
                    "note": "remaining coins are smaller than the fee; stopping",
                    "utxos_left": len(spendables) - position,
                }
            tx = Transaction(
                inputs=[TxInput(txid=s.txid, vout=s.vout) for s in batch],
                outputs=[TxOutput(amount=total - fee_sats, address=from_address)],
                locktime=0,
            )
            for index, utxo in enumerate(batch):
                tx.sign_input(index, wallet.private_key, utxo)
            if transaction_weight(tx) <= MAX_WALLET_SEND_WEIGHT:
                response = _node_post(node_url, "/tx", tx.to_dict(), timeout=30)
                batches.append(
                    {
                        "txid": response.get("txid") or tx.txid(),
                        "inputs": len(batch),
                        "consolidated": (total - fee_sats) / COIN,
                        "fee": fee_sats / COIN,
                    }
                )
                position += size
                break
            size //= 2  # too heavy: halve the batch and retry
        else:
            break
    return {
        "address": from_address,
        "batches": batches,
        "transactions": len(batches),
        "utxos_left_unbatched": max(0, len(spendables) - position),
    }


# --------------------------------------------------------------------------- #
# Single-page UI
# --------------------------------------------------------------------------- #

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>NetCoin Wallet</title>
<style>
 :root{--bg:#0e1116;--card:#171c24;--bd:#272e3a;--fg:#e6edf3;--mut:#8b97a7;--acc:#f7931a;--ok:#2ea043;--err:#f85149}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
 header{padding:18px 20px;border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:12px}
 header h1{font-size:18px;margin:0} .tag{color:var(--mut);font-size:13px}
 .wrap{max-width:960px;margin:0 auto;padding:20px}
 .tabs{display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap}
 .tabs button{background:var(--card);color:var(--fg);border:1px solid var(--bd);padding:8px 14px;border-radius:8px;cursor:pointer}
 .tabs button.on{border-color:var(--acc);color:var(--acc)}
 .card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:18px;margin-bottom:16px}
 h2{font-size:15px;margin:0 0 12px} label{display:block;color:var(--mut);font-size:13px;margin:10px 0 4px}
 input,select{width:100%;background:#0e131a;color:var(--fg);border:1px solid var(--bd);border-radius:8px;padding:9px}
 button.act{background:var(--acc);color:#1a1205;border:0;padding:10px 16px;border-radius:8px;font-weight:600;cursor:pointer;margin-top:12px}
 button.ghost{background:transparent;color:var(--fg);border:1px solid var(--bd);padding:8px 12px;border-radius:8px;cursor:pointer}
 .mono{font-family:ui-monospace,Menlo,monospace;word-break:break-all;font-size:13px}
 .row{display:flex;gap:10px;flex-wrap:wrap} .row>*{flex:1;min-width:140px}
 .muted{color:var(--mut)} .big{font-size:26px;font-weight:700} .ok{color:var(--ok)} .err{color:var(--err)}
 .warn{background:#3a2a08;border:1px solid #6b4d12;color:#f0c674;padding:10px;border-radius:8px;font-size:13px;margin-top:10px}
 table{width:100%;border-collapse:collapse;font-size:13px} td,th{text-align:left;padding:6px 4px;border-bottom:1px solid var(--bd)}
 .hide{display:none} a{color:var(--acc)}
 @media (min-width:900px){body{font-size:16px}.wrap{max-width:min(1280px,calc(100vw - 56px));padding:28px}.tabs{gap:10px}.tabs button{padding:10px 16px}.card{border-radius:16px;padding:22px}.row>*{min-width:220px}#tab-wallet{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;align-items:start}#tab-wallet.hide{display:none}#tab-wallet>.card{margin-bottom:0}#noWallet,#haveWallet{grid-column:1/-1}.big{font-size:34px}}
 @media (min-width:1180px){.wrap{max-width:min(1380px,calc(100vw - 72px));padding:36px}#tab-wallet{grid-template-columns:repeat(3,minmax(0,1fr))}#noWallet,#haveWallet{grid-column:span 2}}
 /* Responsive local-wallet desktop layout */
 .rcard{background:#0e131a;border:1px solid var(--bd);border-radius:10px;padding:14px}
 .rtitle{color:var(--acc);font-weight:700;margin-bottom:8px;font-size:15px}
 .sub{margin-bottom:10px;color:var(--mut)}
 .kv{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid var(--bd)}
 .kv:last-child{border-bottom:0}
 .lnk{cursor:pointer;color:var(--acc);padding:3px 0}.lnk:hover{text-decoration:underline}
 #latest th{color:var(--mut);font-weight:600}
</style></head><body>
<header><span class="big" style="color:var(--acc)">◈</span><h1>NetCoin Wallet</h1><span class="tag" id="netinfo">testnet</span></header>
<div class="wrap">
 <div class="tabs">
  <button class="on" data-tab="wallet">Wallet</button>
  <button data-tab="faucet">Faucet</button>
  <button data-tab="explorer">Explorer</button>
  <button data-tab="node">Node</button>
  <button data-tab="seed">Seed</button>
 </div>

 <section id="tab-wallet">
  <div class="card" id="noWallet">
   <h2>Get a wallet</h2>
   <p class="muted">Create a fresh testnet wallet, or load one you already have. Testnet NET has no real value.</p>
   <div class="row">
     <button class="act" onclick="newWallet()">Create new wallet</button>
     <button class="ghost" onclick="document.getElementById('loadBox').classList.toggle('hide')">Load existing</button>
     <button class="ghost" onclick="document.getElementById('pkBox').classList.toggle('hide')">Private key</button>
   </div>
   <div id="loadBox" class="hide">
     <label>Paste wallet JSON</label><input id="loadJson" placeholder='{"network":"NetCoin",...}'>
     <label>Passphrase (if encrypted)</label><input id="loadPass" type="password">
     <button class="act" onclick="loadWallet()">Load</button>
   </div>
   <div id="pkBox" class="hide">
     <label>Private key hex</label><input id="privHex" placeholder="64-character private key hex" autocomplete="off">
     <p class="muted">Use this only for single-key testnet wallets. Do not paste private keys into untrusted pages.</p>
     <button class="act" onclick="loadPrivateKey()">Log in with private key</button>
   </div>
  </div>

  <div class="card hide" id="haveWallet">
   <h2>Balance</h2>
   <div class="big" id="balSpendable">—</div>
   <div class="muted" id="balDetail"></div>
   <label>Address (<span id="addrType">segwit</span>)</label>
   <div class="mono" id="addr"></div>
   <div class="row" style="margin-top:8px">
     <button class="ghost" onclick="copyAddr()">Copy address</button>
     <button class="ghost" onclick="refreshBalance()">Refresh</button>
     <select id="typeSel" onchange="switchType()"></select>
   </div>
   <div id="mnemonicBox"></div>
  </div>

  <div class="card hide" id="sendCard">
   <h2>Send</h2>
   <label>Paste a payment link (optional)</label><input id="payLink" placeholder="netcoin:Nc...?amount=..." oninput="applyPayLink()">
   <label>To address</label><input id="sendTo" placeholder="Nc... / net1...">
   <div class="row">
    <div><label>Amount (NET)</label><input id="sendAmt" type="number" step="0.00000001" placeholder="1.0"></div>
    <div><label>Fee (NET)</label><input id="sendFee" type="number" step="0.00000001" value="0.01"></div>
   </div>
	   <label>Fee selector</label><select id="feePreset" onchange="applyFeePreset()"><option value="normal">Normal</option><option value="fast">Fast</option><option value="economy">Economy</option><option value="custom">Custom</option></select>
	   <label><input id="rbfSend" type="checkbox" checked> Make this send fee-bumpable with opt-in RBF</label>
   <button class="act" onclick="send()">Send</button>
	   <button class="ghost" onclick="bumpLastFee()">Bump fee on pending send</button>
   <div id="sendOut" style="margin-top:10px"></div>
  </div>

	  <div class="card hide" id="multisigCard">
	   <h2>Multisig wallet</h2>
	   <p class="muted">Create an M-of-N P2SH multisig address, then build/export PSBTs for cosigners until enough signatures are collected.</p>
	   <div class="row"><div><label>Required signatures</label><input id="msRequired" type="number" value="2" min="1"></div><div><label>Cosigner public keys</label><input id="msPubkeys" placeholder="02abc..., 03def..."></div></div>
	   <button class="ghost" onclick="createMultisigWallet()">Create multisig wallet</button>
	   <div id="msCreateOut" class="mono muted" style="margin-top:8px"></div>
	   <div class="row"><div><label>Redeem script</label><input id="msRedeem" class="mono" placeholder="OP_2 ... OP_CHECKMULTISIG"></div><div><label>Destination</label><input id="msTo" placeholder="Nc... / net1..."></div></div>
	   <div class="row"><div><label>Amount (NET)</label><input id="msAmount" type="number" step="0.00000001"></div><div><label>Fee (NET)</label><input id="msFee" type="number" step="0.00000001" value="0.01"></div></div>
	   <button class="ghost" onclick="createMultisigPsbt()">Create multisig spend PSBT</button>
	   <button class="ghost" onclick="signMultisigPsbt()">Sign with loaded wallet</button>
	   <button class="ghost" onclick="extractMultisigPsbt()">Extract when ready</button>
	   <label>PSBT exchange box</label><input id="msPsbt" class="mono" placeholder="netpsbt:...">
	   <div id="msProgress" class="muted" style="margin-top:8px">0 of 0 collected</div>
	   <div id="msSpendOut" class="mono muted" style="margin-top:8px"></div>
	  </div>

  <div class="card hide" id="receiveCard">
   <h2>Request payment</h2>
   <p class="muted">Create a shareable payment link for your address.</p>
   <div class="row">
    <div><label>Amount (NET, optional)</label><input id="reqAmt" type="number" step="0.00000001" placeholder="any"></div>
    <div><label>Label (optional)</label><input id="reqLabel" placeholder="e.g. Coffee"></div>
   </div>
   <button class="act" onclick="makePayLink()">Create payment link</button>
   <div id="reqOut" style="margin-top:10px"></div>
  </div>

  <div class="card hide" id="historyCard">
   <h2>Recent activity</h2>
   <div id="historyOut" class="muted">—</div>
  </div>
 </section>

 <section id="tab-faucet" class="hide">
  <div class="card"><h2>Faucet</h2>
   <p class="muted">Get free testnet NET sent to your wallet address.</p>
   <div class="mono" id="faucetAddr">Create or load a wallet first.</div>
   <div id="faucetLink" style="margin-top:12px"></div>
  </div>
 </section>

 <section id="tab-explorer" class="hide">
  <div class="card"><h2>Search</h2>
   <div class="row"><input id="q" placeholder="height, block hash, txid, or address">
   <button class="act" style="flex:0 0 auto" onclick="search()">Search</button></div>
   <div id="searchOut" style="margin-top:10px"></div>
  </div>
  <div class="card"><h2>Latest blocks</h2><table id="latest"><tbody></tbody></table></div>
 </section>

 <section id="tab-node" class="hide">
  <div class="card"><h2>Local node</h2>
   <p class="muted">Start or stop a NetCoin node on this computer. The button is available only when this page is served from the local install on 127.0.0.1.</p>
   <div id="nodeStatus" class="muted">Checking local node control...</div>
   <div class="row" style="margin-top:10px">
    <button class="act" onclick="startLocalNode()">Start node</button>
    <button class="ghost" onclick="stopLocalNode()">Stop node</button>
    <button class="ghost" onclick="refreshLocalNode()">Refresh</button>
   </div>
   <div class="warn">If another NetCoin node is already using the default port, this page will connect to it but will not stop it.</div>
  </div>
 </section>

 <section id="tab-seed" class="hide">
  <div class="card"><h2>Run a public seed</h2>
   <p class="muted">A seed is a public node that helps other nodes find the network. This is a bigger commitment than the local Node tab: it listens on 0.0.0.0 and needs your router/firewall to forward the port to be reachable from the internet.</p>
   <ul class="muted" style="margin:8px 0 14px;padding-left:18px">
    <li>Use a machine that can stay on — a laptop that sleeps will drop off the network.</li>
    <li>Forward TCP port 28444 (or your chosen port) on your router to this machine.</li>
    <li>Set "Advertise" to <b>your own</b> real, reachable public IP or domain and port, like 198.51.100.10:28444 (that number is just a format example — use your actual address). Leave it blank to run for yourself only, without announcing it.</li>
    <li>Pick "home" bandwidth mode on a home internet connection so relay traffic doesn't saturate your link.</li>
    <li>Share the address with others only after it's stayed synced for a while.</li>
   </ul>
   <div class="row">
    <div><label>Port</label><input id="seedPort" type="number" placeholder="28444"></div>
    <div><label>Bandwidth mode</label><select id="seedBandwidth"><option value="">normal</option><option value="home">home</option><option value="low">low</option></select></div>
   </div>
   <label>Advertise (public host:port peers should use — optional)</label><input id="seedAdvertise" placeholder="your.public.ip:28444" autocomplete="off">
   <div id="seedStatus" class="muted" style="margin-top:10px">Checking seed node control...</div>
   <div class="row" style="margin-top:10px">
    <button class="act" onclick="startSeedNode()">Start seed</button>
    <button class="ghost" onclick="stopSeedNode()">Stop seed</button>
    <button class="ghost" onclick="refreshSeedNode()">Refresh</button>
   </div>
   <div class="warn">This opens your machine to inbound connections on the chosen port. Only run this if you understand what a public seed does; testnet only, never expose wallet/API-key ports this way.</div>
  </div>
 </section>
</div>
	<script>
		let CFG={}, ADDRS={}, curType="segwit", BAL={}, FEE_ESTIMATES=null, LAST_SENT=null;
	const $=s=>document.querySelector(s);
	const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
	const jsq=s=>JSON.stringify(String(s??''));
	function safeUrl(u){try{const x=new URL(String(u),location.href);return ['http:','https:'].includes(x.protocol)?x.href:'';}catch{return '';}}
	async function api(p,opt={},timeoutMs=35000){const ctrl=new AbortController();const timer=setTimeout(()=>ctrl.abort(),timeoutMs);
  try{opt=Object.assign({},opt,{signal:ctrl.signal});const r=await fetch(p,opt);const text=await r.text();let j={};
    try{j=text?JSON.parse(text):{};}catch(e){throw new Error('node returned non-JSON response');}
    if(!r.ok&&j.error)throw new Error(j.error);if(!r.ok)throw new Error('HTTP '+r.status);return j;}
  catch(e){if(e.name==='AbortError')throw new Error('request timed out; check mempool/explorer, then try again');throw e;}
  finally{clearTimeout(timer);}}
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('on'));b.classList.add('on');
  ['wallet','faucet','explorer','node','seed'].forEach(t=>$('#tab-'+t).classList.toggle('hide',t!==b.dataset.tab));
  if(b.dataset.tab==='explorer')loadLatest();
  if(b.dataset.tab==='node')refreshLocalNode();
  if(b.dataset.tab==='seed')refreshSeedNode();
});
function nodeHelp(msg){return esc(msg)+'<div class="warn"><b>Node connection help</b><br>Use the public API proxy when home Wi-Fi blocks the seed port. If your network blocks api.netcoin.online, use the direct-IP API:<div class="mono">python -m netcoin web --node http://18.220.89.128/api --faucet https://faucet.netcoin.online</div><br>Configured node: <span class="mono">'+esc(CFG.node||'unknown')+'</span></div>';}
async function boot(){CFG=await api('/api/config');$('#netinfo').textContent=CFG.network+' · node '+CFG.node;
  $('#q').addEventListener('keydown',e=>{if(e.key==='Enter')search();});
	  await loadFeeEstimates();const w=await api('/api/wallet/current');if(w.address)showWallet(w);refreshLocalNode();}
function showWallet(w){ADDRS=w.addresses;const sel=$('#typeSel');sel.innerHTML='';
  Object.keys(ADDRS).forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t;sel.appendChild(o);});
	  $('#noWallet').classList.add('hide');$('#haveWallet').classList.remove('hide');$('#sendCard').classList.remove('hide');$('#receiveCard').classList.remove('hide');$('#historyCard').classList.remove('hide');$('#multisigCard').classList.remove('hide');
	  if(w.mnemonic){$('#mnemonicBox').innerHTML='<div class="warn"><b>Recovery phrase (shown once):</b><div class="mono">'+esc(w.mnemonic)+'</div>Write it down. <a href="data:application/json,'+encodeURIComponent(JSON.stringify(w.wallet_file))+'" download="wallet.json">Download wallet.json</a></div>';}
		  switchType();applyFeePreset();}
	async function loadFeeEstimates(){try{FEE_ESTIMATES=await api('/api/fee-estimates',{},8000);applyFeePreset();}catch(e){FEE_ESTIMATES=null;}}
	function presetFeeNet(name){const presets=(FEE_ESTIMATES&&FEE_ESTIMATES.presets)||{};const mapped={economy:'slow',normal:'normal',fast:'fast'}[name]||name;const entry=presets[mapped]||{};const sats=Number(entry.estimated_fee_sats||0);return sats>0?(sats/100000000).toFixed(8):'';}
	function applyFeePreset(){const sel=$('#feePreset');if(!sel||sel.value==='custom')return;const fee=presetFeeNet(sel.value);if(fee)$('#sendFee').value=fee;}
function switchType(){curType=$('#typeSel').value||'segwit';$('#addrType').textContent=curType;
  $('#addr').textContent=ADDRS[curType];$('#faucetAddr').textContent=ADDRS[curType];
	  const faucet=safeUrl(CFG.faucet);
	  $('#faucetLink').innerHTML=faucet?'<a class="act" style="display:inline-block;text-decoration:none" href="'+esc(faucet)+'" target="_blank" rel="noopener noreferrer">Open faucet ↗</a> <span class="muted">paste the address above</span>':'<span class="muted">No faucet configured.</span>';
	  refreshBalance();loadHistory();}
function openTx(t){document.querySelectorAll('.tabs button').forEach(x=>x.classList.remove('on'));
  const eb=document.querySelector('.tabs button[data-tab="explorer"]');eb.classList.add('on');
  ['wallet','faucet','explorer','node','seed'].forEach(tb=>$('#tab-'+tb).classList.toggle('hide',tb!=='explorer'));
  loadLatest();searchFor(t);}
async function loadHistory(){const out=$('#historyOut');try{
  const d=await api('/api/history?address='+ADDRS[curType]);
  const ids=(d.transaction_ids||[]).slice(-15).reverse();
	  out.innerHTML=ids.length?(`<div class="muted">${esc(d.transaction_count)} total · newest first</div>`+ids.map(t=>`<div class="lnk mono" onclick="openTx(${jsq(t)})">${esc(short(t))}</div>`).join('')):'<span class="muted">No transactions yet for this address.</span>';
	}catch(e){out.innerHTML=nodeHelp(e.message);}}
async function newWallet(){try{const w=await api('/api/wallet/new',{method:'POST'});showWallet(w);}catch(e){alert(e.message)}}
async function loadWallet(){try{const w=await api('/api/wallet/load',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({json:$('#loadJson').value,passphrase:$('#loadPass').value})});showWallet(w);}catch(e){alert(e.message)}}
async function loadPrivateKey(){try{const w=await api('/api/wallet/private-key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({private_key_hex:$('#privHex').value})});showWallet(w);}catch(e){alert(e.message)}}
function renderNodeStatus(d){const out=$('#nodeStatus');if(!out)return;
  if(!d.enabled){out.innerHTML='<span class="err">Unavailable here.</span><div class="muted">'+esc(d.reason||'Open this through python -m netcoin web on 127.0.0.1.')+'</div>';return;}
  const mode=d.external?'already running outside this page':(d.owned?'started by this page':'stopped');
  out.innerHTML='<div class="rcard">'+kv('Status',d.running?'<b class="ok">running</b>':'<span class="muted">stopped</span>')+
    kv('Mode',esc(mode))+kv('Node URL','<span class="mono">'+esc(d.url||'')+'</span>')+
    kv('Height',esc(d.height??'n/a'))+kv('Peers',esc(d.peers??'n/a'))+
    kv('Log','<span class="mono">'+esc(d.log||'')+'</span>')+'</div>';}
async function refreshLocalNode(){try{renderNodeStatus(await api('/api/local-node/status',{},8000));}catch(e){$('#nodeStatus').innerHTML=nodeHelp(e.message);}}
async function startLocalNode(){const out=$('#nodeStatus');out.textContent='Starting local node...';try{renderNodeStatus(await api('/api/local-node/start',{method:'POST'},15000));}catch(e){out.innerHTML=nodeHelp(e.message);}}
async function stopLocalNode(){const out=$('#nodeStatus');out.textContent='Stopping local node...';try{renderNodeStatus(await api('/api/local-node/stop',{method:'POST'},15000));}catch(e){out.innerHTML=nodeHelp(e.message);}}
function renderSeedStatus(d){const out=$('#seedStatus');if(!out)return;
  if(!d.enabled){out.innerHTML='<span class="err">Unavailable here.</span><div class="muted">'+esc(d.reason||'Open this through python -m netcoin web on 127.0.0.1.')+'</div>';return;}
  const mode=d.external?'already running outside this page':(d.owned?'started by this page':'stopped');
  out.innerHTML='<div class="rcard">'+kv('Status',d.running?'<b class="ok">running</b>':'<span class="muted">stopped</span>')+
    kv('Mode',esc(mode))+kv('Bind address','<span class="mono">'+esc(d.bind_host||'')+':'+esc(d.port??'')+'</span>')+
    kv('Advertise',d.advertise?('<span class="mono">'+esc(d.advertise)+'</span>'):'<span class="muted">not announced (local peers only)</span>')+
    (d.advertise_unreachable?kv('Advertise check','<span class="err">unreachable — check public IP and port forwarding</span><div class="muted">'+esc(d.advertise_unreachable_error||'self-dial failed')+'</div>'):'')+
    kv('Height',esc(d.height??'n/a'))+kv('Peers',esc(d.peers??'n/a'))+
    kv('Log','<span class="mono">'+esc(d.log||'')+'</span>')+'</div>';}
async function refreshSeedNode(){try{renderSeedStatus(await api('/api/seed-node/status',{},8000));}catch(e){$('#seedStatus').innerHTML=nodeHelp(e.message);}}
async function startSeedNode(){const out=$('#seedStatus');out.textContent='Starting seed node...';
  try{renderSeedStatus(await api('/api/seed-node/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({port:$('#seedPort').value||undefined,advertise:$('#seedAdvertise').value.trim(),bandwidth_mode:$('#seedBandwidth').value})},15000));}
  catch(e){out.innerHTML=nodeHelp(e.message);}}
async function stopSeedNode(){const out=$('#seedStatus');out.textContent='Stopping seed node...';try{renderSeedStatus(await api('/api/seed-node/stop',{method:'POST'},15000));}catch(e){out.innerHTML=nodeHelp(e.message);}}
function copyAddr(){navigator.clipboard.writeText(ADDRS[curType]);}
async function refreshBalance(){try{const b=await api('/api/balance?address='+ADDRS[curType]);BAL=b;
	  $('#balSpendable').innerHTML=esc(b.spendable||'0')+' <span class="muted" style="font-size:14px">'+esc(CFG.ticker)+'</span>';
  $('#balDetail').textContent='immature '+(b.immature||'0')+' · total '+(b.total||'0')+' · '+(b.utxo_count||0)+' UTXOs';}catch(e){$('#balSpendable').textContent='—';$('#balDetail').innerHTML=nodeHelp(e.message);}}
async function makePayLink(){const out=$('#reqOut');try{
  const p=new URLSearchParams({address:ADDRS[curType]});
  if($('#reqAmt').value)p.set('amount',$('#reqAmt').value);
  if($('#reqLabel').value)p.set('label',$('#reqLabel').value);
  const d=await api('/api/payment-uri?'+p.toString());
	  out.innerHTML=`<div class="muted">Share this link:</div><div class="mono" id="payUriOut">${esc(d.uri)}</div><button class="ghost" style="margin-top:8px" onclick="navigator.clipboard.writeText(document.getElementById('payUriOut').textContent)">Copy link</button>`;
	}catch(e){out.innerHTML=nodeHelp(e.message);}}
async function applyPayLink(){const v=$('#payLink').value.trim();if(!v.toLowerCase().startsWith('netcoin:'))return;try{
  const d=await api('/api/parse-uri?uri='+encodeURIComponent(v));
  $('#sendTo').value=d.address;if(d.amount)$('#sendAmt').value=d.amount;
}catch(e){}}
async function send(){const out=$('#sendOut'),btn=$('#sendBtn');
  const amount=parseFloat($('#sendAmt').value||'0'),fee=parseFloat($('#sendFee').value||'0'),spendable=parseFloat(BAL.spendable||'0');
  if(!$('#sendTo').value.trim()){out.innerHTML='<span class="err">Destination address required.</span>';return;}
  if(!(amount>0)){out.innerHTML='<span class="err">Amount must be positive.</span>';return;}
  if((amount+fee)>spendable){out.innerHTML='<span class="err">Amount plus fee exceeds spendable balance. Spendable: '+esc(BAL.spendable||'0')+' '+esc(CFG.ticker)+'</span>';return;}
  if(spendable>0&&(amount+fee)>spendable*0.9&&!confirm('This sends more than 90% of your spendable balance. Continue?'))return;
  if(btn){btn.disabled=true;btn.textContent='Sending…';}out.textContent='Preparing and broadcasting transaction…';try{
  const j=await api('/api/wallet/send',{method:'POST',headers:{'Content-Type':'application/json'},
	   body:JSON.stringify({to:$('#sendTo').value.trim(),amount:$('#sendAmt').value,fee:$('#sendFee').value,from_type:curType,rbf:$('#rbfSend').checked})},45000);
		  LAST_SENT=j;
		  out.innerHTML='<span class="ok">Sent!</span> txid <span class="mono">'+esc(j.txid)+'</span><div class="muted">inputs '+esc(j.input_count||'?')+' · weight '+esc(j.weight||'?')+' · change '+esc(j.change||0)+' '+esc(CFG.ticker)+' · RBF '+(j.signals_rbf?'enabled':'off')+'</div>';refreshBalance();loadHistory();}
	  catch(e){out.innerHTML=nodeHelp(e.message)+'<div class="warn">If this timed out after a large send, check the mempool and mine one block before trying again.</div>';}
  finally{if(btn){btn.disabled=false;btn.textContent='Send';}}}
	async function bumpLastFee(){const out=$('#sendOut');try{if(!LAST_SENT||!LAST_SENT.tx||!LAST_SENT.prevouts)throw new Error('send an opt-in-RBF transaction first');
	  const current=Number(LAST_SENT.fee||0);const next=(current>0?current*2:0.02).toFixed(8);
	  const wanted=prompt('New replacement fee in NET',next);if(!wanted)return;
	  const bumped=await api('/api/wallet/rbf-bump',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({original_tx:LAST_SENT.tx,prevouts:LAST_SENT.prevouts,new_fee:wanted,change_address:ADDRS[curType],broadcast:true})},45000);
	  LAST_SENT={tx:bumped.replacement_tx,prevouts:LAST_SENT.prevouts,fee:bumped.new_fee_net,txid:bumped.txid};
	  out.innerHTML='<span class="ok">Fee bumped!</span> replacement txid <span class="mono">'+esc(bumped.txid||bumped.replacement_txid)+'</span><div class="muted">old fee '+esc(bumped.old_fee_net)+' NET · new fee '+esc(bumped.new_fee_net)+' NET</div>';}
	  catch(e){out.innerHTML=nodeHelp(e.message);}}
	function msSetProgress(progress){const p=progress||{};$('#msProgress').textContent=`${p.collected||0} of ${p.required||0} collected${p.ready?' · ready to extract':''}`;}
	async function createMultisigWallet(){const out=$('#msCreateOut');try{const d=await api('/api/wallet/multisig/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({required:$('#msRequired').value,pubkeys:$('#msPubkeys').value})});
	  $('#msRedeem').value=d.redeem_script;out.innerHTML='Address: '+esc(d.address)+'\\nRedeem script: '+esc(d.redeem_script);}catch(e){out.innerHTML=nodeHelp(e.message);}}
	async function createMultisigPsbt(){const out=$('#msSpendOut');try{const d=await api('/api/wallet/multisig/psbt/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({redeem_script:$('#msRedeem').value,to:$('#msTo').value,amount:$('#msAmount').value,fee:$('#msFee').value})},45000);
	  $('#msPsbt').value=d.unsigned_psbt;msSetProgress(d.progress);out.textContent='Unsigned multisig PSBT created for '+d.multisig_address+'. Export/import this box between cosigners.';}catch(e){out.innerHTML=nodeHelp(e.message);}}
	async function signMultisigPsbt(){const out=$('#msSpendOut');try{const d=await api('/api/wallet/multisig/psbt/sign',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({psbt:$('#msPsbt').value,redeem_script:$('#msRedeem').value})},45000);
	  $('#msPsbt').value=d.signed_psbt;msSetProgress(d.progress);out.textContent='Signature added. Share the updated PSBT with the next cosigner, or extract if ready.';}catch(e){out.innerHTML=nodeHelp(e.message);}}
	async function extractMultisigPsbt(){const out=$('#msSpendOut');try{const d=await api('/api/wallet/psbt/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({psbt:$('#msPsbt').value})},45000);
	  msSetProgress(d.progress);out.innerHTML='<span class="ok">Ready transaction extracted.</span> txid <span class="mono">'+esc(d.txid)+'</span>';}
	  catch(e){out.innerHTML=nodeHelp(e.message);}}
function fmtTime(ts){return ts?new Date(ts*1000).toLocaleString():'';}
function short(h){return h?(h.length>26?h.slice(0,14)+'…'+h.slice(-8):h):'';}
	function card(t,b){return '<div class="rcard"><div class="rtitle">'+esc(t)+'</div>'+b+'</div>';}
	function kv(k,v){return '<div class="kv"><span class="muted">'+esc(k)+'</span><span>'+v+'</span></div>';}
function searchFor(q){$('#q').value=q;search();$('#searchOut').scrollIntoView({behavior:'smooth',block:'center'});}
function renderResult(d){
	  if(!d||d.error)return '<div class="err">'+esc((d&&d.error)||'no result')+'</div>';
	  if(d.type==='address'){const r=d.result,b=r.balance_net||{};
	    const txs=(r.transaction_ids||[]).slice(0,30).map(t=>`<div class="lnk mono" onclick="searchFor(${jsq(t)})">${esc(short(t))}</div>`).join('');
	    return card('Address','<div class="mono sub">'+esc(r.address)+'</div>'+
	      kv('Spendable','<b>'+esc(b.spendable||'0')+'</b> '+esc(CFG.ticker))+kv('Immature',esc(b.immature||'0')+' '+esc(CFG.ticker))+
	      kv('Total',esc(b.total||'0')+' '+esc(CFG.ticker))+kv('Transactions',esc(r.transaction_count||0))+kv('UTXOs',esc(r.utxo_count||0))+
	      (txs?'<div class="muted" style="margin:10px 0 4px">Transaction IDs</div>'+txs:''));}
	  if(d.type==='transaction'){const r=d.result,tx=r.tx||{};
	    return card('Transaction','<div class="mono sub">'+esc(r.txid||'')+'</div>'+
	      kv('Status',r.confirmed?'confirmed ✓':'unconfirmed')+kv('Block',r.block_height!=null?('#'+esc(r.block_height)):'mempool')+
	      kv('Inputs',esc((tx.inputs||[]).length))+kv('Outputs',esc((tx.outputs||[]).length))+
	      (r.block_hash?`<div class="lnk mono" onclick="searchFor(${jsq(r.block_hash)})">in block ${esc(short(r.block_hash))}</div>`:''));}
	  if(d.type==='block'){const r=d.result,h=r.header||{};
	    return card('Block #'+esc(h.height),'<div class="mono sub">'+esc(r.hash||'')+'</div>'+
	      kv('Time',esc(fmtTime(h.timestamp)))+kv('Transactions',esc((r.transactions||[]).length))+kv('Weight',esc(r.weight||''))+
	      (h.previous_hash?`<div class="lnk mono" onclick="searchFor(${jsq(h.previous_hash)})">↑ previous ${esc(short(h.previous_hash))}</div>`:''));}
	  return '<pre class="mono">'+esc(JSON.stringify(d,null,2))+'</pre>';}
async function search(){const out=$('#searchOut');if(!$('#q').value.trim()){out.innerHTML='';return;}out.innerHTML='<span class="muted">Searching…</span>';
  try{out.innerHTML=renderResult(await api('/api/search?q='+encodeURIComponent($('#q').value.trim())));}
	  catch(e){out.innerHTML=nodeHelp(e.message);}}
	async function loadLatest(){const tb=$('#latest').querySelector('tbody');tb.innerHTML='<tr><td class="muted">Loading…</td></tr>';
	  try{const d=await api('/api/latest?n=15');tb.innerHTML='<tr><th>Height</th><th>Hash</th><th>Txns</th><th>Time</th></tr>'+
	    d.blocks.map(b=>`<tr class="lnk" onclick="searchFor(${jsq(b.hash)})"><td>#${esc(b.height)}</td><td class="mono">${esc(short(b.hash))}</td><td>${esc(b.transactions)}</td><td class="muted">${esc(fmtTime(b.timestamp))}</td></tr>`).join('');}
	  catch(e){tb.innerHTML='<tr><td>'+nodeHelp(e.message)+'</td></tr>';}}
boot();
</script></body></html>"""


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #


def make_handler(node_url: str, faucet_url: str = "", *, allow_node_control: bool = False):
    node_url = _normalize_node_url(node_url)
    state: dict[str, Wallet | None] = {"wallet": None}
    # ThreadingHTTPServer serves requests concurrently against this one
    # mutable wallet. Without a lock, two overlapping sends (or a send racing
    # a load/new that swaps the active wallet mid-flight) could both select
    # the same UTXOs or build against a wallet that changed underneath them.
    send_lock = threading.Lock()
    local_node = LocalNodeController(enabled=allow_node_control)
    # A public seed is a different animal from the loopback convenience node
    # above: it binds 0.0.0.0 (reachable from the internet if the operator
    # forwards the port) on the real network's default P2P port, not the
    # wallet's local-only 18444. Its own data dir keeps it independent of
    # the convenience node so both can run at once.
    seed_node = LocalNodeController(
        enabled=allow_node_control,
        port=28444,
        data_dir=Path.home() / ".netcoin-seed-node",
        bind_host="0.0.0.0",
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # quiet
            return

        # Maximum JSON request body this local wallet server will read into
        # memory at once. Without a ceiling, any localhost/network client can
        # exhaust memory just by sending a large Content-Length.
        _MAX_BODY_BYTES = 5 * 1024 * 1024

        def _security_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            # PAGE is a single self-contained document with its own inline
            # <style>/<script> blocks (there are no external site assets to
            # attack via CDN injection here) -- a bare default-src 'self'
            # silently blocks both, breaking the wallet's own UI/behavior.
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
            )

        def _same_origin(self) -> bool:
            """A same-site browser POST cannot be forged from another origin
            when we require the request to actually target this server's own
            Host. A cross-site <form> submit or fetch() carries an Origin (or
            Referer) header naming the attacker's page, not this one -- so
            rejecting a mismatch blocks that CSRF path outright. Non-browser
            callers (curl, scripts) send no Origin at all and are unaffected."""
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            referer = self.headers.get("Referer")
            candidate = origin or referer
            if not candidate:
                return True
            try:
                candidate_host = urlparse(candidate).netloc
            except ValueError:
                return False
            return candidate_host == host

        def _send(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(body)

        def _read(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length <= 0:
                return {}
            if length > self._MAX_BODY_BYTES:
                raise ValueError("request body is too large")
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    data = PAGE.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self._security_headers()
                    self.end_headers()
                    self.wfile.write(data)
                elif parsed.path == "/api/config":
                    self._send(
                        {
                            "node": node_url,
                            "faucet": faucet_url,
                            "network": NETWORK_NAME,
                            "ticker": TICKER,
                            "version": NODE_VERSION,
                        }
                    )
                elif parsed.path == "/api/wallet/current":
                    w = state["wallet"]
                    self._send(
                        {"address": w.address_for("segwit"), "addresses": _wallet_addresses(w)}
                        if w
                        else {"address": None}
                    )
                elif parsed.path == "/api/balance":
                    address = parse_qs(parsed.query).get("address", [""])[0]
                    self._send(_node_get(node_url, f"/balance/{address}"))
                elif parsed.path == "/api/history":
                    address = parse_qs(parsed.query).get("address", [""])[0]
                    self._send(_node_get(node_url, f"/address/{address}"))
                elif parsed.path == "/api/latest":
                    n = parse_qs(parsed.query).get("n", ["15"])[0]
                    self._send(_node_get(node_url, f"/latest?n={int(n)}"))
                elif parsed.path == "/api/fee-estimates":
                    self._send(_node_get(node_url, "/fee-estimates"))
                elif parsed.path == "/api/search":
                    self._send(self._search(parse_qs(parsed.query).get("q", [""])[0]))
                elif parsed.path == "/api/payment-uri":
                    from .paymenturi import build_uri

                    q = parse_qs(parsed.query)
                    self._send(
                        {
                            "uri": build_uri(
                                q.get("address", [""])[0],
                                amount=q.get("amount", [None])[0] or None,
                                label=q.get("label", [None])[0] or None,
                                message=q.get("message", [None])[0] or None,
                            )
                        }
                    )
                elif parsed.path == "/api/parse-uri":
                    from .paymenturi import parse_uri

                    self._send(parse_uri(parse_qs(parsed.query).get("uri", [""])[0]))
                elif parsed.path == "/api/local-node/status":
                    self._send(local_node.status())
                elif parsed.path == "/api/seed-node/status":
                    self._send(seed_node.status())
                else:
                    self._send({"error": "not found"}, status=404)
            except HTTPError as exc:
                self._send({"error": f"node returned HTTP {exc.code} for {parsed.path}"}, status=502)
            except (URLError, OSError) as exc:
                self._send(
                    {
                        "error": "cannot reach the node",
                        "node": node_url,
                        "hint": "Use --node https://api.netcoin.online/api, or start a local node and use --node http://127.0.0.1:28444",
                        "detail": str(exc),
                    },
                    status=502,
                )
            except Exception as exc:
                self._send({"error": str(exc)}, status=400)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if not self._same_origin():
                self._send({"error": "cross-origin request rejected"}, status=403)
                return
            try:
                if parsed.path == "/api/wallet/new":
                    wallet, mnemonic = Wallet.create_with_mnemonic()
                    state["wallet"] = wallet
                    self._send(
                        {
                            "address": wallet.address_for("segwit"),
                            "addresses": _wallet_addresses(wallet),
                            "mnemonic": mnemonic,
                            "wallet_file": wallet.to_dict(passphrase=None),
                        }
                    )
                elif parsed.path == "/api/wallet/load":
                    body = self._read()
                    wallet = self._load_wallet(body.get("json", ""), body.get("passphrase") or None)
                    state["wallet"] = wallet
                    self._send({"address": wallet.address_for("segwit"), "addresses": _wallet_addresses(wallet)})
                elif parsed.path == "/api/wallet/private-key":
                    body = self._read()
                    wallet = self._load_private_key(body.get("private_key_hex", ""))
                    state["wallet"] = wallet
                    self._send({"address": wallet.address_for("segwit"), "addresses": _wallet_addresses(wallet)})
                elif parsed.path == "/api/wallet/send":
                    self._send(self._send_tx(self._read()))
                elif parsed.path == "/api/wallet/rbf-bump":
                    self._send(self._rbf_bump(self._read()))
                elif parsed.path == "/api/wallet/multisig/create":
                    self._send(self._multisig_create(self._read()))
                elif parsed.path == "/api/wallet/multisig/psbt/create":
                    self._send(self._multisig_psbt_create(self._read()))
                elif parsed.path == "/api/wallet/multisig/psbt/sign":
                    self._send(self._multisig_psbt_sign(self._read()))
                elif parsed.path == "/api/wallet/psbt/combine":
                    self._send(self._psbt_combine(self._read()))
                elif parsed.path == "/api/wallet/psbt/extract":
                    self._send(self._psbt_extract(self._read()))
                elif parsed.path == "/api/wallet/psbt/export":
                    self._send(self._psbt_export(self._read()))
                elif parsed.path == "/api/wallet/psbt/sign":
                    self._send(self._psbt_sign(self._read()))
                elif parsed.path == "/api/wallet/psbt/import":
                    self._send(self._psbt_import(self._read()))
                elif parsed.path == "/api/wallet/psbt/broadcast":
                    self._send(self._psbt_broadcast(self._read()))
                elif parsed.path == "/api/local-node/start":
                    self._send(local_node.start())
                elif parsed.path == "/api/local-node/stop":
                    self._send(local_node.stop())
                elif parsed.path == "/api/seed-node/start":
                    body = self._read()
                    advertise = str(body.get("advertise") or "").strip()
                    bandwidth_mode = str(body.get("bandwidth_mode") or "").strip()
                    port = body.get("port")
                    if advertise and ":" not in advertise:
                        raise ValueError("advertise must be host:port, e.g. your.public.ip:28444")
                    if bandwidth_mode and bandwidth_mode not in {"normal", "home", "low"}:
                        raise ValueError("bandwidth_mode must be normal, home, or low")
                    seed_node.advertise = advertise
                    seed_node.bandwidth_mode = bandwidth_mode
                    if port:
                        seed_node.port = int(port)
                    self._send(seed_node.start())
                elif parsed.path == "/api/seed-node/stop":
                    self._send(seed_node.stop())
                else:
                    self._send({"error": "not found"}, status=404)
            except HTTPError as exc:
                self._send({"error": f"node rejected the request (HTTP {exc.code})"}, status=400)
            except Exception as exc:
                self._send({"error": str(exc)}, status=400)

        def _load_wallet(self, raw_json: str, passphrase: str | None) -> Wallet:
            if not raw_json.strip():
                raise ValueError("paste your wallet JSON")
            # Validate it parses, then load via the standard (encryption-aware) path.
            try:
                json.loads(raw_json)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"that isn't valid wallet JSON ({exc.msg}). Paste the full contents "
                    f"of your wallet .json file (an address goes in the Explorer, not here)."
                ) from exc
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
                handle.write(raw_json)
                path = handle.name
            try:
                return Wallet.load(path, passphrase=passphrase)
            finally:
                Path(path).unlink(missing_ok=True)

        def _load_private_key(self, private_key_hex: str) -> Wallet:
            clean = str(private_key_hex or "").strip().removeprefix("0x").replace(" ", "").replace("\n", "")
            if len(clean) != 64:
                raise ValueError("private key must be 64 hex characters")
            return Wallet.from_dict({"private_key_hex": clean})

        def _send_tx(self, body: dict[str, Any]) -> dict[str, Any]:
            with send_lock:
                wallet = state["wallet"]
                if wallet is None:
                    raise ValueError("no wallet loaded")
                to = str(body.get("to", "")).strip()
                if not to:
                    raise ValueError("destination address required")
                amount_sats = amount_to_sats(str(body.get("amount", "")))
                fee_sats = amount_to_sats(str(body.get("fee", "0") or "0"))
                from_type = str(body.get("from_type") or "segwit")
                rbf = bool(body.get("rbf"))
                return build_and_broadcast(wallet, to, amount_sats, fee_sats, from_type, node_url, rbf=rbf)

        def _rbf_bump(self, body: dict[str, Any]) -> dict[str, Any]:
            with send_lock:
                wallet = state["wallet"]
                if wallet is None:
                    raise ValueError("no wallet loaded")
                original = Transaction.from_dict(body.get("original_tx") or {})
                prevouts = [SpendableOutput.from_dict(item) for item in body.get("prevouts") or []]
                if not prevouts:
                    raise ValueError("prevouts are required to bump a fee")
                new_fee = amount_to_sats(str(body.get("new_fee", "")))
                change_address = str(body.get("change_address") or wallet.address_for("segwit")).strip()
                old_fee = transaction_fee(original, prevouts)
                plan = create_rbf_replacement(
                    wallet, original, prevouts, new_fee=new_fee, change_address=change_address
                )
                payload: dict[str, Any] = {
                    **plan.to_dict(),
                    "old_fee": old_fee,
                    "old_fee_net": old_fee / COIN,
                    "new_fee_net": new_fee / COIN,
                    "replacement_tx": plan.replacement.to_dict(),
                }
                if body.get("broadcast"):
                    response = _node_post(node_url, "/tx", plan.replacement.to_dict(), timeout=30)
                    payload["txid"] = response.get("txid") or plan.replacement.txid()
                    payload["node_response"] = response
                return payload

        def _multisig_create(self, body: dict[str, Any]) -> dict[str, Any]:
            wallet = state["wallet"]
            if wallet is None:
                raise ValueError("no wallet loaded")
            raw_pubkeys = body.get("pubkeys") or body.get("public_keys") or []
            if isinstance(raw_pubkeys, str):
                pubkeys = [item.strip() for item in raw_pubkeys.replace(",", "\n").splitlines() if item.strip()]
            else:
                pubkeys = [str(item).strip() for item in raw_pubkeys if str(item).strip()]
            required = int(body.get("required") or 0)
            if not pubkeys:
                raise ValueError("at least one cosigner public key is required")
            result = wallet.create_multisig_address(required, pubkeys)
            return {**result, "required": required, "cosigners": len(pubkeys), "public_keys": pubkeys}

        def _multisig_psbt_create(self, body: dict[str, Any]) -> dict[str, Any]:
            redeem_script = str(body.get("redeem_script") or "").strip()
            if not redeem_script:
                raise ValueError("redeem_script is required")
            to = str(body.get("to", "")).strip()
            if not to:
                raise ValueError("destination address required")
            amount_sats = amount_to_sats(str(body.get("amount", "")))
            fee_sats = amount_to_sats(str(body.get("fee", "0") or "0"))
            psbt = build_unsigned_multisig_psbt(redeem_script, to, amount_sats, fee_sats, node_url)
            text = "netpsbt:" + psbt.to_base64()
            return {
                "unsigned_psbt": text,
                "multisig_address": script_to_p2sh_address(redeem_script),
                "progress": multisig_psbt_progress(psbt),
            }

        def _multisig_psbt_sign(self, body: dict[str, Any]) -> dict[str, Any]:
            wallet = state["wallet"]
            if wallet is None:
                raise ValueError("no wallet loaded")
            psbt_text = str(body.get("psbt") or body.get("unsigned_psbt") or "").strip()
            if not psbt_text:
                raise ValueError("psbt is required")
            psbt = PartiallySignedTransaction.from_base64(psbt_text)
            redeem_script = str(body.get("redeem_script") or "").strip()
            for index in range(len(psbt.tx.inputs)):
                if redeem_script and index not in psbt.redeem_scripts:
                    psbt.set_multisig_input(index, redeem_script)
                psbt.sign_multisig_input(index, wallet)
            return {"signed_psbt": "netpsbt:" + psbt.to_base64(), "progress": multisig_psbt_progress(psbt)}

        def _psbt_combine(self, body: dict[str, Any]) -> dict[str, Any]:
            texts = [str(item).strip() for item in body.get("psbts") or [] if str(item).strip()]
            if not texts:
                raise ValueError("psbts are required")
            combined = PartiallySignedTransaction.from_base64(texts[0])
            for text in texts[1:]:
                combined.combine(PartiallySignedTransaction.from_base64(text))
            return {"combined_psbt": "netpsbt:" + combined.to_base64(), "progress": multisig_psbt_progress(combined)}

        def _psbt_extract(self, body: dict[str, Any]) -> dict[str, Any]:
            psbt_text = str(body.get("psbt") or body.get("signed_psbt") or "").strip()
            if not psbt_text:
                raise ValueError("psbt is required")
            psbt = PartiallySignedTransaction.from_base64(psbt_text)
            tx = psbt.extract()
            payload: dict[str, Any] = {"txid": tx.txid(), "tx": tx.to_dict(), "progress": multisig_psbt_progress(psbt)}
            if body.get("broadcast"):
                response = _node_post(node_url, "/tx", tx.to_dict(), timeout=30)
                payload["txid"] = response.get("txid") or tx.txid()
                payload["node_response"] = response
            return payload

        def _psbt_export(self, body: dict[str, Any]) -> dict[str, Any]:
            """Build an unsigned PSBT for offline/hardware signing (no keys used)."""
            wallet = state["wallet"]
            if wallet is None:
                raise ValueError("no wallet loaded")
            to = str(body.get("to", "")).strip()
            if not to:
                raise ValueError("destination address required")
            amount_sats = amount_to_sats(str(body.get("amount", "")))
            fee_sats = amount_to_sats(str(body.get("fee", "0") or "0"))
            from_type = str(body.get("from_type") or "segwit")
            psbt = build_unsigned_psbt_for_send(wallet, to, amount_sats, fee_sats, from_type, node_url)
            unsigned_text = "netpsbt:" + psbt.to_base64()
            return export_unsigned_psbt_bundle(unsigned_text)

        def _psbt_sign(self, body: dict[str, Any]) -> dict[str, Any]:
            """Software offline signer: sign a supplied unsigned PSBT with the loaded wallet."""
            wallet = state["wallet"]
            if wallet is None:
                raise ValueError("no wallet loaded")
            unsigned_text = str(body.get("unsigned_psbt", "")).strip()
            if not unsigned_text.startswith("netpsbt:"):
                raise ValueError("unsigned_psbt must be a netpsbt: payload")
            psbt = PartiallySignedTransaction.from_base64(unsigned_text)
            psbt.sign(wallet)
            return {
                "signed_psbt": "netpsbt:" + psbt.to_base64(),
                "fully_signed": psbt.is_fully_signed(),
                "signer_type": "software-offline",
            }

        def _psbt_import(self, body: dict[str, Any]) -> dict[str, Any]:
            """Validate a signed PSBT against its unsigned skeleton; prep for broadcast."""
            unsigned_text = str(body.get("unsigned_psbt", "")).strip()
            signed_text = str(body.get("signed_psbt", "")).strip()
            if not unsigned_text or not signed_text:
                raise ValueError("both unsigned_psbt and signed_psbt are required")
            return import_signed_psbt(unsigned_text, signed_text)

        def _psbt_broadcast(self, body: dict[str, Any]) -> dict[str, Any]:
            """Extract the signed transaction and submit it to the node."""
            signed_text = str(body.get("signed_psbt", "")).strip()
            if not signed_text:
                raise ValueError("signed_psbt is required")
            package = build_broadcast_package(signed_text)
            psbt = PartiallySignedTransaction.from_base64(signed_text)
            tx = psbt.extract()
            response = _node_post(node_url, "/tx", tx.to_dict(), timeout=30)
            return {
                "txid": response.get("txid") or package["txid"],
                "broadcast_hash": package["broadcast_hash"],
                "node_response": response,
            }

        def _search(self, query: str) -> dict[str, Any]:
            query = query.strip()
            if not query:
                return {"error": "empty query"}
            # Try, in order: height -> block, txid, address.
            if query.isdigit():
                headers = _node_get(node_url, f"/headers?start={int(query)}&limit=1").get("headers", [])
                if headers and int(headers[0].get("height", -1)) == int(query):
                    return {"type": "block", "result": _node_get(node_url, f"/block/{headers[0]['hash']}")}
            for path, kind in (
                (f"/tx/{query}", "transaction"),
                (f"/address/{query}", "address"),
                (f"/block/{query}", "block"),
            ):
                try:
                    return {"type": kind, "result": _node_get(node_url, path)}
                except HTTPError:
                    continue
            return {"error": "no block, transaction, or address matched"}

    # Exposed so run_web_wallet can stop any node this wallet spawned when
    # the server process exits -- otherwise a launched node/seed keeps
    # running as an orphan, holding its port even after the wallet is gone.
    Handler.owned_node_controllers = (local_node, seed_node)
    return Handler


def run_web_wallet(node_url: str, faucet_url: str = "", host: str = "127.0.0.1", port: int = 8088) -> None:
    node_url = _normalize_node_url(node_url)
    allow_node_control = host in LOCAL_NODE_HOSTS
    handler_class = make_handler(node_url, faucet_url, allow_node_control=allow_node_control)
    server = ThreadingHTTPServer((host, int(port)), handler_class)
    print(f"NetCoin web wallet on http://{host}:{port}  (node: {node_url})")
    print("Local tool — keys stay on this machine. Do not expose this port publicly.")
    if allow_node_control:
        print("Local node button enabled. It can start/stop only the node launched by this web wallet.")

    def _stop_owned_nodes() -> None:
        for controller in getattr(handler_class, "owned_node_controllers", ()):
            try:
                if controller.process and controller.process.poll() is None:
                    controller.stop()
            except Exception:
                pass

    atexit.register(_stop_owned_nodes)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    finally:
        _stop_owned_nodes()
