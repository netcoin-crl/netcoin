"""Live product API helpers for v0.18.

These helpers connect the polished public sites to real node/app state while
remaining safe for local demos. Every function degrades gracefully when a node
has no blocks, no indexer database, or no market/faucet/exchange state yet.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .tx import sats_to_amount


def _short(value: Any, n: int = 12) -> str:
    text = str(value or "")
    return text[:n] + ("…" if len(text) > n else "")


def _chain_data_dir(chain: Any) -> Path:
    return Path(getattr(chain, "data_dir", "."))


def _tx_payload(chain: Any, txid: str) -> dict[str, Any] | None:
    try:
        from .explorer_server import transaction_payload

        return transaction_payload(chain, txid)
    except Exception:
        pass
    try:
        rec = getattr(chain, "tx_index", {}).get(txid)
        if rec:
            return {"txid": txid, **rec}
    except Exception:
        pass
    return None


def _block_payload(chain: Any, block_id: str) -> dict[str, Any] | None:
    block = None
    try:
        if str(block_id).isdigit() and hasattr(chain, "block_at_height"):
            block = chain.block_at_height(int(block_id))
    except Exception:
        block = None
    if block is None:
        try:
            block = chain.get_block_by_hash(block_id)
        except Exception:
            block = None
    if block is None and str(block_id).isdigit():
        try:
            idx = int(block_id)
            if 0 <= idx < len(getattr(chain, "chain", [])):
                block = chain.chain[idx]
        except Exception:
            block = None
    if block is None:
        return None
    try:
        payload = block.to_dict()
    except Exception:
        payload = {}
    try:
        txids = [tx.txid() for tx in getattr(block, "transactions", [])]
    except Exception:
        txids = []
    payload.update(
        {
            "height": getattr(getattr(block, "header", None), "height", payload.get("height")),
            "hash": block.hash() if hasattr(block, "hash") else payload.get("hash"),
            "tx_count": len(txids),
            "txids": txids,
        }
    )
    return payload


def explorer_address_live(chain: Any, address: str, *, limit: int = 100) -> dict[str, Any]:
    address = str(address or "").strip()
    try:
        balance = chain.address_balance_summary(address)
    except Exception as exc:
        balance = {"address": address, "error": str(exc), "total_sats": 0, "spendable_sats": 0, "immature_sats": 0}
    try:
        utxos = [
            u.to_dict() if hasattr(u, "to_dict") else dict(u)
            for u in chain.utxos_for_address(address, include_immature=True)
        ]
    except Exception:
        utxos = []
    txids = []
    try:
        txids = sorted(getattr(chain, "address_index", {}).get(address, set()), reverse=True)[:limit]
    except Exception:
        pass
    history = []
    for txid in txids:
        txp = _tx_payload(chain, txid) or {"txid": txid}
        history.append(
            {
                "txid": txid,
                "short_txid": _short(txid, 16),
                "height": txp.get("height") or txp.get("block_height"),
                "confirmations": txp.get("confirmations"),
                "mempool": bool(txp.get("mempool", False)),
            }
        )
    total_sats = int(balance.get("total_sats") or balance.get("balance", {}).get("total") or 0)
    return {
        "address": address,
        "balance": balance,
        "utxos": utxos[:limit],
        "history": history,
        "history_count": len(txids),
        "profile": {
            "address": address,
            "total_sats": total_sats,
            "total": sats_to_amount(total_sats),
            "utxo_count": len(utxos),
            "activity_count": len(txids),
            "watchable": True,
        },
        "exports": {
            "csv": f"/api/explorer/address/{address}/csv",
            "statement": f"/api/wallet/statement.csv?address={address}",
        },
    }


def explorer_tx_live(chain: Any, txid: str) -> dict[str, Any]:
    txid = str(txid or "").strip()
    payload = _tx_payload(chain, txid)
    if payload is None:
        return {"ok": False, "txid": txid, "error": "transaction not found", "mempool": False}
    return {"ok": True, "txid": txid, "short_txid": _short(txid, 16), **payload}


def explorer_block_live(chain: Any, block_id: str) -> dict[str, Any]:
    block_id = str(block_id or "").strip()
    payload = _block_payload(chain, block_id)
    if payload is None:
        return {"ok": False, "id": block_id, "error": "block not found"}
    return {"ok": True, **payload}


def explorer_mempool_live(chain: Any, *, limit: int = 200) -> dict[str, Any]:
    try:
        info = chain.mempool_info()
    except Exception:
        info = {}
    txs = []
    try:
        for tx in getattr(chain, "mempool", [])[:limit]:
            txs.append(
                {
                    "txid": tx.txid(),
                    "vsize": getattr(tx, "vsize", lambda: None)(),
                    "outputs": len(getattr(tx, "outputs", [])),
                }
            )
    except Exception:
        pass
    return {"summary": info, "transactions": txs, "count": len(txs), "generated_at": int(time.time())}


def explorer_watchlist_live(store: Any, chain: Any, query: dict[str, list[str]] | None = None) -> dict[str, Any]:
    addresses = []
    if query:
        raw = query.get("address", []) + query.get("addresses", [])
        for item in raw:
            addresses.extend(a.strip() for a in str(item).split(",") if a.strip())
    cards = []
    for address in addresses[:50]:
        item = explorer_address_live(chain, address, limit=10)
        cards.append(
            {
                "address": address,
                "activity_count": item["history_count"],
                "total": item["profile"]["total"],
                "latest": item["history"][:3],
            }
        )
    return {"watchlist": cards, "count": len(cards), "generated_at": int(time.time())}


def explorer_address_csv(chain: Any, address: str) -> str:
    payload = explorer_address_live(chain, address, limit=1000)
    rows = ["txid,height,confirmations,mempool"]
    for event in payload.get("history", []):
        rows.append(
            f"{event.get('txid','')},{event.get('height','')},{event.get('confirmations','')},{event.get('mempool',False)}"
        )
    return "\n".join(rows) + "\n"


def wallet_workflow_status(store: Any) -> dict[str, Any]:
    try:
        data = store.load()
    except Exception:
        data = {}
    return {
        "drafts": data.get("wallet_tx_drafts", []),
        "approvals": data.get("wallet_approval_queue", []),
        "fee_presets": {"slow": 1.0, "normal": 2.0, "fast": 5.0},
        "offline_signing": {
            "unsigned_export": True,
            "signed_import": True,
            "qr_placeholder": True,
            "hardware_signer": "adapter-ready",
        },
        "backup_health": data.get("backup_health", {}),
        "vault": {"encrypted_vault_module": True, "session_timeout_minutes": 720},
    }


def save_wallet_draft(store: Any, payload: dict[str, Any]) -> dict[str, Any]:
    data = store.load()
    drafts = data.setdefault("wallet_tx_drafts", [])
    draft = {
        "draft_id": f"draft_{int(time.time())}_{len(drafts)+1}",
        "to": str(payload.get("to") or payload.get("address") or "")[:120],
        "amount": str(payload.get("amount") or "")[:40],
        "fee": str(payload.get("fee") or "")[:40],
        "memo": str(payload.get("memo") or "")[:200],
        "status": "draft",
        "created_at": int(time.time()),
    }
    drafts.append(draft)
    data["wallet_tx_drafts"] = drafts[-100:]
    store.save(data)
    return draft


def faucet_admin_status(state: dict[str, Any] | None = None) -> dict[str, Any]:
    state = state or {}
    return {
        "paused": bool(state.get("paused", False)),
        "difficulty": int(state.get("difficulty", 0) or 0),
        "daily_cap_sats": int(state.get("daily_cap_sats", 0) or 0),
        "recent_requests": list(reversed(state.get("requests", []) or []))[:100],
        "blocked_requests": [x for x in reversed(state.get("abuse", []) or [])][:100],
        "reputation": state.get("reputation", {}),
        "updated_at": int(time.time()),
    }


def operator_live_controls(chain: Any, node: Any | None = None) -> dict[str, Any]:
    peers = []
    try:
        pm = getattr(node, "peer_manager", None)
        if pm and hasattr(pm, "summary"):
            peers = pm.summary().get("peers", [])
    except Exception:
        peers = []
    try:
        height = chain.height()
        tip = chain.tip_hash()
        mempool = chain.mempool_info()
    except Exception:
        height, tip, mempool = 0, "", {}
    return {
        "height": height,
        "tip": tip,
        "mempool": mempool,
        "peers": peers,
        "runbook_actions": ["verify-db", "ops-bundle", "reindex", "backup", "release-verify"],
        "diagnostic_bundle": "/api/operator/diagnostics/bundle",
    }


def exchange_live_status(store: Any) -> dict[str, Any]:
    data = store.load()
    deposits = data.get("exchange_deposits", []) or []
    withdrawals = data.get("exchange_withdrawals", []) or []
    approvals = data.get("exchange_withdrawal_approvals", []) or []
    reserve = data.get("reserve_attestations", []) or []
    return {
        "deposits": deposits[-100:],
        "withdrawals": withdrawals[-100:],
        "approval_queue": [w for w in withdrawals if str(w.get("status")) in {"requested", "approved"}],
        "approvals": approvals[-100:],
        "custody": data.get("exchange_custody", {"hot": 0, "warm": 0, "cold": 0}),
        "reserve_attestations": reserve[-10:],
        "risk_alerts": data.get("exchange_risk_alerts", []),
    }


def release_verify_payload(root: str | Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    base = Path(root)
    payload = payload or {}
    files = {
        "verify_signature": base / "tools" / "verify_signature.py",
        "verify_provenance": base / "tools" / "verify_provenance.py",
        "generate_sbom": base / "tools" / "generate_sbom.py",
    }
    artifact_hash = str(payload.get("sha256") or "").strip().lower()
    expected = str(payload.get("expected_sha256") or "").strip().lower()
    checksum_match = bool(artifact_hash and expected and artifact_hash == expected)
    return {
        "tools": {name: path.exists() for name, path in files.items()},
        "checksum": {"provided": artifact_hash, "expected": expected, "match": checksum_match if expected else None},
        "commands": {
            "signature": "python tools/verify_signature.py <artifact> <signature>",
            "provenance": "python tools/verify_provenance.py <provenance.json>",
            "sbom": "python tools/generate_sbom.py --out sbom.json",
        },
        "status": "verified" if checksum_match else "ready",
    }


def digest_payload(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
