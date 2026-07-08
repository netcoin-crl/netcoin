"""Blockchain state, consensus validation, mining, mempool policy, and persistence."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from .block import (
    Block,
    BlockError,
    BlockHeader,
    bits_to_target,
    check_proof_of_work,
    cumulative_work,
    make_block,
    merkle_root,
    target_to_bits,
    validate_witness_commitment,
    witness_commitment,
)
from .consensus import (
    chainstate_commitment as build_chainstate_commitment,
)
from .consensus import (
    check_header_checkpoint,
    consensus_rules_at_height,
    validate_block_weight_limit,
    validate_median_time_past,
)
from .crypto import validate_address
from .emission import emission_subsidy, is_active, is_legacy_random_window, legacy_random_emission_subsidy
from .params import (
    COINBASE_MATURITY,
    DEFAULT_DATA_DIR,
    DIFFICULTY_ADJUSTMENT_INTERVAL,
    DUST_THRESHOLD,
    GENESIS_MESSAGE,
    GENESIS_TIMESTAMP,
    INCREMENTAL_RELAY_FEE,
    INITIAL_BITS,
    INITIAL_SUBSIDY,
    LOCKTIME_THRESHOLD,
    MAX_BLOCK_WEIGHT,
    MAX_MEMPOOL_ANCESTORS,
    MAX_MEMPOOL_BYTES,
    MAX_MEMPOOL_TRANSACTIONS,
    MAX_MONEY,
    MAX_STANDARD_TX_INPUTS,
    MAX_STANDARD_TX_WEIGHT,
    MEMPOOL_EXPIRY_SECONDS,
    MIN_RELAY_FEE_PER_KB,
    POW_LIMIT_BITS,
    ZERO_HASH,
    min_difficulty_gap_at,
    target_timespan_at,
)
from .serialization import transaction_vsize, transaction_weight
from .tx import (
    SpendableOutput,
    Transaction,
    TransactionError,
    TxInput,
    TxOutput,
    create_coinbase_transaction,
    ensure_unique_inputs,
    sats_to_amount,
)


class ChainError(ValueError):
    """Raised when chain state or consensus validation fails."""


class Blockchain:
    """A small Bitcoin-like blockchain database.

    The class stores blocks and mempool transactions as JSON files under a data
    directory. It validates proof-of-work, UTXO spends, signatures, coinbase
    rewards, reward reductions, coinbase maturity, difficulty retargeting, block weight,
    and a small set of mempool policy rules.
    """

    def __init__(
        self,
        data_dir: str | os.PathLike[str] = DEFAULT_DATA_DIR,
        autosave: bool = True,
        backend: str | None = None,
        genesis_allocation: dict[str, int] | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.autosave = autosave
        # Optional premine baked into the genesis (used by a relaunch to carry
        # balances forward from a snapshot). None => the standard empty genesis.
        self._genesis_allocation = genesis_allocation
        # Persistence backend: "sqlite" (default) or "json". Falls back to the
        # NETCOIN_BACKEND env var so it threads through the whole CLI uniformly.
        # JSON remains available for demos/export with backend="json" or NETCOIN_BACKEND=json.
        self.backend = (backend or os.environ.get("NETCOIN_BACKEND") or "sqlite").lower()
        self.store = None
        if self.backend == "sqlite":
            from .storage import SqliteChainStore

            self.store = SqliteChainStore(self.data_dir / "netcoin.sqlite")
        elif self.backend != "json":
            raise ChainError(f"unknown storage backend: {self.backend}")
        self.chain: list[Block] = []
        self.mempool: list[Transaction] = []
        self.mempool_times: dict[str, float] = {}
        self.orphan_blocks: dict[str, Block] = {}
        # Fast-lookup indexes (rebuilt from self.chain; O(1) block/tx lookup).
        self.block_index: dict[str, Block] = {}
        self.tx_index: dict[str, dict[str, Any]] = {}
        self.address_index: dict[str, set] = {}
        self._utxo_addr: dict[str, str] = {}  # outpoint -> address, for the address index
        self._utxos: dict[str, SpendableOutput] = {}  # persistent authoritative UTXO set
        # Per-address UTXO index (address -> {outpoint -> SpendableOutput}) so
        # balance/utxos lookups are O(coins-at-address) instead of scanning the
        # whole UTXO set on every call. Mirrors self._utxos exactly; maintained
        # at the three mutation points (reindex, snapshot load, block connect)
        # and asserted consistent in self_check().
        self._utxos_by_addr: dict[str, dict[str, SpendableOutput]] = {}
        self.pruned = False  # True when running from a pruned store (no old block bodies)
        self.pruned_below = 0
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.load_or_create()

    def _index_block(self, block: Block) -> None:
        self.block_index[block.hash()] = block
        for position, tx in enumerate(block.transactions):
            txid = tx.txid()
            self.tx_index[txid] = {
                "block_hash": block.hash(),
                "height": block.header.height,
                "position": position,
            }
            # Address index: a tx touches an address if it pays to it or spends
            # one of its outputs.
            if not tx.is_coinbase:
                for txin in tx.inputs:
                    spent_addr = self._utxo_addr.get(txin.outpoint())
                    if spent_addr:
                        self.address_index.setdefault(spent_addr, set()).add(txid)
            for index, output in enumerate(tx.outputs):
                if output.address:
                    self.address_index.setdefault(output.address, set()).add(txid)
                    self._utxo_addr[f"{txid}:{index}"] = output.address
            if not tx.is_coinbase:
                for txin in tx.inputs:
                    self._utxo_addr.pop(txin.outpoint(), None)

    def _reindex_indexes_only(self) -> None:
        self.block_index = {}
        self.tx_index = {}
        self.address_index = {}
        self._utxo_addr = {}
        for block in self.chain:
            self._index_block(block)

    def reindex(self) -> None:
        """Rebuild the block, transaction, address, and UTXO indexes from the chain."""
        self._reindex_indexes_only()
        # A pruned node's UTXO set comes from its snapshot, not a full rescan.
        if not self.pruned:
            self._utxos = self._recompute_utxos_from_chain()
            self._rebuild_utxo_addr_index()

    def _load_utxos_from_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._utxos = {}
        for item in snapshot.get("utxos", []):
            spendable = SpendableOutput.from_dict(item)
            self._utxos[spendable.outpoint()] = spendable
        self._rebuild_utxo_addr_index()

    def address_summary(self, address: str) -> dict[str, Any]:
        if not validate_address(address):
            raise ChainError("address is not a valid NetCoin address")
        balances = self.balances_for_address(address)
        utxos = self.utxos_for_address(address, include_immature=True)
        txids = sorted(self.address_index.get(address, set()))
        return {
            "address": address,
            "balance": balances,
            "balance_net": {
                "total": sats_to_amount(balances["total"]),
                "spendable": sats_to_amount(balances["spendable"]),
                "immature": sats_to_amount(balances["immature"]),
            },
            "utxo_count": len(utxos),
            "transaction_count": len(txids),
            "transaction_ids": txids,
        }

    def address_balance_summary(self, address: str) -> dict[str, Any]:
        if not validate_address(address):
            raise ChainError("address is not a valid NetCoin address")
        balances = self.balances_for_address(address)
        utxos = self.utxos_for_address(address, include_immature=True)
        txids = sorted(self.address_index.get(address, set()))
        spend_height = self.height() + 1
        maturing = [
            COINBASE_MATURITY - (spend_height - utxo.height)
            for utxo in utxos
            if utxo.coinbase and spend_height - utxo.height < COINBASE_MATURITY
        ]
        return {
            "address": address,
            "height": self.height(),
            "tip_hash": self.tip_hash(),
            "total_sats": balances["total"],
            "spendable_sats": balances["spendable"],
            "immature_sats": balances["immature"],
            "total": sats_to_amount(balances["total"]),
            "spendable": sats_to_amount(balances["spendable"]),
            "immature": sats_to_amount(balances["immature"]),
            "immature_next_mature_in_blocks": min(maturing) if maturing else 0,
            "immature_all_mature_in_blocks": max(maturing) if maturing else 0,
            "utxo_count": len(utxos),
            "transaction_count": len(txids),
        }

    def supply_summary(self) -> dict[str, Any]:
        total_minted_sats = 0
        for block in self.chain:
            if block.transactions:
                total_minted_sats += block.transactions[0].total_output()
        tip_coinbase_sats = self.tip().transactions[0].total_output() if self.tip().transactions else 0
        next_height = self.height() + 1
        next_subsidy_sats = self.subsidy(next_height)
        return {
            "height": self.height(),
            "tip_hash": self.tip_hash(),
            "total_minted_sats": total_minted_sats,
            "total_minted": sats_to_amount(total_minted_sats),
            "tip_coinbase_sats": tip_coinbase_sats,
            "tip_coinbase": sats_to_amount(tip_coinbase_sats),
            "next_height": next_height,
            "next_subsidy_sats": next_subsidy_sats,
            "next_subsidy": sats_to_amount(next_subsidy_sats),
        }

    @property
    def chain_path(self) -> Path:
        return self.data_dir / "chain.json"

    @property
    def mempool_path(self) -> Path:
        return self.data_dir / "mempool.json"

    def height(self) -> int:
        return self.chain[-1].header.height

    def tip(self) -> Block:
        return self.chain[-1]

    def tip_hash(self) -> str:
        return self.tip().hash()

    def load_or_create(self) -> None:
        if self.store is not None and self.store.is_pruned():
            # Pruned reload: trust the stored UTXO snapshot and the kept recent
            # blocks; do not revalidate from genesis (old bodies are gone).
            self.pruned = True
            self.pruned_below = self.store.pruned_below()
            self.chain = [Block.from_dict(item) for item in self.store.load_chain()]
            if not self.chain:
                raise ChainError("pruned store has no retained blocks")
            snapshot = self.store.load_utxo_snapshot()
            if snapshot is None:
                raise ChainError("pruned store is missing its UTXO snapshot")
            self._load_utxos_from_snapshot(snapshot)
            self._reindex_indexes_only()
            self.mempool = [Transaction.from_dict(item) for item in self.store.load_mempool()]
            return
        if self.store is not None:
            if self.store.has_chain():
                self.chain = [Block.from_dict(item) for item in self.store.load_chain()]
                self.assert_valid_chain(self.chain)
            else:
                self.chain = [create_genesis_block(self._genesis_allocation)]
                self.save_chain()
        elif self._chain_files_exist():
            self.chain = self._load_chain_with_recovery()
        else:
            self.chain = [create_genesis_block(self._genesis_allocation)]
            self.save_chain()
        self.reindex()

        loaded_mempool: list | None = None
        if self.store is not None:
            loaded_mempool = [Transaction.from_dict(item) for item in self.store.load_mempool()]
        elif self.mempool_path.exists():
            try:
                data = json.loads(self.mempool_path.read_text())
                loaded_mempool = [Transaction.from_dict(item) for item in data.get("transactions", [])]
            except (ValueError, OSError, KeyError, TypeError):
                # The mempool is ephemeral and non-consensus: a corrupt file is
                # never worth refusing to start over. Drop it and continue empty.
                loaded_mempool = []

        if loaded_mempool is not None:
            self.mempool = []
            for tx in loaded_mempool:
                try:
                    self.add_mempool_transaction(tx, save=False)
                except (ChainError, TransactionError):
                    continue
            self.evict_expired_mempool(MEMPOOL_EXPIRY_SECONDS, save=False)
            if self.autosave:
                self.save_mempool()
        else:
            self.mempool = []
            self.save_mempool()

    def _atomic_write_json(self, path: Path, payload: dict[str, Any]) -> None:
        """Crash-safe JSON write.

        Write to a temp file and fsync it, keep the previous good file as a
        ``.bak`` copy, then atomically ``os.replace`` it into place and fsync the
        directory. A crash at any point leaves either the old file, the new file,
        or a recoverable ``.tmp``/``.bak`` — never a half-written live file.
        """
        text = json.dumps(payload, indent=2, sort_keys=True)
        tmp = path.parent / (path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass  # directory fsync is best-effort (not supported everywhere)
        # Mirror the just-written good file as a backup. Copying *after* the
        # replace keeps .bak at the latest committed state, so recovery from a
        # corrupt live file does not lose the most recent write.
        try:
            (path.parent / (path.name + ".bak")).write_bytes(path.read_bytes())
        except OSError:
            pass  # a missing backup is not fatal; the live file is already committed

    def save_chain(self) -> None:
        if not self.autosave:
            return
        if self.store is not None:
            self.store.save_chain(self.chain)
            return
        self._atomic_write_json(self.chain_path, {"blocks": [block.to_dict() for block in self.chain]})

    def save_mempool(self) -> None:
        if not self.autosave:
            return
        if self.store is not None:
            self.store.save_mempool(self.mempool)
            return
        payload = {"transactions": [tx.to_dict(include_scripts=True, include_witness=True) for tx in self.mempool]}
        self._atomic_write_json(self.mempool_path, payload)

    def _chain_files_exist(self) -> bool:
        """True if a live chain file or any recoverable copy is present."""
        return any(
            (self.chain_path.parent / (self.chain_path.name + suffix)).exists() for suffix in ("", ".bak", ".tmp")
        )

    def _load_chain_with_recovery(self) -> list[Block]:
        """Load the chain, tolerating a corrupt live file.

        Tries the live ``chain.json`` first, then the ``.bak`` backup, then a
        leftover ``.tmp`` from an interrupted write. The first copy that both
        parses and passes full chain validation wins; if recovery used a backup
        copy, the canonical file is rewritten so the node heals itself on start.
        """
        candidates = [
            self.chain_path,
            self.chain_path.parent / (self.chain_path.name + ".bak"),
            self.chain_path.parent / (self.chain_path.name + ".tmp"),
        ]
        errors: list[str] = []
        for source in candidates:
            if not source.exists():
                continue
            try:
                data = json.loads(source.read_text())
                candidate = [Block.from_dict(item) for item in data["blocks"]]
                self.assert_valid_chain(candidate)
            except (ValueError, KeyError, TypeError, BlockError, ChainError, OSError) as exc:
                errors.append(f"{source.name}: {exc}")
                continue
            self.chain = candidate
            if source != self.chain_path:
                # Recovered from a backup/temp copy — restore the canonical file.
                self.save_chain()
            return candidate
        raise ChainError("chain data is corrupt or unreadable (" + "; ".join(errors) + ")")

    def save(self) -> None:
        self.save_chain()
        self.save_mempool()

    # ------------------------------------------------------------------
    # Consensus rules
    # ------------------------------------------------------------------

    def subsidy(self, height: int, chain_prefix: Sequence[Block] | None = None) -> int:
        if height < 0:
            raise ChainError("height cannot be negative")
        # Deterministic 10% reward-reduction schedule. A legacy random-emission
        # compatibility window is preserved for already-mined public-testnet
        # blocks before the new schedule activates. During full-chain validation
        # use the candidate prefix rather than self.chain, because self.chain may
        # not be populated yet while loading from disk.
        if is_active(height):
            return emission_subsidy(height)
        if is_legacy_random_window(height):
            source = chain_prefix if chain_prefix is not None else self.chain
            return legacy_random_emission_subsidy(height, lambda h: source[h].hash())
        return INITIAL_SUBSIDY

    def expected_bits_for_height(self, height: int, chain_prefix: Sequence[Block] | None = None) -> int:
        if height == 0:
            return INITIAL_BITS
        prefix = list(chain_prefix) if chain_prefix is not None else self.chain
        if not prefix:
            return INITIAL_BITS
        previous_bits = prefix[-1].header.bits
        if height % DIFFICULTY_ADJUSTMENT_INTERVAL != 0:
            return previous_bits
        if len(prefix) < DIFFICULTY_ADJUSTMENT_INTERVAL:
            return previous_bits

        first = prefix[-DIFFICULTY_ADJUSTMENT_INTERVAL]
        last = prefix[-1]
        actual_timespan = last.header.timestamp - first.header.timestamp
        target_timespan = target_timespan_at(height)  # spacing v2 after activation
        min_timespan = target_timespan // 4
        max_timespan = target_timespan * 4
        actual_timespan = max(min_timespan, min(actual_timespan, max_timespan))
        old_target = bits_to_target(previous_bits)
        new_target = old_target * actual_timespan // target_timespan
        return target_to_bits(new_target)

    def _bits_acceptable(self, height: int, prefix: Sequence[Block] | None, bits: int, timestamp: int) -> bool:
        """A block must use the normal retarget difficulty, UNLESS it is mined more
        than min_difficulty_gap_at(height) seconds after its parent (the testnet lone-miner
        rule), in which case it may instead use the PoW floor so the chain can't
        get stuck when hashpower drops."""
        if bits == self.expected_bits_for_height(height, prefix):
            return True
        chain_prefix = list(prefix) if prefix is not None else self.chain
        if chain_prefix and bits == POW_LIMIT_BITS:
            if timestamp > chain_prefix[-1].header.timestamp + min_difficulty_gap_at(height):
                return True
        return False

    def _recompute_utxos_from_chain(self) -> dict[str, SpendableOutput]:
        """Authoritative full-scan UTXO computation (source of truth for rebuilds
        and integrity checks). The persistent `self._utxos` cache mirrors this."""
        utxos: dict[str, SpendableOutput] = {}
        for block in self.chain:
            self._apply_block_to_utxos(block, utxos)
        return utxos

    def _rebuild_utxo_addr_index(self) -> None:
        """Recompute the per-address UTXO index from the authoritative set.
        Called after any wholesale rebuild of self._utxos."""
        index: dict[str, dict[str, SpendableOutput]] = {}
        for outpoint, spendable in self._utxos.items():
            index.setdefault(spendable.output.address, {})[outpoint] = spendable
        self._utxos_by_addr = index

    def _apply_block_to_persistent_utxos(self, block: Block) -> None:
        """Connect a block to the authoritative UTXO set AND keep the per-address
        index in lockstep. Use this (not the bare _apply_block_to_utxos) for the
        real persistent set so lookups stay correct."""
        for tx in block.transactions:
            if not tx.is_coinbase:
                for txin in tx.inputs:
                    op = txin.outpoint()
                    spent = self._utxos.pop(op, None)
                    if spent is not None:
                        bucket = self._utxos_by_addr.get(spent.output.address)
                        if bucket is not None:
                            bucket.pop(op, None)
                            if not bucket:
                                self._utxos_by_addr.pop(spent.output.address, None)
            txid = tx.txid()
            for index, output in enumerate(tx.outputs):
                if output.amount > 0:
                    op = f"{txid}:{index}"
                    spendable = SpendableOutput(
                        txid=txid,
                        vout=index,
                        output=output,
                        height=block.header.height,
                        coinbase=tx.is_coinbase,
                    )
                    self._utxos[op] = spendable
                    self._utxos_by_addr.setdefault(output.address, {})[op] = spendable

    def _apply_block_to_utxos(self, block: Block, utxos: dict[str, SpendableOutput]) -> None:
        for tx in block.transactions:
            if not tx.is_coinbase:
                for txin in tx.inputs:
                    utxos.pop(txin.outpoint(), None)
            txid = tx.txid()
            for index, output in enumerate(tx.outputs):
                if output.amount > 0:
                    utxos[f"{txid}:{index}"] = SpendableOutput(
                        txid=txid,
                        vout=index,
                        output=output,
                        height=block.header.height,
                        coinbase=tx.is_coinbase,
                    )

    def utxo_set(self, include_mempool: bool = False) -> dict[str, SpendableOutput]:
        # Serve a copy of the persistent UTXO cache so callers can mutate freely.
        utxos = dict(self._utxos)
        if include_mempool:
            height = self.height() + 1
            for tx in self.mempool:
                self.validate_regular_transaction(tx, utxos, height)
                self.apply_regular_transaction(tx, utxos, height)
        return utxos

    def utxos_for_address(self, address: str, *, include_immature: bool = False) -> list[SpendableOutput]:
        if not validate_address(address):
            raise ChainError("address is not a valid NetCoin address")
        spend_height = self.height() + 1
        result = []
        # O(coins-at-address) via the per-address index instead of scanning the
        # whole UTXO set. Semantics identical to iterating utxo_set() (confirmed
        # set only; mempool-spend filtering happens at the node layer).
        for utxo in self._utxos_by_addr.get(address, {}).values():
            if utxo.coinbase and not include_immature and spend_height - utxo.height < COINBASE_MATURITY:
                continue
            result.append(utxo)
        result.sort(key=lambda item: (item.height, item.txid, item.vout))
        return result

    def balances_for_address(self, address: str) -> dict[str, int]:
        if not validate_address(address):
            raise ChainError("address is not a valid NetCoin address")
        total = 0
        spendable = 0
        immature = 0
        spend_height = self.height() + 1
        for utxo in self._utxos_by_addr.get(address, {}).values():
            total += utxo.output.amount
            if utxo.coinbase and spend_height - utxo.height < COINBASE_MATURITY:
                immature += utxo.output.amount
            else:
                spendable += utxo.output.amount
        return {"total": total, "spendable": spendable, "immature": immature}

    def check_locktime(self, tx: Transaction, spend_height: int) -> None:
        if tx.locktime == 0:
            return
        if all(txin.sequence == 0xFFFFFFFF for txin in tx.inputs):
            return
        if tx.locktime < LOCKTIME_THRESHOLD:
            if tx.locktime > spend_height:
                raise ChainError("transaction locktime is above current block height")
        else:
            if tx.locktime > int(time.time()):
                raise ChainError("transaction locktime is in the future")

    def validate_regular_transaction(
        self, tx: Transaction, utxos: dict[str, SpendableOutput], spend_height: int
    ) -> int:
        if tx.is_coinbase:
            raise ChainError("coinbase transactions cannot appear outside block position 0")
        if not tx.outputs:
            raise ChainError("regular transaction must have at least one output")
        ensure_unique_inputs(tx.inputs)
        self.check_locktime(tx, spend_height)
        output_total = tx.total_output()
        if output_total <= 0:
            raise ChainError("regular transaction output total must be positive")
        if output_total > MAX_MONEY:
            raise ChainError("transaction output total exceeds MAX_MONEY")

        input_total = 0
        for index, txin in enumerate(tx.inputs):
            prevout = utxos.get(txin.outpoint())
            if prevout is None:
                raise ChainError(f"missing or already-spent UTXO: {txin.outpoint()}")
            if prevout.coinbase and spend_height - prevout.height < COINBASE_MATURITY:
                raise ChainError("transaction tries to spend an immature coinbase output")
            if not tx.verify_input(index, prevout):
                raise ChainError("transaction signature verification failed")
            input_total += prevout.output.amount
            if input_total > MAX_MONEY:
                raise ChainError("transaction input total exceeds MAX_MONEY")

        if input_total < output_total:
            raise ChainError("transaction spends more than its inputs")
        return input_total - output_total

    def apply_regular_transaction(self, tx: Transaction, utxos: dict[str, SpendableOutput], spend_height: int) -> None:
        for txin in tx.inputs:
            del utxos[txin.outpoint()]
        txid = tx.txid()
        for index, output in enumerate(tx.outputs):
            if output.amount > 0:
                utxos[f"{txid}:{index}"] = SpendableOutput(
                    txid=txid,
                    vout=index,
                    output=output,
                    height=spend_height,
                    coinbase=False,
                )

    def validate_coinbase_transaction(self, tx: Transaction, height: int, max_reward: int) -> None:
        if not tx.is_coinbase:
            raise ChainError("first transaction in a block must be coinbase")
        output_total = tx.total_output()
        if output_total < 0 or output_total > MAX_MONEY:
            raise ChainError("coinbase output total is outside money range")
        if output_total > max_reward:
            raise ChainError("coinbase pays more than subsidy plus fees")
        if height > 0 and output_total == 0:
            raise ChainError("non-genesis coinbase must pay a positive amount")

    def apply_coinbase_transaction(self, tx: Transaction, utxos: dict[str, SpendableOutput], height: int) -> None:
        txid = tx.txid()
        for index, output in enumerate(tx.outputs):
            if output.amount > 0:
                utxos[f"{txid}:{index}"] = SpendableOutput(
                    txid=txid,
                    vout=index,
                    output=output,
                    height=height,
                    coinbase=True,
                )

    def validate_block_against(
        self,
        block: Block,
        previous: Block,
        utxos: dict[str, SpendableOutput],
        chain_prefix: Sequence[Block],
    ) -> dict[str, SpendableOutput]:
        expected_height = previous.header.height + 1
        if block.header.height != expected_height:
            raise ChainError("block height does not extend the previous block")
        if block.header.previous_hash != previous.hash():
            raise ChainError("block previous hash does not match chain tip")
        if not check_header_checkpoint(block):
            raise ChainError("block hash does not match the activated header checkpoint")
        if not validate_median_time_past(block, chain_prefix):
            raise ChainError("block timestamp is not greater than median-time-past")
        if not self._bits_acceptable(block.header.height, chain_prefix, block.header.bits, block.header.timestamp):
            raise ChainError("block bits do not match expected difficulty target")
        if block.header.merkle_root != merkle_root(block.transactions):
            raise ChainError("block merkle root does not match its transactions")
        if not validate_witness_commitment(block):
            raise ChainError("block witness commitment is missing or invalid")
        if not check_proof_of_work(block.header):
            raise ChainError("block proof of work is invalid")
        if block.header.timestamp > int(time.time()) + 2 * 60 * 60:
            raise ChainError("block timestamp is too far in the future")
        if not validate_block_weight_limit(block):
            raise ChainError("block exceeds maximum weight")
        if not block.transactions[0].is_coinbase:
            raise ChainError("block is missing a coinbase transaction")
        if any(tx.is_coinbase for tx in block.transactions[1:]):
            raise ChainError("block contains more than one coinbase transaction")

        seen_txids = set()
        temp_utxos = dict(utxos)
        fees = 0
        for tx in block.transactions[1:]:
            txid = tx.txid()
            if txid in seen_txids:
                raise ChainError("block contains a duplicate transaction id")
            seen_txids.add(txid)
            fee = self.validate_regular_transaction(tx, temp_utxos, block.header.height)
            fees += fee
            if fees > MAX_MONEY:
                raise ChainError("block fees exceed MAX_MONEY")
            self.apply_regular_transaction(tx, temp_utxos, block.header.height)

        max_reward = self.subsidy(block.header.height, chain_prefix) + fees
        self.validate_coinbase_transaction(block.transactions[0], block.header.height, max_reward)
        coinbase_txid = block.transactions[0].txid()
        if coinbase_txid in seen_txids:
            raise ChainError("coinbase transaction id duplicates another transaction")
        self.apply_coinbase_transaction(block.transactions[0], temp_utxos, block.header.height)
        return temp_utxos

    def assert_valid_chain(self, blocks: Sequence[Block]) -> None:
        if not blocks:
            raise ChainError("chain is empty")
        genesis = create_genesis_block(self._genesis_allocation)
        if blocks[0].hash() != genesis.hash():
            raise ChainError("genesis block does not match NetCoin genesis")
        if blocks[0].header.height != 0:
            raise ChainError("genesis block height must be 0")
        if blocks[0].header.previous_hash != ZERO_HASH:
            raise ChainError("genesis previous hash must be zero")
        if blocks[0].header.merkle_root != merkle_root(blocks[0].transactions):
            raise ChainError("genesis merkle root is invalid")
        if not check_proof_of_work(blocks[0].header):
            raise ChainError("genesis proof of work is invalid")

        utxos: dict[str, SpendableOutput] = {}
        self.apply_coinbase_transaction(blocks[0].transactions[0], utxos, 0)
        prefix = [blocks[0]]
        for block in blocks[1:]:
            utxos = self.validate_block_against(block, prefix[-1], utxos, prefix)
            prefix.append(block)

    def is_valid_chain(self, blocks: Sequence[Block]) -> bool:
        try:
            self.assert_valid_chain(blocks)
            return True
        except (ChainError, TransactionError, BlockError):
            return False

    # ------------------------------------------------------------------
    # Mempool policy
    # ------------------------------------------------------------------

    def calculate_fee(
        self, tx: Transaction, utxos: dict[str, SpendableOutput] | None = None, spend_height: int | None = None
    ) -> int:
        temp_utxos = self.utxo_set() if utxos is None else dict(utxos)
        return self.validate_regular_transaction(tx, temp_utxos, spend_height or self.height() + 1)

    def fee_rate(self, tx: Transaction, fee: int | None = None) -> int:
        fee_value = self.calculate_fee(tx) if fee is None else int(fee)
        vsize = max(1, transaction_vsize(tx))
        return fee_value * 1000 // vsize

    def check_standard_transaction(self, tx: Transaction, fee: int) -> None:
        self.check_standard_transaction_shape(tx)
        min_fee = (transaction_vsize(tx) * MIN_RELAY_FEE_PER_KB + 999) // 1000
        if fee < min_fee:
            raise ChainError("transaction fee is below min relay fee")

    def check_standard_transaction_shape(self, tx: Transaction) -> None:
        """Check non-fee standardness shared by single-tx and package relay policy."""
        if len(tx.inputs) > MAX_STANDARD_TX_INPUTS:
            raise ChainError(f"non-standard transaction: too many inputs ({len(tx.inputs)} > {MAX_STANDARD_TX_INPUTS})")
        if transaction_weight(tx) > MAX_STANDARD_TX_WEIGHT:
            raise ChainError("non-standard transaction: weight too high")
        for output in tx.outputs:
            if 0 < output.amount < DUST_THRESHOLD:
                raise ChainError("transaction creates dust output")

    def mempool_conflicts(self, tx: Transaction) -> list[Transaction]:
        spent = {txin.outpoint() for txin in tx.inputs}
        conflicts = []
        for existing in self.mempool:
            if spent.intersection({txin.outpoint() for txin in existing.inputs}):
                conflicts.append(existing)
        return conflicts

    def add_mempool_transaction(self, tx: Transaction, *, save: bool = True) -> str:
        txid = tx.txid()
        if tx.is_coinbase:
            raise ChainError("cannot add coinbase transaction to mempool")
        if any(existing.txid() == txid for existing in self.mempool):
            return txid

        self.evict_expired_mempool(MEMPOOL_EXPIRY_SECONDS)
        if len(self.mempool) >= MAX_MEMPOOL_TRANSACTIONS:
            self.evict_mempool_to_size(max(0, MAX_MEMPOOL_TRANSACTIONS - 1))
        current_bytes = int(self.mempool_info().get("bytes", 0)) if self.mempool else 0
        if current_bytes + transaction_vsize(tx) > MAX_MEMPOOL_BYTES:
            self.evict_mempool_to_size(max(0, len(self.mempool) - 1))
            current_bytes = int(self.mempool_info().get("bytes", 0)) if self.mempool else 0
            if current_bytes + transaction_vsize(tx) > MAX_MEMPOOL_BYTES:
                raise ChainError("mempool is full; try again after pending transactions confirm")

        conflicts = self.mempool_conflicts(tx)
        if conflicts:
            if not all(conflict.signals_rbf for conflict in conflicts):
                raise ChainError("transaction conflicts with non-replaceable mempool transaction")
            old_fees = 0
            old_vsize = 0
            for conflict in conflicts:
                try:
                    old_fees += self.calculate_fee(conflict)
                except ChainError:
                    pass
                old_vsize += max(1, transaction_vsize(conflict))
            new_fee = self.calculate_fee(tx)
            required_delta = (old_vsize * INCREMENTAL_RELAY_FEE + 999) // 1000
            if new_fee <= old_fees:
                raise ChainError("replacement fee is not higher than conflicting transactions")
            if new_fee < old_fees + required_delta:
                raise ChainError("replacement fee increase is below incremental relay fee")
            if self.fee_rate(tx, new_fee) <= (old_fees * 1000 // max(1, old_vsize)):
                raise ChainError("replacement fee rate is not higher than conflicting transactions")
            conflict_txids = {conflict.txid() for conflict in conflicts}
            self.mempool = [existing for existing in self.mempool if existing.txid() not in conflict_txids]

        temp_utxos = self.utxo_set()
        spend_height = self.height() + 1
        for existing in self.mempool:
            self.validate_regular_transaction(existing, temp_utxos, spend_height)
            self.apply_regular_transaction(existing, temp_utxos, spend_height)
        fee = self.validate_regular_transaction(tx, temp_utxos, spend_height)
        self.check_standard_transaction(tx, fee)
        if self.mempool_ancestor_count(tx) >= MAX_MEMPOOL_ANCESTORS:
            raise ChainError("transaction has too many unconfirmed ancestors")
        self.mempool.append(tx)
        self.mempool_times[txid] = time.time()
        if save:
            self.save_mempool()
        return txid

    def add_mempool_package(self, txs: Sequence[Transaction], *, save: bool = True) -> list[str]:
        """Accept a small ancestor/descendant package using aggregate fee policy.

        This is a deliberately compact CPFP/package-relay primitive: every
        transaction must be valid in package order, individually non-fee-standard
        (weight/dust), and the aggregate package fee must meet min relay. It lets
        a high-fee child pay for a low-fee unconfirmed parent while still keeping
        consensus validation unchanged.
        """
        package = list(txs)
        if not package:
            raise ChainError("package is empty")
        txids = [tx.txid() for tx in package]
        if len(set(txids)) != len(txids):
            raise ChainError("package contains duplicate transactions")
        if len(package) > MAX_MEMPOOL_ANCESTORS:
            raise ChainError("package exceeds ancestor limit")
        existing_ids = {tx.txid() for tx in self.mempool}
        if existing_ids.intersection(txids):
            raise ChainError("package contains transaction already in mempool")
        for tx in package:
            if tx.is_coinbase:
                raise ChainError("cannot add coinbase transaction to mempool")
            if self.mempool_conflicts(tx):
                raise ChainError("package conflicts with existing mempool transaction")

        temp_utxos = self.utxo_set()
        spend_height = self.height() + 1
        for existing in self.mempool:
            self.validate_regular_transaction(existing, temp_utxos, spend_height)
            self.apply_regular_transaction(existing, temp_utxos, spend_height)

        fees: list[int] = []
        total_vsize = 0
        for tx in package:
            fee = self.validate_regular_transaction(tx, temp_utxos, spend_height)
            self.check_standard_transaction_shape(tx)
            fees.append(fee)
            total_vsize += transaction_vsize(tx)
            self.apply_regular_transaction(tx, temp_utxos, spend_height)
        required = (total_vsize * MIN_RELAY_FEE_PER_KB + 999) // 1000
        if sum(fees) < required:
            raise ChainError("package fee is below min relay fee")
        for tx in package:
            if self.mempool_ancestor_count(tx) >= MAX_MEMPOOL_ANCESTORS:
                raise ChainError("package transaction has too many unconfirmed ancestors")

        self.mempool.extend(package)
        now = time.time()
        for txid in txids:
            self.mempool_times[txid] = now
        if save:
            self.save_mempool()
        return txids

    def _safe_fee_rate(self, tx: Transaction) -> int:
        try:
            return self.fee_rate(tx)
        except (ChainError, TransactionError):
            return 0

    def evict_expired_mempool(self, max_age_seconds: int, now: float | None = None, *, save: bool = True) -> int:
        """Drop mempool transactions older than max_age_seconds. Returns count."""
        now = time.time() if now is None else now
        kept: list[Transaction] = []
        evicted = 0
        for tx in self.mempool:
            added = self.mempool_times.get(tx.txid(), now)
            if now - added > max_age_seconds:
                self.mempool_times.pop(tx.txid(), None)
                evicted += 1
            else:
                kept.append(tx)
        if evicted:
            self.mempool = kept
            if save:
                self.save_mempool()
        return evicted

    def evict_mempool_to_size(self, max_count: int) -> int:
        """Evict lowest-fee-rate transactions until the mempool fits max_count."""
        if len(self.mempool) <= max_count:
            return 0
        ranked = sorted(self.mempool, key=self._safe_fee_rate)
        drop_count = len(self.mempool) - max_count
        dropped_ids = {tx.txid() for tx in ranked[:drop_count]}
        self.mempool = [tx for tx in self.mempool if tx.txid() not in dropped_ids]
        for txid in dropped_ids:
            self.mempool_times.pop(txid, None)
        self.save_mempool()
        return len(dropped_ids)

    def mempool_ancestor_count(self, tx: Transaction) -> int:
        """Number of unconfirmed mempool transactions this tx (transitively) spends."""
        mempool_by_id = {existing.txid(): existing for existing in self.mempool}
        seen: set = set()
        stack = [tx]
        while stack:
            current = stack.pop()
            for txin in current.inputs:
                parent = mempool_by_id.get(txin.txid)
                if parent is not None and parent.txid() not in seen:
                    seen.add(parent.txid())
                    stack.append(parent)
        return len(seen)

    def remove_mempool_transactions(self, txids: Iterable[str]) -> None:
        remove = set(txids)
        self.mempool = [tx for tx in self.mempool if tx.txid() not in remove]
        for txid in remove:
            self.mempool_times.pop(txid, None)
        self.save_mempool()

    def clear_mempool(self) -> int:
        """Drop every unconfirmed transaction. Confirmed blocks and UTXOs stay intact."""
        count = len(self.mempool)
        self.mempool = []
        self.mempool_times = {}
        self.save_mempool()
        return count

    def purge_invalid_mempool(self) -> None:
        temp_utxos = self.utxo_set()
        spend_height = self.height() + 1
        kept: list[Transaction] = []
        for tx in self.mempool:
            try:
                fee = self.validate_regular_transaction(tx, temp_utxos, spend_height)
                self.check_standard_transaction(tx, fee)
                self.apply_regular_transaction(tx, temp_utxos, spend_height)
                kept.append(tx)
            except (ChainError, TransactionError):
                continue
        self.mempool = kept
        self.save_mempool()

    def mempool_info(self) -> dict[str, Any]:
        entries = []
        total_bytes = 0
        entry_by_txid: dict[str, dict[str, Any]] = {}
        temp_utxos = self.utxo_set()
        spend_height = self.height() + 1
        for tx in self.mempool:
            try:
                # Validate against a rolling view so CPFP/package children can
                # spend unconfirmed parents already present in mempool order.
                fee = self.validate_regular_transaction(tx, temp_utxos, spend_height)
                vsize = transaction_vsize(tx)
                total_bytes += vsize
                entry = {
                    "txid": tx.txid(),
                    "wtxid": tx.wtxid(),
                    "vsize": vsize,
                    "weight": transaction_weight(tx),
                    "fee": fee,
                    "fee_rate_per_kvb": self.fee_rate(tx, fee),
                    "rbf": bool(tx.signals_rbf),
                }
                entries.append(entry)
                entry_by_txid[tx.txid()] = entry
                self.apply_regular_transaction(tx, temp_utxos, spend_height)
            except ChainError:
                continue
        packages = self.mempool_packages(entry_by_txid)
        return {
            "size": len(entries),
            "bytes": total_bytes,
            "max_transactions": MAX_MEMPOOL_TRANSACTIONS,
            "max_bytes": MAX_MEMPOOL_BYTES,
            "expiry_seconds": MEMPOOL_EXPIRY_SECONDS,
            "min_relay_fee_per_kvb": MIN_RELAY_FEE_PER_KB,
            "entries": entries,
            "packages": packages,
        }

    def mempool_packages(self, entry_by_txid: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Return connected mempool transaction packages for CPFP/package views."""
        entry_by_txid = entry_by_txid or {}
        mempool_ids = {tx.txid() for tx in self.mempool}
        edges: dict[str, set[str]] = {txid: set() for txid in mempool_ids}
        for tx in self.mempool:
            txid = tx.txid()
            for txin in tx.inputs:
                if txin.txid in mempool_ids:
                    edges[txid].add(txin.txid)
                    edges[txin.txid].add(txid)
        seen: set[str] = set()
        packages: list[dict[str, Any]] = []
        for txid in sorted(mempool_ids):
            if txid in seen:
                continue
            stack = [txid]
            component: list[str] = []
            seen.add(txid)
            while stack:
                current = stack.pop()
                component.append(current)
                for nxt in edges.get(current, set()):
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            fee = sum(int(entry_by_txid.get(t, {}).get("fee", 0)) for t in component)
            vsize = sum(int(entry_by_txid.get(t, {}).get("vsize", 0)) for t in component)
            packages.append(
                {
                    "txids": sorted(component),
                    "count": len(component),
                    "fee": fee,
                    "vsize": vsize,
                    "fee_rate_per_kvb": (fee * 1000 // max(1, vsize)),
                }
            )
        return packages

    def estimate_smart_fee(self, target_blocks: int = 1) -> dict[str, Any]:
        # A tiny local estimator: with no fee market, return min relay. If the
        # mempool has entries, return the median observed fee rate plus a small
        # target-dependent bump.
        rates = []
        for tx in self.mempool:
            try:
                rates.append(self.fee_rate(tx))
            except ChainError:
                pass
        if rates:
            rates.sort()
            rate = rates[len(rates) // 2]
        else:
            rate = MIN_RELAY_FEE_PER_KB
        rate += max(0, 6 - int(target_blocks)) * 100
        return {"blocks": int(target_blocks), "fee_rate_per_kvb": rate, "method": "local-policy"}

    # ------------------------------------------------------------------
    # Mining, chain selection, headers, explorer helpers
    # ------------------------------------------------------------------

    def mine_block(self, miner_address: str) -> Block:
        if not validate_address(miner_address):
            raise ChainError("miner address is not a valid NetCoin address")
        height = self.height() + 1
        mined_at = int(time.time())
        bits = self.expected_bits_for_height(height, self.chain)
        if self.chain and mined_at > self.tip().header.timestamp + min_difficulty_gap_at(height):
            bits = POW_LIMIT_BITS  # testnet lone-miner rule: mine the floor when late
        previous_hash = self.tip_hash()
        temp_utxos = self.utxo_set()
        selected: list[Transaction] = []
        selected_txids: list[str] = []
        fees = 0
        weight_budget = MAX_BLOCK_WEIGHT
        for tx in list(self.mempool):
            try:
                tx_weight = transaction_weight(tx)
                if tx_weight > weight_budget:
                    continue
                fee = self.validate_regular_transaction(tx, temp_utxos, height)
                self.apply_regular_transaction(tx, temp_utxos, height)
            except (ChainError, TransactionError):
                continue
            selected.append(tx)
            selected_txids.append(tx.txid())
            fees += fee
            weight_budget -= tx_weight

        reward = self.subsidy(height) + fees
        extra_nonce = 0
        needs_witness_commitment = any(tx.has_witness for tx in selected)
        while True:
            coinbase = create_coinbase_transaction(height, miner_address, reward, extra_nonce=extra_nonce)
            txs = [coinbase] + selected
            if needs_witness_commitment:
                commit = witness_commitment(txs)
                coinbase = create_coinbase_transaction(
                    height, miner_address, reward, extra_nonce=extra_nonce, witness_commitment=commit
                )
                txs = [coinbase] + selected
            candidate = make_block(previous_hash, height, bits, txs, timestamp=mined_at)
            try:
                self.validate_block_against(candidate, self.tip(), self.utxo_set(), self.chain)
                break
            except (ChainError, BlockError):
                extra_nonce += 1
                if extra_nonce > 1_000_000:
                    raise ChainError("failed to mine a valid block after many coinbase nonces")

        self.chain.append(candidate)
        self._index_block(candidate)
        self._apply_block_to_persistent_utxos(candidate)
        self.remove_mempool_transactions(selected_txids)
        self.purge_invalid_mempool()
        self.save_chain()
        return candidate

    def add_block(self, block: Block) -> str:
        block_hash = block.hash()
        if self.block_by_hash(block_hash) is not None:
            # Already part of the active chain: idempotent.
            return block_hash

        if block.header.previous_hash == self.tip_hash():
            # Fast path: the block extends the current best tip.
            self.validate_block_against(block, self.tip(), self.utxo_set(), self.chain)
            self.chain.append(block)
            self._index_block(block)
            self._apply_block_to_persistent_utxos(block)
            included = [tx.txid() for tx in block.transactions[1:]]
            self.remove_mempool_transactions(included)
            self.purge_invalid_mempool()
            self.save_chain()
            # A new tip can let a previously-stored fork branch connect.
            if self.orphan_blocks:
                self._maybe_reorg()
            return block_hash

        # Otherwise the block is a fork branch or a future/orphan block. Reject
        # cheap junk (bad proof of work) before storing anything, then keep it as
        # a candidate and see whether a heavier valid branch now exists.
        if not check_proof_of_work(block.header):
            raise ChainError("block proof of work is invalid")
        self._remember_orphan(block)
        if self._maybe_reorg() and self.block_by_hash(block_hash) is not None:
            return block_hash
        raise ChainError("block does not connect to current tip; stored as fork/orphan candidate")

    def _remember_orphan(self, block: Block) -> None:
        # Bounded store of off-tip blocks (forks and future blocks). Real Bitcoin
        # Core keeps a full block index; this is a readable, memory-capped step.
        self.orphan_blocks[block.hash()] = block
        max_orphans = 2000
        while len(self.orphan_blocks) > max_orphans:
            oldest = next(iter(self.orphan_blocks))
            del self.orphan_blocks[oldest]

    def _build_branch(self, tip_hash: str, known: dict[str, Block]) -> list[Block] | None:
        """Walk parent links from tip_hash back to genesis using known blocks."""
        branch: list[Block] = []
        seen: set[str] = set()
        current = tip_hash
        while current in known:
            if current in seen:  # cycle guard
                return None
            seen.add(current)
            node = known[current]
            branch.append(node)
            if node.header.height == 0 or node.header.previous_hash == ZERO_HASH:
                break
            current = node.header.previous_hash
        branch.reverse()
        if not branch or branch[0].header.height != 0:
            return None
        return branch

    def _maybe_reorg(self) -> bool:
        """Switch to the heaviest fully valid branch if it beats the active tip.

        Only a strictly greater cumulative work wins, so the first-seen tip is
        kept on ties (matching Bitcoin's tie-breaking)."""
        known: dict[str, Block] = {b.hash(): b for b in self.chain}
        known.update(self.orphan_blocks)
        genesis_hash = self.chain[0].hash()
        best_chain = self.chain
        best_work = cumulative_work(self.chain)

        for candidate_hash in list(known):
            branch = self._build_branch(candidate_hash, known)
            if branch is None or branch[0].hash() != genesis_hash:
                continue
            if branch[-1].hash() == self.tip_hash():
                continue  # same tip as (a prefix of) the active chain
            work = cumulative_work(branch)
            if work <= best_work:
                continue
            if not self.is_valid_chain(branch):
                continue
            best_chain, best_work = branch, work

        if best_chain is self.chain or best_chain[-1].hash() == self.tip_hash():
            return False
        self._switch_to(best_chain)
        return True

    def _switch_to(self, new_chain: Sequence[Block]) -> None:
        new_hashes = {b.hash() for b in new_chain}
        disconnected = [b for b in self.chain if b.hash() not in new_hashes]

        self.chain = list(new_chain)
        self.reindex()
        # Keep blocks that left the active chain as fork candidates, and drop the
        # now-active blocks from the candidate pool.
        for b in disconnected:
            self.orphan_blocks[b.hash()] = b
        for b in new_chain:
            self.orphan_blocks.pop(b.hash(), None)

        # Return transactions from disconnected blocks to the mempool, then drop
        # anything no longer valid against the new chain.
        for b in disconnected:
            for tx in b.transactions[1:]:
                try:
                    self.add_mempool_transaction(tx, save=False)
                except (ChainError, TransactionError):
                    continue
        included = {tx.txid() for b in new_chain for tx in b.transactions[1:]}
        if included:
            self.mempool = [tx for tx in self.mempool if tx.txid() not in included]
        self.purge_invalid_mempool()
        self.save_chain()

    def replace_chain(self, blocks: Sequence[Block]) -> bool:
        self.assert_valid_chain(blocks)
        if blocks[0].hash() != self.chain[0].hash():
            raise ChainError("candidate chain has a different genesis block")
        current_work = cumulative_work(self.chain)
        candidate_work = cumulative_work(blocks)
        if candidate_work <= current_work:
            return False
        self.chain = list(blocks)
        self.reindex()
        self.purge_invalid_mempool()
        self.save_chain()
        return True

    def get_block_by_hash(self, block_hash: str) -> Block | None:
        return self.block_index.get(block_hash.lower())

    def get_transaction(self, txid: str) -> tuple[Transaction, Block | None] | None:
        needle = txid.lower()
        located = self.tx_index.get(needle)
        if located is not None:
            block = self.block_index.get(located["block_hash"])
            if block is not None:
                tx = block.transactions[located["position"]]
                return tx, block
        # Mempool and wtxid lookups fall back to a scan (small sets).
        for tx in self.mempool:
            if tx.txid() == needle or tx.wtxid() == needle:
                return tx, None
        if located is None:
            for block in self.chain:
                for tx in block.transactions:
                    if tx.wtxid() == needle:
                        return tx, block
        return None

    def utxo_snapshot_digest(self, utxos: dict[str, SpendableOutput] | None = None) -> str:
        """Deterministic SHA-256 over the UTXO set, for snapshot/integrity checks."""
        import hashlib

        utxos = self.utxo_set() if utxos is None else utxos
        items = sorted(
            f"{outpoint}|{u.output.amount}|{u.output.address}|{int(u.coinbase)}|{u.height}"
            for outpoint, u in utxos.items()
        )
        return hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()

    def export_utxo_snapshot(self) -> dict[str, Any]:
        """Export the current UTXO set for faster bootstrap / external verification."""
        utxos = self.utxo_set()
        return {
            "network": "NetCoin",
            "height": self.height(),
            "tip_hash": self.tip_hash(),
            "utxo_count": len(utxos),
            "digest": self.utxo_snapshot_digest(utxos),
            "utxos": [u.to_dict() for u in utxos.values()],
        }

    def verify_utxo_snapshot(self, snapshot: dict[str, Any]) -> bool:
        """True if a snapshot matches this chain's current UTXO set and tip."""
        if snapshot.get("tip_hash") != self.tip_hash():
            return False
        return snapshot.get("digest") == self.utxo_snapshot_digest()

    def chainstate_commitment(self) -> dict[str, Any]:
        """Deterministic commitment to the active chainstate.

        This is stronger than a plain UTXO digest because it binds height, tip,
        UTXO count, and consensus version into one operator-friendly hash.
        """
        return build_chainstate_commitment(
            height=self.height(),
            tip_hash=self.tip_hash(),
            utxos=self.utxo_set(),
            consensus_version=consensus_rules_at_height(self.height()).version,
        )

    def prune(self, keep_depth: int) -> dict[str, Any]:
        """Drop block bodies below tip-keep_depth from disk, keeping headers and a
        UTXO snapshot (SQLite backend only). The running node is unaffected; on the
        next reload the node runs in pruned mode. keep_depth should be at least the
        difficulty window (2016) for a node that will keep mining across a retarget."""
        if self.store is None:
            raise ChainError("pruning requires the SQLite backend (NETCOIN_BACKEND=sqlite)")
        if keep_depth < 1:
            raise ChainError("keep_depth must be >= 1")
        # Ensure the latest blocks are persisted, then snapshot the UTXO set.
        self.save_chain()
        self.store.save_utxo_snapshot(self.export_utxo_snapshot())
        below_height = max(1, self.height() - keep_depth + 1)
        pruned = self.store.prune_bodies(below_height)
        return {
            "ok": True,
            "pruned_block_bodies": pruned,
            "pruned_below_height": below_height,
            "kept_from_height": below_height,
            "tip_height": self.height(),
        }

    def verify_integrity(self) -> dict[str, Any]:
        """Revalidate the chain and check index/UTXO consistency (chainstate check)."""
        if self.pruned:
            # A pruned node cannot revalidate from genesis; report pruned state.
            return {
                "ok": True,
                "pruned": True,
                "pruned_below_height": self.pruned_below,
                "height": self.height(),
                "retained_blocks": len(self.chain),
                "utxos": len(self._utxos),
            }
        self.assert_valid_chain(self.chain)
        expected_blocks = {b.hash() for b in self.chain}
        index_consistent = set(self.block_index) == expected_blocks
        # The persistent UTXO cache must match a fresh full-scan recomputation.
        recomputed = self._recompute_utxos_from_chain()
        utxo_consistent = set(self._utxos) == set(recomputed)
        # The per-address index must mirror the authoritative set exactly.
        fresh_addr_index = {op for bucket in self._utxos_by_addr.values() for op in bucket}
        addr_index_consistent = fresh_addr_index == set(self._utxos) and all(
            self._utxos[op].output.address == addr for addr, bucket in self._utxos_by_addr.items() for op in bucket
        )
        return {
            "ok": index_consistent and utxo_consistent and addr_index_consistent,
            "utxo_addr_index_consistent": addr_index_consistent,
            "height": self.height(),
            "blocks": len(self.chain),
            "indexed_blocks": len(self.block_index),
            "indexed_txs": len(self.tx_index),
            "utxos": len(self._utxos),
            "index_consistent": index_consistent,
            "utxo_consistent": utxo_consistent,
        }

    def headers(self, start_height: int = 0, limit: int = 2000) -> list[dict[str, Any]]:
        start_height = max(0, int(start_height))
        limit = max(0, min(int(limit), 2000))
        return [
            block.header.to_dict() | {"hash": block.hash(), "work": cumulative_work([block])}
            for block in self.chain[start_height : start_height + limit]
        ]

    def validate_headers_from_tip(self, headers: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate a consecutive headers-first sync segment extending our tip.

        This performs the cheap checks before block-body download: height, parent
        link, difficulty bits, header hash, and proof-of-work. Full block
        validation still happens after each body is downloaded.
        """
        accepted: list[dict[str, Any]] = []
        previous_hash = self.tip_hash()
        prefix = list(self.chain)
        expected_height = self.height() + 1
        for raw in headers:
            header = BlockHeader.from_dict(raw)
            advertised_hash = str(raw.get("hash", header.hash())).lower()
            if advertised_hash != header.hash():
                raise ChainError("header hash does not match advertised hash")
            if header.height != expected_height:
                raise ChainError("headers are not height-consecutive")
            if header.previous_hash != previous_hash:
                raise ChainError("headers do not connect to local tip")
            if not self._bits_acceptable(header.height, prefix, header.bits, header.timestamp):
                raise ChainError("header bits do not match expected difficulty")
            if not check_proof_of_work(header):
                raise ChainError("header proof of work is invalid")
            accepted.append(raw | {"hash": advertised_hash})
            # Only the existing prefix is needed for current retarget windows. A
            # lightweight placeholder would work for deep segments, but NetCoin
            # sync windows are small and each real block is fetched immediately.
            previous_hash = advertised_hash
            expected_height += 1
        return accepted

    def compact_block(self, block_hash: str) -> dict[str, Any]:
        block = self.get_block_by_hash(block_hash)
        if block is None:
            raise ChainError("block not found")
        return {
            "header": block.header.to_dict() | {"hash": block.hash()},
            "txids": [tx.txid() for tx in block.transactions],
            "prefilled": [{"index": 0, "tx": block.transactions[0].to_dict()}],
        }

    def block_template(self, miner_address: str) -> dict[str, Any]:
        if not validate_address(miner_address):
            raise ChainError("miner address is not a valid NetCoin address")
        height = self.height() + 1
        mined_at = int(time.time())
        bits = self.expected_bits_for_height(height, self.chain)
        if self.chain and mined_at > self.tip().header.timestamp + min_difficulty_gap_at(height):
            bits = POW_LIMIT_BITS
        temp_utxos = self.utxo_set()
        txs = []
        fees = 0
        for tx in self.mempool:
            try:
                fee = self.validate_regular_transaction(tx, temp_utxos, height)
                self.apply_regular_transaction(tx, temp_utxos, height)
                fees += fee
                txs.append(
                    {
                        "txid": tx.txid(),
                        "wtxid": tx.wtxid(),
                        "fee": fee,
                        "weight": transaction_weight(tx),
                        "tx": tx.to_dict(include_scripts=True, include_witness=True),
                    }
                )
            except ChainError:
                continue
        return {
            "version": 1,
            "previous_hash": self.tip_hash(),
            "height": height,
            "bits": bits,
            "subsidy": self.subsidy(height),
            "fees": fees,
            "max_block_weight": MAX_BLOCK_WEIGHT,
            "transactions": txs,
            "coinbase_value": self.subsidy(height) + fees,
        }

    def chain_info(self) -> dict[str, Any]:
        return {
            "height": self.height(),
            "tip_hash": self.tip_hash(),
            "blocks": len(self.chain),
            "mempool_transactions": len(self.mempool),
            "cumulative_work": cumulative_work(self.chain),
            "bits": self.tip().header.bits,
            "block_weight_limit": MAX_BLOCK_WEIGHT,
            "orphan_candidates": len(self.orphan_blocks),
        }

    def export_chain(self, start: int = 0, limit: int | None = None) -> dict[str, Any]:
        """Export a bounded chain slice.

        Public HTTP callers should not be able to force a full-chain JSON dump as
        the chain grows. CLI callers can still omit ``limit`` for a local full
        export, while the node API passes an explicit bounded limit.
        """
        start = max(0, int(start))
        if limit is None:
            selected = self.chain[start:]
            limit_value = len(selected)
        else:
            limit_value = max(1, min(int(limit), 2000))
            selected = self.chain[start : start + limit_value]
        next_start = start + len(selected)
        return {
            "height": self.height(),
            "tip_hash": self.tip_hash(),
            "start": start,
            "limit": limit_value,
            "has_next": next_start < len(self.chain),
            "next_start": next_start,
            "blocks": [block.to_dict() for block in selected],
        }

    def export_mempool(self) -> dict[str, Any]:
        return {"transactions": [tx.to_dict(include_scripts=True, include_witness=True) for tx in self.mempool]}

    def import_chain_data(self, data: dict[str, Any]) -> list[Block]:
        return [Block.from_dict(item) for item in data["blocks"]]


def create_genesis_block(allocation: dict[str, int] | None = None) -> Block:
    # An optional allocation pre-funds addresses in the genesis coinbase. This is
    # how a relaunch carries balances forward from a snapshot of the old chain
    # (see netcoin/migration.py). With no allocation the genesis is unchanged.
    outputs = []
    if allocation:
        for address, amount in sorted(allocation.items()):
            if amount > 0:
                outputs.append(TxOutput(amount=int(amount), address=address))
    coinbase = Transaction(
        inputs=[TxInput(txid=ZERO_HASH, vout=-1, coinbase=GENESIS_MESSAGE)],
        outputs=outputs,
    )
    root = merkle_root([coinbase])
    header = BlockHeader(
        version=1,
        previous_hash=ZERO_HASH,
        merkle_root=root,
        timestamp=GENESIS_TIMESTAMP,
        bits=INITIAL_BITS,
        nonce=0,
        height=0,
    )
    from .block import mine_header

    return Block(header=mine_header(header), transactions=[coinbase])


# Compatibility helpers for the v2 CLI/node modules.
def _chain_header_list(self, start_height: int = 0, limit: int = 2000):
    return self.headers(start_height, limit)


def _chain_block_by_hash(self, block_hash: str):
    return self.get_block_by_hash(block_hash)


def _chain_get_block_template(self, miner_address=None):
    if miner_address is None:
        miner_address = (
            self.chain[0].transactions[0].outputs[0].address if self.chain[0].transactions[0].outputs else ""
        )
        if not miner_address:
            # Template without a payout address is still useful for inspection.
            height = self.height() + 1
            return {
                "version": 1,
                "previous_hash": self.tip_hash(),
                "height": height,
                "bits": self.expected_bits_for_height(height, self.chain),
                "subsidy": self.subsidy(height),
                "fees": 0,
                "max_block_weight": MAX_BLOCK_WEIGHT,
                "transactions": [],
                "coinbase_value": self.subsidy(height),
            }
    return self.block_template(miner_address)


def _chain_fee_lookup(self):
    lookup = {}
    for tx in self.mempool:
        try:
            lookup[tx.txid()] = self.calculate_fee(tx)
        except Exception:
            pass
    return lookup


def _chain_estimate_fee_rate(self, target_blocks: int = 1):
    return max(1, int(self.estimate_smart_fee(target_blocks).get("fee_rate_per_kvb", MIN_RELAY_FEE_PER_KB)) // 1000)


Blockchain.header_list = _chain_header_list
Blockchain.block_by_hash = _chain_block_by_hash
Blockchain.get_block_template = _chain_get_block_template
Blockchain.fee_lookup = _chain_fee_lookup
Blockchain.estimate_fee_rate = _chain_estimate_fee_rate
