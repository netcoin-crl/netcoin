"""Consensus-rule helpers isolated from node policy.

This module is deliberately pure: it contains deterministic validation helpers,
version/activation metadata, chainstate commitments, checkpoint checks, and fork
work auditing utilities.  The ``Blockchain`` class still orchestrates storage,
mempool policy, mining templates, and node operations; new consensus changes
should land here first so they can be tested independently.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from .block import Block, cumulative_work
from .params import MAX_BLOCK_WEIGHT, ZERO_HASH
from .serialization import block_weight
from .tx import SpendableOutput

CONSENSUS_VERSION = 2
GENESIS_ACTIVATION_HEIGHT = 0
MTP_ACTIVATION_HEIGHT = 1_000_000  # staged for testnet soak before enforcement
CHECKPOINT_ACTIVATION_HEIGHT = 0


@dataclass(frozen=True)
class ConsensusDeployment:
    """A height-gated consensus deployment."""

    name: str
    bit: int | None
    start_height: int
    timeout_height: int | None
    lockin_height: int | None = None
    active_height: int | None = None
    description: str = ""

    def is_active(self, height: int) -> bool:
        return self.active_height is not None and int(height) >= int(self.active_height)


@dataclass(frozen=True)
class ConsensusRuleSet:
    version: int
    active_deployments: tuple[str, ...]
    mtp_enforced: bool
    max_block_weight: int


DEPLOYMENTS: tuple[ConsensusDeployment, ...] = (
    ConsensusDeployment(
        name="segwit-style-witness-commitment",
        bit=0,
        start_height=0,
        timeout_height=None,
        active_height=0,
        description="Witness commitment rule for blocks containing witness data.",
    ),
    ConsensusDeployment(
        name="median-time-past-v2",
        bit=1,
        start_height=MTP_ACTIVATION_HEIGHT,
        timeout_height=None,
        active_height=MTP_ACTIVATION_HEIGHT,
        description="Require block timestamp to be strictly greater than the median of recent ancestors.",
    ),
)

# Known checkpoint hooks.  Public testnet operators can append audited hashes as
# the network matures; keeping the structure in code prevents ad hoc hard-coding
# in node policy.
HEADER_CHECKPOINTS: dict[int, str] = {}


def consensus_rules_at_height(height: int) -> ConsensusRuleSet:
    height = int(height)
    active = tuple(d.name for d in DEPLOYMENTS if d.is_active(height))
    return ConsensusRuleSet(
        version=CONSENSUS_VERSION,
        active_deployments=active,
        mtp_enforced=height >= MTP_ACTIVATION_HEIGHT,
        max_block_weight=MAX_BLOCK_WEIGHT,
    )


def deployment_report(height: int) -> dict[str, Any]:
    return {
        "height": int(height),
        "rules": asdict(consensus_rules_at_height(height)),
        "deployments": [asdict(d) | {"active": d.is_active(height)} for d in DEPLOYMENTS],
        "checkpoint_count": len(HEADER_CHECKPOINTS),
    }


def median_time_past(headers: Sequence[Block], *, window: int = 11) -> int:
    """Return the median timestamp of up to ``window`` ancestors."""

    if not headers:
        return 0
    timestamps: list[int] = []
    for block in list(headers)[-max(1, int(window)) :]:
        timestamps.append(int(block.header.timestamp))
    timestamps.sort()
    return timestamps[len(timestamps) // 2]


def validate_median_time_past(block: Block, chain_prefix: Sequence[Block]) -> bool:
    """Return True if the block satisfies the staged MTP rule.

    The rule is only enforced after ``MTP_ACTIVATION_HEIGHT`` so existing testnet
    history and educational fixtures are not invalidated unexpectedly.
    """

    if not consensus_rules_at_height(block.header.height).mtp_enforced:
        return True
    return int(block.header.timestamp) > median_time_past(chain_prefix)


def validate_block_weight_limit(block: Block) -> bool:
    return block_weight(block) <= MAX_BLOCK_WEIGHT


def check_header_checkpoint(block: Block) -> bool:
    expected = HEADER_CHECKPOINTS.get(int(block.header.height))
    return expected is None or expected.lower() == block.hash().lower()


def chainstate_commitment(
    *,
    height: int,
    tip_hash: str,
    utxos: Mapping[str, SpendableOutput],
    consensus_version: int = CONSENSUS_VERSION,
) -> dict[str, Any]:
    """Return a deterministic commitment to the active UTXO set."""

    rows = []
    for outpoint, u in sorted(utxos.items()):
        rows.append(
            "|".join(
                [
                    str(outpoint),
                    str(int(u.output.amount)),
                    str(u.output.address),
                    str(int(bool(u.coinbase))),
                    str(int(u.height)),
                ]
            )
        )
    digest = hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()
    payload = {
        "height": int(height),
        "tip_hash": str(tip_hash),
        "utxo_count": len(rows),
        "utxo_digest": digest,
        "consensus_version": int(consensus_version),
    }
    payload["commitment"] = hashlib.sha256(
        f"{payload['height']}|{payload['tip_hash']}|{payload['utxo_count']}|{digest}|{payload['consensus_version']}".encode()
    ).hexdigest()
    return payload


def audit_cumulative_work(active: Sequence[Block], candidates: Iterable[Sequence[Block]]) -> dict[str, Any]:
    """Explain fork-choice work comparison for candidate branches."""

    active_work = cumulative_work(active) if active else 0
    rows = []
    best: dict[str, Any] = {"kind": "active", "height": active[-1].header.height if active else -1, "work": active_work}
    best_work = active_work
    for index, branch in enumerate(candidates, start=1):
        if not branch:
            continue
        work = cumulative_work(branch)
        row = {
            "candidate": index,
            "height": branch[-1].header.height,
            "tip_hash": branch[-1].hash(),
            "work": work,
            "beats_active": work > active_work,
            "work_delta": work - active_work,
        }
        rows.append(row)
        if work > best_work:
            best_work = work
            best = {"kind": f"candidate:{index}", "height": row["height"], "work": work, "tip_hash": row["tip_hash"]}
    return {
        "active_work": active_work,
        "best": best,
        "candidates": rows,
        "tie_breaker": "first-seen active tip wins ties",
    }


def invalid_block_corpus_summary(root: str = "tests/fixtures/invalid_blocks") -> dict[str, Any]:
    from pathlib import Path

    path = Path(root)
    files = sorted(p.name for p in path.glob("*.json")) if path.exists() else []
    return {"path": str(path), "count": len(files), "files": files}


def invalid_tx_corpus_summary(root: str = "tests/fixtures/invalid_txs") -> dict[str, Any]:
    from pathlib import Path

    path = Path(root)
    files = sorted(p.name for p in path.glob("*.json")) if path.exists() else []
    return {"path": str(path), "count": len(files), "files": files}


ZERO_HASH_CHECKPOINT = ZERO_HASH
