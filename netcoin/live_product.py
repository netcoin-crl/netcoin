"""Live product API helpers for v0.18.

These helpers connect the polished public sites to real node/app state while
remaining safe for local demos. Every function degrades gracefully when a node
has no blocks, no indexer database, or no market/faucet/exchange state yet.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .tx import Transaction, sats_to_amount


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
        raw_utxos = [
            u.to_dict() if hasattr(u, "to_dict") else dict(u)
            for u in chain.utxos_for_address(address, include_immature=True)
        ]
    except Exception:
        raw_utxos = []
    current_height = int(balance.get("height") or getattr(chain, "height", lambda: 0)() or 0)
    utxos = []
    for item in raw_utxos:
        output = item.get("output") or {}
        amount_sats = int(item.get("amount_sats") or output.get("amount") or item.get("amount") or 0)
        height = item.get("height")
        confirmations = max(0, current_height - int(height) + 1) if height is not None else 0
        coinbase = bool(item.get("coinbase", False))
        immature = bool(coinbase and balance.get("height") is not None and confirmations < 100)
        utxos.append(
            {
                **item,
                "outpoint": item.get("outpoint") or f"{item.get('txid', '')}:{item.get('vout', 0)}",
                "address": output.get("address") or item.get("address") or address,
                "amount_sats": amount_sats,
                "amount": sats_to_amount(amount_sats),
                "confirmations": confirmations,
                "spend_status": "immature" if immature else "unspent",
            }
        )
    txids = []
    with contextlib.suppress(Exception):
        txids = sorted(getattr(chain, "address_index", {}).get(address, set()), reverse=True)[:limit]
    history = []
    for txid in txids:
        txp = _tx_payload(chain, txid) or {"txid": txid}
        height = txp.get("height") or txp.get("block_height")
        confirmations = txp.get("confirmations")
        if confirmations is None and height is not None:
            confirmations = max(0, current_height - int(height) + 1)
        history.append(
            {
                "txid": txid,
                "short_txid": _short(txid, 16),
                "height": height,
                "confirmations": confirmations,
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


def explorer_tx_risk(chain: Any, tx_payload: dict[str, Any]) -> dict[str, Any]:
    confirmed = bool(tx_payload.get("confirmed"))
    tx_data = tx_payload.get("tx") or tx_payload.get("transaction") or {}
    warnings: list[dict[str, Any]] = []
    risk_score = 0
    if not confirmed:
        warnings.append({"code": "unconfirmed", "severity": "medium", "message": "Transaction is not confirmed yet."})
        risk_score += 35
    try:
        tx = Transaction.from_dict(tx_data)
        if tx.signals_rbf:
            warnings.append({"code": "rbf", "severity": "medium", "message": "Transaction signals opt-in Replace-By-Fee."})
            risk_score += 20
        try:
            from .tx_simulator import simulate_transaction

            preview = simulate_transaction(chain, tx)
            for warning in preview.get("warnings", []):
                if hasattr(warning, "to_dict"):
                    warnings.append(warning.to_dict())
                elif isinstance(warning, dict):
                    warnings.append(warning)
            risk_score = max(risk_score, int(preview.get("risk_score", 0)))
        except Exception:
            pass
    except Exception:
        tx = None
    mempool = {}
    try:
        mempool = next(
            (entry for entry in chain.mempool_info().get("entries", []) if entry.get("txid") == tx_payload.get("txid")),
            {},
        )
    except Exception:
        mempool = {}
    if mempool:
        risk_score = max(risk_score, 25)
    risk_level = "low"
    if risk_score >= 75:
        risk_level = "critical"
    elif risk_score >= 50:
        risk_level = "high"
    elif risk_score >= 25:
        risk_level = "medium"
    return {
        "status": "confirmed" if confirmed else "unconfirmed",
        "confirmed": confirmed,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "warnings": warnings,
        "mempool": mempool,
        "rbf": bool(mempool.get("rbf")) or any(w.get("code") == "rbf" for w in warnings),
        "fee_sats": mempool.get("fee", 0),
        "fee_rate_per_kvb": mempool.get("fee_rate_per_kvb", 0),
        "policy": "testnet explorer risk summary; not a final settlement guarantee",
    }


def explorer_tx_live(chain: Any, txid: str) -> dict[str, Any]:
    txid = str(txid or "").strip()
    payload = _tx_payload(chain, txid)
    if payload is None:
        return {"ok": False, "txid": txid, "error": "transaction not found", "mempool": False}
    risk = explorer_tx_risk(chain, payload)
    return {"ok": True, "txid": txid, "short_txid": _short(txid, 16), "risk": risk, **payload}


def explorer_block_live(chain: Any, block_id: str) -> dict[str, Any]:
    block_id = str(block_id or "").strip()
    payload = _block_payload(chain, block_id)
    if payload is None:
        return {"ok": False, "id": block_id, "error": "block not found"}
    return {"ok": True, **payload}


def explorer_search_live(chain: Any, store: Any, query: str, *, limit: int = 25) -> dict[str, Any]:
    """Full-text search across every explorer-relevant data type.

    Previously the explorer site's search box was purely a client-side
    heuristic (netcoin/../sites/explorer/explorer-app.js's doSearch): it
    guessed a single destination -- height, address, txid, or block hash --
    from the query's shape and navigated straight there with no way to search
    by name/label/title, and no way to see more than one candidate result.
    This does a real lookup: exact resolution for chain primitives (address,
    txid, block height/hash), plus a case-insensitive substring match across
    usernames, address labels, merchants, bounties, community posts, and
    prediction markets -- anything a person might plausibly be looking for
    by name rather than by raw id.
    """
    q = str(query or "").strip()
    result: dict[str, Any] = {"ok": True, "query": q, "exact": None, "matches": []}
    if not q:
        return result

    needle = q.lower().lstrip("@")

    # Exact chain-primitive resolution first -- these are unambiguous, so
    # surface them as `exact` for a client to jump straight to.
    if len(q) == 64 and all(c in "0123456789abcdefABCDEF" for c in q):
        tx_payload = _tx_payload(chain, q)
        if tx_payload is not None:
            result["exact"] = {"type": "tx", "id": q}
        else:
            block_payload = _block_payload(chain, q)
            if block_payload is not None:
                result["exact"] = {"type": "block", "id": block_payload.get("hash", q)}
    elif q.isdigit():
        block_payload = _block_payload(chain, q)
        if block_payload is not None:
            result["exact"] = {"type": "block", "id": block_payload.get("hash", q)}
    else:
        try:
            balance = chain.address_balance_summary(q)
            if balance and not balance.get("error"):
                result["exact"] = {"type": "address", "id": q}
        except Exception:
            pass

    if result["exact"] is None:
        try:
            record = store.load().get("usernames", {}).get(needle)
            if record and record.get("address"):
                result["exact"] = {"type": "address", "id": record["address"], "label": "@" + needle}
        except Exception:
            pass

    data: dict[str, Any] = {}
    with contextlib.suppress(Exception):
        data = store.load()

    def add_match(kind: str, item_id: str, label: str, haystacks: list[str]) -> None:
        if len(result["matches"]) >= limit:
            return
        if any(needle in str(h or "").lower() for h in haystacks):
            result["matches"].append({"type": kind, "id": item_id, "label": label})

    for name, rec in data.get("usernames", {}).items():
        add_match("username", rec.get("address", ""), "@" + name, [name])
    try:
        for name, addr in chain.list_onchain_usernames().items():
            add_match("username", addr.get("address", "") if isinstance(addr, dict) else str(addr), "@" + name, [name])
    except Exception:
        pass
    for addr, label_rec in data.get("known_labels", {}).items():
        label_text = label_rec.get("label", "") if isinstance(label_rec, dict) else str(label_rec)
        add_match("label", addr, label_text or addr, [label_text, addr])
    for mid, rec in data.get("merchants", {}).items():
        add_match("merchant", mid, str(rec.get("display_name") or rec.get("name") or mid), [mid, rec.get("display_name"), rec.get("name")])
    for bid, rec in data.get("bounties", {}).items():
        add_match("bounty", bid, str(rec.get("title") or bid), [rec.get("title"), rec.get("description")])
    for post in data.get("community_posts", []):
        add_match("community_post", str(post.get("post_id", "")), str(post.get("title") or post.get("body", ""))[:80], [post.get("title"), post.get("body")])
    for mid, rec in data.get("prediction_markets", {}).items():
        add_match("market", mid, str(rec.get("title") or rec.get("question") or mid), [rec.get("title"), rec.get("question")])

    return result


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


def _explorer_watch_store(store: Any) -> Any:
    from .explorer_watch import ExplorerWatchStore

    base = Path(getattr(store, "data_dir", "."))
    return ExplorerWatchStore(base / "explorer_watch.sqlite3")


def explorer_watchlist_live(store: Any, chain: Any, query: dict[str, list[str]] | None = None) -> dict[str, Any]:
    watches = _explorer_watch_store(store).list_watches(active_only=True)
    addresses = [w["value"] for w in watches if w.get("watch_type") == "address"]
    if query:
        raw = query.get("address", []) + query.get("addresses", [])
        for item in raw:
            addresses.extend(a.strip() for a in str(item).split(",") if a.strip())
    seen: set[str] = set()
    cards = []
    for address in addresses[:50]:
        if address in seen:
            continue
        seen.add(address)
        item = explorer_address_live(chain, address, limit=10)
        watch = next((w for w in watches if w.get("watch_type") == "address" and w.get("value") == address), {})
        cards.append(
            {
                "address": address,
                "label": watch.get("label", ""),
                "item_id": watch.get("item_id", ""),
                "activity_count": item["history_count"],
                "utxo_count": item["profile"]["utxo_count"],
                "total": item["profile"]["total"],
                "latest": item["history"][:3],
            }
        )
    return {
        "watchlist": cards,
        "watches": watches,
        "summary": _explorer_watch_store(store).summary(),
        "count": len(cards),
        "generated_at": int(time.time()),
    }


def explorer_watchlist_add(store: Any, chain: Any, body: dict[str, Any]) -> dict[str, Any]:
    watch_type = str(body.get("watch_type") or body.get("type") or "address").lower().strip()
    value = str(body.get("value") or body.get("address") or body.get("txid") or body.get("block") or "").strip()
    label = str(body.get("label") or "").strip()[:120]
    if watch_type == "address":
        from .crypto import validate_address

        if not validate_address(value):
            raise ValueError("address is not a valid NetCoin address")
    elif watch_type == "transaction":
        if len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
            raise ValueError("transaction watch value must be a txid")
    elif watch_type == "block":
        if not value:
            raise ValueError("block watch value is required")
    watch = _explorer_watch_store(store).add_watch(watch_type, value, label=label)
    return {"ok": True, "watch": watch, "watchlist": explorer_watchlist_live(store, chain, {})["watchlist"]}


def explorer_watchlist_remove(store: Any, body: dict[str, Any]) -> dict[str, Any]:
    item_id = str(body.get("item_id") or "").strip()
    if not item_id:
        raise ValueError("item_id is required")
    watch = _explorer_watch_store(store).deactivate_watch(item_id)
    return {"ok": bool(watch), "watch": watch}


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


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _latest_ledger_audit(root: Path | None, chain_dir: Path | None) -> dict[str, Any]:
    candidates: list[Path] = []
    if chain_dir is not None:
        candidates.extend(
            [
                chain_dir / "ledger_audit_report.json",
                chain_dir / "reports" / "ledger_audit_report.json",
                chain_dir / "reports" / "ledger-audit.json",
            ]
        )
    if root is not None:
        candidates.extend(
            [
                root / "reports" / "ledger_audit_report.json",
                root / "reports" / "ledger-audit.json",
            ]
        )
    existing = [p for p in candidates if p.exists()]
    report_path = max(existing, key=lambda p: p.stat().st_mtime) if existing else None
    report = _read_json_file(report_path) if report_path else None
    rows_checked = 0
    if report:
        rows_checked = len(report.get("independent", {}).get("accounts", []) or [])
    ledger_hint = chain_dir / "accounting.sqlite" if chain_dir is not None else Path("accounting.sqlite")
    return {
        "status": "available" if report else "missing-report",
        "ok": bool(report.get("ok")) if report else None,
        "drift_detected": bool(report and (not report.get("ok") or report.get("mismatches"))),
        "rows_checked": rows_checked,
        "report_path": str(report_path) if report_path else "",
        "command": f"python3 tools/run_ledger_audit.py --ledger {ledger_hint} --out reports/ledger_audit_report.json",
    }


def _maintenance_status(chain: Any, chain_dir: Path | None) -> dict[str, Any]:
    backend = str(getattr(chain, "backend", "unknown"))
    sqlite_path = chain_dir / "netcoin.sqlite" if chain_dir is not None else None
    json_path = chain_dir / "chain.json" if chain_dir is not None else None
    backup_candidates: list[Path] = []
    if chain_dir is not None:
        backup_candidates.extend(chain_dir.glob("*.bak"))
        backup_candidates.extend((chain_dir / "backups").glob("*"))
    latest_backup = max(backup_candidates, key=lambda p: p.stat().st_mtime) if backup_candidates else None
    return {
        "backend": backend,
        "data_dir": str(chain_dir or ""),
        "sqlite_present": bool(sqlite_path and sqlite_path.exists()),
        "json_present": bool(json_path and json_path.exists()),
        "backup_available": bool(latest_backup),
        "latest_backup": str(latest_backup) if latest_backup else "",
        "reindex_command": "python3 -m netcoin.cli reindex",
        "backup_command": "python3 -m netcoin.cli backup --out backups/$(date +%Y%m%d-%H%M%S)",
        "restore_note": "Restore stays manual until an operator-run restore drill report exists.",
        "destructive_actions_enabled": False,
    }


def _advertise_status(node: Any | None) -> dict[str, Any]:
    if node is None:
        return {
            "advertise": "",
            "status": "not-configured",
            "unreachable": False,
            "error": "",
            "last_check": "live node unavailable",
        }
    info: dict[str, Any] = {}
    try:
        if hasattr(node, "info"):
            info = node.info()
    except Exception:
        info = {}
    advertised = str(info.get("advertise") or getattr(node, "self_url", "") or "")
    unreachable = bool(info.get("advertise_unreachable", getattr(node, "advertise_unreachable", False)))
    error = str(info.get("advertise_unreachable_error", getattr(node, "advertise_unreachable_error", "")) or "")
    if not advertised:
        status = "not-configured"
    elif unreachable:
        status = "unreachable"
    else:
        status = "reachable"
    return {
        "advertise": advertised,
        "status": status,
        "unreachable": unreachable,
        "error": error,
        "last_check": "startup self-dial" if advertised else "not announced",
    }


def operator_live_controls(chain: Any, node: Any | None = None, root: str | Path | None = None) -> dict[str, Any]:
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
    try:
        chainstate = chain.chainstate_commitment()
    except Exception as exc:
        chainstate = {"ok": False, "error": str(exc) or exc.__class__.__name__}
    chain_dir = Path(getattr(chain, "data_dir", "")) if getattr(chain, "data_dir", None) else None
    root_path = Path(root) if root is not None else None
    return {
        "height": height,
        "tip": tip,
        "mempool": mempool,
        "peers": peers,
        "chainstate": chainstate,
        "ledger_audit": _latest_ledger_audit(root_path, chain_dir),
        "peer_advertise": _advertise_status(node),
        "maintenance": _maintenance_status(chain, chain_dir),
        "runbook_actions": ["verify-db", "ops-bundle", "reindex", "backup", "release-verify"],
        "diagnostic_bundle": "/api/operator/diagnostics/bundle",
    }


def localnet_onboarding_status(chain: Any, store: Any | None = None, node: Any | None = None) -> dict[str, Any]:
    try:
        height = int(chain.height())
        tip = str(chain.tip_hash())
    except Exception:
        height, tip = 0, ""
    try:
        mempool = chain.mempool_info()
    except Exception:
        mempool = {}
    try:
        wallet_payload = wallet_workflow_status(store) if store is not None else {}
    except Exception:
        wallet_payload = {}
    faucet_status = "unknown"
    if store is not None:
        try:
            data = store.load()
            faucet_state = data.get("faucet_state", {})
            faucet_status = "paused" if faucet_state.get("paused") else "available"
        except Exception:
            faucet_status = "unknown"
    node_status = "available" if tip else "unknown"
    if node is not None:
        try:
            health = node.health() if hasattr(node, "health") else {}
            node_status = "available" if health.get("ok", True) else "degraded"
        except Exception:
            node_status = "unknown"
    return {
        "schema": "netcoin-localnet-status-v1",
        "status": "available" if tip else "setup-required",
        "generated_at": int(time.time()),
        "height": height,
        "tip": tip,
        "services": {
            "node_api": {
                "status": node_status,
                "height": height,
                "tip": tip,
                "health_endpoint": "/health",
                "info_endpoint": "/info",
            },
            "wallet": {
                "status": "available" if wallet_payload else "guide-only",
                "endpoint": "/api/wallet/workflow",
                "fee_presets": wallet_payload.get("fee_presets", {}),
            },
            "faucet": {
                "status": faucet_status,
                "endpoint": "/api/faucet/status",
            },
            "explorer": {
                "status": "available",
                "endpoint": "/api/explorer/mempool",
                "mempool": mempool,
            },
        },
        "commands": {
            "install": "python3 -m venv .venv && . .venv/bin/activate && python3 -m pip install -e .",
            "localnet_harness": "PYTHONPATH=. python3 tools/run_localnet.py --nodes 3 --bootstrap-blocks 101 --topology line",
            "single_node": "python3 -m netcoin --data ~/.netcoin-local node --host 127.0.0.1 --port 28444",
            "wallet": "python3 -m netcoin web --node http://127.0.0.1:28444 --faucet http://127.0.0.1:8000/api",
            "mine": "python3 -m netcoin miner --node http://127.0.0.1:28444 --wallet local-wallet.json --blocks 1 --sync-after",
        },
        "testnet_only": True,
        "real_money_value": False,
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


def exchange_listing_readiness(store: Any, root: str | Path | None = None) -> dict[str, Any]:
    """Return the code-side exchange/listing readiness state.

    This deliberately does not claim that NetCoin is listed anywhere. Real listings
    require external counterparties, legal review, liquidity, custody operations,
    and market-maker/compliance work outside the repository.
    """
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    live = exchange_live_status(store)
    files = {
        "exchange_dashboard": base / "sites" / "exchange" / "index.html",
        "exchange_ledger": base / "netcoin" / "exchange.py",
        "deposit_reorg_drill": base / "tests" / "test_exchange_deposit_reorg_drill.py",
        "proof_of_reserves": base / "netcoin" / "exchange_reserves.py",
        "accounting_ledger": base / "netcoin" / "exchange_accounting.py",
        "readiness_doc": base / "docs" / "EXCHANGE_READINESS.md",
    }
    code_gates = [
        {"id": "deposit-withdrawal-state-machine", "label": "Deposit and withdrawal state machine", "status": "available" if files["exchange_ledger"].exists() else "missing", "evidence": "netcoin/exchange.py"},
        {"id": "reorg-safe-deposit-drill", "label": "Reorg-safe deposit drill", "status": "available" if files["deposit_reorg_drill"].exists() else "missing", "evidence": "tests/test_exchange_deposit_reorg_drill.py"},
        {"id": "proof-of-reserves-tooling", "label": "Proof-of-reserves tooling", "status": "available" if files["proof_of_reserves"].exists() else "missing", "evidence": "netcoin/exchange_reserves.py"},
        {"id": "accounting-reconciliation", "label": "Accounting reconciliation helpers", "status": "available" if files["accounting_ledger"].exists() else "missing", "evidence": "netcoin/exchange_accounting.py"},
        {"id": "operator-dashboard", "label": "Operator exchange dashboard", "status": "available" if files["exchange_dashboard"].exists() else "missing", "evidence": "sites/exchange/index.html"},
        {"id": "readiness-doc", "label": "Exchange readiness documentation", "status": "available" if files["readiness_doc"].exists() else "recommended", "evidence": "docs/EXCHANGE_READINESS.md"},
    ]
    external_blockers = [
        {"id": "legal-review", "label": "Legal/entity/compliance review", "status": "external"},
        {"id": "exchange-counterparty", "label": "Exchange or broker counterparty approval", "status": "external"},
        {"id": "liquidity-market-maker", "label": "Liquidity and market-maker agreement", "status": "external"},
        {"id": "independent-security-audit", "label": "Independent security audit", "status": "external"},
        {"id": "production-custody-ops", "label": "Production custody operations and insurance decision", "status": "external"},
    ]
    return {
        "status": "code-side-testnet-readiness",
        "real_listing_available": False,
        "production_ready": False,
        "testnet_only": True,
        "real_money_value": False,
        "summary": "Code-side exchange integration tooling is visible for testnet operators, but NetCoin is not listed and this is not production exchange readiness.",
        "code_gates": code_gates,
        "external_blockers": external_blockers,
        "live_counts": {
            "deposits": len(live.get("deposits", [])),
            "withdrawals": len(live.get("withdrawals", [])),
            "reserve_attestations": len(live.get("reserve_attestations", [])),
            "risk_alerts": len(live.get("risk_alerts", [])),
        },
        "commands": {
            "audit_package": "python3 tools/generate_external_audit_package.py --out reports/external-audit-package",
            "mainnet_readiness": "python3 tools/run_mainnet_readiness.py --strict --timeout 300 --out reports/mainnet_readiness_report.json",
            "ledger_audit": "python3 tools/run_ledger_audit.py --db <exchange-ledger.sqlite> --out reports/ledger_audit_report.json",
            "reserve_attestation": "python3 -m netcoin.exchange_reserves --help",
        },
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
