"""Blockchain state, consensus validation, mining, mempool policy, and persistence."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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
)
from .crypto import validate_address
from .params import (
    COINBASE_MATURITY,
    DEFAULT_DATA_DIR,
    DIFFICULTY_ADJUSTMENT_INTERVAL,
    DUST_THRESHOLD,
    GENESIS_MESSAGE,
    GENESIS_TIMESTAMP,
    HALVING_INTERVAL,
    INITIAL_BITS,
    INITIAL_SUBSIDY,
    LOCKTIME_THRESHOLD,
    MAX_BLOCK_WEIGHT,
    MAX_MEMPOOL_ANCESTORS,
    MAX_MONEY,
    MAX_STANDARD_TX_WEIGHT,
    MIN_RELAY_FEE_PER_KB,
    POW_LIMIT_BITS,
    TARGET_TIMESPAN_SECONDS,
    ZERO_HASH,
)
from .serialization import block_weight, transaction_vsize, transaction_weight
from .tx import (
    SpendableOutput,
    Transaction,
    TransactionError,
    TxInput,
    create_coinbase_transaction,
    ensure_unique_inputs,
)


class ChainError(ValueError):
    """Raised when chain state or consensus validation fails."""


class Blockchain:
    """A small Bitcoin-like blockchain database.

    The class stores blocks and mempool transactions as JSON files under a data
    directory. It validates proof-of-work, UTXO spends, signatures, coinbase
    rewards, halving, coinbase maturity, difficulty retargeting, block weight,
    and a small set of mempool policy rules.
    """

    def __init__(self, data_dir: str | os.PathLike[str] = DEFAULT_DATA_DIR, autosave: bool = True):
        self.data_dir = Path(data_dir)
        self.autosave = autosave
        self.chain: List[Block] = []
        self.mempool: List[Transaction] = []
        self.orphan_blocks: Dict[str, Block] = {}
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.load_or_create()

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
        if self.chain_path.exists():
            data = json.loads(self.chain_path.read_text())
            self.chain = [Block.from_dict(item) for item in data["blocks"]]
            self.assert_valid_chain(self.chain)
        else:
            self.chain = [create_genesis_block()]
            self.save_chain()

        if self.mempool_path.exists():
            data = json.loads(self.mempool_path.read_text())
            loaded = [Transaction.from_dict(item) for item in data.get("transactions", [])]
            self.mempool = []
            for tx in loaded:
                try:
                    self.add_mempool_transaction(tx, save=False)
                except (ChainError, TransactionError):
                    continue
        else:
            self.mempool = []
            self.save_mempool()

    def save_chain(self) -> None:
        if not self.autosave:
            return
        payload = {"blocks": [block.to_dict() for block in self.chain]}
        tmp = self.chain_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp.replace(self.chain_path)

    def save_mempool(self) -> None:
        if not self.autosave:
            return
        payload = {"transactions": [tx.to_dict(include_scripts=True, include_witness=True) for tx in self.mempool]}
        tmp = self.mempool_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp.replace(self.mempool_path)

    def save(self) -> None:
        self.save_chain()
        self.save_mempool()

    # ------------------------------------------------------------------
    # Consensus rules
    # ------------------------------------------------------------------

    def subsidy(self, height: int) -> int:
        if height < 0:
            raise ChainError("height cannot be negative")
        halvings = height // HALVING_INTERVAL
        if halvings >= 64:
            return 0
        return INITIAL_SUBSIDY >> halvings

    def expected_bits_for_height(self, height: int, chain_prefix: Optional[Sequence[Block]] = None) -> int:
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
        min_timespan = TARGET_TIMESPAN_SECONDS // 4
        max_timespan = TARGET_TIMESPAN_SECONDS * 4
        actual_timespan = max(min_timespan, min(actual_timespan, max_timespan))
        old_target = bits_to_target(previous_bits)
        new_target = old_target * actual_timespan // TARGET_TIMESPAN_SECONDS
        return target_to_bits(new_target)

    def utxo_set(self, include_mempool: bool = False) -> Dict[str, SpendableOutput]:
        utxos: Dict[str, SpendableOutput] = {}
        for block in self.chain:
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
        if include_mempool:
            height = self.height() + 1
            for tx in self.mempool:
                self.validate_regular_transaction(tx, utxos, height)
                self.apply_regular_transaction(tx, utxos, height)
        return utxos

    def utxos_for_address(self, address: str, *, include_immature: bool = False) -> List[SpendableOutput]:
        if not validate_address(address):
            raise ChainError("address is not a valid NetCoin address")
        spend_height = self.height() + 1
        result = []
        for utxo in self.utxo_set().values():
            if utxo.output.address != address:
                continue
            if utxo.coinbase and not include_immature and spend_height - utxo.height < COINBASE_MATURITY:
                continue
            result.append(utxo)
        result.sort(key=lambda item: (item.height, item.txid, item.vout))
        return result

    def balances_for_address(self, address: str) -> Dict[str, int]:
        if not validate_address(address):
            raise ChainError("address is not a valid NetCoin address")
        total = 0
        spendable = 0
        immature = 0
        spend_height = self.height() + 1
        for utxo in self.utxo_set().values():
            if utxo.output.address != address:
                continue
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
        self, tx: Transaction, utxos: Dict[str, SpendableOutput], spend_height: int
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

    def apply_regular_transaction(
        self, tx: Transaction, utxos: Dict[str, SpendableOutput], spend_height: int
    ) -> None:
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

    def apply_coinbase_transaction(
        self, tx: Transaction, utxos: Dict[str, SpendableOutput], height: int
    ) -> None:
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
        utxos: Dict[str, SpendableOutput],
        chain_prefix: Sequence[Block],
    ) -> Dict[str, SpendableOutput]:
        expected_height = previous.header.height + 1
        if block.header.height != expected_height:
            raise ChainError("block height does not extend the previous block")
        if block.header.previous_hash != previous.hash():
            raise ChainError("block previous hash does not match chain tip")
        if block.header.bits != self.expected_bits_for_height(block.header.height, chain_prefix):
            raise ChainError("block bits do not match expected difficulty target")
        if block.header.merkle_root != merkle_root(block.transactions):
            raise ChainError("block merkle root does not match its transactions")
        if not check_proof_of_work(block.header):
            raise ChainError("block proof of work is invalid")
        if block.header.timestamp > int(time.time()) + 2 * 60 * 60:
            raise ChainError("block timestamp is too far in the future")
        if block_weight(block) > MAX_BLOCK_WEIGHT:
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

        max_reward = self.subsidy(block.header.height) + fees
        self.validate_coinbase_transaction(block.transactions[0], block.header.height, max_reward)
        coinbase_txid = block.transactions[0].txid()
        if coinbase_txid in seen_txids:
            raise ChainError("coinbase transaction id duplicates another transaction")
        self.apply_coinbase_transaction(block.transactions[0], temp_utxos, block.header.height)
        return temp_utxos

    def assert_valid_chain(self, blocks: Sequence[Block]) -> None:
        if not blocks:
            raise ChainError("chain is empty")
        genesis = create_genesis_block()
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

        utxos: Dict[str, SpendableOutput] = {}
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

    def calculate_fee(self, tx: Transaction, utxos: Optional[Dict[str, SpendableOutput]] = None, spend_height: Optional[int] = None) -> int:
        temp_utxos = self.utxo_set() if utxos is None else dict(utxos)
        return self.validate_regular_transaction(tx, temp_utxos, spend_height or self.height() + 1)

    def fee_rate(self, tx: Transaction, fee: Optional[int] = None) -> int:
        fee_value = self.calculate_fee(tx) if fee is None else int(fee)
        vsize = max(1, transaction_vsize(tx))
        return fee_value * 1000 // vsize

    def check_standard_transaction(self, tx: Transaction, fee: int) -> None:
        if transaction_weight(tx) > MAX_STANDARD_TX_WEIGHT:
            raise ChainError("non-standard transaction: weight too high")
        min_fee = (transaction_vsize(tx) * MIN_RELAY_FEE_PER_KB + 999) // 1000
        if fee < min_fee:
            raise ChainError("transaction fee is below min relay fee")
        for output in tx.outputs:
            if 0 < output.amount < DUST_THRESHOLD:
                raise ChainError("transaction creates dust output")

    def mempool_conflicts(self, tx: Transaction) -> List[Transaction]:
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

        conflicts = self.mempool_conflicts(tx)
        if conflicts:
            if not all(conflict.signals_rbf for conflict in conflicts):
                raise ChainError("transaction conflicts with non-replaceable mempool transaction")
            old_fees = 0
            for conflict in conflicts:
                try:
                    old_fees += self.calculate_fee(conflict)
                except ChainError:
                    pass
            new_fee = self.calculate_fee(tx)
            if new_fee <= old_fees:
                raise ChainError("replacement fee is not higher than conflicting transactions")
            conflict_txids = {conflict.txid() for conflict in conflicts}
            self.mempool = [existing for existing in self.mempool if existing.txid() not in conflict_txids]

        temp_utxos = self.utxo_set()
        spend_height = self.height() + 1
        for existing in self.mempool:
            self.validate_regular_transaction(existing, temp_utxos, spend_height)
            self.apply_regular_transaction(existing, temp_utxos, spend_height)
        fee = self.validate_regular_transaction(tx, temp_utxos, spend_height)
        self.check_standard_transaction(tx, fee)
        self.mempool.append(tx)
        if save:
            self.save_mempool()
        return txid

    def remove_mempool_transactions(self, txids: Iterable[str]) -> None:
        remove = set(txids)
        self.mempool = [tx for tx in self.mempool if tx.txid() not in remove]
        self.save_mempool()

    def purge_invalid_mempool(self) -> None:
        temp_utxos = self.utxo_set()
        spend_height = self.height() + 1
        kept: List[Transaction] = []
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

    def mempool_info(self) -> Dict[str, Any]:
        entries = []
        total_bytes = 0
        for tx in self.mempool:
            try:
                fee = self.calculate_fee(tx)
                vsize = transaction_vsize(tx)
                total_bytes += vsize
                entries.append(
                    {
                        "txid": tx.txid(),
                        "wtxid": tx.wtxid(),
                        "vsize": vsize,
                        "weight": transaction_weight(tx),
                        "fee": fee,
                        "fee_rate_per_kvb": self.fee_rate(tx, fee),
                        "rbf": tx.signals_rbf,
                    }
                )
            except ChainError:
                continue
        return {"size": len(entries), "bytes": total_bytes, "min_relay_fee_per_kvb": MIN_RELAY_FEE_PER_KB, "entries": entries}

    def estimate_smart_fee(self, target_blocks: int = 1) -> Dict[str, Any]:
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
        bits = self.expected_bits_for_height(height, self.chain)
        previous_hash = self.tip_hash()
        temp_utxos = self.utxo_set()
        selected: List[Transaction] = []
        selected_txids: List[str] = []
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
        while True:
            coinbase = create_coinbase_transaction(height, miner_address, reward, extra_nonce=extra_nonce)
            candidate = make_block(previous_hash, height, bits, [coinbase] + selected)
            try:
                self.validate_block_against(candidate, self.tip(), self.utxo_set(), self.chain)
                break
            except (ChainError, BlockError):
                extra_nonce += 1
                if extra_nonce > 1_000_000:
                    raise ChainError("failed to mine a valid block after many coinbase nonces")

        self.chain.append(candidate)
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

    def _build_branch(self, tip_hash: str, known: Dict[str, Block]) -> Optional[List[Block]]:
        """Walk parent links from tip_hash back to genesis using known blocks."""
        branch: List[Block] = []
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
        known: Dict[str, Block] = {b.hash(): b for b in self.chain}
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
        self.purge_invalid_mempool()
        self.save_chain()
        return True

    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        needle = block_hash.lower()
        for block in self.chain:
            if block.hash() == needle:
                return block
        return None

    def get_transaction(self, txid: str) -> Optional[Tuple[Transaction, Optional[Block]]]:
        needle = txid.lower()
        for block in self.chain:
            for tx in block.transactions:
                if tx.txid() == needle or tx.wtxid() == needle:
                    return tx, block
        for tx in self.mempool:
            if tx.txid() == needle or tx.wtxid() == needle:
                return tx, None
        return None

    def headers(self, start_height: int = 0, limit: int = 2000) -> List[Dict[str, Any]]:
        start_height = max(0, int(start_height))
        limit = max(0, min(int(limit), 2000))
        return [block.header.to_dict() | {"hash": block.hash(), "work": cumulative_work([block])} for block in self.chain[start_height : start_height + limit]]

    def compact_block(self, block_hash: str) -> Dict[str, Any]:
        block = self.get_block_by_hash(block_hash)
        if block is None:
            raise ChainError("block not found")
        return {
            "header": block.header.to_dict() | {"hash": block.hash()},
            "txids": [tx.txid() for tx in block.transactions],
            "prefilled": [{"index": 0, "tx": block.transactions[0].to_dict()}],
        }

    def block_template(self, miner_address: str) -> Dict[str, Any]:
        if not validate_address(miner_address):
            raise ChainError("miner address is not a valid NetCoin address")
        height = self.height() + 1
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
            "bits": self.expected_bits_for_height(height, self.chain),
            "subsidy": self.subsidy(height),
            "fees": fees,
            "max_block_weight": MAX_BLOCK_WEIGHT,
            "transactions": txs,
            "coinbase_value": self.subsidy(height) + fees,
        }

    def chain_info(self) -> Dict[str, Any]:
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

    def export_chain(self) -> Dict[str, Any]:
        return {"blocks": [block.to_dict() for block in self.chain]}

    def export_mempool(self) -> Dict[str, Any]:
        return {"transactions": [tx.to_dict(include_scripts=True, include_witness=True) for tx in self.mempool]}

    def import_chain_data(self, data: Dict[str, Any]) -> List[Block]:
        return [Block.from_dict(item) for item in data["blocks"]]


def create_genesis_block() -> Block:
    coinbase = Transaction(
        inputs=[TxInput(txid=ZERO_HASH, vout=-1, coinbase=GENESIS_MESSAGE)],
        outputs=[],
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
        miner_address = self.chain[0].transactions[0].outputs[0].address if self.chain[0].transactions[0].outputs else ""
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
