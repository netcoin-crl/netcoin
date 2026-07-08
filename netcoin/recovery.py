"""Wallet recovery-center helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .wallet import Wallet, WalletError, verify_seed_phrase, wallet_needs_migration


def seed_backup_check(seed_phrase: str, expected_address: str | None = None, *, indexes: int = 20) -> dict[str, Any]:
    valid = verify_seed_phrase(seed_phrase)
    addresses = []
    matched_index = None
    if valid:
        for index in range(max(1, min(int(indexes), 200))):
            wallet = Wallet.create(seed_phrase=seed_phrase, index=index)
            info = wallet.public_dict()
            info["index"] = index
            addresses.append(info)
            if expected_address and expected_address in info.get("addresses", {}).values():
                matched_index = index
    return {
        "valid": valid,
        "expected_address": expected_address,
        "matched_index": matched_index,
        "addresses": addresses,
        "address_count": len(addresses),
    }


def encrypted_backup_validate(path: str | Path, passphrase: str | None = None) -> dict[str, Any]:
    path = Path(path)
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        return {"ok": False, "path": str(path), "error": f"cannot read wallet file: {exc}"}
    encrypted = bool(data.get("encrypted"))
    needs_migration = wallet_needs_migration(data)
    public = {k: data.get(k) for k in ("network", "address", "addresses", "wallet_version", "encrypted") if k in data}
    if encrypted and passphrase is None:
        return {
            "ok": True,
            "path": str(path),
            "encrypted": True,
            "needs_passphrase": True,
            "needs_migration": needs_migration,
            "public": public,
        }
    try:
        wallet = Wallet.from_dict(data, passphrase=passphrase)
    except WalletError as exc:
        return {"ok": False, "path": str(path), "encrypted": encrypted, "error": str(exc), "public": public}
    return {
        "ok": True,
        "path": str(path),
        "encrypted": encrypted,
        "needs_migration": needs_migration,
        "address": wallet.address,
        "public": wallet.public_dict(),
    }


def migration_dry_run(path: str | Path, passphrase: str | None = None) -> dict[str, Any]:
    report = encrypted_backup_validate(path, passphrase=passphrase)
    if not report.get("ok") or report.get("needs_passphrase"):
        return report | {"can_migrate": False}
    data = json.loads(Path(path).read_text())
    return report | {"can_migrate": True, "would_upgrade": wallet_needs_migration(data), "target_format_version": 3}


def gap_limit_scan_preview(
    chain: Any, seed_phrase: str, *, gap_limit: int = 20, max_index: int = 200
) -> dict[str, Any]:
    if not verify_seed_phrase(seed_phrase):
        raise WalletError("seed phrase checksum is invalid")
    gap = 0
    found = []
    scanned = 0
    for index in range(max(1, int(max_index))):
        wallet = Wallet.create(seed_phrase=seed_phrase, index=index)
        addresses = wallet.public_dict().get("addresses", {})
        used = False
        balances = {}
        for kind, address in addresses.items():
            try:
                summary = chain.address_balance_summary(address)
                balances[kind] = summary
                if summary.get("transaction_count", 0) or summary.get("total_sats", 0):
                    used = True
            except Exception:
                balances[kind] = {"address": address, "error": "not scanned"}
        scanned += 1
        if used:
            gap = 0
            found.append({"index": index, "addresses": addresses, "balances": balances})
        else:
            gap += 1
            if gap >= int(gap_limit):
                break
    return {"scanned_indexes": scanned, "gap_limit": int(gap_limit), "used_indexes": found, "used_count": len(found)}


def recovery_report(
    chain: Any | None = None,
    *,
    seed_phrase: str | None = None,
    wallet_file: str | Path | None = None,
    passphrase: str | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {"checks": []}
    if seed_phrase:
        seed = seed_backup_check(seed_phrase)
        report["seed_backup"] = seed
        report["checks"].append({"name": "seed_phrase", "ok": seed["valid"]})
        if chain is not None:
            scan = gap_limit_scan_preview(chain, seed_phrase)
            report["gap_scan"] = scan
            report["checks"].append({"name": "gap_limit_scan", "ok": True, "used_count": scan["used_count"]})
    if wallet_file:
        backup = encrypted_backup_validate(wallet_file, passphrase=passphrase)
        report["wallet_file"] = backup
        report["checks"].append(
            {"name": "wallet_file", "ok": backup.get("ok", False), "needs_migration": backup.get("needs_migration")}
        )
    report["ok"] = all(item.get("ok") for item in report["checks"]) if report["checks"] else False
    return report


def recovery_action_plan(report: dict[str, Any]) -> dict[str, Any]:
    """Turn recovery check results into user-facing next steps."""
    actions: list[dict[str, Any]] = []
    if not report.get("checks"):
        actions.append(
            {"priority": "high", "action": "run_recovery_checks", "message": "No recovery checks were provided."}
        )
    seed = report.get("seed_backup") or {}
    if seed and not seed.get("valid"):
        actions.append(
            {"priority": "critical", "action": "replace_seed_backup", "message": "Seed phrase checksum is invalid."}
        )
    wallet_file = report.get("wallet_file") or {}
    if wallet_file.get("needs_passphrase"):
        actions.append(
            {
                "priority": "medium",
                "action": "test_passphrase",
                "message": "Encrypted backup was readable but not decrypted; test the passphrase.",
            }
        )
    if wallet_file.get("needs_migration"):
        actions.append(
            {"priority": "medium", "action": "migrate_wallet_backup", "message": "Wallet backup uses an older format."}
        )
    gap = report.get("gap_scan") or {}
    if gap and gap.get("used_count", 0) > 0:
        actions.append(
            {
                "priority": "low",
                "action": "restore_used_indexes",
                "message": f"Found {gap.get('used_count')} used HD indexes during scan.",
            }
        )
    ok = bool(report.get("ok")) and not any(a["priority"] == "critical" for a in actions)
    return {"ok": ok, "action_count": len(actions), "actions": actions}


def export_recovery_report(path: str | Path, report: dict[str, Any]) -> dict[str, Any]:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(report)
    payload["action_plan"] = recovery_action_plan(report)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return {"ok": True, "path": str(out), "action_count": payload["action_plan"]["action_count"]}
