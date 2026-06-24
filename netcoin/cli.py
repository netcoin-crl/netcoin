"""Command-line interface for NetCoin."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .block import Block
from .chain import Blockchain, ChainError
from .crypto import validate_address
from .miner import block_summary, solve_template
from .explorer import generate_explorer
from .explorer_server import run_explorer_server
from .webwallet import run_web_wallet
from .fuzz import FuzzConfig, run_fuzz
from .node import run_node
from .p2p import Message, getheaders_message, ping_message, request_message, run_p2p_server, version_message
from .params import DEFAULT_DATA_DIR, DEFAULT_NODE_PORT, DEFAULT_P2P_PORT, DEFAULT_POOL_PORT, DEFAULT_RPC_PORT, DEFAULT_TESTNET_SEEDS, NETWORKS, NODE_VERSION, PROTOCOL_VERSION, TICKER
from .pool import run_pool
from .psbt import PartiallySignedTransaction
from .rpc import run_rpc
from .script import describe_address, multisig_redeem_script, script_to_p2sh_address
from .serialization import block_to_raw_hex, decode_raw_transaction, tx_to_raw_hex
from .soak import SoakConfig, run_soak
from .tx import Transaction, amount_to_sats, sats_to_amount
from .wallet import AutoLockWalletSession, Wallet, WalletError, confirm_seed_phrase, verify_seed_phrase


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def load_address(wallet_path: Optional[str], address: Optional[str], *, address_type: str = "p2pkh", passphrase: Optional[str] = None) -> str:
    if wallet_path:
        return Wallet.load(wallet_path, passphrase=passphrase).address_for(address_type)
    if address:
        return address
    raise WalletError("provide --wallet or --address")


def post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str) -> Dict[str, Any]:
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def warn_if_node_incompatible(node_url: str, *, need_service: Optional[str] = None) -> None:
    """Best-effort compatibility check for a remote ``--node``.

    Fetches ``/info`` and prints a warning (without raising) when the node looks
    like it is running an older or mismatched NetCoin: a missing ``version`` field
    (the node predates the version handshake, e.g. pre-v0.4.x seeds), a different
    protocol version, or a missing service the command needs. Network/parse errors
    are swallowed so the real request still surfaces them with its own message.
    """
    try:
        info = get_json(node_url.rstrip("/") + "/info").get("node", {})
    except Exception:
        return
    problems = []
    remote_proto = info.get("protocol_version")
    if remote_proto is not None and remote_proto != PROTOCOL_VERSION:
        problems.append(f"protocol v{remote_proto}, this client speaks v{PROTOCOL_VERSION}")
    if not info.get("version"):
        problems.append("node reports no version (predates v0.4.x)")
    services = info.get("services") or []
    if need_service and need_service not in services:
        problems.append(f"missing '{need_service}' service")
    if problems:
        print(
            f"warning: node {node_url} may be incompatible with this client (v{NODE_VERSION}): "
            + "; ".join(problems)
            + ". If you control the seed, update it (see docs/UPGRADING.md).",
            file=sys.stderr,
        )


def find_transaction(chain: Blockchain, txid: str) -> Optional[Transaction]:
    for tx in chain.mempool:
        if tx.txid() == txid:
            return tx
    for block in chain.chain:
        for tx in block.transactions:
            if tx.txid() == txid:
                return tx
    return None


def cmd_init(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    print_json({"ok": True, "data_dir": str(chain.data_dir), "chain": chain.chain_info()})


def cmd_wallet_new(args: argparse.Namespace) -> None:
    path = Path(args.out)
    if path.exists() and not args.force:
        raise WalletError(f"wallet already exists: {path}; use --force to overwrite")
    mnemonic = None
    if args.from_mnemonic:
        wallet = Wallet.from_mnemonic(args.from_mnemonic, passphrase=args.mnemonic_passphrase or "")
    elif args.wif:
        wallet = Wallet.from_wif(args.wif)
    elif args.mnemonic:
        wallet, mnemonic = Wallet.create_with_mnemonic()
    else:
        wallet = Wallet.create()
    wallet.save(path, passphrase=args.passphrase if args.encrypt else None)
    result = {
        "ok": True,
        "wallet_file": str(path),
        "encrypted": bool(args.encrypt),
        "address": wallet.address,
        "segwit_address": wallet.segwit_address,
        "taproot_address": wallet.taproot_address,
        "p2sh_segwit_address": wallet.p2sh_segwit_address,
        "public_key": wallet.public_key_hex,
    }
    if mnemonic:
        result["mnemonic"] = mnemonic
        result["backup_warning"] = "Write this phrase down now. It is not stored again unless you save it."
        if getattr(args, "confirm_backup", False):
            if sys.stdin.isatty():
                print("Re-enter your seed phrase to confirm you backed it up:", file=sys.stderr)
                typed = sys.stdin.readline().strip()
                if not confirm_seed_phrase(mnemonic, typed):
                    path.unlink(missing_ok=True)
                    raise WalletError("seed phrase confirmation did not match; wallet file removed")
                result["backup_confirmed"] = True
            else:
                # Non-interactive: cannot prompt, so flag that confirmation is owed.
                result["backup_confirmed"] = False
                result["backup_confirmation_required"] = True
    print_json(result)


def cmd_wallet_watch(args: argparse.Namespace) -> None:
    data = Wallet.watch_only(args.address)
    Path(args.out).write_text(json.dumps(data, indent=2, sort_keys=True))
    print_json({"ok": True, "wallet_file": args.out, "watch_only": True, "address": args.address})


def cmd_verify_mnemonic(args: argparse.Namespace) -> None:
    phrase = args.from_mnemonic
    valid = verify_seed_phrase(phrase)
    result: Dict[str, Any] = {"ok": valid, "seed_phrase_valid": valid}
    if not valid:
        result["error"] = "seed phrase is not a valid NetCoin phrase (unknown word or bad checksum)"
        print_json(result)
        sys.exit(1)
    if args.wallet:
        wallet = Wallet.load(args.wallet, passphrase=args.passphrase)
        matches = wallet.matches_seed_phrase(phrase, index=args.index)
        result["wallet_file"] = args.wallet
        result["address"] = wallet.address
        result["matches_wallet"] = matches
        result["ok"] = matches
        if not matches:
            result["error"] = "seed phrase is valid but does not regenerate this wallet's key"
            print_json(result)
            sys.exit(1)
    else:
        # Without a wallet we can still show which address the phrase controls.
        result["address"] = Wallet.create(seed_phrase=phrase, index=args.index).address
    print_json(result)


def cmd_wallet_info(args: argparse.Namespace) -> None:
    wallet = Wallet.load(args.wallet, passphrase=args.passphrase)
    info = wallet.to_plain_dict()
    info["wallet_file"] = args.wallet
    if args.show_private:
        # Guard private-key exposure behind an explicit acknowledgement so it is
        # not printed by accident (e.g. in shared terminals or logs).
        if not args.i_understand_export_risk:
            raise WalletError(
                "refusing to print the private key without --i-understand-export-risk; "
                "anyone with this key controls the wallet"
            )
        info["export_warning"] = "PRIVATE KEY SHOWN. Never share it, paste it, or commit it."
    else:
        info.pop("private_key_hex", None)
        info.pop("wif", None)
    print_json(info)


def cmd_wallet_backup(args: argparse.Namespace) -> None:
    src = Path(args.wallet)
    if not src.exists():
        raise WalletError(f"wallet file not found: {src}")
    out_dir = Path(args.out_dir) if args.out_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = out_dir / f"{src.stem}.backup-{stamp}.json"
    shutil.copy2(src, dest)
    os.chmod(dest, 0o600)
    print_json({"ok": True, "wallet_file": str(src), "backup_file": str(dest)})


def cmd_wallet_migrate(args: argparse.Namespace) -> None:
    from .wallet import WALLET_FORMAT_VERSION, wallet_file_version, wallet_needs_migration

    src = Path(args.wallet)
    if not src.exists():
        raise WalletError(f"wallet file not found: {src}")
    data = json.loads(src.read_text())
    old_version = wallet_file_version(data)
    if not wallet_needs_migration(data):
        print_json({"ok": True, "migrated": False, "wallet_version": old_version, "note": "already current"})
        return
    # Load (decrypting if needed), back up the original, then re-save in the
    # current format (re-encrypts at the upgraded KDF and stamps the version).
    wallet = Wallet.load(src, passphrase=args.passphrase)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    backup = src.with_name(f"{src.stem}.pre-migrate-{stamp}.json")
    shutil.copy2(src, backup)
    os.chmod(backup, 0o600)
    was_encrypted = bool(data.get("encrypted"))
    wallet.save(src, passphrase=args.passphrase if was_encrypted else None)
    os.chmod(src, 0o600)
    print_json(
        {
            "ok": True,
            "migrated": True,
            "from_version": old_version,
            "to_version": WALLET_FORMAT_VERSION,
            "encrypted": was_encrypted,
            "backup_file": str(backup),
            "address": wallet.address,
        }
    )


def cmd_wallet_recover_test(args: argparse.Namespace) -> None:
    if args.wallet:
        expected = Wallet.load(args.wallet, passphrase=args.passphrase).address
    elif args.address:
        expected = args.address
    else:
        raise WalletError("provide --wallet or --address to compare against")
    if not verify_seed_phrase(args.from_mnemonic):
        print_json({"ok": False, "error": "seed phrase is not valid"})
        sys.exit(1)
    # Full round-trip: restore the phrase, save to a temp file, reload, compare.
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "recovered.json"
        recovered = Wallet.from_mnemonic(args.from_mnemonic)
        recovered.save(tmp)
        reloaded = Wallet.load(tmp)
    ok = reloaded.address == expected
    print_json({"ok": ok, "expected_address": expected, "recovered_address": recovered.address})
    if not ok:
        sys.exit(1)


def cmd_wallet_scan(args: argparse.Namespace) -> None:
    if not verify_seed_phrase(args.from_mnemonic):
        print_json({"ok": False, "error": "seed phrase is not valid"})
        sys.exit(1)
    chain = Blockchain(args.data)
    accounts = []
    active = 0
    for index in range(args.gap + 1):
        wallet = Wallet.create(seed_phrase=args.from_mnemonic, index=index)
        balances = chain.balances_for_address(wallet.address)
        tx_count = len(chain.address_index.get(wallet.address, set()))
        is_active = balances["total"] > 0 or tx_count > 0
        active += 1 if is_active else 0
        accounts.append(
            {
                "index": index,
                "address": wallet.address,
                "total": sats_to_amount(balances["total"]),
                "transactions": tx_count,
                "active": is_active,
            }
        )
    print_json({"ok": True, "gap": args.gap, "active_accounts": active, "accounts": accounts})


def cmd_wallet_export_watch(args: argparse.Namespace) -> None:
    wallet = Wallet.load(args.wallet, passphrase=args.passphrase)
    # public_dict carries the public key and every address type, but no secret.
    data = wallet.public_dict()
    data["watch_only"] = True
    data["encrypted"] = False
    Path(args.out).write_text(json.dumps(data, indent=2, sort_keys=True))
    print_json({"ok": True, "watch_only_file": args.out, "address": wallet.address})


def cmd_wallet_descriptor(args: argparse.Namespace) -> None:
    from .descriptors import describe_wallet

    wallet = Wallet.load(args.wallet, passphrase=args.passphrase)
    print_json({"ok": True, "address": wallet.address, "descriptors": describe_wallet(wallet)})


def cmd_descriptor_address(args: argparse.Namespace) -> None:
    from .descriptors import descriptor_to_address

    print_json({"ok": True, "descriptor": args.descriptor, "address": descriptor_to_address(args.descriptor)})


def cmd_wallet_unlock(args: argparse.Namespace) -> None:
    # Verifies the passphrase opens the wallet; optionally writes a decrypted copy.
    passphrase = args.passphrase
    if passphrase is None and sys.stdin.isatty():
        import getpass

        passphrase = getpass.getpass("Wallet passphrase: ")
    if getattr(args, "ttl_seconds", None):
        session = AutoLockWalletSession(args.wallet, passphrase=passphrase, ttl_seconds=args.ttl_seconds)
        wallet = session.get_wallet()
        result: Dict[str, Any] = {"ok": True, "wallet_file": args.wallet, "address": wallet.address, "unlocked": True, "auto_lock": session.status()}
    else:
        wallet = Wallet.load(args.wallet, passphrase=passphrase)
        result: Dict[str, Any] = {"ok": True, "wallet_file": args.wallet, "address": wallet.address, "unlocked": True}
    if args.out:
        wallet.save(args.out, passphrase=None)
        os.chmod(args.out, 0o600)
        result["decrypted_file"] = args.out
        result["warning"] = "Decrypted wallet written without a passphrase. Keep it private."
    print_json(result)


def cmd_multisig_address(args: argparse.Namespace) -> None:
    if args.required < 1 or args.required > len(args.pubkey):
        raise WalletError("required signatures must be between 1 and the number of pubkeys")
    redeem = multisig_redeem_script(args.required, args.pubkey)
    address = script_to_p2sh_address(redeem)
    print_json(
        {
            "ok": True,
            "type": f"{args.required}-of-{len(args.pubkey)} multisig",
            "address": address,
            "required": args.required,
            "pubkeys": args.pubkey,
            "redeem_script": redeem,
        }
    )


def cmd_migrate_sqlite(args: argparse.Namespace) -> None:
    from .storage import SqliteChainStore

    source = Blockchain(args.data, backend="json")
    store = SqliteChainStore(Path(args.data) / "netcoin.sqlite")
    store.save_chain(source.chain)
    store.save_mempool(source.mempool)
    store.close()
    print_json(
        {
            "ok": True,
            "data_dir": args.data,
            "sqlite_file": str(Path(args.data) / "netcoin.sqlite"),
            "blocks": len(source.chain),
            "mempool": len(source.mempool),
            "note": "Set NETCOIN_BACKEND=sqlite to run against the SQLite database.",
        }
    )


def cmd_prune(args: argparse.Namespace) -> None:
    import os

    os.environ.setdefault("NETCOIN_BACKEND", "sqlite")
    chain = Blockchain(args.data, backend="sqlite")
    print_json(chain.prune(keep_depth=args.keep))


def cmd_utxo_snapshot(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    snapshot = chain.export_utxo_snapshot()
    if args.out:
        Path(args.out).write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    summary = {k: v for k, v in snapshot.items() if k != "utxos"}
    summary["ok"] = True
    if args.out:
        summary["snapshot_file"] = args.out
    print_json(summary)


def cmd_label(args: argparse.Namespace) -> None:
    from .labels import LabelStore

    path = args.file or (Path(args.data) / "labels.json")
    store = LabelStore(path)
    if args.set is not None:
        key, label = args.set
        store.set(key, label)
        print_json({"ok": True, "labels_file": str(path), "set": {key: label}})
    elif args.remove is not None:
        removed = store.remove(args.remove)
        print_json({"ok": removed, "labels_file": str(path), "removed": args.remove})
    elif args.get is not None:
        print_json({"key": args.get, "label": store.get(args.get)})
    else:
        print_json({"labels_file": str(path), "labels": store.all()})


def cmd_balance(args: argparse.Namespace) -> None:
    address = load_address(args.wallet, args.address, address_type=args.address_type, passphrase=args.passphrase)
    if args.node:
        warn_if_node_incompatible(args.node)
        response = get_json(args.node.rstrip("/") + f"/balance/{address}")
        print_json(response)
        return
    chain = Blockchain(args.data)
    result = chain.address_balance_summary(address)
    result["ticker"] = TICKER
    print_json(result)


def cmd_utxos(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    address = load_address(args.wallet, args.address, address_type=args.address_type, passphrase=args.passphrase)
    utxos = chain.utxos_for_address(address, include_immature=args.include_immature)
    print_json({"address": address, "utxos": [utxo.to_dict() for utxo in utxos]})


def cmd_mine(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    address = load_address(args.wallet, args.address, address_type=args.address_type, passphrase=args.passphrase)
    mined = []
    for _ in range(args.blocks):
        block = chain.mine_block(address)
        mined.append(
            {
                "height": block.header.height,
                "hash": block.hash(),
                "txs": len(block.transactions),
                "nonce": block.header.nonce,
                "reward": sats_to_amount(block.transactions[0].total_output()),
                "weight": block.weight(),
            }
        )
    print_json({"ok": True, "mined": mined, "tip": chain.chain_info()})


def cmd_send(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    wallet = Wallet.load(args.wallet, passphrase=args.passphrase)
    source = args.from_address or wallet.address_for(args.from_type)
    change_address = args.change_address or wallet.address_for(args.from_type)
    rotated_change = False
    if getattr(args, "rotate_change", False) and not args.change_address:
        wallet_path = Path(args.wallet)
        wallet_data = json.loads(wallet_path.read_text())
        address_types = ["p2pkh", "p2wpkh", "p2tr", "p2sh-segwit"]
        counter = int(wallet_data.get("change_index", 0))
        change_address = wallet.address_for(address_types[counter % len(address_types)])
        rotated_change = True
    tx = wallet.create_transaction(
        chain,
        to_address=args.to,
        amount=amount_to_sats(args.amount),
        fee=amount_to_sats(args.fee),
        from_address=source,
        change_address=change_address,
        rbf=args.rbf,
        select_outpoints=getattr(args, "utxo", None),
        strategy=getattr(args, "coin_strategy", "greedy"),
    )
    txid = chain.add_mempool_transaction(tx)
    if rotated_change:
        wallet_path = Path(args.wallet)
        wallet_data = json.loads(wallet_path.read_text())
        wallet_data["change_index"] = int(wallet_data.get("change_index", 0)) + 1
        wallet_data["last_change_address"] = change_address
        wallet_path.write_text(json.dumps(wallet_data, indent=2, sort_keys=True))
    result: Dict[str, Any] = {
        "ok": True,
        "txid": txid,
        "wtxid": tx.wtxid(),
        "from": source,
        "to": args.to,
        "amount": args.amount,
        "fee": args.fee,
        "change_address": change_address,
        "change_rotated": rotated_change,
        "weight": tx.weight(),
        "vsize": tx.vsize(),
        "outputs": [output.to_dict() for output in tx.outputs],
        "added_to_local_mempool": True,
    }
    if args.broadcast_to:
        response = post_json(args.broadcast_to.rstrip("/") + "/tx", tx.to_dict(include_scripts=True, include_witness=True))
        result["broadcast_response"] = response
    print_json(result)


def cmd_mempool(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    fees = chain.fee_lookup()
    print_json(
        {
            "count": len(chain.mempool),
            "transactions": [
                {
                    "txid": tx.txid(),
                    "wtxid": tx.wtxid(),
                    "inputs": len(tx.inputs),
                    "outputs": len(tx.outputs),
                    "fee": fees.get(tx.txid()),
                    "weight": tx.weight(),
                    "vsize": tx.vsize(),
                    "signals_rbf": bool(tx.signals_rbf),
                }
                for tx in chain.mempool
            ],
        }
    )


def cmd_chain(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    blocks = chain.chain[-args.limit :] if args.limit else chain.chain
    print_json(
        {
            "info": chain.chain_info(),
            "blocks": [
                {
                    "height": block.header.height,
                    "hash": block.hash(),
                    "previous_hash": block.header.previous_hash,
                    "timestamp": block.header.timestamp,
                    "bits": block.header.bits,
                    "nonce": block.header.nonce,
                    "transactions": len(block.transactions),
                    "weight": block.weight(),
                }
                for block in blocks
            ],
        }
    )


def cmd_validate(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    chain.assert_valid_chain(chain.chain)
    print_json({"ok": True, "chain": chain.chain_info()})


def cmd_reindex(args: argparse.Namespace) -> None:
    # Loading the chain already recovers from a corrupt live file if needed
    # (.bak / .tmp fallback) and rebuilds the indexes and UTXO set from blocks.
    chain = Blockchain(args.data)
    chain.reindex()
    print_json({"ok": True, "reindexed": True, "integrity": chain.verify_integrity()})


def cmd_blockfilter(args: argparse.Namespace) -> None:
    from .blockfilter import build_block_filter, filter_hash

    if args.node:
        node = args.node.rstrip("/")
        block_hash = args.block or get_json(f"{node}/headers?start={args.height or 0}&limit=1")["headers"][0]["hash"]
        print_json(get_json(f"{node}/cfilter/{block_hash}"))
        return
    chain = Blockchain(args.data)
    if args.block:
        block = chain.block_by_hash(args.block)
    else:
        height = args.height if args.height is not None else chain.height()
        block = chain.chain[height] if 0 <= height < len(chain.chain) else None
    if block is None:
        print_json({"ok": False, "error": "block not found"})
        return
    data = build_block_filter(block)
    print_json({"block_hash": block.hash(), "height": block.header.height, "filter": data.hex(),
                "filter_hash": filter_hash(data), "bytes": len(data)})


def cmd_scan_filters(args: argparse.Namespace) -> None:
    """Light-client scan: download per-block filters and only flag matching blocks."""
    from .blockfilter import block_filter_match
    from .script import address_to_script_pubkey

    node = args.node.rstrip("/")
    if args.address:
        addresses = [args.address]
    elif args.wallet:
        w = Wallet.load(args.wallet, passphrase=args.passphrase)
        addresses = [w.address_for(t) for t in ("legacy", "segwit", "taproot", "p2sh-segwit")]
    else:
        print_json({"ok": False, "error": "provide --wallet or --address"})
        return
    scripts = {a: address_to_script_pubkey(a) for a in addresses}

    tip = get_json(f"{node}/info")["node"]["height"]
    start = max(0, args.start)
    end = tip if args.end is None else min(args.end, tip)
    matches: List[Dict[str, Any]] = []
    filter_bytes = 0
    scanned = 0
    height = start
    while height <= end:
        headers = get_json(f"{node}/headers?start={height}&limit={min(2000, end - height + 1)}")["headers"]
        if not headers:
            break
        for hdr in headers:
            cf = get_json(f"{node}/cfilter/{hdr['hash']}")
            raw = bytes.fromhex(cf["filter"])
            filter_bytes += len(raw)
            scanned += 1
            hit = [a for a, spk in scripts.items() if block_filter_match(raw, hdr["hash"], spk)]
            if hit:
                matches.append({"height": hdr["height"], "hash": hdr["hash"], "addresses": hit})
        height = headers[-1]["height"] + 1
    print_json({
        "addresses": addresses,
        "scanned_blocks": scanned,
        "filter_bytes_downloaded": filter_bytes,
        "matched_blocks": matches,
        "note": "fetch only the matched blocks in full to read the payments",
    })


def cmd_hd_derive(args: argparse.Namespace) -> None:
    from .hd import HDKey

    leaf = HDKey.from_mnemonic(args.mnemonic, passphrase=args.passphrase or "").derive_path(args.path)
    wallet = Wallet(private_key=leaf.key)
    print_json({
        "path": args.path,
        "addresses": {t: wallet.address_for(t) for t in ("legacy", "segwit", "taproot", "p2sh-segwit")},
        "wif": wallet.wif,
        "xprv": leaf.extended_private_key(),
        "xpub": leaf.neuter().extended_public_key(),
        "warning": "Educational HD wallet. Keep the mnemonic/xprv secret.",
    })


def cmd_hd_address(args: argparse.Namespace) -> None:
    """Watch-only: derive a receive address from an account xpub (no private key)."""
    from .hd import HDKey
    from .crypto import public_key_to_address, public_key_to_p2wpkh_address, public_key_to_taproot_address

    account = HDKey.from_extended_key(args.xpub)
    child = account.derive(args.change).derive(args.index)
    pub = child.public_key
    print_json({
        "path": f".../{args.change}/{args.index}",
        "watch_only": True,
        "addresses": {
            "legacy": public_key_to_address(pub),
            "segwit": public_key_to_p2wpkh_address(pub),
            "taproot": public_key_to_taproot_address(pub[1:]),
        },
    })


def cmd_signmessage(args: argparse.Namespace) -> None:
    from .crypto import sign_message

    wallet = Wallet.load(args.wallet, passphrase=args.passphrase)
    signature = sign_message(wallet.private_key, args.message)
    print_json({"address": wallet.address_for("legacy"), "message": args.message, "signature": signature})


def cmd_verifymessage(args: argparse.Namespace) -> None:
    from .crypto import verify_message

    print_json({"valid": verify_message(args.address, args.message, args.signature)})


def cmd_taproot_tree(args: argparse.Namespace) -> None:
    from .taproot import taproot_output
    from .crypto import private_key_to_xonly_public_key

    if args.wallet:
        wallet = Wallet.load(args.wallet, passphrase=args.passphrase)
        internal = private_key_to_xonly_public_key(wallet.private_key)
    elif args.internal:
        internal = bytes.fromhex(args.internal)
    else:
        print_json({"ok": False, "error": "provide --wallet or --internal <xonly-hex>"})
        return
    print_json(taproot_output(internal, args.script or []))


def cmd_payment_uri(args: argparse.Namespace) -> None:
    from .paymenturi import build_uri, parse_uri

    if args.decode:
        print_json(parse_uri(args.decode))
        return
    if not args.address:
        print_json({"ok": False, "error": "provide --address (or --decode <uri>)"})
        return
    print_json({"uri": build_uri(args.address, amount=args.amount, label=args.label, message=args.message)})


def cmd_export(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    print_json(chain.export_chain())


def cmd_import(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    with open(args.file, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    blocks = chain.import_chain_data(data)
    changed = chain.replace_chain(blocks)
    print_json({"ok": True, "replaced": changed, "chain": chain.chain_info()})


def cmd_headers(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    print_json({"headers": chain.header_list(args.start, args.limit)})


def cmd_fee(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    sat_vb = chain.estimate_fee_rate(args.target)
    print_json({"target_blocks": args.target, "feerate_sat_vb": sat_vb, "feerate_net_kvb": sats_to_amount(sat_vb * 1000)})


def cmd_template(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    address = load_address(args.wallet, args.address, address_type=args.address_type, passphrase=args.passphrase) if (args.wallet or args.address) else None
    print_json(chain.get_block_template(miner_address=address))


def cmd_submitblock(args: argparse.Namespace) -> None:
    block = Block.from_dict(json.loads(Path(args.block).read_text()))
    if args.node:
        response = post_json(args.node.rstrip("/") + "/submitblock", block.to_dict())
        print_json({"submitted_to": args.node, "response": response, "block": block_summary(block)})
        return
    chain = Blockchain(args.data)
    block_hash = chain.add_block(block)
    print_json({"ok": True, "block_hash": block_hash, "block": block_summary(block), "chain": chain.chain_info()})


def cmd_miner(args: argparse.Namespace) -> None:
    payout = load_address(args.wallet, args.address, address_type=args.address_type, passphrase=args.passphrase)
    node = args.node.rstrip("/")
    warn_if_node_incompatible(node, need_service="block-template")
    mined = []
    for _ in range(args.blocks):
        query = urlencode({"address": payout})
        template = get_json(f"{node}/blocktemplate?{query}")
        block = solve_template(template, payout)
        if args.save_blocks:
            out_dir = Path(args.save_blocks)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"block-{block.header.height}-{block.hash()}.json").write_text(
                json.dumps(block.to_dict(), indent=2, sort_keys=True)
            )
        response = post_json(f"{node}/submitblock", block.to_dict())
        mined.append({"block": block_summary(block), "response": response})
        if args.sync_after:
            try:
                post_json(f"{node}/sync", {})
            except Exception:
                pass
    print_json({"ok": True, "node": node, "payout_address": payout, "mined": mined})


def cmd_rawtx(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    tx = find_transaction(chain, args.txid)
    if tx is None:
        raise ChainError("transaction not found")
    raw = tx_to_raw_hex(tx, include_witness=not args.no_witness)
    print_json({"txid": tx.txid(), "wtxid": tx.wtxid(), "raw": raw, "decoded": decode_raw_transaction(raw) if args.decode else None})


def cmd_rawblock(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    block = chain.tip() if args.block_hash == "tip" else chain.block_by_hash(args.block_hash)
    if block is None:
        raise ChainError("block not found")
    print_json({"hash": block.hash(), "height": block.header.height, "raw": block_to_raw_hex(block, include_witness=not args.no_witness)})


def cmd_decode_rawtx(args: argparse.Namespace) -> None:
    print_json(decode_raw_transaction(args.raw_hex))


def cmd_script(args: argparse.Namespace) -> None:
    if not validate_address(args.address):
        raise ChainError("invalid NetCoin address")
    template = describe_address(args.address)
    print_json({"address": args.address, "type": template.kind, "script_pubkey": template.script_pubkey.hex() if hasattr(template.script_pubkey, "hex") else template.script_pubkey, "description": template.description})


def cmd_node(args: argparse.Namespace) -> None:
    host, port, advertise = args.host, args.port, getattr(args, "advertise", None)
    use_seeds = getattr(args, "seeds", False)
    sync_interval = getattr(args, "sync_interval", 0)
    rate_limit_per_min = getattr(args, "rate_limit_per_min", 240)
    peers = list(args.peer or [])
    if getattr(args, "config", None):
        from .config import load_config

        cfg = load_config(args.config)
        peers.extend(p for p in cfg.get("peer", []) if p not in peers)
        if host == "127.0.0.1" and cfg.get("host"):
            host = cfg["host"]
        if port == DEFAULT_NODE_PORT and cfg.get("port"):
            port = cfg["port"]
        if advertise is None and cfg.get("advertise"):
            advertise = cfg["advertise"]
        if not sync_interval and cfg.get("sync_interval") is not None:
            sync_interval = int(cfg["sync_interval"])
        if cfg.get("rate_limit_per_min") is not None and rate_limit_per_min == 240:
            rate_limit_per_min = int(cfg["rate_limit_per_min"])
        use_seeds = use_seeds or cfg.get("seeds", False)
    if use_seeds:
        peers.extend(s for s in DEFAULT_TESTNET_SEEDS if s not in peers)
    run_node(
        data_dir=args.data,
        host=host,
        port=port,
        peers=peers,
        advertise=advertise,
        sync_interval=sync_interval,
        rate_limit_per_min=rate_limit_per_min,
    )


def cmd_rpc(args: argparse.Namespace) -> None:
    run_rpc(data_dir=args.data, host=args.host, port=args.port, token=getattr(args, "rpc_token", None))


def cmd_rpc_call(args: argparse.Namespace) -> None:
    params = json.loads(args.params) if args.params else []
    payload = {"jsonrpc": "2.0", "id": "netcoin-cli", "method": args.method, "params": params}
    print_json(post_json(args.url, payload))


def cmd_pool(args: argparse.Namespace) -> None:
    address = load_address(args.wallet, args.address, address_type=args.address_type, passphrase=args.passphrase)
    run_pool(data_dir=args.data, payout_address=address, host=args.host, port=args.port)


def cmd_explorer(args: argparse.Namespace) -> None:
    chain = Blockchain(args.data)
    index = generate_explorer(chain, args.out)
    print_json({"ok": True, "index": str(index), "blocks": len(chain.chain)})


def cmd_explorer_server(args: argparse.Namespace) -> None:
    run_explorer_server(data_dir=args.data, host=args.host, port=args.port, rate_limit_per_min=args.rate_limit_per_min)


def cmd_web(args: argparse.Namespace) -> None:
    run_web_wallet(node_url=args.node, faucet_url=args.faucet, host=args.host, port=args.port)


def cmd_networks(args: argparse.Namespace) -> None:
    print_json({name: profile.__dict__ for name, profile in NETWORKS.items()})


def cmd_p2p_message(args: argparse.Namespace) -> None:
    if args.parse:
        msg = Message.parse(bytes.fromhex(args.parse))
        print_json({"command": msg.command, "payload_hex": msg.payload.hex(), "payload_text": msg.payload.decode("utf-8", errors="replace")})
    else:
        msg = version_message(args.height)
        print_json({"command": msg.command, "message_hex": msg.serialize().hex()})


def cmd_p2p_server(args: argparse.Namespace) -> None:
    run_p2p_server(data_dir=args.data, host=args.host, port=args.port)


def cmd_p2p_call(args: argparse.Namespace) -> None:
    if args.command == "version":
        message = version_message(args.height, genesis_hash=args.genesis_hash or "")
    elif args.command == "ping":
        message = ping_message(args.nonce)
    elif args.command == "getheaders":
        message = getheaders_message(args.locator)
    else:
        raise ChainError("unsupported p2p-call command")
    response = request_message(args.host, args.port, message, timeout=args.timeout)
    if response is None:
        print_json({"ok": False, "response": None})
        return
    payload_text = response.payload.decode("utf-8", errors="replace")
    try:
        payload: Any = json.loads(payload_text) if payload_text else {}
    except json.JSONDecodeError:
        payload = {"hex": response.payload.hex()}
    print_json({"ok": True, "command": response.command, "payload": payload})


def cmd_soak(args: argparse.Namespace) -> None:
    report = run_soak(
        SoakConfig(
            nodes=args.nodes,
            rounds=args.rounds,
            transactions_per_round=args.transactions_per_round,
            bootstrap_blocks=args.bootstrap_blocks,
            amount=args.amount,
            fee=args.fee,
        ),
        base_dir=args.dir,
    )
    print_json(report)


def cmd_fuzz(args: argparse.Namespace) -> None:
    report = run_fuzz(FuzzConfig(target=args.target, iterations=args.iterations, seed=args.seed, max_bytes=args.max_bytes))
    print_json(report)


def cmd_psbt_sign(args: argparse.Namespace) -> None:
    wallet = Wallet.load(args.wallet, passphrase=args.passphrase)
    psbt = PartiallySignedTransaction.from_base64(Path(args.psbt).read_text().strip())
    psbt.sign(wallet)
    if args.out:
        Path(args.out).write_text(psbt.to_base64())
    print_json({"ok": True, "fully_signed": psbt.is_fully_signed(), "psbt": None if args.out else psbt.to_base64()})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="netcoin", description="NetCoin: a Bitcoin-like cryptocurrency from scratch")
    parser.add_argument("--data", default=DEFAULT_DATA_DIR, help="NetCoin data directory")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create or load a NetCoin data directory")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("wallet-new", help="create a new wallet file")
    p.add_argument("--out", required=True, help="wallet JSON path")
    p.add_argument("--force", action="store_true", help="overwrite an existing wallet")
    p.add_argument("--encrypt", action="store_true", help="encrypt private key material")
    p.add_argument("--passphrase", help="wallet encryption passphrase")
    p.add_argument("--mnemonic", action="store_true", help="create from a new NetCoin seed phrase")
    p.add_argument("--from-mnemonic", help="restore from a NetCoin seed phrase")
    p.add_argument("--mnemonic-passphrase", default="", help="optional seed phrase passphrase")
    p.add_argument("--wif", help="import a NetCoin WIF private key")
    p.add_argument("--confirm-backup", action="store_true", help="require re-entering the seed phrase to confirm backup")
    p.set_defaults(func=cmd_wallet_new)

    p = sub.add_parser("wallet-watch", help="create a watch-only wallet file")
    p.add_argument("--address", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_wallet_watch)

    p = sub.add_parser("wallet-info", help="show wallet public information")
    p.add_argument("--wallet", required=True)
    p.add_argument("--passphrase")
    p.add_argument("--show-private", action="store_true")
    p.add_argument("--i-understand-export-risk", action="store_true", help="required to actually print the private key")
    p.set_defaults(func=cmd_wallet_info)

    p = sub.add_parser("wallet-backup", help="copy a wallet file to a timestamped backup (chmod 600)")
    p.add_argument("--wallet", required=True)
    p.add_argument("--out-dir", help="directory for the backup (default: alongside the wallet)")
    p.set_defaults(func=cmd_wallet_backup)

    p = sub.add_parser("wallet-migrate", help="upgrade a wallet file to the current format/KDF (backs up the original)")
    p.add_argument("--wallet", required=True)
    p.add_argument("--passphrase", help="passphrase for an encrypted wallet")
    p.set_defaults(func=cmd_wallet_migrate)

    p = sub.add_parser("wallet-recover-test", help="restore a seed phrase into a temp wallet and verify the address")
    p.add_argument("--from-mnemonic", required=True)
    p.add_argument("--wallet", help="wallet file whose address the phrase should reproduce")
    p.add_argument("--address", help="expected address (alternative to --wallet)")
    p.add_argument("--passphrase", help="passphrase for an encrypted --wallet")
    p.set_defaults(func=cmd_wallet_recover_test)

    p = sub.add_parser("wallet-export-watch", help="export a watch-only wallet file (no private key) from a wallet")
    p.add_argument("--wallet", required=True)
    p.add_argument("--passphrase")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_wallet_export_watch)

    p = sub.add_parser("wallet-descriptor", help="show output descriptors (pkh/wpkh/tr/sh-wpkh) for a wallet")
    p.add_argument("--wallet", required=True)
    p.add_argument("--passphrase")
    p.set_defaults(func=cmd_wallet_descriptor)

    p = sub.add_parser("descriptor-address", help="resolve an output descriptor to its NetCoin address")
    p.add_argument("--descriptor", required=True)
    p.set_defaults(func=cmd_descriptor_address)

    p = sub.add_parser("wallet-scan", help="derive addresses 0..gap from a seed and report on-chain activity")
    p.add_argument("--from-mnemonic", required=True)
    p.add_argument("--gap", type=int, default=20, help="highest key index to scan (default 20)")
    p.set_defaults(func=cmd_wallet_scan)

    p = sub.add_parser("wallet-unlock", help="verify an encrypted wallet opens; optionally write a decrypted copy")
    p.add_argument("--wallet", required=True)
    p.add_argument("--passphrase", help="passphrase (prompted if omitted on a TTY)")
    p.add_argument("--out", help="optional path to write a decrypted (unencrypted) wallet copy")
    p.add_argument("--ttl-seconds", type=int, help="report an auto-lock expiry for daemon/interactive integrations")
    p.set_defaults(func=cmd_wallet_unlock)

    p = sub.add_parser("multisig-address", help="build an M-of-N P2SH multisig address from public keys")
    p.add_argument("--required", type=int, required=True, help="M: required signatures")
    p.add_argument("--pubkey", action="append", required=True, help="a signer public key hex (repeatable)")
    p.set_defaults(func=cmd_multisig_address)

    p = sub.add_parser("utxo-snapshot", help="export the current UTXO set (with digest) for bootstrap/verification")
    p.add_argument("--out", help="write the snapshot JSON to this file")
    p.set_defaults(func=cmd_utxo_snapshot)

    p = sub.add_parser("migrate-sqlite", help="copy a JSON data directory into a SQLite database")
    p.set_defaults(func=cmd_migrate_sqlite)

    p = sub.add_parser("prune", help="prune old block bodies (SQLite backend), keeping headers + a UTXO snapshot")
    p.add_argument("--keep", type=int, default=2016, help="number of most-recent blocks to keep with full bodies")
    p.set_defaults(func=cmd_prune)

    p = sub.add_parser("label", help="manage an address/peer/txid label book")
    p.add_argument("--file", help="labels JSON file (default: <data>/labels.json)")
    p.add_argument("--set", nargs=2, metavar=("KEY", "LABEL"), help="set a label")
    p.add_argument("--get", metavar="KEY", help="show a label")
    p.add_argument("--remove", metavar="KEY", help="remove a label")
    p.set_defaults(func=cmd_label)

    p = sub.add_parser("verify-mnemonic", help="check a seed phrase is valid and (optionally) controls a wallet")
    p.add_argument("--from-mnemonic", required=True, help="the NetCoin seed phrase to verify")
    p.add_argument("--wallet", help="optional wallet file the phrase should regenerate")
    p.add_argument("--passphrase", help="passphrase for an encrypted wallet file")
    p.add_argument("--index", type=int, default=0, help="key index (default 0)")
    p.set_defaults(func=cmd_verify_mnemonic)

    p = sub.add_parser("balance", help="show address balance")
    p.add_argument("--wallet")
    p.add_argument("--address")
    p.add_argument("--address-type", default="p2pkh", choices=["p2pkh", "p2wpkh", "p2tr", "p2sh-segwit"])
    p.add_argument("--passphrase")
    p.add_argument("--node", help="query a remote node instead of local chain data")
    p.set_defaults(func=cmd_balance)

    p = sub.add_parser("utxos", help="list UTXOs for an address")
    p.add_argument("--wallet")
    p.add_argument("--address")
    p.add_argument("--address-type", default="p2pkh", choices=["p2pkh", "p2wpkh", "p2tr", "p2sh-segwit"])
    p.add_argument("--include-immature", action="store_true")
    p.add_argument("--passphrase")
    p.set_defaults(func=cmd_utxos)

    p = sub.add_parser("mine", help="mine one or more blocks")
    p.add_argument("--wallet")
    p.add_argument("--address")
    p.add_argument("--address-type", default="p2pkh", choices=["p2pkh", "p2wpkh", "p2tr", "p2sh-segwit"])
    p.add_argument("--blocks", type=int, default=1)
    p.add_argument("--passphrase")
    p.set_defaults(func=cmd_mine)

    p = sub.add_parser("send", help="create, sign, and queue a transaction")
    p.add_argument("--wallet", required=True, help="sender wallet file")
    p.add_argument("--passphrase")
    p.add_argument("--from-type", default="p2pkh", choices=["p2pkh", "p2wpkh", "p2tr", "p2sh-segwit"])
    p.add_argument("--from-address", help="explicit source address")
    p.add_argument("--change-address")
    p.add_argument("--to", required=True, help="destination NetCoin address")
    p.add_argument("--amount", required=True, help="amount in NET, e.g. 1.25")
    p.add_argument("--fee", default="0.001", help="fee in NET")
    p.add_argument("--rbf", action="store_true", help="signal opt-in replace-by-fee")
    p.add_argument("--utxo", action="append", metavar="TXID:VOUT", help="coin control: spend specific UTXOs (repeatable)")
    p.add_argument("--coin-strategy", default="greedy", choices=["greedy", "largest-first", "smallest-first", "random"], help="coin-selection strategy")
    p.add_argument("--rotate-change", action="store_true", help="rotate change across wallet-controlled address types and persist change_index")
    p.add_argument("--broadcast-to", help="node URL, e.g. http://127.0.0.1:18444")
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("mempool", help="show local mempool")
    p.set_defaults(func=cmd_mempool)

    p = sub.add_parser("chain", help="show chain summary")
    p.add_argument("--limit", type=int, default=10, help="number of latest blocks to print; 0 prints all")
    p.set_defaults(func=cmd_chain)

    p = sub.add_parser("headers", help="show headers for headers-first syncing")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_headers)

    p = sub.add_parser("fee", help="estimate local smart fee")
    p.add_argument("--target", type=int, default=1)
    p.set_defaults(func=cmd_fee)

    p = sub.add_parser("template", help="show getblocktemplate-style mining data")
    p.add_argument("--wallet")
    p.add_argument("--address")
    p.add_argument("--address-type", default="p2pkh", choices=["p2pkh", "p2wpkh", "p2tr", "p2sh-segwit"])
    p.add_argument("--passphrase")
    p.set_defaults(func=cmd_template)

    p = sub.add_parser("submitblock", help="submit a solved block JSON locally or to a node")
    p.add_argument("block", help="path to solved block JSON")
    p.add_argument("--node", help="node URL, e.g. http://seed1.netcoin.online:28444")
    p.set_defaults(func=cmd_submitblock)

    p = sub.add_parser("miner", help="mine blocks using a remote node block template")
    p.add_argument("--node", default="http://127.0.0.1:18444", help="node URL")
    p.add_argument("--wallet", help="payout wallet file")
    p.add_argument("--address", help="payout address")
    p.add_argument("--address-type", default="p2pkh", choices=["p2pkh", "p2wpkh", "p2tr", "p2sh-segwit"])
    p.add_argument("--passphrase")
    p.add_argument("--blocks", type=int, default=1)
    p.add_argument("--save-blocks", help="optional directory for solved block JSON files")
    p.add_argument("--sync-after", action="store_true", help="ask the node to sync after each submission")
    p.set_defaults(func=cmd_miner)

    p = sub.add_parser("rawtx", help="export a transaction in Bitcoin-style raw hex")
    p.add_argument("txid")
    p.add_argument("--no-witness", action="store_true")
    p.add_argument("--decode", action="store_true")
    p.set_defaults(func=cmd_rawtx)

    p = sub.add_parser("rawblock", help="export a block in Bitcoin-style raw hex")
    p.add_argument("block_hash", nargs="?", default="tip")
    p.add_argument("--no-witness", action="store_true")
    p.set_defaults(func=cmd_rawblock)

    p = sub.add_parser("decode-rawtx", help="decode Bitcoin-style raw transaction hex")
    p.add_argument("raw_hex")
    p.set_defaults(func=cmd_decode_rawtx)

    p = sub.add_parser("script", help="show the scriptPubKey for an address")
    p.add_argument("address")
    p.set_defaults(func=cmd_script)

    p = sub.add_parser("validate", help="validate the whole local chain")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("reindex", help="rebuild indexes and the UTXO set from block data (recovers a corrupt chain file)")
    p.set_defaults(func=cmd_reindex)

    p = sub.add_parser("hd-derive", help="derive an HD (BIP32) key + NetCoin addresses from a mnemonic at a path")
    p.add_argument("--mnemonic", required=True, help="seed phrase")
    p.add_argument("--passphrase", help="optional BIP39 passphrase")
    p.add_argument("--path", default="m/44'/0'/0'/0/0", help="derivation path (default m/44'/0'/0'/0/0)")
    p.set_defaults(func=cmd_hd_derive)

    p = sub.add_parser("taproot-tree", help="build a Taproot script-tree (BIP341) address + control blocks")
    p.add_argument("--wallet", help="use this wallet's key as the internal key")
    p.add_argument("--internal", help="internal x-only pubkey hex (instead of --wallet)")
    p.add_argument("--passphrase", help="wallet passphrase if encrypted")
    p.add_argument("--script", action="append", help="a leaf script (repeatable)")
    p.set_defaults(func=cmd_taproot_tree)

    p = sub.add_parser("payment-uri", help="build or decode a netcoin: payment URI (BIP21-style)")
    p.add_argument("--address", help="address to request payment to")
    p.add_argument("--amount", help="requested amount in NET")
    p.add_argument("--label", help="payee label")
    p.add_argument("--message", help="payment message")
    p.add_argument("--decode", help="decode an existing netcoin: URI instead of building one")
    p.set_defaults(func=cmd_payment_uri)

    p = sub.add_parser("signmessage", help="sign a message with a wallet key (proves address control)")
    p.add_argument("--wallet", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--passphrase", help="wallet passphrase if encrypted")
    p.set_defaults(func=cmd_signmessage)

    p = sub.add_parser("verifymessage", help="verify a signed message against an address")
    p.add_argument("--address", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--signature", required=True)
    p.set_defaults(func=cmd_verifymessage)

    p = sub.add_parser("hd-address", help="watch-only: derive a receive address from an account xpub (no private key)")
    p.add_argument("--xpub", required=True, help="account extended public key")
    p.add_argument("--change", type=int, default=0, help="change branch (0=receive, 1=change)")
    p.add_argument("--index", type=int, default=0, help="address index")
    p.set_defaults(func=cmd_hd_address)

    p = sub.add_parser("blockfilter", help="compute or fetch a block's BIP158-style compact filter")
    p.add_argument("--node", help="fetch the filter from a node instead of the local chain")
    p.add_argument("--height", type=int, help="block height (default: tip)")
    p.add_argument("--block", help="block hash (overrides --height)")
    p.set_defaults(func=cmd_blockfilter)

    p = sub.add_parser("scan-filters", help="light-client scan: download compact filters and flag only matching blocks")
    p.add_argument("--node", required=True, help="node serving /cfilter and /headers")
    p.add_argument("--wallet", help="scan all of a wallet's address types")
    p.add_argument("--address", help="scan a single address")
    p.add_argument("--passphrase", help="wallet passphrase if encrypted")
    p.add_argument("--start", type=int, default=0, help="start height (default 0)")
    p.add_argument("--end", type=int, default=None, help="end height (default: tip)")
    p.set_defaults(func=cmd_scan_filters)

    p = sub.add_parser("export", help="export chain JSON")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("import", help="import a better-work chain from a JSON file")
    p.add_argument("file")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("node", help="run an HTTP peer node")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=DEFAULT_NODE_PORT)
    p.add_argument("--peer", action="append", help="peer URL; can be repeated")
    p.add_argument("--seeds", action="store_true", help="also connect to the built-in public testnet seeds")
    p.add_argument("--advertise", help="public URL to announce to peers for gossip discovery")
    p.add_argument("--config", help="path to a netcoin.conf (JSON or key=value)")
    p.add_argument("--sync-interval", type=int, default=0, help="background peer discovery/sync interval in seconds; 0 disables")
    p.add_argument("--rate-limit-per-min", type=int, default=240, help="per-IP/per-path HTTP request limit; 0 disables")
    p.set_defaults(func=cmd_node)

    p = sub.add_parser("rpc", help="run JSON-RPC server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=DEFAULT_RPC_PORT)
    p.add_argument("--rpc-token", help="require this bearer token (else NETCOIN_RPC_TOKEN env var)")
    p.set_defaults(func=cmd_rpc)

    p = sub.add_parser("rpc-call", help="call a NetCoin JSON-RPC server")
    p.add_argument("method")
    p.add_argument("--params", help="JSON list of params, e.g. '[true]'")
    p.add_argument("--url", default=f"http://127.0.0.1:{DEFAULT_RPC_PORT}")
    p.set_defaults(func=cmd_rpc_call)

    p = sub.add_parser("pool", help="run educational mining-pool server")
    p.add_argument("--wallet")
    p.add_argument("--address")
    p.add_argument("--address-type", default="p2pkh", choices=["p2pkh", "p2wpkh", "p2tr", "p2sh-segwit"])
    p.add_argument("--passphrase")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=DEFAULT_POOL_PORT)
    p.set_defaults(func=cmd_pool)

    p = sub.add_parser("explorer", help="generate a static HTML block explorer")
    p.add_argument("--out", default="explorer")
    p.set_defaults(func=cmd_explorer)

    p = sub.add_parser("explorer-server", help="run API-backed explorer web service")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--rate-limit-per-min", type=int, default=240, help="per-IP/per-path request limit; 0 disables")
    p.set_defaults(func=cmd_explorer_server)

    p = sub.add_parser("web", help="local web wallet + faucet + explorer page (open in a browser)")
    p.add_argument("--node", default="http://seed1.netcoin.online:28444", help="NetCoin node to query/broadcast through")
    p.add_argument("--faucet", default="http://18.220.89.128/faucet", help="faucet URL to link to (set empty to hide)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8088)
    p.set_defaults(func=cmd_web)

    p = sub.add_parser("networks", help="show main/testnet/signet/regtest profiles")
    p.set_defaults(func=cmd_networks)

    p = sub.add_parser("p2p-message", help="create or parse a Bitcoin-style P2P envelope")
    p.add_argument("--height", type=int, default=0)
    p.add_argument("--parse", help="parse message hex instead of creating a version message")
    p.set_defaults(func=cmd_p2p_message)

    p = sub.add_parser("p2p-server", help="run experimental TCP P2P message server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=DEFAULT_P2P_PORT)
    p.set_defaults(func=cmd_p2p_server)

    p = sub.add_parser("p2p-call", help="send one TCP P2P message and print the response")
    p.add_argument("command", choices=["version", "ping", "getheaders"])
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=DEFAULT_P2P_PORT)
    p.add_argument("--timeout", type=int, default=10)
    p.add_argument("--height", type=int, default=0, help="start height for version")
    p.add_argument("--genesis-hash", default="", help="genesis hash for version")
    p.add_argument("--nonce", type=int, default=1, help="nonce for ping")
    p.add_argument("--locator", default="0" * 64, help="locator hash for getheaders")
    p.set_defaults(func=cmd_p2p_call)

    p = sub.add_parser("soak", help="run a local multi-node relay/sync soak test")
    p.add_argument("--nodes", type=int, default=3, help="number of local HTTP nodes")
    p.add_argument("--rounds", type=int, default=3, help="relay/mine/sync rounds after bootstrap")
    p.add_argument("--transactions-per-round", type=int, default=1)
    p.add_argument("--bootstrap-blocks", type=int, default=101, help="initial blocks mined before spending")
    p.add_argument("--amount", default="1")
    p.add_argument("--fee", default="0.01")
    p.add_argument("--dir", help="optional directory for soak node data; default uses a temp dir")
    p.set_defaults(func=cmd_soak)

    p = sub.add_parser("fuzz", help="run deterministic parser/endpoint fuzz smoke tests")
    p.add_argument("--target", default="all", choices=["all", "tx-dict", "block-dict", "rawtx", "script", "node-http"])
    p.add_argument("--iterations", type=int, default=500)
    p.add_argument("--seed", type=int, default=1234567)
    p.add_argument("--max-bytes", type=int, default=256)
    p.set_defaults(func=cmd_fuzz)

    p = sub.add_parser("psbt-sign", help="sign a NetCoin PSBT-like base64 file")
    p.add_argument("--wallet", required=True)
    p.add_argument("--passphrase")
    p.add_argument("--psbt", required=True)
    p.add_argument("--out")
    p.set_defaults(func=cmd_psbt_sign)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except (ChainError, WalletError, Exception) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
